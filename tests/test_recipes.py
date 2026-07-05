import pytest

from db.materials import add_material
from db.products import add_product
from db.recipes import (
    add_recipe_item,
    calculate_recipe_cost,
    get_recipe,
    remove_recipe_item,
    update_recipe_item,
)


@pytest.fixture
def sample_product_and_materials(test_db):
    product_id = add_product(test_db, "Test Vinyl", "VINYL", 3000, 2000)
    sleeves_id = add_material(
        test_db, "Vinyl Sleeves", "STOCK", 25, initial_stock=100
    )
    mastering_id = add_material(test_db, "Mastering", "SERVICE", 5000)
    label_id = add_material(test_db, "Labels", "STOCK", 10, initial_stock=500)
    return {
        "product_id": product_id,
        "sleeves_id": sleeves_id,
        "mastering_id": mastering_id,
        "label_id": label_id,
    }


def test_add_and_get_recipe(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]
    sleeves_id = sample_product_and_materials["sleeves_id"]
    mastering_id = sample_product_and_materials["mastering_id"]
    label_id = sample_product_and_materials["label_id"]

    add_recipe_item(test_db, product_id, sleeves_id, 1)
    add_recipe_item(test_db, product_id, mastering_id, 1)
    add_recipe_item(test_db, product_id, label_id, 2)

    recipe = get_recipe(test_db, product_id)
    assert len(recipe) == 3

    by_name = {row["material_name"]: row for row in recipe}
    assert by_name["Labels"]["quantity_needed"] == 2
    assert by_name["Labels"]["material_type"] == "STOCK"
    assert by_name["Labels"]["material_unit"] == "piece"
    assert by_name["Labels"]["material_unit_cost"] == 10

    assert by_name["Mastering"]["quantity_needed"] == 1
    assert by_name["Mastering"]["material_type"] == "SERVICE"
    assert by_name["Mastering"]["material_unit_cost"] == 5000

    assert by_name["Vinyl Sleeves"]["quantity_needed"] == 1
    assert by_name["Vinyl Sleeves"]["material_unit_cost"] == 25

    names = [row["material_name"] for row in recipe]
    assert names == sorted(names)


def test_calculate_recipe_cost(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]
    sleeves_id = sample_product_and_materials["sleeves_id"]
    mastering_id = sample_product_and_materials["mastering_id"]
    label_id = sample_product_and_materials["label_id"]

    add_recipe_item(test_db, product_id, sleeves_id, 1)
    add_recipe_item(test_db, product_id, mastering_id, 1)
    add_recipe_item(test_db, product_id, label_id, 2)

    # 1*25 + 1*5000 + 2*10 = 5045
    assert calculate_recipe_cost(test_db, product_id) == 5045


def test_calculate_recipe_cost_empty_recipe(test_db):
    product_id = add_product(test_db, "Empty Product", "OTHER", 100, 80)
    assert calculate_recipe_cost(test_db, product_id) == 0


def test_calculate_recipe_cost_nonexistent_product(test_db):
    with pytest.raises(ValueError, match="does not exist"):
        calculate_recipe_cost(test_db, 9999)


def test_duplicate_recipe_item_raises_value_error(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]
    sleeves_id = sample_product_and_materials["sleeves_id"]

    add_recipe_item(test_db, product_id, sleeves_id, 1)

    with pytest.raises(ValueError, match="already in the recipe"):
        add_recipe_item(test_db, product_id, sleeves_id, 2)


def test_update_recipe_item(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]
    sleeves_id = sample_product_and_materials["sleeves_id"]

    add_recipe_item(test_db, product_id, sleeves_id, 1)
    update_recipe_item(test_db, product_id, sleeves_id, 3)

    recipe = get_recipe(test_db, product_id)
    assert recipe[0]["quantity_needed"] == 3


def test_update_recipe_item_nonexistent_raises(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]
    sleeves_id = sample_product_and_materials["sleeves_id"]

    with pytest.raises(ValueError, match="No recipe item found"):
        update_recipe_item(test_db, product_id, sleeves_id, 1)


def test_remove_recipe_item(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]
    sleeves_id = sample_product_and_materials["sleeves_id"]

    add_recipe_item(test_db, product_id, sleeves_id, 1)
    remove_recipe_item(test_db, product_id, sleeves_id)

    assert get_recipe(test_db, product_id) == []


def test_remove_recipe_item_nonexistent_raises(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]
    sleeves_id = sample_product_and_materials["sleeves_id"]

    with pytest.raises(ValueError, match="No recipe item found"):
        remove_recipe_item(test_db, product_id, sleeves_id)


def test_add_recipe_item_invalid_quantity(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]
    sleeves_id = sample_product_and_materials["sleeves_id"]

    with pytest.raises(ValueError, match="quantity_needed must be > 0"):
        add_recipe_item(test_db, product_id, sleeves_id, 0)

    with pytest.raises(ValueError, match="quantity_needed must be > 0"):
        add_recipe_item(test_db, product_id, sleeves_id, -1)


def test_update_recipe_item_invalid_quantity(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]
    sleeves_id = sample_product_and_materials["sleeves_id"]

    add_recipe_item(test_db, product_id, sleeves_id, 1)

    with pytest.raises(ValueError, match="quantity_needed must be > 0"):
        update_recipe_item(test_db, product_id, sleeves_id, 0)


def test_add_recipe_item_nonexistent_product(test_db, sample_product_and_materials):
    sleeves_id = sample_product_and_materials["sleeves_id"]

    with pytest.raises(ValueError, match="Product with id 9999 does not exist"):
        add_recipe_item(test_db, 9999, sleeves_id, 1)


def test_add_recipe_item_nonexistent_material(test_db, sample_product_and_materials):
    product_id = sample_product_and_materials["product_id"]

    with pytest.raises(ValueError, match="Material with id 9999 does not exist"):
        add_recipe_item(test_db, product_id, 9999, 1)
