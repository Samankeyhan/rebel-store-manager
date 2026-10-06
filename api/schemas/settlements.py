from pydantic import BaseModel, ConfigDict, StrictInt

from api.schemas.common import DateStr, Money


class PendingOrderOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    invoice_number: str | None
    order_date: str
    paid_date: str
    customer_name: str | None
    channel: str
    customer_total: int
    transaction_fee: int
    expected_amount: int
    expected_settlement_date: str


class PendingDateGroupOut(BaseModel):
    """IMMEDIATE / DAYS_AFTER: pending orders sharing one expected date."""

    model_config = ConfigDict(extra="forbid")

    expected_date: str
    due: bool
    overdue: bool
    order_count: int
    customer_total_sum: int
    fee_sum: int
    expected_amount: int
    orders: list[PendingOrderOut]


class PendingMonthGroupOut(BaseModel):
    """DAY_OF_NEXT_MONTH: one Jalali month, settled as a whole once it has ended."""

    model_config = ConfigDict(extra="forbid")

    jalali_year: int
    jalali_month: int
    month_first_day: str
    month_last_day: str
    expected_date: str
    month_ended: bool
    can_settle: bool
    due: bool
    overdue: bool
    order_count: int
    customer_total_sum: int
    fee_sum: int
    expected_amount: int
    orders: list[PendingOrderOut]


class PendingMethodOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method_id: int
    name: str
    settlement_rule: str
    settlement_days: int | None
    is_active: int
    total_expected: int
    groups: list[PendingDateGroupOut | PendingMonthGroupOut]


class SettlementOrderOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    invoice_number: str | None
    order_date: str
    paid_date: str
    customer_name: str | None
    channel: str
    status: str
    customer_total: int
    transaction_fee: int
    expected_amount: int


class SettlementListItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    payment_method_id: int
    payment_method_name: str
    settlement_rule: str
    settled_date: str
    jalali_year: int | None
    jalali_month: int | None
    expected_amount: int
    amount_received: int
    # amount_received - expected_amount, computed in db/ on read.
    difference: int
    note: str | None
    created_at: str
    order_count: int


class SettlementOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    payment_method_id: int
    payment_method_name: str
    settlement_rule: str
    settled_date: str
    jalali_year: int | None
    jalali_month: int | None
    expected_amount: int
    amount_received: int
    difference: int
    note: str | None
    created_at: str
    orders: list[SettlementOrderOut]


class SettlementCreate(BaseModel):
    """IMMEDIATE / DAYS_AFTER: give order_ids. DAY_OF_NEXT_MONTH: give
    jalali_year and jalali_month; the server takes every pending order of
    that month."""

    model_config = ConfigDict(extra="forbid")

    payment_method_id: StrictInt
    settled_date: DateStr
    amount_received: Money
    note: str | None = None
    order_ids: list[StrictInt] | None = None
    jalali_year: StrictInt | None = None
    jalali_month: StrictInt | None = None


class SettlementUpdate(BaseModel):
    """Only the fields present in the body change; note may be null. Which
    orders a settlement holds, and its expected_amount, never change."""

    model_config = ConfigDict(extra="forbid")

    amount_received: Money | None = None
    settled_date: DateStr | None = None
    note: str | None = None
