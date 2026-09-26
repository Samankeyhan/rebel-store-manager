import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.suppliers import SupplierOut
from db.errors import NotFoundError
from db.suppliers import get_supplier, list_suppliers

router = APIRouter(tags=["suppliers"])


@router.get("/suppliers", response_model=list[SupplierOut])
def read_suppliers(conn: sqlite3.Connection = Depends(get_db)) -> list[SupplierOut]:
    return [SupplierOut.model_validate(s) for s in list_suppliers(conn)]


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
def read_supplier(
    supplier_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> SupplierOut:
    supplier = get_supplier(conn, supplier_id)
    if supplier is None:
        raise NotFoundError(f"Supplier with id {supplier_id} does not exist")
    return SupplierOut.model_validate(supplier)
