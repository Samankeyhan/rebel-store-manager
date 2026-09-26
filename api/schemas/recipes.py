from pydantic import BaseModel, ConfigDict


class RecipeItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    product_id: int
    material_id: int
    quantity_needed: float
    cost_basis: str
    material_name: str
    material_type: str
    material_unit: str
    material_unit_cost: int


class RecipeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecipeItemOut]
    unit_cost_at_qty_1: int
    unit_cost_at_batch_qty: int
