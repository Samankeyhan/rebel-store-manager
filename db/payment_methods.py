"""Payment methods: the fee a method charges and when it settles.

A method's fee is computed here and frozen on each order (orders.transaction_fee);
its settlement rule fixes each paid order's expected_settlement_date and,
for DAY_OF_NEXT_MONTH, the Jalali month the order is settled in.
"""

import sqlite3
from datetime import date, timedelta

from db import jalali
from db.connection import transaction
from db.errors import ConflictError, NotFoundError, ValidationError
from db.timeutil import now_utc

SETTLEMENT_RULES = ("IMMEDIATE", "DAYS_AFTER", "DAY_OF_NEXT_MONTH")

# An order counts as paid in these statuses; pending settlement while it has
# a payment method and no settlement_id.
PAID_STATUSES = ("PAID", "COMPLETED")

UPDATABLE_FIELDS = ("name", "fee_bps", "fee_fixed", "settlement_rule", "settlement_days")

_BPS_DENOMINATOR = 10000
_DAYS_RANGE = {"DAYS_AFTER": (1, 365), "DAY_OF_NEXT_MONTH": (1, 31)}


def _validate_name(name: str) -> str:
    stripped = name.strip() if name is not None else ""
    if not stripped:
        raise ValidationError("name is required and cannot be empty", field="name")
    return stripped


def _validate_fee(fee_bps: int, fee_fixed: int) -> None:
    if not 0 <= fee_bps <= _BPS_DENOMINATOR:
        raise ValidationError(
            f"fee_bps must be between 0 and {_BPS_DENOMINATOR}, got {fee_bps}",
            field="fee_bps",
        )
    if fee_fixed < 0:
        raise ValidationError(f"fee_fixed must be >= 0, got {fee_fixed}", field="fee_fixed")


def _validate_rule(settlement_rule: str, settlement_days: int | None) -> None:
    if settlement_rule not in SETTLEMENT_RULES:
        valid = ", ".join(SETTLEMENT_RULES)
        raise ValidationError(
            f"Invalid settlement_rule '{settlement_rule}'. Must be one of: {valid}",
            field="settlement_rule",
        )
    if settlement_rule == "IMMEDIATE":
        if settlement_days is not None:
            raise ValidationError(
                "settlement_days must be empty for an IMMEDIATE method",
                field="settlement_days",
            )
        return
    low, high = _DAYS_RANGE[settlement_rule]
    if settlement_days is None or not low <= settlement_days <= high:
        raise ValidationError(
            f"settlement_days must be between {low} and {high} for "
            f"{settlement_rule}, got {settlement_days}",
            field="settlement_days",
        )


def _name_conflict(name: str) -> ConflictError:
    return ConflictError(f"A payment method named '{name}' already exists")


def count_pending_orders(conn: sqlite3.Connection, payment_method_id: int) -> int:
    """Paid orders of this method that are not yet in a settlement."""
    placeholders = ", ".join("?" for _ in PAID_STATUSES)
    row = conn.execute(
        f"""
        SELECT COUNT(*) FROM orders
        WHERE payment_method_id = ?
          AND status IN ({placeholders})
          AND settlement_id IS NULL
        """,
        (payment_method_id, *PAID_STATUSES),
    ).fetchone()
    return row[0]


def add_payment_method(
    conn: sqlite3.Connection,
    name: str,
    settlement_rule: str,
    settlement_days: int | None = None,
    fee_bps: int = 0,
    fee_fixed: int = 0,
) -> int:
    validated_name = _validate_name(name)
    _validate_fee(fee_bps, fee_fixed)
    _validate_rule(settlement_rule, settlement_days)

    try:
        with transaction(conn):
            cursor = conn.execute(
                """
                INSERT INTO payment_methods
                    (name, fee_bps, fee_fixed, settlement_rule, settlement_days)
                VALUES (?, ?, ?, ?, ?)
                """,
                (validated_name, fee_bps, fee_fixed, settlement_rule, settlement_days),
            )
    except sqlite3.IntegrityError:
        raise _name_conflict(validated_name) from None
    return cursor.lastrowid


def list_payment_methods(
    conn: sqlite3.Connection, include_inactive: bool = False
) -> list[dict]:
    query = "SELECT * FROM payment_methods"
    if not include_inactive:
        query += " WHERE is_active = 1"
    query += " ORDER BY name"
    return [dict(row) for row in conn.execute(query).fetchall()]


def get_payment_method(conn: sqlite3.Connection, payment_method_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM payment_methods WHERE id = ?", (payment_method_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"Payment method with id {payment_method_id} does not exist")
    return dict(row)


def update_payment_method(conn: sqlite3.Connection, payment_method_id: int, **fields) -> None:
    """Partial update. Fee changes are always allowed (the fee is frozen per
    order); a rule change is refused while paid orders are pending settlement,
    because their frozen expected dates and month groups follow the old rule."""
    current = get_payment_method(conn, payment_method_id)

    for field_name in fields:
        if field_name not in UPDATABLE_FIELDS:
            raise ValidationError(f"Unknown field '{field_name}'", field=field_name)
    if not fields:
        return

    if "name" in fields:
        fields["name"] = _validate_name(fields["name"])

    merged = {**current, **fields}
    _validate_fee(merged["fee_bps"], merged["fee_fixed"])
    _validate_rule(merged["settlement_rule"], merged["settlement_days"])

    rule_changed = (
        merged["settlement_rule"] != current["settlement_rule"]
        or merged["settlement_days"] != current["settlement_days"]
    )
    if rule_changed:
        pending = count_pending_orders(conn, payment_method_id)
        if pending:
            noun = "paid order is" if pending == 1 else "paid orders are"
            raise ConflictError(
                f"Cannot change the settlement rule of '{current['name']}': "
                f"{pending} {noun} still pending settlement. Deactivate this method "
                f"and create a new one with the new rule."
            )

    assignments = [f"{name} = ?" for name in fields] + ["updated_at = ?"]
    params = [*fields.values(), now_utc(), payment_method_id]
    try:
        with transaction(conn):
            conn.execute(
                f"UPDATE payment_methods SET {', '.join(assignments)} WHERE id = ?",
                params,
            )
    except sqlite3.IntegrityError:
        raise _name_conflict(merged["name"]) from None


def _set_active(conn: sqlite3.Connection, payment_method_id: int, is_active: int) -> None:
    get_payment_method(conn, payment_method_id)  # raises NotFoundError if missing
    with transaction(conn):
        conn.execute(
            "UPDATE payment_methods SET is_active = ?, updated_at = ? WHERE id = ?",
            (is_active, now_utc(), payment_method_id),
        )


def deactivate_payment_method(conn: sqlite3.Connection, payment_method_id: int) -> None:
    """An inactive method can't be chosen for a new order or as a channel
    default; its existing orders still settle normally."""
    _set_active(conn, payment_method_id, 0)


def reactivate_payment_method(conn: sqlite3.Connection, payment_method_id: int) -> None:
    _set_active(conn, payment_method_id, 1)


def compute_fee(customer_total: int, method: dict) -> int:
    """half_even(customer_total × fee_bps / 10000) + fee_fixed, in integer Toman.

    Integer arithmetic only: divmod gives the exact remainder, and an exact
    half rounds to the even neighbour (never float, never round()).
    """
    quotient, remainder = divmod(customer_total * method["fee_bps"], _BPS_DENOMINATOR)
    twice = 2 * remainder
    if twice > _BPS_DENOMINATOR or (twice == _BPS_DENOMINATOR and quotient % 2 == 1):
        quotient += 1
    return quotient + method["fee_fixed"]


def compute_expected_settlement_date(paid_date: date, method: dict) -> date:
    """The local calendar day the method is expected to pay out an order paid on paid_date.

    IMMEDIATE: the paid day. DAYS_AFTER: paid_date + N days.
    DAY_OF_NEXT_MONTH: day N of the Jalali month after paid_date's month,
    clamped to that month's length (N = 31 in Mehr gives 30 Mehr).
    """
    rule = method["settlement_rule"]
    days = method["settlement_days"]
    if rule == "IMMEDIATE":
        return paid_date
    if rule == "DAYS_AFTER":
        return paid_date + timedelta(days=days)
    if rule == "DAY_OF_NEXT_MONTH":
        jy, jm, _ = jalali.to_jalali(paid_date)
        ny, nm = jalali.next_month(jy, jm)
        return jalali.to_gregorian(ny, nm, min(days, jalali.month_length(ny, nm)))
    raise ValidationError(f"Unknown settlement_rule '{rule}'", field="settlement_rule")


def preview_fee(conn: sqlite3.Connection, payment_method_id: int, amount: int) -> dict:
    """The fee this method would charge on a customer_total of `amount`, and
    what it would then pay out. Display only; an inactive method may be previewed."""
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ValidationError(f"amount must be an integer >= 0, got {amount!r}", field="amount")
    method = get_payment_method(conn, payment_method_id)  # raises NotFoundError
    fee = compute_fee(amount, method)
    return {
        "payment_method_id": method["id"],
        "amount": amount,
        "transaction_fee": fee,
        "expected_amount": amount - fee,
    }
