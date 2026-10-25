from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Strict

from api.schemas.common import DateStr, Money, Rial
from api.schemas.purchases import PaymentStatus, SupplierPaymentMethod


class AllocationIn(BaseModel):
    """The part of a payment that pays one purchase (a purchase invoice)."""

    model_config = ConfigDict(extra="forbid")

    purchase_id: Annotated[int, Strict()]
    amount: Money


class SupplierPaymentCreate(BaseModel):
    """Money paid to a supplier (supplier_id null: purchases that have no supplier). `allocations` must add up to
    `amount` exactly; omitted = oldest unpaid purchases first. No advances: never more than what is owed."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: int | None
    payment_date: DateStr
    amount: Money
    method: SupplierPaymentMethod
    reference: str | None = None
    note: str | None = None
    allocations: list[AllocationIn] | None = None


class SupplierPaymentUpdate(BaseModel):
    """Only these change; the amount and the allocations never do (delete and record again)."""

    model_config = ConfigDict(extra="forbid")

    payment_date: DateStr | None = None
    method: SupplierPaymentMethod | None = None
    reference: str | None = None
    note: str | None = None


class AllocationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    purchase_id: int
    amount: Rial
    invoice_number: str | None
    purchase_date: str
    item_names: list[str]


class SupplierPaymentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    supplier_id: int | None
    supplier_name: str | None
    payment_date: str
    amount: Rial
    method: SupplierPaymentMethod
    reference: str | None
    note: str | None
    created_at: str
    updated_at: str | None
    allocations: list[AllocationOut]


class OpenPurchaseOut(BaseModel):
    """A purchase invoice that still owes something."""

    model_config = ConfigDict(extra="forbid")

    purchase_id: int
    invoice_number: str | None
    purchase_date: str
    item_names: list[str]
    total: Rial
    paid: Rial
    outstanding: Rial
    payment_status: PaymentStatus


class PayablesSupplierOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: int | None
    supplier_name: str | None
    purchases_total: Rial
    paid_total: Rial
    outstanding: Rial
    oldest_unpaid_date: str
    open_purchases: list[OpenPurchaseOut]


class PayablesOut(BaseModel):
    """Suppliers still owed something, largest debt first."""

    model_config = ConfigDict(extra="forbid")

    outstanding_total: Rial
    suppliers: list[PayablesSupplierOut]


class AllocationPlanOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_id: int
    amount: Rial
