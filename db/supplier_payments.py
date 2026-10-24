"""What the shop owes its suppliers (docs/accounting-rules.md section 21). A purchase is a purchase invoice
(`purchase_invoices`, section 22); its `total` is the sum of its line totals, computed on read (`total_sql`). A supplier
payment (`supplier_payments`) is money paid to one supplier, split over that supplier's purchase invoices by
`supplier_payment_allocations`. `paid` (Σ allocations), `outstanding` (total − paid) and `payment_status` (UNPAID,
PARTIAL, PAID) are computed on read, never stored. Only ACTIVE purchases owe anything.
`record_supplier_payment` (allocations given, or oldest first by `allocate_oldest_first`), `update_supplier_payment`
(date, method, reference, note only), `delete_supplier_payment` (hard delete; the audit log keeps the rows).
No advances: a payment is always wholly allocated and never more than what is owed. Payments are cash, never P&L, and a
closed day (section 11) never refuses them. `record_purchase_payment` is the purchase form's payment (db/purchases.py).
A supplier that has payments must not be deleted (there is no supplier delete; the foreign key refuses it too)."""

import sqlite3

from db.audit import audited
from db.connection import transaction
from db.costing import check_money
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.timeutil import local_day, normalize_record_date, refuse_future_day, to_utc_range

METHODS = ("CASH", "CARD", "BANK_TRANSFER", "CHEQUE", "OTHER")
PAYMENT_MODES = ("FULL", "NONE", "PARTIAL")
UNPAID, PARTIAL, PAID = "UNPAID", "PARTIAL", "PAID"
UPDATABLE_FIELDS = ("payment_date", "method", "reference", "note")
ACTIVE = "ACTIVE"


def total_sql(alias: str = "purchase_invoices") -> str:
    """SQL for a purchase invoice's total: Σ its line totals (the invoice row in scope is `alias`)."""
    return (
        f"((SELECT COALESCE(SUM(l.total_paid), 0) FROM material_purchases AS l WHERE l.purchase_invoice_id = {alias}.id)"
        f" + (SELECT COALESCE(SUM(l.total_paid), 0) FROM product_purchases AS l WHERE l.purchase_invoice_id = {alias}.id))"
    )


def paid_sql(alias: str = "purchase_invoices") -> str:
    """SQL for Σ allocations of the purchase invoice in scope (`alias`)."""
    return (
        f"(SELECT COALESCE(SUM(spa.amount), 0) FROM supplier_payment_allocations AS spa "
        f"WHERE spa.purchase_invoice_id = {alias}.id)"
    )


def item_names(conn: sqlite3.Connection, purchase_id: int) -> list[str]:
    """The item names of a purchase invoice's lines: materials (and services), then products, each by line id."""
    return [
        r[0]
        for r in conn.execute(
            """
            SELECT name FROM (
                SELECT 0 AS k, l.id, m.name FROM material_purchases AS l JOIN materials AS m ON m.id = l.material_id
                WHERE l.purchase_invoice_id = ?
                UNION ALL
                SELECT 1, l.id, p.name FROM product_purchases AS l JOIN products AS p ON p.id = l.product_id
                WHERE l.purchase_invoice_id = ?
            ) ORDER BY k, id
            """,
            (purchase_id, purchase_id),
        )
    ]


def payment_status(total: int, paid: int) -> str:
    if paid >= total:
        return PAID
    return UNPAID if paid == 0 else PARTIAL


def with_payment_figures(row: dict) -> dict:
    """A purchase invoice row that has `total` and `paid` gains `outstanding` and `payment_status`."""
    row["outstanding"] = row["total"] - row["paid"]
    row["payment_status"] = payment_status(row["total"], row["paid"])
    return row


# ---------------------------------------------------------------- validation


def _check_amount(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field} must be an integer amount of Rial, got {value!r}", field=field)
    check_money(value, field)
    if value <= 0:
        raise ValidationError(f"{field} must be > 0, got {value}", field=field)
    return value


def _check_method(method) -> str:
    if method not in METHODS:
        raise ValidationError(f"method must be one of {', '.join(METHODS)}, got {method!r}", field="method")
    return method


def _check_supplier(conn: sqlite3.Connection, supplier_id: int | None) -> None:
    if supplier_id is not None and conn.execute("SELECT 1 FROM suppliers WHERE id = ?", (supplier_id,)).fetchone() is None:
        raise NotFoundError(
            f"Supplier with id {supplier_id} does not exist",
            code=ErrorCode.SUPPLIER_NOT_FOUND,
            details={"supplier_id": supplier_id},
        )


def _payment_moment(conn: sqlite3.Connection, payment_date: str) -> str:
    if not isinstance(payment_date, str):
        raise ValidationError(f"payment_date must be 'YYYY-MM-DD', got {payment_date!r}", field="payment_date")
    try:
        moment = normalize_record_date(payment_date, conn)
    except ValidationError as exc:
        raise ValidationError(str(exc), field="payment_date") from None
    refuse_future_day(conn, local_day(moment, conn), "payment_date")
    return moment


def _clean_allocations(allocations) -> list[dict]:
    if not isinstance(allocations, (list, tuple)) or not allocations:
        raise ValidationError("allocations must list at least one purchase", field="allocations")
    cleaned, seen = [], set()
    for position, allocation in enumerate(allocations):
        purchase_id = allocation.get("purchase_id")
        if isinstance(purchase_id, bool) or not isinstance(purchase_id, int):
            raise ValidationError(f"purchase_id must be an integer, got {purchase_id!r}", field=f"allocations.{position}.purchase_id")
        if purchase_id in seen:
            raise ValidationError(f"Purchase {purchase_id} is listed twice", field="allocations")
        seen.add(purchase_id)
        amount = _check_amount(allocation.get("amount"), f"allocations.{position}.amount")
        cleaned.append({"purchase_id": purchase_id, "amount": amount})
    return cleaned


# ---------------------------------------------------------------- reads


def not_found(purchase_id: int) -> NotFoundError:
    return NotFoundError(
        f"Purchase #{purchase_id} does not exist",
        code=ErrorCode.PURCHASE_NOT_FOUND,
        details={"purchase_id": purchase_id},
    )


def _purchase(conn: sqlite3.Connection, purchase_id: int) -> dict:
    row = conn.execute(
        f"SELECT id, supplier_id, purchase_date, status, {total_sql()} AS total, {paid_sql()} AS paid "
        f"FROM purchase_invoices WHERE id = ?",
        (purchase_id,),
    ).fetchone()
    if row is None:
        raise not_found(purchase_id)
    purchase = dict(row)
    # a cancelled purchase owes nothing (it has no allocations either)
    purchase["outstanding"] = purchase["total"] - purchase["paid"] if purchase["status"] == ACTIVE else 0
    return purchase


def open_purchases(conn: sqlite3.Connection, supplier_id: int | None) -> list[dict]:
    """ACTIVE purchase invoices of the supplier (None: purchases with no supplier) that still owe something, oldest
    first (purchase_date, then id), each with its item names."""
    rows = []
    for row in conn.execute(
        f"""
        SELECT id AS purchase_id, invoice_number, purchase_date, {total_sql()} AS total, {paid_sql()} AS paid
        FROM purchase_invoices
        WHERE supplier_id IS ? AND status = 'ACTIVE'
        ORDER BY purchase_date, id
        """,
        (supplier_id,),
    ):
        purchase = dict(row)
        if purchase["paid"] < purchase["total"]:
            rows.append({**with_payment_figures(purchase), "item_names": item_names(conn, purchase["purchase_id"])})
    return rows


def allocate_oldest_first(conn: sqlite3.Connection, supplier_id: int | None, amount: int) -> list[dict]:
    """Split `amount` over the supplier's open purchases, oldest first, each up to what it still owes. An amount above
    everything owed is SUPPLIER_PAYMENT_EXCEEDS_BALANCE (no advances)."""
    _check_amount(amount, "amount")
    _check_supplier(conn, supplier_id)
    purchases = open_purchases(conn, supplier_id)
    owed = sum(p["outstanding"] for p in purchases)
    if amount > owed:
        raise ConflictError(
            f"The payment ({amount}) is more than everything owed to this supplier ({owed})",
            code=ErrorCode.SUPPLIER_PAYMENT_EXCEEDS_BALANCE,
            details={"supplier_id": supplier_id, "outstanding": owed},
        )
    allocations, left = [], amount
    for purchase in purchases:
        if left == 0:
            break
        share = min(left, purchase["outstanding"])
        allocations.append({"purchase_id": purchase["purchase_id"], "amount": share})
        left -= share
    return allocations


def _allocation_rows(conn: sqlite3.Connection, payment_id: int) -> list[dict]:
    rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT spa.id, spa.purchase_invoice_id AS purchase_id, spa.amount, pi.invoice_number, pi.purchase_date
            FROM supplier_payment_allocations AS spa
            JOIN purchase_invoices AS pi ON pi.id = spa.purchase_invoice_id
            WHERE spa.payment_id = ?
            ORDER BY pi.purchase_date, spa.id
            """,
            (payment_id,),
        )
    ]
    for row in rows:
        row["item_names"] = item_names(conn, row["purchase_id"])
    return rows


_PAYMENT_SQL = """
    SELECT supplier_payments.*, suppliers.name AS supplier_name
    FROM supplier_payments LEFT JOIN suppliers ON suppliers.id = supplier_payments.supplier_id
"""


def get_supplier_payment(conn: sqlite3.Connection, payment_id: int) -> dict:
    row = conn.execute(f"{_PAYMENT_SQL} WHERE supplier_payments.id = ?", (payment_id,)).fetchone()
    if row is None:
        raise NotFoundError(
            f"Supplier payment #{payment_id} does not exist",
            code=ErrorCode.SUPPLIER_PAYMENT_NOT_FOUND,
            details={"payment_id": payment_id},
        )
    return {**dict(row), "allocations": _allocation_rows(conn, payment_id)}


def list_supplier_payments(
    conn: sqlite3.Connection,
    supplier_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Newest first, each with its allocations. Dates are local calendar days on payment_date (section 1)."""
    query = f"{_PAYMENT_SQL} WHERE 1=1"
    params: list = []
    if supplier_id is not None:
        query += " AND supplier_payments.supplier_id = ?"
        params.append(supplier_id)
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND supplier_payments.payment_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND supplier_payments.payment_date < ?"
        params.append(end_exclusive_utc)
    query += " ORDER BY supplier_payments.payment_date DESC, supplier_payments.id DESC"
    return [{**dict(r), "allocations": _allocation_rows(conn, r["id"])} for r in conn.execute(query, params).fetchall()]


def purchase_payments(conn: sqlite3.Connection, purchase_id: int) -> list[dict]:
    """The payments that paid this purchase invoice: each payment's date, method, reference and note, the amount
    allocated to this purchase and the payment's whole amount; oldest first."""
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT sp.id AS payment_id, sp.payment_date, sp.method, sp.reference, sp.note,
                   spa.amount AS amount, sp.amount AS payment_amount
            FROM supplier_payment_allocations AS spa JOIN supplier_payments AS sp ON sp.id = spa.payment_id
            WHERE spa.purchase_invoice_id = ?
            ORDER BY sp.payment_date, sp.id
            """,
            (purchase_id,),
        )
    ]


def get_payables(conn: sqlite3.Connection) -> dict:
    """{outstanding_total, suppliers}: one row per supplier that is still owed something (supplier_id None: purchases
    with no supplier), largest debt first, with all-time purchases_total and paid_total over its ACTIVE purchases, the
    outstanding, the oldest unpaid purchase_date and its open purchases (oldest first)."""
    suppliers = []
    keys = [r[0] for r in conn.execute("SELECT DISTINCT supplier_id FROM purchase_invoices WHERE status = 'ACTIVE'")]
    for supplier_id in keys:
        purchases = open_purchases(conn, supplier_id)
        if not purchases:
            continue
        row = conn.execute(
            f"SELECT COALESCE(SUM({total_sql()}), 0) AS total, COALESCE(SUM({paid_sql()}), 0) AS paid "
            f"FROM purchase_invoices WHERE supplier_id IS ? AND status = 'ACTIVE'",
            (supplier_id,),
        ).fetchone()
        totals = {"purchases_total": row["total"], "paid_total": row["paid"]}
        name = conn.execute("SELECT name FROM suppliers WHERE id = ?", (supplier_id,)).fetchone() if supplier_id else None
        suppliers.append({
            "supplier_id": supplier_id,
            "supplier_name": name["name"] if name else None,
            **totals,
            "outstanding": sum(p["outstanding"] for p in purchases),
            "oldest_unpaid_date": purchases[0]["purchase_date"],
            "open_purchases": purchases,
        })
    suppliers.sort(key=lambda s: (-s["outstanding"], s["supplier_name"] or "", s["supplier_id"] or 0))
    return {"outstanding_total": sum(s["outstanding"] for s in suppliers), "suppliers": suppliers}


def payables_outstanding(conn: sqlite3.Connection) -> int:
    """Everything owed to suppliers now: Σ (total − paid) over ACTIVE purchase invoices."""
    return conn.execute(
        f"SELECT COALESCE(SUM({total_sql()} - {paid_sql()}), 0) FROM purchase_invoices WHERE status = 'ACTIVE'"
    ).fetchone()[0]


# ---------------------------------------------------------------- writes


def _refuse_before_purchase(conn: sqlite3.Connection, payment_day, purchase: dict) -> None:
    purchase_day = local_day(purchase["purchase_date"], conn)
    if payment_day < purchase_day:
        raise ValidationError(
            f"The payment day {payment_day} is before the day of purchase #{purchase['id']} ({purchase_day})",
            field="payment_date",
            code=ErrorCode.SUPPLIER_PAYMENT_BEFORE_PURCHASE,
            details={"purchase_id": purchase["id"], "purchase_date": purchase_day.isoformat()},
        )


def _write_allocations(conn: sqlite3.Connection, payment_id: int, supplier_id: int | None, payment_day, allocations: list[dict]) -> None:
    """Check each allocation against its purchase (inside the caller's transaction, so the outstanding is current) and
    write it; afterwards no purchase may hold more than its total (the guard against a concurrent payment)."""
    for allocation in allocations:
        purchase_id = allocation["purchase_id"]
        purchase = _purchase(conn, purchase_id)
        if purchase["supplier_id"] != supplier_id:
            raise ValidationError(
                f"Purchase #{purchase_id} belongs to another supplier",
                field="allocations",
                code=ErrorCode.SUPPLIER_PAYMENT_SUPPLIER_MISMATCH,
                details={"purchase_id": purchase_id, "supplier_id": purchase["supplier_id"]},
            )
        _refuse_before_purchase(conn, payment_day, purchase)
        if allocation["amount"] > purchase["outstanding"]:
            raise ConflictError(
                f"{allocation['amount']} is more than purchase #{purchase_id} still owes ({purchase['outstanding']})",
                code=ErrorCode.SUPPLIER_PAYMENT_EXCEEDS_DUE,
                details={"purchase_id": purchase_id, "outstanding": purchase["outstanding"]},
            )
        conn.execute(
            "INSERT INTO supplier_payment_allocations (payment_id, purchase_invoice_id, amount) VALUES (?, ?, ?)",
            (payment_id, purchase_id, allocation["amount"]),
        )
    for allocation in allocations:
        purchase = _purchase(conn, allocation["purchase_id"])
        if purchase["paid"] > purchase["total"]:
            raise ConflictError(
                "This purchase was paid meanwhile; reload and try again.",
                code=ErrorCode.SUPPLIER_PAYMENT_EXCEEDS_DUE,
                details={"purchase_id": purchase["id"], "outstanding": 0},
            )


@audited()
def record_supplier_payment(
    conn: sqlite3.Connection,
    supplier_id: int | None,
    payment_date: str,
    amount: int,
    method: str,
    reference: str | None = None,
    note: str | None = None,
    allocations: list[dict] | None = None,
) -> int:
    """Record money paid to a supplier and allocate it: to the `allocations` given ({purchase_id, amount}, a purchase
    invoice each, adding up to `amount` exactly), or oldest first when None. Returns the payment id."""
    _check_amount(amount, "amount")
    _check_method(method)
    _check_supplier(conn, supplier_id)
    moment = _payment_moment(conn, payment_date)
    if allocations is not None:
        allocations = _clean_allocations(allocations)
        allocated = sum(a["amount"] for a in allocations)
        if allocated != amount:
            raise ValidationError(
                f"The allocations add up to {allocated}, not the payment's {amount}",
                field="allocations",
                code=ErrorCode.SUPPLIER_PAYMENT_ALLOCATION_MISMATCH,
                details={"amount": amount, "allocated": allocated},
            )
    with transaction(conn):
        if allocations is None:
            allocations = allocate_oldest_first(conn, supplier_id, amount)
        cursor = conn.execute(
            "INSERT INTO supplier_payments (supplier_id, payment_date, amount, method, reference, note) VALUES (?, ?, ?, ?, ?, ?)",
            (supplier_id, moment, amount, method, reference, note),
        )
        payment_id = cursor.lastrowid
        _write_allocations(conn, payment_id, supplier_id, local_day(moment, conn), allocations)
    return payment_id


def check_purchase_payment(payment: dict | None, supplier_id: int | None, total: int) -> dict | None:
    """Validate the purchase form's payment ({mode, amount, method, reference}; None = FULL) before anything is written.
    Returns {amount, method, reference} for the payment to record, or None when none is (NONE, or a total of 0)."""
    payment = dict(payment or {})
    mode = payment.get("mode", "FULL")
    if mode not in PAYMENT_MODES:
        raise ValidationError(f"payment.mode must be one of {', '.join(PAYMENT_MODES)}, got {mode!r}", field="payment.mode")
    method = payment.get("method") or "OTHER"
    if method not in METHODS:
        raise ValidationError(f"payment.method must be one of {', '.join(METHODS)}, got {method!r}", field="payment.method")
    if mode != "FULL" and supplier_id is None:
        raise ValidationError(
            "A purchase that is not paid in full needs a supplier", field="supplier_id",
            code=ErrorCode.SUPPLIER_REQUIRED_FOR_CREDIT,
        )
    if mode == "PARTIAL":
        amount = payment.get("amount")
        _check_amount(amount, "payment.amount")
        if amount >= total:
            raise ValidationError(
                f"A partial payment must be less than the invoice total ({total}); choose FULL to pay it all",
                field="payment.amount",
            )
    elif payment.get("amount") is not None:
        raise ValidationError("payment.amount is only given with mode PARTIAL", field="payment.amount")
    else:
        amount = total if mode == "FULL" else 0
    if amount == 0:
        return None
    return {"amount": amount, "method": method, "reference": payment.get("reference")}


@audited()
def record_purchase_payment(conn: sqlite3.Connection, purchase_id: int, payment: dict | None) -> None:
    """The payment made with a purchase invoice (`check_purchase_payment`'s result), dated with the purchase and
    allocated to it. Runs inside the purchase's own transaction, and joins its audit operation."""
    if payment is None:
        return
    purchase = _purchase(conn, purchase_id)
    cursor = conn.execute(
        "INSERT INTO supplier_payments (supplier_id, payment_date, amount, method, reference) VALUES (?, ?, ?, ?, ?)",
        (purchase["supplier_id"], purchase["purchase_date"], payment["amount"], payment["method"], payment["reference"]),
    )
    _write_allocations(
        conn, cursor.lastrowid, purchase["supplier_id"], local_day(purchase["purchase_date"], conn),
        [{"purchase_id": purchase_id, "amount": payment["amount"]}],
    )


@audited()
def update_supplier_payment(conn: sqlite3.Connection, payment_id: int, **fields) -> None:
    """Correct the date, method, reference or note. The amount and the allocations never change: delete the payment
    and record it again instead. A new date is re-checked (not in the future, not before a purchase it pays); the same
    local day keeps the stored time."""
    old = get_supplier_payment(conn, payment_id)
    for name in fields:
        if name not in UPDATABLE_FIELDS:
            raise ValidationError(f"Unknown field '{name}'", field=name)
    changes: dict = {}
    if "method" in fields:
        changes["method"] = _check_method(fields["method"])
    for name in ("reference", "note"):
        if name in fields:
            changes[name] = fields[name]
    if "payment_date" in fields:
        moment = _payment_moment(conn, fields["payment_date"])
        day = local_day(moment, conn)
        if day != local_day(old["payment_date"], conn):
            for allocation in old["allocations"]:
                _refuse_before_purchase(conn, day, _purchase(conn, allocation["purchase_id"]))
            changes["payment_date"] = moment
    if not changes:
        return
    with transaction(conn):
        conn.execute(
            f"UPDATE supplier_payments SET {', '.join(f'{name} = ?' for name in changes)} WHERE id = ?",
            [*changes.values(), payment_id],
        )


@audited()
def delete_supplier_payment(conn: sqlite3.Connection, payment_id: int) -> None:
    """Remove a payment entered by mistake, with its allocations; the audit log keeps every row."""
    get_supplier_payment(conn, payment_id)
    with transaction(conn):
        conn.execute("DELETE FROM supplier_payments WHERE id = ?", (payment_id,))
