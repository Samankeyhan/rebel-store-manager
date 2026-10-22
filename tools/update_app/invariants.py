"""The figures a migration must not change, read-only, through the functions in `db/` (no formula is repeated here):
row count per table, the all-time profit and loss, every material and product row (stock, costs ...), the settlement totals.
`compare` looks only at what exists in BOTH databases (a new migration may add tables and columns) and ignores `schema_migrations`,
`sqlite_sequence` and time stamps; tables only in the after-database are INFO. Any other difference is a failure."""

from db.materials import list_materials
from db.products import list_products
from db.reports import get_profit_and_loss
from db.settlements import list_settlements
from tools.integrity_check.readonly import open_readonly

EXCLUDED_TABLES = {"schema_migrations", "sqlite_sequence"}
IGNORED_KEYS = {"created_at", "updated_at"}


def collect(path) -> dict:
    conn = open_readonly(path)
    try:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        counts = {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in sorted(tables) if name not in EXCLUDED_TABLES}
        settlements = list_settlements(conn)
        return {
            "migrations": sorted(row[0] for row in conn.execute("SELECT filename FROM schema_migrations")),
            "counts": counts,
            "profit_and_loss": get_profit_and_loss(conn),
            "materials": {row["id"]: row for row in list_materials(conn, active_only=False)},
            "products": {row["id"]: row for row in list_products(conn, active_only=False)},
            "settlements": {
                "count": len(settlements),
                "amount_received": sum(s["amount_received"] for s in settlements),
                "expected_amount": sum(s["expected_amount"] for s in settlements),
                "difference": sum(s["difference"] for s in settlements),
            },
        }
    finally:
        conn.close()


def _differences(label: str, before, after, out: list[str]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() & after.keys(), key=str):
            if key not in IGNORED_KEYS:
                _differences(f"{label}.{key}", before[key], after[key], out)
    elif before != after:
        out.append(f"{label}: {before!r} -> {after!r}")


def compare(before: dict, after: dict, new_files: list[str]) -> tuple[list[str], list[str]]:
    """(failures, info lines). `new_files` = migration files that were not applied before and exist now."""
    failures: list[str] = []
    info: list[str] = []
    applied_new = sorted(set(after["migrations"]) - set(before["migrations"]))
    if len(applied_new) != len(new_files):
        failures.append(f"schema_migrations grew by {len(applied_new)} rows but {len(new_files)} new migration files exist")
    if set(before["migrations"]) - set(after["migrations"]):
        failures.append("migrations disappeared from schema_migrations")
    for name in sorted(set(before["counts"]) - set(after["counts"])):
        failures.append(f"table {name} disappeared")
    for name in sorted(set(after["counts"]) - set(before["counts"])):
        info.append(f"new table {name}: {after['counts'][name]} rows")
    _differences("row count", before["counts"], after["counts"], failures)
    _differences("profit and loss", before["profit_and_loss"], after["profit_and_loss"], failures)
    _differences("settlements", before["settlements"], after["settlements"], failures)
    for kind in ("materials", "products"):
        for item_id in sorted(set(before[kind]) - set(after[kind])):
            failures.append(f"{kind} id {item_id} disappeared")
        for item_id in sorted(set(after[kind]) - set(before[kind])):
            failures.append(f"{kind} id {item_id} appeared")
        _differences(kind, before[kind], after[kind], failures)
    return failures, info
