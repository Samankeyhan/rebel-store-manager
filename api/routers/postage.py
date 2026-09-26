import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.postage import PostageBatchCreate, PostageBatchOut, PostageEstimateOut
from db.postage import (
    get_current_postage_estimate,
    get_postage_batch,
    list_postage_batches,
    record_postage_batch,
)
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


@router.post("/postage/batches", response_model=PostageBatchOut, status_code=201)
def create_postage_batch(
    body: PostageBatchCreate, conn: sqlite3.Connection = Depends(get_db)
) -> PostageBatchOut:
    batch_id = record_postage_batch(
        conn,
        body.total_paid,
        body.order_count,
        paid_date=body.paid_date,
        notes=body.notes,
    )
    return PostageBatchOut.model_validate(get_postage_batch(conn, batch_id))
