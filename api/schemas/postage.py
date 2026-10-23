from pydantic import BaseModel, ConfigDict, StrictInt

from api.schemas.common import DateStr, Money, Rial


class PostageBatchOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    paid_date: str
    total_paid: Rial
    order_count: int
    notes: str | None
    created_at: str


class PostageEstimateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimate: Rial
    window: int


class PostageBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_paid: Money
    order_count: int
    paid_date: DateStr | None = None
    notes: str | None = None


class PostageBatchUpdate(BaseModel):
    """Only the fields present in the body change. `notes: null` clears them; null on any other field is a 422.
    A new `paid_date` after today is a 422 DATE_IN_FUTURE; a change of `total_paid` or `paid_date` on a closed day is
    a 409 PERIOD_ALREADY_DISTRIBUTED (`order_count` and `notes` are always allowed)."""

    model_config = ConfigDict(extra="forbid")

    total_paid: Money | None = None
    order_count: StrictInt | None = None
    paid_date: DateStr | None = None
    notes: str | None = None
