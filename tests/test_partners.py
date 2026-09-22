import pytest

from db.partners import (
    add_partner,
    deactivate_partner,
    get_active_percentage_total,
    get_partner,
    list_partners,
    update_partner_percentage,
)


def test_add_partner_happy_path(test_db):
    partner_id = add_partner(
        test_db, "Alice", 50.0, phone="555-0100", email="alice@example.com"
    )
    partner = get_partner(test_db, partner_id)

    assert partner is not None
    assert partner["name"] == "Alice"
    assert partner["current_percentage"] == 50.0
    assert partner["phone"] == "555-0100"
    assert partner["email"] == "alice@example.com"
    assert partner["is_active"] == 1


def test_add_partner_percentage_zero_raises(test_db):
    with pytest.raises(ValueError, match="percentage must be > 0"):
        add_partner(test_db, "Bad Partner", 0)


def test_add_partner_percentage_over_100_raises(test_db):
    with pytest.raises(ValueError, match="percentage must be > 0"):
        add_partner(test_db, "Bad Partner", 100.1)


def test_update_partner_percentage_happy_path(test_db):
    partner_id = add_partner(test_db, "Bob", 40.0)
    update_partner_percentage(test_db, partner_id, 55.0)

    partner = get_partner(test_db, partner_id)
    assert partner["current_percentage"] == 55.0


def test_update_partner_percentage_validation(test_db):
    partner_id = add_partner(test_db, "Bob", 40.0)

    with pytest.raises(ValueError, match="new_percentage must be > 0"):
        update_partner_percentage(test_db, partner_id, 0)

    with pytest.raises(ValueError, match="new_percentage must be > 0"):
        update_partner_percentage(test_db, partner_id, 150)

    with pytest.raises(ValueError, match="does not exist"):
        update_partner_percentage(test_db, 9999, 50.0)


def test_update_partner_percentage_inactive_raises(test_db):
    partner_id = add_partner(test_db, "Inactive", 50.0)
    deactivate_partner(test_db, partner_id)

    with pytest.raises(ValueError, match="is not active"):
        update_partner_percentage(test_db, partner_id, 60.0)


def test_deactivate_partner_excludes_from_active_list(test_db):
    partner_id = add_partner(test_db, "Carol", 30.0)
    deactivate_partner(test_db, partner_id)

    partner = get_partner(test_db, partner_id)
    assert partner["is_active"] == 0

    active = list_partners(test_db, active_only=True)
    assert all(p["id"] != partner_id for p in active)

    all_partners = list_partners(test_db, active_only=False)
    assert any(p["id"] == partner_id for p in all_partners)


def test_get_active_percentage_total(test_db):
    add_partner(test_db, "Alice", 50.0)
    add_partner(test_db, "Bob", 30.0)
    inactive_id = add_partner(test_db, "Inactive", 20.0)
    deactivate_partner(test_db, inactive_id)

    assert get_active_percentage_total(test_db) == 80.0
