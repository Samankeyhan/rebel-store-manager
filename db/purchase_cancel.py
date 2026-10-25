"""Cancelling and correcting a purchase invoice entered by mistake, docs/accounting-rules.md section 23. Always the whole
invoice; the invoice, its lines, its PUR number and every figure stay, only its status, `cancel_reason` and
`cancelled_at` change (the pattern of db/order_voids.py).
`plan_cancel_purchase` (read-only) lists what a cancel would put back and every rule that refuses it; `cancel_purchase`
applies it in one transaction: each stock material or product line takes its quantity back out with a −qty PURCHASE
movement (`cancel_movement_id`, note «ابطال خرید PUR-… — reason»), a service line writes no movement, and every line's
item gets back exactly the unit cost it had before the purchase (`item_cost_before`; NULL for a product that had none).
No cost is recomputed: the rule that makes this exact is that the line must still be its item's latest cost event.
Refused (in this order): PURCHASE_ALREADY_CANCELLED, PURCHASE_HAS_PAYMENTS (payments without `with_payments`, or a
payment that also pays another purchase), PERIOD_ALREADY_DISTRIBUTED (the invoice's local day is closed),
PURCHASE_STOCK_USED, STOCKTAKE_AFTER_PURCHASE, PURCHASE_COST_CHANGED_SINCE (a later stock-in on the item other than a
cancelled purchase's own, a later purchase of the same service on an ACTIVE invoice, or a cost changed without a
movement), PURCHASE_COST_HISTORY_UNKNOWN (no cost snapshot, or a stock line with no movement link). With
`with_payments`, the payments allocated only to this invoice are deleted in the same operation.
`correct_purchase` cancels the invoice and records the right one with `record_purchase` in ONE audit operation and
transaction, then sets the new invoice's `replaces_invoice_id`. The old invoice's allocations move to the new one (their
payments are unchanged, the one made with the purchase follows its day and every payment follows a new supplier, a shared
payment refuses a supplier change); the new total must be at least what was paid (PURCHASE_CORRECTION_BELOW_PAID) and
the payment chosen on the form is on the remainder only; the new day must not be closed. Any refusal leaves both as
they were."""

import sqlite3

from db.audit import audited
from db.connection import transaction
from db.errors import AppError, ConflictError, ErrorCode, ValidationError
from db.names import stored_form
from db.period_lock import refuse_closed_day
from db.purchases import (
    _record,
    _follow_payments,
    invoice_payments,
    invoice_row,
    refuse_cancelled,
    refuse_shared_payments,
)
from db.stocktake import difference, stocktake_after
from db.timeutil import local_day, now_utc

MAX_REASON_LENGTH = 500
CANCEL_NOTE_PREFIX = "ابطال خرید"

# line kind -> (line table, item table, item column)
_TABLES = {
    "MATERIAL": ("material_purchases", "materials", "material_id"),
    "PRODUCT": ("product_purchases", "products", "product_id"),
}


def _lines(conn: sqlite3.Connection, purchase_id: int) -> list[dict]:
    """The invoice's lines in line order (materials and services by id, then products by id), with their item's live
    stock, cost, name and unit, and `line_index`."""
    lines = []
    for kind, (table, item_table, item_column) in _TABLES.items():
        extra = "i.type AS material_type, i.unit" if kind == "MATERIAL" else "'PRODUCT' AS material_type, NULL AS unit"
        for row in conn.execute(
            f"""
            SELECT l.id, l.{item_column} AS item_id, l.quantity_bought, l.stock_movement_id, l.cancel_movement_id,
                   l.item_cost_before, l.item_cost_after, i.name, i.current_stock, i.unit_cost, {extra}
            FROM {table} AS l JOIN {item_table} AS i ON i.id = l.{item_column}
            WHERE l.purchase_invoice_id = ?
            ORDER BY l.id
            """,
            (purchase_id,),
        ):
            line = dict(row)
            line["kind"] = kind
            line["item_type"] = "SERVICE" if row["material_type"] == "SERVICE" else ("STOCK" if kind == "MATERIAL" else "PRODUCT")
            line["service"] = line["item_type"] == "SERVICE"
            del line["material_type"]
            lines.append(line)
    for index, line in enumerate(lines):
        line["line_index"] = index
    return lines


# ----------------------------------------------------------------- the rules


def _line_details(purchase_id: int, line: dict) -> dict:
    return {
        "purchase_id": purchase_id,
        "line_index": line["line_index"],
        "item_type": line["kind"],
        "item_id": line["item_id"],
        "item_name": line["name"],
    }


def _refuse_payments(purchase_id: int, payments: list[dict], with_payments: bool) -> None:
    if not payments:
        return
    paid = sum(p["amount"] for p in payments)
    refuse_shared_payments(purchase_id, payments, paid)
    if not with_payments:
        raise ConflictError(
            f"Purchase #{purchase_id} has payments; cancel it with them (with_payments) or delete them first",
            code=ErrorCode.PURCHASE_HAS_PAYMENTS,
            details={"purchase_id": purchase_id, "paid": paid, "payment_ids": [p["payment_id"] for p in payments], "shared": 0},
        )


def _known_history(line: dict) -> bool:
    return line["item_cost_after"] is not None and (line["service"] or line["stock_movement_id"] is not None)


def _refuse_history_unknown(purchase_id: int, lines: list[dict]) -> None:
    for line in lines:
        if not _known_history(line):
            raise ConflictError(
                f"Purchase #{purchase_id} line {line['line_index']} was recorded before its cost history was kept",
                code=ErrorCode.PURCHASE_COST_HISTORY_UNKNOWN,
                details=_line_details(purchase_id, line),
            )


def _refuse_stock_used(purchase_id: int, lines: list[dict]) -> None:
    for line in lines:
        if line["service"]:
            continue
        if difference(line["current_stock"], line["quantity_bought"]) < 0:
            raise ConflictError(
                f"Less of '{line['name']}' is left ({line['current_stock']}) than purchase #{purchase_id} brought in "
                f"({line['quantity_bought']})",
                code=ErrorCode.PURCHASE_STOCK_USED,
                details={
                    **_line_details(purchase_id, line),
                    "current_stock": line["current_stock"],
                    "quantity_bought": line["quantity_bought"],
                },
            )


def _refuse_stocktake_after(conn: sqlite3.Connection, purchase_id: int, lines: list[dict]) -> None:
    for line in lines:
        if line["service"] or line["stock_movement_id"] is None:
            continue
        row = stocktake_after(conn, line["stock_movement_id"], {(line["kind"], line["item_id"])})
        if row is not None:
            raise ConflictError(
                f"A stocktake recorded after purchase #{purchase_id} counted '{line['name']}'; taking its stock out "
                f"again would count it twice",
                code=ErrorCode.STOCKTAKE_AFTER_PURCHASE,
                details={**_line_details(purchase_id, line), "stocktake_date": local_day(row["movement_date"], conn).isoformat()},
            )


def _purchase_of_movement(conn: sqlite3.Connection, movement_id: int) -> dict | None:
    """{purchase_id, invoice_number} of the purchase line whose own PURCHASE movement this is, or None."""
    for table, _, _ in _TABLES.values():
        row = conn.execute(
            f"SELECT pi.id, pi.invoice_number FROM {table} AS l JOIN purchase_invoices AS pi ON pi.id = l.purchase_invoice_id "
            f"WHERE l.stock_movement_id = ?",
            (movement_id,),
        ).fetchone()
        if row is not None:
            return {"purchase_id": row["id"], "invoice_number": row["invoice_number"]}
    return None


def later_cost_events(conn: sqlite3.Connection, line: dict) -> list[dict]:
    """What came in on the line's item after it, as {reason, movement_id, date, purchase_id, invoice_number}:
    - a stock material or product: every movement after the line's own with a positive quantity, except the
      PURCHASE movement of a line whose invoice is CANCELLED (its cancel movement takes it out again, D1)
    - a service: every later line of the same service on an ACTIVE invoice."""
    if line["service"]:
        rows = conn.execute(
            """
            SELECT pi.id, pi.invoice_number, pi.purchase_date FROM material_purchases AS l
            JOIN purchase_invoices AS pi ON pi.id = l.purchase_invoice_id
            WHERE l.material_id = ? AND l.id > ? AND pi.status = 'ACTIVE'
            ORDER BY l.id
            """,
            (line["item_id"], line["id"]),
        ).fetchall()
        return [
            {"reason": "PURCHASE", "movement_id": None, "date": r["purchase_date"], "purchase_id": r["id"], "invoice_number": r["invoice_number"]}
            for r in rows
        ]
    table = _TABLES[line["kind"]][0]
    rows = conn.execute(
        f"""
        SELECT m.id, m.reason, m.movement_date FROM stock_movements AS m
        WHERE m.item_type = ? AND m.item_id = ? AND m.id > ? AND m.quantity_change > 0
          AND m.id NOT IN (
              SELECT l.stock_movement_id FROM {table} AS l JOIN purchase_invoices AS pi ON pi.id = l.purchase_invoice_id
              WHERE pi.status = 'CANCELLED' AND l.stock_movement_id IS NOT NULL)
        ORDER BY m.id
        """,
        (line["kind"], line["item_id"], line["stock_movement_id"]),
    ).fetchall()
    events = []
    for r in rows:
        purchase = _purchase_of_movement(conn, r["id"]) if r["reason"] == "PURCHASE" else None
        events.append({
            "reason": r["reason"],
            "movement_id": r["id"],
            "date": r["movement_date"],
            "purchase_id": purchase["purchase_id"] if purchase else None,
            "invoice_number": purchase["invoice_number"] if purchase else None,
        })
    return events


def _refuse_cost_changed(conn: sqlite3.Connection, purchase_id: int, lines: list[dict]) -> None:
    for line in lines:
        if not _known_history(line):
            continue
        later = later_cost_events(conn, line)
        changed = line["unit_cost"] != line["item_cost_after"]
        if later or changed:
            raise ConflictError(
                f"The cost of '{line['name']}' changed after purchase #{purchase_id}; cancel the later purchases first",
                code=ErrorCode.PURCHASE_COST_CHANGED_SINCE,
                details={**_line_details(purchase_id, line), "later": later, "cost_changed_without_movement": int(changed and not later)},
            )


def _checks(conn: sqlite3.Connection, invoice: sqlite3.Row, lines: list[dict], payments: list[dict] | None, with_payments: bool):
    """The refusal rules, in the order they are reported. `payments` None: a correction, which moves them."""
    purchase_id = invoice["id"]
    checks = [lambda: refuse_cancelled(conn, invoice)]
    if payments is not None:
        checks.append(lambda: _refuse_payments(purchase_id, payments, with_payments))
    checks += [
        lambda: refuse_closed_day(conn, local_day(invoice["purchase_date"], conn)),
        lambda: _refuse_stock_used(purchase_id, lines),
        lambda: _refuse_stocktake_after(conn, purchase_id, [line for line in lines if _known_history(line)]),
        lambda: _refuse_cost_changed(conn, purchase_id, lines),
        lambda: _refuse_history_unknown(purchase_id, lines),
    ]
    return checks


def _blocker(check) -> dict | None:
    try:
        check()
    except AppError as exc:
        return {"code": str(exc.code), "details": exc.details}
    return None


def plan_cancel_purchase(conn: sqlite3.Connection, purchase_id: int) -> dict:
    """Read-only: what cancelling the invoice would do, and every rule that refuses it now (`blockers`, empty when it
    may be cancelled; PURCHASE_HAS_PAYMENTS is listed while there are payments, since only the owner's tick sends
    `with_payments`). Each line: the quantity taken out, the stock and the unit cost before and after (a service has
    no stock). `payments`: the payments that pay it, each with `shared`."""
    invoice = invoice_row(conn, purchase_id)
    lines = _lines(conn, purchase_id)
    payments = invoice_payments(conn, purchase_id)
    blockers = [b for b in (_blocker(c) for c in _checks(conn, invoice, lines, payments, False)) if b is not None]
    return {
        "purchase_id": purchase_id,
        "invoice_number": invoice["invoice_number"],
        "status": invoice["status"],
        "purchase_date": invoice["purchase_date"],
        "blockers": blockers,
        "lines": [
            {
                "line_index": line["line_index"],
                "kind": line["kind"],
                "item_type": line["item_type"],
                "item_id": line["item_id"],
                "item_name": line["name"],
                "unit": line["unit"],
                "quantity": line["quantity_bought"],
                "stock_before": None if line["service"] else line["current_stock"],
                "stock_after": None if line["service"] else _stock_after(line),
                "cost_before": line["unit_cost"],
                "cost_after": line["item_cost_before"],
            }
            for line in lines
        ],
        "payments": payments,
        "paid": sum(p["amount"] for p in payments),
    }


# ----------------------------------------------------------------- the write


def clean_reason(reason) -> str:
    """The reason as stored (names.stored_form); blank is VOID_REASON_REQUIRED."""
    text = stored_form(reason) if isinstance(reason, str) else ""
    if not text:
        raise ValidationError(
            "A reason is required to cancel or correct a purchase", field="reason", code=ErrorCode.VOID_REASON_REQUIRED
        )
    if len(text) > MAX_REASON_LENGTH:
        raise ValidationError(f"reason must be at most {MAX_REASON_LENGTH} characters", field="reason")
    return text


def _stock_after(line: dict):
    """The stock after taking the line's quantity out, exact to 1e-9 (D2): equal amounts give exactly 0."""
    left = difference(line["current_stock"], line["quantity_bought"])
    return int(left) if line["kind"] == "PRODUCT" else float(left)


def _cancel(conn: sqlite3.Connection, purchase_id: int, text: str, with_payments: bool, correcting: bool) -> sqlite3.Row:
    """Check and cancel inside the caller's transaction; returns the invoice row as it was. A correction (`correcting`)
    keeps the allocations: it moves them to the new invoice."""
    invoice = invoice_row(conn, purchase_id)
    lines = _lines(conn, purchase_id)
    payments = None if correcting else invoice_payments(conn, purchase_id)
    for check in _checks(conn, invoice, lines, payments, with_payments):
        check()
    if payments:
        marks = ", ".join("?" for _ in payments)
        conn.execute(f"DELETE FROM supplier_payments WHERE id IN ({marks})", [p["payment_id"] for p in payments])
    note = f"{CANCEL_NOTE_PREFIX} {invoice['invoice_number'] or '#' + str(purchase_id)} — {text}"
    for line in lines:
        table, item_table, _ = _TABLES[line["kind"]]
        if not line["service"]:
            conn.execute(f"UPDATE {item_table} SET current_stock = ? WHERE id = ?", (_stock_after(line), line["item_id"]))
            movement = conn.execute(
                "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason, notes) VALUES (?, ?, ?, 'PURCHASE', ?)",
                (line["kind"], line["item_id"], -line["quantity_bought"], note),
            ).lastrowid
            conn.execute(f"UPDATE {table} SET cancel_movement_id = ? WHERE id = ?", (movement, line["id"]))
        if line["unit_cost"] != line["item_cost_before"]:
            conn.execute(f"UPDATE {item_table} SET unit_cost = ? WHERE id = ?", (line["item_cost_before"], line["item_id"]))
    conn.execute(
        "UPDATE purchase_invoices SET status = 'CANCELLED', cancel_reason = ?, cancelled_at = ? WHERE id = ?",
        (text, now_utc(), purchase_id),
    )
    return invoice


@audited()
def cancel_purchase(conn: sqlite3.Connection, purchase_id: int, reason: str, with_payments: bool = False) -> None:
    """Cancel a whole purchase invoice entered by mistake: its stock goes back out, its items get back the cost they
    had before it, and it leaves every purchase figure, keeping its row, lines, number and figures. `with_payments`: the
    payments allocated only to it are deleted with it (the owner ticked «پرداخت‌های این خرید هم حذف شوند»).
    Refusals: see the module docstring."""
    text = clean_reason(reason)
    with transaction(conn):
        _cancel(conn, purchase_id, text, bool(with_payments), correcting=False)


@audited()
def correct_purchase(
    conn: sqlite3.Connection,
    purchase_id: int,
    reason: str,
    lines: list[dict],
    supplier_id: int | None = None,
    purchase_date: str | None = None,
    notes: str | None = None,
    payment: dict | None = None,
) -> int:
    """Cancel `purchase_id` and record the right invoice in its place (`record_purchase`'s arguments); returns the new
    invoice's id. The allocations move to it; `payment` (FULL / NONE / PARTIAL) is on the part not yet paid."""
    text = clean_reason(reason)
    with transaction(conn):
        invoice = invoice_row(conn, purchase_id)
        refuse_cancelled(conn, invoice)
        payments = invoice_payments(conn, purchase_id)
        paid = sum(p["amount"] for p in payments)
        supplier_changed = supplier_id != invoice["supplier_id"]
        if payments and supplier_changed:
            refuse_shared_payments(purchase_id, payments, paid)
        _cancel(conn, purchase_id, text, False, correcting=True)

        def move_allocations(new_id: int, new_date: str) -> None:
            conn.execute(
                "UPDATE supplier_payment_allocations SET purchase_invoice_id = ? WHERE purchase_invoice_id = ?",
                (new_id, purchase_id),
            )
            if payments:
                _follow_payments(
                    conn, new_id, invoice_payments(conn, new_id), invoice["purchase_date"], new_date,
                    supplier_id, supplier_changed, made_with_id=purchase_id,
                )

        new_id, _ = _record(
            conn, lines, supplier_id, purchase_date, notes, payment, one_line=False,
            corrects={"purchase_id": purchase_id, "paid": paid, "before_payment": move_allocations},
        )
        new_date = conn.execute("SELECT purchase_date FROM purchase_invoices WHERE id = ?", (new_id,)).fetchone()[0]
        refuse_closed_day(conn, local_day(new_date, conn))
        conn.execute("UPDATE purchase_invoices SET replaces_invoice_id = ? WHERE id = ?", (purchase_id, new_id))
    return new_id
