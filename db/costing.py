"""Exact money arithmetic for costs. `blend_unit_cost`: weighted-average unit cost when stock comes in (accounting rules section 2), exact and rounded half-even once at the end; with no prior stock or cost, the incoming value ÷ quantity.
`exact_quantity` reads a stored REAL quantity as the decimal it was entered as; `round_half_even` rounds an exact value to the Rial. Money never goes through float."""

from decimal import Decimal
from fractions import Fraction


def exact_quantity(quantity: float | int) -> Fraction:
    """A stored REAL quantity as the decimal it was entered as (2.5, 0.1), exactly."""
    return Fraction(Decimal(repr(quantity)))


def round_half_even(value: Fraction | int) -> int:
    """An exact value rounded half-even to the Rial (round() on a Fraction is exact)."""
    return round(Fraction(value))


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
