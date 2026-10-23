from typing import Literal

from pydantic import BaseModel, ConfigDict

from api.schemas.common import Money, NamedOut, Rial


class MissingMaterialOut(BaseModel):
    """A recipe material whose cost is 0 ("not entered"): why a recipe cost is incomplete."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str


class ProductOut(NamedOut):
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
    # Display only: what one unit costs to make from the recipe today (NULL unless COMPLETE). Never stored.
    recipe_cost: Rial | None
    recipe_cost_status: Literal["NONE", "INCOMPLETE", "COMPLETE"]
    recipe_cost_missing: list[MissingMaterialOut]
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


class ProductCostSet(BaseModel):
    """«ثبت بها»: the unit cost of a product that has none yet (NULL), in Rial (at least 1).
    A product that already has a cost is a 409 COST_ALREADY_SET; 0 or less is a 422 (field "unit_cost")."""

    model_config = ConfigDict(extra="forbid")

    unit_cost: Money


class MadeToOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    made_to_order: bool
