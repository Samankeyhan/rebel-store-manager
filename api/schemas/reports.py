from pydantic import BaseModel, ConfigDict

from api.schemas.common import Rial


class ProfitAndLossOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items_revenue: Rial
    shipping_revenue: Rial
    total_revenue: Rial
    cogs: Rial
    packaging_cost: Rial
    postage_estimated: Rial
    transaction_fees: Rial
    gross_profit: Rial
    postage_actual: Rial
    postage_variance: Rial
    refund_losses: Rial
    waste_cost: Rial
    operating_expenses: Rial
    net_profit: Rial
    order_count: int


class ProductPerformanceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    product_name: str
    units_sold: int
    total_revenue: Rial
    total_cost: Rial
    total_profit: Rial


class ChannelBreakdownOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    order_count: int
    total_revenue: Rial
    total_profit: Rial


class ShippingSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipping_revenue: Rial
    packaging_cost: Rial
    postage_estimated: Rial
    postage_actual: Rial
    net_shipping_result: Rial
    order_count: int
    shipped_order_count: int
    avg_shipping_revenue: Rial
    avg_packaging_cost: Rial
    avg_postage_actual: Rial
    avg_net_shipping_result: Rial
    net_shipping_result_estimated: Rial
    avg_net_shipping_result_estimated: Rial
    postage_gap: Rial


class ShippingByChannelOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    shipped_order_count: int
    shipping_revenue: Rial
    packaging_cost: Rial
    postage_estimated: Rial
    net: Rial
    net_per_order: Rial


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
    total_amount: Rial
    expense_count: int


class RevenueSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_count: int
    total_revenue: Rial
    total_profit: Rial


class PurchasesSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_purchases_total: Rial
    material_purchases_count: int
    product_purchases_total: Rial
    product_purchases_count: int


class PaymentMethodReportRowOut(BaseModel):
    """One payment method, or (payment_method_id null) orders without one."""

    model_config = ConfigDict(extra="forbid")

    payment_method_id: int | None
    name: str | None
    settlement_rule: str | None
    is_active: int | None
    order_count: int
    customer_total: Rial
    transaction_fees: Rial
    fees_lost_on_returns: Rial
    pending_expected: Rial
    settled_expected: Rial
    settled_received: Rial
    settlement_difference: Rial
