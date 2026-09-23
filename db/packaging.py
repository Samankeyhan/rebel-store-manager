import sqlite3

from db.connection import transaction
from db.errors import ConflictError, NotFoundError, ValidationError
from db.materials import get_material


def _validate_quantity(quantity: float) -> None:
    if quantity <= 0:
        raise ValidationError(f"quantity must be > 0, got {quantity}", field="quantity")


def _get_kit_row(conn: sqlite3.Connection, kit_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM packaging_kits WHERE id = ?", (kit_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"Packaging kit with id {kit_id} does not exist")
    return dict(row)


def _validate_kit_material(conn: sqlite3.Connection, material_id: int) -> dict:
    material = get_material(conn, material_id)
    if material is None:
        raise NotFoundError(f"Material with id {material_id} does not exist")
    if not material["is_active"] or material["type"] != "STOCK":
        raise ValidationError(
            f"Material '{material['name']}' must be an active STOCK material to be "
            f"used in a packaging kit",
            field="material_id",
        )
    return material


def create_kit(conn: sqlite3.Connection, name: str) -> int:
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO packaging_kits (name) VALUES (?)", (name,)
        )
    return cursor.lastrowid


def list_kits(conn: sqlite3.Connection, active_only: bool = True) -> list[dict]:
    if active_only:
        rows = conn.execute(
            "SELECT * FROM packaging_kits WHERE is_active = 1 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM packaging_kits ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def _get_kit_items(conn: sqlite3.Connection, kit_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            packaging_kit_items.id,
            packaging_kit_items.kit_id,
            packaging_kit_items.material_id,
            packaging_kit_items.quantity,
            materials.name AS material_name,
            materials.unit_cost AS material_unit_cost
        FROM packaging_kit_items
        JOIN materials ON materials.id = packaging_kit_items.material_id
        WHERE packaging_kit_items.kit_id = ?
        ORDER BY materials.name
        """,
        (kit_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def calculate_kit_cost(conn: sqlite3.Connection, kit_id: int) -> int:
    _get_kit_row(conn, kit_id)
    items = _get_kit_items(conn, kit_id)
    total = sum(item["quantity"] * item["material_unit_cost"] for item in items)
    return round(total)


def get_kit(conn: sqlite3.Connection, kit_id: int) -> dict:
    kit = _get_kit_row(conn, kit_id)
    kit["items"] = _get_kit_items(conn, kit_id)
    kit["kit_cost"] = calculate_kit_cost(conn, kit_id)
    return kit


def add_kit_item(
    conn: sqlite3.Connection, kit_id: int, material_id: int, quantity: float
) -> int:
    _validate_quantity(quantity)
    kit = _get_kit_row(conn, kit_id)
    material = _validate_kit_material(conn, material_id)

    try:
        with transaction(conn):
            cursor = conn.execute(
                """
                INSERT INTO packaging_kit_items (kit_id, material_id, quantity)
                VALUES (?, ?, ?)
                """,
                (kit_id, material_id, quantity),
            )
    except sqlite3.IntegrityError:
        raise ConflictError(
            f"Material '{material['name']}' is already in kit '{kit['name']}' — "
            f"use update_kit_item to change its quantity instead."
        ) from None
    return cursor.lastrowid


def update_kit_item(
    conn: sqlite3.Connection, kit_id: int, material_id: int, quantity: float
) -> None:
    _validate_quantity(quantity)
    with transaction(conn):
        cursor = conn.execute(
            """
            UPDATE packaging_kit_items
            SET quantity = ?
            WHERE kit_id = ? AND material_id = ?
            """,
            (quantity, kit_id, material_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(
                f"No kit item found for kit_id {kit_id} and material_id {material_id}. "
                f"Use add_kit_item to create one first."
            )


def remove_kit_item(
    conn: sqlite3.Connection, kit_id: int, material_id: int
) -> None:
    with transaction(conn):
        cursor = conn.execute(
            """
            DELETE FROM packaging_kit_items
            WHERE kit_id = ? AND material_id = ?
            """,
            (kit_id, material_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(
                f"No kit item found for kit_id {kit_id} and material_id {material_id}."
            )


def deactivate_kit(conn: sqlite3.Connection, kit_id: int) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE packaging_kits SET is_active = 0 WHERE id = ?", (kit_id,)
        )
