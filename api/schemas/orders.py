from typing import Literal

from pydantic import BaseModel, ConfigDict

from api.schemas.common import DateStr, Money


class OrderListItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    invoice_number: str | None
    order_date: str
    status: str
    channel: str
    customer_name: str | None
    shipping_charge: int
    postage_cost: int
    transaction_fee: int
    notes: str | None
    packaging_kit_id: int | None
    packaging_cost: int
    stock_committed: int
    customer_total: int
    profit: int | None


class OrderOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    invoice_number: str | None
    order_date: str
    status: str
    channel: str
    customer_name: str | None
    shipping_charge: int
    postage_cost: int
    transaction_fee: int
    notes: str | None
    packaging_kit_id: int | None
    packaging_cost: int
    stock_committed: int


class OrderItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    order_id: int
    product_id: int
    quantity: int
    list_price: int
    discount_amount: int
    discount_reason: str | None
    unit_price: int
    unit_cost_at_time: int
    product_name: str


class OrderDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: OrderOut
    items: list[OrderItemOut]
    customer_total: int
    profit: int


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
    transaction_fee: Money = 0
    notes: str | None = None
    status: str = "COMPLETED"


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class OrderReturn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["CANCELLED", "REFUNDED"]
    reason: str | None = None
