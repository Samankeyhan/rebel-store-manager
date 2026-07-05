import pytest

from db.suppliers import (
    add_supplier,
    get_supplier,
    list_suppliers,
    update_supplier,
)


def test_add_and_list_suppliers(test_db):
    id1 = add_supplier(
        test_db,
        "Alpha Pressing",
        phone="555-0100",
        email="alpha@example.com",
    )
    id2 = add_supplier(test_db, "Beta Vinyl Co")

    suppliers = list_suppliers(test_db)
    assert len(suppliers) == 2
    assert suppliers[0]["name"] == "Alpha Pressing"
    assert suppliers[1]["name"] == "Beta Vinyl Co"

    supplier = get_supplier(test_db, id1)
    assert supplier is not None
    assert supplier["phone"] == "555-0100"
    assert supplier["email"] == "alpha@example.com"


def test_get_supplier_returns_none_for_missing(test_db):
    assert get_supplier(test_db, 9999) is None


def test_empty_name_raises_value_error(test_db):
    with pytest.raises(ValueError, match="name is required"):
        add_supplier(test_db, "   ")


def test_update_supplier(test_db):
    supplier_id = add_supplier(
        test_db,
        "Gamma Records",
        phone="111",
        email="gamma@example.com",
        website="https://gamma.example",
        notes="Primary vendor",
    )

    update_supplier(test_db, supplier_id, phone="222")

    supplier = get_supplier(test_db, supplier_id)
    assert supplier["phone"] == "222"
    assert supplier["name"] == "Gamma Records"
    assert supplier["email"] == "gamma@example.com"
    assert supplier["website"] == "https://gamma.example"
    assert supplier["notes"] == "Primary vendor"


def test_update_nonexistent_supplier_raises(test_db):
    with pytest.raises(ValueError, match="Supplier with id 9999 does not exist"):
        update_supplier(test_db, 9999, phone="000")
