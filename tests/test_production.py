import pytest

from db.materials import add_material, get_material
from db.products import add_product, get_product
from db.recipes import add_recipe_item
from db.production import (
    get_production_batch,
    list_production_batches,
    run_production_batch,
)


@pytest.fixture
def production_setup(test_db):
    product_id = add_product(test_db, "Test Vinyl", "VINYL", 3000, 2000)
    sleeves_id = add_material(
        test_db, "Vinyl Sleeves", "STOCK", 25, initial_stock=100
    )
    mastering_id = add_material(test_db, "Mastering", "SERVICE", 5000)
    label_id = add_material(test_db, "Labels", "STOCK", 10, initial_stock=500)

    add_recipe_item(test_db, product_id, sleeves_id, 1)
    add_recipe_item(test_db, product_id, mastering_id, 1)
    add_recipe_item(test_db, product_id, label_id, 2)

    return {
        "product_id": product_id,
        "sleeves_id": sleeves_id,
        "mastering_id": mastering_id,
        "label_id": label_id,
    }


def _count_rows(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _get_material_stock(conn, material_id: int) -> float:
    return get_material(conn, material_id)["current_stock"]


def test_run_production_batch_happy_path(test_db, production_setup):
    product_id = production_setup["product_id"]
    sleeves_id = production_setup["sleeves_id"]
    mastering_id = production_setup["mastering_id"]
    label_id = production_setup["label_id"]
    quantity = 5

    batch_id = run_production_batch(test_db, product_id, quantity, notes="Test run")

    assert batch_id == 1
    assert _get_material_stock(test_db, sleeves_id) == 95
    assert _get_material_stock(test_db, label_id) == 490
    assert get_material(test_db, mastering_id)["current_stock"] is None

    product = get_product(test_db, product_id)
    assert product["current_stock"] == quantity
    # 1*25 + 1*5000 + 2*10 = 5045 per unit
    assert product["unit_cost"] == 5045

    batch = get_production_batch(test_db, batch_id)
    assert batch["batch"]["quantity_produced"] == quantity
    assert batch["batch"]["unit_cost"] == 5045
    assert batch["batch"]["notes"] == "Test run"
    assert len(batch["materials"]) == 3

    by_material = {m["material_id"]: m for m in batch["materials"]}
    assert by_material[sleeves_id]["quantity_used"] == 5
    assert by_material[sleeves_id]["unit_cost_at_time"] == 25
    assert by_material[mastering_id]["quantity_used"] == 5
    assert by_material[mastering_id]["unit_cost_at_time"] == 5000
    assert by_material[label_id]["quantity_used"] == 10
    assert by_material[label_id]["unit_cost_at_time"] == 10

    movements = test_db.execute(
        "SELECT * FROM stock_movements ORDER BY id"
    ).fetchall()
    assert len(movements) == 3  # 2 STOCK materials + 1 product output

    consumption = [
        m for m in movements if m["reason"] == "PRODUCTION_CONSUMPTION"
    ]
    assert len(consumption) == 2
    consumed_ids = {m["item_id"] for m in consumption}
    assert consumed_ids == {sleeves_id, label_id}
    for move in consumption:
        assert move["item_type"] == "MATERIAL"
        assert move["reference_production_batch_id"] == batch_id
        assert move["quantity_change"] < 0

    output = [
        m for m in movements if m["reason"] == "PRODUCTION_OUTPUT"
    ]
    assert len(output) == 1
    assert output[0]["item_type"] == "PRODUCT"
    assert output[0]["item_id"] == product_id
    assert output[0]["quantity_change"] == quantity
    assert output[0]["reference_production_batch_id"] == batch_id


def test_insufficient_stock_rolls_back_entire_batch(test_db, production_setup):
    product_id = production_setup["product_id"]
    sleeves_id = production_setup["sleeves_id"]
    label_id = production_setup["label_id"]

    sleeves_before = _get_material_stock(test_db, sleeves_id)
    labels_before = _get_material_stock(test_db, label_id)
    product_before = get_product(test_db, product_id)["current_stock"]
    batches_before = _count_rows(test_db, "production_batches")
    movements_before = _count_rows(test_db, "stock_movements")

    # Labels need 2 * 300 = 600 but only 500 available
    with pytest.raises(ValueError, match="Insufficient stock for 'Labels'"):
        run_production_batch(test_db, product_id, 300)

    assert _get_material_stock(test_db, sleeves_id) == sleeves_before
    assert _get_material_stock(test_db, label_id) == labels_before
    assert get_product(test_db, product_id)["current_stock"] == product_before
    assert _count_rows(test_db, "production_batches") == batches_before
    assert _count_rows(test_db, "stock_movements") == movements_before


def test_no_recipe_raises_value_error(test_db):
    product_id = add_product(test_db, "No Recipe Product", "OTHER", 100, 80)

    with pytest.raises(ValueError, match="has no recipe defined"):
        run_production_batch(test_db, product_id, 1)

    assert _count_rows(test_db, "production_batches") == 0
    assert _count_rows(test_db, "stock_movements") == 0


def test_invalid_quantity_raises_value_error(test_db, production_setup):
    product_id = production_setup["product_id"]

    with pytest.raises(ValueError, match="quantity_produced must be > 0"):
        run_production_batch(test_db, product_id, 0)

    with pytest.raises(ValueError, match="quantity_produced must be > 0"):
        run_production_batch(test_db, product_id, -1)


def test_nonexistent_product_raises_value_error(test_db):
    with pytest.raises(ValueError, match="Product with id 9999 does not exist"):
        run_production_batch(test_db, 9999, 1)


def test_service_materials_no_stock_movements(test_db, production_setup):
    product_id = production_setup["product_id"]
    mastering_id = production_setup["mastering_id"]

    batch_id = run_production_batch(test_db, product_id, 1)

    service_movements = test_db.execute(
        """
        SELECT * FROM stock_movements
        WHERE item_type = 'MATERIAL' AND item_id = ?
        """,
        (mastering_id,),
    ).fetchall()
    assert service_movements == []

    batch = get_production_batch(test_db, batch_id)
    mastering_row = next(
        m for m in batch["materials"] if m["material_id"] == mastering_id
    )
    assert mastering_row["material_type"] == "SERVICE"
    assert mastering_row["quantity_used"] == 1
    assert mastering_row["unit_cost_at_time"] == 5000


def test_two_batches_freeze_costs_independently(test_db, production_setup):
    product_id = production_setup["product_id"]
    sleeves_id = production_setup["sleeves_id"]

    batch1_id = run_production_batch(test_db, product_id, 2)
    assert get_production_batch(test_db, batch1_id)["batch"]["unit_cost"] == 5045

    test_db.execute(
        "UPDATE materials SET unit_cost = 50 WHERE id = ?", (sleeves_id,)
    )
    test_db.commit()

    batch2_id = run_production_batch(test_db, product_id, 2)
    # 1*50 + 1*5000 + 2*10 = 5070 per unit
    assert get_production_batch(test_db, batch2_id)["batch"]["unit_cost"] == 5070

    batch1_materials = get_production_batch(test_db, batch1_id)["materials"]
    sleeves_row = next(
        m for m in batch1_materials if m["material_id"] == sleeves_id
    )
    assert sleeves_row["unit_cost_at_time"] == 25

    assert get_product(test_db, product_id)["unit_cost"] == 5070


def test_list_production_batches(test_db, production_setup):
    product_id = production_setup["product_id"]
    run_production_batch(test_db, product_id, 3)
    run_production_batch(test_db, product_id, 2)

    all_batches = list_production_batches(test_db)
    assert len(all_batches) == 2
    assert all_batches[0]["quantity_produced"] == 2
    assert all_batches[1]["quantity_produced"] == 3

    filtered = list_production_batches(test_db, product_id=product_id)
    assert len(filtered) == 2
    assert all(b["product_name"] == "Test Vinyl" for b in filtered)
