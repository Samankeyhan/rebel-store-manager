import pytest

from db.categories import create_category, deactivate_category
from db.products import (
    add_product,
    deactivate_product,
    get_product,
    list_products,
    reactivate_product,
    set_made_to_order,
    set_product_category,
    update_product_prices,
)
from db.recipes import add_recipe_item
from db.materials import add_material
from tests.helpers import cat


def test_add_and_get_product(test_db):
    product_id = add_product(test_db, "Test Vinyl", cat(test_db, "VINYL"), 2500, 1800)
    product = get_product(test_db, product_id)

    assert product is not None
    assert product["id"] == product_id
    assert product["name"] == "Test Vinyl"
    assert product["category"] is None  # legacy code column; new products leave it empty
    assert product["category_id"] == cat(test_db, "VINYL")
    assert product["category_name"] == "وینیل"
    assert product["parent_category_id"] is None
    assert product["parent_category_name"] is None
    assert product["retail_price"] == 2500
    assert product["wholesale_price"] == 1800
    assert product["current_stock"] == 0
    assert product["unit_cost"] is None
    assert product["is_active"] == 1


def test_list_products_ordered_by_name(test_db):
    add_product(test_db, "Zebra Album", cat(test_db, "ALBUM"), 1000, 800)
    add_product(test_db, "Alpha Cassette", cat(test_db, "CASSETTE"), 500, 400)

    products = list_products(test_db)
    names = [p["name"] for p in products]
    assert names == sorted(names)
    assert len(products) == 2


def test_negative_retail_price_raises_value_error(test_db):
    with pytest.raises(ValueError, match="retail_price must be >= 0"):
        add_product(test_db, "Bad Product", cat(test_db, "OTHER"), -100, 800)


def test_negative_wholesale_price_raises_value_error(test_db):
    with pytest.raises(ValueError, match="wholesale_price must be >= 0"):
        add_product(test_db, "Bad Product", cat(test_db, "OTHER"), 1000, -50)


def test_update_product_prices(test_db):
    product_id = add_product(test_db, "Poster", cat(test_db, "POSTER"), 1000, 800)

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
    product_id = add_product(test_db, "Sticker", cat(test_db, "STICKER"), 100, 80)
    with pytest.raises(ValueError, match="retail_price must be >= 0"):
        update_product_prices(test_db, product_id, retail_price=-1)


def test_deactivate_product(test_db):
    product_id = add_product(test_db, "Old T-Shirt", cat(test_db, "TSHIRT"), 2000, 1500)
    deactivate_product(test_db, product_id)

    product = get_product(test_db, product_id)
    assert product is not None
    assert product["is_active"] == 0

    active = list_products(test_db, active_only=True)
    assert all(p["id"] != product_id for p in active)


def test_reactivate_product(test_db):
    product_id = add_product(test_db, "Old T-Shirt", cat(test_db, "TSHIRT"), 2000, 1500)
    deactivate_product(test_db, product_id)
    reactivate_product(test_db, product_id)

    assert get_product(test_db, product_id)["is_active"] == 1
    active = list_products(test_db, active_only=True)
    assert any(p["id"] == product_id for p in active)


def test_reactivate_active_product_is_a_no_op(test_db):
    product_id = add_product(test_db, "T-Shirt", cat(test_db, "TSHIRT"), 2000, 1500)
    reactivate_product(test_db, product_id)
    assert get_product(test_db, product_id)["is_active"] == 1

    all_products = list_products(test_db, active_only=False)
    assert any(p["id"] == product_id for p in all_products)


def test_lighter_category_accepted(test_db):
    product_id = add_product(test_db, "Zippo", cat(test_db, "فندک"), 500000, 400000)
    assert get_product(test_db, product_id)["category_name"] == "فندک"


def test_add_product_in_subcategory_returns_parent_name(test_db):
    lighters = cat(test_db, "فندک")
    big = create_category(test_db, "PRODUCT", "فندک بزرگ", parent_id=lighters)
    product_id = add_product(test_db, "Big Zippo", big, 900000, 700000)

    product = get_product(test_db, product_id)
    assert product["category_id"] == big
    assert product["category_name"] == "فندک بزرگ"
    assert product["parent_category_id"] == lighters
    assert product["parent_category_name"] == "فندک"
    assert list_products(test_db)[0]["parent_category_name"] == "فندک"


def _assert_category_error(exc_info):
    assert exc_info.value.field == "category_id"


def test_add_product_unknown_category_raises(test_db):
    with pytest.raises(ValueError, match="does not exist") as exc_info:
        add_product(test_db, "Bad Product", 9999, 1000, 800)
    _assert_category_error(exc_info)


def test_add_product_material_category_raises(test_db):
    mat_cat = create_category(test_db, "MATERIAL", "چاپ")
    with pytest.raises(ValueError, match="MATERIAL category") as exc_info:
        add_product(test_db, "Bad Product", mat_cat, 1000, 800)
    _assert_category_error(exc_info)


def test_add_product_inactive_category_raises(test_db):
    unused = create_category(test_db, "PRODUCT", "کلاه")
    deactivate_category(test_db, unused)
    with pytest.raises(ValueError, match="inactive") as exc_info:
        add_product(test_db, "Bad Product", unused, 1000, 800)
    _assert_category_error(exc_info)


def test_add_product_to_parent_with_active_subcategories_raises(test_db):
    lighters = cat(test_db, "فندک")
    create_category(test_db, "PRODUCT", "فندک بزرگ", parent_id=lighters)
    with pytest.raises(ValueError, match="has subcategories") as exc_info:
        add_product(test_db, "Ambiguous", lighters, 1000, 800)
    _assert_category_error(exc_info)


def test_parent_is_assignable_again_once_its_subcategories_are_inactive(test_db):
    lighters = cat(test_db, "فندک")
    big = create_category(test_db, "PRODUCT", "فندک بزرگ", parent_id=lighters)
    deactivate_category(test_db, big)
    product_id = add_product(test_db, "Zippo", lighters, 1000, 800)
    assert get_product(test_db, product_id)["category_id"] == lighters


def test_set_product_category_moves_product(test_db):
    lighters = cat(test_db, "فندک")
    product_id = add_product(test_db, "Zippo", lighters, 1000, 800)
    big = create_category(test_db, "PRODUCT", "فندک بزرگ", parent_id=lighters)

    set_product_category(test_db, product_id, big)
    assert get_product(test_db, product_id)["category_id"] == big


def test_set_product_category_validates(test_db):
    lighters = cat(test_db, "فندک")
    product_id = add_product(test_db, "Zippo", lighters, 1000, 800)
    create_category(test_db, "PRODUCT", "فندک بزرگ", parent_id=lighters)
    mat_cat = create_category(test_db, "MATERIAL", "چاپ")

    with pytest.raises(ValueError, match="has subcategories"):
        set_product_category(test_db, product_id, lighters)
    with pytest.raises(ValueError, match="MATERIAL category"):
        set_product_category(test_db, product_id, mat_cat)
    with pytest.raises(ValueError, match="does not exist"):
        set_product_category(test_db, 9999, lighters)
    assert get_product(test_db, product_id)["category_id"] == lighters


def test_add_product_defaults_made_to_order_false(test_db):
    product_id = add_product(test_db, "Test Vinyl", cat(test_db, "VINYL"), 2500, 1800)
    assert get_product(test_db, product_id)["made_to_order"] == 0


def test_add_product_made_to_order_true(test_db):
    product_id = add_product(test_db, "CD Album", cat(test_db, "ALBUM"), 2500, 1800, made_to_order=True)
    assert get_product(test_db, product_id)["made_to_order"] == 1


def test_list_products_includes_made_to_order(test_db):
    add_product(test_db, "MTO Product", cat(test_db, "ALBUM"), 1000, 800, made_to_order=True)
    products = list_products(test_db)
    assert products[0]["made_to_order"] == 1


def test_set_made_to_order_requires_recipe(test_db):
    product_id = add_product(test_db, "No Recipe Product", cat(test_db, "ALBUM"), 1000, 800)

    with pytest.raises(ValueError, match="no recipe") as exc_info:
        set_made_to_order(test_db, product_id, True)
    assert exc_info.value.field == "made_to_order"

    assert get_product(test_db, product_id)["made_to_order"] == 0


def test_set_made_to_order_succeeds_with_recipe(test_db):
    product_id = add_product(test_db, "Recipe Product", cat(test_db, "ALBUM"), 1000, 800)
    material_id = add_material(test_db, "Blank CD", "STOCK", 1000, initial_stock=10)
    add_recipe_item(test_db, product_id, material_id, 1)

    set_made_to_order(test_db, product_id, True)
    assert get_product(test_db, product_id)["made_to_order"] == 1

    set_made_to_order(test_db, product_id, False)
    assert get_product(test_db, product_id)["made_to_order"] == 0


def test_set_made_to_order_nonexistent_product_raises(test_db):
    with pytest.raises(ValueError, match="does not exist"):
        set_made_to_order(test_db, 9999, True)
