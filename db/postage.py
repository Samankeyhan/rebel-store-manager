import sqlite3

from db.connection import transaction
from db.errors import ValidationError
from db.settings import get_setting
from db.timeutil import normalize_record_date, to_utc_range


def _validate_total_paid(total_paid: int) -> None:
    if total_paid < 0:
        raise ValidationError(f"total_paid must be >= 0, got {total_paid}", field="total_paid")


def _validate_order_count(order_count: int) -> None:
    if order_count <= 0:
        raise ValidationError(f"order_count must be > 0, got {order_count}", field="order_count")


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
    return round(total_paid / order_count)
