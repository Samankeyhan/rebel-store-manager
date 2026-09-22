import pytest

from db.errors import NotFoundError, ValidationError
from db.settings import (
    get_channel_settings,
    get_setting,
    set_setting,
    update_channel_settings,
)


def test_get_setting_returns_seeded_defaults(test_db):
    assert get_setting(test_db, "default_shipping_charge") == "180000"
    assert get_setting(test_db, "postage_estimate_window") == "3"
    assert get_setting(test_db, "default_postage_estimate") == "0"
    assert get_setting(test_db, "timezone") == "Asia/Tehran"


def test_get_setting_missing_key_returns_default(test_db):
    assert get_setting(test_db, "does_not_exist") is None
    assert get_setting(test_db, "does_not_exist", default="fallback") == "fallback"


def test_set_setting_updates_existing_and_creates_new_key(test_db):
    set_setting(test_db, "default_shipping_charge", 200000)
    assert get_setting(test_db, "default_shipping_charge") == "200000"

    set_setting(test_db, "custom_key", "hello")
    assert get_setting(test_db, "custom_key") == "hello"


def test_set_setting_rejects_negative_money(test_db):
    with pytest.raises(ValidationError):
        set_setting(test_db, "default_shipping_charge", -10)
    with pytest.raises(ValidationError):
        set_setting(test_db, "default_postage_estimate", -1)


def test_set_setting_rejects_non_positive_window(test_db):
    with pytest.raises(ValidationError):
        set_setting(test_db, "postage_estimate_window", 0)
    with pytest.raises(ValidationError):
        set_setting(test_db, "postage_estimate_window", -3)


def test_set_setting_rejects_invalid_timezone(test_db):
    with pytest.raises(ValidationError):
        set_setting(test_db, "timezone", "Not/AZone")


def test_set_setting_accepts_valid_timezone(test_db):
    set_setting(test_db, "timezone", "UTC")
    assert get_setting(test_db, "timezone") == "UTC"


def test_get_channel_settings_seeded_rows(test_db):
    website = get_channel_settings(test_db, "WEBSITE")
    assert website["applies_shipping_charge"] == 1
    assert website["applies_postage"] == 1
    assert website["default_packaging_kit_id"] is None

    in_person = get_channel_settings(test_db, "IN_PERSON")
    assert in_person["applies_shipping_charge"] == 0
    assert in_person["applies_postage"] == 0


def test_get_channel_settings_rejects_invalid_channel(test_db):
    with pytest.raises(ValidationError):
        get_channel_settings(test_db, "NOT_A_CHANNEL")


def test_update_channel_settings_updates_only_given_fields(test_db):
    update_channel_settings(test_db, "IN_PERSON", applies_shipping_charge=1)
    updated = get_channel_settings(test_db, "IN_PERSON")
    assert updated["applies_shipping_charge"] == 1
    assert updated["applies_postage"] == 0  # untouched


def test_update_channel_settings_rejects_bad_boolean(test_db):
    with pytest.raises(ValidationError):
        update_channel_settings(test_db, "WEBSITE", applies_postage=2)


def test_update_channel_settings_rejects_missing_packaging_kit(test_db):
    with pytest.raises(NotFoundError):
        update_channel_settings(test_db, "WEBSITE", default_packaging_kit_id=999)


def test_update_channel_settings_accepts_and_clears_packaging_kit(test_db):
    kit_id = test_db.execute(
        "INSERT INTO packaging_kits (name) VALUES ('Standard Box')"
    ).lastrowid
    test_db.commit()

    update_channel_settings(test_db, "WEBSITE", default_packaging_kit_id=kit_id)
    updated = get_channel_settings(test_db, "WEBSITE")
    assert updated["default_packaging_kit_id"] == kit_id

    update_channel_settings(test_db, "WEBSITE", default_packaging_kit_id=None)
    cleared = get_channel_settings(test_db, "WEBSITE")
    assert cleared["default_packaging_kit_id"] is None
