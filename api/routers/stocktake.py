import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.stocktake import StocktakeRequest, StocktakeResult
from db.stocktake import apply_stocktake, plan_stocktake

router = APIRouter(tags=["stocktake"])


@router.post("/stocktake/preview", response_model=StocktakeResult)
def preview_stocktake(
    body: StocktakeRequest, conn: sqlite3.Connection = Depends(get_db)
) -> StocktakeResult:
    """What applying this count would do (corrections, cost used, value). Writes nothing."""
    items = [item.model_dump() for item in body.items]
    return StocktakeResult.model_validate(plan_stocktake(conn, items, body.stocktake_date, body.note))


@router.post("/stocktake", response_model=StocktakeResult)
def create_stocktake(
    body: StocktakeRequest, conn: sqlite3.Connection = Depends(get_db)
) -> StocktakeResult:
    """Apply a physical count: every differing item gets an ADJUSTMENT movement in one transaction, or
    nothing is written. Items counted equal to the system quantity are left alone."""
    items = [item.model_dump() for item in body.items]
    return StocktakeResult.model_validate(apply_stocktake(conn, items, body.stocktake_date, body.note))
