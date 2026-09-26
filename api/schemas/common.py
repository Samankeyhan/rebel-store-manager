from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

DateStr = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str
    field: str | None = None
    details: dict = {}


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
