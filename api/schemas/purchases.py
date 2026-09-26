from pydantic import BaseModel, ConfigDict

from api.schemas.common import DateStr, Money


class MaterialPurchaseOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    material_id: int
    supplier_id: int | None
    invoice_number: str | None
    purchase_date: str
    quantity_bought: float
    total_paid: int
    unit_cost: int
    notes: str | None
    material_name: str
    supplier_name: str | None


class ProductPurchaseOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    product_id: int
    supplier_id: int | None
    invoice_number: str | None
    purchase_date: str
    quantity_bought: int
    total_paid: int
    unit_cost: int
    notes: str | None
    product_name: str
    supplier_name: str | None


class MaterialPurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: int
    quantity_bought: float
    total_paid: Money
    supplier_id: int | None = None
    purchase_date: DateStr | None = None
    notes: str | None = None


class ProductPurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    quantity_bought: int
    total_paid: Money
    supplier_id: int | None = None
    purchase_date: DateStr | None = None
    notes: str | None = None
