from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from db.errors import ValidationError
from db.timeutil import (
    normalize_record_date,
    now_utc,
    parse_calendar_date,
    to_utc_range,
    today_local,
    validate_calendar_date,
)


def test_normalize_record_date_bare_date_is_local_midnight():
    assert normalize_record_date("2026-03-10") == "2026-03-09 20:30:00"


def test_normalize_record_date_with_time():
    assert normalize_record_date("2026-03-10 11:30") == "2026-03-10 08:00:00"


def test_normalize_record_date_rejects_bad_format():
    with pytest.raises(ValidationError):
        normalize_record_date("03/10/2026")


def test_validate_calendar_date_round_trips_and_rejects_bad_format():
    assert validate_calendar_date("2026-03-10") == "2026-03-10"
    with pytest.raises(ValidationError):
        validate_calendar_date("2026-13-40")
    with pytest.raises(ValidationError):
        validate_calendar_date("2026-03-10 08:00:00")


def test_now_utc_format_and_roughly_current():
    value = now_utc()
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    delta = abs((datetime.now(timezone.utc).replace(tzinfo=None) - parsed).total_seconds())
    assert delta < 5


def test_to_utc_range_none_bounds_pass_through():
    assert to_utc_range(None, None) == (None, None)


def test_to_utc_range_boundary_case_exactly_as_specified():
    # An order stored at local Tehran 2026-03-10 23:30 (UTC "2026-03-10 20:00:00")
    # IS included by end_date "2026-03-10".
    _, end_exclusive_utc = to_utc_range(None, "2026-03-10")
    assert end_exclusive_utc == "2026-03-10 20:30:00"
    assert "2026-03-10 20:00:00" < end_exclusive_utc

    # An order at local 2026-03-11 01:00 (UTC "2026-03-10 21:30:00") is NOT
    # included by end_date "2026-03-10" ...
    assert not ("2026-03-10 21:30:00" < end_exclusive_utc)

    # ... and IS included by start_date = end_date = "2026-03-11".
    start_utc2, end_exclusive_utc2 = to_utc_range("2026-03-11", "2026-03-11")
    assert start_utc2 == "2026-03-10 20:30:00"
    assert end_exclusive_utc2 == "2026-03-11 20:30:00"
    assert start_utc2 <= "2026-03-10 21:30:00" < end_exclusive_utc2


def test_parse_calendar_date_returns_a_date_and_rejects_bad_input():
    assert parse_calendar_date("2026-09-22") == date(2026, 9, 22)
    assert parse_calendar_date(" 2026-09-22 ") == date(2026, 9, 22)
    for bad in ("2026-02-30", "22/09/2026", "2026-09-22 10:00"):
        with pytest.raises(ValidationError):
            parse_calendar_date(bad)


def test_today_local_defaults_to_tehran():
    before = datetime.now(ZoneInfo("Asia/Tehran")).date()
    value = today_local()
    after = datetime.now(ZoneInfo("Asia/Tehran")).date()
    assert value in (before, after)


@pytest.mark.parametrize("zone", ["Pacific/Kiritimati", "Pacific/Pago_Pago"])
def test_today_local_follows_the_timezone_setting(test_db, zone):
    test_db.execute("UPDATE settings SET value = ? WHERE key = 'timezone'", (zone,))
    before = datetime.now(ZoneInfo(zone)).date()
    value = today_local(test_db)
    after = datetime.now(ZoneInfo(zone)).date()
    assert value in (before, after)
