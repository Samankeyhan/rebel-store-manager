from datetime import datetime, timezone

import pytest

from db.errors import ValidationError
from db.timeutil import (
    normalize_record_date,
    now_utc,
    to_utc_range,
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
