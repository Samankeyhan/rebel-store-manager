import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.production import (
    ProductionBatchDetailOut,
    ProductionBatchListOut,
    ProductionCreate,
)
from db.production import (
    get_production_batch,
    list_production_batches,
    run_production_batch,
)

router = APIRouter(tags=["production"])


@router.get("/production", response_model=list[ProductionBatchListOut])
def read_production_batches(
    product_id: int | None = None, conn: sqlite3.Connection = Depends(get_db)
) -> list[ProductionBatchListOut]:
    return [
        ProductionBatchListOut.model_validate(b)
        for b in list_production_batches(conn, product_id)
    ]


@router.get("/production/{batch_id}", response_model=ProductionBatchDetailOut)
def read_production_batch(
    batch_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> ProductionBatchDetailOut:
    # get_production_batch raises NotFoundError itself.
    return ProductionBatchDetailOut.model_validate(get_production_batch(conn, batch_id))


@router.post("/production", response_model=ProductionBatchDetailOut, status_code=201)
def create_production_batch(
    body: ProductionCreate, conn: sqlite3.Connection = Depends(get_db)
) -> ProductionBatchDetailOut:
    """Run a production batch: consumes recipe materials and adds finished stock.
    production_date defaults to now when omitted."""
    batch_id = run_production_batch(
        conn,
        body.product_id,
        body.quantity_produced,
        notes=body.notes,
        production_date=body.production_date,
    )
    return ProductionBatchDetailOut.model_validate(get_production_batch(conn, batch_id))
