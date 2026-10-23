"""Postage payments in batches: `record_postage_batch` (total_paid >= 0, order_count > 0), `get_postage_batch`, `list_postage_batches`.
`update_postage_batch` / `delete_postage_batch` fix a mistaken payment (hard delete: the audit log keeps the old row; they change the estimate for future orders only, never frozen `postage_cost`); a paid_date after today is refused (DATE_IN_FUTURE); changing total_paid or paid_date, or deleting, on a closed day is refused (`db/period_lock.py`).
`get_current_postage_estimate`: total_paid ÷ order_count over the newest `postage_estimate_window` batches, rounded half-even; `default_postage_estimate` when there are none."""

import sqlite3
from fractions import Fraction

from db.audit import audited
from db.connection import transaction
from db.costing import check_money, round_half_even
from db.errors import NotFoundError, ValidationError
from db.period_lock import refuse_closed_day
from db.settings import get_setting
from db.timeutil import local_day, normalize_record_date, refuse_future_day, to_utc_range


def _validate_total_paid(total_paid: int) -> None:
    check_money(total_paid, "total_paid")
    if total_paid < 0:
        raise ValidationError(f"total_paid must be >= 0, got {total_paid}", field="total_paid")


def _validate_order_count(order_count: int) -> None:
    if order_count <= 0:
        raise ValidationError(f"order_count must be > 0, got {order_count}", field="order_count")


@audited()
def record_postage_batch(
    conn: sqlite3.Connection,
    total_paid: int,
    order_count: int,
    paid_date: str | None = None,
    notes: str | None = None,
) -> int:
    _validate_total_paid(total_paid)
    _validate_order_count(order_count)

    if paid_date is not None:
        paid_date = normalize_record_date(paid_date, conn)
        refuse_future_day(conn, local_day(paid_date, conn), "paid_date")

    with transaction(conn):
        if paid_date is not None:
            cursor = conn.execute(
                """
                INSERT INTO postage_batches (paid_date, total_paid, order_count, notes)
                VALUES (?, ?, ?, ?)
                """,
                (paid_date, total_paid, order_count, notes),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO postage_batches (total_paid, order_count, notes)
                VALUES (?, ?, ?)
                """,
                (total_paid, order_count, notes),
            )
    return cursor.lastrowid


_EDITABLE = ("total_paid", "order_count", "paid_date", "notes")


@audited()
def update_postage_batch(conn: sqlite3.Connection, batch_id: int, **fields) -> None:
    """Partial update: only the keys given change (`notes=None` clears them; the others cannot be None).
    A new `paid_date` may not be after today (DATE_IN_FUTURE). A change of `total_paid` or `paid_date` is refused on a
    day on or before the latest profit distribution's period_end, old or new (PERIOD_ALREADY_DISTRIBUTED);
    `order_count` and `notes` changes are always allowed (they move the estimate, not the P&L)."""
    unknown = sorted(set(fields) - set(_EDITABLE))
    if unknown:
        raise ValidationError(f"Cannot update: {', '.join(unknown)}", field=unknown[0])
    old = get_postage_batch(conn, batch_id)
    if old is None:
        raise NotFoundError(f"Postage batch with id {batch_id} does not exist")
    for name in ("total_paid", "order_count", "paid_date"):
        if name in fields and fields[name] is None:
            raise ValidationError(f"{name} cannot be empty", field=name)

    changes: dict = {}
    if "total_paid" in fields:
        _validate_total_paid(fields["total_paid"])
        if fields["total_paid"] != old["total_paid"]:
            changes["total_paid"] = fields["total_paid"]
    if "order_count" in fields:
        _validate_order_count(fields["order_count"])
        if fields["order_count"] != old["order_count"]:
            changes["order_count"] = fields["order_count"]
    if "notes" in fields and fields["notes"] != old["notes"]:
        changes["notes"] = fields["notes"]

    old_day = local_day(old["paid_date"], conn)
    new_day = old_day
    if "paid_date" in fields:
        moment = normalize_record_date(fields["paid_date"], conn)
        new_day = local_day(moment, conn)
        if new_day != old_day:  # the same day keeps the stored time of day
            refuse_future_day(conn, new_day, "paid_date")
            changes["paid_date"] = moment

    if "total_paid" in changes or "paid_date" in changes:
        refuse_closed_day(conn, old_day)
        refuse_closed_day(conn, new_day)

    if not changes:
        return
    with transaction(conn):
        assignments = ", ".join(f"{name} = ?" for name in changes)
        conn.execute(f"UPDATE postage_batches SET {assignments} WHERE id = ?", (*changes.values(), batch_id))


@audited()
def delete_postage_batch(conn: sqlite3.Connection, batch_id: int) -> None:
    """Hard delete; the audit log keeps the whole old row. Refused on a day on or before the latest profit
    distribution's period_end (PERIOD_ALREADY_DISTRIBUTED). Changes the postage estimate for future orders only."""
    old = get_postage_batch(conn, batch_id)
    if old is None:
        raise NotFoundError(f"Postage batch with id {batch_id} does not exist")
    refuse_closed_day(conn, local_day(old["paid_date"], conn))
    with transaction(conn):
        conn.execute("DELETE FROM postage_batches WHERE id = ?", (batch_id,))


def get_postage_batch(conn: sqlite3.Connection, batch_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM postage_batches WHERE id = ?", (batch_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def list_postage_batches(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM postage_batches WHERE 1=1"
    params: list = []

    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND paid_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND paid_date < ?"
        params.append(end_exclusive_utc)

    query += " ORDER BY paid_date DESC, id DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_current_postage_estimate(conn: sqlite3.Connection) -> int:
    window = int(get_setting(conn, "postage_estimate_window"))
    rows = conn.execute(
        """
        SELECT total_paid, order_count
        FROM postage_batches
        ORDER BY paid_date DESC, id DESC
        LIMIT ?
        """,
        (window,),
    ).fetchall()

    if not rows:
        return int(get_setting(conn, "default_postage_estimate"))

    total_paid = sum(row["total_paid"] for row in rows)
    order_count = sum(row["order_count"] for row in rows)
    return round_half_even(Fraction(total_paid, order_count))
