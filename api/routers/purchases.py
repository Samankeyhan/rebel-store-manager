import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.purchases import (
    MaterialPurchaseCreate,
    MaterialPurchaseDetailOut,
    MaterialPurchaseOut,
    ProductPurchaseCreate,
    ProductPurchaseDetailOut,
    ProductPurchaseOut,
)
from db.errors import ErrorCode, NotFoundError
from db.purchases import (
    get_material_purchase,
    get_product_purchase,
    list_material_purchases,
    list_product_purchases,
    record_material_purchase,
    record_product_purchase,
)

router = APIRouter(tags=["purchases"])


def _not_found(kind: str, purchase_id: int) -> NotFoundError:
    return NotFoundError(
        f"{kind.capitalize()} purchase with id {purchase_id} does not exist",
        code=ErrorCode.PURCHASE_NOT_FOUND,
        details={"purchase_kind": kind, "purchase_id": purchase_id},
    )


@router.get("/purchases/materials", response_model=list[MaterialPurchaseOut])
def read_material_purchases(
    material_id: int | None = None,
    supplier_id: int | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[MaterialPurchaseOut]:
    purchases = list_material_purchases(
        conn,
        material_id=material_id,
        supplier_id=supplier_id,
        start_date=start_date,
        end_date=end_date,
    )
    return [MaterialPurchaseOut.model_validate(p) for p in purchases]


@router.get("/purchases/materials/{purchase_id}", response_model=MaterialPurchaseDetailOut)
def read_material_purchase(
    purchase_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> MaterialPurchaseDetailOut:
    purchase = get_material_purchase(conn, purchase_id)
    if purchase is None:
        raise _not_found("MATERIAL", purchase_id)
    return MaterialPurchaseDetailOut.model_validate(purchase)


@router.get("/purchases/products", response_model=list[ProductPurchaseOut])
def read_product_purchases(
    product_id: int | None = None,
    supplier_id: int | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[ProductPurchaseOut]:
    purchases = list_product_purchases(
        conn,
        product_id=product_id,
        supplier_id=supplier_id,
        start_date=start_date,
        end_date=end_date,
    )
    return [ProductPurchaseOut.model_validate(p) for p in purchases]


@router.get("/purchases/products/{purchase_id}", response_model=ProductPurchaseDetailOut)
def read_product_purchase(
    purchase_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> ProductPurchaseDetailOut:
    purchase = get_product_purchase(conn, purchase_id)
    if purchase is None:
        raise _not_found("PRODUCT", purchase_id)
    return ProductPurchaseDetailOut.model_validate(purchase)


@router.post("/purchases/materials", response_model=MaterialPurchaseDetailOut, status_code=201)
def create_material_purchase(
    body: MaterialPurchaseCreate, conn: sqlite3.Connection = Depends(get_db)
) -> MaterialPurchaseDetailOut:
    purchase_id = record_material_purchase(
        conn,
        body.material_id,
        body.quantity_bought,
        body.total_paid,
        supplier_id=body.supplier_id,
        purchase_date=body.purchase_date,
        notes=body.notes,
        payment=body.payment.model_dump() if body.payment is not None else None,
    )
    return MaterialPurchaseDetailOut.model_validate(get_material_purchase(conn, purchase_id))


@router.post("/purchases/products", response_model=ProductPurchaseDetailOut, status_code=201)
def create_product_purchase(
    body: ProductPurchaseCreate, conn: sqlite3.Connection = Depends(get_db)
) -> ProductPurchaseDetailOut:
    purchase_id = record_product_purchase(
        conn,
        body.product_id,
        body.quantity_bought,
        body.total_paid,
        supplier_id=body.supplier_id,
        purchase_date=body.purchase_date,
        notes=body.notes,
        payment=body.payment.model_dump() if body.payment is not None else None,
    )
    return ProductPurchaseDetailOut.model_validate(get_product_purchase(conn, purchase_id))
