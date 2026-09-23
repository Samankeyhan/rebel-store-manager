import pytest

from db.adjustments import record_stock_adjustment
from db.errors import InsufficientStockError, ValidationError
from db.materials import add_material, get_material
from db.orders import record_order
from db.products import add_product, get_product
from db.recipes import add_recipe_item, calculate_recipe_cost
from db.returns import process_return

# NOTE: the task's hand-calculated fixture claims calculate_recipe_cost(batch_qty=1)
# == 202,033, listing addends 77,333 + 53,393 + 26,664 + 20,000 + 10,000 + 9,600 +
# 3,750 + 1,290 as the proof. Those addends sum to 202,030, not 202,033 (a
# hand-arithmetic error in the fixture, not a code bug) — verified by direct
# addition and independently by db.recipes.calculate_recipe_cost itself. All
# expected values below use the corrected 202,030 base and values derived from it
# (176,015 instead of the fixture's 176,017). Flagged to the requester.
CD_ALBUM_UNIT_COST = 202_030


@pytest.fixture
def cd_album_setup(test_db):
    blank_cd_id = add_material(test_db, "Blank CD", "STOCK", 53_393, initial_stock=100)
    cd_case_id = add_material(test_db, "CD Case", "STOCK", 77_333, initial_stock=105)
    a3_print_id = add_material(test_db, "A3 Print", "SERVICE", 80_000)
    a4_print_id = add_material(test_db, "A4 Print", "SERVICE", 40_000)
    branding_id = add_material(test_db, "Branding Sticker", "STOCK", 3_750, initial_stock=128)
    qr_id = add_material(test_db, "QR Sticker", "STOCK", 1_290, initial_stock=186)
    disc_dye_id = add_material(test_db, "Disc Dye", "SERVICE", 10_000)
    shrink_nylon_id = add_material(
        test_db, "Shrink Nylon", "STOCK", 1_200_000, unit="kg", initial_stock=1
    )

    product_id = add_product(
        test_db, "CD Album", "ALBUM", 570_000, 285_000, made_to_order=True
    )
    add_recipe_item(test_db, product_id, blank_cd_id, 1)
    add_recipe_item(test_db, product_id, cd_case_id, 1)
    add_recipe_item(test_db, product_id, a3_print_id, 0.3333)
    add_recipe_item(test_db, product_id, a4_print_id, 0.5)
    add_recipe_item(test_db, product_id, branding_id, 1)
    add_recipe_item(test_db, product_id, qr_id, 1)
    add_recipe_item(test_db, product_id, disc_dye_id, 1)
    add_recipe_item(test_db, product_id, shrink_nylon_id, 0.008)

    return {
        "product_id": product_id,
        "blank_cd_id": blank_cd_id,
        "cd_case_id": cd_case_id,
        "branding_id": branding_id,
        "qr_id": qr_id,
        "shrink_nylon_id": shrink_nylon_id,
    }


def _count_rows(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_calculate_recipe_cost_for_batch_of_one(test_db, cd_album_setup):
    assert (
        calculate_recipe_cost(test_db, cd_album_setup["product_id"], batch_qty=1)
        == CD_ALBUM_UNIT_COST
    )


def test_in_person_order_fully_manufactured(test_db, cd_album_setup):
    product_id = cd_album_setup["product_id"]

    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": product_id, "quantity": 1, "unit_price": 570_000}],
    )

    item = test_db.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchone()
    assert item["unit_cost_at_time"] == CD_ALBUM_UNIT_COST

    assert get_material(test_db, cd_album_setup["blank_cd_id"])["current_stock"] == 99
    assert get_material(test_db, cd_album_setup["cd_case_id"])["current_stock"] == 104
    assert get_material(test_db, cd_album_setup["branding_id"])["current_stock"] == 127
    assert get_material(test_db, cd_album_setup["qr_id"])["current_stock"] == 185
    assert (
        get_material(test_db, cd_album_setup["shrink_nylon_id"])["current_stock"] == 0.992
    )

    consumption_movements = test_db.execute(
        """
        SELECT * FROM stock_movements
        WHERE reason = 'PRODUCTION_CONSUMPTION' AND reference_order_id = ?
        """,
        (order_id,),
    ).fetchall()
    # 5 STOCK materials in the recipe; SERVICE materials (A3/A4 Print, Disc Dye)
    # cost money but have no stock, so they get no movement.
    assert len(consumption_movements) == 5
    assert all(m["item_type"] == "MATERIAL" for m in consumption_movements)
    assert all(m["reference_order_id"] == order_id for m in consumption_movements)

    assert _count_rows(test_db, "production_batches") == 0

    product = get_product(test_db, product_id)
    assert product["current_stock"] == 0
    assert product["unit_cost"] is None


def test_quantity_three_scales_material_consumption(test_db, cd_album_setup):
    product_id = cd_album_setup["product_id"]

    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": product_id, "quantity": 3, "unit_price": 570_000}],
    )

    item = test_db.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchone()
    assert item["unit_cost_at_time"] == CD_ALBUM_UNIT_COST
    assert get_material(test_db, cd_album_setup["blank_cd_id"])["current_stock"] == 97


def test_mixed_from_stock_and_manufactured(test_db, cd_album_setup):
    product_id = cd_album_setup["product_id"]

    record_stock_adjustment(
        test_db, "PRODUCT", product_id, 1, "ADJUSTMENT", unit_cost=150_000
    )
    assert get_product(test_db, product_id)["current_stock"] == 1

    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": product_id, "quantity": 2, "unit_price": 570_000}],
    )

    item = test_db.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchone()
    # from_stock=1 @ 150,000; to_make=1 @ 202,030 -> round((150000+202030)/2)
    assert item["unit_cost_at_time"] == 176_015

    sale_movements = test_db.execute(
        "SELECT * FROM stock_movements WHERE reason = 'SALE' AND reference_order_id = ?",
        (order_id,),
    ).fetchall()
    assert len(sale_movements) == 1
    assert sale_movements[0]["quantity_change"] == -1

    consumption_movements = test_db.execute(
        """
        SELECT * FROM stock_movements
        WHERE reason = 'PRODUCTION_CONSUMPTION' AND reference_order_id = ?
        """,
        (order_id,),
    ).fetchall()
    assert len(consumption_movements) == 5
    blank_cd_movement = next(
        m for m in consumption_movements if m["item_id"] == cd_album_setup["blank_cd_id"]
    )
    assert blank_cd_movement["quantity_change"] == -1

    assert get_product(test_db, product_id)["current_stock"] == 0


def test_sells_entirely_from_finished_stock_no_material_consumption(
    test_db, cd_album_setup
):
    product_id = cd_album_setup["product_id"]

    record_stock_adjustment(
        test_db, "PRODUCT", product_id, 1, "ADJUSTMENT", unit_cost=150_000
    )

    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": product_id, "quantity": 1, "unit_price": 570_000}],
    )

    item = test_db.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchone()
    assert item["unit_cost_at_time"] == 150_000

    consumption_movements = test_db.execute(
        "SELECT * FROM stock_movements WHERE reason = 'PRODUCTION_CONSUMPTION'"
    ).fetchall()
    assert consumption_movements == []
    assert get_product(test_db, product_id)["current_stock"] == 0


def test_short_material_raises_and_writes_nothing(test_db, cd_album_setup):
    product_id = cd_album_setup["product_id"]
    blank_cd_id = cd_album_setup["blank_cd_id"]

    test_db.execute(
        "UPDATE materials SET current_stock = 2 WHERE id = ?", (blank_cd_id,)
    )
    test_db.commit()

    orders_before = _count_rows(test_db, "orders")
    movements_before = _count_rows(test_db, "stock_movements")

    with pytest.raises(InsufficientStockError) as exc_info:
        record_order(
            test_db,
            "IN_PERSON",
            [{"product_id": product_id, "quantity": 3, "unit_price": 570_000}],
        )

    assert exc_info.value.item_name == "Blank CD"
    assert exc_info.value.needed == 3
    assert exc_info.value.available == 2

    assert _count_rows(test_db, "orders") == orders_before
    assert _count_rows(test_db, "stock_movements") == movements_before
    assert get_material(test_db, blank_cd_id)["current_stock"] == 2


def test_made_to_order_with_no_recipe_raises_on_sale(test_db):
    product_id = add_product(
        test_db, "No Recipe Product", "ALBUM", 1000, 800, made_to_order=True
    )

    with pytest.raises(ValidationError) as exc_info:
        record_order(
            test_db,
            "IN_PERSON",
            [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
        )
    assert exc_info.value.field == "made_to_order"
    assert _count_rows(test_db, "orders") == 0


def test_cancelled_restores_consumed_materials_and_adds_nothing_to_product_stock(
    test_db, cd_album_setup
):
    product_id = cd_album_setup["product_id"]
    blank_cd_id = cd_album_setup["blank_cd_id"]
    cd_case_id = cd_album_setup["cd_case_id"]

    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": product_id, "quantity": 2, "unit_price": 570_000}],
        status="PAID",
    )
    assert get_material(test_db, blank_cd_id)["current_stock"] == 98
    assert get_material(test_db, cd_case_id)["current_stock"] == 103

    process_return(test_db, order_id, "CANCELLED")

    assert get_material(test_db, blank_cd_id)["current_stock"] == 100
    assert get_material(test_db, cd_case_id)["current_stock"] == 105
    assert get_product(test_db, product_id)["current_stock"] == 0


def test_refunded_adds_manufactured_units_to_stock_blended_by_weighted_average(
    test_db, cd_album_setup
):
    product_id = cd_album_setup["product_id"]

    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": product_id, "quantity": 2, "unit_price": 570_000}],
    )
    assert get_product(test_db, product_id)["current_stock"] == 0

    process_return(test_db, order_id, "REFUNDED")

    product = get_product(test_db, product_id)
    assert product["current_stock"] == 2
    assert product["unit_cost"] == CD_ALBUM_UNIT_COST


def test_normal_product_insufficient_stock_untouched_by_made_to_order_logic(test_db):
    product_id = add_product(test_db, "Plain Poster", "POSTER", 1000, 800)
    test_db.execute(
        "UPDATE products SET current_stock = 0, unit_cost = 100 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()

    movements_before = _count_rows(test_db, "stock_movements")

    with pytest.raises(InsufficientStockError):
        record_order(
            test_db,
            "IN_PERSON",
            [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
        )

    assert _count_rows(test_db, "stock_movements") == movements_before
