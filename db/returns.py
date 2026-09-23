import sqlite3

from db.connection import transaction
from db.errors import ConflictError, NotFoundError, ValidationError
from db.orders import _fetch_order_items

RETURN_STATUSES = ("CANCELLED", "REFUNDED")

_CANCELLED_ALLOWED_FROM = {"DRAFT", "PENDING", "PAID"}
_REFUNDED_ALLOWED_FROM = {"PAID", "COMPLETED"}


def process_return(
    conn: sqlite3.Connection,
    order_id: int,
    new_status: str,
    reason: str | None = None,
) -> None:
    if new_status not in RETURN_STATUSES:
        valid = ", ".join(RETURN_STATUSES)
        raise ValidationError(
            f"new_status must be one of: {valid}. "
            f"Use update_order_status for other status changes.",
            field="new_status",
        )

    with transaction(conn):
        order = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if order is None:
            raise NotFoundError(f"Order with id {order_id} does not exist")

        current_status = order["status"]
        if current_status in RETURN_STATUSES:
            raise ConflictError(
                f"Order #{order_id} is already {current_status}."
            )

        if new_status == "CANCELLED" and current_status not in _CANCELLED_ALLOWED_FROM:
            raise ConflictError(
                f"Cannot cancel order #{order_id} from status {current_status}."
            )
        if new_status == "REFUNDED" and current_status not in _REFUNDED_ALLOWED_FROM:
            raise ConflictError(
                f"Cannot refund order #{order_id} from status {current_status}."
            )

        if order["stock_committed"]:
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

            if new_status == "CANCELLED":
                # Restore exactly what this order's commit actually deducted, by
                # reversing its own PACKAGING movements — not by re-reading the
                # kit's current items, which may have changed since commit.
                packaging_movements = conn.execute(
                    """
                    SELECT item_id, quantity_change
                    FROM stock_movements
                    WHERE reason = 'PACKAGING' AND reference_order_id = ?
                    """,
                    (order_id,),
                ).fetchall()
                for movement in packaging_movements:
                    restored_quantity = abs(movement["quantity_change"])
                    conn.execute(
                        """
                        UPDATE materials
                        SET current_stock = current_stock + ?
                        WHERE id = ?
                        """,
                        (restored_quantity, movement["item_id"]),
                    )
                    conn.execute(
                        """
                        INSERT INTO stock_movements
                            (item_type, item_id, quantity_change, reason,
                             reference_order_id, notes)
                        VALUES ('MATERIAL', ?, ?, 'RETURN', ?, ?)
                        """,
                        (
                            movement["item_id"],
                            restored_quantity,
                            order_id,
                            reason,
                        ),
                    )

        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id),
        )
