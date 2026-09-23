import pytest

from db import packaging
from db.errors import ConflictError, NotFoundError, ValidationError
from db.materials import add_material, deactivate_material


def test_create_kit_and_list_kits(test_db):
    kit_id = packaging.create_kit(test_db, "Standard box")

    kits = packaging.list_kits(test_db)
    assert len(kits) == 1
    assert kits[0]["id"] == kit_id
    assert kits[0]["name"] == "Standard box"
    assert kits[0]["is_active"] == 1


def test_get_kit_returns_items_and_cost(test_db):
    box_id = add_material(test_db, "Box", "STOCK", unit_cost=30000, initial_stock=10)
    filler_id = add_material(test_db, "Filler", "STOCK", unit_cost=10000, initial_stock=10)
    kit_id = packaging.create_kit(test_db, "Standard box")
    packaging.add_kit_item(test_db, kit_id, box_id, 1)
    packaging.add_kit_item(test_db, kit_id, filler_id, 1)

    kit = packaging.get_kit(test_db, kit_id)
    assert kit["name"] == "Standard box"
    assert kit["kit_cost"] == 40000
    assert len(kit["items"]) == 2
    assert {item["material_id"] for item in kit["items"]} == {box_id, filler_id}


def test_get_kit_nonexistent_raises_not_found(test_db):
    with pytest.raises(NotFoundError):
        packaging.get_kit(test_db, 9999)


def test_add_kit_item_rejects_service_material(test_db):
    kit_id = packaging.create_kit(test_db, "Kit")
    service_id = add_material(test_db, "Printing", "SERVICE", unit_cost=5000)

    with pytest.raises(ValidationError):
        packaging.add_kit_item(test_db, kit_id, service_id, 1)


def test_add_kit_item_rejects_inactive_material(test_db):
    kit_id = packaging.create_kit(test_db, "Kit")
    box_id = add_material(test_db, "Box", "STOCK", unit_cost=1000, initial_stock=10)
    deactivate_material(test_db, box_id)

    with pytest.raises(ValidationError):
        packaging.add_kit_item(test_db, kit_id, box_id, 1)


def test_add_kit_item_duplicate_raises_conflict(test_db):
    kit_id = packaging.create_kit(test_db, "Kit")
    box_id = add_material(test_db, "Box", "STOCK", unit_cost=1000, initial_stock=10)
    packaging.add_kit_item(test_db, kit_id, box_id, 1)

    with pytest.raises(ConflictError):
        packaging.add_kit_item(test_db, kit_id, box_id, 2)


def test_update_kit_item_changes_quantity(test_db):
    kit_id = packaging.create_kit(test_db, "Kit")
    box_id = add_material(test_db, "Box", "STOCK", unit_cost=1000, initial_stock=10)
    packaging.add_kit_item(test_db, kit_id, box_id, 1)

    packaging.update_kit_item(test_db, kit_id, box_id, 3)

    kit = packaging.get_kit(test_db, kit_id)
    assert kit["items"][0]["quantity"] == 3
    assert kit["kit_cost"] == 3000


def test_update_kit_item_missing_raises_not_found(test_db):
    kit_id = packaging.create_kit(test_db, "Kit")

    with pytest.raises(NotFoundError):
        packaging.update_kit_item(test_db, kit_id, 9999, 1)


def test_remove_kit_item(test_db):
    kit_id = packaging.create_kit(test_db, "Kit")
    box_id = add_material(test_db, "Box", "STOCK", unit_cost=1000, initial_stock=10)
    packaging.add_kit_item(test_db, kit_id, box_id, 1)

    packaging.remove_kit_item(test_db, kit_id, box_id)

    assert packaging.get_kit(test_db, kit_id)["items"] == []


def test_remove_kit_item_missing_raises_not_found(test_db):
    kit_id = packaging.create_kit(test_db, "Kit")

    with pytest.raises(NotFoundError):
        packaging.remove_kit_item(test_db, kit_id, 9999)


def test_deactivate_kit(test_db):
    kit_id = packaging.create_kit(test_db, "Kit")

    packaging.deactivate_kit(test_db, kit_id)

    assert packaging.list_kits(test_db) == []
    all_kits = packaging.list_kits(test_db, active_only=False)
    assert all_kits[0]["is_active"] == 0
