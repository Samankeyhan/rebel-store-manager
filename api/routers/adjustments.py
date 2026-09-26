import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.adjustments import AdjustmentOut
from api.schemas.common import DateStr
from db.adjustments import list_stock_adjustments

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
