"""Shared test helpers (plain functions; fixtures live in conftest.py)."""

import sqlite3

from db.constants import LEGACY_PRODUCT_CATEGORIES
from db.products import add_product


def cat(conn: sqlite3.Connection, code: str = "OTHER") -> int:
    """Id of the top-level PRODUCT category migration 005 seeded for a legacy code."""
    row = conn.execute(
        "SELECT id FROM categories WHERE kind = 'PRODUCT' AND parent_id IS NULL AND name = ?",
        (LEGACY_PRODUCT_CATEGORIES[code],),
    ).fetchone()
    return row["id"]


def stocked_product(
    conn: sqlite3.Connection, name: str = "Test LP", stock: int = 100, unit_cost: int = 500
) -> int:
    """An active VINYL product with stock and a unit cost, ready to sell."""
    product_id = add_product(conn, name, cat(conn, "VINYL"), 3000, 2000)
    conn.execute(
        "UPDATE products SET current_stock = ?, unit_cost = ? WHERE id = ?",
        (stock, unit_cost, product_id),
    )
    conn.commit()
    return product_id
