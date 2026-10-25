import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.purchases import ListItemType, PurchaseCreate, PurchaseDetailOut, PurchaseOut
from db.purchases import list_purchases, record_purchase, require_purchase

router = APIRouter(tags=["purchases"])


@router.get("/purchases", response_model=list[PurchaseOut])
def read_purchases(
    supplier_id: int | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    item_type: ListItemType | None = None,
    item_id: int | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[PurchaseOut]:
    """Purchase invoices, newest first, each with its lines. `item_type` keeps the invoices with a line of that type
    (MATERIAL = STOCK materials, SERVICE, PRODUCT); `item_id` (needs item_type) a line of that item."""
    purchases = list_purchases(
        conn, supplier_id=supplier_id, start_date=start_date, end_date=end_date, item_type=item_type, item_id=item_id
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
