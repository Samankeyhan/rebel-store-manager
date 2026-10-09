from pydantic import BaseModel, ConfigDict

from api.schemas.common import DateStr, Money, Rial


class DistributionListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    distribution_date: str
    period_start: str
    period_end: str
    total_profit_available: Rial
    total_amount_distributed: Rial
    notes: str | None


class DistributionShareOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    distribution_id: int
    partner_id: int
    percentage_at_time: float
    amount: Rial
    partner_name: str


class DistributionDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    distribution_date: str
    period_start: str
    period_end: str
    total_profit_available: Rial
    total_amount_distributed: Rial
    notes: str | None
    shares: list[DistributionShareOut]


class UndistributedProfitOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    undistributed_profit: Rial
    as_of: str


class DistributionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: DateStr
    period_end: DateStr
    total_amount_distributed: Money
    distribution_date: DateStr | None = None
    notes: str | None = None
    allow_exceeding: bool = False


class DistributionPreviewShareOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    partner_id: int
    partner_name: str
    percentage_at_time: float
    amount: Rial


class DistributionPreviewOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: str
    period_end: str
    total_amount_distributed: Rial
    total_profit_available: Rial
    undistributed_profit: Rial
    exceeds_undistributed: bool
    shares: list[DistributionPreviewShareOut]
