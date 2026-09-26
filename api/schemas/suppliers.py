from pydantic import BaseModel, ConfigDict


class SupplierOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    phone: str | None
    email: str | None
    website: str | None
    notes: str | None
    created_at: str
    updated_at: str | None
