import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.suppliers import SupplierCreate, SupplierOut, SupplierUpdate
from db.errors import NotFoundError
from db.suppliers import add_supplier, get_supplier, list_suppliers, update_supplier

router = APIRouter(tags=["suppliers"])


@router.get("/suppliers", response_model=list[SupplierOut])
def read_suppliers(conn: sqlite3.Connection = Depends(get_db)) -> list[SupplierOut]:
    return [SupplierOut.model_validate(s) for s in list_suppliers(conn)]


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
def read_supplier(
    supplier_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> SupplierOut:
    return build_supplier(conn, supplier_id)


def build_supplier(conn: sqlite3.Connection, supplier_id: int) -> SupplierOut:
    supplier = get_supplier(conn, supplier_id)
    if supplier is None:
        raise NotFoundError(f"Supplier with id {supplier_id} does not exist")
    return SupplierOut.model_validate(supplier)


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(
    body: SupplierCreate, conn: sqlite3.Connection = Depends(get_db)
) -> SupplierOut:
    supplier_id = add_supplier(
        conn,
        body.name,
        phone=body.phone,
        email=body.email,
        website=body.website,
        notes=body.notes,
    )
    return build_supplier(conn, supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
def patch_supplier(
    supplier_id: int,
    body: SupplierUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> SupplierOut:
    """Only the fields present in the body change. Optional fields (phone,
    email, website, notes) can be cleared with null; name cannot."""
    update_supplier(conn, supplier_id, **body.model_dump(exclude_unset=True))
    return build_supplier(conn, supplier_id)
