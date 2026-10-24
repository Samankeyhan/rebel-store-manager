"""The integrity checks. Each takes (conn, schema_number) with a read-only connection and returns a CheckResult.
Every formula is a db/ function (costing, orders, settlements, payment_methods, jalali, distributions, name_keys,
supplier_payments); nothing is
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
from db.orders import REVENUE_ELIGIBLE_STATUSES, get_order, list_orders
from db.payment_methods import compute_expected_settlement_date, compute_fee, get_payment_method
from db.purchases import list_material_purchases, list_product_purchases
from db.reports import get_profit_and_loss, get_purchases_summary
from db.settlements import get_settlement
from db.supplier_payments import get_payables
from db.timeutil import local_day
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

    legacy_unpaid_date: list[int] = []
    orders = list_orders(conn, include_voided=True)
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
                if method is None:
                    legacy_unpaid_date.append(order_id)  # created before migration 008 added paid_date; never backfilled
                else:
                    result.fails.append(Row("orders", order_id, "paid_date", None, "a date", note=f"status {order['status']}, method {method['id']}"))
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
    if legacy_unpaid_date:
        result.infos.append(
            f"orders ids={sorted(legacy_unpaid_date)}: PAID/COMPLETED with no payment method and no paid_date (legacy, created "
            f"before migration 008); a new id in this list after go-live must be reported"
        )
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


def check_service_waste(conn: sqlite3.Connection, schema: int) -> CheckResult:
    result = CheckResult("d4", "Service waste")
    services = conn.execute("SELECT id, current_stock FROM materials WHERE type = 'SERVICE' ORDER BY id").fetchall()
    for service in services:
        if service["current_stock"] not in (None, 0):
            result.fails.append(Row("materials", service["id"], "current_stock", service["current_stock"], "NULL or 0",
                                    note="a SERVICE holds no stock"))
    count = 0
    for row in conn.execute(
        "SELECT sm.id, sm.reason, sm.quantity_change, sm.unit_cost_at_time FROM stock_movements sm "
        "JOIN materials m ON m.id = sm.item_id WHERE sm.item_type = 'MATERIAL' AND m.type = 'SERVICE' ORDER BY sm.id"
    ):
        count += 1
        if row["reason"] != "WASTE":
            result.fails.append(Row("stock_movements", row["id"], "reason", row["reason"], "WASTE",
                                    note="WASTE is the only movement a SERVICE can have"))
        elif row["quantity_change"] >= 0:
            result.fails.append(Row("stock_movements", row["id"], "quantity_change", row["quantity_change"], "< 0"))
        elif row["unit_cost_at_time"] is None or row["unit_cost_at_time"] < 1:
            result.fails.append(Row("stock_movements", row["id"], "unit_cost_at_time", row["unit_cost_at_time"], ">= 1",
                                    note="a service waste is valued at its price per unit"))
    result.summary = f"{len(services)} services and {count} service movements checked"
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


# ------------------------------------------------------------------ i. voided orders


def check_voided_orders(conn: sqlite3.Connection, schema: int) -> CheckResult:
    """Section 20: a VOIDED order has its reason and moment, was committed, is in no settlement, and its stock
    came back (its movements net to zero per item); a correction points at a voided order; and no voided
    order is counted: the all-time P&L order count and revenue are those of the PENDING / PAID / COMPLETED
    orders `list_orders` returns."""
    result = CheckResult("i", "Voided orders and corrections")
    every_order = list_orders(conn, include_voided=True)
    by_id = {order["id"]: order for order in every_order}
    voided = [order for order in every_order if order["status"] == "VOIDED"]
    for order in voided:
        if not (order["void_reason"] or "").strip():
            result.fails.append(Row("orders", order["id"], "void_reason", order["void_reason"], "a reason"))
        if order["voided_at"] is None:
            result.fails.append(Row("orders", order["id"], "voided_at", None, "a moment"))
        if order["settlement_id"] is not None:
            result.fails.append(Row("orders", order["id"], "settlement_id", order["settlement_id"], None,
                                    note="a voided order is in no settlement"))
        if order["stock_committed"] != 1:
            result.fails.append(Row("orders", order["id"], "stock_committed", order["stock_committed"], 1))
        net = defaultdict(Fraction)
        moved_abs = defaultdict(Fraction)
        for row in conn.execute(
            "SELECT item_type, item_id, quantity_change FROM stock_movements WHERE reference_order_id = ?",
            (order["id"],),
        ):
            net[(row["item_type"], row["item_id"])] += _exact(row["quantity_change"])
            moved_abs[(row["item_type"], row["item_id"])] += abs(_exact(row["quantity_change"]))
        for (item_type, item_id), total in sorted(net.items()):
            tolerance = Fraction(0) if item_type == "PRODUCT" else stock_tolerance(0, moved_abs[(item_type, item_id)])
            if abs(total) > tolerance:
                result.fails.append(Row("stock_movements", f"order {order['id']}", f"{item_type.lower()} {item_id}",
                                        total, 0, total, "a voided order's movements must net to zero"))
    for order in every_order:
        replaced = order["replaces_order_id"]
        if replaced is not None and by_id.get(replaced, {}).get("status") != "VOIDED":
            result.fails.append(Row("orders", order["id"], "replaces_order_id", replaced, "a VOIDED order"))
    eligible = [order for order in every_order if order["status"] in REVENUE_ELIGIBLE_STATUSES]
    pnl = get_profit_and_loss(conn)
    if pnl["order_count"] != len(eligible):
        result.fails.append(Row("profit_and_loss", "all time", "order_count", pnl["order_count"], len(eligible),
                                pnl["order_count"] - len(eligible), "PENDING / PAID / COMPLETED orders"))
    revenue = sum(order["customer_total"] for order in eligible)
    if pnl["total_revenue"] != revenue:
        result.fails.append(_money_row("profit_and_loss", "all time", "total_revenue", pnl["total_revenue"], revenue,
                                       "sum of customer_total over PENDING / PAID / COMPLETED orders"))
    corrections = sum(1 for order in every_order if order["replaces_order_id"] is not None)
    result.summary = f"{len(voided)} voided orders, {corrections} corrections checked"
    return result


# ------------------------------------------------------------------ j. supplier payables


def check_supplier_payables(conn: sqlite3.Connection, schema: int) -> CheckResult:
    """Section 21: every payment is wholly allocated; every allocation pays an ACTIVE purchase of the payment's own
    supplier, on or after its day; no purchase is paid more than its total; per supplier, `get_payables` owes exactly
    Σ (total − paid) over its ACTIVE purchases as the purchase lists give them; the all-time purchases summary's
    payments equal the stored payments."""
    result = CheckResult("j", "Supplier payables")
    payments = conn.execute("SELECT id, supplier_id, payment_date, amount FROM supplier_payments ORDER BY id").fetchall()
    allocated = defaultdict(int)
    for row in conn.execute("SELECT payment_id, amount FROM supplier_payment_allocations"):
        allocated[row["payment_id"]] += row["amount"]
    for payment in payments:
        if payment["amount"] <= 0:
            result.fails.append(Row("supplier_payments", payment["id"], "amount", payment["amount"], "> 0"))
        if allocated[payment["id"]] != payment["amount"]:
            result.fails.append(_money_row("supplier_payments", payment["id"], "amount", payment["amount"],
                                           allocated[payment["id"]], "sum of its allocations"))
    by_id = {payment["id"]: payment for payment in payments}

    purchases = {("MATERIAL", p["id"]): p for p in list_material_purchases(conn)}
    purchases.update({("PRODUCT", p["id"]): p for p in list_product_purchases(conn)})
    count = 0
    for kind, column in (("MATERIAL", "material_purchase_id"), ("PRODUCT", "product_purchase_id")):
        for row in conn.execute(
            f"SELECT id, payment_id, {column} AS purchase_id, amount FROM supplier_payment_allocations "
            f"WHERE {column} IS NOT NULL ORDER BY id"
        ):
            count += 1
            purchase, payment = purchases.get((kind, row["purchase_id"])), by_id.get(row["payment_id"])
            if purchase is None or payment is None:
                result.fails.append(Row("supplier_payment_allocations", row["id"], "purchase / payment",
                                        f"{kind} {row['purchase_id']} / {row['payment_id']}", "existing rows"))
                continue
            if purchase["status"] != "ACTIVE":
                result.fails.append(Row("supplier_payment_allocations", row["id"], "purchase status", purchase["status"],
                                        "ACTIVE", note=f"{kind.lower()} purchase {row['purchase_id']}"))
            if payment["supplier_id"] != purchase["supplier_id"]:
                result.fails.append(Row("supplier_payment_allocations", row["id"], "supplier_id", payment["supplier_id"],
                                        purchase["supplier_id"], note=f"payment {payment['id']} vs {kind.lower()} purchase "
                                                                      f"{row['purchase_id']}"))
            payment_day, purchase_day = local_day(payment["payment_date"], conn), local_day(purchase["purchase_date"], conn)
            if payment_day < purchase_day:
                result.fails.append(Row("supplier_payments", payment["id"], "payment_date", payment_day.isoformat(),
                                        f">= {purchase_day.isoformat()}", note=f"pays {kind.lower()} purchase {row['purchase_id']}"))

    owed = defaultdict(int)
    for (kind, purchase_id), purchase in sorted(purchases.items()):
        if purchase["paid"] > purchase["total_paid"]:
            result.fails.append(_money_row(f"{kind.lower()}_purchases", purchase_id, "paid", purchase["paid"],
                                           purchase["total_paid"], "allocations above the invoice total"))
        if purchase["status"] == "ACTIVE" and purchase["total_paid"] > purchase["paid"]:
            owed[purchase["supplier_id"]] += purchase["total_paid"] - purchase["paid"]
    payables = {row["supplier_id"]: row["outstanding"] for row in get_payables(conn)["suppliers"]}
    for supplier_id in sorted(set(owed) | set(payables), key=lambda s: (s is None, s or 0)):
        if payables.get(supplier_id, 0) != owed[supplier_id]:
            result.fails.append(_money_row("suppliers", supplier_id, "outstanding", payables.get(supplier_id, 0),
                                           owed[supplier_id], "sum of total - paid over its ACTIVE purchases"))
    summary = get_purchases_summary(conn)
    stored = sum(payment["amount"] for payment in payments)
    if summary["supplier_payments_total"] != stored:
        result.fails.append(_money_row("purchases_summary", "all time", "supplier_payments_total",
                                       summary["supplier_payments_total"], stored, "sum of supplier_payments.amount"))
    if summary["payables_outstanding"] != sum(owed.values()):
        result.fails.append(_money_row("purchases_summary", "now", "payables_outstanding", summary["payables_outstanding"],
                                       sum(owed.values()), "sum over suppliers"))
    result.summary = f"{len(payments)} payments, {count} allocations, {len(payables)} suppliers owed"
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
    Check("d4", "Service waste", 3, check_service_waste, "stock movements are complete from migration 003"),
    Check("e", "Unit costs vs purchases and production batches", 9, check_costs, "money is stored in Rial from migration 009"),
    Check("f", "Invoice numbers", 3, check_invoice_numbers, "invoice counters exist from migration 003"),
    Check("g", "Partner distributions", 9, check_distributions, "money is stored in Rial from migration 009"),
    Check("h", "Name collisions", 13, check_name_collisions, "name_key exists from migration 013"),
    Check("i", "Voided orders and corrections", 14, check_voided_orders, "VOIDED exists from migration 014"),
    Check("j", "Supplier payables", 15, check_supplier_payables, "supplier payments exist from migration 015"),
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
