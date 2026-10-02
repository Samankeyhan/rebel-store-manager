import sqlite3

from db.categories import validate_assignable
from db.connection import transaction
from db.errors import NotFoundError, ValidationError

VALID_TYPES = ("STOCK", "SERVICE")

# A material's category is optional (materials had none before migration 005);
# when set, its name and its parent's name come along.
_SELECT = """
    SELECT materials.*,
           c.name AS category_name,
           c.parent_id AS parent_category_id,
           pc.name AS parent_category_name
    FROM materials
    LEFT JOIN categories c ON c.id = materials.category_id
    LEFT JOIN categories pc ON pc.id = c.parent_id
"""


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
    category_id: int | None = None,
) -> int:
    _validate_type(type)
    _validate_unit_cost(unit_cost)
    if category_id is not None:
        validate_assignable(conn, category_id, "MATERIAL")

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
            INSERT INTO materials (name, type, unit, current_stock, unit_cost, category_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, type, unit, current_stock, unit_cost, category_id),
        )
    return cursor.lastrowid


def list_materials(
    conn: sqlite3.Connection, active_only: bool = True
) -> list[dict]:
    if active_only:
        rows = conn.execute(
            f"{_SELECT} WHERE materials.is_active = 1 ORDER BY materials.name"
        ).fetchall()
    else:
        rows = conn.execute(f"{_SELECT} ORDER BY materials.name").fetchall()
    return [dict(row) for row in rows]


def get_material(conn: sqlite3.Connection, material_id: int) -> dict | None:
    row = conn.execute(f"{_SELECT} WHERE materials.id = ?", (material_id,)).fetchone()
    return dict(row) if row is not None else None


def get_low_stock_materials(
    conn: sqlite3.Connection, threshold: float
) -> list[dict]:
    rows = conn.execute(
        f"""
        {_SELECT}
        WHERE materials.type = 'STOCK'
          AND materials.is_active = 1
          AND materials.current_stock <= ?
        ORDER BY materials.name
        """,
        (threshold,),
    ).fetchall()
    return [dict(row) for row in rows]


def deactivate_material(conn: sqlite3.Connection, material_id: int) -> None:
    with transaction(conn):
        conn.execute("UPDATE materials SET is_active = 0 WHERE id = ?", (material_id,))


def reactivate_material(conn: sqlite3.Connection, material_id: int) -> None:
    with transaction(conn):
        conn.execute("UPDATE materials SET is_active = 1 WHERE id = ?", (material_id,))


def set_material_category(
    conn: sqlite3.Connection, material_id: int, category_id: int
) -> None:
    if get_material(conn, material_id) is None:
        raise NotFoundError(f"Material with id {material_id} does not exist")
    validate_assignable(conn, category_id, "MATERIAL")
    with transaction(conn):
        conn.execute(
            "UPDATE materials SET category_id = ? WHERE id = ?", (category_id, material_id)
        )
