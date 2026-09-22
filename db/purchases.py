import sqlite3

from db.connection import transaction
from db.errors import NotFoundError, ValidationError
from db.materials import get_material
from db.products import get_product
from db.suppliers import get_supplier


def _generate_invoice_number(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM material_purchases)
            + (SELECT COUNT(*) FROM product_purchases) AS total
        """
    ).fetchone()
    next_number = row[0] + 1
    return f"PUR-{next_number:06d}"


def _validate_total_paid(total_paid: int) -> None:
    if total_paid < 0:
        raise ValidationError(f"total_paid must be >= 0, got {total_paid}", field="total_paid")


def _validate_supplier(conn: sqlite3.Connection, supplier_id: int | None) -> None:
    if supplier_id is None:
        return
    if get_supplier(conn, supplier_id) is None:
        raise NotFoundError(f"Supplier with id {supplier_id} does not exist")


def _compute_unit_cost(total_paid: int, quantity_bought: float) -> int:
    """Per-unit cost from total paid and quantity.

    Uses Python ``round()`` to the nearest integer (half-to-even / banker's
    rounding for .5 ties), consistent with ``round(total_paid / quantity_bought)``.
    """
    return round(total_paid / quantity_bought)


def record_material_purchase(
    conn: sqlite3.Connection,
    material_id: int,
    quantity_bought: float,
    total_paid: int,
    supplier_id: int | None = None,
    purchase_date: str | None = None,
    notes: str | None = None,
) -> int:
    material = get_material(conn, material_id)
    if material is None:
        raise NotFoundError(f"Material with id {material_id} does not exist")
    if not material["is_active"]:
        raise ValidationError(f"Material '{material['name']}' is not active")
    if material["type"] == "SERVICE":
        raise ValidationError(
            f"Material '{material['name']}' is a SERVICE and cannot be purchased "
            f"into stock"
        )
    if quantity_bought <= 0:
        raise ValidationError(
            f"quantity_bought must be > 0, got {quantity_bought}",
            field="quantity_bought",
        )

    _validate_total_paid(total_paid)
    _validate_supplier(conn, supplier_id)

    unit_cost = _compute_unit_cost(total_paid, quantity_bought)

    with transaction(conn):
        invoice_number = _generate_invoice_number(conn)

        if purchase_date is not None:
            cursor = conn.execute(
                """
                INSERT INTO material_purchases
                    (material_id, supplier_id, invoice_number, purchase_date,
                     quantity_bought, total_paid, unit_cost, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    material_id,
                    supplier_id,
                    invoice_number,
                    purchase_date,
                    quantity_bought,
                    total_paid,
                    unit_cost,
                    notes,
                ),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO material_purchases
                    (material_id, supplier_id, invoice_number,
                     quantity_bought, total_paid, unit_cost, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    material_id,
                    supplier_id,
                    invoice_number,
                    quantity_bought,
                    total_paid,
                    unit_cost,
                    notes,
                ),
            )
        purchase_id = cursor.lastrowid

        conn.execute(
            """
            UPDATE materials
            SET current_stock = current_stock + ?, unit_cost = ?
            WHERE id = ?
            """,
            (quantity_bought, unit_cost, material_id),
        )

        movement_notes = (
            f"Material purchase #{purchase_id} (invoice {invoice_number})"
        )
        if purchase_date is not None:
            conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason,
                     movement_date, notes)
                VALUES ('MATERIAL', ?, ?, 'PURCHASE', ?, ?)
                """,
                (material_id, quantity_bought, purchase_date, movement_notes),
            )
        else:
            conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason, notes)
                VALUES ('MATERIAL', ?, ?, 'PURCHASE', ?)
                """,
                (material_id, quantity_bought, movement_notes),
            )

    return purchase_id


def record_product_purchase(
    conn: sqlite3.Connection,
    product_id: int,
    quantity_bought: int,
    total_paid: int,
    supplier_id: int | None = None,
    purchase_date: str | None = None,
    notes: str | None = None,
) -> int:
    product = get_product(conn, product_id)
    if product is None:
        raise NotFoundError(f"Product with id {product_id} does not exist")
    if not product["is_active"]:
        raise ValidationError(f"Product '{product['name']}' is not active")
    if quantity_bought <= 0:
        raise ValidationError(
            f"quantity_bought must be > 0, got {quantity_bought}",
            field="quantity_bought",
        )

    _validate_total_paid(total_paid)
    _validate_supplier(conn, supplier_id)

    unit_cost = _compute_unit_cost(total_paid, quantity_bought)

    with transaction(conn):
        invoice_number = _generate_invoice_number(conn)

        if purchase_date is not None:
            cursor = conn.execute(
                """
                INSERT INTO product_purchases
                    (product_id, supplier_id, invoice_number, purchase_date,
                     quantity_bought, total_paid, unit_cost, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    supplier_id,
                    invoice_number,
                    purchase_date,
                    quantity_bought,
                    total_paid,
                    unit_cost,
                    notes,
                ),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO product_purchases
                    (product_id, supplier_id, invoice_number,
                     quantity_bought, total_paid, unit_cost, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    supplier_id,
                    invoice_number,
                    quantity_bought,
                    total_paid,
                    unit_cost,
                    notes,
                ),
            )
        purchase_id = cursor.lastrowid

        conn.execute(
            """
            UPDATE products
            SET current_stock = current_stock + ?, unit_cost = ?
            WHERE id = ?
            """,
            (quantity_bought, unit_cost, product_id),
        )

        movement_notes = (
            f"Product purchase #{purchase_id} (invoice {invoice_number})"
        )
        if purchase_date is not None:
            conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason,
                     movement_date, notes)
                VALUES ('PRODUCT', ?, ?, 'PURCHASE', ?, ?)
                """,
                (product_id, quantity_bought, purchase_date, movement_notes),
            )
        else:
            conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason, notes)
                VALUES ('PRODUCT', ?, ?, 'PURCHASE', ?)
                """,
                (product_id, quantity_bought, movement_notes),
            )

    return purchase_id


def get_material_purchase(
    conn: sqlite3.Connection, purchase_id: int
) -> dict | None:
    row = conn.execute(
        """
        SELECT
            material_purchases.*,
            materials.name AS material_name,
            suppliers.name AS supplier_name
        FROM material_purchases
        JOIN materials ON materials.id = material_purchases.material_id
        LEFT JOIN suppliers ON suppliers.id = material_purchases.supplier_id
        WHERE material_purchases.id = ?
        """,
        (purchase_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_product_purchase(conn: sqlite3.Connection, purchase_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT
            product_purchases.*,
            products.name AS product_name,
            suppliers.name AS supplier_name
        FROM product_purchases
        JOIN products ON products.id = product_purchases.product_id
        LEFT JOIN suppliers ON suppliers.id = product_purchases.supplier_id
        WHERE product_purchases.id = ?
        """,
        (purchase_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def list_material_purchases(
    conn: sqlite3.Connection,
    material_id: int | None = None,
    supplier_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = """
        SELECT
            material_purchases.*,
            materials.name AS material_name,
            suppliers.name AS supplier_name
        FROM material_purchases
        JOIN materials ON materials.id = material_purchases.material_id
        LEFT JOIN suppliers ON suppliers.id = material_purchases.supplier_id
        WHERE 1=1
    """
    params: list = []

    if material_id is not None:
        query += " AND material_purchases.material_id = ?"
        params.append(material_id)
    if supplier_id is not None:
        query += " AND material_purchases.supplier_id = ?"
        params.append(supplier_id)
    if start_date is not None:
        query += " AND material_purchases.purchase_date >= ?"
        params.append(start_date)
    if end_date is not None:
        query += " AND material_purchases.purchase_date <= ?"
        params.append(end_date)

    query += " ORDER BY material_purchases.purchase_date DESC, material_purchases.id DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def list_product_purchases(
    conn: sqlite3.Connection,
    product_id: int | None = None,
    supplier_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = """
        SELECT
            product_purchases.*,
            products.name AS product_name,
            suppliers.name AS supplier_name
        FROM product_purchases
        JOIN products ON products.id = product_purchases.product_id
        LEFT JOIN suppliers ON suppliers.id = product_purchases.supplier_id
        WHERE 1=1
    """
    params: list = []

    if product_id is not None:
        query += " AND product_purchases.product_id = ?"
        params.append(product_id)
    if supplier_id is not None:
        query += " AND product_purchases.supplier_id = ?"
        params.append(supplier_id)
    if start_date is not None:
        query += " AND product_purchases.purchase_date >= ?"
        params.append(start_date)
    if end_date is not None:
        query += " AND product_purchases.purchase_date <= ?"
        params.append(end_date)

    query += " ORDER BY product_purchases.purchase_date DESC, product_purchases.id DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
