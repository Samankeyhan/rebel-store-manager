from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.common import DateStr, Money, PositiveQuantity, Rial

# db/supplier_payments.py METHODS: cash, card to card, bank transfer, cheque, other (not the sales payment methods)
SupplierPaymentMethod = Literal["CASH", "CARD", "BANK_TRANSFER", "CHEQUE", "OTHER"]
# db/supplier_payments.py: computed on read from the purchase total and its allocations
PaymentStatus = Literal["UNPAID", "PARTIAL", "PAID"]
PurchaseStatus = Literal["ACTIVE", "CANCELLED"]
# a line is a MATERIAL (a STOCK material or a service) or a PRODUCT
LineKind = Literal["MATERIAL", "PRODUCT"]
# what a line's item is: a stock material, a service (no stock) or a finished product
LineItemType = Literal["STOCK", "SERVICE", "PRODUCT"]
# the filter of the purchases list: invoices with a line of this type (MATERIAL = STOCK materials)
ListItemType = Literal["MATERIAL", "SERVICE", "PRODUCT"]


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


class PurchaseLineIn(BaseModel):
    """One item of a purchase. `quantity_bought` must be whole for a PRODUCT; a service line needs a total above 0
    (it sets the service's price)."""

    model_config = ConfigDict(extra="forbid")

    kind: LineKind
    item_id: int
    quantity_bought: PositiveQuantity
    # the line total in integer Rial
    total_paid: Money


class PurchaseLineOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    kind: LineKind
    item_type: LineItemType
    item_id: int
    item_name: str
    # the material's unit; null for a product
    unit: str | None
    quantity_bought: float
    total_paid: Rial
    unit_cost: Rial


class PurchaseOut(BaseModel):
    """A purchase invoice: one supplier bill with its lines (`total` = Σ line totals)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    invoice_number: str | None
    supplier_id: int | None
    supplier_name: str | None
    purchase_date: str
    notes: str | None
    status: PurchaseStatus
    cancel_reason: str | None
    cancelled_at: str | None
    replaces_invoice_id: int | None
    replaced_by_invoice_id: int | None
    total: Rial
    paid: Rial
    outstanding: Rial
    payment_status: PaymentStatus
    lines: list[PurchaseLineOut]


class PurchaseDetailOut(PurchaseOut):
    payments: list[PurchasePaymentOut]


class PurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: int | None = None
    purchase_date: DateStr | None = None
    notes: str | None = None
    payment: PurchasePaymentIn | None = None
    lines: list[PurchaseLineIn] = Field(min_length=1)
