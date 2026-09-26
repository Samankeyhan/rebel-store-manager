import sqlite3
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.orders import (
    OrderCreate,
    OrderDetailOut,
    OrderListItemOut,
    OrderReturn,
    OrderStatusUpdate,
)
from db.orders import (
    USE_CHANNEL_DEFAULT,
    get_order,
    list_orders,
    record_order,
    update_order_status,
)
from db.returns import process_return
from pdf.invoice import generate_invoice_pdf

router = APIRouter(tags=["orders"])


@router.get("/orders", response_model=list[OrderListItemOut])
def read_orders(
    channel: str | None = None,
    status: str | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[OrderListItemOut]:
    orders = list_orders(
        conn, channel=channel, status=status, start_date=start_date, end_date=end_date
    )
    return [OrderListItemOut.model_validate(o) for o in orders]


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
def read_order(order_id: int, conn: sqlite3.Connection = Depends(get_db)) -> OrderDetailOut:
    # get_order raises NotFoundError itself.
    return OrderDetailOut.model_validate(get_order(conn, order_id))


@router.post("/orders", response_model=OrderDetailOut, status_code=201)
def create_order(
    body: OrderCreate, conn: sqlite3.Connection = Depends(get_db)
) -> OrderDetailOut:
    """Record a sales order.

    **packaging_kit_id** has three cases:
    - `"default"` (or omitted): use the channel's default packaging kit (none if
      the channel has no default).
    - `null`: no packaging at all; packaging_cost is 0.
    - an integer: use that kit.

    **shipping_charge** and **postage_cost**: `null` (or omitted) means *use the
    channel default*, not zero. shipping_charge defaults to the
    default_shipping_charge setting if the channel applies shipping, else 0;
    postage_cost defaults to the current postage estimate if the channel
    applies postage, else 0. Sending `0` is a real zero override.

    DRAFT orders commit no stock and freeze no costs until they leave DRAFT.
    """
    if body.packaging_kit_id == "default":
        packaging_kit_id = USE_CHANNEL_DEFAULT
    else:
        packaging_kit_id = body.packaging_kit_id

    order_id = record_order(
        conn,
        channel=body.channel,
        items=[item.model_dump() for item in body.items],
        customer_name=body.customer_name,
        order_date=body.order_date,
        shipping_charge=body.shipping_charge,
        packaging_kit_id=packaging_kit_id,
        postage_cost=body.postage_cost,
        transaction_fee=body.transaction_fee,
        notes=body.notes,
        status=body.status,
    )
    return OrderDetailOut.model_validate(get_order(conn, order_id))


@router.post("/orders/{order_id}/status", response_model=OrderDetailOut)
def change_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> OrderDetailOut:
    """Move an order forward (DRAFT → PENDING/PAID/COMPLETED, PENDING →
    PAID/COMPLETED, PAID → COMPLETED). Anything else is a 409. CANCELLED and
    REFUNDED go through /orders/{order_id}/return."""
    update_order_status(conn, order_id, body.status)
    return OrderDetailOut.model_validate(get_order(conn, order_id))


@router.post("/orders/{order_id}/return", response_model=OrderDetailOut)
def return_order(
    order_id: int,
    body: OrderReturn,
    conn: sqlite3.Connection = Depends(get_db),
) -> OrderDetailOut:
    """Cancel (from DRAFT/PENDING/PAID) or refund (from PAID/COMPLETED) an order,
    restoring stock. Any other starting status is a 409."""
    process_return(conn, order_id, body.status, reason=body.reason)
    return OrderDetailOut.model_validate(get_order(conn, order_id))


@router.get(
    "/orders/{order_id}/invoice.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def read_invoice_pdf(order_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Response:
    """The customer-facing Persian invoice PDF for an order."""
    # generate_invoice_pdf re-raises a missing order as a plain ValueError
    # (a 500 here), so check first: get_order raises NotFoundError (404).
    get_order(conn, order_id)
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = Path(generate_invoice_pdf(conn, order_id, output_dir=tmp_dir))
        content = pdf_path.read_bytes()
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_path.name}"'},
    )
