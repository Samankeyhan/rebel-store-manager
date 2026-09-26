from pydantic import BaseModel, ConfigDict


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
