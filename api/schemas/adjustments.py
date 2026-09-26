from pydantic import BaseModel, ConfigDict


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
    unit_cost_at_time: int | None
    item_name: str | None
