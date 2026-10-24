"""The go-live reset: turns a test database into a clean production database, once (docs/RUNNING.md, "Go-live reset").
Every table has exactly one class (`TABLE_CLASS`; `unclassified_tables` finds a table a new migration forgot): KEEP (setup data, never touched), CLEAR (transactions, emptied; their ids restart), VALUE (products, materials, counters, payment methods, the audit log: only the named values change) or BOOKKEEPING.
`apply_go_live` does everything in ONE transaction (the CLI probes for a lock first) (clear, merge the duplicate payment method, stock and cost to 0, counters to 0, `reset_audit_log` last, the marker, then the checks): any problem rolls all of it back and removes the archive file it made. It never takes a backup, prompts or prints: the CLI (tools/go_live_reset) does.
Unit cost: products NULL ("cost unknown", the stocktake then asks for it) or 0; STOCK materials 0 (the column is NOT NULL); SERVICE materials keep theirs unless asked. `updated_at` is restored after the value reset (a reset is not an edit).
A database that went live is never reset again. Three markers, any one is enough: `PRAGMA user_version` = GO_LIVE_USER_VERSION (a database header field: it survives `reset_audit_log` and the online backup API), the `go_live_marker` row in `settings` (KEEP class, so a reset leaves it), or an audit row left by this reset (archive named `audit-archive-golive-…`); a plain older audit reset is not a marker.
`heal_marker` (run by `init_db`) sets the header again when it is 0 and one of the other two exists, never from nothing. `mark_live` marks a database that went live without the reset (it has orders): the owner's explicit step (`python -m tools.go_live_reset --mark-live`)."""

import json
import sqlite3
from pathlib import Path
from typing import Callable

from db.audit import audit_operation, reset_audit_log
from db.connection import transaction
from db.errors import ConflictError, ValidationError
from db.name_keys import backfill_name_keys, find_name_collisions
from db.timeutil import now_utc

GO_LIVE_USER_VERSION = 1
ARCHIVE_PREFIX = "audit-archive-golive-"
OPERATION = "go_live_reset"
MARK_LIVE_OPERATION = "mark_live"
SETTING_KEY = "go_live_marker"  # settings row, JSON {"method": "reset" | "mark_live", "at": UTC moment}
METHOD_RESET, METHOD_MARK_LIVE = "reset", "mark_live"

KEEP, CLEAR, VALUE, BOOKKEEPING = "KEEP", "CLEAR", "VALUE", "BOOKKEEPING"

# Rows are deleted in this order (children, then parents): supplier payment allocations point at payments and purchases,
# purchases point at their stock movements, stock_movements points at orders and batches.
CLEAR_ORDER = (
    "supplier_payment_allocations", "supplier_payments",
    "material_purchases", "product_purchases",
    "stock_movements", "order_items", "orders", "settlements",
    "production_batch_materials", "production_batches",
    "expenses", "postage_batches",
    "distribution_shares", "profit_distributions",
)

TABLE_CLASS = {
    **{table: CLEAR for table in CLEAR_ORDER},
    **{table: KEEP for table in (
        "categories", "suppliers", "partners", "packaging_kits", "packaging_kit_items", "product_recipe",
        "expense_categories", "settings", "channel_settings",
    )},
    **{table: VALUE for table in ("products", "materials", "counters", "payment_methods", "audit_log")},
    **{table: BOOKKEEPING for table in ("schema_migrations", "audit_context", "audit_control")},
}

# the only name collision the reset resolves: the same payment method typed twice
DUPLICATE_PAYMENT_METHOD = ("DigiPay", "digipay")
SURVIVOR_NAME = "DigiPay"

PRODUCT_COST_CHOICES = ("null", "zero")


def user_tables(conn: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def unclassified_tables(conn: sqlite3.Connection) -> list[str]:
    """Tables the reset has no class for (a new migration must classify its table here)."""
    return [table for table in user_tables(conn) if table not in TABLE_CLASS]


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in user_tables(conn)}


# ------------------------------------------------------------------- marker and state


def _reset_rows(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT before_json FROM audit_log WHERE operation = 'reset_audit_log'").fetchall()
    result = []
    for row in rows:
        try:
            result.append(json.loads(row[0] or "{}"))
        except ValueError:
            result.append({})
    return result


def _flag_row(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (SETTING_KEY,)).fetchone()
    if row is None:
        return None
    try:
        value = json.loads(row[0] or "{}")
    except ValueError:
        value = {}
    return value if isinstance(value, dict) else {}


def live_markers(conn: sqlite3.Connection) -> list[str]:
    """Which go-live markers this database carries ([] = it never went live)."""
    found = []
    if conn.execute("PRAGMA user_version").fetchone()[0] == GO_LIVE_USER_VERSION:
        found.append("user_version")
    if any(str(row.get("archive", "")).startswith(ARCHIVE_PREFIX) for row in _reset_rows(conn)):
        found.append("audit_archive_tag")
    if _flag_row(conn) is not None:
        found.append("settings_flag")
    return found


def marker_method(conn: sqlite3.Connection) -> str | None:
    """How the settings flag says the database was marked ("reset" / "mark_live"), None without a flag."""
    flag = _flag_row(conn)
    return None if flag is None else flag.get("method")


def _write_flag(conn: sqlite3.Connection, method: str) -> None:
    value = json.dumps({"method": method, "at": now_utc()}, sort_keys=True)
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (SETTING_KEY, value),
    )


def heal_marker(conn: sqlite3.Connection) -> bool:
    """Put the header marker back when it reads 0 and the database still carries another marker (the audit tag or the
    settings flag). Never sets it from nothing and writes nothing else: no row, no audit entry changes. True = it was set."""
    if conn.execute("PRAGMA user_version").fetchone()[0] != 0:
        return False
    try:
        evidence = set(live_markers(conn)) & {"audit_archive_tag", "settings_flag"}
    except sqlite3.OperationalError:  # a database at a schema before the audit log / settings tables: nothing to go on
        return False
    if not evidence:
        return False
    conn.execute(f"PRAGMA user_version = {GO_LIVE_USER_VERSION}")
    return True


def database_facts(conn: sqlite3.Connection) -> dict:
    """What `mark_live` looks at: order count, first and last order day (UTC date part), the header value, the markers."""
    first, last, count = conn.execute("SELECT MIN(order_date), MAX(order_date), COUNT(*) FROM orders").fetchone()
    return {
        "orders": count,
        "first_order_day": first[:10] if first else None,
        "last_order_day": last[:10] if last else None,
        "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
        "markers": live_markers(conn),
    }


def mark_live(conn: sqlite3.Connection) -> dict:
    """Mark a database that went live without the reset: header + settings flag (method "mark_live"), one transaction, one
    audit row for the flag. Refuses a database with no orders or one that already carries a marker; changes nothing else."""
    if conn.in_transaction:
        raise ValidationError("mark_live needs a connection with no open transaction")
    with transaction(conn):
        facts = database_facts(conn)
        if facts["markers"]:
            raise ConflictError(f"This database is already marked live ({', '.join(facts['markers'])})")
        if not facts["orders"]:
            raise ConflictError("This database has no orders: there is nothing to protect yet (use the go-live reset instead)")
        with audit_operation(conn, MARK_LIVE_OPERATION):
            _write_flag(conn, METHOD_MARK_LIVE)
        conn.execute(f"PRAGMA user_version = {GO_LIVE_USER_VERSION}")
    return {**facts, "markers": live_markers(conn)}


def _clean_problems(conn: sqlite3.Connection, product_unit_cost: str, reset_service_costs: bool) -> list[str]:
    """What differs from the state after a reset (empty list = nothing left to reset)."""
    problems = []
    for table, count in table_counts(conn).items():
        if TABLE_CLASS.get(table) == CLEAR and count:
            problems.append(f"{table}: {count} rows")
    stocked = conn.execute("SELECT COUNT(*) FROM products WHERE current_stock != 0").fetchone()[0]
    stocked += conn.execute("SELECT COUNT(*) FROM materials WHERE type = 'STOCK' AND current_stock != 0").fetchone()[0]
    if stocked:
        problems.append(f"{stocked} products/materials hold stock")
    wanted = "unit_cost IS NOT NULL" if product_unit_cost == "null" else "unit_cost IS NOT 0"
    costly = conn.execute(f"SELECT COUNT(*) FROM products WHERE {wanted}").fetchone()[0]
    scope = "" if reset_service_costs else " AND type = 'STOCK'"
    costly += conn.execute(f"SELECT COUNT(*) FROM materials WHERE unit_cost != 0{scope}").fetchone()[0]
    if costly:
        problems.append(f"{costly} products/materials have a unit cost")
    if conn.execute("SELECT COUNT(*) FROM counters WHERE value != 0").fetchone()[0]:
        problems.append("an invoice counter is not 0")
    if find_name_collisions(conn):
        problems.append("name collisions")
    return problems


def assess(conn: sqlite3.Connection, product_unit_cost: str = "null", reset_service_costs: bool = False) -> dict:
    """{state, markers, problems}: state is "ready" (the reset may run), "already_reset" (marked and nothing left to reset)
    or "live" (marked, and there is data: the reset must refuse)."""
    markers = live_markers(conn)
    problems = _clean_problems(conn, product_unit_cost, reset_service_costs)
    if not markers:
        state = "ready"
    elif problems:
        state = "live"
    else:
        state = "already_reset"
    return {"state": state, "markers": markers, "problems": problems}


def value_summary(conn: sqlite3.Connection) -> dict:
    """The values the reset changes, for the report: rows holding stock or a unit cost, and the counters."""
    one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "products_with_stock": one("SELECT COUNT(*) FROM products WHERE current_stock != 0"),
        "products_with_unit_cost": one("SELECT COUNT(*) FROM products WHERE unit_cost IS NOT NULL"),
        "products_with_unit_cost_above_0": one("SELECT COUNT(*) FROM products WHERE unit_cost > 0"),
        "stock_materials_with_stock": one("SELECT COUNT(*) FROM materials WHERE type = 'STOCK' AND current_stock != 0"),
        "materials_with_unit_cost_above_0": one("SELECT COUNT(*) FROM materials WHERE unit_cost > 0"),
        "counters": {row["name"]: row["value"] for row in conn.execute("SELECT name, value FROM counters ORDER BY name")},
    }


def payment_method_merge(conn: sqlite3.Connection) -> dict | None:
    """{survivor_id, duplicate_id, names} when the only name collision is the DigiPay pair, None when there is no
    collision; any other collision raises ConflictError."""
    collisions = find_name_collisions(conn)
    if not collisions:
        return None
    wanted = set(DUPLICATE_PAYMENT_METHOD)
    if len(collisions) != 1 or collisions[0]["table"] != "payment_methods" or set(collisions[0]["names"]) != wanted:
        raise ConflictError(
            "The reset only resolves the payment method duplicate DigiPay / digipay; other name collisions: "
            + "; ".join(f"{c['table']} ids {c['ids']} {c['names']}" for c in collisions)
        )
    rows = conn.execute(
        "SELECT id, name FROM payment_methods WHERE name IN (?, ?) ORDER BY id", DUPLICATE_PAYMENT_METHOD
    ).fetchall()
    survivors = [r["id"] for r in rows if r["name"] == SURVIVOR_NAME]
    duplicates = [r["id"] for r in rows if r["name"] != SURVIVOR_NAME]
    if len(survivors) != 1 or len(duplicates) != 1:
        raise ConflictError(f"Cannot tell the surviving payment method apart: {[dict(r) for r in rows]}")
    return {"survivor_id": survivors[0], "duplicate_id": duplicates[0], "names": list(DUPLICATE_PAYMENT_METHOD)}


# ------------------------------------------------------------------------- the steps


def _clear(conn: sqlite3.Connection) -> dict[str, int]:
    return {table: conn.execute(f"DELETE FROM {table}").rowcount for table in CLEAR_ORDER}


def _merge_payment_methods(conn: sqlite3.Connection, merge: dict | None) -> int:
    """Re-point every foreign key to payment_methods from the duplicate to the survivor (found with PRAGMA
    foreign_key_list, so a future table is covered), delete the duplicate, then give the survivor its name_key."""
    repointed = 0
    if merge is not None:
        for table in user_tables(conn):
            for fk in conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
                if fk["table"] == "payment_methods":
                    repointed += conn.execute(
                        f'UPDATE "{table}" SET "{fk["from"]}" = ? WHERE "{fk["from"]}" = ?',
                        (merge["survivor_id"], merge["duplicate_id"]),
                    ).rowcount
        conn.execute("DELETE FROM payment_methods WHERE id = ?", (merge["duplicate_id"],))
    remaining = backfill_name_keys(conn)
    if remaining:
        raise ConflictError(f"Name collisions remain after the merge: {remaining}")
    return repointed


def _restoring_updated_at(conn: sqlite3.Connection, table: str, statements: list[tuple[str, tuple]]) -> None:
    """Run the statements, then put every row's updated_at back (the updated_at trigger fires on stock and cost)."""
    saved = [(row["id"], row["updated_at"]) for row in conn.execute(f"SELECT id, updated_at FROM {table}")]
    for sql, params in statements:
        conn.execute(sql, params)
    conn.executemany(f"UPDATE {table} SET updated_at = ? WHERE id = ?", [(stamp, row_id) for row_id, stamp in saved])


def _reset_values(conn: sqlite3.Connection, product_unit_cost: str, reset_service_costs: bool) -> None:
    cost = None if product_unit_cost == "null" else 0
    _restoring_updated_at(conn, "products", [("UPDATE products SET current_stock = 0, unit_cost = ?", (cost,))])
    scope = "" if reset_service_costs else " WHERE type = 'STOCK'"
    _restoring_updated_at(conn, "materials", [
        ("UPDATE materials SET current_stock = 0 WHERE type = 'STOCK'", ()),
        (f"UPDATE materials SET unit_cost = 0{scope}", ()),
    ])
    conn.execute("UPDATE counters SET value = 0")
    marks = ", ".join("?" for _ in CLEAR_ORDER)
    conn.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({marks})", CLEAR_ORDER)


def archive_path_for(db_folder: str | Path) -> Path:
    """<database folder>/backups/audit-archive-golive-<UTC stamp>.jsonl (never overwritten: a clash gets -1, -2 …)."""
    stamp = now_utc().replace("-", "").replace(":", "").replace(" ", "-")
    folder = Path(db_folder) / "backups"
    path = folder / f"{ARCHIVE_PREFIX}{stamp}.jsonl"
    suffix = 1
    while path.exists():
        path = folder / f"{ARCHIVE_PREFIX}{stamp}-{suffix}.jsonl"
        suffix += 1
    return path


def _self_check(conn: sqlite3.Connection, product_unit_cost: str, reset_service_costs: bool) -> list[str]:
    problems = []
    if conn.execute("PRAGMA integrity_check").fetchall()[0][0] != "ok":
        problems.append("PRAGMA integrity_check is not ok")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        problems.append(f"{len(violations)} foreign key violations")
    problems += _clean_problems(conn, product_unit_cost, reset_service_costs)
    if conn.execute("PRAGMA user_version").fetchone()[0] != GO_LIVE_USER_VERSION:
        problems.append("the go-live marker is not set")
    audit = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    if audit != 1:
        problems.append(f"the audit log holds {audit} rows, not the single reset row")
    return problems


def apply_go_live(
    conn: sqlite3.Connection,
    archive_path: str | Path,
    product_unit_cost: str = "null",
    reset_service_costs: bool = False,
    verify: Callable[[sqlite3.Connection], list[str]] | None = None,
) -> dict:
    """Run the whole reset in one transaction on `conn` (from `get_connection`, no transaction open).
    `verify(conn)` returns problem texts from further checks (the CLI passes the integrity check); any problem, any error:
    rollback, the archive file removed, ConflictError / the original error raised. Returns before/after counts and details."""
    if product_unit_cost not in PRODUCT_COST_CHOICES:
        raise ValidationError(f"product_unit_cost must be one of {PRODUCT_COST_CHOICES}", field="product_unit_cost")
    if conn.in_transaction:
        raise ValidationError("apply_go_live needs a connection with no open transaction")
    missing = unclassified_tables(conn)
    if missing:
        raise ValidationError(f"Tables without a go-live class: {missing}", field="tables")
    path = Path(archive_path)
    made_archive = not path.exists()

    try:
        with transaction(conn):
            state = assess(conn, product_unit_cost, reset_service_costs)
            if state["state"] == "live":
                raise ConflictError(
                    "This database already went live and holds data: the reset never erases a live database ("
                    + "; ".join(state["problems"]) + ")"
                )
            if state["state"] == "already_reset":
                raise ConflictError("This database was already reset and nothing is left to reset")
            before = table_counts(conn)
            values_before = value_summary(conn)
            merge = payment_method_merge(conn)
            with audit_operation(conn, OPERATION):
                cleared = _clear(conn)
                repointed = _merge_payment_methods(conn, merge)
                _reset_values(conn, product_unit_cost, reset_service_costs)
                _write_flag(conn, METHOD_RESET)
                archive = reset_audit_log(conn, archive_path=path)
            conn.execute(f"PRAGMA user_version = {GO_LIVE_USER_VERSION}")
            problems = _self_check(conn, product_unit_cost, reset_service_costs)
            if verify is not None:
                problems += verify(conn)
            if problems:
                raise ConflictError("The reset was rolled back: " + "; ".join(problems))
            after = table_counts(conn)
            values_after = value_summary(conn)
    except BaseException:
        if made_archive:
            path.unlink(missing_ok=True)
        raise
    return {
        "before": before, "after": after, "values_before": values_before, "values_after": values_after, "cleared": cleared, "merge": merge, "references_repointed": repointed,
        "archive": archive, "markers": live_markers(conn),
    }
