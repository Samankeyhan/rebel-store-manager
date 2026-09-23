import sqlite3

from db.expenses import get_total_expenses, list_expenses
from db.orders import (
    REVENUE_ELIGIBLE_STATUSES,
    _fetch_order_items,
    compute_order_profit,
    compute_order_revenue,
    get_revenue_summary,
)
from db.timeutil import to_utc_range


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
            SUM(order_items.quantity * order_items.unit_price) AS total_revenue,
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
    """Waste grouped by item. *estimated_cost* uses current unit_cost on
    materials/products — an estimate, not a frozen historical figure (same
    caveat as calculate_recipe_cost).
    """
    date_filter = ""
    date_params: list = []
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        date_filter += " AND stock_movements.movement_date >= ?"
        date_params.append(start_utc)
    if end_exclusive_utc is not None:
        date_filter += " AND stock_movements.movement_date < ?"
        date_params.append(end_exclusive_utc)

    material_rows = conn.execute(
        f"""
        SELECT
            'MATERIAL' AS item_type,
            materials.name AS item_name,
            SUM(ABS(stock_movements.quantity_change)) AS total_wasted,
            COUNT(*) AS waste_event_count,
            SUM(ABS(stock_movements.quantity_change) * materials.unit_cost)
                AS estimated_cost
        FROM stock_movements
        JOIN materials ON materials.id = stock_movements.item_id
        WHERE stock_movements.reason = 'WASTE'
          AND stock_movements.item_type = 'MATERIAL'
          {date_filter}
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
            SUM(ABS(stock_movements.quantity_change) * COALESCE(products.unit_cost, 0))
                AS estimated_cost
        FROM stock_movements
        JOIN products ON products.id = stock_movements.item_id
        WHERE stock_movements.reason = 'WASTE'
          AND stock_movements.item_type = 'PRODUCT'
          {date_filter}
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
            "estimated_cost": row["estimated_cost"],
        }
        for row in material_rows + product_rows
    ]

    results.sort(
        key=lambda row: (
            row["estimated_cost"] is None,
            -(row["estimated_cost"] or 0),
        ),
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
    """Combine revenue summary and expenses into a P&L snapshot.

    total_cost_of_goods is derived as total_revenue minus total_profit from
    get_revenue_summary. That profit already subtracts per-order COGS,
    packaging, postage, and transaction fees (see compute_order_profit), so
    this derived figure captures all of those costs relative to revenue —
    not COGS alone.
    """
    revenue_summary = get_revenue_summary(conn, start_date, end_date)
    total_expenses = get_total_expenses(conn, start_date, end_date)

    total_revenue = revenue_summary["total_revenue"]
    total_profit = revenue_summary["total_profit"]

    return {
        "total_revenue": total_revenue,
        "total_cost_of_goods": total_revenue - total_profit,
        "total_expenses": total_expenses,
        "net_profit": total_profit - total_expenses,
        "order_count": revenue_summary["order_count"],
    }
