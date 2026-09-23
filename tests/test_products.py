import pytest

from db.products import (
    VALID_CATEGORIES,
    add_product,
    deactivate_product,
    get_product,
    list_products,
    set_made_to_order,
    update_product_prices,
)
from db.recipes import add_recipe_item
from db.materials import add_material


def test_add_and_get_product(test_db):
    product_id = add_product(test_db, "Test Vinyl", "VINYL", 2500, 1800)
    product = get_product(test_db, product_id)

    assert product is not None
    assert product["id"] == product_id
    assert product["name"] == "Test Vinyl"
    assert product["category"] == "VINYL"
    assert product["retail_price"] == 2500
    assert product["wholesale_price"] == 1800
    assert product["current_stock"] == 0
    assert product["unit_cost"] is None
    assert product["is_active"] == 1


def test_list_products_ordered_by_name(test_db):
    add_product(test_db, "Zebra Album", "ALBUM", 1000, 800)
    add_product(test_db, "Alpha Cassette", "CASSETTE", 500, 400)

    products = list_products(test_db)
    names = [p["name"] for p in products]
    assert names == sorted(names)
    assert len(products) == 2


def test_invalid_category_raises_value_error(test_db):
    with pytest.raises(ValueError, match="Invalid category"):
        add_product(test_db, "Bad Product", "INVALID", 1000, 800)


def test_negative_retail_price_raises_value_error(test_db):
    with pytest.raises(ValueError, match="retail_price must be >= 0"):
        add_product(test_db, "Bad Product", "OTHER", -100, 800)


def test_negative_wholesale_price_raises_value_error(test_db):
    with pytest.raises(ValueError, match="wholesale_price must be >= 0"):
        add_product(test_db, "Bad Product", "OTHER", 1000, -50)


def test_update_product_prices(test_db):
    product_id = add_product(test_db, "Poster", "POSTER", 1000, 800)

    update_product_prices(test_db, product_id, retail_price=1200)
    product = get_product(test_db, product_id)
    assert product["retail_price"] == 1200
    assert product["wholesale_price"] == 800

    update_product_prices(test_db, product_id, wholesale_price=900)
    product = get_product(test_db, product_id)
    assert product["retail_price"] == 1200
    assert product["wholesale_price"] == 900


def test_update_product_prices_nonexistent_raises(test_db):
    with pytest.raises(ValueError, match="does not exist"):
        update_product_prices(test_db, 9999, retail_price=1000)


def test_update_product_prices_negative_raises(test_db):
    product_id = add_product(test_db, "Sticker", "STICKER", 100, 80)
    with pytest.raises(ValueError, match="retail_price must be >= 0"):
        update_product_prices(test_db, product_id, retail_price=-1)


def test_deactivate_product(test_db):
    product_id = add_product(test_db, "Old T-Shirt", "TSHIRT", 2000, 1500)
    deactivate_product(test_db, product_id)

    product = get_product(test_db, product_id)
    assert product is not None
    assert product["is_active"] == 0

    active = list_products(test_db, active_only=True)
    assert all(p["id"] != product_id for p in active)

    all_products = list_products(test_db, active_only=False)
    assert any(p["id"] == product_id for p in all_products)


def test_all_valid_categories(test_db):
    for category in VALID_CATEGORIES:
        product_id = add_product(test_db, f"Product {category}", category, 100, 80)
        assert get_product(test_db, product_id)["category"] == category


def test_lighter_category_accepted(test_db):
    product_id = add_product(test_db, "Zippo", "فندک", 500000, 400000)
    assert get_product(test_db, product_id)["category"] == "فندک"


def test_add_product_defaults_made_to_order_false(test_db):
    product_id = add_product(test_db, "Test Vinyl", "VINYL", 2500, 1800)
    assert get_product(test_db, product_id)["made_to_order"] == 0


def test_add_product_made_to_order_true(test_db):
    product_id = add_product(test_db, "CD Album", "ALBUM", 2500, 1800, made_to_order=True)
    assert get_product(test_db, product_id)["made_to_order"] == 1


def test_list_products_includes_made_to_order(test_db):
    add_product(test_db, "MTO Product", "ALBUM", 1000, 800, made_to_order=True)
    products = list_products(test_db)
    assert products[0]["made_to_order"] == 1


def test_set_made_to_order_requires_recipe(test_db):
    product_id = add_product(test_db, "No Recipe Product", "ALBUM", 1000, 800)

    with pytest.raises(ValueError, match="no recipe") as exc_info:
        set_made_to_order(test_db, product_id, True)
    assert exc_info.value.field == "made_to_order"

    assert get_product(test_db, product_id)["made_to_order"] == 0


def test_set_made_to_order_succeeds_with_recipe(test_db):
    product_id = add_product(test_db, "Recipe Product", "ALBUM", 1000, 800)
    material_id = add_material(test_db, "Blank CD", "STOCK", 1000, initial_stock=10)
    add_recipe_item(test_db, product_id, material_id, 1)

    set_made_to_order(test_db, product_id, True)
    assert get_product(test_db, product_id)["made_to_order"] == 1

    set_made_to_order(test_db, product_id, False)
    assert get_product(test_db, product_id)["made_to_order"] == 0


def test_set_made_to_order_nonexistent_product_raises(test_db):
    with pytest.raises(ValueError, match="does not exist"):
        set_made_to_order(test_db, 9999, True)
