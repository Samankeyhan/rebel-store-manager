from pydantic import BaseModel, ConfigDict

from api.schemas.common import DateStr


class ProductionBatchListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    product_id: int
    quantity_produced: int
    unit_cost: int
    # Batch total cost at run time; None for batches recorded before migration 006.
    total_cost: int | None
    production_date: str
    # When the batch was recorded (production_date may be backdated);
    # None for batches recorded before migration 006.
    created_at: str | None
    notes: str | None
    product_name: str


class ProductionBatchOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    product_id: int
    quantity_produced: int
    unit_cost: int
    # Batch total cost at run time; None for batches recorded before migration 006.
    total_cost: int | None
    production_date: str
    # When the batch was recorded (production_date may be backdated);
    # None for batches recorded before migration 006.
    created_at: str | None
    notes: str | None


class ProductionBatchMaterialOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    production_batch_id: int
    material_id: int
    quantity_used: float
    unit_cost_at_time: int
    material_name: str
    material_type: str


class ProductionBatchDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch: ProductionBatchOut
    materials: list[ProductionBatchMaterialOut]


class ProductionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    quantity_produced: int
    production_date: DateStr | None = None
    notes: str | None = None
