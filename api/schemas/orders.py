from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from api.schemas.common import DateStr, Money, Rial, WholeQuantity


class OrderListItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    invoice_number: str | None
    order_date: str
    status: str
    channel: str
    customer_name: str | None
    shipping_charge: Rial
    postage_cost: Rial
    transaction_fee: Rial
    notes: str | None
    packaging_kit_id: int | None
    packaging_cost: Rial
    stock_committed: int
    # Migration 008: payment method and settlement state. NULL on orders
    # recorded before it; paid/expected dates are local calendar days.
    payment_method_id: int | None
    payment_reference: str | None
    paid_date: str | None
    expected_settlement_date: str | None
    paid_jalali_year: int | None
    paid_jalali_month: int | None
    settlement_id: int | None
    payment_method_name: str | None
    # Migration 014: a VOIDED order's reason and moment (UTC), and on a correction the
    # voided order it replaces. NULL otherwise.
    void_reason: str | None
    voided_at: str | None
    replaces_order_id: int | None
    customer_total: Rial
    profit: Rial | None


class OrderOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    invoice_number: str | None
    order_date: str
    status: str
    channel: str
    customer_name: str | None
    shipping_charge: Rial
    postage_cost: Rial
    transaction_fee: Rial
    notes: str | None
    packaging_kit_id: int | None
    packaging_cost: Rial
    stock_committed: int
    # Migration 008: payment method and settlement state. NULL on orders
    # recorded before it; paid/expected dates are local calendar days.
    payment_method_id: int | None
    payment_reference: str | None
    paid_date: str | None
    expected_settlement_date: str | None
    paid_jalali_year: int | None
    paid_jalali_month: int | None
    settlement_id: int | None
    payment_method_name: str | None
    # Migration 014: a VOIDED order's reason and moment (UTC), and on a correction the
    # voided order it replaces. NULL otherwise.
    void_reason: str | None
    voided_at: str | None
    replaces_order_id: int | None
    # Both sides of a correction: the invoice number of the order this one replaces,
    # and the order that replaced this one (None when there is none).
    replaces_invoice_number: str | None
    replaced_by_order_id: int | None
    replaced_by_invoice_number: str | None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    order_id: int
    product_id: int
    quantity: int
    list_price: Rial
    discount_amount: Rial
    discount_reason: str | None
    list_unit_price: Rial = Field(
        description="List price of one unit (list_price ÷ quantity, exact): what screens "
        "and the invoice show. Integer Rial."
    )
    unit_price: Rial = Field(
        description="Legacy: floor((list_price - discount_amount) / quantity), integer "
        "Rial. Not the list price (the unit_price sent when recording is); do not show it, "
        "use list_unit_price."
    )
    unit_cost_at_time: Rial
    product_name: str


class OrderDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: OrderOut
    items: list[OrderItemOut]
    customer_total: Rial
    profit: Rial


class OrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    quantity: WholeQuantity
    unit_price: Money
    discount_amount: Money = 0
    discount_reason: str | None = None


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    items: list[OrderItemCreate]
    customer_name: str | None = None
    # The sale day: omitted = now. A past day backdates the sale (cost, stock and
    # packaging stay as of today, accounting-rules section 7); a day after today is
    # a 422 DATE_IN_FUTURE on field order_date.
    order_date: DateStr | None = None
    # null = use the channel default; 0 = a real zero override.
    shipping_charge: Money | None = None
    # "default" = the channel's default kit; null = no packaging; int = that kit.
    packaging_kit_id: int | Literal["default"] | None = "default"
    # null = use the channel default (current estimate if the channel applies
    # postage, else 0); 0 = a real zero override.
    postage_cost: Money | None = None
    # null (or omitted) = computed from the payment method (0 with no method);
    # an integer, including 0, overrides it.
    transaction_fee: Money | None = None
    notes: str | None = None
    status: str = "COMPLETED"
    # "default" = the channel's default payment method (none if it has no
    # default); null = no payment method; int = that method (must be active).
    payment_method_id: StrictInt | Literal["default"] | None = "default"
    payment_reference: str | None = None
    # Only for a PAID/COMPLETED order: the local day the money was paid
    # (default: the local day of order_date, or today). Never in the future.
    paid_date: DateStr | None = None


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    # Only when the order becomes paid (DRAFT/PENDING -> PAID/COMPLETED);
    # default today. Anything else with a paid_date is a 422.
    paid_date: DateStr | None = None


class OrderPaidDateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paid_date: DateStr


class OrderReturn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["CANCELLED", "REFUNDED"]
    reason: str | None = None


class OrderVoid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Required; why the sale was entered by mistake (stored form, at most 500 characters).
    reason: str


class OrderCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    # The corrected sale, exactly as POST /orders takes it (status PENDING, PAID or COMPLETED).
    order: OrderCreate


class VoidBlockerOut(BaseModel):
    """A rule that refuses the void now: the ErrorCode the void would answer with, and its details."""

    model_config = ConfigDict(extra="forbid")

    code: str
    details: dict[str, str | int | None]


class VoidProductOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int
    name: str
    quantity: int
    unit_cost_before: Rial | None
    unit_cost_after: Rial | None
    # 1 = every unit comes back at its frozen cost; 0 = some at today's cost (an order from before section 20).
    frozen_cost_known: int


class VoidMaterialOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int
    name: str
    unit: str
    quantity: float
    # PACKAGING / PRODUCTION_CONSUMPTION -> quantity put back for that reason.
    reasons: dict[str, float]
    unit_cost_before: Rial | None
    unit_cost_after: Rial | None
    frozen_cost_known: int


class VoidPreviewOut(BaseModel):
    """What voiding the order would put back and take out of the figures; `blockers` is empty when it may be voided."""

    model_config = ConfigDict(extra="forbid")

    order_id: int
    invoice_number: str | None
    status: str
    blockers: list[VoidBlockerOut]
    products: list[VoidProductOut]
    materials: list[VoidMaterialOut]
    customer_total: Rial
    profit: Rial
    transaction_fee: Rial
    pending_settlement: int
    order_day: str
    order_jalali_year: int
    order_jalali_month: int
