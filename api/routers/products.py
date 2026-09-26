import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.products import ProductOut
from db.errors import NotFoundError
from db.products import get_product, list_products

router = APIRouter(tags=["products"])


@router.get("/products", response_model=list[ProductOut])
def read_products(
    active_only: bool = True, conn: sqlite3.Connection = Depends(get_db)
) -> list[ProductOut]:
    return [ProductOut.model_validate(p) for p in list_products(conn, active_only)]


@router.get("/products/{product_id}", response_model=ProductOut)
def read_product(
    product_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> ProductOut:
    product = get_product(conn, product_id)
    if product is None:
        raise NotFoundError(f"Product with id {product_id} does not exist")
    return ProductOut.model_validate(product)
