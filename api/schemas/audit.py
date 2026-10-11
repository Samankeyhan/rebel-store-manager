from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    ts: str = Field(description='UTC moment, "YYYY-MM-DD HH:MM:SS" (like every stored moment)')
    entity_type: str = Field(description="The table that changed, e.g. orders")
    entity_id: str = Field(description="The row's key as text (a number, or a text key for settings)")
    action: str = Field(description="INSERT, UPDATE or DELETE")
    operation: str = Field(
        description="The business operation (the db/ function name), or UNLABELLED for a write outside one"
    )
    before: dict[str, Any] | None = Field(
        description="UPDATE: the changed columns before. DELETE: the whole row. Money is integer Rial."
    )
    after: dict[str, Any] | None = Field(
        description="UPDATE: the changed columns after. INSERT: the whole row. Money is integer Rial."
    )
    actor: str | None
    op_id: str | None = Field(description="Shared by every row written by one business operation")


class AuditPageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEntryOut]
    total: int = Field(description="Rows matching the filters, ignoring limit and offset")
    limit: int
    offset: int
