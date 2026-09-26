from pydantic import BaseModel, ConfigDict

from api.schemas.common import Money


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


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
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
