"""Jalali calendar arithmetic, a port of jalaali-js (matches the frontend's date-fns-jalali). Pure functions on `date`:
`to_jalali`, `to_gregorian`, `month_length`, `month_range`, `next_month`, `is_leap`."""

from datetime import date, timedelta

# Jalali years where the 33-year leap cycle breaks.
_BREAKS = (
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
)

# Days before the first day of each month (index 0 = Farvardin).
_MONTH_OFFSETS = tuple((m * 31) if m <= 6 else (186 + (m - 6) * 30) for m in range(12))


def _div(a: int, b: int) -> int:
    """Integer division truncating toward zero (JS `~~(a / b)`)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def _mod(a: int, b: int) -> int:
    """Remainder with the sign of the dividend (JS `a % b`)."""
    return a - _div(a, b) * b


def _jal_cal(jy: int) -> tuple[int, int, int]:
    """(leap, gy, march) for Jalali year jy.

    leap: years since the last leap year (0 means jy itself is leap).
    gy: the Gregorian year in which jy begins.
    march: the day of March (in gy) on which Farvardin 1 of jy falls.
    """
    if jy < _BREAKS[0] or jy >= _BREAKS[-1]:
        raise ValueError(f"Jalali year {jy} is out of the supported range")

    gy = jy + 621
    leap_j = -14
    jp = _BREAKS[0]
    jump = 0
    for jm in _BREAKS[1:]:
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm

    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1

    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g

    if jump - n < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4
    return leap, gy, march


def _farvardin_first(jy: int) -> date:
    _, gy, march = _jal_cal(jy)
    return date(gy, 3, march)


def is_leap(jy: int) -> bool:
    """True when Esfand of jy has 30 days."""
    return _jal_cal(jy)[0] == 0


def month_length(jy: int, jm: int) -> int:
    """31 for months 1-6, 30 for 7-11, 29 or 30 (leap) for Esfand."""
    if not 1 <= jm <= 12:
        raise ValueError(f"Jalali month must be 1-12, got {jm}")
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_leap(jy) else 29


def to_gregorian(jy: int, jm: int, jd: int) -> date:
    """Jalali (jy, jm, jd) -> Gregorian date. Raises ValueError if invalid."""
    length = month_length(jy, jm)
    if not 1 <= jd <= length:
        raise ValueError(f"Jalali {jy}/{jm} has {length} days, got day {jd}")
    return _farvardin_first(jy) + timedelta(days=_MONTH_OFFSETS[jm - 1] + jd - 1)


def to_jalali(d: date) -> tuple[int, int, int]:
    """Gregorian date -> Jalali (jy, jm, jd)."""
    jy = d.year - 621
    start = _farvardin_first(jy)
    if d < start:
        jy -= 1
        start = _farvardin_first(jy)
    day_of_year = (d - start).days
    if day_of_year < 186:
        return jy, 1 + day_of_year // 31, 1 + day_of_year % 31
    day_of_year -= 186
    return jy, 7 + day_of_year // 30, 1 + day_of_year % 30


def month_range(jy: int, jm: int) -> tuple[date, date]:
    """(first day, last day) of Jalali month jy/jm, as Gregorian dates."""
    return to_gregorian(jy, jm, 1), to_gregorian(jy, jm, month_length(jy, jm))


def next_month(jy: int, jm: int) -> tuple[int, int]:
    """The Jalali month after jy/jm (Esfand -> Farvardin of the next year)."""
    if not 1 <= jm <= 12:
        raise ValueError(f"Jalali month must be 1-12, got {jm}")
    return (jy + 1, 1) if jm == 12 else (jy, jm + 1)
