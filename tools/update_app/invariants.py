"""The figures a migration must not change, read-only, through the functions in `db/` (no formula is repeated here):
row count per table, the all-time profit and loss, every material and product row (stock, costs ...), every order row
(every column, voided ones included: migration 014 rebuilt the table), every purchase row (every stored column, read
from the tables: migration 015 rebuilt them, and the purchase reads of this code need its columns), the settlement totals.
`compare` looks only at what exists in BOTH databases (a new migration may add tables and columns) and ignores `schema_migrations`,
`sqlite_sequence` and time stamps; tables only in the after-database are INFO. Any other difference is a failure.
Supplier payables (migration 015): when the payment tables are new, the backfill must leave nothing owed (every
supplier's outstanding is 0) and exactly one payment per purchase with a total; INFO lines count the payments and the
purchases a later cancel cannot use (no movement link, no cost snapshot)."""

from db.materials import list_materials
from db.orders import list_orders
from db.products import list_products
from db.reports import get_profit_and_loss
from db.settlements import list_settlements
from db.supplier_payments import payables_outstanding
from tools.integrity_check.readonly import open_readonly

EXCLUDED_TABLES = {"schema_migrations", "sqlite_sequence"}
IGNORED_KEYS = {"created_at", "updated_at"}
PURCHASE_TABLES = (("MATERIAL", "material_purchases"), ("PRODUCT", "product_purchases"))


def _payables(conn, tables) -> dict | None:
    """What the backfill must give, when the database has supplier payments (None before migration 015)."""
    if "supplier_payments" not in tables:
        return None
    with_total = sum(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE total_paid > 0").fetchone()[0] for _, table in PURCHASE_TABLES)
    return {
        "outstanding": payables_outstanding(conn),
        "payments": conn.execute("SELECT COUNT(*) FROM supplier_payments").fetchone()[0],
        "purchases_with_total": with_total,
        "without_movement_link": sum(
            conn.execute(f"SELECT COUNT(*) FROM {table} WHERE stock_movement_id IS NULL").fetchone()[0] for _, table in PURCHASE_TABLES
        ),
        "without_cost_snapshot": sum(
            conn.execute(f"SELECT COUNT(*) FROM {table} WHERE item_cost_after IS NULL").fetchone()[0] for _, table in PURCHASE_TABLES
        ),
    }


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
            "orders": {row["id"]: row for row in list_orders(conn, include_voided=True)},
            "purchases": {
                f"{kind}:{row['id']}": dict(row)
                for kind, table in PURCHASE_TABLES
                for row in conn.execute(f"SELECT * FROM {table} ORDER BY id")
            },
            "settlements": {
                "count": len(settlements),
                "amount_received": sum(s["amount_received"] for s in settlements),
                "expected_amount": sum(s["expected_amount"] for s in settlements),
                "difference": sum(s["difference"] for s in settlements),
            },
            "payables": _payables(conn, tables),
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


def _payables_checks(before: dict, after: dict, failures: list[str], info: list[str]) -> None:
    payables = after.get("payables")
    if payables is None:
        return
    if before.get("payables") is None:  # the payment tables are new: the backfill
        if payables["outstanding"] != 0:
            failures.append(f"payables: {payables['outstanding']} owed to suppliers right after the backfill (must be 0)")
        if payables["payments"] != payables["purchases_with_total"]:
            failures.append(
                f"payables: {payables['payments']} payments backfilled for {payables['purchases_with_total']} purchases with a total"
            )
        info.append(f"supplier payments backfilled: {payables['payments']} (purchases with a total: {payables['purchases_with_total']})")
    else:
        _differences("payables", before["payables"], payables, failures)
    info.append(f"purchases without a movement link: {payables['without_movement_link']}")
    info.append(f"purchases without a cost snapshot (cannot be cancelled later): {payables['without_cost_snapshot']}")


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
    for kind in ("materials", "products", "orders", "purchases"):
        rows_before, rows_after = before.get(kind, {}), after.get(kind, {})
        for item_id in sorted(set(rows_before) - set(rows_after), key=str):
            failures.append(f"{kind} id {item_id} disappeared")
        for item_id in sorted(set(rows_after) - set(rows_before), key=str):
            failures.append(f"{kind} id {item_id} appeared")
        _differences(kind, rows_before, rows_after, failures)
    _payables_checks(before, after, failures, info)
    return failures, info
