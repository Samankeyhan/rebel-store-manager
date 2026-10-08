from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, Strict, StringConstraints

DateStr = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]

RIAL_DESCRIPTION = "Integer Rial (the stored unit; Toman = Rial ÷ 10 is display only)"

# Money in request bodies: integer Rial, strict, so 1000.5, 1000.0, "1000" and
# true are all rejected with 422 instead of being silently coerced or truncated.
Money = Annotated[int, Strict(), Field(description=RIAL_DESCRIPTION)]

# Money in responses: integer Rial.
Rial = Annotated[int, Field(description=RIAL_DESCRIPTION)]

# A stock quantity in request bodies (REAL, in the item's own unit): a finite
# number >= 0. Strict, so "5" and true are rejected with 422; JSON integers pass.
Quantity = Annotated[float, Strict(), Field(ge=0, allow_inf_nan=False)]


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str
    field: str | None = None
    details: dict = {}


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
