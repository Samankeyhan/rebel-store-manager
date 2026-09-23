import sqlite3

from db.connection import next_counter, transaction
from db.constants import VALID_CHANNELS, VALID_STATUSES  # re-exported for existing importers
from db.errors import ConflictError, InsufficientStockError, NotFoundError, ValidationError
from db.materials import get_material
from db.packaging import calculate_kit_cost, get_kit
from db.postage import get_current_postage_estimate
from db.products import get_product
from db.settings import get_channel_settings, get_setting
from db.timeutil import normalize_record_date, to_utc_range

REVENUE_ELIGIBLE_STATUSES = ("PENDING", "PAID", "COMPLETED")
CREATION_ALLOWED_STATUSES = ("DRAFT", "PENDING", "PAID", "COMPLETED")

USE_CHANNEL_DEFAULT = object()

_RETURN_STATUSES = ("CANCELLED", "REFUNDED")

_ALLOWED_TRANSITIONS = {
    "DRAFT": {"PENDING", "PAID", "COMPLETED"},
    "PENDING": {"PAID", "COMPLETED"},
    "PAID": {"COMPLETED"},
    "COMPLETED": set(),
}


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


def compute_order_revenue(order: sqlite3.Row, items: list[sqlite3.Row]) -> int:
    items_total = sum(
        _line_revenue(item["list_price"], item["discount_amount"]) for item in items
    )
    return items_total + order["shipping_charge"]


def compute_order_profit(order: sqlite3.Row, items: list[sqlite3.Row]) -> int:
    revenue = compute_order_revenue(order, items)
    cogs = sum(item["unit_cost_at_time"] * item["quantity"] for item in items)
    return (
        revenue
        - cogs
        - order["packaging_cost"]
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


def _fetch_recipe(conn: sqlite3.Connection, product_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            product_recipe.material_id,
            product_recipe.quantity_needed,
            product_recipe.cost_basis,
            materials.name AS material_name,
            materials.type AS material_type,
            materials.unit_cost AS material_unit_cost
        FROM product_recipe
        JOIN materials ON materials.id = product_recipe.material_id
        WHERE product_recipe.product_id = ?
        """,
        (product_id,),
    ).fetchall()


def _recipe_requirements(recipe_rows: list[sqlite3.Row], batch_qty: float) -> list[dict]:
    requirements = []
    for row in recipe_rows:
        if row["cost_basis"] == "PER_BATCH":
            needed = row["quantity_needed"]
        else:
            needed = row["quantity_needed"] * batch_qty
        requirements.append(
            {
                "material_id": row["material_id"],
                "material_name": row["material_name"],
                "material_type": row["material_type"],
                "unit_cost": row["material_unit_cost"],
                "needed": needed,
            }
        )
    return requirements


def _resolve_packaging_kit_id(conn, channel_settings: dict, packaging_kit_id) -> int | None:
    if packaging_kit_id is USE_CHANNEL_DEFAULT:
        resolved = channel_settings["default_packaging_kit_id"]
    else:
        resolved = packaging_kit_id

    if resolved is not None:
        kit = get_kit(conn, resolved)  # raises NotFoundError if missing
        if not kit["is_active"]:
            raise ValidationError(
                f"Packaging kit '{kit['name']}' is not active. Choose another kit "
                f"or update the channel's default packaging kit.",
                field="packaging_kit_id",
            )

    return resolved


def _commit_order(
    conn: sqlite3.Connection, order_id: int, postage_cost_override: int | None = None
) -> None:
    with transaction(conn):
        order = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        items = _fetch_order_items(conn, order_id)

        needed_by_product: dict[int, float] = {}
        for item in items:
            needed_by_product[item["product_id"]] = (
                needed_by_product.get(item["product_id"], 0) + item["quantity"]
            )

        products_by_id: dict[int, dict] = {}
        made_to_order_plan: dict[int, dict] = {}
        material_needed: dict[int, float] = {}

        for product_id, needed in needed_by_product.items():
            product = get_product(conn, product_id)
            products_by_id[product_id] = product

            if product["made_to_order"]:
                recipe_rows = _fetch_recipe(conn, product_id)
                if not recipe_rows:
                    raise ValidationError(
                        f"Cannot commit order #{order_id}: product '{product['name']}' "
                        f"is made-to-order but has no recipe",
                        field="made_to_order",
                    )

                from_stock = min(product["current_stock"], needed)
                to_make = needed - from_stock

                if from_stock > 0 and product["unit_cost"] is None:
                    raise ValidationError(
                        f"Cannot commit order #{order_id}: product '{product['name']}' "
                        f"has no unit_cost",
                        field="unit_cost",
                    )

                make_cost = 0
                if to_make > 0:
                    requirements = _recipe_requirements(recipe_rows, to_make)
                    make_cost = round(
                        sum(req["needed"] * req["unit_cost"] for req in requirements)
                    )
                    for req in requirements:
                        if req["material_type"] == "STOCK":
                            material_needed[req["material_id"]] = (
                                material_needed.get(req["material_id"], 0)
                                + req["needed"]
                            )

                unit_cost_at_time = round(
                    (from_stock * (product["unit_cost"] or 0) + make_cost) / needed
                )

                made_to_order_plan[product_id] = {
                    "from_stock": from_stock,
                    "to_make": to_make,
                    "unit_cost_at_time": unit_cost_at_time,
                }
            else:
                if product["unit_cost"] is None:
                    raise ValidationError(
                        f"Cannot commit order #{order_id}: product '{product['name']}' "
                        f"has no unit_cost",
                        field="unit_cost",
                    )
                if product["current_stock"] < needed:
                    raise InsufficientStockError(
                        f"Product '{product['name']}': insufficient stock — "
                        f"need {needed}, available {product['current_stock']}",
                        item_name=product["name"],
                        needed=needed,
                        available=product["current_stock"],
                    )

        for material_id, needed_qty in material_needed.items():
            material = get_material(conn, material_id)
            if material["current_stock"] < needed_qty:
                raise InsufficientStockError(
                    f"Material '{material['name']}': insufficient stock — "
                    f"need {needed_qty}, available {material['current_stock']}",
                    item_name=material["name"],
                    needed=needed_qty,
                    available=material["current_stock"],
                )

        kit_items: list[dict] = []
        if order["packaging_kit_id"] is not None:
            kit_items = get_kit(conn, order["packaging_kit_id"])["items"]
            needed_by_material: dict[int, float] = {}
            for kit_item in kit_items:
                needed_by_material[kit_item["material_id"]] = (
                    needed_by_material.get(kit_item["material_id"], 0)
                    + kit_item["quantity"]
                )
            for material_id, needed in needed_by_material.items():
                material = get_material(conn, material_id)
                if material["current_stock"] < needed:
                    raise InsufficientStockError(
                        f"Material '{material['name']}': insufficient stock — "
                        f"need {needed}, available {material['current_stock']}",
                        item_name=material["name"],
                        needed=needed,
                        available=material["current_stock"],
                    )

        remaining_from_stock = {
            product_id: plan["from_stock"] for product_id, plan in made_to_order_plan.items()
        }

        for item in items:
            product = products_by_id[item["product_id"]]

            if item["product_id"] in made_to_order_plan:
                plan = made_to_order_plan[item["product_id"]]
                available = remaining_from_stock[item["product_id"]]
                line_from_stock = min(available, item["quantity"])
                remaining_from_stock[item["product_id"]] -= line_from_stock

                if line_from_stock > 0:
                    conn.execute(
                        "UPDATE products SET current_stock = current_stock - ? WHERE id = ?",
                        (line_from_stock, item["product_id"]),
                    )
                    conn.execute(
                        """
                        INSERT INTO stock_movements
                            (item_type, item_id, quantity_change, reason, reference_order_id)
                        VALUES ('PRODUCT', ?, ?, 'SALE', ?)
                        """,
                        (item["product_id"], -line_from_stock, order_id),
                    )

                conn.execute(
                    "UPDATE order_items SET unit_cost_at_time = ? WHERE id = ?",
                    (plan["unit_cost_at_time"], item["id"]),
                )
            else:
                conn.execute(
                    "UPDATE products SET current_stock = current_stock - ? WHERE id = ?",
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
                conn.execute(
                    "UPDATE order_items SET unit_cost_at_time = ? WHERE id = ?",
                    (product["unit_cost"], item["id"]),
                )

        for material_id, needed_qty in material_needed.items():
            conn.execute(
                "UPDATE materials SET current_stock = current_stock - ? WHERE id = ?",
                (needed_qty, material_id),
            )
            conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason, reference_order_id)
                VALUES ('MATERIAL', ?, ?, 'PRODUCTION_CONSUMPTION', ?)
                """,
                (material_id, -needed_qty, order_id),
            )

        packaging_cost = 0
        if order["packaging_kit_id"] is not None:
            for kit_item in kit_items:
                conn.execute(
                    "UPDATE materials SET current_stock = current_stock - ? WHERE id = ?",
                    (kit_item["quantity"], kit_item["material_id"]),
                )
                conn.execute(
                    """
                    INSERT INTO stock_movements
                        (item_type, item_id, quantity_change, reason, reference_order_id)
                    VALUES ('MATERIAL', ?, ?, 'PACKAGING', ?)
                    """,
                    (kit_item["material_id"], -kit_item["quantity"], order_id),
                )
            packaging_cost = calculate_kit_cost(conn, order["packaging_kit_id"])

        if postage_cost_override is not None:
            postage_cost = postage_cost_override
        else:
            channel_settings = get_channel_settings(conn, order["channel"])
            postage_cost = (
                get_current_postage_estimate(conn)
                if channel_settings["applies_postage"]
                else 0
            )

        conn.execute(
            """
            UPDATE orders
            SET packaging_cost = ?, postage_cost = ?, stock_committed = 1
            WHERE id = ?
            """,
            (packaging_cost, postage_cost, order_id),
        )


def record_order(
    conn: sqlite3.Connection,
    channel: str,
    items: list[dict],
    customer_name: str | None = None,
    order_date: str | None = None,
    shipping_charge: int | None = None,
    packaging_kit_id=USE_CHANNEL_DEFAULT,
    postage_cost: int | None = None,
    transaction_fee: int = 0,
    notes: str | None = None,
    status: str = "COMPLETED",
) -> int:
    _validate_channel(channel)
    _validate_creation_status(status)
    if shipping_charge is not None:
        _validate_non_negative(shipping_charge, "shipping_charge")
    if postage_cost is not None:
        _validate_non_negative(postage_cost, "postage_cost")
    _validate_non_negative(transaction_fee, "transaction_fee")

    if not items:
        raise ValidationError("An order must have at least one item", field="items")

    channel_settings = get_channel_settings(conn, channel)

    if shipping_charge is None:
        shipping_charge = (
            int(get_setting(conn, "default_shipping_charge"))
            if channel_settings["applies_shipping_charge"]
            else 0
        )

    resolved_kit_id = _resolve_packaging_kit_id(conn, channel_settings, packaging_kit_id)

    if order_date is not None:
        order_date = normalize_record_date(order_date, conn)

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

            effective_unit_price = (list_price - discount_amount) // quantity
            placeholder_unit_cost = (
                product["unit_cost"] if product["unit_cost"] is not None else 0
            )

            validated_items.append(
                {
                    "product_id": product_id,
                    "quantity": quantity,
                    "list_price": list_price,
                    "discount_amount": discount_amount,
                    "discount_reason": discount_reason,
                    "unit_price": effective_unit_price,
                    "unit_cost_at_time": placeholder_unit_cost,
                }
            )

        insert_columns = [
            "status", "channel", "customer_name", "shipping_charge",
            "postage_cost", "transaction_fee", "notes", "invoice_number",
            "packaging_kit_id", "packaging_cost", "stock_committed",
        ]
        insert_values = [
            status, channel, customer_name, shipping_charge,
            0, transaction_fee, notes, f"INV-{next_counter(conn, 'INV'):06d}",
            resolved_kit_id, 0, 0,
        ]
        if order_date is not None:
            insert_columns.append("order_date")
            insert_values.append(order_date)

        placeholders = ", ".join("?" for _ in insert_values)
        cursor = conn.execute(
            f"INSERT INTO orders ({', '.join(insert_columns)}) VALUES ({placeholders})",
            insert_values,
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

        if status != "DRAFT":
            _commit_order(conn, order_id, postage_cost_override=postage_cost)

    return order_id


def get_order(conn: sqlite3.Connection, order_id: int) -> dict:
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise NotFoundError(f"Order with id {order_id} does not exist")

    items = _fetch_order_items(conn, order_id)
    return {
        "order": dict(order),
        "items": [dict(item) for item in items],
        "customer_total": compute_order_revenue(order, items),
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
                + orders.shipping_charge AS customer_total
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
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND orders.order_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND orders.order_date < ?"
        params.append(end_exclusive_utc)

    query += """
        GROUP BY orders.id
        ORDER BY orders.order_date DESC, orders.id DESC
    """

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_revenue_summary(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    status_placeholders = ", ".join("?" for _ in REVENUE_ELIGIBLE_STATUSES)
    query = f"""
        SELECT orders.*
        FROM orders
        WHERE orders.status IN ({status_placeholders})
    """
    params: list = list(REVENUE_ELIGIBLE_STATUSES)

    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND orders.order_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND orders.order_date < ?"
        params.append(end_exclusive_utc)

    orders = conn.execute(query, params).fetchall()

    total_revenue = 0
    total_profit = 0
    for order in orders:
        items = _fetch_order_items(conn, order["id"])
        total_revenue += compute_order_revenue(order, items)
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

    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise NotFoundError(f"Order with id {order_id} does not exist")

    if new_status in _RETURN_STATUSES:
        raise ConflictError(
            f"Use process_return to mark an order as {new_status} — "
            f"that restores stock and records RETURN movements."
        )

    current_status = order["status"]
    allowed_targets = _ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed_targets:
        raise ConflictError(
            f"Cannot transition order #{order_id} from {current_status} to {new_status}"
        )

    with transaction(conn):
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id),
        )
        if current_status == "DRAFT":
            _commit_order(conn, order_id, postage_cost_override=None)
