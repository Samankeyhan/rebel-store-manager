import sqlite3

from db.connection import transaction
from db.errors import NotFoundError, ValidationError
from db.materials import get_material
from db.products import get_product
from db.timeutil import normalize_record_date, to_utc_range

VALID_ITEM_TYPES = ("MATERIAL", "PRODUCT")
VALID_REASONS = ("WASTE", "ADJUSTMENT")


def _validate_item_type(item_type: str) -> None:
    if item_type not in VALID_ITEM_TYPES:
        valid = ", ".join(VALID_ITEM_TYPES)
        raise ValidationError(
            f"Invalid item_type '{item_type}'. Must be one of: {valid}",
            field="item_type",
        )


def _validate_reason(reason: str) -> None:
    if reason not in VALID_REASONS:
        valid = ", ".join(VALID_REASONS)
        raise ValidationError(
            f"Invalid reason '{reason}'. Must be one of: {valid}", field="reason"
        )


def _validate_item(conn: sqlite3.Connection, item_type: str, item_id: int) -> None:
    if item_type == "MATERIAL":
        material = get_material(conn, item_id)
        if material is None:
            raise NotFoundError(f"Material with id {item_id} does not exist")
        if not material["is_active"]:
            raise ValidationError(f"Material '{material['name']}' is not active")
        if material["type"] == "SERVICE":
            raise ValidationError(
                f"Material '{material['name']}' is a SERVICE and has no stock to adjust"
            )
    else:
        product = get_product(conn, item_id)
        if product is None:
            raise NotFoundError(f"Product with id {item_id} does not exist")
        if not product["is_active"]:
            raise ValidationError(f"Product '{product['name']}' is not active")


def record_stock_adjustment(
    conn: sqlite3.Connection,
    item_type: str,
    item_id: int,
    quantity_change: float,
    reason: str,
    notes: str | None = None,
    movement_date: str | None = None,
) -> int:
    _validate_item_type(item_type)
    _validate_reason(reason)

    if quantity_change == 0:
        raise ValidationError("quantity_change must not be 0", field="quantity_change")

    _validate_item(conn, item_type, item_id)
    if movement_date is not None:
        movement_date = normalize_record_date(movement_date, conn)

    with transaction(conn):
        if item_type == "MATERIAL":
            conn.execute(
                """
                UPDATE materials
                SET current_stock = current_stock + ?
                WHERE id = ?
                """,
                (quantity_change, item_id),
            )
        else:
            conn.execute(
                """
                UPDATE products
                SET current_stock = current_stock + ?
                WHERE id = ?
                """,
                (quantity_change, item_id),
            )

        if movement_date is not None:
            cursor = conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason,
                     movement_date, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item_type, item_id, quantity_change, reason, movement_date, notes),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item_type, item_id, quantity_change, reason, notes),
            )

        movement_id = cursor.lastrowid

    return movement_id


def get_stock_movement(conn: sqlite3.Connection, movement_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT
            stock_movements.*,
            CASE
                WHEN stock_movements.item_type = 'MATERIAL' THEN materials.name
                WHEN stock_movements.item_type = 'PRODUCT' THEN products.name
            END AS item_name
        FROM stock_movements
        LEFT JOIN materials
            ON stock_movements.item_type = 'MATERIAL'
            AND materials.id = stock_movements.item_id
        LEFT JOIN products
            ON stock_movements.item_type = 'PRODUCT'
            AND products.id = stock_movements.item_id
        WHERE stock_movements.id = ?
        """,
        (movement_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def list_stock_adjustments(
    conn: sqlite3.Connection,
    item_type: str | None = None,
    reason: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    if item_type is not None:
        _validate_item_type(item_type)
    if reason is not None:
        _validate_reason(reason)

    query = """
        SELECT
            stock_movements.*,
            CASE
                WHEN stock_movements.item_type = 'MATERIAL' THEN materials.name
                WHEN stock_movements.item_type = 'PRODUCT' THEN products.name
            END AS item_name
        FROM stock_movements
        LEFT JOIN materials
            ON stock_movements.item_type = 'MATERIAL'
            AND materials.id = stock_movements.item_id
        LEFT JOIN products
            ON stock_movements.item_type = 'PRODUCT'
            AND products.id = stock_movements.item_id
        WHERE stock_movements.reason IN ('WASTE', 'ADJUSTMENT')
    """
    params: list = []

    if item_type is not None:
        query += " AND stock_movements.item_type = ?"
        params.append(item_type)
    if reason is not None:
        query += " AND stock_movements.reason = ?"
        params.append(reason)
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND stock_movements.movement_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND stock_movements.movement_date < ?"
        params.append(end_exclusive_utc)

    query += " ORDER BY stock_movements.movement_date DESC, stock_movements.id DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
