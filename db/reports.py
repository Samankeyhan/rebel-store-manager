import sqlite3

from db.expenses import get_total_expenses, list_expenses
from db.orders import (
    REVENUE_ELIGIBLE_STATUSES,
    _fetch_order_items,
    compute_order_profit,
    compute_order_revenue,
)
from db.timeutil import to_utc_range

REFUND_INCLUDED_STATUSES = REVENUE_ELIGIBLE_STATUSES + ("REFUNDED",)


def _revenue_eligible_status_clause() -> tuple[str, list[str]]:
    placeholders = ", ".join("?" for _ in REVENUE_ELIGIBLE_STATUSES)
    return f"orders.status IN ({placeholders})", list(REVENUE_ELIGIBLE_STATUSES)


def _append_order_date_filters(
    conn: sqlite3.Connection,
    query: str,
    params: list,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, list]:
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND orders.order_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND orders.order_date < ?"
        params.append(end_exclusive_utc)
    return query, params


def _date_range_clause(
    conn: sqlite3.Connection,
    column: str,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, list]:
    """An " AND <column> >= ? AND <column> < ?"-style clause plus its params."""
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    clause = ""
    params: list = []
    if start_utc is not None:
        clause += f" AND {column} >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        clause += f" AND {column} < ?"
        params.append(end_exclusive_utc)
    return clause, params


def _eligible_order_aggregates(
    conn: sqlite3.Connection, start_date: str | None, end_date: str | None
) -> dict:
    """Sums over PENDING/PAID/COMPLETED orders in the date range."""
    date_clause, date_params = _date_range_clause(
        conn, "orders.order_date", start_date, end_date
    )
    status_placeholders = ", ".join("?" for _ in REVENUE_ELIGIBLE_STATUSES)

    items_row = conn.execute(
        f"""
        SELECT
            COALESCE(SUM(order_items.list_price - order_items.discount_amount), 0)
                AS items_revenue,
            COALESCE(SUM(order_items.quantity * order_items.unit_cost_at_time), 0)
                AS cogs
        FROM order_items
        JOIN orders ON orders.id = order_items.order_id
        WHERE orders.status IN ({status_placeholders})
        {date_clause}
        """,
        list(REVENUE_ELIGIBLE_STATUSES) + date_params,
    ).fetchone()

    orders_row = conn.execute(
        f"""
        SELECT
            COALESCE(SUM(shipping_charge), 0) AS shipping_revenue,
            COALESCE(SUM(packaging_cost), 0) AS packaging_cost,
            COALESCE(SUM(postage_cost), 0) AS postage_estimated,
            COALESCE(SUM(transaction_fee), 0) AS transaction_fees,
            COUNT(*) AS order_count
        FROM orders
        WHERE status IN ({status_placeholders})
        {date_clause}
        """,
        list(REVENUE_ELIGIBLE_STATUSES) + date_params,
    ).fetchone()

    return {
        "items_revenue": items_row["items_revenue"],
        "cogs": items_row["cogs"],
        "shipping_revenue": orders_row["shipping_revenue"],
        "packaging_cost": orders_row["packaging_cost"],
        "postage_estimated": orders_row["postage_estimated"],
        "transaction_fees": orders_row["transaction_fees"],
        "order_count": orders_row["order_count"],
    }


def _postage_actual(
    conn: sqlite3.Connection, start_date: str | None, end_date: str | None
) -> int:
    date_clause, date_params = _date_range_clause(conn, "paid_date", start_date, end_date)
    row = conn.execute(
        f"SELECT COALESCE(SUM(total_paid), 0) AS total FROM postage_batches WHERE 1=1 {date_clause}",
        date_params,
    ).fetchone()
    return row["total"]


def _postage_committed_on_shipped_orders(
    conn: sqlite3.Connection, start_date: str | None, end_date: str | None
) -> int:
    """Sum of postage_cost over orders that actually shipped (eligible or
    REFUNDED) in the date range — the baseline postage_variance compares
    postage_actual against.
    """
    date_clause, date_params = _date_range_clause(
        conn, "orders.order_date", start_date, end_date
    )
    status_placeholders = ", ".join("?" for _ in REFUND_INCLUDED_STATUSES)
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(postage_cost), 0) AS total
        FROM orders
        WHERE status IN ({status_placeholders})
        {date_clause}
        """,
        list(REFUND_INCLUDED_STATUSES) + date_params,
    ).fetchone()
    return row["total"]


def _refund_losses(
    conn: sqlite3.Connection, start_date: str | None, end_date: str | None
) -> int:
    date_clause, date_params = _date_range_clause(
        conn, "orders.order_date", start_date, end_date
    )

    refunded_row = conn.execute(
        f"""
        SELECT COALESCE(SUM(packaging_cost + postage_cost + transaction_fee), 0) AS total
        FROM orders
        WHERE status = 'REFUNDED'
        {date_clause}
        """,
        date_params,
    ).fetchone()

    cancelled_row = conn.execute(
        f"""
        SELECT COALESCE(SUM(transaction_fee), 0) AS total
        FROM orders
        WHERE status = 'CANCELLED' AND stock_committed = 1
        {date_clause}
        """,
        date_params,
    ).fetchone()

    return refunded_row["total"] + cancelled_row["total"]


def _waste_cost(
    conn: sqlite3.Connection, start_date: str | None, end_date: str | None
) -> int:
    date_clause, date_params = _date_range_clause(
        conn, "movement_date", start_date, end_date
    )
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(ABS(quantity_change) * unit_cost_at_time), 0) AS total
        FROM stock_movements
        WHERE reason = 'WASTE'
        {date_clause}
        """,
        date_params,
    ).fetchone()
    return row["total"]


def get_product_performance(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    status_clause, status_params = _revenue_eligible_status_clause()
    query = f"""
        SELECT
            order_items.product_id,
            products.name AS product_name,
            SUM(order_items.quantity) AS units_sold,
            SUM(order_items.list_price - order_items.discount_amount) AS total_revenue,
            SUM(order_items.quantity * order_items.unit_cost_at_time) AS total_cost
        FROM order_items
        JOIN orders ON orders.id = order_items.order_id
        JOIN products ON products.id = order_items.product_id
        WHERE {status_clause}
    """
    params: list = list(status_params)
    query, params = _append_order_date_filters(conn, query, params, start_date, end_date)
    query += """
        GROUP BY order_items.product_id, products.name
        ORDER BY (total_revenue - total_cost) DESC
    """

    rows = conn.execute(query, params).fetchall()
    return [
        {
            "product_id": row["product_id"],
            "product_name": row["product_name"],
            "units_sold": row["units_sold"],
            "total_revenue": row["total_revenue"],
            "total_cost": row["total_cost"],
            "total_profit": row["total_revenue"] - row["total_cost"],
        }
        for row in rows
    ]


def get_channel_breakdown(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    status_clause, status_params = _revenue_eligible_status_clause()
    query = f"""
        SELECT orders.*
        FROM orders
        WHERE {status_clause}
    """
    params: list = list(status_params)
    query, params = _append_order_date_filters(conn, query, params, start_date, end_date)

    orders = conn.execute(query, params).fetchall()

    by_channel: dict[str, dict] = {}
    for order in orders:
        channel = order["channel"]
        items = _fetch_order_items(conn, order["id"])
        revenue = compute_order_revenue(order, items)
        profit = compute_order_profit(order, items)

        if channel not in by_channel:
            by_channel[channel] = {
                "channel": channel,
                "order_count": 0,
                "total_revenue": 0,
                "total_profit": 0,
            }
        by_channel[channel]["order_count"] += 1
        by_channel[channel]["total_revenue"] += revenue
        by_channel[channel]["total_profit"] += profit

    return sorted(
        by_channel.values(),
        key=lambda row: row["total_revenue"],
        reverse=True,
    )


def get_low_stock_products(
    conn: sqlite3.Connection, threshold: float
) -> list[dict]:
    """Products at or below *threshold* stock.

    Recipe-built products are often kept at zero stock and produced on demand,
    so a low-stock alert may not be meaningful for them — this function
    reports the raw threshold comparison only.
    """
    rows = conn.execute(
        """
        SELECT * FROM products
        WHERE is_active = 1
          AND current_stock <= ?
        ORDER BY name
        """,
        (threshold,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_waste_report(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Waste grouped by item, valued at each movement's own frozen
    unit_cost_at_time (never the item's current cost).

    A movement with no recorded unit_cost_at_time still counts toward
    total_wasted/waste_event_count, but is excluded from the cost sum and
    counted separately in unknown_cost_count; if every movement for an item
    is unknown, cost is reported as None.
    """
    date_clause, date_params = _date_range_clause(
        conn, "stock_movements.movement_date", start_date, end_date
    )

    material_rows = conn.execute(
        f"""
        SELECT
            'MATERIAL' AS item_type,
            materials.name AS item_name,
            SUM(ABS(stock_movements.quantity_change)) AS total_wasted,
            COUNT(*) AS waste_event_count,
            SUM(ABS(stock_movements.quantity_change) * stock_movements.unit_cost_at_time)
                AS cost,
            SUM(CASE WHEN stock_movements.unit_cost_at_time IS NULL THEN 1 ELSE 0 END)
                AS unknown_cost_count
        FROM stock_movements
        JOIN materials ON materials.id = stock_movements.item_id
        WHERE stock_movements.reason = 'WASTE'
          AND stock_movements.item_type = 'MATERIAL'
          {date_clause}
        GROUP BY materials.id, materials.name
        """,
        date_params,
    ).fetchall()

    product_rows = conn.execute(
        f"""
        SELECT
            'PRODUCT' AS item_type,
            products.name AS item_name,
            SUM(ABS(stock_movements.quantity_change)) AS total_wasted,
            COUNT(*) AS waste_event_count,
            SUM(ABS(stock_movements.quantity_change) * stock_movements.unit_cost_at_time)
                AS cost,
            SUM(CASE WHEN stock_movements.unit_cost_at_time IS NULL THEN 1 ELSE 0 END)
                AS unknown_cost_count
        FROM stock_movements
        JOIN products ON products.id = stock_movements.item_id
        WHERE stock_movements.reason = 'WASTE'
          AND stock_movements.item_type = 'PRODUCT'
          {date_clause}
        GROUP BY products.id, products.name
        """,
        date_params,
    ).fetchall()

    results = [
        {
            "item_type": row["item_type"],
            "item_name": row["item_name"],
            "total_wasted": row["total_wasted"],
            "waste_event_count": row["waste_event_count"],
            "cost": row["cost"],
            "unknown_cost_count": row["unknown_cost_count"],
        }
        for row in material_rows + product_rows
    ]

    results.sort(
        key=lambda row: (row["cost"] is None, -(row["cost"] or 0)),
    )
    return results


def get_expense_breakdown(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    expenses = list_expenses(conn, start_date=start_date, end_date=end_date)

    by_category: dict[str, dict] = {}
    for expense in expenses:
        name = expense["category_name"]
        if name not in by_category:
            by_category[name] = {
                "category_name": name,
                "total_amount": 0,
                "expense_count": 0,
            }
        by_category[name]["total_amount"] += expense["amount"]
        by_category[name]["expense_count"] += 1

    return sorted(
        by_category.values(),
        key=lambda row: row["total_amount"],
        reverse=True,
    )


def get_profit_and_loss(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Full profit & loss per accounting-rules.md section 9."""
    agg = _eligible_order_aggregates(conn, start_date, end_date)
    items_revenue = agg["items_revenue"]
    shipping_revenue = agg["shipping_revenue"]
    total_revenue = items_revenue + shipping_revenue
    cogs = agg["cogs"]
    packaging_cost = agg["packaging_cost"]
    postage_estimated = agg["postage_estimated"]
    transaction_fees = agg["transaction_fees"]
    order_count = agg["order_count"]

    gross_profit = (
        total_revenue - cogs - packaging_cost - postage_estimated - transaction_fees
    )

    postage_actual = _postage_actual(conn, start_date, end_date)
    postage_variance = postage_actual - _postage_committed_on_shipped_orders(
        conn, start_date, end_date
    )

    refund_losses = _refund_losses(conn, start_date, end_date)
    waste_cost = _waste_cost(conn, start_date, end_date)
    operating_expenses = get_total_expenses(conn, start_date, end_date)

    net_profit = (
        gross_profit - postage_variance - refund_losses - waste_cost - operating_expenses
    )

    return {
        "items_revenue": items_revenue,
        "shipping_revenue": shipping_revenue,
        "total_revenue": total_revenue,
        "cogs": cogs,
        "packaging_cost": packaging_cost,
        "postage_estimated": postage_estimated,
        "transaction_fees": transaction_fees,
        "gross_profit": gross_profit,
        "postage_actual": postage_actual,
        "postage_variance": postage_variance,
        "refund_losses": refund_losses,
        "waste_cost": waste_cost,
        "operating_expenses": operating_expenses,
        "net_profit": net_profit,
        "order_count": order_count,
    }


def get_shipping_summary(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Shipping economics per accounting-rules.md section 9."""
    agg = _eligible_order_aggregates(conn, start_date, end_date)
    shipping_revenue = agg["shipping_revenue"]
    packaging_cost = agg["packaging_cost"]
    postage_estimated = agg["postage_estimated"]
    order_count = agg["order_count"]

    postage_actual = _postage_actual(conn, start_date, end_date)
    net_shipping_result = shipping_revenue - packaging_cost - postage_actual

    def _avg(total: int) -> int:
        return round(total / order_count) if order_count else 0

    return {
        "shipping_revenue": shipping_revenue,
        "packaging_cost": packaging_cost,
        "postage_estimated": postage_estimated,
        "postage_actual": postage_actual,
        "net_shipping_result": net_shipping_result,
        "order_count": order_count,
        "avg_shipping_revenue": _avg(shipping_revenue),
        "avg_packaging_cost": _avg(packaging_cost),
        "avg_postage_actual": _avg(postage_actual),
        "avg_net_shipping_result": _avg(net_shipping_result),
    }
