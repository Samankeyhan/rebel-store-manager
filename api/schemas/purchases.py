from typing import Literal

from pydantic import BaseModel, ConfigDict

from api.schemas.common import DateStr, Money, PositiveQuantity, Rial, WholeQuantity

# db/supplier_payments.py METHODS: cash, card to card, bank transfer, cheque, other (not the sales payment methods)
SupplierPaymentMethod = Literal["CASH", "CARD", "BANK_TRANSFER", "CHEQUE", "OTHER"]
# db/supplier_payments.py: computed on read from the purchase total and its allocations
PaymentStatus = Literal["UNPAID", "PARTIAL", "PAID"]
PurchaseStatus = Literal["ACTIVE", "CANCELLED"]


class PurchasePaymentIn(BaseModel):
    """What is paid with a new purchase: FULL (the invoice total), NONE (on credit) or PARTIAL (`amount`, less than the
    total). NONE and PARTIAL need a supplier (422 SUPPLIER_REQUIRED_FOR_CREDIT)."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["FULL", "NONE", "PARTIAL"] = "FULL"
    amount: Money | None = None
    method: SupplierPaymentMethod = "OTHER"
    reference: str | None = None


class PurchasePaymentOut(BaseModel):
    """A payment that paid this purchase: `amount` is the part allocated to it, `payment_amount` the whole payment."""

    model_config = ConfigDict(extra="forbid")

    payment_id: int
    payment_date: str
    method: SupplierPaymentMethod
    reference: str | None
    note: str | None
    amount: Rial
    payment_amount: Rial


class _PurchaseOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    supplier_id: int | None
    invoice_number: str | None
    purchase_date: str
    # the invoice total (it sets the weighted-average cost)
    total_paid: Rial
    unit_cost: Rial
    notes: str | None
    supplier_name: str | None
    status: PurchaseStatus
    cancel_reason: str | None
    cancelled_at: str | None
    replaces_purchase_id: int | None
    replaced_by_purchase_id: int | None
    paid: Rial
    outstanding: Rial
    payment_status: PaymentStatus


class MaterialPurchaseOut(_PurchaseOut):
    material_id: int
    quantity_bought: float
    material_name: str


class ProductPurchaseOut(_PurchaseOut):
    product_id: int
    quantity_bought: int
    product_name: str


class MaterialPurchaseDetailOut(MaterialPurchaseOut):
    payments: list[PurchasePaymentOut]


class ProductPurchaseDetailOut(ProductPurchaseOut):
    payments: list[PurchasePaymentOut]


class MaterialPurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: int
    quantity_bought: PositiveQuantity
    total_paid: Money
    supplier_id: int | None = None
    purchase_date: DateStr | None = None
    notes: str | None = None
    payment: PurchasePaymentIn | None = None


class ProductPurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    quantity_bought: WholeQuantity
    total_paid: Money
    supplier_id: int | None = None
    purchase_date: DateStr | None = None
    notes: str | None = None
    payment: PurchasePaymentIn | None = None
