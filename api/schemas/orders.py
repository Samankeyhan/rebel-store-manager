from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt

from api.schemas.common import DateStr, Money, Rial


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


class OrderItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    order_id: int
    product_id: int
    quantity: int
    list_price: Rial
    discount_amount: Rial
    discount_reason: str | None
    unit_price: Rial
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
    quantity: int
    unit_price: Money
    discount_amount: Money = 0
    discount_reason: str | None = None


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    items: list[OrderItemCreate]
    customer_name: str | None = None
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
