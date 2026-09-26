from pydantic import BaseModel, ConfigDict

from api.schemas.common import DateStr, Money


class PostageBatchOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    paid_date: str
    total_paid: int
    order_count: int
    notes: str | None
    created_at: str


class PostageEstimateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimate: int
    window: int


class PostageBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_paid: Money
    order_count: int
    paid_date: DateStr | None = None
    notes: str | None = None
