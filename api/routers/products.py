import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.products import (
    MadeToOrderUpdate,
    ProductCreate,
    ProductOut,
    ProductPricesUpdate,
)
from db.errors import NotFoundError
from db.products import (
    add_product,
    deactivate_product,
    get_product,
    list_products,
    set_made_to_order,
    update_product_prices,
)

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
    return build_product(conn, product_id)


def build_product(conn: sqlite3.Connection, product_id: int) -> ProductOut:
    product = get_product(conn, product_id)
    if product is None:
        raise NotFoundError(f"Product with id {product_id} does not exist")
    return ProductOut.model_validate(product)


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(
    body: ProductCreate, conn: sqlite3.Connection = Depends(get_db)
) -> ProductOut:
    product_id = add_product(
        conn,
        name=body.name,
        category=body.category,
        retail_price=body.retail_price,
        wholesale_price=body.wholesale_price,
        made_to_order=body.made_to_order,
    )
    return build_product(conn, product_id)


@router.patch("/products/{product_id}/prices", response_model=ProductOut)
def update_prices(
    product_id: int,
    body: ProductPricesUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> ProductOut:
    """Omitted (or null) prices are left unchanged."""
    update_product_prices(
        conn,
        product_id,
        retail_price=body.retail_price,
        wholesale_price=body.wholesale_price,
    )
    return build_product(conn, product_id)


@router.post("/products/{product_id}/deactivate", response_model=ProductOut)
def deactivate(product_id: int, conn: sqlite3.Connection = Depends(get_db)) -> ProductOut:
    # deactivate_product doesn't check existence; build_product 404s instead.
    deactivate_product(conn, product_id)
    return build_product(conn, product_id)


@router.post("/products/{product_id}/made-to-order", response_model=ProductOut)
def update_made_to_order(
    product_id: int,
    body: MadeToOrderUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> ProductOut:
    set_made_to_order(conn, product_id, body.made_to_order)
    return build_product(conn, product_id)
