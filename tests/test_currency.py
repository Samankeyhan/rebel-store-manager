import pytest

from db.currency import (
    RIAL_PER_TOMAN,
    currency_label,
    format_display_number,
    get_display_currency,
    to_display_parts,
)
from db.errors import ValidationError
from db.settings import set_setting


def test_rial_is_the_stored_integer():
    assert RIAL_PER_TOMAN == 10
    for rial in (0, 1, 7, 1_800_000, 1_800_005, 10**15):
        assert to_display_parts(rial, "RIAL") == (False, rial, None)


@pytest.mark.parametrize(
    "rial, expected",
    [
        (0, (False, 0, None)),
        (1_800_000, (False, 180_000, None)),  # a multiple of 10: whole Toman
        (1_800_005, (False, 180_000, 5)),     # odd Rial: one decimal digit
        (7, (False, 0, 7)),
        (10, (False, 1, None)),
        (-15, (True, 1, 5)),
        (-2_500, (True, 250, None)),
        (9_007_199_254_740_991, (False, 900_719_925_474_099, 1)),
    ],
)
def test_toman_is_rial_divided_by_ten_exactly(rial, expected):
    assert to_display_parts(rial, "TOMAN") == expected


@pytest.mark.parametrize(
    "rial, toman_text, rial_text",
    [
        (1_800_000, "180,000", "1,800,000"),
        (1_800_005, "180,000.5", "1,800,005"),
        (7, "0.7", "7"),
        (-15, "-1.5", "-15"),
        (0, "0", "0"),
    ],
)
def test_format_display_number(rial, toman_text, rial_text):
    assert format_display_number(rial, "TOMAN") == toman_text
    assert format_display_number(rial, "RIAL") == rial_text
    assert format_display_number(rial, "TOMAN", decimal_mark="٫") == toman_text.replace(".", "٫")


def test_display_refuses_non_int_money():
    for bad in (1.5, 10.0, "100", True):
        with pytest.raises(TypeError):
            to_display_parts(bad, "TOMAN")


def test_display_refuses_unknown_currency():
    with pytest.raises(ValidationError):
        to_display_parts(100, "USD")


def test_currency_labels():
    assert currency_label("TOMAN") == "تومان"
    assert currency_label("RIAL") == "ریال"


def test_get_display_currency_defaults_and_follows_setting(test_db):
    assert get_display_currency(test_db) == "TOMAN"
    set_setting(test_db, "display_currency", "RIAL")
    assert get_display_currency(test_db) == "RIAL"


def test_get_display_currency_falls_back_when_row_missing(test_db):
    test_db.execute("DELETE FROM settings WHERE key = 'display_currency'")
    assert get_display_currency(test_db) == "TOMAN"


def test_toman_parts_round_trip_every_rial_from_minus_2000_to_2000():
    for rial in range(-2000, 2001):
        negative, whole, tenth = to_display_parts(rial, "TOMAN")
        back = whole * RIAL_PER_TOMAN + (tenth or 0)
        assert (-back if negative else back) == rial
        # A whole Toman never shows a decimal digit; an odd Rial always does.
        assert (tenth is None) == (rial % 10 == 0)
