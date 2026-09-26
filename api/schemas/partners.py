from pydantic import BaseModel, ConfigDict


class PartnerOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    current_percentage: float
    phone: str | None
    email: str | None
    notes: str | None
    is_active: int
    created_at: str
    updated_at: str | None


class PartnerPayoutOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percentage_at_time: float
    amount: int
    period_start: str
    period_end: str
    distribution_date: str


class PartnerTotalOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    partner_name: str
    total_received: int
    distribution_count: int
