import pytest

from db.currency import (
    RIAL_PER_TOMAN,
    currency_label,
    get_display_currency,
    to_display_amount,
)
from db.errors import ValidationError
from db.settings import set_setting


def test_rial_is_exactly_ten_toman():
    assert RIAL_PER_TOMAN == 10
    for toman in (0, 1, 7, 180_000, -2_500, 10**15):
        assert to_display_amount(toman, "RIAL") == toman * 10
        assert to_display_amount(toman, "TOMAN") == toman


def test_to_display_amount_refuses_non_int_money():
    for bad in (1.5, 10.0, "100", True):
        with pytest.raises(TypeError):
            to_display_amount(bad, "RIAL")


def test_to_display_amount_refuses_unknown_currency():
    with pytest.raises(ValidationError):
        to_display_amount(100, "USD")


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
