from pydantic import BaseModel, ConfigDict

from api.schemas.common import NamedOut, PositiveQuantity, Rial


class KitOut(NamedOut):
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
    material_unit_cost: Rial


class KitDetailOut(NamedOut):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    is_active: int
    created_at: str
    updated_at: str | None
    items: list[KitItemOut]
    kit_cost: Rial


class KitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class KitItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: int
    quantity: PositiveQuantity


class KitItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: PositiveQuantity
