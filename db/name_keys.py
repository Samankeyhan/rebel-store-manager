"""Unique names per table, compared by `name_key` (db/names.py), so spelling variants of one name cannot be saved twice.
`duplicate_guard` wraps a create or rename: it pre-checks (against rows with a key AND rows whose key is still NULL, so a collision pair left by the backfill cannot be joined by a third row), and turns the unique index's IntegrityError into the duplicate error: the index is the final guard against a race.
`backfill_name_keys` (run by init_db) computes the key of existing rows without touching `name` or `updated_at`; rows whose key collides stay NULL and are reported. `find_name_collisions` is the read-only version."""

import contextlib
import logging
import re
import sqlite3

from db.errors import ConflictError, ErrorCode
from db.names import name_key

log = logging.getLogger(__name__)

# table -> entity label sent in the error details.
NAME_KEY_TABLES = {
    "products": "product",
    "materials": "material",
    "suppliers": "supplier",
    "partners": "partner",
    "categories": "category",
    "payment_methods": "payment_method",
    "packaging_kits": "packaging_kit",
    "expense_categories": "expense_category",
}

# Columns that, with the key, make a name unique: categories are unique among siblings.
SCOPE_COLUMNS = {"categories": ("kind", "parent_id")}

_UNIQUE_NAME = re.compile(r"UNIQUE constraint failed:.*\bname(_key)?\b")


def is_name_violation(exc: sqlite3.IntegrityError) -> bool:
    """A unique violation on `name` or `name_key` (not an FK, CHECK or other unique)."""
    return _UNIQUE_NAME.search(str(exc)) is not None


def _scope_sql(table: str, scope: dict | None) -> tuple[str, list]:
    columns = SCOPE_COLUMNS.get(table, ())
    values = scope or {}
    sql = "".join(f" AND {column} IS ?" for column in columns)
    return sql, [values.get(column) for column in columns]


def find_existing_id(
    conn: sqlite3.Connection,
    table: str,
    name: str,
    scope: dict | None = None,
    exclude_id: int | None = None,
) -> int | None:
    """Id of another row of `table` (within `scope`) whose name has the same key."""
    key = name_key(name)
    extra, params = _scope_sql(table, scope)
    rows = conn.execute(
        f"SELECT id, name, name_key FROM {table} "
        f"WHERE (name_key = ? OR name_key IS NULL){extra} ORDER BY id",
        [key, *params],
    ).fetchall()
    for row in rows:
        if row["id"] == exclude_id:
            continue
        if row["name_key"] == key or (row["name_key"] is None and name_key(row["name"]) == key):
            return row["id"]
    return None


def duplicate_error(
    table: str, name: str, existing_id: int | None, code: ErrorCode | None = None
) -> ConflictError:
    entity = NAME_KEY_TABLES[table]
    return ConflictError(
        f"A {entity.replace('_', ' ')} named '{name}' already exists "
        f"(the same name in a similar spelling counts).",
        code=code or ErrorCode.NAME_DUPLICATE,
        details={"entity": entity, "existing_id": existing_id},
    )


@contextlib.contextmanager
def duplicate_guard(
    conn: sqlite3.Connection,
    table: str,
    name: str,
    scope: dict | None = None,
    exclude_id: int | None = None,
    code: ErrorCode | None = None,
):
    """Use outside the write's own `transaction(conn)`:
    `with duplicate_guard(...): with transaction(conn): INSERT / UPDATE`.
    `name` is the stored form; `scope` = {"kind", "parent_id"} for categories."""
    existing = find_existing_id(conn, table, name, scope, exclude_id)
    if existing is not None:
        raise duplicate_error(table, name, existing, code)
    try:
        yield
    except sqlite3.IntegrityError as exc:
        if not is_name_violation(exc):
            raise
        existing = find_existing_id(conn, table, name, scope, exclude_id)
        raise duplicate_error(table, name, existing, code) from None


# ------------------------------------------------------------------- backfill


def _tables_with_key(conn: sqlite3.Connection) -> list[str]:
    return [
        table
        for table in NAME_KEY_TABLES
        if any(row["name"] == "name_key" for row in conn.execute(f"PRAGMA table_info({table})"))
    ]


def _plan(conn: sqlite3.Connection) -> tuple[list[tuple[str, int, str]], list[dict]]:
    """(assignments (table, id, key), collisions) for every row whose key is NULL."""
    assignments: list[tuple[str, int, str]] = []
    collisions: list[dict] = []
    for table in _tables_with_key(conn):
        scope_columns = SCOPE_COLUMNS.get(table, ())
        select = ", ".join(("id", "name", "name_key", *scope_columns))
        taken: dict[tuple, int] = {}  # (scope, key) -> id of a row that already has the key
        pending: dict[tuple, list[sqlite3.Row]] = {}
        for row in conn.execute(f"SELECT {select} FROM {table} ORDER BY id"):
            scope = tuple(row[c] for c in scope_columns)
            if row["name_key"] is not None:
                taken[(scope, row["name_key"])] = row["id"]
                continue
            pending.setdefault((scope, name_key(row["name"])), []).append(row)
        for (scope, key), rows in pending.items():
            ids = [r["id"] for r in rows]
            names = [r["name"] for r in rows]
            if key == "":
                collisions.append(
                    {"table": table, "name_key": key, "reason": "empty", "ids": ids, "names": names}
                )
            elif len(rows) > 1 or (scope, key) in taken:
                held = [taken[(scope, key)]] if (scope, key) in taken else []
                collisions.append({
                    "table": table, "name_key": key, "reason": "duplicate",
                    "ids": [*held, *ids], "names": names,
                })
            else:
                assignments.append((table, ids[0], key))
    return assignments, collisions


def find_name_collisions(conn: sqlite3.Connection) -> list[dict]:
    """Rows still without a key because their name collides (or has an empty key):
    [{table, name_key, reason, ids, names}]. Read-only."""
    return _plan(conn)[1]


def backfill_name_keys(conn: sqlite3.Connection) -> list[dict]:
    """Fill `name_key` where it is NULL and unique; leave colliding rows NULL. Never touches
    `name` or `updated_at` (the updated_at triggers ignore name_key) and writes no audit row
    (name_key is in UNAUDITED_COLUMNS). Idempotent. Returns the remaining collisions."""
    from db.connection import transaction

    with transaction(conn):
        assignments, collisions = _plan(conn)
        for table, row_id, key in assignments:
            conn.execute(f"UPDATE {table} SET name_key = ? WHERE id = ?", (key, row_id))
    for collision in collisions:
        log.warning(
            "name_key collision in %s (%s): ids %s, names %s; left without a key",
            collision["table"], collision["reason"], collision["ids"], collision["names"],
        )
    return collisions
