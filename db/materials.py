import sqlite3

from db.connection import transaction
from db.errors import ValidationError

VALID_TYPES = ("STOCK", "SERVICE")


def _validate_type(material_type: str) -> None:
    if material_type not in VALID_TYPES:
        valid = ", ".join(VALID_TYPES)
        raise ValidationError(
            f"Invalid type '{material_type}'. Must be one of: {valid}", field="type"
        )


def _validate_unit_cost(unit_cost: int) -> None:
    if unit_cost < 0:
        raise ValidationError(f"unit_cost must be >= 0, got {unit_cost}", field="unit_cost")


def add_material(
    conn: sqlite3.Connection,
    name: str,
    type: str,
    unit_cost: int,
    unit: str = "piece",
    initial_stock: float | None = None,
) -> int:
    _validate_type(type)
    _validate_unit_cost(unit_cost)

    if type == "SERVICE":
        if initial_stock is not None:
            raise ValidationError(
                "SERVICE materials cannot have initial_stock", field="initial_stock"
            )
        current_stock = None
    else:
        current_stock = initial_stock if initial_stock is not None else 0

    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO materials (name, type, unit, current_stock, unit_cost)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, type, unit, current_stock, unit_cost),
        )
    return cursor.lastrowid


def list_materials(
    conn: sqlite3.Connection, active_only: bool = True
) -> list[dict]:
    if active_only:
        rows = conn.execute(
            "SELECT * FROM materials WHERE is_active = 1 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM materials ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def get_material(conn: sqlite3.Connection, material_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM materials WHERE id = ?", (material_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def get_low_stock_materials(
    conn: sqlite3.Connection, threshold: float
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM materials
        WHERE type = 'STOCK'
          AND is_active = 1
          AND current_stock <= ?
        ORDER BY name
        """,
        (threshold,),
    ).fetchall()
    return [dict(row) for row in rows]


def deactivate_material(conn: sqlite3.Connection, material_id: int) -> None:
    with transaction(conn):
        conn.execute("UPDATE materials SET is_active = 0 WHERE id = ?", (material_id,))
