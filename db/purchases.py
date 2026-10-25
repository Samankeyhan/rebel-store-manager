"""Purchase invoices from suppliers (accounting rules sections 2, 21 and 22). One supplier invoice is one purchase: a
`purchase_invoices` row (PUR number, supplier, day, note, status) with one or more lines in `material_purchases` /
`product_purchases` (the item, quantity, line total `total_paid` and unit cost). One invoice may mix STOCK materials,
services and products; the same item twice on one invoice is refused (PURCHASE_DUPLICATE_ITEM). The invoice `total` is
Σ line totals, computed on read, never stored.
Recording (`record_purchase`, one transaction): a STOCK material or product line raises the item's stock, blends its
cost (`blend_unit_cost`) and writes its own PURCHASE movement (`stock_movement_id`); a SERVICE line has no stock and
writes no movement, it sets the service's price to line total ÷ quantity (the same `blend_unit_cost`, with no stock),
so a service line of total 0 is refused (SERVICE_PURCHASE_NEEDS_TOTAL). Every line stores the item's unit cost just
before and just after it (`item_cost_before` / `item_cost_after`) for a later cancel or correction
(docs/plans/2026-10-payables-purchase-correction.md, slice B). A purchase is not an expense: it reaches the P&L only
as the stock or service is consumed or wasted. What was paid is in db/supplier_payments.py: FULL (the default), NONE
(on credit) or PARTIAL, on the invoice total; NONE / PARTIAL need a supplier.
`record_material_purchase` / `record_product_purchase` record a one-line invoice and return the line id.
`update_purchase` corrects an invoice's supplier, day or note (section 23); a cancel or correction of the whole
invoice is db/purchase_cancel.py.
Reads: `get_purchase` / `list_purchases` per invoice (with `paid`, `outstanding`, `payment_status`, section 21;
CANCELLED invoices only with `include_cancelled`);
`list_material_purchases` / `list_product_purchases` / `get_*_purchase` per line, with its invoice's fields."""

import sqlite3

from db.audit import audited
from db.connection import next_counter, transaction
from db.costing import blend_unit_cost, check_money, check_quantity, per_unit_cost
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.materials import get_material
from db.products import get_product
from db.supplier_payments import (
    BACKFILL_NOTE,
    check_purchase_payment,
    not_found,
    paid_sql,
    purchase_payments,
    record_purchase_payment,
    total_sql,
    with_payment_figures,
)
from db.suppliers import get_supplier
from db.timeutil import local_day, normalize_record_date, refuse_future_day, to_utc_range

# line kind -> (line table, item table, item column, note label)
_KINDS = {
    "MATERIAL": ("material_purchases", "materials", "material_id", "Material"),
    "PRODUCT": ("product_purchases", "products", "product_id", "Product"),
}
# the item types a list can be narrowed to: STOCK materials, services, products
ITEM_TYPES = ("MATERIAL", "SERVICE", "PRODUCT")


def _validate_supplier(conn: sqlite3.Connection, supplier_id: int | None) -> None:
    if supplier_id is None:
        return
    if get_supplier(conn, supplier_id) is None:
        raise NotFoundError(
            f"Supplier with id {supplier_id} does not exist",
            code=ErrorCode.SUPPLIER_NOT_FOUND,
            details={"supplier_id": supplier_id},
        )


def _with_field(exc: ValidationError, field: str) -> ValidationError:
    return ValidationError(str(exc), field=field, code=exc.code, details=exc.details)


def _check_line(conn: sqlite3.Connection, index: int, line, prefix: str) -> dict:
    """One line, checked before anything is written: {kind, item, quantity_bought, total_paid, unit_cost, cost_before,
    cost_after, service}. `prefix` is put before each field name ("lines.N." for record_purchase, "" for the one-line
    wrappers)."""
    if not isinstance(line, dict):
        raise ValidationError(f"Line {index} must be an object", field=f"{prefix}kind" if prefix else "lines")
    kind = line.get("kind")
    if kind not in _KINDS:
        raise ValidationError(f"kind must be MATERIAL or PRODUCT, got {kind!r}", field=f"{prefix}kind")
    item_id = line.get("item_id")
    if isinstance(item_id, bool) or not isinstance(item_id, int):
        raise ValidationError(f"item_id must be an integer, got {item_id!r}", field=f"{prefix}item_id")
    item = get_material(conn, item_id) if kind == "MATERIAL" else get_product(conn, item_id)
    if item is None:
        raise NotFoundError(f"{kind.capitalize()} with id {item_id} does not exist")
    if not item["is_active"]:
        raise ValidationError(f"{kind.capitalize()} '{item['name']}' is not active", field=f"{prefix}item_id")
    service = kind == "MATERIAL" and item["type"] == "SERVICE"

    quantity = line.get("quantity_bought")
    if kind == "PRODUCT" and isinstance(quantity, float) and quantity.is_integer():
        quantity = int(quantity)  # the API reads every quantity as a number: 3.0 is 3 units, 1.5 is refused below
    try:
        check_quantity(quantity, "quantity_bought", whole=kind == "PRODUCT")
    except ValidationError as exc:
        raise _with_field(exc, f"{prefix}quantity_bought") from None
    total = line.get("total_paid")
    if isinstance(total, bool) or not isinstance(total, int):
        raise ValidationError(f"total_paid must be an integer amount of Rial, got {total!r}", field=f"{prefix}total_paid")
    try:
        check_money(total, "total_paid")
    except ValidationError as exc:
        raise _with_field(exc, f"{prefix}total_paid") from None
    if total < 0:
        raise ValidationError(f"total_paid must be >= 0, got {total}", field=f"{prefix}total_paid")
    if service and total == 0:
        raise ValidationError(
            f"A purchase of the service '{item['name']}' needs its price: a total of 0 would erase it",
            field=f"{prefix}total_paid",
            code=ErrorCode.SERVICE_PURCHASE_NEEDS_TOTAL,
            details={"index": index, "material_id": item_id, "material_name": item["name"]},
        )
    try:
        unit_cost = per_unit_cost(total, quantity)
        # a SERVICE has no stock (current_stock NULL), so this is total ÷ quantity: the new price
        cost_after = blend_unit_cost(item["current_stock"], item["unit_cost"], quantity, total, zero_is_unknown=kind == "MATERIAL")
    except ValidationError as exc:
        if exc.code != ErrorCode.AMOUNT_TOO_LARGE:
            raise
        # A tiny quantity makes the per-unit cost too large: the amount to change is total_paid.
        raise ValidationError(
            f"The unit cost (total_paid / quantity_bought) must be at most {exc.details['max']} Rial",
            field=f"{prefix}total_paid", code=exc.code, details=exc.details,
        ) from None
    return {
        "kind": kind, "item": item, "quantity_bought": quantity, "total_paid": total, "unit_cost": unit_cost,
        "cost_before": item["unit_cost"], "cost_after": cost_after, "service": service,
    }


def _record(
    conn: sqlite3.Connection,
    lines,
    supplier_id: int | None,
    purchase_date: str | None,
    notes: str | None,
    payment: dict | None,
    one_line: bool,
    corrects: dict | None = None,
) -> tuple[int, list[int]]:
    """Check every line, then write the invoice, its lines, each item's stock and cost, the PURCHASE movements and the
    payment made with it, in one transaction. Returns (invoice id, line ids).
    `corrects` (a correction, db/purchase_cancel.py): {purchase_id, paid, before_payment}. The new total must be at least
    `paid` (PURCHASE_CORRECTION_BELOW_PAID), the payment chosen on the form is on the remainder only, and
    `before_payment(new invoice id, its purchase_date)` runs after the lines are written and before that payment (it
    moves the old invoice's allocations)."""
    if not isinstance(lines, (list, tuple)) or not lines:
        raise ValidationError("A purchase needs at least one line", field="lines")
    checked, seen = [], set()
    for index, line in enumerate(lines):
        prefix = "" if one_line else f"lines.{index}."
        entry = _check_line(conn, index, line, prefix)
        key = (entry["kind"], entry["item"]["id"])
        if key in seen:
            raise ValidationError(
                f"'{entry['item']['name']}' is already on this purchase",
                field=f"{prefix}item_id",
                code=ErrorCode.PURCHASE_DUPLICATE_ITEM,
                details={"index": index, "item_type": entry["kind"], "item_id": entry["item"]["id"]},
            )
        seen.add(key)
        checked.append(entry)
    total = sum(entry["total_paid"] for entry in checked)
    check_money(total, "total_paid" if one_line else "lines")
    _validate_supplier(conn, supplier_id)
    paid_before = corrects["paid"] if corrects else 0
    if total < paid_before:
        raise ValidationError(
            f"The corrected total ({total}) is below what was already paid ({paid_before})",
            field="lines",
            code=ErrorCode.PURCHASE_CORRECTION_BELOW_PAID,
            details={"purchase_id": corrects["purchase_id"], "paid": paid_before, "new_total": total},
        )
    paid_now = check_purchase_payment(payment, supplier_id, total - paid_before)
    if purchase_date is not None:
        purchase_date = normalize_record_date(purchase_date, conn)

    with transaction(conn):
        invoice_number = f"PUR-{next_counter(conn, 'PUR'):06d}"
        invoice_id = conn.execute(
            "INSERT INTO purchase_invoices (invoice_number, supplier_id, purchase_date, notes) "
            "VALUES (?, ?, COALESCE(?, datetime('now')), ?)",
            (invoice_number, supplier_id, purchase_date, notes),
        ).lastrowid
        stored_date = conn.execute("SELECT purchase_date FROM purchase_invoices WHERE id = ?", (invoice_id,)).fetchone()[0]
        line_ids = []
        for entry in checked:
            table, item_table, item_column, label = _KINDS[entry["kind"]]
            item_id = entry["item"]["id"]
            line_id = conn.execute(
                f"""
                INSERT INTO {table}
                    (purchase_invoice_id, {item_column}, quantity_bought, total_paid, unit_cost, item_cost_before, item_cost_after)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (invoice_id, item_id, entry["quantity_bought"], entry["total_paid"], entry["unit_cost"],
                 entry["cost_before"], entry["cost_after"]),
            ).lastrowid
            line_ids.append(line_id)
            if entry["service"]:
                # no stock: only the price changes, and no movement is written
                conn.execute("UPDATE materials SET unit_cost = ? WHERE id = ?", (entry["cost_after"], item_id))
                continue
            conn.execute(
                f"UPDATE {item_table} SET current_stock = current_stock + ?, unit_cost = ? WHERE id = ?",
                (entry["quantity_bought"], entry["cost_after"], item_id),
            )
            movement = conn.execute(
                """
                INSERT INTO stock_movements
                    (item_type, item_id, quantity_change, reason, movement_date, notes)
                VALUES (?, ?, ?, 'PURCHASE', ?, ?)
                """,
                (entry["kind"], item_id, entry["quantity_bought"], stored_date,
                 f"{label} purchase #{line_id} (invoice {invoice_number})"),
            )
            conn.execute(f"UPDATE {table} SET stock_movement_id = ? WHERE id = ?", (movement.lastrowid, line_id))
        if corrects:
            corrects["before_payment"](invoice_id, stored_date)
        record_purchase_payment(conn, invoice_id, paid_now)
    return invoice_id, line_ids


@audited()
def record_purchase(
    conn: sqlite3.Connection,
    lines: list[dict],
    supplier_id: int | None = None,
    purchase_date: str | None = None,
    notes: str | None = None,
    payment: dict | None = None,
) -> int:
    """One supplier invoice. `lines`: [{kind MATERIAL | PRODUCT, item_id, quantity_bought, total_paid}] (a MATERIAL may
    be a STOCK material or a service); errors name the field as `lines.N.<field>`. `payment`: {mode FULL | NONE |
    PARTIAL, amount (PARTIAL only), method, reference} on the invoice total; None = paid in full. Returns the
    purchase (invoice) id."""
    return _record(conn, lines, supplier_id, purchase_date, notes, payment, one_line=False)[0]


@audited()
def record_material_purchase(
    conn: sqlite3.Connection,
    material_id: int,
    quantity_bought: float,
    total_paid: int,
    supplier_id: int | None = None,
    purchase_date: str | None = None,
    notes: str | None = None,
    payment: dict | None = None,
) -> int:
    """A purchase of one material (STOCK or SERVICE): a one-line invoice. Returns the line id."""
    line = {"kind": "MATERIAL", "item_id": material_id, "quantity_bought": quantity_bought, "total_paid": total_paid}
    return _record(conn, [line], supplier_id, purchase_date, notes, payment, one_line=True)[1][0]


@audited()
def record_product_purchase(
    conn: sqlite3.Connection,
    product_id: int,
    quantity_bought: int,
    total_paid: int,
    supplier_id: int | None = None,
    purchase_date: str | None = None,
    notes: str | None = None,
    payment: dict | None = None,
) -> int:
    """A purchase of one product: a one-line invoice. Returns the line id."""
    line = {"kind": "PRODUCT", "item_id": product_id, "quantity_bought": quantity_bought, "total_paid": total_paid}
    return _record(conn, [line], supplier_id, purchase_date, notes, payment, one_line=True)[1][0]


# ---------------------------------------------------------------- edits (section 23)

UPDATABLE_FIELDS = ("supplier_id", "purchase_date", "notes")


def invoice_row(conn: sqlite3.Connection, purchase_id: int) -> sqlite3.Row:
    """The purchase_invoices row, or PURCHASE_NOT_FOUND."""
    row = conn.execute("SELECT * FROM purchase_invoices WHERE id = ?", (purchase_id,)).fetchone()
    if row is None:
        raise not_found(purchase_id)
    return row


def refuse_cancelled(conn: sqlite3.Connection, invoice: sqlite3.Row) -> None:
    """PURCHASE_ALREADY_CANCELLED for a CANCELLED invoice: it can be neither edited, cancelled nor corrected."""
    if invoice["status"] == "CANCELLED":
        replaced_by = conn.execute(
            "SELECT id FROM purchase_invoices WHERE replaces_invoice_id = ?", (invoice["id"],)
        ).fetchone()
        raise ConflictError(
            f"Purchase #{invoice['id']} is already cancelled",
            code=ErrorCode.PURCHASE_ALREADY_CANCELLED,
            details={
                "purchase_id": invoice["id"],
                "cancelled_at": invoice["cancelled_at"],
                "replaced_by_purchase_id": replaced_by[0] if replaced_by else None,
            },
        )


def invoice_payments(conn: sqlite3.Connection, purchase_id: int) -> list[dict]:
    """The payments that paid this invoice (`purchase_payments`), each with `shared` 1 when it also pays another
    purchase (a payment is always wholly allocated, so it is shared exactly when its whole amount is more than the part
    allocated here)."""
    return [{**p, "shared": int(p["payment_amount"] != p["amount"])} for p in purchase_payments(conn, purchase_id)]


def refuse_shared_payments(purchase_id: int, payments: list[dict], paid: int) -> None:
    """PURCHASE_HAS_PAYMENTS (shared 1) when a payment of this invoice also pays another purchase."""
    if any(p["shared"] for p in payments):
        raise ConflictError(
            f"A payment of purchase #{purchase_id} also pays another purchase",
            code=ErrorCode.PURCHASE_HAS_PAYMENTS,
            details={"purchase_id": purchase_id, "paid": paid, "payment_ids": [p["payment_id"] for p in payments], "shared": 1},
        )


def _made_with(conn: sqlite3.Connection, purchase_id: int, payment: dict, purchase_date: str) -> bool:
    """Whether `payment` is the one recorded with the purchase (FULL or PARTIAL on the form) and still dated with it:
    its audit INSERT is in the same operation as the invoice's or one of its lines' INSERT; for a purchase from before
    migration 015, the backfilled payment (BACKFILL_NOTE) dated with it. A payment recorded on its own on the same day
    is not."""
    if payment["shared"] or payment["payment_date"] != purchase_date:
        return False
    if payment["note"] == BACKFILL_NOTE:
        return True
    return conn.execute(
        """
        SELECT 1 FROM audit_log AS p
        WHERE p.entity_type = 'supplier_payments' AND p.entity_id = CAST(? AS TEXT) AND p.action = 'INSERT'
          AND p.op_id IS NOT NULL
          AND p.op_id IN (
              SELECT a.op_id FROM audit_log AS a
              WHERE a.action = 'INSERT' AND a.op_id IS NOT NULL AND (
                  (a.entity_type = 'purchase_invoices' AND a.entity_id = CAST(? AS TEXT))
                  OR (a.entity_type = 'material_purchases' AND a.entity_id IN
                      (SELECT CAST(id AS TEXT) FROM material_purchases WHERE purchase_invoice_id = ?))
                  OR (a.entity_type = 'product_purchases' AND a.entity_id IN
                      (SELECT CAST(id AS TEXT) FROM product_purchases WHERE purchase_invoice_id = ?))))
        """,
        (payment["payment_id"], purchase_id, purchase_id, purchase_id),
    ).fetchone() is not None


def _follow_payments(
    conn: sqlite3.Connection,
    purchase_id: int,
    payments: list[dict],
    old_date: str,
    new_date: str,
    supplier_id: int | None,
    supplier_changed: bool,
    made_with_id: int | None = None,
) -> None:
    """The payments of an invoice whose supplier or day changes (D3, D4): when the supplier changes, every payment must
    be wholly on this invoice (else PURCHASE_HAS_PAYMENTS, shared) and follows it; the payment made with the purchase
    (`_made_with`) moves to the new moment; every other payment must not be before the new local day
    (SUPPLIER_PAYMENT_BEFORE_PURCHASE). `made_with_id`: the invoice the payments were made with, when it is not
    `purchase_id` (a correction moves them to the new invoice)."""
    if supplier_changed:
        refuse_shared_payments(purchase_id, payments, sum(p["amount"] for p in payments))
    new_day = local_day(new_date, conn)
    for payment in payments:
        changes: dict = {}
        if supplier_changed:
            changes["supplier_id"] = supplier_id
        if _made_with(conn, made_with_id or purchase_id, payment, old_date):
            if new_date != old_date:
                changes["payment_date"] = new_date
        elif local_day(payment["payment_date"], conn) < new_day:
            raise ValidationError(
                f"Payment #{payment['payment_id']} is dated before the purchase's new day {new_day}",
                field="purchase_date",
                code=ErrorCode.SUPPLIER_PAYMENT_BEFORE_PURCHASE,
                details={"purchase_id": purchase_id, "purchase_date": new_day.isoformat()},
            )
        if changes:
            conn.execute(
                f"UPDATE supplier_payments SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ?",
                [*changes.values(), payment["payment_id"]],
            )


@audited()
def update_purchase(conn: sqlite3.Connection, purchase_id: int, **fields) -> None:
    """Correct an invoice's supplier, day or note (accounting rules section 23). None of them changes stock, cost, P&L
    or a distribution, so a closed day does not refuse them. A CANCELLED invoice is PURCHASE_ALREADY_CANCELLED.
    - supplier_id: an existing supplier (SUPPLIER_NOT_FOUND); None while something is owed is
      SUPPLIER_REQUIRED_FOR_CREDIT; the payments wholly on this invoice follow it, a shared one refuses
      (PURCHASE_HAS_PAYMENTS).
    - purchase_date: a local day, not in the future (DATE_IN_FUTURE); the same local day keeps the stored moment;
      every line's PURCHASE movement follows; the payment made with the purchase moves with it, any other payment must
      not be before the new day (SUPPLIER_PAYMENT_BEFORE_PURCHASE).
    - notes."""
    for name in fields:
        if name not in UPDATABLE_FIELDS:
            raise ValidationError(f"Unknown field '{name}'", field=name)
    with transaction(conn):
        invoice = invoice_row(conn, purchase_id)
        refuse_cancelled(conn, invoice)
        changes: dict = {}
        if "notes" in fields:
            changes["notes"] = fields["notes"]
        supplier_id = invoice["supplier_id"]
        supplier_changed = "supplier_id" in fields and fields["supplier_id"] != invoice["supplier_id"]
        if supplier_changed:
            supplier_id = fields["supplier_id"]
            if supplier_id is not None and (isinstance(supplier_id, bool) or not isinstance(supplier_id, int)):
                raise ValidationError(f"supplier_id must be an integer, got {supplier_id!r}", field="supplier_id")
            _validate_supplier(conn, supplier_id)
            owed = conn.execute(
                f"SELECT {total_sql()} - {paid_sql()} FROM purchase_invoices WHERE id = ?", (purchase_id,)
            ).fetchone()[0]
            if supplier_id is None and owed > 0:
                raise ValidationError(
                    "A purchase that is not paid in full needs a supplier", field="supplier_id",
                    code=ErrorCode.SUPPLIER_REQUIRED_FOR_CREDIT,
                )
            changes["supplier_id"] = supplier_id
        new_date = invoice["purchase_date"]
        if "purchase_date" in fields:
            if not isinstance(fields["purchase_date"], str):
                raise ValidationError(f"purchase_date must be 'YYYY-MM-DD', got {fields['purchase_date']!r}", field="purchase_date")
            moment = normalize_record_date(fields["purchase_date"], conn)
            day = local_day(moment, conn)
            refuse_future_day(conn, day, "purchase_date")
            if day != local_day(invoice["purchase_date"], conn):
                new_date = moment
                changes["purchase_date"] = moment
        if supplier_changed or new_date != invoice["purchase_date"]:
            _follow_payments(
                conn, purchase_id, invoice_payments(conn, purchase_id), invoice["purchase_date"], new_date,
                supplier_id, supplier_changed,
            )
        if not changes:
            return
        conn.execute(
            f"UPDATE purchase_invoices SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ?",
            [*changes.values(), purchase_id],
        )
        if "purchase_date" in changes:
            for table, _, _, _ in _KINDS.values():
                conn.execute(
                    f"UPDATE stock_movements SET movement_date = ? WHERE id IN "
                    f"(SELECT stock_movement_id FROM {table} WHERE purchase_invoice_id = ? AND stock_movement_id IS NOT NULL)",
                    (new_date, purchase_id),
                )


# ---------------------------------------------------------------- reads

_INVOICE_SQL = f"""
    SELECT pi.id, pi.invoice_number, pi.supplier_id, suppliers.name AS supplier_name, pi.purchase_date, pi.notes,
           pi.status, pi.cancel_reason, pi.cancelled_at, pi.replaces_invoice_id,
           (SELECT r.id FROM purchase_invoices AS r WHERE r.replaces_invoice_id = pi.id) AS replaced_by_invoice_id,
           {total_sql("pi")} AS total, {paid_sql("pi")} AS paid
    FROM purchase_invoices AS pi
    LEFT JOIN suppliers ON suppliers.id = pi.supplier_id
"""

_LINES_SQL = """
    SELECT * FROM (
        SELECT 'MATERIAL' AS kind, 0 AS kind_order, l.id, l.material_id AS item_id, m.name AS item_name,
               m.type AS item_type, m.unit, l.quantity_bought, l.total_paid, l.unit_cost
        FROM material_purchases AS l JOIN materials AS m ON m.id = l.material_id
        WHERE l.purchase_invoice_id = :id
        UNION ALL
        SELECT 'PRODUCT', 1, l.id, l.product_id, p.name, 'PRODUCT', NULL, l.quantity_bought, l.total_paid, l.unit_cost
        FROM product_purchases AS l JOIN products AS p ON p.id = l.product_id
        WHERE l.purchase_invoice_id = :id
    ) ORDER BY kind_order, id
"""


def purchase_lines(conn: sqlite3.Connection, purchase_id: int) -> list[dict]:
    """A purchase invoice's lines in line order (materials and services, then products, each by line id): kind
    (MATERIAL | PRODUCT), item_type (STOCK | SERVICE | PRODUCT), item id, name and unit (None for a product), quantity,
    line total and unit cost."""
    lines = []
    for row in conn.execute(_LINES_SQL, {"id": purchase_id}):
        line = dict(row)
        del line["kind_order"]
        lines.append(line)
    return lines


def _invoice(conn: sqlite3.Connection, row) -> dict:
    purchase = with_payment_figures(dict(row))
    purchase["lines"] = purchase_lines(conn, purchase["id"])
    return purchase


def get_purchase(conn: sqlite3.Connection, purchase_id: int) -> dict | None:
    """One purchase invoice with its lines, payment figures and `payments` (the payments that paid it)."""
    row = conn.execute(f"{_INVOICE_SQL} WHERE pi.id = ?", (purchase_id,)).fetchone()
    if row is None:
        return None
    purchase = _invoice(conn, row)
    purchase["payments"] = purchase_payments(conn, purchase_id)
    return purchase


def require_purchase(conn: sqlite3.Connection, purchase_id: int) -> dict:
    """`get_purchase`, or PURCHASE_NOT_FOUND."""
    purchase = get_purchase(conn, purchase_id)
    if purchase is None:
        raise not_found(purchase_id)
    return purchase


def list_purchases(
    conn: sqlite3.Connection,
    supplier_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    item_type: str | None = None,
    item_id: int | None = None,
    include_cancelled: bool = False,
) -> list[dict]:
    """Purchase invoices, newest first (purchase_date, then id), each with its lines and payment figures. CANCELLED
    invoices are left out unless `include_cancelled` (section 23). `item_type` (MATERIAL = STOCK materials, SERVICE,
    PRODUCT) keeps the invoices with a line of that type; with `item_id` too, a line of that item. Dates are local
    calendar days (section 1)."""
    query = f"{_INVOICE_SQL} WHERE 1=1"
    params: list = []
    if not include_cancelled:
        query += " AND pi.status = 'ACTIVE'"
    if supplier_id is not None:
        query += " AND pi.supplier_id = ?"
        params.append(supplier_id)
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND pi.purchase_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND pi.purchase_date < ?"
        params.append(end_exclusive_utc)
    if item_type is not None:
        if item_type not in ITEM_TYPES:
            raise ValidationError(f"item_type must be one of {', '.join(ITEM_TYPES)}, got {item_type!r}", field="item_type")
        if item_type == "PRODUCT":
            line = "SELECT 1 FROM product_purchases AS l WHERE l.purchase_invoice_id = pi.id"
        else:
            material_type = "SERVICE" if item_type == "SERVICE" else "STOCK"
            line = (
                "SELECT 1 FROM material_purchases AS l JOIN materials AS m ON m.id = l.material_id "
                f"WHERE l.purchase_invoice_id = pi.id AND m.type = '{material_type}'"
            )
        if item_id is not None:
            line += f" AND l.{'product_id' if item_type == 'PRODUCT' else 'material_id'} = ?"
            params.append(item_id)
        query += f" AND EXISTS ({line})"
    elif item_id is not None:
        raise ValidationError("item_id needs item_type", field="item_id")
    query += " ORDER BY pi.purchase_date DESC, pi.id DESC"
    return [_invoice(conn, row) for row in conn.execute(query, params).fetchall()]


def _line_select(kind: str) -> str:
    """A purchase line with its invoice's fields (number, supplier, day, note, status) and the item's name."""
    table, item_table, item_column, _ = _KINDS[kind]
    item_name = "material_name" if kind == "MATERIAL" else "product_name"
    return f"""
        SELECT
            l.id, l.purchase_invoice_id, l.{item_column}, pi.supplier_id, pi.invoice_number, pi.purchase_date,
            l.quantity_bought, l.total_paid, l.unit_cost, pi.notes, pi.status, pi.cancel_reason, pi.cancelled_at,
            {item_table}.name AS {item_name}, suppliers.name AS supplier_name
        FROM {table} AS l
        JOIN purchase_invoices AS pi ON pi.id = l.purchase_invoice_id
        JOIN {item_table} ON {item_table}.id = l.{item_column}
        LEFT JOIN suppliers ON suppliers.id = pi.supplier_id
    """


def _get_line(conn: sqlite3.Connection, kind: str, line_id: int) -> dict | None:
    row = conn.execute(f"{_line_select(kind)} WHERE l.id = ?", (line_id,)).fetchone()
    return dict(row) if row is not None else None


def get_material_purchase(conn: sqlite3.Connection, purchase_id: int) -> dict | None:
    """One material purchase line, with its invoice's fields."""
    return _get_line(conn, "MATERIAL", purchase_id)


def get_product_purchase(conn: sqlite3.Connection, purchase_id: int) -> dict | None:
    """One product purchase line, with its invoice's fields."""
    return _get_line(conn, "PRODUCT", purchase_id)


def _list_lines(
    conn: sqlite3.Connection,
    kind: str,
    item_id: int | None,
    supplier_id: int | None,
    start_date: str | None,
    end_date: str | None,
) -> list[dict]:
    item_column = _KINDS[kind][2]
    query = f"{_line_select(kind)} WHERE 1=1"
    params: list = []
    if item_id is not None:
        query += f" AND l.{item_column} = ?"
        params.append(item_id)
    if supplier_id is not None:
        query += " AND pi.supplier_id = ?"
        params.append(supplier_id)
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND pi.purchase_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND pi.purchase_date < ?"
        params.append(end_exclusive_utc)
    query += " ORDER BY pi.purchase_date DESC, l.id DESC"
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def list_material_purchases(
    conn: sqlite3.Connection,
    material_id: int | None = None,
    supplier_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Material purchase lines (STOCK and SERVICE), newest first, each with its invoice's fields."""
    return _list_lines(conn, "MATERIAL", material_id, supplier_id, start_date, end_date)


def list_product_purchases(
    conn: sqlite3.Connection,
    product_id: int | None = None,
    supplier_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Product purchase lines, newest first, each with its invoice's fields."""
    return _list_lines(conn, "PRODUCT", product_id, supplier_id, start_date, end_date)
