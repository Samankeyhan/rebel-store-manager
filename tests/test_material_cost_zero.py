"""A material cost of 0 means "not entered" (accounting rules section 2): the first costed purchase or gain sets the cost
instead of averaging with 0. Materials only; past rows are never touched."""

from db.adjustments import record_stock_adjustment
from db.costing import blend_unit_cost
from db.materials import add_material, get_material
from db.products import add_product, get_product
from db.purchases import record_material_purchase, record_product_purchase
from db.stocktake import apply_stocktake
from tests.helpers import cat
from tools.integrity_check import __main__ as cli


def _cost(conn, material_id):
    return get_material(conn, material_id)["unit_cost"]


def test_blend_treats_zero_as_unknown_only_when_asked():
    assert blend_unit_cost(20, 0, 10, 5_000) == 167  # default: 0 is a real cost, averaged: 5000 / 30 (products)
    assert blend_unit_cost(20, 0, 10, 5_000, zero_is_unknown=True) == 500  # the purchase alone sets the cost
    assert blend_unit_cost(20, 400, 10, 5_000, zero_is_unknown=True) == 433  # a real cost still averages: (20 x 400 + 5000) / 30


def test_blend_zero_is_unknown_is_exact_half_even_and_fractional():
    assert blend_unit_cost(0.5, 0, 0.5, 1_001, zero_is_unknown=True) == 2_002
    assert blend_unit_cost(3, 0, 2, 5, zero_is_unknown=True) == 2  # 2.5 -> 2, half-even
    assert blend_unit_cost(3, 0, 2, 7, zero_is_unknown=True) == 4  # 3.5 -> 4
    assert blend_unit_cost(0, 0, 4, 10, zero_is_unknown=True) == 2  # 2.5 -> 2 also with no stock
    assert blend_unit_cost(5, None, 5, 100, zero_is_unknown=True) == 20


def test_a_purchase_into_a_cost_zero_material_sets_the_cost(test_db):
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    record_material_purchase(test_db, sticker, 10, 5_000)
    material = get_material(test_db, sticker)
    assert material["unit_cost"] == 500 and material["current_stock"] == 30  # not 5000 / 30 = 167


def test_a_purchase_into_a_costed_material_still_averages(test_db):
    box = add_material(test_db, "Box", "STOCK", 1_000, initial_stock=10)
    record_material_purchase(test_db, box, 10, 3_000)
    assert _cost(test_db, box) == 650  # (10 x 1000 + 3000) / 20


def test_a_costed_gain_on_a_cost_zero_material_sets_the_cost(test_db):
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    record_stock_adjustment(test_db, "MATERIAL", sticker, 5, "ADJUSTMENT", unit_cost=800)
    assert _cost(test_db, sticker) == 800


def test_a_gain_without_a_cost_leaves_zero_alone(test_db):
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    record_stock_adjustment(test_db, "MATERIAL", sticker, 5, "ADJUSTMENT")
    assert _cost(test_db, sticker) == 0


def test_a_costed_stocktake_gain_on_a_cost_zero_material_sets_the_cost(test_db):
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=10)
    apply_stocktake(
        test_db, [{"item_type": "MATERIAL", "item_id": sticker, "counted": 14, "system_quantity": 10, "unit_cost": 750}]
    )
    assert _cost(test_db, sticker) == 750


def test_products_at_cost_zero_still_average_with_zero(test_db):
    product = add_product(test_db, "Gift", cat(test_db, "OTHER"), 1_000, 800)
    test_db.execute("UPDATE products SET current_stock = 10, unit_cost = 0 WHERE id = ?", (product,))
    record_product_purchase(test_db, product, 10, 5_000)
    assert get_product(test_db, product)["unit_cost"] == 250
    record_stock_adjustment(test_db, "PRODUCT", product, 10, "ADJUSTMENT", unit_cost=1_000)
    assert get_product(test_db, product)["unit_cost"] == (20 * 250 + 10_000) // 30


def test_a_purchase_at_price_zero_into_a_cost_zero_material_stays_zero(test_db):
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    record_material_purchase(test_db, sticker, 10, 0)
    material = get_material(test_db, sticker)
    assert material["unit_cost"] == 0 and material["current_stock"] == 30


def test_a_zero_price_purchase_into_a_costed_material_lowers_the_average(test_db):
    box = add_material(test_db, "Box", "STOCK", 1_000, initial_stock=10)
    record_material_purchase(test_db, box, 10, 0)
    assert _cost(test_db, box) == 500


def test_repricing_raises_the_stock_value_and_the_integrity_check_still_passes(test_db, capsys):
    """The old units at 0 are valued at the new price from then on: the stock value rises, which is intended."""
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    box = add_material(test_db, "Box", "STOCK", 1_000, initial_stock=5)

    def stock_value():
        return sum(
            round(m["current_stock"] * m["unit_cost"])
            for m in (get_material(test_db, sticker), get_material(test_db, box))
        )

    before = stock_value()
    assert before == 5_000
    record_material_purchase(test_db, sticker, 10, 5_000)
    assert stock_value() == 30 * 500 + 5_000 and stock_value() > before + 5_000

    path = next(row["file"] for row in test_db.execute("PRAGMA database_list") if row["name"] == "main")
    code = cli.main(["--db", path])
    assert code == 0, capsys.readouterr().out
