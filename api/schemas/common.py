from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, Strict, StringConstraints, model_validator

from db.constants import MAX_MONEY, MAX_QUANTITY, MAX_WHOLE_QUANTITY
from db.errors import ErrorCode

DateStr = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]

RIAL_DESCRIPTION = "Integer Rial (the stored unit; Toman = Rial ÷ 10 is display only)"

# Money in request bodies: integer Rial, strict, so 1000.5, 1000.0, "1000" and
# true are all rejected with 422 instead of being silently coerced or truncated.
# Bounded to +-MAX_MONEY (2^53 - 1) on both sides: a larger size is 422 AMOUNT_TOO_LARGE;
# whether a field may be negative is decided in db/ (every amount field is >= 0).
Money = Annotated[int, Strict(), Field(ge=-MAX_MONEY, le=MAX_MONEY, description=RIAL_DESCRIPTION)]

# Money in responses: integer Rial.
Rial = Annotated[int, Field(description=RIAL_DESCRIPTION)]

# A stock quantity in request bodies (REAL, in the item's own unit): a finite
# number >= 0. Strict, so "5" and true are rejected with 422; JSON integers pass.
Quantity = Annotated[float, Strict(), Field(ge=0, le=MAX_QUANTITY, allow_inf_nan=False)]
# A fractional quantity that must be > 0 (purchases, recipe lines, kit items). Strict float:
# JSON 5 and 5.5 both pass, "5" and true do not.
PositiveQuantity = Annotated[float, Strict(), Field(gt=0, le=MAX_QUANTITY, allow_inf_nan=False)]
# A whole number of units that must be >= 1 (order lines, production batches, product purchases).
WholeQuantity = Annotated[int, Strict(), Field(gt=0, le=MAX_WHOLE_QUANTITY)]
# A signed stock change (stock adjustments); zero, the sign rules and whole-for-products are db/ rules.
QuantityChange = Annotated[float, Strict(), Field(ge=-MAX_QUANTITY, le=MAX_QUANTITY, allow_inf_nan=False)]


class NamedOut(BaseModel):
    """Base of the responses for tables with a unique name: `name_key` (db/names.py) is internal,
    never sent."""

    @model_validator(mode="before")
    @classmethod
    def _drop_name_key(cls, data):
        if isinstance(data, dict) and "name_key" in data:
            return {k: v for k, v in data.items() if k != "name_key"}
        return data


class ErrorBody(BaseModel):
    """An app error (db/errors.py). The client decides what to show from
    `code` and `details`; `message` is English text for logs only."""

    model_config = ConfigDict(extra="forbid")

    type: str
    code: ErrorCode
    message: str
    field: str | None = None
    details: dict = {}


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
