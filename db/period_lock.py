"""Closed days: a day on or before the period_end of the LATEST recorded profit distribution (docs/accounting-rules.md section 11).
`refuse_closed_day` is the guard for edits and deletes that would change net_profit on such a day (expenses, postage payments); recording a NEW row on a closed day is not guarded.
Reads `profit_distributions` only, and imports nothing from `db/` but errors, so `expenses` and `postage` can use it without a cycle through `reports`."""

import sqlite3
from datetime import date

from db.errors import ConflictError, ErrorCode


def latest_distribution(conn: sqlite3.Connection) -> dict | None:
    """{id, period_end} of the distribution with the latest period_end (ties: highest id), or None."""
    row = conn.execute(
        "SELECT id, period_end FROM profit_distributions ORDER BY period_end DESC, id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row is not None else None


def refuse_closed_day(conn: sqlite3.Connection, day: date) -> None:
    """ConflictError PERIOD_ALREADY_DISTRIBUTED when `day` is on or before the latest period_end."""
    latest = latest_distribution(conn)
    if latest is not None and day.isoformat() <= latest["period_end"]:
        raise ConflictError(
            f"{day.isoformat()} is closed by profit distribution #{latest['id']} "
            f"(paid out up to {latest['period_end']}); it can no longer be changed",
            code=ErrorCode.PERIOD_ALREADY_DISTRIBUTED,
            details={
                "distribution_id": latest["id"],
                "period_end": latest["period_end"],
                "date": day.isoformat(),
            },
        )
