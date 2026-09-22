import sqlite3

from db.connection import transaction
from db.errors import ConflictError, InsufficientStockError, NotFoundError, ValidationError
from db.products import get_product

VALID_CHANNELS = ("INSTAGRAM", "WEBSITE", "WHOLESALE", "IN_PERSON", "OTHER")
VALID_STATUSES = (
    "DRAFT",
    "PENDING",
    "PAID",
    "COMPLETED",
    "CANCELLED",
    "REFUNDED",
)
REVENUE_ELIGIBLE_STATUSES = ("PENDING", "PAID", "COMPLETED")
CREATION_ALLOWED_STATUSES = ("DRAFT", "PENDING", "PAID", "COMPLETED")


def _validate_channel(channel: str) -> None:
    if channel not in VALID_CHANNELS:
        valid = ", ".join(VALID_CHANNELS)
        raise ValidationError(
            f"Invalid channel '{channel}'. Must be one of: {valid}", field="channel"
        )


def _validate_status(status: str) -> None:
    if status not in VALID_STATUSES:
        valid = ", ".join(VALID_STATUSES)
        raise ValidationError(
            f"Invalid status '{status}'. Must be one of: {valid}", field="status"
        )


def _validate_creation_status(status: str) -> None:
    if status in ("CANCELLED", "REFUNDED"):
        raise ValidationError(
            f"Cannot create an order with status '{status}'. "
            f"CANCELLED and REFUNDED are only set via process_return.",
            field="status",
        )
    if status not in CREATION_ALLOWED_STATUSES:
        valid = ", ".join(CREATION_ALLOWED_STATUSES)
        raise ValidationError(
            f"Invalid status '{status}'. Must be one of: {valid}", field="status"
        )


def _validate_non_negative(value: int, field_name: str) -> None:
    if value < 0:
        raise ValidationError(f"{field_name} must be >= 0, got {value}", field=field_name)


def _line_revenue(list_price: int, discount_amount: int) -> int:
    return list_price - discount_amount


def _generate_order_invoice_number(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM orders
        WHERE invoice_number IS NOT NULL
        """
    ).fetchone()
    next_number = row[0] + 1
    return f"INV-{next_number:06d}"


def compute_order_total(order: sqlite3.Row, items: list[sqlite3.Row]) -> int:
    # Total = sum(quantity * unit_price per item, i.e. list_price, minus discounts)
    #         + shipping_charge + postage_cost - transaction_fee
    items_total = sum(
        _line_revenue(item["list_price"], item["discount_amount"]) for item in items
    )
    return (
        items_total
        + order["shipping_charge"]
        + order["postage_cost"]
        - order["transaction_fee"]
    )


def compute_order_profit(order: sqlite3.Row, items: list[sqlite3.Row]) -> int:
    # Profit = sum(line revenue after discount)
    #          - sum(unit_cost_at_time * quantity)
    #          - shipping_charge - postage_cost - transaction_fee
    items_revenue = sum(
        _line_revenue(item["list_price"], item["discount_amount"]) for item in items
    )
    cogs = sum(item["unit_cost_at_time"] * item["quantity"] for item in items)
    return (
        items_revenue
        - cogs
        - order["shipping_charge"]
        - order["postage_cost"]
        - order["transaction_fee"]
    )


def _fetch_order_items(conn: sqlite3.Connection, order_id: int) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT
            order_items.*,
            products.name AS product_name
        FROM order_items
        JOIN products ON products.id = order_items.product_id
        WHERE order_items.order_id = ?
        ORDER BY order_items.id
        """,
        (order_id,),
    ).fetchall()
    return list(rows)


def record_order(
    conn: sqlite3.Connection,
    channel: str,
    items: list[dict],
    customer_name: str | None = None,
    shipping_charge: int = 0,
    postage_cost: int = 0,
    transaction_fee: int = 0,
    notes: str | None = None,
    status: str = "COMPLETED",
) -> int:
    _validate_channel(channel)
    _validate_creation_status(status)
    _validate_non_negative(shipping_charge, "shipping_charge")
    _validate_non_negative(postage_cost, "postage_cost")
    _validate_non_negative(transaction_fee, "transaction_fee")

    if not items:
        raise ValidationError("An order must have at least one item", field="items")

    with transaction(conn):
        validated_items: list[dict] = []

        for index, item in enumerate(items, start=1):
            product_id = item["product_id"]
            quantity = item["quantity"]
            unit_price = item["unit_price"]
            discount_amount = item.get("discount_amount", 0)
            discount_reason = item.get("discount_reason")

            product = get_product(conn, product_id)
            if product is None:
                raise NotFoundError(
                    f"Item {index}: product with id {product_id} does not exist"
                )
            if not product["is_active"]:
                raise ValidationError(
                    f"Item {index}: product '{product['name']}' is not active"
                )
            if quantity <= 0:
                raise ValidationError(
                    f"Item {index} ('{product['name']}'): quantity must be > 0, "
                    f"got {quantity}",
                    field="quantity",
                )
            if unit_price < 0:
                raise ValidationError(
                    f"Item {index} ('{product['name']}'): unit_price must be >= 0, "
                    f"got {unit_price}",
                    field="unit_price",
                )
            if discount_amount < 0:
                raise ValidationError(
                    f"Item {index} ('{product['name']}'): discount_amount must be >= 0, "
                    f"got {discount_amount}",
                    field="discount_amount",
                )

            list_price = quantity * unit_price
            if discount_amount > list_price:
                raise ValidationError(
                    f"Item {index} ('{product['name']}'): discount_amount ({discount_amount}) "
                    f"cannot exceed line total ({list_price})",
                    field="discount_amount",
                )

            if product["current_stock"] < quantity:
                raise InsufficientStockError(
                    f"Item {index} ('{product['name']}'): insufficient stock — "
                    f"need {quantity}, available {product['current_stock']}",
                    item_name=product["name"],
                    needed=quantity,
                    available=product["current_stock"],
                )

            effective_unit_price = (list_price - discount_amount) // quantity
            unit_cost_at_time = (
                product["unit_cost"] if product["unit_cost"] is not None else 0
            )

            validated_items.append(
                {
                    "product_id": product_id,
                    "product_name": product["name"],
                    "quantity": quantity,
                    "list_price": list_price,
                    "discount_amount": discount_amount,
                    "discount_reason": discount_reason,
                    "unit_price": effective_unit_price,
                    "unit_cost_at_time": unit_cost_at_time,
                }
            )

        cursor = conn.execute(
            """
            INSERT INTO orders
                (status, channel, customer_name, shipping_charge,
                 postage_cost, transaction_fee, notes, invoice_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                status,
                channel,
                customer_name,
                shipping_charge,
                postage_cost,
                transaction_fee,
                notes,
                _generate_order_invoice_number(conn),
            ),
        )
        order_id = cursor.lastrowid

        for item in validated_items:
            conn.execute(
                """
                INSERT INTO order_items
                    (order_id, product_id, quantity, list_price, discount_amount,
                     discount_reason, unit_price, unit_cost_at_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["product_id"],
                    item["quantity"],
                    item["list_price"],
                    item["discount_amount"],
                    item["discount_reason"],
                    item["unit_price"],
                    item["unit_cost_at_time"],
                ),
            )

            conn.execute(
                """
                UPDATE products
                SET current_stock = current_stock - ?
                WHERE id = ?
                """,
                (item["quantity"], item["product_id"]),
            )

            conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason, reference_order_id)
                VALUES ('PRODUCT', ?, ?, 'SALE', ?)
                """,
                (item["product_id"], -item["quantity"], order_id),
            )

    return order_id


def get_order(conn: sqlite3.Connection, order_id: int) -> dict:
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise NotFoundError(f"Order with id {order_id} does not exist")

    items = _fetch_order_items(conn, order_id)
    # total/profit are computed for any status, including CANCELLED/REFUNDED.
    # Revenue reports should exclude those statuses (see get_revenue_summary).
    return {
        "order": dict(order),
        "items": [dict(item) for item in items],
        "total": compute_order_total(order, items),
        "profit": compute_order_profit(order, items),
    }


def list_orders(
    conn: sqlite3.Connection,
    channel: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    if channel is not None:
        _validate_channel(channel)
    if status is not None:
        _validate_status(status)

    query = """
        SELECT
            orders.*,
            COALESCE(SUM(order_items.list_price - order_items.discount_amount), 0)
                + orders.shipping_charge
                + orders.postage_cost
                - orders.transaction_fee AS total
        FROM orders
        LEFT JOIN order_items ON order_items.order_id = orders.id
        WHERE 1=1
    """
    params: list = []

    if channel is not None:
        query += " AND orders.channel = ?"
        params.append(channel)
    if status is not None:
        query += " AND orders.status = ?"
        params.append(status)
    if start_date is not None:
        query += " AND orders.order_date >= ?"
        params.append(start_date)
    if end_date is not None:
        query += " AND orders.order_date <= ?"
        params.append(end_date)

    query += """
        GROUP BY orders.id
        ORDER BY orders.order_date DESC, orders.id DESC
    """

    # Each row includes a total for all statuses. CANCELLED/REFUNDED orders remain
    # visible here for operational lookup; revenue reporting excludes them separately.
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_revenue_summary(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    # Revenue reporting excludes DRAFT, CANCELLED, and REFUNDED orders — only
    # PENDING, PAID, and COMPLETED count toward totals.
    status_placeholders = ", ".join("?" for _ in REVENUE_ELIGIBLE_STATUSES)
    query = f"""
        SELECT
            orders.id,
            orders.shipping_charge,
            orders.postage_cost,
            orders.transaction_fee
        FROM orders
        WHERE orders.status IN ({status_placeholders})
    """
    params: list = list(REVENUE_ELIGIBLE_STATUSES)

    if start_date is not None:
        query += " AND orders.order_date >= ?"
        params.append(start_date)
    if end_date is not None:
        query += " AND orders.order_date <= ?"
        params.append(end_date)

    orders = conn.execute(query, params).fetchall()

    total_revenue = 0
    total_profit = 0
    for order in orders:
        items = _fetch_order_items(conn, order["id"])
        total_revenue += compute_order_total(order, items)
        total_profit += compute_order_profit(order, items)

    return {
        "order_count": len(orders),
        "total_revenue": total_revenue,
        "total_profit": total_profit,
    }


def update_order_status(
    conn: sqlite3.Connection, order_id: int, new_status: str
) -> None:
    _validate_status(new_status)

    order = conn.execute("SELECT id FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise NotFoundError(f"Order with id {order_id} does not exist")

    if new_status in ("CANCELLED", "REFUNDED"):
        raise ConflictError(
            f"Use process_return to mark an order as {new_status} — "
            f"that restores stock and records RETURN movements."
        )

    with transaction(conn):
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id),
        )
