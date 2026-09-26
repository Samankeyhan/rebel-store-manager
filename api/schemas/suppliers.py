from pydantic import BaseModel, ConfigDict, field_validator


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


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    notes: str | None = None


class SupplierUpdate(BaseModel):
    """Only the fields present in the body change; omitted fields are kept."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def _name_not_null(cls, value: str | None) -> str:
        # name may be omitted, but not cleared.
        if value is None:
            raise ValueError("name cannot be null")
        return value
