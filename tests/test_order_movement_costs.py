"""The order commit freezes unit_cost_at_time on its SALE, PACKAGING and PRODUCTION_CONSUMPTION movements:
the item's unit cost at that moment, which a void returns the stock at (accounting-rules section 20)."""

from db.adjustments import record_stock_adjustment
from db.materials import add_material
from db.orders import record_order, update_order_status
from db.packaging import add_kit_item, create_kit
from db.products import add_product
from db.recipes import add_recipe_item
from tests.helpers import cat, stocked_product


def _movements(conn, order_id):
    return [
        dict(r)
        for r in conn.execute(
            "SELECT item_type, item_id, quantity_change, reason, unit_cost_at_time FROM stock_movements "
            "WHERE reference_order_id = ? ORDER BY id",
            (order_id,),
        )
    ]


def _line(product_id, quantity=1, price=3000):
    return [{"product_id": product_id, "quantity": quantity, "unit_price": price}]


def test_a_sale_from_stock_freezes_the_product_cost(test_db):
    product = stocked_product(test_db, stock=10, unit_cost=700)
    order = record_order(test_db, "IN_PERSON", _line(product, 2), packaging_kit_id=None)
    assert _movements(test_db, order) == [
        {"item_type": "PRODUCT", "item_id": product, "quantity_change": -2, "reason": "SALE", "unit_cost_at_time": 700}
    ]


def test_a_made_to_order_line_freezes_the_stock_part_and_each_consumed_material(test_db):
    paper = add_material(test_db, "Paper", "STOCK", 1_250, initial_stock=50)
    print_service = add_material(test_db, "Print", "SERVICE", 9_000)
    product = add_product(test_db, "Poster", cat(test_db, "POSTER"), 50_000, 40_000, made_to_order=True)
    add_recipe_item(test_db, product, paper, 2)
    add_recipe_item(test_db, product, print_service, 1)
    record_stock_adjustment(test_db, "PRODUCT", product, 1, "ADJUSTMENT", unit_cost=20_000)

    order = record_order(test_db, "IN_PERSON", _line(product, 3), packaging_kit_id=None)

    assert _movements(test_db, order) == [
        {"item_type": "PRODUCT", "item_id": product, "quantity_change": -1, "reason": "SALE", "unit_cost_at_time": 20_000},
        {"item_type": "MATERIAL", "item_id": paper, "quantity_change": -4, "reason": "PRODUCTION_CONSUMPTION",
         "unit_cost_at_time": 1_250},
    ]


def test_packaging_freezes_each_kit_material_cost_including_a_cost_of_zero(test_db):
    box = add_material(test_db, "Box", "STOCK", 3_000, initial_stock=10)
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=10)
    kit = create_kit(test_db, "Small")
    add_kit_item(test_db, kit, box, 1)
    add_kit_item(test_db, kit, sticker, 2)
    product = stocked_product(test_db)

    order = record_order(test_db, "WEBSITE", _line(product), packaging_kit_id=kit)

    packaging = {m["item_id"]: m for m in _movements(test_db, order) if m["reason"] == "PACKAGING"}
    assert packaging[box]["unit_cost_at_time"] == 3_000
    assert packaging[sticker]["unit_cost_at_time"] == 0


def test_the_frozen_cost_does_not_follow_a_later_cost_change(test_db):
    product = stocked_product(test_db, stock=5, unit_cost=500)
    order = record_order(test_db, "IN_PERSON", _line(product), packaging_kit_id=None)
    record_stock_adjustment(test_db, "PRODUCT", product, 5, "ADJUSTMENT", unit_cost=1_500)
    # (4 × 500 + 5 × 1,500) ÷ 9, half-even
    assert test_db.execute("SELECT unit_cost FROM products WHERE id = ?", (product,)).fetchone()[0] == 1_056
    assert _movements(test_db, order)[0]["unit_cost_at_time"] == 500


def test_a_draft_writes_no_movement_until_it_commits(test_db):
    product = stocked_product(test_db, stock=5, unit_cost=800)
    order = record_order(test_db, "IN_PERSON", _line(product), packaging_kit_id=None, status="DRAFT")
    assert _movements(test_db, order) == []

    update_order_status(test_db, order, "COMPLETED")
    assert _movements(test_db, order)[0]["unit_cost_at_time"] == 800
