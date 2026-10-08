from pydantic import BaseModel, ConfigDict, StrictInt

from api.schemas.common import Money, Rial


class PaymentMethodOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    fee_bps: int
    fee_fixed: Rial
    # Cap on the percentage part of the fee (integer Rial); null = no cap.
    fee_cap: Rial | None
    settlement_rule: str
    settlement_days: int | None
    is_active: int
    created_at: str
    updated_at: str
    # Paid orders of this method not yet in a settlement; while > 0 the
    # settlement rule cannot change (PATCH is a 409).
    pending_order_count: int


class PaymentMethodCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    # IMMEDIATE | DAYS_AFTER | DAY_OF_NEXT_MONTH (validated in db/, 422 field "settlement_rule").
    settlement_rule: str
    # Empty for IMMEDIATE; 1..365 for DAYS_AFTER; 1..31 for DAY_OF_NEXT_MONTH.
    settlement_days: StrictInt | None = None
    # Basis points of customer_total (150 = 1.5%), 0..10000.
    fee_bps: StrictInt = 0
    fee_fixed: Money = 0


class PaymentMethodUpdate(BaseModel):
    """Only the fields present in the body change; settlement_days may be null
    (required when switching to IMMEDIATE)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    settlement_rule: str | None = None
    settlement_days: StrictInt | None = None
    fee_bps: StrictInt | None = None
    fee_fixed: Money | None = None


class FeePreviewOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method_id: int
    amount: Rial
    transaction_fee: Rial
    expected_amount: Rial
