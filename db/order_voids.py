"""Voiding a sale entered by mistake (status VOIDED), docs/accounting-rules.md section 20. Not a customer return: `returns.process_return` stays for those.
`plan_void` (read-only) lists what a void would put back and every rule that refuses it; `void_order` applies it in one transaction. The order row and its lines stay; only status, `void_reason` and `voided_at` change.
Stock comes back by reversing the order's own SALE / PACKAGING / PRODUCTION_CONSUMPTION movements (RETURN movements, `reference_order_id` = the order). Each item's cost takes the returned stock at its frozen cost by weighted average (section 2, `costing.blend_unit_cost_exact`; materials treat 0 as "not entered"); a movement with no frozen cost (orders committed before section 20) comes back at the current cost, which then stays. Nothing is written for payment, fee or settlement: VOIDED is in no status list, so the order leaves every figure.
Refused (in this order): ORDER_ALREADY_VOIDED, ORDER_HAS_RETURN, ORDER_NOT_COMMITTED, ORDER_ALREADY_SETTLED, PERIOD_ALREADY_DISTRIBUTED (the order's local day is closed), STOCKTAKE_AFTER_SALE (a count recorded after the sale covered an affected item)."""

import sqlite3
from fractions import Fraction

from db import jalali
from db.audit import audited
from db.connection import transaction
from db.costing import blend_unit_cost_exact, exact_quantity
from db.errors import AppError, ConflictError, ErrorCode, NotFoundError, ValidationError
from db.names import stored_form
from db.orders import VOIDED, _fetch_order_items, get_order, replaced_by_order_id
from db.payment_methods import PAID_STATUSES
from db.period_lock import refuse_closed_day
from db.stocktake import NOTE_PREFIX as STOCKTAKE_NOTE_PREFIX
from db.timeutil import local_day, now_utc

VOIDABLE_STATUSES = ("PENDING", "PAID", "COMPLETED")
MAX_REASON_LENGTH = 500
VOID_NOTE_PREFIX = "ابطال سفارش"
_RETURNED_REASONS = ("SALE", "PACKAGING", "PRODUCTION_CONSUMPTION")


def _order_row(conn: sqlite3.Connection, order_id: int) -> sqlite3.Row:
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise NotFoundError(f"Order with id {order_id} does not exist")
    return order


def _movements(conn: sqlite3.Connection, order_id: int) -> list[sqlite3.Row]:
    placeholders = ", ".join("?" for _ in _RETURNED_REASONS)
    return conn.execute(
        f"""
        SELECT id, item_type, item_id, quantity_change, reason, unit_cost_at_time
        FROM stock_movements
        WHERE reference_order_id = ? AND reason IN ({placeholders})
        ORDER BY id
        """,
        (order_id, *_RETURNED_REASONS),
    ).fetchall()


# ----------------------------------------------------------------- the rules


def _refuse_status(conn: sqlite3.Connection, order: sqlite3.Row) -> None:
    status = order["status"]
    if status == VOIDED:
        raise ConflictError(
            f"Order #{order['id']} is already voided.",
            code=ErrorCode.ORDER_ALREADY_VOIDED,
            details={
                "order_id": order["id"],
                "voided_at": order["voided_at"],
                "replaced_by_order_id": replaced_by_order_id(conn, order["id"]),
            },
        )
    if status in ("CANCELLED", "REFUNDED"):
        raise ConflictError(
            f"Order #{order['id']} is {status}: a return was recorded, so it cannot be voided.",
            code=ErrorCode.ORDER_HAS_RETURN,
            details={"order_id": order["id"], "status": status},
        )
    if status not in VOIDABLE_STATUSES or not order["stock_committed"]:
        raise ConflictError(
            f"Order #{order['id']} is {status} and committed nothing; cancel it instead.",
            code=ErrorCode.ORDER_NOT_COMMITTED,
            details={"order_id": order["id"], "status": status},
        )


def _refuse_settled(order: sqlite3.Row) -> None:
    if order["settlement_id"] is not None:
        raise ConflictError(
            f"Order #{order['id']} is part of settlement #{order['settlement_id']}; it can no longer be voided.",
            code=ErrorCode.ORDER_ALREADY_SETTLED,
            details={"order_id": order["id"], "settlement_id": order["settlement_id"]},
        )


def _item_name(conn: sqlite3.Connection, item_type: str, item_id: int) -> str:
    table = "products" if item_type == "PRODUCT" else "materials"
    row = conn.execute(f"SELECT name FROM {table} WHERE id = ?", (item_id,)).fetchone()
    return row["name"] if row else ""


def _refuse_stocktake_after(conn: sqlite3.Connection, order: sqlite3.Row, movements: list[sqlite3.Row]) -> None:
    """A stocktake ADJUSTMENT recorded after the sale's last movement, on an item the sale moved, already
    took that item's stock as the sale left it: returning the stock now would count it twice. A stocktake
    movement is one the audit log labels `apply_stocktake`, or one carrying the stocktake note."""
    if not movements:
        return
    affected = {(m["item_type"], m["item_id"]) for m in movements}
    rows = conn.execute(
        """
        SELECT stock_movements.id, item_type, item_id, movement_date
        FROM stock_movements
        WHERE reason = 'ADJUSTMENT' AND stock_movements.id > ?
          AND (notes LIKE ? || '%' OR EXISTS (
                SELECT 1 FROM audit_log
                WHERE audit_log.entity_type = 'stock_movements'
                  AND audit_log.entity_id = CAST(stock_movements.id AS TEXT)
                  AND audit_log.action = 'INSERT'
                  AND audit_log.operation = 'apply_stocktake'))
        ORDER BY stock_movements.id
        """,
        (max(m["id"] for m in movements), STOCKTAKE_NOTE_PREFIX),
    ).fetchall()
    for row in rows:
        if (row["item_type"], row["item_id"]) in affected:
            raise ConflictError(
                f"Order #{order['id']}: a stocktake recorded after this sale counted "
                f"{row['item_type'].lower()} #{row['item_id']}; returning its stock would count it twice.",
                code=ErrorCode.STOCKTAKE_AFTER_SALE,
                details={
                    "order_id": order["id"],
                    "item_type": row["item_type"],
                    "item_id": row["item_id"],
                    "item_name": _item_name(conn, row["item_type"], row["item_id"]),
                    "stocktake_date": local_day(row["movement_date"], conn).isoformat(),
                },
            )


def _checks(conn: sqlite3.Connection, order: sqlite3.Row, movements: list[sqlite3.Row]):
    """The refusal rules, in the order they are reported."""
    return (
        lambda: _refuse_status(conn, order),
        lambda: _refuse_settled(order),
        lambda: refuse_closed_day(conn, local_day(order["order_date"], conn)),
        lambda: _refuse_stocktake_after(conn, order, movements),
    )


def refuse_void(conn: sqlite3.Connection, order: sqlite3.Row) -> None:
    """Raise the first rule that refuses voiding this order (none: it may be voided)."""
    movements = _movements(conn, order["id"])
    for check in _checks(conn, order, movements):
        check()


# ----------------------------------------------------------------- what comes back


def _frozen_product_costs(conn: sqlite3.Connection, order_id: int, sale_qty: dict[int, Fraction]) -> dict[int, int]:
    """For SALE movements committed before section 20 (no cost on the movement): the line's frozen
    unit_cost_at_time, when that is the product's own cost at commit. That holds for a product that is
    not made to order, and for a made-to-order product taken wholly from stock (the blend of section 13
    then equals the product cost). Any other product is absent (its stock comes back at today's cost)."""
    lines: dict[int, list[sqlite3.Row]] = {}
    for item in _fetch_order_items(conn, order_id):
        lines.setdefault(item["product_id"], []).append(item)
    found: dict[int, int] = {}
    for product_id, items in lines.items():
        made_to_order = conn.execute(
            "SELECT made_to_order FROM products WHERE id = ?", (product_id,)
        ).fetchone()["made_to_order"]
        costs = {item["unit_cost_at_time"] for item in items}
        whole_from_stock = sale_qty.get(product_id, Fraction(0)) == sum(item["quantity"] for item in items)
        if len(costs) == 1 and (not made_to_order or whole_from_stock):
            found[product_id] = costs.pop()
    return found


def _plan_items(conn: sqlite3.Connection, order_id: int, movements: list[sqlite3.Row]) -> tuple[list[dict], list[dict]]:
    """(products, materials) the void puts back, with each item's unit cost before and after."""
    sale_qty: dict[int, Fraction] = {}
    for m in movements:
        if m["reason"] == "SALE":
            sale_qty[m["item_id"]] = sale_qty.get(m["item_id"], Fraction(0)) - exact_quantity(m["quantity_change"])
    legacy_costs = _frozen_product_costs(conn, order_id, sale_qty)

    groups: dict[tuple, dict] = {}
    for m in movements:
        key = (m["item_type"], m["item_id"])
        group = groups.setdefault(key, {"movements": [], "reasons": {}})
        quantity = -exact_quantity(m["quantity_change"])
        frozen = m["unit_cost_at_time"]
        if frozen is None and m["item_type"] == "PRODUCT":
            frozen = legacy_costs.get(m["item_id"])
        group["movements"].append({"id": m["id"], "quantity": abs(m["quantity_change"]), "frozen": frozen})
        group["reasons"][m["reason"]] = group["reasons"].get(m["reason"], Fraction(0)) + quantity

    products, materials = [], []
    for (item_type, item_id), group in groups.items():
        table = "products" if item_type == "PRODUCT" else "materials"
        columns = "name, current_stock, unit_cost" + (", unit" if item_type == "MATERIAL" else "")
        item = conn.execute(f"SELECT {columns} FROM {table} WHERE id = ?", (item_id,)).fetchone()
        cost_before = item["unit_cost"]
        is_material = item_type == "MATERIAL"
        known = [(exact_quantity(m["quantity"]), m["frozen"]) for m in group["movements"] if m["frozen"] is not None]
        unknown = sum((exact_quantity(m["quantity"]) for m in group["movements"] if m["frozen"] is None), Fraction(0))
        cost_after = cost_before
        if known:
            qty = sum((q for q, _ in known), Fraction(0))
            value = sum((q * c for q, c in known), Fraction(0))
            cost_known = cost_before is not None and not (is_material and cost_before == 0)
            if unknown and cost_known:
                qty += unknown  # comes back at today's cost
                value += unknown * cost_before
            cost_after = blend_unit_cost_exact(item["current_stock"], cost_before, qty, value, zero_is_unknown=is_material)
        total = sum((q for q in group["reasons"].values()), Fraction(0))
        row = {
            "item_id": item_id,
            "name": item["name"],
            "quantity": int(total) if item_type == "PRODUCT" else float(total),
            "unit_cost_before": cost_before,
            "unit_cost_after": cost_after,
            "frozen_cost_known": not unknown,
            "movements": group["movements"],
        }
        if is_material:
            row["unit"] = item["unit"]
            row["reasons"] = {reason: float(q) for reason, q in group["reasons"].items()}
            materials.append(row)
        else:
            products.append(row)
    return products, materials


def _blocker(check) -> dict | None:
    try:
        check()
    except AppError as exc:
        return {"code": str(exc.code), "details": exc.details}
    return None


def plan_void(conn: sqlite3.Connection, order_id: int) -> dict:
    """Read-only: what voiding the order would do, and every rule that refuses it now (`blockers`, empty
    when it may be voided). Products and materials list the quantity put back and the unit cost before and
    after; the money figures are the ones that leave the reports."""
    order = _order_row(conn, order_id)
    movements = _movements(conn, order_id)
    blockers = [b for b in (_blocker(check) for check in _checks(conn, order, movements)) if b is not None]
    products, materials = _plan_items(conn, order_id, movements)
    detail = get_order(conn, order_id)
    day = local_day(order["order_date"], conn)
    jy, jm, _ = jalali.to_jalali(day)
    return {
        "order_id": order_id,
        "invoice_number": order["invoice_number"],
        "status": order["status"],
        "blockers": blockers,
        "products": [_public(p) for p in products],
        "materials": [_public(m) for m in materials],
        "customer_total": detail["customer_total"],
        "profit": detail["profit"],
        "transaction_fee": order["transaction_fee"],
        "pending_settlement": (
            order["payment_method_id"] is not None
            and order["status"] in PAID_STATUSES
            and order["settlement_id"] is None
        ),
        "order_day": day.isoformat(),
        "order_jalali_year": jy,
        "order_jalali_month": jm,
    }


def _public(row: dict) -> dict:
    return {key: value for key, value in row.items() if key != "movements"}


# ----------------------------------------------------------------- the write


def clean_reason(reason) -> str:
    """The reason as stored (names.stored_form); blank is VOID_REASON_REQUIRED."""
    text = stored_form(reason) if isinstance(reason, str) else ""
    if not text:
        raise ValidationError(
            "A reason is required to void an order", field="reason", code=ErrorCode.VOID_REASON_REQUIRED
        )
    if len(text) > MAX_REASON_LENGTH:
        raise ValidationError(f"reason must be at most {MAX_REASON_LENGTH} characters", field="reason")
    return text


def _return_stock(conn: sqlite3.Connection, order: sqlite3.Row, items: list[dict], item_type: str, note: str) -> None:
    table = "products" if item_type == "PRODUCT" else "materials"
    for item in items:
        for movement in item["movements"]:
            conn.execute(
                f"UPDATE {table} SET current_stock = current_stock + ? WHERE id = ?",
                (movement["quantity"], item["item_id"]),
            )
            conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason, reference_order_id, notes, unit_cost_at_time)
                VALUES (?, ?, ?, 'RETURN', ?, ?, ?)
                """,
                (item_type, item["item_id"], movement["quantity"], order["id"], note, movement["frozen"]),
            )
        if item["unit_cost_after"] != item["unit_cost_before"]:
            conn.execute(f"UPDATE {table} SET unit_cost = ? WHERE id = ?", (item["unit_cost_after"], item["item_id"]))


@audited()
def void_order(conn: sqlite3.Connection, order_id: int, reason: str) -> None:
    """Void a PENDING / PAID / COMPLETED order entered by mistake: its stock comes back (at the frozen cost,
    weighted average), it leaves every report, P&L, settlement and partner figure, and it keeps its row,
    lines, invoice number and frozen figures. Refusals: see the module docstring."""
    text = clean_reason(reason)
    with transaction(conn):
        order = _order_row(conn, order_id)
        refuse_void(conn, order)
        products, materials = _plan_items(conn, order_id, _movements(conn, order_id))
        note = f"{VOID_NOTE_PREFIX} {order['invoice_number'] or '#' + str(order_id)} — {text}"
        _return_stock(conn, order, products, "PRODUCT", note)
        _return_stock(conn, order, materials, "MATERIAL", note)
        conn.execute(
            "UPDATE orders SET status = ?, void_reason = ?, voided_at = ? WHERE id = ?",
            (VOIDED, text, now_utc(), order_id),
        )
