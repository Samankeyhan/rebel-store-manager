from pydantic import BaseModel, ConfigDict


class KitOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    is_active: int
    created_at: str
    updated_at: str | None


class KitItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    kit_id: int
    material_id: int
    quantity: float
    material_name: str
    material_unit_cost: int


class KitDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    is_active: int
    created_at: str
    updated_at: str | None
    items: list[KitItemOut]
    kit_cost: int
