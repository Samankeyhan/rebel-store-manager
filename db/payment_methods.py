"""Payment methods: CRUD, deactivate/reactivate. Fee = `fee_bps` (optionally capped by `fee_cap`) + `fee_fixed`; settlement rule IMMEDIATE / DAYS_AFTER / DAY_OF_NEXT_MONTH.
`compute_fee` (integer only, half-even), `compute_expected_settlement_date`, `preview_fee`, `count_pending_orders`.
`fee_cap` caps the percentage part only (None = no cap) and needs fee_bps > 0.
A settlement-rule change is refused while the method has pending orders."""

import sqlite3
from datetime import date, timedelta

from db import jalali
from db.audit import audited
from db.connection import transaction
from db.costing import check_money
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.name_keys import duplicate_guard
from db.names import name_key, stored_form
from db.timeutil import now_utc

SETTLEMENT_RULES = ("IMMEDIATE", "DAYS_AFTER", "DAY_OF_NEXT_MONTH")

# An order counts as paid in these statuses; pending settlement while it has
# a payment method and no settlement_id.
PAID_STATUSES = ("PAID", "COMPLETED")

UPDATABLE_FIELDS = ("name", "fee_bps", "fee_fixed", "fee_cap", "settlement_rule", "settlement_days")

_BPS_DENOMINATOR = 10000
_DAYS_RANGE = {"DAYS_AFTER": (1, 365), "DAY_OF_NEXT_MONTH": (1, 31)}


def _validate_name(name: str) -> str:
    stripped = stored_form(name) if name is not None else ""
    if not stripped:
        raise ValidationError("name is required and cannot be empty", field="name")
    return stripped


def _require_int(value, field: str) -> None:
    """fee_bps / fee_fixed always have a value: an integer, never None, bool or float."""
    if value is None:
        raise ValidationError(f"{field} cannot be empty", field=field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field} must be an integer, got {value!r}", field=field)


def _validate_fee(fee_bps: int, fee_fixed: int) -> None:
    _require_int(fee_bps, "fee_bps")
    _require_int(fee_fixed, "fee_fixed")
    if not 0 <= fee_bps <= _BPS_DENOMINATOR:
        raise ValidationError(
            f"fee_bps must be between 0 and {_BPS_DENOMINATOR}, got {fee_bps}",
            field="fee_bps",
        )
    check_money(fee_fixed, "fee_fixed")
    if fee_fixed < 0:
        raise ValidationError(f"fee_fixed must be >= 0, got {fee_fixed}", field="fee_fixed")


def _validate_fee_cap(fee_cap: int | None, fee_bps: int) -> None:
    """None = no cap. Otherwise an integer >= 1 Rial, on a method with a percentage fee."""
    if fee_cap is None:
        return
    if isinstance(fee_cap, bool) or not isinstance(fee_cap, int):
        raise ValidationError(
            f"fee_cap must be an integer number of Rial, or empty for no cap, got {fee_cap!r}",
            field="fee_cap",
        )
    check_money(fee_cap, "fee_cap")
    if fee_cap < 1:
        raise ValidationError(
            f"fee_cap must be >= 1 Rial; leave it empty for no cap, got {fee_cap}",
            field="fee_cap",
        )
    if fee_bps == 0:
        raise ValidationError(
            "fee_cap needs a percentage fee (fee_bps > 0); clear fee_cap for a method "
            "without a percentage fee",
            field="fee_cap",
        )


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


@audited()
def add_payment_method(
    conn: sqlite3.Connection,
    name: str,
    settlement_rule: str,
    settlement_days: int | None = None,
    fee_bps: int = 0,
    fee_fixed: int = 0,
    fee_cap: int | None = None,
) -> int:
    validated_name = _validate_name(name)
    _validate_fee(fee_bps, fee_fixed)
    _validate_fee_cap(fee_cap, fee_bps)
    _validate_rule(settlement_rule, settlement_days)

    with duplicate_guard(
        conn, "payment_methods", validated_name, code=ErrorCode.PAYMENT_METHOD_DUPLICATE_NAME
    ):
        with transaction(conn):
            cursor = conn.execute(
                """
                INSERT INTO payment_methods
                    (name, name_key, fee_bps, fee_fixed, fee_cap, settlement_rule, settlement_days)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (validated_name, name_key(validated_name), fee_bps, fee_fixed, fee_cap,
                 settlement_rule, settlement_days),
            )
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
        raise NotFoundError(
            f"Payment method with id {payment_method_id} does not exist",
            code=ErrorCode.PAYMENT_METHOD_NOT_FOUND,
            details={"payment_method_id": payment_method_id},
        )
    return dict(row)


@audited()
def update_payment_method(conn: sqlite3.Connection, payment_method_id: int, **fields) -> None:
    """Partial update. Fee changes are always allowed (the fee is frozen per
    order); a rule change is refused while paid orders are pending settlement,
    because their frozen expected dates and month groups follow the old rule.

    fee_cap=None clears the cap. Setting fee_bps to 0 while a cap is set is
    refused unless the same update clears it (fee_cap=None)."""
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
    _validate_fee_cap(merged["fee_cap"], merged["fee_bps"])
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
                f"and create a new one with the new rule.",
                code=ErrorCode.PAYMENT_METHOD_RULE_PENDING,
                details={"pending_count": pending},
            )

    if "name" in fields:
        fields["name_key"] = name_key(fields["name"])
    assignments = [f"{name} = ?" for name in fields] + ["updated_at = ?"]
    params = [*fields.values(), now_utc(), payment_method_id]
    with duplicate_guard(
        conn, "payment_methods", merged["name"], exclude_id=payment_method_id,
        code=ErrorCode.PAYMENT_METHOD_DUPLICATE_NAME,
    ):
        with transaction(conn):
            conn.execute(
                f"UPDATE payment_methods SET {', '.join(assignments)} WHERE id = ?",
                params,
            )


def _set_active(conn: sqlite3.Connection, payment_method_id: int, is_active: int) -> None:
    get_payment_method(conn, payment_method_id)  # raises NotFoundError if missing
    with transaction(conn):
        conn.execute(
            "UPDATE payment_methods SET is_active = ?, updated_at = ? WHERE id = ?",
            (is_active, now_utc(), payment_method_id),
        )


@audited()
def deactivate_payment_method(conn: sqlite3.Connection, payment_method_id: int) -> None:
    """An inactive method can't be chosen for a new order or as a channel
    default; its existing orders still settle normally."""
    _set_active(conn, payment_method_id, 0)


@audited()
def reactivate_payment_method(conn: sqlite3.Connection, payment_method_id: int) -> None:
    _set_active(conn, payment_method_id, 1)


def compute_fee(customer_total: int, method: dict) -> int:
    """min(half_even(customer_total × fee_bps / 10000), fee_cap) + fee_fixed, in integer Rial.

    Integer arithmetic only: divmod gives the exact remainder, and an exact
    half rounds to the even neighbour (never float, never round()). The cap
    (None = no cap) applies to the rounded percentage part only; fee_fixed is
    never capped.
    """
    quotient, remainder = divmod(customer_total * method["fee_bps"], _BPS_DENOMINATOR)
    twice = 2 * remainder
    if twice > _BPS_DENOMINATOR or (twice == _BPS_DENOMINATOR and quotient % 2 == 1):
        quotient += 1
    if method["fee_cap"] is not None:
        quotient = min(quotient, method["fee_cap"])
    return check_money(quotient + method["fee_fixed"], "transaction_fee")


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
