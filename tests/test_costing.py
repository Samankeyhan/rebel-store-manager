from db.costing import blend_unit_cost


def test_blend_unit_cost_weighted_average():
    # (90*25 + 550) / (90 + 10) = 2800 / 100 = 28
    assert blend_unit_cost(90, 25, 10, 550) == 28


def test_blend_unit_cost_first_purchase_into_empty_stock():
    # stock_before <= 0 -> new_cost = round(value_in / qty_in)
    assert blend_unit_cost(0, 0, 100, 3_000_000) == 30_000


def test_blend_unit_cost_null_cost_before():
    assert blend_unit_cost(50, None, 10, 1000) == 100
