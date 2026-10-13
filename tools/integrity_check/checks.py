"""The integrity checks. Each takes (conn, schema_number) with a read-only connection and returns a CheckResult.
Every formula is a db/ function (costing, orders, settlements, payment_methods, jalali, distributions, name_keys); nothing is
re-implemented here: a check only compares what is stored with what db/ computes, or sums stored rows.
Money is exact integer Rial. Quantities are REAL: they are read as the decimal they were entered as (`exact_quantity`) and
compared with an explicit tolerance (`stock_tolerance`)."""

import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from typing import Callable

from db import jalali
from db.costing import exact_quantity, per_unit_cost, recipe_batch_total
from db.distributions import compute_share_amounts, get_profit_distribution
from db.name_keys import find_name_collisions
from db.orders import get_order, list_orders
from db.payment_methods import compute_expected_settlement_date, compute_fee, get_payment_method
from db.settlements import get_settlement
from tools.integrity_check.report import CheckResult, Row

PAID_STATUSES = ("PAID", "COMPLETED")
EXAMPLE_LIMIT = 10


def stock_tolerance(stored, movements_abs) -> Fraction:
    """max(1e-6, 1e-9 x the larger of |stock| and the sum of |movements|). SQLite adds REAL stock in binary floating point
    (about 1e-16 relative per addition), so 1e-9 relative is millions of times above the drift of any real history, and
    1e-6 absolute is far below the smallest meaningful step (0.001 of a unit)."""
    scale = max(abs(Fraction(stored)), abs(Fraction(movements_abs)))
    return max(Fraction(1, 10**6), scale / 10**9)


def _exact(value) -> Fraction:
    return exact_quantity(value)


def _money_row(table, row_id, field, stored, expected, note="") -> Row:
    return Row(table, row_id, field, stored, expected, stored - expected, note)


# ------------------------------------------------------------------ a. database health


def check_database_health(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("a", "Database health")
    messages = [row[0] for row in conn.execute("PRAGMA integrity_check")]
    if messages != ["ok"]:
        for message in messages[:50]:
            result.fails.append(Row("database", "-", "integrity_check", message, "ok"))
    violations = list(conn.execute("PRAGMA foreign_key_check"))
    for row in violations:
        result.fails.append(
            Row(row["table"], row["rowid"], f"foreign key -> {row['parent']}", "no such row", "an existing row")
        )
    result.summary = f"integrity_check {'ok' if messages == ['ok'] else 'FAILED'}; {len(violations)} foreign-key violations"
    return result


# ------------------------------------------------------------------ b. settlements


def check_settlements(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("b", "Settlements")
    ids = [row[0] for row in conn.execute("SELECT id FROM settlements ORDER BY id")]
    for settlement_id in ids:
        settlement = get_settlement(conn, settlement_id)
        orders = settlement["orders"]
        expected = sum(order["expected_amount"] for order in orders)
        if settlement["expected_amount"] != expected:
            result.fails.append(
                _money_row("settlements", settlement_id, "expected_amount", settlement["expected_amount"], expected,
                           f"sum of its {len(orders)} orders' customer_total - transaction_fee")
            )
        if not orders:
            result.fails.append(Row("settlements", settlement_id, "order_count", 0, ">= 1"))
        if settlement["amount_received"] < 0:
            result.fails.append(Row("settlements", settlement_id, "amount_received", settlement["amount_received"], ">= 0"))
        for order in conn.execute(
            "SELECT id, payment_method_id, paid_date, paid_jalali_year, paid_jalali_month FROM orders "
            "WHERE settlement_id = ? ORDER BY id",
            (settlement_id,),
        ):
            if order["payment_method_id"] != settlement["payment_method_id"]:
                result.fails.append(Row("orders", order["id"], "payment_method_id", order["payment_method_id"],
                                        settlement["payment_method_id"], note=f"in settlement {settlement_id}"))
            if order["paid_date"] is None or order["paid_date"] > settlement["settled_date"]:
                result.fails.append(Row("orders", order["id"], "paid_date", order["paid_date"],
                                        f"<= {settlement['settled_date']}", note=f"in settlement {settlement_id}"))
            if settlement["settlement_rule"] == "DAY_OF_NEXT_MONTH":
                stored = (order["paid_jalali_year"], order["paid_jalali_month"])
                wanted = (settlement["jalali_year"], settlement["jalali_month"])
                if stored != wanted:
                    result.fails.append(Row("orders", order["id"], "paid_jalali_year/month", list(stored), list(wanted),
                                            note=f"in monthly settlement {settlement_id}"))
    result.summary = f"{len(ids)} settlements checked"
    return result


# ------------------------------------------------------------------ c. orders


def check_orders(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("c", "Orders")
    methods: dict[int, dict] = {}

    def method_of(method_id):
        if method_id not in methods:
            methods[method_id] = get_payment_method(conn, method_id)
        return methods[method_id]

    orders = list_orders(conn)
    for order in orders:
        order_id = order["id"]
        detail = get_order(conn, order_id)
        if detail["customer_total"] != order["customer_total"]:
            result.fails.append(_money_row("orders", order_id, "customer_total", detail["customer_total"],
                                           order["customer_total"], "get_order vs list_orders"))
        customer_total = order["customer_total"]

        for item in detail["items"]:
            if item["quantity"] <= 0 or item["list_price"] % item["quantity"] != 0:
                result.fails.append(Row("order_items", item["id"], "list_price", item["list_price"],
                                        f"a multiple of quantity {item['quantity']}", note=f"order {order_id}"))
            if not 0 <= item["discount_amount"] <= item["list_price"]:
                result.fails.append(Row("order_items", item["id"], "discount_amount", item["discount_amount"],
                                        f"0 .. {item['list_price']}", note=f"order {order_id}"))

        fee = order["transaction_fee"]
        if fee < 0:
            result.fails.append(Row("orders", order_id, "transaction_fee", fee, ">= 0"))
        elif fee > customer_total:
            result.warns.append(Row("orders", order_id, "transaction_fee", fee, f"<= customer_total {customer_total}",
                                    fee - customer_total, "fee larger than the order total"))

        method = method_of(order["payment_method_id"]) if order["payment_method_id"] is not None else None
        if method is not None and fee >= 0:
            rule_fee = compute_fee(customer_total, method)
            if fee != rule_fee:
                result.warns.append(Row("orders", order_id, "transaction_fee", fee, rule_fee, fee - rule_fee,
                                        f"differs from method {method['id']}'s current rule: a hand-entered fee or a "
                                        f"rule edited later"))

        if order["status"] in PAID_STATUSES:
            if order["paid_date"] is None:
                result.fails.append(Row("orders", order_id, "paid_date", None, "a date", note=f"status {order['status']}"))
                continue
            try:
                paid_day = date.fromisoformat(order["paid_date"])
            except ValueError:
                result.fails.append(Row("orders", order_id, "paid_date", order["paid_date"], "YYYY-MM-DD"))
                continue
            year, month, _ = jalali.to_jalali(paid_day)
            if (order["paid_jalali_year"], order["paid_jalali_month"]) != (year, month):
                result.fails.append(Row("orders", order_id, "paid_jalali_year/month",
                                        [order["paid_jalali_year"], order["paid_jalali_month"]], [year, month],
                                        note=f"paid_date {order['paid_date']}"))
            if method is not None and order["settlement_id"] is None:
                wanted = compute_expected_settlement_date(paid_day, method).isoformat()
                if order["expected_settlement_date"] != wanted:
                    result.fails.append(Row("orders", order_id, "expected_settlement_date",
                                            order["expected_settlement_date"], wanted,
                                            note=f"pending order, method {method['id']}'s rule"))
    result.summary = f"{len(orders)} orders checked"
    return result


# ------------------------------------------------------------------ d. stock


@dataclass
class _Item:
    kind: str  # PRODUCT | MATERIAL
    id: int
    table: str
    stock: object


def _stock_items(conn) -> list[_Item]:
    items = [_Item("PRODUCT", r["id"], "products", r["current_stock"])
             for r in conn.execute("SELECT id, current_stock FROM products ORDER BY id")]
    items += [_Item("MATERIAL", r["id"], "materials", r["current_stock"])
              for r in conn.execute("SELECT id, current_stock FROM materials WHERE type = 'STOCK' ORDER BY id")]
    return items


def _audit_opening(conn, table: str, item_id: int, schema: int):
    """The stock an item was created with, from its audit INSERT row (schema >= 012), else None."""
    if schema < 12:
        return None
    row = conn.execute(
        "SELECT after_json FROM audit_log WHERE entity_type = ? AND entity_id = ? AND action = 'INSERT' "
        "ORDER BY id LIMIT 1",
        (table, str(item_id)),
    ).fetchone()
    if row is None or row["after_json"] is None:
        return None
    return json.loads(row["after_json"]).get("current_stock")


def check_stock_replay(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("d1", "Stock vs movement history")
    movements = defaultdict(list)
    for row in conn.execute("SELECT id, item_type, item_id, quantity_change FROM stock_movements ORDER BY id"):
        movements[(row["item_type"], row["item_id"])].append((row["id"], _exact(row["quantity_change"])))
    items = _stock_items(conn)
    for item in items:
        history = movements.get((item.kind, item.id), [])
        total = sum((q for _, q in history), Fraction(0))
        total_abs = sum((abs(q) for _, q in history), Fraction(0))
        stock = _exact(item.stock)
        opening = stock - total
        tolerance = Fraction(0) if item.kind == "PRODUCT" else stock_tolerance(stock, total_abs)
        audit_opening = _audit_opening(conn, item.table, item.id, schema) if item.kind == "MATERIAL" else None

        if item.kind == "PRODUCT":
            # A product can only get stock through a movement, so its history must add up to its stock exactly.
            if abs(opening) > tolerance:
                result.fails.append(Row(item.table, item.id, "current_stock", item.stock, total, stock - total,
                                        "sum of stock_movements; a product starts at 0"))
                continue
        elif audit_opening is not None:
            if abs(opening - _exact(audit_opening)) > tolerance:
                result.fails.append(Row(item.table, item.id, "current_stock", item.stock,
                                        _exact(audit_opening) + total, stock - (_exact(audit_opening) + total),
                                        f"created with {audit_opening} (audit log) plus its movements"))
                continue
        else:
            if opening < -tolerance:
                result.fails.append(Row(item.table, item.id, "implied_opening_balance", opening, ">= 0",
                                        note="current_stock minus the sum of stock_movements is negative"))
                continue
            if abs(opening) > tolerance:
                result.infos.append(
                    f"{item.table} id={item.id}: implied opening balance {float(opening):.12g} "
                    f"(stock {float(stock):.12g} - movements {float(total):.12g}); created with stock, not in the ledger"
                )

        running = opening
        for movement_id, quantity in history:
            running += quantity
            if running < -tolerance:
                result.fails.append(Row("stock_movements", movement_id, "running_balance", running, ">= 0",
                                        note=f"{item.table} id {item.id} went below zero in its history"))
                break
    result.summary = f"{len(items)} products and stock materials checked"
    return result


def check_stock_documents(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("d2", "Stock movements vs purchases and production batches")

    def compare(table, key, field, stored, expected, kind, note):
        tolerance = Fraction(0) if kind == "PRODUCT" else stock_tolerance(expected, abs(stored))
        if abs(stored - expected) > tolerance:
            result.fails.append(Row(table, key, field, stored, expected, stored - expected, note))

    count = 0
    for kind, table, name in (("MATERIAL", "material_purchases", "material_id"), ("PRODUCT", "product_purchases", "product_id")):
        bought = defaultdict(Fraction)
        for row in conn.execute(f"SELECT {name} AS item, quantity_bought FROM {table}"):
            bought[row["item"]] += _exact(row["quantity_bought"])
        moved = defaultdict(Fraction)
        for row in conn.execute("SELECT item_id, quantity_change FROM stock_movements WHERE item_type = ? AND reason = 'PURCHASE'", (kind,)):
            moved[row["item_id"]] += _exact(row["quantity_change"])
        for item in sorted(set(bought) | set(moved)):
            count += 1
            compare("stock_movements", item, "sum PURCHASE quantity", moved[item], bought[item], kind,
                    f"{kind.lower()} id {item}: movements vs {table}.quantity_bought")

    output = defaultdict(Fraction)
    for row in conn.execute(
        "SELECT reference_production_batch_id AS batch, quantity_change FROM stock_movements "
        "WHERE reason = 'PRODUCTION_OUTPUT' AND reference_production_batch_id IS NOT NULL"
    ):
        output[row["batch"]] += _exact(row["quantity_change"])
    consumed = defaultdict(Fraction)
    for row in conn.execute(
        "SELECT reference_production_batch_id AS batch, item_id, quantity_change FROM stock_movements "
        "WHERE reason = 'PRODUCTION_CONSUMPTION' AND item_type = 'MATERIAL' AND reference_production_batch_id IS NOT NULL"
    ):
        consumed[(row["batch"], row["item_id"])] -= _exact(row["quantity_change"])
    batches = conn.execute("SELECT id, quantity_produced FROM production_batches ORDER BY id").fetchall()
    for batch in batches:
        count += 1
        compare("production_batches", batch["id"], "quantity_produced vs PRODUCTION_OUTPUT movements",
                output[batch["id"]], _exact(batch["quantity_produced"]), "PRODUCT", "")
        for used in conn.execute(
            "SELECT pbm.material_id, pbm.quantity_used FROM production_batch_materials pbm "
            "JOIN materials m ON m.id = pbm.material_id WHERE pbm.production_batch_id = ? AND m.type = 'STOCK'",
            (batch["id"],),
        ):
            count += 1
            compare("production_batches", batch["id"], f"material {used['material_id']} consumed",
                    consumed[(batch["id"], used["material_id"])], _exact(used["quantity_used"]), "MATERIAL",
                    "PRODUCTION_CONSUMPTION movements vs production_batch_materials.quantity_used")
    result.summary = f"{count} comparisons"
    return result


def check_stock_orders(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("d3", "Stock movements per order (SALE / RETURN / PACKAGING)")
    result.skipped = ("not checked: what each order should move is the order-commit logic (made-to-order split, kits, "
                      "cancellations) and db/ has no read-only helper for it")
    return result


# ------------------------------------------------------------------ e. costs


def check_costs(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("e", "Unit costs vs purchases and production batches")
    count = 0
    for table in ("material_purchases", "product_purchases"):
        for row in conn.execute(f"SELECT id, total_paid, quantity_bought, unit_cost FROM {table} ORDER BY id"):
            count += 1
            expected = per_unit_cost(row["total_paid"], row["quantity_bought"])
            if row["unit_cost"] != expected:
                result.fails.append(_money_row(table, row["id"], "unit_cost", row["unit_cost"], expected,
                                               "total_paid / quantity_bought"))
    legacy = 0
    has_total = any(r["name"] == "total_cost" for r in conn.execute("PRAGMA table_info(production_batches)"))
    columns = "id, quantity_produced, unit_cost" + (", total_cost" if has_total else "")
    for batch in conn.execute(f"SELECT {columns} FROM production_batches ORDER BY id").fetchall():
        total = batch["total_cost"] if has_total else None
        if total is None:
            legacy += 1
            continue
        count += 1
        expected_unit = per_unit_cost(total, batch["quantity_produced"])
        if batch["unit_cost"] != expected_unit:
            result.fails.append(_money_row("production_batches", batch["id"], "unit_cost", batch["unit_cost"],
                                           expected_unit, "total_cost / quantity_produced"))
        lines = [(r["quantity_used"], "PER_BATCH", r["unit_cost_at_time"]) for r in conn.execute(
            "SELECT quantity_used, unit_cost_at_time FROM production_batch_materials WHERE production_batch_id = ?",
            (batch["id"],))]
        expected_total = recipe_batch_total(lines, 1)
        if total != expected_total:
            result.fails.append(_money_row("production_batches", batch["id"], "total_cost", total, expected_total,
                                           "sum of quantity_used x unit_cost_at_time of its materials"))
    if legacy:
        result.infos.append(f"{legacy} production batches were recorded before total_cost was stored; only their rows are skipped")
    result.summary = f"{count} purchases and batches checked"
    return result


# ------------------------------------------------------------------ f. invoice numbers


def _numbers(conn, table, prefix, result):
    pattern = re.compile(rf"^{prefix}-(\d{{6,}})$")
    found = defaultdict(list)
    for row in conn.execute(f"SELECT id, invoice_number FROM {table} WHERE invoice_number IS NOT NULL ORDER BY id"):
        number = row["invoice_number"]
        match = pattern.match(number)
        if match is None:
            result.fails.append(Row(table, row["id"], "invoice_number", number, f"{prefix}-nnnnnn"))
            continue
        found[int(match.group(1))].append((table, row["id"], number))
    return found


def check_invoice_numbers(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("f", "Invoice numbers")
    counters = {r["name"]: r["value"] for r in conn.execute("SELECT name, value FROM counters")}

    inv = _numbers(conn, "orders", "INV", result)
    pur = _numbers(conn, "material_purchases", "PUR", result)
    for number, rows in _numbers(conn, "product_purchases", "PUR", result).items():
        pur[number].extend(rows)

    for prefix, found in (("INV", inv), ("PUR", pur)):
        for number, rows in sorted(found.items()):
            if len(rows) > 1:
                for table, row_id, text in rows[1:]:
                    result.fails.append(Row(table, row_id, "invoice_number", text, "unique",
                                            note=f"also used by {rows[0][0]} id {rows[0][1]}"))
        highest = max(found, default=0)
        counter = counters.get(prefix)
        if counter is None:
            if highest:
                result.fails.append(Row("counters", prefix, "value", None, f">= {highest}"))
        elif counter < highest:
            result.fails.append(Row("counters", prefix, "value", counter, f">= {highest}", counter - highest,
                                    "the counter is behind the highest number in use"))
        gaps = [n for n in range(1, highest + 1) if n not in found]
        if gaps:
            shown = ", ".join(f"{prefix}-{n:06d}" for n in gaps[:EXAMPLE_LIMIT])
            result.infos.append(f"{len(gaps)} {prefix} numbers below the highest are unused (e.g. {shown})")
    result.summary = f"{sum(map(len, inv.values()))} order and {sum(map(len, pur.values()))} purchase numbers"
    return result


# ------------------------------------------------------------------ g. partner distributions


def check_distributions(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("g", "Partner distributions")
    rows = conn.execute("SELECT id, period_start, period_end FROM profit_distributions ORDER BY period_start, id").fetchall()
    for position, row in enumerate(rows):
        if row["period_start"] > row["period_end"]:
            result.fails.append(Row("profit_distributions", row["id"], "period", f"{row['period_start']}..{row['period_end']}", "start <= end"))
        for earlier in rows[:position]:
            if earlier["period_end"] >= row["period_start"] and row["period_end"] >= earlier["period_start"]:
                result.fails.append(Row("profit_distributions", row["id"], "period", f"{row['period_start']}..{row['period_end']}",
                                        f"no overlap with distribution {earlier['id']}"))
    for row in rows:
        distribution = get_profit_distribution(conn, row["id"])
        shares = distribution["shares"]
        paid = sum(share["amount"] for share in shares)
        if paid != distribution["total_amount_distributed"]:
            result.fails.append(_money_row("profit_distributions", row["id"], "total_amount_distributed",
                                           distribution["total_amount_distributed"], paid, "sum of its shares"))
        percent = sum((_exact(share["percentage_at_time"]) for share in shares), Fraction(0))
        if percent != 100:
            result.infos.append(
                f"profit_distributions id={row['id']}: percentages sum to {float(percent):.12g}, not exactly 100; "
                f"the leftover rule is not specified, so shares were not recomputed"
            )
            continue
        planned = compute_share_amounts(
            [{"id": s["partner_id"], "current_percentage": s["percentage_at_time"]} for s in shares],
            distribution["total_amount_distributed"],
        )
        by_partner = {p["partner_id"]: p["amount"] for p in planned}
        for share in shares:
            if share["amount"] != by_partner[share["partner_id"]]:
                result.fails.append(_money_row("distribution_shares", share["id"], "amount", share["amount"],
                                               by_partner[share["partner_id"]],
                                               f"distribution {row['id']}, partner {share['partner_id']}"))
    result.summary = f"{len(rows)} distributions checked"
    return result


# ------------------------------------------------------------------ h. name collisions


def check_name_collisions(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("h", "Name collisions")
    collisions = find_name_collisions(conn)
    for collision in collisions:
        result.warns.append(Row(collision["table"], collision["ids"], "name", collision["names"], "one row per name",
                                note=f"{collision['reason']}; these rows have no name_key yet"))
    result.summary = f"{len(collisions)} collision groups"
    return result


# ------------------------------------------------------------------ registry


@dataclass(frozen=True)
class Check:
    key: str
    name: str
    min_schema: int
    run: Callable[[sqlite3.Connection, int], CheckResult]
    why: str


CHECKS = [
    Check("a", "Database health", 0, check_database_health, ""),
    Check("b", "Settlements", 9, check_settlements, "money is stored in Rial from migration 009"),
    Check("c", "Orders", 10, check_orders, "the fee rule has fee_cap from migration 010"),
    Check("d1", "Stock vs movement history", 3, check_stock_replay, "stock movements are complete from migration 003"),
    Check("d2", "Stock movements vs purchases and production batches", 3, check_stock_documents, "stock movements are complete from migration 003"),
    Check("d3", "Stock movements per order (SALE / RETURN / PACKAGING)", 0, check_stock_orders, ""),
    Check("e", "Unit costs vs purchases and production batches", 9, check_costs, "money is stored in Rial from migration 009"),
    Check("f", "Invoice numbers", 3, check_invoice_numbers, "invoice counters exist from migration 003"),
    Check("g", "Partner distributions", 9, check_distributions, "money is stored in Rial from migration 009"),
    Check("h", "Name collisions", 13, check_name_collisions, "name_key exists from migration 013"),
]


def run_checks(conn: sqlite3.Connection, schema: int) -> list[CheckResult]:
    results = []
    for check in CHECKS:
        if schema < check.min_schema:
            result = CheckResult(check.key, check.name)
            result.skipped = f"needs migration {check.min_schema:03d} ({check.why}); the database is at {schema:03d}"
        else:
            try:
                result = check.run(conn, schema)
            except Exception as exc:  # a check that cannot run must not hide the others
                result = CheckResult(check.key, check.name)
                result.error = f"{type(exc).__name__}: {exc}"
        results.append(result)
    return results
