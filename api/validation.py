"""Request-validation errors (FastAPI/pydantic) in the app's error envelope {"error": {type, code, message, field, details}}.
`type` is "RequestValidationError", `field` the dotted location without its "body"/"query" prefix, `details.errors` the pydantic errors reduced to loc, msg and type (never the input or ctx, so a huge value is not echoed back).
The first error picks the code: a money bound -> AMOUNT_TOO_LARGE, a quantity field -> QUANTITY_NOT_WHOLE / QUANTITY_OUT_OF_RANGE, anything else VALIDATION_FAILED."""

from fastapi.encoders import jsonable_encoder

from db.constants import MAX_MONEY
from db.errors import ErrorCode

# Request fields that hold a quantity (api/schemas: WholeQuantity, PositiveQuantity, Quantity, QuantityChange).
QUANTITY_FIELDS = frozenset({
    "quantity", "quantity_produced", "quantity_bought", "quantity_needed",
    "quantity_change", "initial_stock", "min_stock", "counted", "system_quantity",
})

_NOT_WHOLE_TYPES = frozenset({"int_type", "int_parsing", "int_from_float", "int_parsing_size"})
_RANGE_TYPES = frozenset({"greater_than", "greater_than_equal", "less_than", "less_than_equal"})


def _classify(error: dict) -> tuple[ErrorCode, dict]:
    kind = error.get("type")
    ctx = error.get("ctx") or {}
    loc = error.get("loc") or ()
    if kind in ("less_than_equal", "greater_than_equal") and (
        ctx.get("le") == MAX_MONEY or ctx.get("ge") == -MAX_MONEY
    ):
        return ErrorCode.AMOUNT_TOO_LARGE, {"max": MAX_MONEY}
    if loc and loc[0] == "body" and loc[-1] in QUANTITY_FIELDS:
        if kind in _NOT_WHOLE_TYPES:
            return ErrorCode.QUANTITY_NOT_WHOLE, {}
        if kind in _RANGE_TYPES:
            return ErrorCode.QUANTITY_OUT_OF_RANGE, {
                "min": ctx.get("gt", ctx.get("ge")),
                "max": ctx.get("lt", ctx.get("le")),
            }
    return ErrorCode.VALIDATION_FAILED, {}


def validation_envelope(errors: list[dict]) -> dict:
    """The response body for a RequestValidationError's `errors()`."""
    first = errors[0] if errors else {}
    code, extra = _classify(first)
    loc = first.get("loc") or ()
    field = ".".join(str(part) for part in loc[1:]) or None
    kept = jsonable_encoder(
        [{"loc": e.get("loc", ()), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in errors]
    )
    return {
        "error": {
            "type": "RequestValidationError",
            "code": str(code),
            "message": first.get("msg") or "Invalid request",
            "field": field,
            "details": {**extra, "errors": kept},
        }
    }
