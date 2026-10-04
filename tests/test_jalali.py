from datetime import date, timedelta

import pytest

from db.jalali import (
    is_leap,
    month_length,
    month_range,
    next_month,
    to_gregorian,
    to_jalali,
)


@pytest.mark.parametrize(
    "gregorian, jalali",
    [
        (date(2025, 3, 21), (1404, 1, 1)),
        (date(2026, 3, 21), (1405, 1, 1)),
        (date(2026, 9, 22), (1405, 6, 31)),
        (date(2026, 9, 23), (1405, 7, 1)),
        (date(2026, 10, 4), (1405, 7, 12)),
        (date(2025, 3, 20), (1403, 12, 30)),   # last day of a leap Esfand
        (date(2026, 3, 20), (1404, 12, 29)),   # last day of a common Esfand
        (date(2021, 3, 20), (1399, 12, 30)),   # 1399 is leap
        (date(2000, 1, 1), (1378, 10, 11)),
        (date(1979, 2, 11), (1357, 11, 22)),
    ],
)
def test_known_pairs_both_directions(gregorian, jalali):
    assert to_jalali(gregorian) == jalali
    assert to_gregorian(*jalali) == gregorian


@pytest.mark.parametrize(
    "jy, leap",
    [(1399, True), (1400, False), (1403, True), (1404, False), (1405, False), (1408, True)],
)
def test_leap_years(jy, leap):
    assert is_leap(jy) is leap


@pytest.mark.parametrize(
    "jy, jm, length",
    [
        (1405, 1, 31),    # Farvardin
        (1405, 6, 31),    # Shahrivar
        (1405, 7, 30),    # Mehr
        (1405, 11, 30),   # Bahman
        (1404, 12, 29),   # Esfand, common year
        (1403, 12, 30),   # Esfand, leap year
    ],
)
def test_month_length(jy, jm, length):
    assert month_length(jy, jm) == length


def test_leap_esfand_30_is_followed_by_farvardin_1():
    last = to_gregorian(1403, 12, 30)
    assert last == date(2025, 3, 20)
    assert to_jalali(last + timedelta(days=1)) == (1404, 1, 1)


def test_common_esfand_has_no_day_30():
    with pytest.raises(ValueError):
        to_gregorian(1404, 12, 30)
    assert to_jalali(to_gregorian(1404, 12, 29) + timedelta(days=1)) == (1405, 1, 1)


@pytest.mark.parametrize(
    "jy, jm, first, last",
    [
        (1405, 6, date(2026, 8, 23), date(2026, 9, 22)),    # 31 days
        (1405, 7, date(2026, 9, 23), date(2026, 10, 22)),   # 30 days
        (1404, 12, date(2026, 2, 20), date(2026, 3, 20)),   # 29 days
        (1403, 12, date(2025, 2, 19), date(2025, 3, 20)),   # 30 days, leap
    ],
)
def test_month_range(jy, jm, first, last):
    assert month_range(jy, jm) == (first, last)
    assert (last - first).days + 1 == month_length(jy, jm)
    # The day after the range is the first day of the next month.
    assert to_jalali(last + timedelta(days=1)) == (*next_month(jy, jm), 1)


def test_next_month():
    assert next_month(1405, 6) == (1405, 7)
    assert next_month(1405, 11) == (1405, 12)
    assert next_month(1403, 12) == (1404, 1)
    assert next_month(1404, 12) == (1405, 1)


def test_round_trip_every_day_2015_to_2040_and_days_are_consecutive():
    day = date(2015, 1, 1)
    end = date(2040, 12, 31)
    previous = to_jalali(day - timedelta(days=1))
    while day <= end:
        jy, jm, jd = to_jalali(day)
        assert to_gregorian(jy, jm, jd) == day
        # Each day is the one after the previous day in the Jalali calendar.
        py, pm, pd = previous
        if pd == month_length(py, pm):
            assert (jy, jm, jd) == (*next_month(py, pm), 1)
        else:
            assert (jy, jm, jd) == (py, pm, pd + 1)
        previous = (jy, jm, jd)
        day += timedelta(days=1)


@pytest.mark.parametrize("args", [(1405, 0, 1), (1405, 13, 1), (1405, 7, 31), (1405, 1, 0)])
def test_invalid_dates_raise(args):
    with pytest.raises(ValueError):
        to_gregorian(*args)


def test_out_of_range_year_raises():
    with pytest.raises(ValueError):
        is_leap(3178)
    with pytest.raises(ValueError):
        month_length(1405, 13)
    with pytest.raises(ValueError):
        next_month(1405, 0)
