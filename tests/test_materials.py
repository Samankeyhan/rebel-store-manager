import pytest

from db.materials import (
    add_material,
    deactivate_material,
    get_low_stock_materials,
    get_material,
    list_materials,
)


def test_add_and_get_stock_material(test_db):
    material_id = add_material(
        test_db, "CD Cases", "STOCK", 150, unit="piece", initial_stock=100
    )
    material = get_material(test_db, material_id)

    assert material is not None
    assert material["id"] == material_id
    assert material["name"] == "CD Cases"
    assert material["type"] == "STOCK"
    assert material["unit"] == "piece"
    assert material["current_stock"] == 100
    assert material["unit_cost"] == 150
    assert material["is_active"] == 1


def test_add_stock_material_default_stock(test_db):
    material_id = add_material(test_db, "Labels", "STOCK", 50)
    material = get_material(test_db, material_id)
    assert material["current_stock"] == 0


def test_add_service_material(test_db):
    material_id = add_material(test_db, "Mastering", "SERVICE", 5000)
    material = get_material(test_db, material_id)

    assert material["type"] == "SERVICE"
    assert material["current_stock"] is None
    assert material["unit"] == "piece"


def test_invalid_type_raises_value_error(test_db):
    with pytest.raises(ValueError, match="Invalid type"):
        add_material(test_db, "Bad Material", "INVALID", 100)


def test_negative_unit_cost_raises_value_error(test_db):
    with pytest.raises(ValueError, match="unit_cost must be >= 0"):
        add_material(test_db, "Bad Material", "STOCK", -10)


def test_service_with_initial_stock_raises_value_error(test_db):
    with pytest.raises(ValueError, match="SERVICE materials cannot have initial_stock"):
        add_material(test_db, "Mastering", "SERVICE", 5000, initial_stock=10)


def test_list_materials_ordered_by_name(test_db):
    add_material(test_db, "Zebra Paper", "STOCK", 10)
    add_material(test_db, "Alpha Ink", "STOCK", 20)

    materials = list_materials(test_db)
    names = [m["name"] for m in materials]
    assert names == sorted(names)
    assert len(materials) == 2


def test_deactivate_material(test_db):
    material_id = add_material(test_db, "Old Stock", "STOCK", 100)
    deactivate_material(test_db, material_id)

    material = get_material(test_db, material_id)
    assert material is not None
    assert material["is_active"] == 0

    active = list_materials(test_db, active_only=True)
    assert all(m["id"] != material_id for m in active)

    all_materials = list_materials(test_db, active_only=False)
    assert any(m["id"] == material_id for m in all_materials)


def test_get_low_stock_materials(test_db):
    low_id = add_material(test_db, "Low Stock", "STOCK", 10, initial_stock=5)
    ok_id = add_material(test_db, "OK Stock", "STOCK", 10, initial_stock=50)
    service_id = add_material(test_db, "Printing", "SERVICE", 100)

    low_stock = get_low_stock_materials(test_db, threshold=10)
    ids = {m["id"] for m in low_stock}

    assert low_id in ids
    assert ok_id not in ids
    assert service_id not in ids


def test_get_low_stock_excludes_inactive(test_db):
    material_id = add_material(test_db, "Deactivated Low", "STOCK", 10, initial_stock=2)
    deactivate_material(test_db, material_id)

    low_stock = get_low_stock_materials(test_db, threshold=10)
    assert all(m["id"] != material_id for m in low_stock)
