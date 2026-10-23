"""recipes.recipe_costs: the display-only recipe cost per product (accounting rules sections 2 and 13)."""

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from db.connection import get_connection, init_db
from db.materials import add_material
from db.orders import record_order
from db.products import add_product, get_product, list_products
from db.recipes import add_recipe_item, calculate_recipe_cost, recipe_costs
from db.reports import get_product_performance
from tests.helpers import cat


def _product(conn, name="Album", made_to_order=True):
    return add_product(conn, name, cat(conn, "ALBUM"), 570_000, 285_000, made_to_order=made_to_order)


def test_a_product_without_a_recipe_is_none(test_db):
    product_id = _product(test_db)
    assert recipe_costs(test_db)[product_id] == {
        "recipe_cost": None, "recipe_cost_status": "NONE", "recipe_cost_missing": [],
    }


def test_complete_recipe_cost_is_the_sum_of_the_lines(test_db):
    product_id = _product(test_db)
    cd = add_material(test_db, "Blank CD", "STOCK", 53_393, initial_stock=10)
    dye = add_material(test_db, "Disc Dye", "SERVICE", 10_000)
    add_recipe_item(test_db, product_id, cd, 1)
    add_recipe_item(test_db, product_id, dye, 0.5)
    row = recipe_costs(test_db)[product_id]
    assert row == {"recipe_cost": 58_393, "recipe_cost_status": "COMPLETE", "recipe_cost_missing": []}


def test_per_batch_lines_count_once(test_db):
    product_id = _product(test_db)
    cd = add_material(test_db, "Blank CD", "STOCK", 1_000, initial_stock=10)
    setup = add_material(test_db, "Setup", "SERVICE", 7_000)
    add_recipe_item(test_db, product_id, cd, 2)
    add_recipe_item(test_db, product_id, setup, 1, "PER_BATCH")
    assert recipe_costs(test_db)[product_id]["recipe_cost"] == 9_000


def test_a_cost_zero_material_makes_the_recipe_incomplete_and_names_it(test_db):
    product_id = _product(test_db)
    cd = add_material(test_db, "Blank CD", "STOCK", 1_000, initial_stock=10)
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=5)
    add_recipe_item(test_db, product_id, cd, 1)
    add_recipe_item(test_db, product_id, sticker, 1)
    row = recipe_costs(test_db)[product_id]
    assert row["recipe_cost"] is None  # never a cheap-looking 1,000
    assert row["recipe_cost_status"] == "INCOMPLETE"
    assert row["recipe_cost_missing"] == [{"id": sticker, "name": "Sticker"}]


def test_a_service_at_cost_zero_is_incomplete_too(test_db):
    product_id = _product(test_db)
    service = add_material(test_db, "Printing", "SERVICE", 0)
    add_recipe_item(test_db, product_id, service, 1)
    assert recipe_costs(test_db)[product_id]["recipe_cost_status"] == "INCOMPLETE"


def test_an_inactive_material_still_counts(test_db):
    product_id = _product(test_db)
    cd = add_material(test_db, "Blank CD", "STOCK", 1_000, initial_stock=10)
    add_recipe_item(test_db, product_id, cd, 3)
    test_db.execute("UPDATE materials SET is_active = 0 WHERE id = ?", (cd,))
    assert recipe_costs(test_db)[product_id]["recipe_cost"] == 3_000


def test_missing_materials_are_listed_by_name(test_db):
    product_id = _product(test_db)
    b = add_material(test_db, "Bb", "STOCK", 0, initial_stock=1)
    a = add_material(test_db, "Aa", "STOCK", 0, initial_stock=1)
    add_recipe_item(test_db, product_id, b, 1)
    add_recipe_item(test_db, product_id, a, 1)
    assert recipe_costs(test_db)[product_id]["recipe_cost_missing"] == [
        {"id": a, "name": "Aa"}, {"id": b, "name": "Bb"},
    ]


def test_product_ids_filter_and_unknown_ids(test_db):
    first, second = _product(test_db, "One"), _product(test_db, "Two")
    cd = add_material(test_db, "Blank CD", "STOCK", 1_000, initial_stock=10)
    add_recipe_item(test_db, first, cd, 1)
    assert set(recipe_costs(test_db, [first])) == {first}
    assert set(recipe_costs(test_db, [second, 9999])) == {second}
    assert recipe_costs(test_db, []) == {}
    assert set(recipe_costs(test_db)) == {first, second}


def test_recipe_cost_equals_calculate_recipe_cost_and_the_sale_make_cost(test_db):
    product_id = _product(test_db)
    cd = add_material(test_db, "Blank CD", "STOCK", 53_393, initial_stock=10)
    dye = add_material(test_db, "Disc Dye", "SERVICE", 10_000)
    nylon = add_material(test_db, "Nylon", "STOCK", 1_200_000, unit="kg", initial_stock=1)
    setup = add_material(test_db, "Setup", "SERVICE", 3_333)
    add_recipe_item(test_db, product_id, cd, 1)
    add_recipe_item(test_db, product_id, dye, 0.3333)
    add_recipe_item(test_db, product_id, nylon, 0.008)
    add_recipe_item(test_db, product_id, setup, 1, "PER_BATCH")
    cost = recipe_costs(test_db)[product_id]["recipe_cost"]
    assert cost == calculate_recipe_cost(test_db, product_id, 1)
    order_id = record_order(test_db, "IN_PERSON", [{"product_id": product_id, "quantity": 1, "unit_price": 570_000}])
    frozen = test_db.execute("SELECT unit_cost_at_time FROM order_items WHERE order_id = ?", (order_id,)).fetchone()[0]
    assert frozen == cost


def test_product_rows_carry_the_fields_and_unit_cost_is_untouched(test_db):
    product_id = _product(test_db)
    cd = add_material(test_db, "Blank CD", "STOCK", 1_000, initial_stock=10)
    add_recipe_item(test_db, product_id, cd, 2)
    for row in (get_product(test_db, product_id), next(p for p in list_products(test_db) if p["id"] == product_id)):
        assert row["recipe_cost"] == 2_000 and row["recipe_cost_status"] == "COMPLETE"
        assert row["unit_cost"] is None  # the estimate is never stored
    assert test_db.execute("SELECT unit_cost FROM products WHERE id = ?", (product_id,)).fetchone()[0] is None


def test_a_stored_weighted_average_is_never_overwritten_by_the_estimate(test_db):
    product_id = _product(test_db, made_to_order=False)
    cd = add_material(test_db, "Blank CD", "STOCK", 1_000, initial_stock=10)
    add_recipe_item(test_db, product_id, cd, 1)
    test_db.execute("UPDATE products SET unit_cost = 777 WHERE id = ?", (product_id,))
    row = get_product(test_db, product_id)
    assert row["unit_cost"] == 777 and row["recipe_cost"] == 1_000


def test_performance_rows_carry_the_estimate_and_the_frozen_totals_do_not_move(test_db):
    product_id = _product(test_db)
    cd = add_material(test_db, "Blank CD", "STOCK", 1_000, initial_stock=10)
    add_recipe_item(test_db, product_id, cd, 1)
    record_order(test_db, "IN_PERSON", [{"product_id": product_id, "quantity": 2, "unit_price": 570_000}])
    test_db.execute("UPDATE materials SET unit_cost = 5000 WHERE id = ?", (cd,))  # the price rose after the sale
    (row,) = get_product_performance(test_db)
    assert row["total_cost"] == 2_000  # frozen at sale time
    assert row["recipe_cost"] == 5_000 and row["recipe_cost_status"] == "COMPLETE" and row["unit_cost"] is None


# ------------------------------------------------------------------------------- API


@pytest.fixture
def api(tmp_path):
    db_path = str(tmp_path / "api.db")
    init_db(db_path)

    def override_get_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    seed = get_connection(db_path)
    try:
        yield TestClient(app), seed
    finally:
        seed.close()
        app.dependency_overrides.clear()


def test_api_products_and_report_expose_the_fields(api):
    client, conn = api
    product_id = _product(conn)
    cd = add_material(conn, "Blank CD", "STOCK", 1_000, initial_stock=10)
    sticker = add_material(conn, "Sticker", "STOCK", 0, initial_stock=5)
    add_recipe_item(conn, product_id, cd, 1)
    add_recipe_item(conn, product_id, sticker, 1)
    listed = client.get("/products").json()[0]
    assert listed["recipe_cost"] is None and listed["recipe_cost_status"] == "INCOMPLETE"
    assert listed["recipe_cost_missing"] == [{"id": sticker, "name": "Sticker"}]
    one = client.get(f"/products/{product_id}").json()
    assert one["recipe_cost_missing"] == listed["recipe_cost_missing"]
    conn.execute("UPDATE materials SET unit_cost = 500 WHERE id = ?", (sticker,))
    assert client.get(f"/products/{product_id}").json()["recipe_cost"] == 1_500
    record_order(conn, "IN_PERSON", [{"product_id": product_id, "quantity": 1, "unit_price": 570_000}])
    (report,) = client.get("/reports/products").json()
    assert report["recipe_cost"] == 1_500 and report["recipe_cost_status"] == "COMPLETE"
    assert report["recipe_cost_missing"] == [] and report["unit_cost"] is None
    assert report["total_cost"] == 1_500
    assert client.get("/catalog").json()["products"][0]["recipe_cost"] == 1_500
