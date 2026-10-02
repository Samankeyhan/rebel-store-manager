import pytest

from db.categories import create_category, deactivate_category
from db.materials import (
    add_material,
    deactivate_material,
    get_low_stock_materials,
    get_material,
    list_materials,
    reactivate_material,
    set_material_category,
)
from tests.helpers import cat


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


def test_reactivate_material(test_db):
    material_id = add_material(test_db, "Old Stock", "STOCK", 100, initial_stock=5)
    deactivate_material(test_db, material_id)
    reactivate_material(test_db, material_id)

    material = get_material(test_db, material_id)
    assert material["is_active"] == 1
    assert material["current_stock"] == 5
    assert any(m["id"] == material_id for m in list_materials(test_db, active_only=True))


def test_material_category_defaults_to_none(test_db):
    material = get_material(test_db, add_material(test_db, "Ink", "STOCK", 10))
    assert material["category_id"] is None
    assert material["category_name"] is None
    assert material["parent_category_id"] is None
    assert material["parent_category_name"] is None


def test_add_material_with_subcategory(test_db):
    printing = create_category(test_db, "MATERIAL", "چاپ")
    a3 = create_category(test_db, "MATERIAL", "A3", parent_id=printing)
    material_id = add_material(test_db, "A3 Print", "SERVICE", 2000, category_id=a3)

    material = get_material(test_db, material_id)
    assert material["category_id"] == a3
    assert material["category_name"] == "A3"
    assert material["parent_category_id"] == printing
    assert material["parent_category_name"] == "چاپ"
    assert list_materials(test_db)[0]["category_name"] == "A3"


def test_add_material_rejects_product_category(test_db):
    with pytest.raises(ValueError, match="PRODUCT category") as exc_info:
        add_material(test_db, "Ink", "STOCK", 10, category_id=cat(test_db, "VINYL"))
    assert exc_info.value.field == "category_id"


def test_add_material_rejects_unknown_inactive_or_parent_category(test_db):
    printing = create_category(test_db, "MATERIAL", "چاپ")
    create_category(test_db, "MATERIAL", "A3", parent_id=printing)
    old = create_category(test_db, "MATERIAL", "قدیمی")
    deactivate_category(test_db, old)

    for category_id, message in ((9999, "does not exist"), (old, "inactive"), (printing, "has subcategories")):
        with pytest.raises(ValueError, match=message) as exc_info:
            add_material(test_db, "Ink", "STOCK", 10, category_id=category_id)
        assert exc_info.value.field == "category_id"
    assert list_materials(test_db, active_only=False) == []


def test_set_material_category(test_db):
    packaging = create_category(test_db, "MATERIAL", "بسته‌بندی")
    material_id = add_material(test_db, "Box", "STOCK", 10)

    set_material_category(test_db, material_id, packaging)
    assert get_material(test_db, material_id)["category_name"] == "بسته‌بندی"

    with pytest.raises(ValueError, match="PRODUCT category"):
        set_material_category(test_db, material_id, cat(test_db, "OTHER"))
    with pytest.raises(ValueError, match="does not exist"):
        set_material_category(test_db, 9999, packaging)
