from pydantic import BaseModel, ConfigDict


class DistributionListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    distribution_date: str
    period_start: str
    period_end: str
    total_profit_available: int
    total_amount_distributed: int
    notes: str | None


class DistributionShareOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    distribution_id: int
    partner_id: int
    percentage_at_time: float
    amount: int
    partner_name: str


class DistributionDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    distribution_date: str
    period_start: str
    period_end: str
    total_profit_available: int
    total_amount_distributed: int
    notes: str | None
    shares: list[DistributionShareOut]


class UndistributedProfitOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    undistributed_profit: int
    as_of: str
