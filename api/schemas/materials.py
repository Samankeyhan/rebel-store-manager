from pydantic import BaseModel, ConfigDict

from api.schemas.common import Money, Quantity, Rial


class MaterialOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    type: str
    unit: str
    current_stock: float | None
    # Quantity in the material's unit; null = no minimum (SERVICE: always null).
    min_stock: float | None
    # 1 = low stock (db/materials.py: active STOCK at stock <= 0 or <= min_stock).
    is_low_stock: int
    unit_cost: Rial
    is_active: int
    category_id: int | None
    category_name: str | None
    parent_category_id: int | None
    parent_category_name: str | None
    created_at: str
    updated_at: str | None


class MaterialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    unit_cost: Money
    unit: str = "piece"
    initial_stock: float | None = None
    category_id: int | None = None
    # Optional minimum stock in the material's unit; null/omitted = none.
    # STOCK only: a SERVICE material with a minimum is a 422 (field "min_stock").
    min_stock: Quantity | None = None


class MaterialUpdate(BaseModel):
    """Only min_stock is editable: omitted = unchanged, null = clear.
    Negative, non-number or a minimum on a SERVICE material: 422 (field "min_stock")."""

    model_config = ConfigDict(extra="forbid")

    min_stock: Quantity | None = None
