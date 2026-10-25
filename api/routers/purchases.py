import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.purchases import (
    ListItemType,
    PurchaseCancel,
    PurchaseCancelPreviewOut,
    PurchaseCorrection,
    PurchaseCreate,
    PurchaseDetailOut,
    PurchaseOut,
    PurchaseUpdate,
)
from db.purchase_cancel import cancel_purchase, correct_purchase, plan_cancel_purchase
from db.purchases import list_purchases, record_purchase, require_purchase, update_purchase

router = APIRouter(tags=["purchases"])


@router.get("/purchases", response_model=list[PurchaseOut])
def read_purchases(
    supplier_id: int | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    item_type: ListItemType | None = None,
    item_id: int | None = None,
    include_cancelled: bool = False,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[PurchaseOut]:
    """Purchase invoices, newest first, each with its lines. `item_type` keeps the invoices with a line of that type
    (MATERIAL = STOCK materials, SERVICE, PRODUCT); `item_id` (needs item_type) a line of that item. CANCELLED
    invoices are left out unless include_cancelled=true."""
    purchases = list_purchases(
        conn, supplier_id=supplier_id, start_date=start_date, end_date=end_date, item_type=item_type, item_id=item_id,
        include_cancelled=include_cancelled,
    )
    return [PurchaseOut.model_validate(p) for p in purchases]


@router.get("/purchases/{purchase_id}", response_model=PurchaseDetailOut)
def read_purchase(purchase_id: int, conn: sqlite3.Connection = Depends(get_db)) -> PurchaseDetailOut:
    return PurchaseDetailOut.model_validate(require_purchase(conn, purchase_id))


@router.post("/purchases", response_model=PurchaseDetailOut, status_code=201)
def create_purchase(body: PurchaseCreate, conn: sqlite3.Connection = Depends(get_db)) -> PurchaseDetailOut:
    """One supplier invoice with one or more lines (STOCK materials, services, products), one payment choice."""
    purchase_id = record_purchase(
        conn,
        [line.model_dump() for line in body.lines],
        supplier_id=body.supplier_id,
        purchase_date=body.purchase_date,
        notes=body.notes,
        payment=body.payment.model_dump() if body.payment is not None else None,
    )
    return PurchaseDetailOut.model_validate(require_purchase(conn, purchase_id))


@router.patch("/purchases/{purchase_id}", response_model=PurchaseDetailOut)
def patch_purchase(purchase_id: int, body: PurchaseUpdate, conn: sqlite3.Connection = Depends(get_db)) -> PurchaseDetailOut:
    """Only the fields present in the body change (supplier, day, note); a closed day does not refuse them."""
    update_purchase(conn, purchase_id, **body.model_dump(exclude_unset=True))
    return PurchaseDetailOut.model_validate(require_purchase(conn, purchase_id))


@router.get("/purchases/{purchase_id}/cancel-preview", response_model=PurchaseCancelPreviewOut)
def read_cancel_preview(purchase_id: int, conn: sqlite3.Connection = Depends(get_db)) -> PurchaseCancelPreviewOut:
    """Read-only: what cancelling this purchase would take out (each line's stock and the cost it gets back), the
    payments that would go with it, and every rule that refuses it now (`blockers`)."""
    return PurchaseCancelPreviewOut.model_validate(plan_cancel_purchase(conn, purchase_id))


@router.post("/purchases/{purchase_id}/cancel", response_model=PurchaseDetailOut)
def cancel(purchase_id: int, body: PurchaseCancel, conn: sqlite3.Connection = Depends(get_db)) -> PurchaseDetailOut:
    """Cancel the whole purchase entered by mistake. 409 with the codes of `cancel-preview`; 422 VOID_REASON_REQUIRED
    for a blank reason."""
    cancel_purchase(conn, purchase_id, body.reason, with_payments=body.with_payments)
    return PurchaseDetailOut.model_validate(require_purchase(conn, purchase_id))


@router.post("/purchases/{purchase_id}/correct", response_model=PurchaseDetailOut, status_code=201)
def correct(purchase_id: int, body: PurchaseCorrection, conn: sqlite3.Connection = Depends(get_db)) -> PurchaseDetailOut:
    """Cancel the purchase and record the right one in its place (one operation); returns the new purchase. Any
    refusal (the cancel's, the new purchase's, a closed new day) leaves both as they were."""
    new_id = correct_purchase(
        conn,
        purchase_id,
        body.reason,
        [line.model_dump() for line in body.lines],
        supplier_id=body.supplier_id,
        purchase_date=body.purchase_date,
        notes=body.notes,
        payment=body.payment.model_dump() if body.payment is not None else None,
    )
    return PurchaseDetailOut.model_validate(require_purchase(conn, new_id))
