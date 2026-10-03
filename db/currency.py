"""Display currency. Money is stored, computed and sent as integer Toman; the
owner can choose to SEE it in Rial (Toman x 10, always exact). This module is
the backend's one place that knows the conversion (the frontend's twin is
frontend/lib/money.ts). It only converts for display; it never changes a
stored or reported figure."""

import sqlite3

from db.errors import ValidationError

DISPLAY_CURRENCIES = ("TOMAN", "RIAL")
DEFAULT_DISPLAY_CURRENCY = "TOMAN"
RIAL_PER_TOMAN = 10

_LABELS = {"TOMAN": "تومان", "RIAL": "ریال"}


def _check_currency(currency: str) -> None:
    if currency not in DISPLAY_CURRENCIES:
        valid = ", ".join(DISPLAY_CURRENCIES)
        raise ValidationError(
            f"Display currency must be one of: {valid}, got {currency!r}",
            field="value",
        )


def get_display_currency(conn: sqlite3.Connection) -> str:
    """The saved display currency; TOMAN if the row is missing or unknown."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'display_currency'"
    ).fetchone()
    value = row["value"] if row is not None else None
    return value if value in DISPLAY_CURRENCIES else DEFAULT_DISPLAY_CURRENCY


def to_display_amount(toman: int, currency: str) -> int:
    """An integer Toman amount in the display currency: exact, never rounded."""
    # bool is an int subclass; a float would mean a money slip upstream.
    if not isinstance(toman, int) or isinstance(toman, bool):
        raise TypeError(f"Money must be an int count of Toman, got {toman!r}")
    _check_currency(currency)
    return toman * RIAL_PER_TOMAN if currency == "RIAL" else toman


def currency_label(currency: str) -> str:
    _check_currency(currency)
    return _LABELS[currency]
