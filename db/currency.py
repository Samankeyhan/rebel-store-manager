"""Display currency (TOMAN/RIAL). Money is stored, computed and sent as integer Rial; this is the backend's only conversion point, display only (the frontend's twin is frontend/lib/money.ts).
RIAL shows the stored integer; TOMAN shows Rial ÷ 10 by integer `divmod`, with one decimal digit only when the Rial amount is not a multiple of 10. Never changes a stored or reported figure.
`DISPLAY_CURRENCIES`, `get_display_currency`, `to_display_parts`, `format_display_number`, `currency_label`. Money stays integer Rial everywhere else."""

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


def _check_rial(rial: int) -> None:
    # bool is an int subclass; a float would mean a money slip upstream.
    if not isinstance(rial, int) or isinstance(rial, bool):
        raise TypeError(f"Money must be an int count of Rial, got {rial!r}")


def get_display_currency(conn: sqlite3.Connection) -> str:
    """The saved display currency; TOMAN if the row is missing or unknown."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'display_currency'"
    ).fetchone()
    value = row["value"] if row is not None else None
    return value if value in DISPLAY_CURRENCIES else DEFAULT_DISPLAY_CURRENCY


def to_display_parts(rial: int, currency: str) -> tuple[bool, int, int | None]:
    """An integer Rial amount in the display currency, as (negative, whole, tenth).

    RIAL: whole = |rial|, tenth None. TOMAN: whole = |rial| // 10 and tenth =
    the last Rial digit, or None when it is 0 (a whole Toman). Exact: integer
    divmod only, never a float, never rounded.
    """
    _check_rial(rial)
    _check_currency(currency)
    negative = rial < 0
    magnitude = -rial if negative else rial
    if currency == "RIAL":
        return negative, magnitude, None
    whole, tenth = divmod(magnitude, RIAL_PER_TOMAN)
    return negative, whole, tenth or None


def format_display_number(rial: int, currency: str, decimal_mark: str = ".") -> str:
    """The display number in Latin digits with "," grouping and no unit:
    (1800005, "TOMAN") -> "180,000.5", (1800005, "RIAL") -> "1,800,005"."""
    negative, whole, tenth = to_display_parts(rial, currency)
    text = f"{whole:,}"
    if tenth is not None:
        text += f"{decimal_mark}{tenth}"
    return f"-{text}" if negative else text


def currency_label(currency: str) -> str:
    _check_currency(currency)
    return _LABELS[currency]
