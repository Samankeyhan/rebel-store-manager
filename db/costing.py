"""Exact money arithmetic for costs. `blend_unit_cost`: weighted-average unit cost when stock comes in (accounting rules section 2), exact and rounded half-even once at the end; with no prior stock or cost, the incoming value ÷ quantity.
`recipe_batch_total` (sections 3 and 13: Σ needed × unit cost, rounded once) and `per_unit_cost` (a total ÷ a quantity) are the shared recipe and purchase formulas. `exact_quantity` reads a stored REAL quantity as the decimal it was entered as; `round_half_even` rounds an exact value to the Rial (and refuses a result over MAX_MONEY, so every computed amount is bounded). `check_money` is the bound itself. Money never goes through float."""

from decimal import Decimal
from fractions import Fraction

from db.constants import MAX_MONEY, MAX_QUANTITY, MAX_WHOLE_QUANTITY
from db.errors import ErrorCode, ValidationError


def check_quantity(value, field: str, *, whole: bool = False, prefix: str = "") -> None:
    """A quantity that must be > 0 and at most MAX_QUANTITY (MAX_WHOLE_QUANTITY, and an int, when `whole`).
    QUANTITY_NOT_WHOLE for a non-integer; QUANTITY_OUT_OF_RANGE (details min, max) otherwise."""
    if whole and (isinstance(value, bool) or not isinstance(value, int)):
        raise ValidationError(
            f"{prefix}{field} must be a whole number, got {value!r}",
            field=field,
            code=ErrorCode.QUANTITY_NOT_WHOLE,
        )
    if value <= 0:
        raise ValidationError(
            f"{prefix}{field} must be > 0, got {value}",
            field=field,
            code=ErrorCode.QUANTITY_OUT_OF_RANGE,
            details={"min": 0, "max": None},
        )
    maximum = MAX_WHOLE_QUANTITY if whole else MAX_QUANTITY
    if value > maximum:
        raise ValidationError(
            f"{prefix}{field} must be at most {maximum}",
            field=field,
            code=ErrorCode.QUANTITY_OUT_OF_RANGE,
            details={"min": None, "max": maximum},
        )


def check_money(value: int, field: str | None = None) -> int:
    """Refuse an amount whose size is over MAX_MONEY (either sign) with AMOUNT_TOO_LARGE; returns it.
    Called on every money input and on every computed amount before it is written."""
    if abs(value) > MAX_MONEY:
        raise ValidationError(
            f"{field or 'amount'} must be at most {MAX_MONEY} Rial in size",
            field=field,
            code=ErrorCode.AMOUNT_TOO_LARGE,
            details={"max": MAX_MONEY},
        )
    return value


def exact_quantity(quantity: float | int) -> Fraction:
    """A stored REAL quantity as the decimal it was entered as (2.5, 0.1), exactly."""
    return Fraction(Decimal(repr(quantity)))


def round_half_even(value: Fraction | int) -> int:
    """An exact value rounded half-even to the Rial (round() on a Fraction is exact)."""
    return check_money(round(Fraction(value)))


def blend_unit_cost(
    stock_before: float | None,
    cost_before: int | None,
    qty_in: float,
    value_in: int | Fraction,
) -> int:
    """Weighted-average unit cost when stock comes in (accounting rules section 2)."""
    qty = exact_quantity(qty_in)
    if cost_before is None or stock_before is None or stock_before <= 0:
        return round_half_even(Fraction(value_in) / qty)
    before = exact_quantity(stock_before)
    return round_half_even((before * cost_before + value_in) / (before + qty))


def per_unit_cost(total: int, quantity: float) -> int:
    """A money total ÷ a quantity, exact, rounded half-even to the Rial."""
    return round_half_even(Fraction(total) / exact_quantity(quantity))


def recipe_batch_total(lines, batch_qty: float) -> int:
    """Σ needed × unit_cost over recipe lines, exact, rounded half-even once.

    `lines` are (quantity_needed, cost_basis, unit_cost) tuples: a PER_UNIT line
    needs quantity_needed × batch_qty, a PER_BATCH line quantity_needed once.
    """
    batch = exact_quantity(batch_qty)
    total = Fraction(0)
    for quantity_needed, cost_basis, unit_cost in lines:
        needed = exact_quantity(quantity_needed)
        if cost_basis != "PER_BATCH":
            needed *= batch
        total += needed * unit_cost
    return round_half_even(total)
