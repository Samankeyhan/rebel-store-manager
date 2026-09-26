import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.postage import PostageBatchOut, PostageEstimateOut
from db.postage import get_current_postage_estimate, list_postage_batches
from db.settings import get_setting

router = APIRouter(tags=["postage"])


@router.get("/postage/batches", response_model=list[PostageBatchOut])
def read_postage_batches(
    conn: sqlite3.Connection = Depends(get_db),
) -> list[PostageBatchOut]:
    return [PostageBatchOut.model_validate(b) for b in list_postage_batches(conn)]


@router.get("/postage/estimate", response_model=PostageEstimateOut)
def read_postage_estimate(
    conn: sqlite3.Connection = Depends(get_db),
) -> PostageEstimateOut:
    estimate = get_current_postage_estimate(conn)
    window = int(get_setting(conn, "postage_estimate_window"))
    return PostageEstimateOut(estimate=estimate, window=window)
