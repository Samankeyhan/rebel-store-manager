import sqlite3

from db.orders import _fetch_order_items

RETURN_STATUSES = ("CANCELLED", "REFUNDED")


def process_return(
    conn: sqlite3.Connection,
    order_id: int,
    new_status: str,
    reason: str | None = None,
) -> None:
    if new_status not in RETURN_STATUSES:
        valid = ", ".join(RETURN_STATUSES)
        raise ValueError(
            f"new_status must be one of: {valid}. "
            f"Use update_order_status for other status changes."
        )

    conn.execute("BEGIN")
    try:
        order = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if order is None:
            raise ValueError(f"Order with id {order_id} does not exist")

        current_status = order["status"]
        if current_status in RETURN_STATUSES:
            raise ValueError(
                f"Order #{order_id} is already {current_status}."
            )

        items = _fetch_order_items(conn, order_id)

        # Assumes returned items are always resellable (undamaged). If a returned
        # item is actually damaged, the correct follow-up is to separately log a
        # WASTE-equivalent movement to remove it from stock again.
        for item in items:
            conn.execute(
                """
                UPDATE products
                SET current_stock = current_stock + ?
                WHERE id = ?
                """,
                (item["quantity"], item["product_id"]),
            )
            conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason,
                     reference_order_id, notes)
                VALUES ('PRODUCT', ?, ?, 'RETURN', ?, ?)
                """,
                (
                    item["product_id"],
                    item["quantity"],
                    order_id,
                    reason,
                ),
            )

        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id),
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
