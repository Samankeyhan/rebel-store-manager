from pydantic import BaseModel, ConfigDict

from api.schemas.common import Money


class MaterialOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    type: str
    unit: str
    current_stock: float | None
    unit_cost: int
    is_active: int
    created_at: str
    updated_at: str | None


class MaterialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    unit_cost: Money
    unit: str = "piece"
    initial_stock: float | None = None
