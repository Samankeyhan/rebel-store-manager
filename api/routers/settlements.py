import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.settlements import (
    PendingMethodOut,
    SettlementCreate,
    SettlementListItemOut,
    SettlementOut,
    SettlementUpdate,
)
from db.settlements import (
    get_pending,
    get_settlement,
    list_settlements,
    record_settlement,
    update_settlement,
)

router = APIRouter(tags=["settlements"])


# Declared before /settlements/{settlement_id} so "pending" is never read as an id.
@router.get("/settlements/pending", response_model=list[PendingMethodOut])
def read_pending(
    payment_method_id: int | None = None, conn: sqlite3.Connection = Depends(get_db)
) -> list[PendingMethodOut]:
    """Paid orders with a payment method that are not yet in a settlement,
    per method (inactive methods included). IMMEDIATE / DAYS_AFTER groups are
    by expected date; DAY_OF_NEXT_MONTH groups are Jalali months."""
    rows = get_pending(conn, payment_method_id=payment_method_id)
    return [PendingMethodOut.model_validate(r) for r in rows]


@router.post("/settlements", response_model=SettlementOut, status_code=201)
def create_settlement(
    body: SettlementCreate, conn: sqlite3.Connection = Depends(get_db)
) -> SettlementOut:
    """Record money a payment method paid out.

    - IMMEDIATE / DAYS_AFTER: `order_ids` (pending orders of this method);
      jalali_year / jalali_month must be absent.
    - DAY_OF_NEXT_MONTH: `jalali_year` + `jalali_month` of a month that has
      ended; every pending order of that month is included. `order_ids` is a
      422 (field "order_ids"): the method settles whole months only.
    """
    settlement_id = record_settlement(conn, **body.model_dump())
    return SettlementOut.model_validate(get_settlement(conn, settlement_id))


@router.get("/settlements", response_model=list[SettlementListItemOut])
def read_settlements(
    payment_method_id: int | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[SettlementListItemOut]:
    """Newest first; start_date / end_date are inclusive days on settled_date."""
    rows = list_settlements(
        conn, payment_method_id=payment_method_id, start_date=start_date, end_date=end_date
    )
    return [SettlementListItemOut.model_validate(r) for r in rows]


@router.get("/settlements/{settlement_id}", response_model=SettlementOut)
def read_settlement(settlement_id: int, conn: sqlite3.Connection = Depends(get_db)) -> SettlementOut:
    return SettlementOut.model_validate(get_settlement(conn, settlement_id))


@router.patch("/settlements/{settlement_id}", response_model=SettlementOut)
def patch_settlement(
    settlement_id: int,
    body: SettlementUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> SettlementOut:
    """Correct amount_received, settled_date or note; only fields present
    in the body change."""
    update_settlement(conn, settlement_id, **body.model_dump(exclude_unset=True))
    return SettlementOut.model_validate(get_settlement(conn, settlement_id))
