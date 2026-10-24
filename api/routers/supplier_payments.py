import sqlite3

from fastapi import APIRouter, Depends, Query, Response

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.supplier_payments import (
    AllocationPlanOut,
    PayablesOut,
    SupplierPaymentCreate,
    SupplierPaymentOut,
    SupplierPaymentUpdate,
)
from db.constants import MAX_MONEY
from db.supplier_payments import (
    allocate_oldest_first,
    delete_supplier_payment,
    get_payables,
    get_supplier_payment,
    list_supplier_payments,
    record_supplier_payment,
    update_supplier_payment,
)

router = APIRouter(tags=["supplier payments"])


@router.get("/supplier-payments", response_model=list[SupplierPaymentOut])
def read_supplier_payments(
    supplier_id: int | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[SupplierPaymentOut]:
    """Newest first, each with its allocations; dates are local days on payment_date."""
    payments = list_supplier_payments(conn, supplier_id=supplier_id, start_date=start_date, end_date=end_date)
    return [SupplierPaymentOut.model_validate(p) for p in payments]


@router.get("/supplier-payments/{payment_id}", response_model=SupplierPaymentOut)
def read_supplier_payment(payment_id: int, conn: sqlite3.Connection = Depends(get_db)) -> SupplierPaymentOut:
    return SupplierPaymentOut.model_validate(get_supplier_payment(conn, payment_id))


@router.post("/supplier-payments", response_model=SupplierPaymentOut, status_code=201)
def create_supplier_payment(body: SupplierPaymentCreate, conn: sqlite3.Connection = Depends(get_db)) -> SupplierPaymentOut:
    payment_id = record_supplier_payment(
        conn,
        body.supplier_id,
        body.payment_date,
        body.amount,
        body.method,
        reference=body.reference,
        note=body.note,
        allocations=[a.model_dump() for a in body.allocations] if body.allocations is not None else None,
    )
    return SupplierPaymentOut.model_validate(get_supplier_payment(conn, payment_id))


@router.patch("/supplier-payments/{payment_id}", response_model=SupplierPaymentOut)
def patch_supplier_payment(
    payment_id: int, body: SupplierPaymentUpdate, conn: sqlite3.Connection = Depends(get_db)
) -> SupplierPaymentOut:
    """Only the fields present in the body change (date, method, reference, note)."""
    update_supplier_payment(conn, payment_id, **body.model_dump(exclude_unset=True))
    return SupplierPaymentOut.model_validate(get_supplier_payment(conn, payment_id))


@router.delete("/supplier-payments/{payment_id}", status_code=204)
def remove_supplier_payment(payment_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Response:
    """Hard delete with its allocations (the audit log keeps the rows)."""
    delete_supplier_payment(conn, payment_id)
    return Response(status_code=204)


@router.get("/payables", response_model=PayablesOut)
def read_payables(conn: sqlite3.Connection = Depends(get_db)) -> PayablesOut:
    return PayablesOut.model_validate(get_payables(conn))


@router.get("/payables/allocation-preview", response_model=list[AllocationPlanOut])
def read_allocation_preview(
    amount: int = Query(..., ge=-MAX_MONEY, le=MAX_MONEY, description="the payment in integer Rial"),
    supplier_id: int | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[AllocationPlanOut]:
    """How `amount` would be split over the supplier's unpaid purchases, oldest first (no supplier_id: purchases that
    have no supplier). 409 SUPPLIER_PAYMENT_EXCEEDS_BALANCE when it is more than everything owed."""
    return [AllocationPlanOut.model_validate(a) for a in allocate_oldest_first(conn, supplier_id, amount)]
