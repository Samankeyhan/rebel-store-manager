"""Raw materials (STOCK or SERVICE): CRUD, optional category, move category, deactivate/reactivate,
optional minimum stock.

`min_stock` is an optional quantity in the material's own unit (REAL, like `current_stock`);
NULL = no minimum. SERVICE materials hold no stock and never have one. Only `min_stock`
is updatable (`update_material`: omitted = unchanged, None = clear).
Low stock (one rule, `_LOW_STOCK`): an active STOCK material with `current_stock <= 0`,
or with `min_stock` set and `current_stock <= min_stock` (exact `<=` on REAL; 0 is a valid
minimum). Every row carries it as `is_low_stock` (0/1). `get_low_stock_materials()`
without a threshold returns those rows, most urgent first; passing `threshold` is the
legacy flat cut-off (`current_stock <= threshold`, by name) and ignores `min_stock`.
Products have no minimum."""

import math
import sqlite3

from db.categories import validate_assignable
from db.connection import transaction
from db.errors import NotFoundError, ValidationError

VALID_TYPES = ("STOCK", "SERVICE")
UPDATABLE_FIELDS = ("min_stock",)

# The low-stock rule; the is_low_stock column and get_low_stock_materials both use it.
_LOW_STOCK = """
    materials.type = 'STOCK'
    AND materials.is_active = 1
    AND (
        materials.current_stock <= 0
        OR (materials.min_stock IS NOT NULL AND materials.current_stock <= materials.min_stock)
    )
"""

# A material's category is optional (materials had none before migration 005);
# when set, its name and its parent's name come along.
_SELECT = """
    SELECT materials.*,
           CASE WHEN {low} THEN 1 ELSE 0 END AS is_low_stock,
           c.name AS category_name,
           c.parent_id AS parent_category_id,
           pc.name AS parent_category_name
    FROM materials
    LEFT JOIN categories c ON c.id = materials.category_id
    LEFT JOIN categories pc ON pc.id = c.parent_id
""".format(low=_LOW_STOCK)


def _validate_type(material_type: str) -> None:
    if material_type not in VALID_TYPES:
        valid = ", ".join(VALID_TYPES)
        raise ValidationError(
            f"Invalid type '{material_type}'. Must be one of: {valid}", field="type"
        )


def _validate_unit_cost(unit_cost: int) -> None:
    if unit_cost < 0:
        raise ValidationError(f"unit_cost must be >= 0, got {unit_cost}", field="unit_cost")


def _validate_min_stock(min_stock, material_type: str) -> None:
    if min_stock is None:
        return
    if isinstance(min_stock, bool) or not isinstance(min_stock, (int, float)):
        raise ValidationError(
            f"min_stock must be a number, got {min_stock!r}", field="min_stock"
        )
    if not math.isfinite(min_stock) or min_stock < 0:
        raise ValidationError(f"min_stock must be >= 0, got {min_stock}", field="min_stock")
    if material_type == "SERVICE":
        raise ValidationError(
            "SERVICE materials have no stock and cannot have a min_stock", field="min_stock"
        )


def add_material(
    conn: sqlite3.Connection,
    name: str,
    type: str,
    unit_cost: int,
    unit: str = "piece",
    initial_stock: float | None = None,
    category_id: int | None = None,
    min_stock: float | None = None,
) -> int:
    _validate_type(type)
    _validate_unit_cost(unit_cost)
    _validate_min_stock(min_stock, type)
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
            INSERT INTO materials
                (name, type, unit, current_stock, unit_cost, category_id, min_stock)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, type, unit, current_stock, unit_cost, category_id, min_stock),
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


def update_material(conn: sqlite3.Connection, material_id: int, **fields) -> None:
    """Partial update; only `min_stock` (None clears it). The updated_at trigger stamps the row."""
    for field_name in fields:
        if field_name not in UPDATABLE_FIELDS:
            raise ValidationError(f"Unknown field '{field_name}'", field=field_name)
    current = get_material(conn, material_id)
    if current is None:
        raise NotFoundError(f"Material with id {material_id} does not exist")
    if not fields:
        return
    if "min_stock" in fields:
        _validate_min_stock(fields["min_stock"], current["type"])

    assignments = ", ".join(f"{name} = ?" for name in fields)
    with transaction(conn):
        conn.execute(
            f"UPDATE materials SET {assignments} WHERE id = ?",
            [*fields.values(), material_id],
        )


def get_low_stock_materials(
    conn: sqlite3.Connection, threshold: float | None = None
) -> list[dict]:
    """Without a threshold: every low material (`_LOW_STOCK`), most urgent first —
    current_stock / min_stock ascending (0 when stock <= 0 or there is no or a zero
    minimum), then name, then id. With a threshold: the legacy flat cut-off."""
    if threshold is None:
        rows = conn.execute(
            f"""
            {_SELECT}
            WHERE {_LOW_STOCK}
            ORDER BY
                CASE
                    WHEN materials.current_stock <= 0
                         OR materials.min_stock IS NULL
                         OR materials.min_stock = 0 THEN 0
                    ELSE materials.current_stock / materials.min_stock
                END,
                materials.name,
                materials.id
            """
        ).fetchall()
        return [dict(row) for row in rows]

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
