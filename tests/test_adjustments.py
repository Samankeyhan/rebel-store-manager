import pytest

from db.adjustments import (
    get_stock_movement,
    list_stock_adjustments,
    record_stock_adjustment,
)
from db.materials import add_material, deactivate_material, get_material
from db.products import add_product, deactivate_product, get_product
from db.purchases import record_material_purchase, record_product_purchase


@pytest.fixture
def adjustment_setup(test_db):
    material_id = add_material(
        test_db, "Adjust Stock Material", "STOCK", 100, initial_stock=50
    )
    service_id = add_material(test_db, "Adjust Service", "SERVICE", 50)
    product_id = add_product(test_db, "Adjust Product", "VINYL", 3000, 2000)
    test_db.execute(
        "UPDATE products SET current_stock = 20 WHERE id = ?",
        (product_id,),
    )
    inactive_material_id = add_material(
        test_db, "Inactive Material", "STOCK", 100, initial_stock=5
    )
    deactivate_material(test_db, inactive_material_id)
    inactive_product_id = add_product(
        test_db, "Inactive Product", "OTHER", 1000, 800
    )
    deactivate_product(test_db, inactive_product_id)
    test_db.commit()
    return {
        "material_id": material_id,
        "service_id": service_id,
        "product_id": product_id,
        "inactive_material_id": inactive_material_id,
        "inactive_product_id": inactive_product_id,
    }


def _count_movements(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]


def test_waste_decreases_material_stock(adjustment_setup, test_db):
    material_id = adjustment_setup["material_id"]
    stock_before = get_material(test_db, material_id)["current_stock"]

    movement_id = record_stock_adjustment(
        test_db,
        "MATERIAL",
        material_id,
        -5,
        "WASTE",
        notes="Spilled",
        movement_date="2026-05-01",
    )

    assert get_material(test_db, material_id)["current_stock"] == stock_before - 5
    movement = get_stock_movement(test_db, movement_id)
    assert movement is not None
    assert movement["item_type"] == "MATERIAL"
    assert movement["item_id"] == material_id
    assert movement["item_name"] == "Adjust Stock Material"
    assert movement["quantity_change"] == -5
    assert movement["reason"] == "WASTE"
    assert movement["notes"] == "Spilled"
    assert movement["movement_date"] == "2026-05-01"


def test_waste_decreases_product_stock(adjustment_setup, test_db):
    product_id = adjustment_setup["product_id"]
    stock_before = get_product(test_db, product_id)["current_stock"]

    movement_id = record_stock_adjustment(
        test_db, "PRODUCT", product_id, -3, "WASTE"
    )

    assert get_product(test_db, product_id)["current_stock"] == stock_before - 3
    movement = get_stock_movement(test_db, movement_id)
    assert movement["quantity_change"] == -3
    assert movement["reason"] == "WASTE"
    assert movement["item_name"] == "Adjust Product"


def test_adjustment_increases_material_stock(adjustment_setup, test_db):
    material_id = adjustment_setup["material_id"]
    stock_before = get_material(test_db, material_id)["current_stock"]

    movement_id = record_stock_adjustment(
        test_db,
        "MATERIAL",
        material_id,
        7.5,
        "ADJUSTMENT",
        notes="Count correction",
    )

    assert get_material(test_db, material_id)["current_stock"] == stock_before + 7.5
    movement = get_stock_movement(test_db, movement_id)
    assert movement["quantity_change"] == 7.5
    assert movement["reason"] == "ADJUSTMENT"


def test_zero_quantity_change_raises(adjustment_setup, test_db):
    material_id = adjustment_setup["material_id"]
    with pytest.raises(ValueError, match="quantity_change must not be 0"):
        record_stock_adjustment(test_db, "MATERIAL", material_id, 0, "WASTE")


def test_invalid_reason_raises(adjustment_setup, test_db):
    material_id = adjustment_setup["material_id"]
    with pytest.raises(ValueError, match="Invalid reason"):
        record_stock_adjustment(test_db, "MATERIAL", material_id, -1, "SALE")


def test_invalid_item_type_raises(adjustment_setup, test_db):
    material_id = adjustment_setup["material_id"]
    with pytest.raises(ValueError, match="Invalid item_type"):
        record_stock_adjustment(test_db, "INVALID", material_id, -1, "WASTE")


def test_service_material_raises_and_rolls_back(adjustment_setup, test_db):
    service_id = adjustment_setup["service_id"]
    movements_before = _count_movements(test_db)

    with pytest.raises(ValueError, match="SERVICE"):
        record_stock_adjustment(test_db, "MATERIAL", service_id, -1, "WASTE")

    assert _count_movements(test_db) == movements_before


def test_nonexistent_item_raises(adjustment_setup, test_db):
    with pytest.raises(ValueError, match="does not exist"):
        record_stock_adjustment(test_db, "MATERIAL", 99999, -1, "WASTE")

    with pytest.raises(ValueError, match="does not exist"):
        record_stock_adjustment(test_db, "PRODUCT", 99999, -1, "WASTE")


def test_inactive_item_raises(adjustment_setup, test_db):
    with pytest.raises(ValueError, match="not active"):
        record_stock_adjustment(
            test_db,
            "MATERIAL",
            adjustment_setup["inactive_material_id"],
            -1,
            "WASTE",
        )

    with pytest.raises(ValueError, match="not active"):
        record_stock_adjustment(
            test_db,
            "PRODUCT",
            adjustment_setup["inactive_product_id"],
            -1,
            "WASTE",
        )


def test_list_stock_adjustments_excludes_other_reasons(adjustment_setup, test_db):
    material_id = adjustment_setup["material_id"]
    product_id = adjustment_setup["product_id"]

    waste_id = record_stock_adjustment(
        test_db,
        "MATERIAL",
        material_id,
        -2,
        "WASTE",
        movement_date="2026-04-10",
    )
    adj_id = record_stock_adjustment(
        test_db,
        "PRODUCT",
        product_id,
        4,
        "ADJUSTMENT",
        movement_date="2026-04-15",
    )

    record_material_purchase(test_db, material_id, 1, 100)
    record_product_purchase(test_db, product_id, 1, 200)
    test_db.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, movement_date)
        VALUES ('PRODUCT', ?, -1, 'SALE', '2026-04-12')
        """,
        (product_id,),
    )
    test_db.commit()

    all_rows = list_stock_adjustments(test_db)
    assert len(all_rows) == 2
    ids = {row["id"] for row in all_rows}
    assert waste_id in ids
    assert adj_id in ids
    assert all(row["reason"] in ("WASTE", "ADJUSTMENT") for row in all_rows)

    by_type = list_stock_adjustments(test_db, item_type="MATERIAL")
    assert len(by_type) == 1
    assert by_type[0]["id"] == waste_id

    by_reason = list_stock_adjustments(test_db, reason="ADJUSTMENT")
    assert len(by_reason) == 1
    assert by_reason[0]["id"] == adj_id

    in_april = list_stock_adjustments(
        test_db, start_date="2026-04-01", end_date="2026-04-30"
    )
    assert len(in_april) == 2

    empty = list_stock_adjustments(test_db, start_date="2099-01-01")
    assert empty == []


def test_get_stock_movement_returns_none_for_missing(adjustment_setup, test_db):
    assert get_stock_movement(test_db, 99999) is None
