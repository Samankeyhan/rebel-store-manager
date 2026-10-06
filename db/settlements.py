"""Settlements: the owner confirming that a payment method paid out money.

Every paid order with a payment method is pending until the owner records a
settlement that includes it; nothing is settled automatically, whatever the
method's rule. IMMEDIATE and DAYS_AFTER methods settle any chosen set of
pending orders; a DAY_OF_NEXT_MONTH method pays one amount per Jalali month,
so it settles a whole month at once.

An order's expected amount is customer_total - transaction_fee (it may be
negative). expected_amount is frozen on the settlement when it is recorded;
the difference to amount_received is computed on read, never stored.
"""

import sqlite3
from datetime import date

from db import jalali
from db.connection import transaction
from db.errors import ConflictError, NotFoundError, ValidationError
from db.payment_methods import PAID_STATUSES, compute_expected_settlement_date, get_payment_method
from db.timeutil import parse_calendar_date, today_local

MONTHLY_RULE = "DAY_OF_NEXT_MONTH"

UPDATABLE_FIELDS = ("amount_received", "settled_date", "note")

# The same customer_total formula as db/orders.py::list_orders.
_CUSTOMER_TOTAL_SQL = """
    (SELECT COALESCE(SUM(order_items.list_price - order_items.discount_amount), 0)
     FROM order_items WHERE order_items.order_id = orders.id)
    + orders.shipping_charge
"""

_ORDER_COLUMNS_SQL = f"""
    orders.id, orders.invoice_number, orders.order_date, orders.paid_date,
    orders.customer_name, orders.channel, orders.status, orders.payment_method_id,
    orders.expected_settlement_date, orders.paid_jalali_year, orders.paid_jalali_month,
    orders.settlement_id, orders.transaction_fee,
    {_CUSTOMER_TOTAL_SQL} AS customer_total
"""

_PENDING_ORDER_KEYS = (
    "id", "invoice_number", "order_date", "paid_date", "customer_name", "channel",
    "customer_total", "transaction_fee", "expected_amount", "expected_settlement_date",
)

_SETTLED_ORDER_KEYS = (
    "id", "invoice_number", "order_date", "paid_date", "customer_name", "channel",
    "status", "customer_total", "transaction_fee", "expected_amount",
)


def _with_expected(row: sqlite3.Row) -> dict:
    order = dict(row)
    order["expected_amount"] = order["customer_total"] - order["transaction_fee"]
    return order


def _pick(order: dict, keys: tuple) -> dict:
    return {key: order[key] for key in keys}


def _sums(orders: list[dict]) -> dict:
    return {
        "order_count": len(orders),
        "customer_total_sum": sum(o["customer_total"] for o in orders),
        "fee_sum": sum(o["transaction_fee"] for o in orders),
        "expected_amount": sum(o["expected_amount"] for o in orders),
    }


def _paid_placeholders() -> str:
    return ", ".join("?" for _ in PAID_STATUSES)


# ---------------------------------------------------------------- pending

def _pending_orders(conn: sqlite3.Connection, payment_method_id: int | None) -> list[dict]:
    query = f"""
        SELECT {_ORDER_COLUMNS_SQL}
        FROM orders
        WHERE orders.payment_method_id IS NOT NULL
          AND orders.status IN ({_paid_placeholders()})
          AND orders.settlement_id IS NULL
    """
    params: list = list(PAID_STATUSES)
    if payment_method_id is not None:
        query += " AND orders.payment_method_id = ?"
        params.append(payment_method_id)
    query += " ORDER BY orders.paid_date, orders.id"
    return [_with_expected(row) for row in conn.execute(query, params).fetchall()]


def _date_groups(orders: list[dict], today: date) -> list[dict]:
    by_date: dict[str, list[dict]] = {}
    for order in orders:
        by_date.setdefault(order["expected_settlement_date"], []).append(order)

    groups = []
    for expected_text in sorted(by_date):
        expected = parse_calendar_date(expected_text)
        members = by_date[expected_text]
        groups.append(
            {
                "expected_date": expected_text,
                "due": expected <= today,
                "overdue": expected < today,
                **_sums(members),
                "orders": [_pick(o, _PENDING_ORDER_KEYS) for o in members],
            }
        )
    return groups


def _month_groups(orders: list[dict], method: dict, today: date) -> list[dict]:
    by_month: dict[tuple[int, int], list[dict]] = {}
    for order in orders:
        key = (order["paid_jalali_year"], order["paid_jalali_month"])
        by_month.setdefault(key, []).append(order)

    groups = []
    for jy, jm in sorted(by_month):
        first_day, last_day = jalali.month_range(jy, jm)
        expected = compute_expected_settlement_date(first_day, method)
        members = by_month[(jy, jm)]
        month_ended = last_day < today
        groups.append(
            {
                "jalali_year": jy,
                "jalali_month": jm,
                "month_first_day": first_day.isoformat(),
                "month_last_day": last_day.isoformat(),
                "expected_date": expected.isoformat(),
                "month_ended": month_ended,
                "can_settle": month_ended,
                "due": expected <= today,
                "overdue": expected < today,
                **_sums(members),
                "orders": [_pick(o, _PENDING_ORDER_KEYS) for o in members],
            }
        )
    return groups


def get_pending(
    conn: sqlite3.Connection,
    payment_method_id: int | None = None,
    today: date | None = None,
) -> list[dict]:
    """One entry per method (inactive ones included) that has paid orders not
    yet in a settlement, grouped by expected date, or by Jalali month for
    DAY_OF_NEXT_MONTH. Methods ordered by name, groups oldest first."""
    if today is None:
        today = today_local(conn)
    if payment_method_id is not None:
        get_payment_method(conn, payment_method_id)  # raises NotFoundError if missing

    by_method: dict[int, list[dict]] = {}
    for order in _pending_orders(conn, payment_method_id):
        by_method.setdefault(order["payment_method_id"], []).append(order)

    methods = [get_payment_method(conn, method_id) for method_id in by_method]
    methods.sort(key=lambda m: (m["name"], m["id"]))

    result = []
    for method in methods:
        orders = by_method[method["id"]]
        if method["settlement_rule"] == MONTHLY_RULE:
            groups = _month_groups(orders, method, today)
        else:
            groups = _date_groups(orders, today)
        result.append(
            {
                "payment_method_id": method["id"],
                "name": method["name"],
                "settlement_rule": method["settlement_rule"],
                "settlement_days": method["settlement_days"],
                "is_active": method["is_active"],
                "total_expected": sum(o["expected_amount"] for o in orders),
                "groups": groups,
            }
        )
    return result


# ---------------------------------------------------------------- validation

def _validate_amount_received(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            f"amount_received must be an integer, got {value!r}", field="amount_received"
        )
    if value < 0:
        raise ValidationError(
            f"amount_received must be >= 0, got {value}", field="amount_received"
        )
    return value


def _validate_settled_date(conn: sqlite3.Connection, value) -> date:
    if not isinstance(value, str):
        raise ValidationError(
            f"settled_date must be a 'YYYY-MM-DD' string, got {value!r}",
            field="settled_date",
        )
    try:
        settled = parse_calendar_date(value)
    except ValidationError as exc:
        raise ValidationError(str(exc), field="settled_date") from None
    today = today_local(conn)
    if settled > today:
        raise ValidationError(
            f"settled_date {settled.isoformat()} is in the future (today is "
            f"{today.isoformat()})",
            field="settled_date",
        )
    return settled


def _check_after_month(settled: date, jy: int, jm: int) -> None:
    _, last_day = jalali.month_range(jy, jm)
    if settled <= last_day:
        raise ValidationError(
            f"settled_date {settled.isoformat()} must be after the end of month "
            f"{jy}/{jm:02d} ({last_day.isoformat()})",
            field="settled_date",
        )


def _check_not_before_paid(settled: date, latest_paid: str | None) -> None:
    if latest_paid is not None and settled < parse_calendar_date(latest_paid):
        raise ValidationError(
            f"settled_date {settled.isoformat()} is before the latest paid date "
            f"of its orders ({latest_paid})",
            field="settled_date",
        )


def _validate_jalali_month(jalali_year, jalali_month) -> tuple[int, int]:
    if jalali_year is None:
        raise ValidationError(
            "jalali_year is required for a method that settles whole months",
            field="jalali_year",
        )
    if jalali_month is None:
        raise ValidationError(
            "jalali_month is required for a method that settles whole months",
            field="jalali_month",
        )
    if isinstance(jalali_month, bool) or not isinstance(jalali_month, int) or not 1 <= jalali_month <= 12:
        raise ValidationError(
            f"jalali_month must be between 1 and 12, got {jalali_month!r}",
            field="jalali_month",
        )
    if isinstance(jalali_year, bool) or not isinstance(jalali_year, int):
        raise ValidationError(
            f"jalali_year must be an integer, got {jalali_year!r}", field="jalali_year"
        )
    try:
        jalali.month_range(jalali_year, jalali_month)
    except ValueError as exc:
        raise ValidationError(str(exc), field="jalali_year") from None
    return jalali_year, jalali_month


# ---------------------------------------------------------------- record

def _orders_for_subset(
    conn: sqlite3.Connection, method: dict, order_ids, settled: date
) -> list[dict]:
    if not isinstance(order_ids, (list, tuple)) or not order_ids:
        raise ValidationError(
            "order_ids is required: choose at least one pending order to settle",
            field="order_ids",
        )
    if len(set(order_ids)) != len(order_ids):
        raise ValidationError("order_ids contains duplicates", field="order_ids")

    placeholders = ", ".join("?" for _ in order_ids)
    rows = conn.execute(
        f"SELECT {_ORDER_COLUMNS_SQL} FROM orders WHERE orders.id IN ({placeholders})",
        list(order_ids),
    ).fetchall()
    found = {row["id"]: _with_expected(row) for row in rows}

    orders = []
    for order_id in order_ids:
        order = found.get(order_id)
        if order is None:
            raise ValidationError(f"Order #{order_id} does not exist", field="order_ids")
        if order["payment_method_id"] != method["id"]:
            raise ValidationError(
                f"Order #{order_id} was not paid with '{method['name']}'",
                field="order_ids",
            )
        if order["status"] not in PAID_STATUSES:
            raise ConflictError(
                f"Order #{order_id} is {order['status']}, not paid; it cannot be settled."
            )
        if order["settlement_id"] is not None:
            raise ConflictError(
                f"Order #{order_id} is already in settlement #{order['settlement_id']}."
            )
        orders.append(order)

    _check_not_before_paid(settled, max(o["paid_date"] for o in orders))
    return orders


def _orders_for_month(
    conn: sqlite3.Connection, method: dict, jy: int, jm: int, settled: date
) -> list[dict]:
    _, last_day = jalali.month_range(jy, jm)
    today = today_local(conn)
    if not last_day < today:
        raise ConflictError(
            f"Month {jy}/{jm:02d} has not ended yet (it ends {last_day.isoformat()}); "
            f"'{method['name']}' settles whole months only."
        )
    _check_after_month(settled, jy, jm)

    existing = conn.execute(
        """
        SELECT id FROM settlements
        WHERE payment_method_id = ? AND jalali_year = ? AND jalali_month = ?
        """,
        (method["id"], jy, jm),
    ).fetchone()
    if existing is not None:
        raise ConflictError(
            f"{method['name']}'s month {jy}/{jm:02d} is already settled "
            f"(settlement #{existing['id']})."
        )

    rows = conn.execute(
        f"""
        SELECT {_ORDER_COLUMNS_SQL}
        FROM orders
        WHERE orders.payment_method_id = ?
          AND orders.status IN ({_paid_placeholders()})
          AND orders.settlement_id IS NULL
          AND orders.paid_jalali_year = ?
          AND orders.paid_jalali_month = ?
        ORDER BY orders.paid_date, orders.id
        """,
        (method["id"], *PAID_STATUSES, jy, jm),
    ).fetchall()
    if not rows:
        raise ConflictError(
            f"Nothing to settle: '{method['name']}' has no pending paid orders "
            f"in {jy}/{jm:02d}."
        )
    return [_with_expected(row) for row in rows]


def record_settlement(
    conn: sqlite3.Connection,
    payment_method_id: int,
    settled_date: str,
    amount_received: int,
    note: str | None = None,
    order_ids: list[int] | None = None,
    jalali_year: int | None = None,
    jalali_month: int | None = None,
) -> int:
    """Record a payout. IMMEDIATE / DAYS_AFTER: the chosen order_ids.
    DAY_OF_NEXT_MONTH: every pending order of jalali_year/jalali_month, after
    that month has ended. An inactive method may still settle."""
    method = get_payment_method(conn, payment_method_id)  # raises NotFoundError
    _validate_amount_received(amount_received)
    settled = _validate_settled_date(conn, settled_date)
    monthly = method["settlement_rule"] == MONTHLY_RULE

    if monthly:
        if order_ids is not None:
            raise ValidationError(
                f"'{method['name']}' settles whole months only; give jalali_year "
                f"and jalali_month, not order_ids",
                field="order_ids",
            )
        jy, jm = _validate_jalali_month(jalali_year, jalali_month)
    else:
        for name, value in (("jalali_year", jalali_year), ("jalali_month", jalali_month)):
            if value is not None:
                raise ValidationError(
                    f"{name} applies only to a method that settles whole months; "
                    f"'{method['name']}' settles chosen orders",
                    field=name,
                )
        jy = jm = None

    try:
        with transaction(conn):
            if monthly:
                orders = _orders_for_month(conn, method, jy, jm, settled)
            else:
                orders = _orders_for_subset(conn, method, order_ids, settled)
            expected_amount = sum(o["expected_amount"] for o in orders)

            cursor = conn.execute(
                """
                INSERT INTO settlements
                    (payment_method_id, settled_date, jalali_year, jalali_month,
                     expected_amount, amount_received, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    method["id"], settled.isoformat(), jy, jm,
                    expected_amount, amount_received, note,
                ),
            )
            settlement_id = cursor.lastrowid

            ids = [o["id"] for o in orders]
            placeholders = ", ".join("?" for _ in ids)
            updated = conn.execute(
                f"""
                UPDATE orders SET settlement_id = ?
                WHERE id IN ({placeholders}) AND settlement_id IS NULL
                """,
                [settlement_id, *ids],
            ).rowcount
            if updated != len(ids):
                raise ConflictError(
                    "Some of these orders were settled meanwhile; reload and try again."
                )
    except sqlite3.IntegrityError:
        raise ConflictError(
            f"{method['name']}'s month {jy}/{jm:02d} is already settled."
        ) from None
    return settlement_id


# ---------------------------------------------------------------- read

def _fetch_settlement(conn: sqlite3.Connection, settlement_id: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT settlements.*,
               payment_methods.name AS payment_method_name,
               payment_methods.settlement_rule
        FROM settlements
        JOIN payment_methods ON payment_methods.id = settlements.payment_method_id
        WHERE settlements.id = ?
        """,
        (settlement_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError(f"Settlement with id {settlement_id} does not exist")
    return row


def _settlement_orders(conn: sqlite3.Connection, settlement_id: int) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT {_ORDER_COLUMNS_SQL}
        FROM orders
        WHERE orders.settlement_id = ?
        ORDER BY orders.paid_date, orders.id
        """,
        (settlement_id,),
    ).fetchall()
    return [_with_expected(row) for row in rows]


def get_settlement(conn: sqlite3.Connection, settlement_id: int) -> dict:
    settlement = dict(_fetch_settlement(conn, settlement_id))
    settlement["difference"] = settlement["amount_received"] - settlement["expected_amount"]
    settlement["orders"] = [
        _pick(o, _SETTLED_ORDER_KEYS) for o in _settlement_orders(conn, settlement_id)
    ]
    return settlement


def _validate_filter_date(value: str, field_name: str) -> str:
    try:
        return parse_calendar_date(value).isoformat()
    except ValidationError as exc:
        raise ValidationError(str(exc), field=field_name) from None


def list_settlements(
    conn: sqlite3.Connection,
    payment_method_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Newest first. start_date/end_date are inclusive local calendar days on settled_date."""
    query = """
        SELECT settlements.*,
               payment_methods.name AS payment_method_name,
               payment_methods.settlement_rule,
               settlements.amount_received - settlements.expected_amount AS difference,
               (SELECT COUNT(*) FROM orders WHERE orders.settlement_id = settlements.id)
                   AS order_count
        FROM settlements
        JOIN payment_methods ON payment_methods.id = settlements.payment_method_id
        WHERE 1=1
    """
    params: list = []
    if payment_method_id is not None:
        query += " AND settlements.payment_method_id = ?"
        params.append(payment_method_id)
    if start_date is not None:
        query += " AND settlements.settled_date >= ?"
        params.append(_validate_filter_date(start_date, "start_date"))
    if end_date is not None:
        query += " AND settlements.settled_date <= ?"
        params.append(_validate_filter_date(end_date, "end_date"))
    query += " ORDER BY settlements.settled_date DESC, settlements.id DESC"
    return [dict(row) for row in conn.execute(query, params).fetchall()]


# ---------------------------------------------------------------- update

def update_settlement(conn: sqlite3.Connection, settlement_id: int, **fields) -> None:
    """Correct amount_received, settled_date or note. Which orders a settlement
    holds, and its expected_amount, never change."""
    settlement = _fetch_settlement(conn, settlement_id)  # raises NotFoundError

    for field_name in fields:
        if field_name not in UPDATABLE_FIELDS:
            raise ValidationError(f"Unknown field '{field_name}'", field=field_name)
    if not fields:
        return

    if "amount_received" in fields:
        _validate_amount_received(fields["amount_received"])

    if "settled_date" in fields:
        settled = _validate_settled_date(conn, fields["settled_date"])
        # A monthly settlement is identified by its stored month, not by the
        # method's current rule (the rule may change once nothing is pending).
        if settlement["jalali_month"] is not None:
            _check_after_month(settled, settlement["jalali_year"], settlement["jalali_month"])
        else:
            latest_paid = conn.execute(
                "SELECT MAX(paid_date) FROM orders WHERE settlement_id = ?",
                (settlement_id,),
            ).fetchone()[0]
            _check_not_before_paid(settled, latest_paid)
        fields["settled_date"] = settled.isoformat()

    assignments = ", ".join(f"{name} = ?" for name in fields)
    with transaction(conn):
        conn.execute(
            f"UPDATE settlements SET {assignments} WHERE id = ?",
            [*fields.values(), settlement_id],
        )
