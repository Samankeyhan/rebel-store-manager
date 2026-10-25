from typing import Literal

from pydantic import BaseModel, ConfigDict

from api.schemas.common import Rial
from api.schemas.products import MissingMaterialOut


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
    postage_committed: Rial
    postage_variance: Rial
    refund_losses: Rial
    refund_fee_losses: Rial
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
    # Display only, next to the frozen total_cost: today's stored cost and recipe estimate (not in any total).
    unit_cost: Rial | None
    recipe_cost: Rial | None
    recipe_cost_status: Literal["NONE", "INCOMPLETE", "COMPLETE"]
    recipe_cost_missing: list[MissingMaterialOut]


class ChannelBreakdownOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    order_count: int
    total_revenue: Rial
    total_profit: Rial
    avg_order_value: Rial


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
    item_id: int
    item_name: str
    # materials.unit; "piece" for a product (whole units).
    unit: str
    total_wasted: float
    waste_event_count: int
    # Integer Rial, rounded half-even per item; the P&L waste_cost is their sum.
    cost: Rial | None
    unknown_cost_count: int


class ExpenseBreakdownOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: int
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

    # purchase lines in the range: STOCK materials, services (no stock) and products, kept apart (rules section 9)
    material_purchases_total: Rial
    material_purchases_count: int
    service_purchases_total: Rial
    service_purchases_count: int
    product_purchases_total: Rial
    product_purchases_count: int
    # the purchase invoices dated in the range
    purchase_invoices_count: int
    # cash and debt, never P&L: payments to suppliers by payment_date in the range, and what is owed now (any range)
    supplier_payments_total: Rial
    supplier_payments_count: int
    payables_outstanding: Rial


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
