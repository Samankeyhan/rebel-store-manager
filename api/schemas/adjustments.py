from pydantic import BaseModel, ConfigDict

from api.schemas.common import DateStr, Money, PositiveQuantity, QuantityChange, Rial


class AdjustmentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    item_type: str
    item_id: int
    quantity_change: float
    reason: str
    reference_order_id: int | None
    reference_production_batch_id: int | None
    movement_date: str
    notes: str | None
    unit_cost_at_time: Rial | None
    item_name: str | None


class AdjustmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: str
    item_id: int
    quantity_change: QuantityChange
    reason: str
    unit_cost: Money | None = None
    notes: str | None = None
    movement_date: DateStr | None = None


class ServiceWasteCreate(BaseModel):
    """Waste of a SERVICE material: `quantity` units, no stock change. `unit_cost` = the price per unit to
    store (integer Rial, at least 1); omitted = the material's current cost."""

    model_config = ConfigDict(extra="forbid")

    material_id: int
    quantity: PositiveQuantity
    unit_cost: Money | None = None
    notes: str | None = None
    movement_date: DateStr | None = None
