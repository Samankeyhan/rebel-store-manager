from pydantic import BaseModel, ConfigDict


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
