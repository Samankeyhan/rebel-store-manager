import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.adjustments import AdjustmentCreate, AdjustmentOut
from api.schemas.common import DateStr
from db.adjustments import (
    get_stock_movement,
    list_stock_adjustments,
    record_stock_adjustment,
)

router = APIRouter(tags=["adjustments"])


@router.get("/adjustments", response_model=list[AdjustmentOut])
def read_adjustments(
    item_type: str | None = None,
    reason: str | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[AdjustmentOut]:
    adjustments = list_stock_adjustments(
        conn, item_type=item_type, reason=reason, start_date=start_date, end_date=end_date
    )
    return [AdjustmentOut.model_validate(a) for a in adjustments]


@router.post("/adjustments", response_model=AdjustmentOut, status_code=201)
def create_adjustment(
    body: AdjustmentCreate, conn: sqlite3.Connection = Depends(get_db)
) -> AdjustmentOut:
    """Record a WASTE write-off (quantity_change < 0) or an ADJUSTMENT correction.
    unit_cost only matters for a positive ADJUSTMENT (weighted-average blend)."""
    movement_id = record_stock_adjustment(
        conn,
        body.item_type,
        body.item_id,
        body.quantity_change,
        body.reason,
        unit_cost=body.unit_cost,
        notes=body.notes,
        movement_date=body.movement_date,
    )
    return AdjustmentOut.model_validate(get_stock_movement(conn, movement_id))
