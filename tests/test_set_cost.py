"""«ثبت بها» (accounting rules section 2): a material at cost 0 or a product at cost NULL gets its unit cost, and nothing else
changes: no movement, same quantity, past rows untouched, one audit operation."""

import pytest

from db.adjustments import record_stock_adjustment
from db.audit import list_audit_log
from db.constants import MAX_MONEY
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.go_live import apply_go_live
from db.materials import add_material, get_material, set_material_cost
from db.orders import get_order, record_order
from db.products import add_product, get_product, set_product_cost
from db.purchases import record_material_purchase
from db.recipes import add_recipe_item, recipe_costs
from tests.go_live_fixture import build_shop
from tests.helpers import cat, stocked_product
from tools.integrity_check import __main__ as cli


def _movements(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM stock_movements ORDER BY id")]


def _uncosted_product(conn, stock=10):
    """A product that holds stock (through a ledger movement) and has never been costed."""
    product_id = add_product(conn, "Found LP", cat(conn, "VINYL"), 3000, 2000)
    record_stock_adjustment(conn, "PRODUCT", product_id, stock, "ADJUSTMENT")
    assert get_product(conn, product_id)["unit_cost"] is None
    return product_id


def _sell(conn, product_id):
    return record_order(
        conn,
        "WEBSITE",
        [{"product_id": product_id, "quantity": 1, "unit_price": 100_000}],
        order_date="2026-10-01",
        shipping_charge=0,
        packaging_kit_id=None,
        postage_cost=0,
        payment_method_id=None,
    )


def _integrity_ok(conn, capsys):
    path = next(row["file"] for row in conn.execute("PRAGMA database_list") if row["name"] == "main")
    code = cli.main(["--db", path])
    assert code == 0, capsys.readouterr().out


# ------------------------------------------------------------------ materials


def test_a_material_gets_its_cost_and_nothing_else_changes(test_db):
    material = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    before = get_material(test_db, material)
    set_material_cost(test_db, material, 500)
    after = get_material(test_db, material)
    assert after["unit_cost"] == 500
    assert {k: v for k, v in after.items() if k not in ("unit_cost", "updated_at")} == {
        k: v for k, v in before.items() if k not in ("unit_cost", "updated_at")
    }
    assert _movements(test_db) == []


def test_the_stock_value_rises_by_stock_times_cost(test_db):
    material = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    assert round(get_material(test_db, material)["current_stock"] * get_material(test_db, material)["unit_cost"]) == 0
    set_material_cost(test_db, material, 500)
    item = get_material(test_db, material)
    assert round(item["current_stock"] * item["unit_cost"]) == 10_000


def test_past_rows_keep_their_cost(test_db):
    material = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    record_stock_adjustment(test_db, "MATERIAL", material, -5, "WASTE")
    record_stock_adjustment(test_db, "MATERIAL", material, 1, "ADJUSTMENT")
    before = _movements(test_db)
    assert [row["unit_cost_at_time"] for row in before] == [0, 0]
    set_material_cost(test_db, material, 500)
    assert _movements(test_db) == before
    assert get_material(test_db, material)["current_stock"] == 16


def test_a_material_with_a_cost_is_refused(test_db):
    material = add_material(test_db, "Box", "STOCK", 1_000, initial_stock=5)
    with pytest.raises(ConflictError) as exc_info:
        set_material_cost(test_db, material, 2_000)
    exc = exc_info.value
    assert exc.code == ErrorCode.COST_ALREADY_SET
    assert exc.details == {"item_type": "MATERIAL", "item_id": material, "item_name": "Box", "unit_cost": 1_000}
    assert get_material(test_db, material)["unit_cost"] == 1_000


@pytest.mark.parametrize("amount", [0, -1])
def test_a_material_cost_of_zero_or_less_is_refused(test_db, amount):
    material = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    with pytest.raises(ValidationError) as exc_info:
        set_material_cost(test_db, material, amount)
    assert exc_info.value.field == "unit_cost"
    assert get_material(test_db, material)["unit_cost"] == 0


def test_the_largest_amount_is_accepted_and_one_more_is_not(test_db):
    material = add_material(test_db, "Sticker", "STOCK", 0)
    with pytest.raises(ValidationError) as exc_info:
        set_material_cost(test_db, material, MAX_MONEY + 1)
    assert exc_info.value.code == ErrorCode.AMOUNT_TOO_LARGE
    assert get_material(test_db, material)["unit_cost"] == 0
    set_material_cost(test_db, material, MAX_MONEY)
    assert get_material(test_db, material)["unit_cost"] == MAX_MONEY


def test_an_unknown_material_is_not_found(test_db):
    with pytest.raises(NotFoundError):
        set_material_cost(test_db, 999, 500)


def test_a_service_material_can_be_priced(test_db):
    labour = add_material(test_db, "Labour", "SERVICE", 0)
    set_material_cost(test_db, labour, 7_000)
    assert get_material(test_db, labour)["unit_cost"] == 7_000


def test_an_archived_material_can_be_priced(test_db):
    from db.materials import deactivate_material

    material = add_material(test_db, "Old sticker", "STOCK", 0, initial_stock=3)
    deactivate_material(test_db, material)
    set_material_cost(test_db, material, 500)
    assert get_material(test_db, material)["unit_cost"] == 500


def test_a_material_cost_is_one_audit_operation_with_the_old_and_new_cost(test_db):
    material = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    set_material_cost(test_db, material, 500)
    log = list_audit_log(test_db, entity_type="materials", entity_id=material, operation="set_material_cost")
    assert log["total"] == 1
    entry = log["items"][0]
    assert (entry["action"], entry["before"], entry["after"]) == ("UPDATE", {"unit_cost": 0}, {"unit_cost": 500})
    assert list_audit_log(test_db, op_id=entry["op_id"])["total"] == 1


def test_a_recipe_turns_complete_once_its_material_has_a_cost(test_db):
    product = stocked_product(test_db)
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    add_recipe_item(test_db, product, sticker, 2)
    assert recipe_costs(test_db, [product])[product]["recipe_cost_status"] == "INCOMPLETE"
    set_material_cost(test_db, sticker, 500)
    assert recipe_costs(test_db, [product])[product] == {
        "recipe_cost": 1_000,
        "recipe_cost_status": "COMPLETE",
        "recipe_cost_missing": [],
    }


def test_a_later_purchase_averages_with_the_cost_that_was_set(test_db):
    material = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=10)
    set_material_cost(test_db, material, 500)
    record_material_purchase(test_db, material, 10, 10_000)  # 10 x 500 + 10_000 over 20
    assert get_material(test_db, material)["unit_cost"] == 750


# ------------------------------------------------------------------- products


def test_a_product_gets_its_cost_and_nothing_else_changes(test_db):
    product = _uncosted_product(test_db)
    before, movements = get_product(test_db, product), _movements(test_db)
    set_product_cost(test_db, product, 250_000)
    after = get_product(test_db, product)
    assert after["unit_cost"] == 250_000
    assert {k: v for k, v in after.items() if k not in ("unit_cost", "updated_at")} == {
        k: v for k, v in before.items() if k not in ("unit_cost", "updated_at")
    }
    assert _movements(test_db) == movements


def test_a_product_with_a_cost_is_refused_a_cost_of_zero_included(test_db):
    for cost in (500, 0):
        product = stocked_product(test_db, name=f"LP {cost}", unit_cost=cost)
        with pytest.raises(ConflictError) as exc_info:
            set_product_cost(test_db, product, 900)
        exc = exc_info.value
        assert exc.code == ErrorCode.COST_ALREADY_SET
        assert exc.details == {"item_type": "PRODUCT", "item_id": product, "item_name": f"LP {cost}", "unit_cost": cost}
        assert get_product(test_db, product)["unit_cost"] == cost


def test_a_product_cost_of_zero_is_refused(test_db):
    product = _uncosted_product(test_db)
    with pytest.raises(ValidationError) as exc_info:
        set_product_cost(test_db, product, 0)
    assert exc_info.value.field == "unit_cost"
    assert get_product(test_db, product)["unit_cost"] is None


def test_an_unknown_product_is_not_found(test_db):
    with pytest.raises(NotFoundError):
        set_product_cost(test_db, 999, 500)


def test_a_product_cost_is_one_audit_operation_with_the_old_and_new_cost(test_db):
    product = _uncosted_product(test_db)
    set_product_cost(test_db, product, 250_000)
    log = list_audit_log(test_db, entity_type="products", entity_id=product, operation="set_product_cost")
    assert log["total"] == 1
    entry = log["items"][0]
    assert (entry["action"], entry["before"], entry["after"]) == ("UPDATE", {"unit_cost": None}, {"unit_cost": 250_000})
    assert list_audit_log(test_db, op_id=entry["op_id"])["total"] == 1


def test_a_product_without_a_cost_cannot_be_sold_until_it_has_one(test_db):
    product = _uncosted_product(test_db)
    with pytest.raises(ValidationError) as exc_info:
        _sell(test_db, product)
    assert exc_info.value.code == ErrorCode.PRODUCT_NO_UNIT_COST
    set_product_cost(test_db, product, 250_000)
    order_id = _sell(test_db, product)
    assert get_order(test_db, order_id)["items"][0]["unit_cost_at_time"] == 250_000
    assert get_product(test_db, product)["current_stock"] == 9


def test_the_integrity_check_still_passes_after_both(test_db, capsys):
    material = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=20)
    product = _uncosted_product(test_db)
    set_material_cost(test_db, material, 500)
    set_product_cost(test_db, product, 250_000)
    _integrity_ok(test_db, capsys)


def test_after_the_go_live_reset_the_costs_can_be_set(test_db, tmp_path):
    ids = build_shop(test_db)
    apply_go_live(test_db, tmp_path / "golive.jsonl")
    assert get_material(test_db, ids["paper"])["unit_cost"] == 0
    assert get_product(test_db, ids["lp"])["unit_cost"] is None
    set_material_cost(test_db, ids["paper"], 1_000)
    set_product_cost(test_db, ids["lp"], 1_500_000)
    assert get_material(test_db, ids["paper"])["unit_cost"] == 1_000
    assert get_product(test_db, ids["lp"])["unit_cost"] == 1_500_000
