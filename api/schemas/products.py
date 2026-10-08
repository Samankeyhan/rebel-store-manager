from pydantic import BaseModel, ConfigDict

from api.schemas.common import Money, Rial


class ProductOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    # Legacy code column from before migration 005 (NULL for newer products).
    # Read category_name instead; this field goes away with that column.
    category: str | None
    category_id: int
    category_name: str
    parent_category_id: int | None
    parent_category_name: str | None
    retail_price: Rial
    wholesale_price: Rial
    current_stock: int
    unit_cost: Rial | None
    is_active: int
    made_to_order: int
    created_at: str
    updated_at: str | None


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category_id: int
    retail_price: Money
    wholesale_price: Money
    made_to_order: bool = False


class ProductPricesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retail_price: Money | None = None
    wholesale_price: Money | None = None


class MadeToOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    made_to_order: bool
