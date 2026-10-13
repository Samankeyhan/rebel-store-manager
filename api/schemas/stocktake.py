from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.common import DateStr, Money, Quantity, Rial
from db.stocktake import MAX_ITEMS, MAX_NOTE_LENGTH


class StocktakeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: Literal["PRODUCT", "MATERIAL"]
    item_id: int
    # The physical count (products: a whole number, 422 QUANTITY_NOT_WHOLE).
    counted: Quantity
    # The system stock the screen showed when the count was made; a different live stock is 409 STOCKTAKE_STALE.
    system_quantity: Quantity
    # Only for a gain (counted above the system quantity): the cost of the units found, blended per
    # accounting rules section 2. Required when the item has no unit cost yet (422 PRODUCT_NO_UNIT_COST).
    unit_cost: Money | None = None


class StocktakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Local calendar day of the count (default today, never in the future).
    stocktake_date: DateStr | None = None
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    items: list[StocktakeItem] = Field(min_length=1, max_length=MAX_ITEMS)


class StocktakeCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: str
    item_id: int
    item_name: str
    unit: str
    old_quantity: float
    new_quantity: float
    difference: float
    # The cost the difference is valued at (null if unknown) and the value, integer Rial (negative for a loss).
    unit_cost: Rial | None
    value: Rial | None
    # null in a preview.
    movement_id: int | None


class StocktakeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stocktake_date: str
    # The note written on every movement.
    note: str
    corrections: list[StocktakeCorrection]
    unchanged_count: int
    total_value: Rial
    unvalued_count: int
