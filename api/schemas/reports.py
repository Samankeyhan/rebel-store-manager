from pydantic import BaseModel, ConfigDict


class ProfitAndLossOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items_revenue: int
    shipping_revenue: int
    total_revenue: int
    cogs: int
    packaging_cost: int
    postage_estimated: int
    transaction_fees: int
    gross_profit: int
    postage_actual: int
    postage_variance: int
    refund_losses: int
    waste_cost: int
    operating_expenses: int
    net_profit: int
    order_count: int


class ProductPerformanceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    product_name: str
    units_sold: int
    total_revenue: int
    total_cost: int
    total_profit: int


class ChannelBreakdownOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    order_count: int
    total_revenue: int
    total_profit: int


class ShippingSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipping_revenue: int
    packaging_cost: int
    postage_estimated: int
    postage_actual: int
    net_shipping_result: int
    order_count: int
    shipped_order_count: int
    avg_shipping_revenue: int
    avg_packaging_cost: int
    avg_postage_actual: int
    avg_net_shipping_result: int


class ShippingByChannelOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    shipped_order_count: int
    shipping_revenue: int
    packaging_cost: int
    postage_estimated: int
    net: int
    net_per_order: int


class WasteReportOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: str
    item_name: str
    total_wasted: float
    waste_event_count: int
    cost: float | None
    unknown_cost_count: int


class ExpenseBreakdownOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_name: str
    total_amount: int
    expense_count: int


class RevenueSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_count: int
    total_revenue: int
    total_profit: int
