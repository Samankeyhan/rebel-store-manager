"""The figures a migration must not change, read-only, through the functions in `db/` (no formula is repeated here):
row count per table, the all-time profit and loss, every material and product row (stock, costs ...), every order row
(every column, voided ones included: migration 014 rebuilt the table), every purchase (read as one row per purchase
line with every column it had before 016, whichever schema the database is at: migration 016 moved supplier, PUR number,
day, note and status to the purchase invoice, so a 016 line is read back through its invoice), every supplier payment and
allocation (an allocation names the purchase line it pays, through its invoice), the invoice counters and the settlement
totals. `compare` looks only at what exists in BOTH databases (a new migration may add tables and columns) and ignores
`schema_migrations`, `sqlite_sequence` and time stamps; tables only in the after-database are INFO. Any other difference
is a failure, and so is a column of the before-database that the after-database no longer has for a purchase.
Supplier payables (migration 015): when the payment tables are new, the backfill must leave nothing owed (every
supplier's outstanding is 0) and exactly one payment per purchase with a total. Purchase invoices (migration 016): every
purchase line is its own one-line invoice, every allocation keeps its payment, amount and the line it paid, and the
payables per supplier and the all-time purchases summary are the same; INFO lines count the invoices created and the
purchases a later cancel cannot use (no movement link, no cost snapshot).
Before 016 the payables and the summary are read here from the tables as they were (the code in `db/` reads invoices)."""

from db.materials import list_materials
from db.orders import list_orders
from db.products import list_products
from db.reports import get_profit_and_loss, get_purchases_summary
from db.settlements import list_settlements
from db.supplier_payments import get_payables, payables_outstanding
from tools.integrity_check.readonly import open_readonly

EXCLUDED_TABLES = {"schema_migrations", "sqlite_sequence"}
IGNORED_KEYS = {"created_at", "updated_at"}
# kind, line table, item column
PURCHASE_TABLES = (("MATERIAL", "material_purchases", "material_id"), ("PRODUCT", "product_purchases", "product_id"))
NO_SUPPLIER = "none"
# the purchase columns migration 016 moved to the invoice, read back for the line (replaces_purchase_id is mapped)
INVOICE_COLUMNS = ("supplier_id", "invoice_number", "purchase_date", "notes", "status", "cancel_reason", "cancelled_at")


def _supplier_key(supplier_id) -> str:
    return NO_SUPPLIER if supplier_id is None else str(supplier_id)


def _line_of_invoice(conn) -> dict:
    """{invoice id: (kind, line id)} for a database at 016; an invoice with other than one line is ("INVOICE", id)."""
    lines: dict = {}
    for kind, table, _ in PURCHASE_TABLES:
        for row in conn.execute(f"SELECT id, purchase_invoice_id FROM {table} ORDER BY id"):
            lines.setdefault(row["purchase_invoice_id"], []).append((kind, row["id"]))
    return {
        invoice_id: found[0] if len(found) == 1 else ("INVOICE", invoice_id)
        for invoice_id, found in lines.items()
    }


def _purchases(conn, invoiced: bool) -> dict:
    """{"KIND:line id": row} with every column a purchase row had before 016 (and the new ones besides)."""
    if not invoiced:
        return {
            f"{kind}:{row['id']}": dict(row)
            for kind, table, _ in PURCHASE_TABLES
            for row in conn.execute(f"SELECT * FROM {table} ORDER BY id")
        }
    line_of = _line_of_invoice(conn)
    rows = {}
    for kind, table, _ in PURCHASE_TABLES:
        for row in conn.execute(
            f"SELECT l.*, {', '.join('i.' + c for c in INVOICE_COLUMNS)}, i.replaces_invoice_id "
            f"FROM {table} AS l JOIN purchase_invoices AS i ON i.id = l.purchase_invoice_id ORDER BY l.id"
        ):
            purchase = dict(row)
            replaced = purchase.pop("replaces_invoice_id")
            target = line_of.get(replaced) if replaced is not None else None
            purchase["replaces_purchase_id"] = target[1] if target and target[0] == kind else (None if replaced is None else -replaced)
            rows[f"{kind}:{row['id']}"] = purchase
    return rows


def _allocations(conn, invoiced: bool) -> dict:
    """{allocation id: {payment_id, purchase ("KIND:line id"), amount}}: an allocation names the purchase line it pays."""
    if not invoiced:
        return {
            row["id"]: {
                "payment_id": row["payment_id"],
                "purchase": f"MATERIAL:{row['material_purchase_id']}" if row["material_purchase_id"] is not None
                else f"PRODUCT:{row['product_purchase_id']}",
                "amount": row["amount"],
            }
            for row in conn.execute("SELECT * FROM supplier_payment_allocations ORDER BY id")
        }
    line_of = _line_of_invoice(conn)
    return {
        row["id"]: {
            "payment_id": row["payment_id"],
            "purchase": ":".join(str(part) for part in line_of.get(row["purchase_invoice_id"], ("INVOICE", row["purchase_invoice_id"]))),
            "amount": row["amount"],
        }
        for row in conn.execute("SELECT * FROM supplier_payment_allocations ORDER BY id")
    }


def _legacy_owed(conn) -> dict:
    """What is owed per supplier before 016, from the purchase rows themselves: ACTIVE rows (every row before slice B)
    with total_paid above what their allocations hold."""
    owed: dict = {}
    for _, table, _item in PURCHASE_TABLES:
        column = "material_purchase_id" if table == "material_purchases" else "product_purchase_id"
        for row in conn.execute(
            f"SELECT p.supplier_id, p.total_paid - (SELECT COALESCE(SUM(a.amount), 0) FROM supplier_payment_allocations AS a "
            f"WHERE a.{column} = p.id) AS owed FROM {table} AS p WHERE p.status = 'ACTIVE'"
        ):
            if row["owed"] > 0:
                key = _supplier_key(row["supplier_id"])
                owed[key] = owed.get(key, 0) + row["owed"]
    return owed


def _legacy_summary(conn) -> dict:
    """The all-time purchases summary before 016 (the purchase tables hold the invoice fields themselves): ACTIVE rows
    only, as the summary counts them (section 23; every row is ACTIVE before a cancel exists)."""
    result = {}
    for prefix, table in (("material", "material_purchases"), ("product", "product_purchases")):
        columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        active = "WHERE status = 'ACTIVE'" if "status" in columns else ""
        row = conn.execute(f"SELECT COALESCE(SUM(total_paid), 0), COUNT(*) FROM {table} {active}").fetchone()
        result[f"{prefix}_purchases_total"], result[f"{prefix}_purchases_count"] = row[0], row[1]
    result["supplier_payments_total"], result["supplier_payments_count"] = conn.execute(
        "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM supplier_payments"
    ).fetchone()
    return result


def _payables(conn, tables) -> dict | None:
    """The payables figures, when the database has supplier payments (None before migration 015): what is owed in all and
    per supplier, the payment count, the purchases with a total, and the purchases a later cancel cannot use."""
    if "supplier_payments" not in tables:
        return None
    invoiced = "purchase_invoices" in tables
    with_total = sum(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE total_paid > 0").fetchone()[0] for _, table, _i in PURCHASE_TABLES)
    if invoiced:
        by_supplier = {_supplier_key(s["supplier_id"]): s["outstanding"] for s in get_payables(conn)["suppliers"]}
        outstanding = payables_outstanding(conn)
    else:
        by_supplier = _legacy_owed(conn)
        outstanding = sum(by_supplier.values())
    stock_only = "JOIN materials AS m ON m.id = p.material_id WHERE m.type = 'STOCK' AND"
    return {
        "outstanding": outstanding,
        "by_supplier": sorted(by_supplier.items()),  # a list, so a supplier that appears or goes is a difference
        "payments": conn.execute("SELECT COUNT(*) FROM supplier_payments").fetchone()[0],
        "purchases_with_total": with_total,
        "without_movement_link": conn.execute(f"SELECT COUNT(*) FROM material_purchases AS p {stock_only} p.stock_movement_id IS NULL").fetchone()[0]
        + conn.execute("SELECT COUNT(*) FROM product_purchases WHERE stock_movement_id IS NULL").fetchone()[0],
        "without_cost_snapshot": sum(
            conn.execute(f"SELECT COUNT(*) FROM {table} WHERE item_cost_after IS NULL").fetchone()[0] for _, table, _i in PURCHASE_TABLES
        ),
    }


def collect(path) -> dict:
    conn = open_readonly(path)
    try:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        counts = {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in sorted(tables) if name not in EXCLUDED_TABLES}
        settlements = list_settlements(conn)
        invoiced = "purchase_invoices" in tables
        has_payments = "supplier_payments" in tables
        if not has_payments:
            summary = None
        elif invoiced:
            all_time = get_purchases_summary(conn)
            summary = {k: all_time[k] for k in (
                "material_purchases_total", "material_purchases_count", "product_purchases_total", "product_purchases_count",
                "supplier_payments_total", "supplier_payments_count",
            )}
        else:
            summary = _legacy_summary(conn)
        return {
            "migrations": sorted(row[0] for row in conn.execute("SELECT filename FROM schema_migrations")),
            "counts": counts,
            "counters": {row["name"]: row["value"] for row in conn.execute("SELECT name, value FROM counters")},
            "profit_and_loss": get_profit_and_loss(conn),
            "materials": {row["id"]: row for row in list_materials(conn, active_only=False)},
            "products": {row["id"]: row for row in list_products(conn, active_only=False)},
            "orders": {row["id"]: row for row in list_orders(conn, include_voided=True)},
            "purchases": _purchases(conn, invoiced),
            "payments": {row["id"]: dict(row) for row in conn.execute("SELECT * FROM supplier_payments ORDER BY id")} if has_payments else None,
            "allocations": _allocations(conn, invoiced) if has_payments else None,
            "purchases_summary": summary,
            "invoices": (
                {"count": counts["purchase_invoices"], "lines": counts["material_purchases"] + counts["product_purchases"]}
                if invoiced else None
            ),
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


def _invoice_checks(before: dict, after: dict, failures: list[str], info: list[str]) -> None:
    """Migration 016: every purchase row became one invoice with one line."""
    invoices = after.get("invoices")
    if invoices is None or before.get("invoices") is not None:
        return
    rows = len(before.get("purchases", {}))
    if invoices["count"] != rows:
        failures.append(f"purchase invoices: {invoices['count']} invoices for {rows} purchases (one each)")
    if invoices["lines"] != rows:
        failures.append(f"purchase invoices: {invoices['lines']} lines for {rows} purchases")
    for key, row in (after.get("allocations") or {}).items():
        if str(row["purchase"]).startswith("INVOICE:"):
            failures.append(f"allocations.{key}: pays an invoice that does not have exactly one line ({row['purchase']})")
    info.append(f"purchase invoices created: {invoices['count']} (one per purchase)")


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
    _differences("counters", before.get("counters", {}), after.get("counters", {}), failures)
    _differences("profit and loss", before["profit_and_loss"], after["profit_and_loss"], failures)
    _differences("settlements", before["settlements"], after["settlements"], failures)
    if before.get("purchases_summary") is not None and after.get("purchases_summary") is not None:
        _differences("purchases summary", before["purchases_summary"], after["purchases_summary"], failures)
    for kind in ("materials", "products", "orders", "purchases", "payments", "allocations"):
        if kind in ("payments", "allocations") and before.get(kind) is None:
            continue  # the payment tables are new (migration 015): the backfill checks cover them
        rows_before, rows_after = before.get(kind) or {}, after.get(kind) or {}
        for item_id in sorted(set(rows_before) - set(rows_after), key=str):
            failures.append(f"{kind} id {item_id} disappeared")
        for item_id in sorted(set(rows_after) - set(rows_before), key=str):
            failures.append(f"{kind} id {item_id} appeared")
        if kind == "purchases":
            # a purchase column the after-database no longer has would otherwise not be compared at all
            for item_id in sorted(rows_before.keys() & rows_after.keys(), key=str):
                for column in sorted(set(rows_before[item_id]) - set(rows_after[item_id])):
                    failures.append(f"purchases.{item_id}.{column}: the column is gone")
        _differences(kind, rows_before, rows_after, failures)
    _payables_checks(before, after, failures, info)
    _invoice_checks(before, after, failures, info)
    return failures, info
