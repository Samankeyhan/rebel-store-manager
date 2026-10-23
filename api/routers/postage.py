import sqlite3

from fastapi import APIRouter, Depends, Response

from api.deps import get_db
from api.schemas.postage import PostageBatchCreate, PostageBatchOut, PostageBatchUpdate, PostageEstimateOut
from db.postage import (
    delete_postage_batch,
    get_current_postage_estimate,
    get_postage_batch,
    list_postage_batches,
    record_postage_batch,
    update_postage_batch,
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


@router.patch("/postage/batches/{batch_id}", response_model=PostageBatchOut)
def patch_postage_batch(
    batch_id: int, body: PostageBatchUpdate, conn: sqlite3.Connection = Depends(get_db)
) -> PostageBatchOut:
    """Only the fields present in the body change. Moves the postage estimate for future orders (frozen order postage is untouched)."""
    update_postage_batch(conn, batch_id, **body.model_dump(exclude_unset=True))
    return PostageBatchOut.model_validate(get_postage_batch(conn, batch_id))


@router.delete("/postage/batches/{batch_id}", status_code=204)
def remove_postage_batch(batch_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Response:
    """Hard delete (the audit log keeps the old row). 409 PERIOD_ALREADY_DISTRIBUTED on a closed day."""
    delete_postage_batch(conn, batch_id)
    return Response(status_code=204)
