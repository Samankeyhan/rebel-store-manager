import sqlite3
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from db.errors import ValidationError

DEFAULT_TIMEZONE = "Asia/Tehran"
UTC = timezone.utc

_DATE_FORMAT = "%Y-%m-%d"
_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
_STORED_FORMAT = "%Y-%m-%d %H:%M:%S"


def _get_timezone(conn: sqlite3.Connection | None = None) -> ZoneInfo:
    if conn is not None:
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = 'timezone'"
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is not None and row[0]:
            return ZoneInfo(row[0])
    return ZoneInfo(DEFAULT_TIMEZONE)


def _local_to_utc_text(local_naive: datetime, tz: ZoneInfo) -> str:
    aware_local = local_naive.replace(tzinfo=tz)
    return aware_local.astimezone(UTC).strftime(_STORED_FORMAT)


def now_utc() -> str:
    return datetime.now(UTC).strftime(_STORED_FORMAT)


def normalize_record_date(value: str, conn: sqlite3.Connection | None = None) -> str:
    """Convert a caller-supplied local record date/time to a stored UTC string.

    Accepts "YYYY-MM-DD" (local midnight of that day) or
    "YYYY-MM-DD HH:MM" (that local wall-clock time).
    """
    stripped = value.strip()
    tz = _get_timezone(conn)
    for fmt in (_DATETIME_FORMAT, _DATE_FORMAT):
        try:
            local_naive = datetime.strptime(stripped, fmt)
        except ValueError:
            continue
        return _local_to_utc_text(local_naive, tz)
    raise ValidationError(
        f"Invalid date '{value}'. Expected 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM'.",
        field="date",
    )


def validate_calendar_date(value: str) -> str:
    """Validate a local calendar-day string ("YYYY-MM-DD"), returned unchanged.

    Used for fields that mean a whole local day rather than a moment in time
    (e.g. profit_distributions.period_start/period_end) — no UTC conversion.
    """
    stripped = value.strip()
    try:
        datetime.strptime(stripped, _DATE_FORMAT)
    except ValueError:
        raise ValidationError(
            f"Invalid date '{value}'. Expected 'YYYY-MM-DD'.", field="date"
        ) from None
    return stripped


def parse_calendar_date(value: str) -> date:
    """A validated local calendar-day string ("YYYY-MM-DD") as a date."""
    return datetime.strptime(validate_calendar_date(value), _DATE_FORMAT).date()


def today_local(conn: sqlite3.Connection | None = None) -> date:
    """Today's calendar day in the store timezone (the `timezone` setting)."""
    return datetime.now(_get_timezone(conn)).date()


def to_utc_range(
    start_date: str | None,
    end_date: str | None,
    conn: sqlite3.Connection | None = None,
) -> tuple[str | None, str | None]:
    """Convert a local calendar-day [start_date, end_date] range to a UTC
    [start, end) range suitable for `stored_value >= start AND stored_value < end`.

    Either bound may be omitted (None in, None out).
    """
    tz = _get_timezone(conn)
    start_utc = None
    end_exclusive_utc = None

    if start_date is not None:
        start_local = datetime.strptime(start_date.strip(), _DATE_FORMAT)
        start_utc = _local_to_utc_text(start_local, tz)

    if end_date is not None:
        end_local = datetime.strptime(end_date.strip(), _DATE_FORMAT) + timedelta(days=1)
        end_exclusive_utc = _local_to_utc_text(end_local, tz)

    return start_utc, end_exclusive_utc
