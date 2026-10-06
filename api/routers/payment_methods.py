import sqlite3

from fastapi import APIRouter, Depends, Query

from api.deps import get_db
from api.schemas.payment_methods import (
    FeePreviewOut,
    PaymentMethodCreate,
    PaymentMethodOut,
    PaymentMethodUpdate,
)
from db.payment_methods import (
    add_payment_method,
    count_pending_orders,
    deactivate_payment_method,
    get_payment_method,
    list_payment_methods,
    preview_fee,
    reactivate_payment_method,
    update_payment_method,
)

router = APIRouter(tags=["payment methods"])


def _out(conn: sqlite3.Connection, method: dict) -> PaymentMethodOut:
    return PaymentMethodOut.model_validate(
        {**method, "pending_order_count": count_pending_orders(conn, method["id"])}
    )


def _read(conn: sqlite3.Connection, payment_method_id: int) -> PaymentMethodOut:
    # get_payment_method raises NotFoundError itself.
    return _out(conn, get_payment_method(conn, payment_method_id))


@router.get("/payment-methods", response_model=list[PaymentMethodOut])
def read_payment_methods(
    include_inactive: bool = False, conn: sqlite3.Connection = Depends(get_db)
) -> list[PaymentMethodOut]:
    return [_out(conn, m) for m in list_payment_methods(conn, include_inactive=include_inactive)]


@router.post("/payment-methods", response_model=PaymentMethodOut, status_code=201)
def create_payment_method(
    body: PaymentMethodCreate, conn: sqlite3.Connection = Depends(get_db)
) -> PaymentMethodOut:
    method_id = add_payment_method(conn, **body.model_dump())
    return _read(conn, method_id)


@router.get("/payment-methods/{payment_method_id}", response_model=PaymentMethodOut)
def read_payment_method(
    payment_method_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> PaymentMethodOut:
    return _read(conn, payment_method_id)


@router.patch("/payment-methods/{payment_method_id}", response_model=PaymentMethodOut)
def patch_payment_method(
    payment_method_id: int,
    body: PaymentMethodUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> PaymentMethodOut:
    """Only the fields present in the body change. Fee changes are always
    allowed (each order keeps its frozen fee). Changing settlement_rule or
    settlement_days while paid orders are pending settlement is a 409."""
    update_payment_method(conn, payment_method_id, **body.model_dump(exclude_unset=True))
    return _read(conn, payment_method_id)


@router.post("/payment-methods/{payment_method_id}/deactivate", response_model=PaymentMethodOut)
def deactivate(payment_method_id: int, conn: sqlite3.Connection = Depends(get_db)) -> PaymentMethodOut:
    """An inactive method can't be used for a new order or as a channel
    default; its existing orders still get paid and settle normally."""
    deactivate_payment_method(conn, payment_method_id)
    return _read(conn, payment_method_id)


@router.post("/payment-methods/{payment_method_id}/reactivate", response_model=PaymentMethodOut)
def reactivate(payment_method_id: int, conn: sqlite3.Connection = Depends(get_db)) -> PaymentMethodOut:
    reactivate_payment_method(conn, payment_method_id)
    return _read(conn, payment_method_id)


@router.get("/payment-methods/{payment_method_id}/fee-preview", response_model=FeePreviewOut)
def read_fee_preview(
    payment_method_id: int,
    amount: int = Query(..., description="customer_total in Toman"),
    conn: sqlite3.Connection = Depends(get_db),
) -> FeePreviewOut:
    """The fee the method would charge on a customer_total of `amount`
    (half-even on amount × fee_bps / 10000, plus fee_fixed), and the amount
    it would then pay out. A negative amount is a 422 (field "amount")."""
    return FeePreviewOut.model_validate(preview_fee(conn, payment_method_id, amount))
