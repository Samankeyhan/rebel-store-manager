from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    category: str
    retail_price: int
    wholesale_price: int
    current_stock: int
    unit_cost: int | None
    is_active: int
    made_to_order: int
    created_at: str
    updated_at: str | None
