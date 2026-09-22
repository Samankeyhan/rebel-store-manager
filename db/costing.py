def blend_unit_cost(
    stock_before: float | None,
    cost_before: int | None,
    qty_in: float,
    value_in: int,
) -> int:
    """Weighted-average unit cost when stock comes in (accounting rules section 2)."""
    if cost_before is None or stock_before is None or stock_before <= 0:
        return round(value_in / qty_in)
    return round((stock_before * cost_before + value_in) / (stock_before + qty_in))
