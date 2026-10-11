from fractions import Fraction

import pytest

from db.costing import (
    blend_unit_cost,
    exact_quantity,
    per_unit_cost,
    recipe_batch_total,
    round_half_even,
)


def test_blend_unit_cost_weighted_average():
    # (90*25 + 550) / (90 + 10) = 2800 / 100 = 28
    assert blend_unit_cost(90, 25, 10, 550) == 28


def test_blend_unit_cost_first_purchase_into_empty_stock():
    # stock_before <= 0 -> new_cost = round(value_in / qty_in)
    assert blend_unit_cost(0, 0, 100, 3_000_000) == 30_000


def test_blend_unit_cost_null_cost_before():
    assert blend_unit_cost(50, None, 10, 1000) == 100


@pytest.mark.parametrize("quantity, expected", [
    (0.1, Fraction(1, 10)),
    (2.5, Fraction(5, 2)),
    (0.144, Fraction(18, 125)),
    (3, Fraction(3)),
])
def test_exact_quantity_is_the_entered_decimal(quantity, expected):
    assert exact_quantity(quantity) == expected


@pytest.mark.parametrize("value, expected", [
    (Fraction(1, 2), 0), (Fraction(3, 2), 2), (Fraction(5, 2), 2), (Fraction(7, 2), 4),
    (Fraction(51, 100), 1), (7, 7),
])
def test_round_half_even_is_exact(value, expected):
    assert round_half_even(value) == expected


@pytest.mark.parametrize("stock, cost, qty, value, expected", [
    # (0.1*1 + 5) / 0.2 = 25.5 exactly -> 26; float gave 25.499999999999996 -> 25
    (0.1, 1, 0.1, 5, 26),
    (0.1, 1, 0.1, 7, 36),            # 35.5 -> 36 (float gave 35)
    (0.1, 1, 0.1, 4, 20),            # 20.5 -> 20, the even neighbour
    (90, 25, 10, 550, 28),           # integer quantities unchanged
])
def test_blend_unit_cost_with_stock_is_exact_half_even(stock, cost, qty, value, expected):
    assert blend_unit_cost(stock, cost, qty, value) == expected


@pytest.mark.parametrize("qty, value, expected", [
    (0.144, 9, 62),     # 9 / 0.144 = 62.5 exactly -> 62; float gave 62.50000000000001 -> 63
    (0.144, 117, 812),  # 812.5 -> 812 (float gave 813)
    (0.5, 1, 2),        # 1 / 0.5 = 2
])
def test_blend_unit_cost_without_stock_is_exact_half_even(qty, value, expected):
    assert blend_unit_cost(0, None, qty, value) == expected


def test_blend_unit_cost_accepts_exact_fraction_value_in():
    # (0.1*1 + 0.1*5) / 0.2 = 3
    assert blend_unit_cost(0.1, 1, 0.1, exact_quantity(0.1) * 5) == 3


@pytest.mark.parametrize("lines, batch, expected", [
    # 0.1 x 3 x 15 = 4.5 exactly -> 4 (float: 4.500000000000001 -> 5)
    ([(0.1, "PER_UNIT", 15)], 3, 4),
    # 0.3 x 3 x 15 = 13.5 exactly -> 14 (float: 13.499999999999998 -> 13)
    ([(0.3, "PER_UNIT", 15)], 3, 14),
    # PER_BATCH is not multiplied by the batch size: 0.5 x 9 = 4.5 -> 4
    ([(0.5, "PER_BATCH", 9)], 7, 4),
    # PER_BATCH + PER_UNIT: 0.5 x 9 + 0.1 x 3 x 15 = 4.5 + 4.5 = 9
    ([(0.5, "PER_BATCH", 9), (0.1, "PER_UNIT", 15)], 3, 9),
    # rounded once, never per line: 0.5 + 0.5 = 1, not 0 + 0
    ([(0.5, "PER_UNIT", 1), (0.5, "PER_UNIT", 1)], 1, 1),
])
def test_recipe_batch_total_is_exact_and_rounded_once(lines, batch, expected):
    assert recipe_batch_total(lines, batch) == expected


@pytest.mark.parametrize("total, quantity, expected", [
    (9, 0.144, 62),     # 62.5 -> 62 (float: 62.50000000000001 -> 63)
    (5, 2, 2),          # 2.5 -> 2
    (7, 2, 4),          # 3.5 -> 4
    (1_000, 3, 333),
])
def test_per_unit_cost_is_exact_half_even(total, quantity, expected):
    assert per_unit_cost(total, quantity) == expected
