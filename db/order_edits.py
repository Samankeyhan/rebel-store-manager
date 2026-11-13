"""Light order edit («ویرایش سفارش», docs/accounting-rules.md section 20, "Light edit"): a few fields of an order
change in place, without a void and a new sale. Items, quantities, prices, discounts and the packaging kit are never
edited here; they stay with `order_voids.correct_order`. No stock movement, item cost or settlement row is written.

Fields (`EDITABLE_FIELDS`):
- money/date: order_date (a local day; the stored local time of day is kept), payment_method_id (active, never None),
  transaction_fee (only with payment_method_id or shipping_charge: keeps a hand fee), paid_date, shipping_charge,
  postage_cost. A method or shipping change recomputes the fee from the method's current rule unless
  transaction_fee is given; a method or paid_date change on a paid order recomputes expected_settlement_date and
  the paid Jalali month (`orders._paid_fields`). A paid order with no paid_date (a legacy order) that gets a
  method takes the local day of its order_date, as `record_order` does.
- text: payment_reference, customer_name, notes (stripped; blank = None).

Refused (conflicts, in this order; `plan_order_edit` lists them all as `blockers`):
- ORDER_ALREADY_VOIDED: any field of a VOIDED order.
- ORDER_EDIT_NOT_ALLOWED: a money/date field of an order that is not PENDING/PAID/COMPLETED and committed
  (DRAFT, CANCELLED, REFUNDED).
- ORDER_NOT_PAID: paid_date on an order that is not PAID/COMPLETED.
- ORDER_ALREADY_SETTLED: a money/date field of a settled order, except postage_cost (it is not in the settlement).
- PERIOD_ALREADY_DISTRIBUTED: a money/date field when the order's old or new local day is closed (section 11).
- MONTH_ALREADY_SETTLED: a new paid day or method lands in a month its DAY_OF_NEXT_MONTH method already settled.
Input errors (an unknown field, a wrong type, a negative amount, DATE_IN_FUTURE, PAYMENT_METHOD_REQUIRED,
PAYMENT_METHOD_INACTIVE) are raised at once, by the preview too. A value equal to the stored one is no change.
`edit_order` is one audited operation (one op_id; the triggers log each changed column before and after)."""

import sqlite3
from datetime import date

from db.audit import audited
from db.connection import transaction
from db.costing import check_money
from db.errors import AppError, ConflictError, ErrorCode, NotFoundError, ValidationError
from db.orders import (
    REVENUE_ELIGIBLE_STATUSES,
    VOIDED,
    _check_month_open,
    _fetch_order_items,
    _paid_fields,
    _parse_paid_date,
    compute_order_profit,
    compute_order_revenue,
    replaced_by_order_id,
)
from db.payment_methods import PAID_STATUSES, compute_fee, get_payment_method
from db.period_lock import refuse_closed_day
from db.timeutil import local_day, move_to_local_day, parse_calendar_date, refuse_future_day

TEXT_FIELDS = ("payment_reference", "customer_name", "notes")
MONEY_DATE_FIELDS = (
    "order_date", "payment_method_id", "transaction_fee", "paid_date", "shipping_charge", "postage_cost",
)
EDITABLE_FIELDS = (
    "order_date", "payment_method_id", "transaction_fee", "payment_reference", "paid_date",
    "shipping_charge", "postage_cost", "customer_name", "notes",
)
# Money/date fields a settled order may still change: they are not part of the settlement.
SETTLED_EDITABLE = ("postage_cost",)
MAX_TEXT_LENGTH = 500
# A changed column -> the field it is reported under.
_COLUMN_FIELD = {"expected_settlement_date": "paid_date", "paid_jalali_year": "paid_date", "paid_jalali_month": "paid_date"}


def _order_row(conn: sqlite3.Connection, order_id: int) -> sqlite3.Row:
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise NotFoundError(f"Order with id {order_id} does not exist")
    return order


# ----------------------------------------------------------------- input


def _int(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field} must be an integer", field=field)
    return value


def _amount(value, field: str) -> int:
    check_money(_int(value, field), field)
    if value < 0:
        raise ValidationError(f"{field} must be >= 0, got {value}", field=field)
    return value


def _text(value, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text", field=field)
    text = value.strip()
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"{field} must be at most {MAX_TEXT_LENGTH} characters", field=field)
    return text or None


def _day(conn: sqlite3.Connection, value, field: str) -> date:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a 'YYYY-MM-DD' day", field=field)
    try:
        day = parse_calendar_date(value)
    except ValidationError as exc:
        raise ValidationError(str(exc), field=field) from None
    refuse_future_day(conn, day, field)
    return day


def _clean(conn: sqlite3.Connection, changes: dict) -> dict:
    """The requested values, checked one by one (an input error raises)."""
    unknown = [key for key in changes if key not in EDITABLE_FIELDS]
    if unknown:
        raise ValidationError(f"Cannot edit: {', '.join(unknown)}", field=unknown[0])
    if not changes:
        raise ValidationError("Nothing to edit", field="order")
    if "transaction_fee" in changes and not {"payment_method_id", "shipping_charge"} & changes.keys():
        raise ValidationError(
            "transaction_fee is only edited with payment_method_id or shipping_charge", field="transaction_fee"
        )
    clean: dict = {}
    for key, value in changes.items():
        if key in TEXT_FIELDS:
            clean[key] = _text(value, key)
        elif key in ("shipping_charge", "postage_cost", "transaction_fee"):
            clean[key] = _amount(value, key)
        elif key == "order_date":
            clean[key] = _day(conn, value, key)
        elif key == "paid_date":
            if value is None:
                raise ValidationError("paid_date cannot be cleared", field="paid_date")
            clean[key] = _parse_paid_date(conn, value)
        elif key == "payment_method_id":
            if value is None:
                raise ValidationError(
                    "A payment method is required", field="payment_method_id", code=ErrorCode.PAYMENT_METHOD_REQUIRED
                )
            clean[key] = _int(value, key)
    return clean


# ----------------------------------------------------------------- the plan


def _plan(conn: sqlite3.Connection, order: sqlite3.Row, changes: dict) -> tuple[dict, dict, list]:
    """(new column values, the preview, the refusal checks) for the requested changes."""
    clean = _clean(conn, changes)
    old_day = local_day(order["order_date"], conn)
    columns: dict = {}

    for key in TEXT_FIELDS + ("shipping_charge", "postage_cost"):
        if key in clean and clean[key] != order[key]:
            columns[key] = clean[key]

    new_day = old_day
    if "order_date" in clean and clean["order_date"] != old_day:
        new_day = clean["order_date"]
        columns["order_date"] = move_to_local_day(order["order_date"], new_day, conn)

    old_method = get_payment_method(conn, order["payment_method_id"]) if order["payment_method_id"] else None
    method = old_method
    if "payment_method_id" in clean and clean["payment_method_id"] != order["payment_method_id"]:
        method = get_payment_method(conn, clean["payment_method_id"])
        if not method["is_active"]:
            raise ValidationError(
                f"Payment method '{method['name']}' is not active",
                field="payment_method_id",
                code=ErrorCode.PAYMENT_METHOD_INACTIVE,
                details={"payment_method_id": method["id"]},
            )
        columns["payment_method_id"] = method["id"]

    items = _fetch_order_items(conn, order["id"])
    after = {**dict(order), **columns}
    customer_total = compute_order_revenue(after, items)
    check_money(customer_total, "shipping_charge")
    if "transaction_fee" in clean:
        fee = clean["transaction_fee"]
    elif ("payment_method_id" in columns or "shipping_charge" in columns) and method is not None:
        fee = compute_fee(customer_total, method)
    else:
        fee = order["transaction_fee"]
    if fee != order["transaction_fee"]:
        columns["transaction_fee"] = fee

    paid = order["status"] in PAID_STATUSES
    paid_day = None
    if paid and ("paid_date" in clean or "payment_method_id" in columns):
        paid_day = clean.get("paid_date")
        if paid_day is None:
            paid_day = parse_calendar_date(order["paid_date"]) if order["paid_date"] else new_day
        for key, value in _paid_fields(paid_day, method).items():
            if value != order[key]:
                columns[key] = value
        if not any(key in columns for key in ("paid_date", "expected_settlement_date", "paid_jalali_year")):
            paid_day = None  # nothing of the payment moves: no month to check

    after = {**dict(order), **columns}
    requested = set(clean)
    changed = {_COLUMN_FIELD.get(column, column) for column in columns}
    money_date = [key for key in MONEY_DATE_FIELDS if key in changed]
    checks = _checks(conn, order, money_date, requested, old_day, new_day, method, paid_day)

    def _figure(before, value):
        return {"before": before, "after": value}

    preview = {
        "order_id": order["id"],
        "invoice_number": order["invoice_number"],
        "status": order["status"],
        "changes": [
            {
                "field": key,
                "before": old_day.isoformat() if key == "order_date" else order[key],
                "after": new_day.isoformat() if key == "order_date" else columns[key],
            }
            for key in EDITABLE_FIELDS
            if key in columns
        ],
        "figures": {
            "order_day": _figure(old_day.isoformat(), new_day.isoformat()),
            "customer_total": _figure(compute_order_revenue(order, items), customer_total),
            "transaction_fee": _figure(order["transaction_fee"], fee),
            "profit": _figure(compute_order_profit(order, items), compute_order_profit(after, items)),
            "expected_settlement_date": _figure(order["expected_settlement_date"], after["expected_settlement_date"]
            ),
            "paid_date": _figure(order["paid_date"], after["paid_date"]),
            "settlement_amount": _figure(_settlement_amount(order, compute_order_revenue(order, items)),
                _settlement_amount(after, customer_total),
            ),
        },
    }
    return columns, preview, checks


def _settlement_amount(order, customer_total: int) -> int | None:
    """customer_total − fee of an order pending settlement (section 14), else None."""
    if order["payment_method_id"] is None or order["status"] not in PAID_STATUSES or order["settlement_id"] is not None:
        return None
    return customer_total - order["transaction_fee"]


def _checks(conn, order, money_date: list, requested: set, old_day: date, new_day: date, method, paid_day):
    """The refusal rules, in the order they are reported."""
    def voided():
        if order["status"] == VOIDED:
            raise ConflictError(
                f"Order #{order['id']} is voided; it can no longer be edited.",
                code=ErrorCode.ORDER_ALREADY_VOIDED,
                details={
                    "order_id": order["id"],
                    "voided_at": order["voided_at"],
                    "replaced_by_order_id": replaced_by_order_id(conn, order["id"]),
                },
            )

    def status():
        committed = order["status"] in REVENUE_ELIGIBLE_STATUSES and order["stock_committed"]
        if money_date and order["status"] != VOIDED and not committed:
            raise ConflictError(
                f"Order #{order['id']} is {order['status']}: its amounts and dates cannot be edited.",
                code=ErrorCode.ORDER_EDIT_NOT_ALLOWED,
                details={"order_id": order["id"], "status": order["status"], "fields": money_date},
            )

    def not_paid():
        if "paid_date" in requested and order["status"] not in PAID_STATUSES and order["status"] != VOIDED:
            raise ConflictError(
                f"Order #{order['id']} is {order['status']}, not paid; it has no paid date to change.",
                code=ErrorCode.ORDER_NOT_PAID,
                details={"order_id": order["id"], "status": order["status"]},
            )

    def settled():
        if order["settlement_id"] is not None and any(key not in SETTLED_EDITABLE for key in money_date):
            raise ConflictError(
                f"Order #{order['id']} is part of settlement #{order['settlement_id']}; "
                f"its amounts and dates can no longer change.",
                code=ErrorCode.ORDER_ALREADY_SETTLED,
                details={"order_id": order["id"], "settlement_id": order["settlement_id"]},
            )

    def closed():
        if money_date:
            refuse_closed_day(conn, old_day)
            refuse_closed_day(conn, new_day)

    def month():
        if paid_day is not None:
            _check_month_open(conn, method, paid_day)

    return (voided, status, not_paid, settled, closed, month)


def _blocker(check) -> dict | None:
    try:
        check()
    except AppError as exc:
        return {"code": str(exc.code), "details": exc.details}
    return None


def plan_order_edit(conn: sqlite3.Connection, order_id: int, changes: dict) -> dict:
    """Read-only: what `edit_order(conn, order_id, **changes)` would change (`changes`: each changed field before
    and after; `figures`: the order day, customer total, fee, profit, expected settlement date, paid date and the
    amount pending settlement, before and after) and every rule that refuses it now (`blockers`, empty when it may be
    saved). Input errors raise, as the edit would."""
    order = _order_row(conn, order_id)
    _, preview, checks = _plan(conn, order, changes)
    preview["blockers"] = [b for b in (_blocker(check) for check in checks) if b is not None]
    return preview


@audited()
def edit_order(conn: sqlite3.Connection, order_id: int, **changes) -> None:
    """Change the given fields of the order in place (module docstring); nothing else is written. A request whose
    values all equal the stored ones writes nothing."""
    with transaction(conn):
        order = _order_row(conn, order_id)
        columns, _, checks = _plan(conn, order, changes)
        for check in checks:
            check()
        if columns:
            assignments = ", ".join(f"{name} = ?" for name in columns)
            conn.execute(f"UPDATE orders SET {assignments} WHERE id = ?", [*columns.values(), order_id])
