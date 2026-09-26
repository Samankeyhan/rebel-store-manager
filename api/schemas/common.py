from typing import Annotated

from pydantic import BaseModel, ConfigDict, Strict, StringConstraints

DateStr = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]

# Money in request bodies: strict int, so 1000.5, 1000.0, "1000" and true are
# all rejected with 422 instead of being silently coerced or truncated.
Money = Annotated[int, Strict()]


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str
    field: str | None = None
    details: dict = {}


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
