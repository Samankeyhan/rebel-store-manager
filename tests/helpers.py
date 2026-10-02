"""Shared test helpers (plain functions; fixtures live in conftest.py)."""

import sqlite3

from db.constants import LEGACY_PRODUCT_CATEGORIES


def cat(conn: sqlite3.Connection, code: str = "OTHER") -> int:
    """Id of the top-level PRODUCT category migration 005 seeded for a legacy code."""
    row = conn.execute(
        "SELECT id FROM categories WHERE kind = 'PRODUCT' AND parent_id IS NULL AND name = ?",
        (LEGACY_PRODUCT_CATEGORIES[code],),
    ).fetchone()
    return row["id"]
