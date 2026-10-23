"""Voiding a sale entered by mistake (db/order_voids.py, accounting-rules section 20): what comes back, at which
cost, what is refused, and how VOIDED meets the other status rules."""

import pytest

from db.adjustments import record_stock_adjustment
from db.audit import list_audit_log
from db.costing import blend_unit_cost
from db.distributions import record_profit_distribution
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.materials import add_material, get_material
from db.order_voids import plan_void, void_order
from db.orders import get_order, list_orders, record_order, set_paid_date, update_order_status
from db.packaging import add_kit_item, create_kit
from db.partners import add_partner
from db.payment_methods import add_payment_method
from db.products import add_product, get_product
from db.purchases import record_material_purchase, record_product_purchase
from db.recipes import add_recipe_item
from db.returns import process_return
from db.settlements import get_pending, record_settlement
from db.stocktake import apply_stocktake
from tests.helpers import cat, stocked_product

DAY = "2026-10-10"


def _sell(conn, product, quantity=1, price=3000, **kwargs):
    kwargs.setdefault("packaging_kit_id", None)
    kwargs.setdefault("order_date", DAY)
    return record_order(conn, "IN_PERSON", [{"product_id": product, "quantity": quantity, "unit_price": price}], **kwargs)


def _stock(conn, table, item_id):
    return conn.execute(f"SELECT current_stock, unit_cost FROM {table} WHERE id = ?", (item_id,)).fetchone()


def _order(conn, order_id):
    return dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())


def _refused(conn, order_id, code, reason="wrong product"):
    with pytest.raises(ConflictError) as exc_info:
        void_order(conn, order_id, reason)
    assert exc_info.value.code == code
    return exc_info.value.details


@pytest.fixture
def poster(test_db):
    """A made-to-order poster: 2 Paper (STOCK) + 1 Print (SERVICE) per unit; 1 finished poster in stock at 20,000."""
    paper = add_material(test_db, "Paper", "STOCK", 1_250, initial_stock=50)
    print_service = add_material(test_db, "Print", "SERVICE", 9_000)
    product = add_product(test_db, "Poster", cat(test_db, "POSTER"), 50_000, 40_000, made_to_order=True)
    add_recipe_item(test_db, product, paper, 2)
    add_recipe_item(test_db, product, print_service, 1)
    record_stock_adjustment(test_db, "PRODUCT", product, 1, "ADJUSTMENT", unit_cost=20_000)
    return {"product": product, "paper": paper, "print": print_service}


# ------------------------------------------------------------------ what comes back


def test_a_void_returns_the_stock_keeps_the_row_and_marks_it(test_db):
    product = stocked_product(test_db, stock=10, unit_cost=700)
    order_id = _sell(test_db, product, 3)
    before = _order(test_db, order_id)
    items_before = get_order(test_db, order_id)["items"]

    void_order(test_db, order_id, "  wrong   product ")

    after = _order(test_db, order_id)
    assert after["status"] == "VOIDED"
    assert after["void_reason"] == "wrong product"  # stored form
    assert after["voided_at"] is not None
    for column in ("invoice_number", "order_date", "transaction_fee", "packaging_cost", "postage_cost",
                   "shipping_charge", "stock_committed", "paid_date", "paid_jalali_year", "paid_jalali_month"):
        assert after[column] == before[column], column
    assert get_order(test_db, order_id)["items"] == items_before
    assert _stock(test_db, "products", product)["current_stock"] == 10
    returned = test_db.execute(
        "SELECT quantity_change, reason, notes, unit_cost_at_time FROM stock_movements WHERE reason = 'RETURN'"
    ).fetchall()
    assert [tuple(r) for r in returned] == [(3, "RETURN", f"ابطال سفارش {before['invoice_number']} — wrong product", 700)]


def test_a_blank_or_missing_reason_is_refused_and_nothing_is_written(test_db):
    order_id = _sell(test_db, stocked_product(test_db))
    for reason in ("", "   ", None):
        with pytest.raises(ValidationError) as exc_info:
            void_order(test_db, order_id, reason)
        assert (exc_info.value.code, exc_info.value.field) == (ErrorCode.VOID_REASON_REQUIRED, "reason")
    with pytest.raises(ValidationError) as exc_info:
        void_order(test_db, order_id, "x" * 501)
    assert exc_info.value.field == "reason"
    assert _order(test_db, order_id)["status"] == "COMPLETED"


def test_an_unknown_order_is_not_found(test_db):
    with pytest.raises(NotFoundError):
        void_order(test_db, 999, "x")
    with pytest.raises(NotFoundError):
        plan_void(test_db, 999)


def test_a_made_to_order_sale_returns_its_finished_part_and_its_consumed_materials(test_db, poster):
    order_id = _sell(test_db, poster["product"], 3)  # 1 from stock, 2 made: 4 Paper
    assert _stock(test_db, "products", poster["product"])["current_stock"] == 0
    assert get_material(test_db, poster["paper"])["current_stock"] == 46

    void_order(test_db, order_id, "x")

    assert _stock(test_db, "products", poster["product"])["current_stock"] == 1
    assert get_material(test_db, poster["paper"])["current_stock"] == 50
    reasons = test_db.execute(
        "SELECT item_type, quantity_change FROM stock_movements WHERE reason = 'RETURN' ORDER BY id"
    ).fetchall()
    assert [tuple(r) for r in reasons] == [("PRODUCT", 1), ("MATERIAL", 4)]  # nothing for the SERVICE material


def test_a_wholly_made_line_puts_no_finished_unit_into_stock(test_db, poster):
    record_stock_adjustment(test_db, "PRODUCT", poster["product"], -1, "ADJUSTMENT")
    order_id = _sell(test_db, poster["product"], 2)
    void_order(test_db, order_id, "x")
    assert _stock(test_db, "products", poster["product"])["current_stock"] == 0
    assert get_material(test_db, poster["paper"])["current_stock"] == 50


def test_packaging_materials_come_back(test_db):
    box = add_material(test_db, "Box", "STOCK", 3_000, initial_stock=10)
    tape = add_material(test_db, "Tape", "STOCK", 10, unit="m", initial_stock=5.5)
    kit = create_kit(test_db, "Parcel")
    add_kit_item(test_db, kit, box, 1)
    add_kit_item(test_db, kit, tape, 0.3)
    order_id = _sell(test_db, stocked_product(test_db), packaging_kit_id=kit)
    void_order(test_db, order_id, "x")
    assert get_material(test_db, box)["current_stock"] == 10
    assert get_material(test_db, tape)["current_stock"] == pytest.approx(5.5)


# ------------------------------------------------------------------ the cost rule


def test_no_cost_change_since_the_sale_leaves_every_cost_as_it_is(test_db, poster):
    product = stocked_product(test_db, stock=4, unit_cost=333)
    order_ids = [_sell(test_db, product, 3), _sell(test_db, poster["product"], 2)]
    for order_id in order_ids:
        void_order(test_db, order_id, "x")
    assert _stock(test_db, "products", product)["unit_cost"] == 333
    assert _stock(test_db, "products", poster["product"])["unit_cost"] == 20_000
    assert get_material(test_db, poster["paper"])["unit_cost"] == 1_250


def test_after_a_purchase_the_stock_comes_back_at_its_frozen_cost_by_weighted_average(test_db):
    product = stocked_product(test_db, stock=5, unit_cost=100)
    order_id = _sell(test_db, product, 1)  # 4 left at 100
    record_product_purchase(test_db, product, 4, 800)  # 8 at 150
    assert _stock(test_db, "products", product)["unit_cost"] == 150

    void_order(test_db, order_id, "x")

    stock, cost = _stock(test_db, "products", product)
    assert stock == 9
    assert cost == blend_unit_cost(8, 150, 1, 100) == 144  # (8 × 150 + 1 × 100) ÷ 9 = 144.4
    # the same as if the sale had never been recorded: (5 × 100 + 800) ÷ 9
    assert cost == round((5 * 100 + 800) / 9)


def test_materials_come_back_at_their_frozen_cost_too(test_db, poster):
    order_id = _sell(test_db, poster["product"], 3)  # 4 Paper at 1,250; 46 left
    record_material_purchase(test_db, poster["paper"], 46, 46 * 2_000)  # 92 at 1,625
    void_order(test_db, order_id, "x")
    material = get_material(test_db, poster["paper"])
    assert material["current_stock"] == 96
    assert material["unit_cost"] == blend_unit_cost(92, 1_625, 4, 4 * 1_250)


def test_a_material_frozen_at_cost_zero_comes_back_at_zero(test_db):
    sticker = add_material(test_db, "Sticker", "STOCK", 0, initial_stock=10)
    kit = create_kit(test_db, "Sticker kit")
    add_kit_item(test_db, kit, sticker, 1)
    order_id = _sell(test_db, stocked_product(test_db), packaging_kit_id=kit)
    void_order(test_db, order_id, "x")
    assert get_material(test_db, sticker)["unit_cost"] == 0


def _forget_movement_costs(conn, order_id):
    """What an order committed before section 20 looks like: no cost on its movements."""
    conn.execute("UPDATE stock_movements SET unit_cost_at_time = NULL WHERE reference_order_id = ?", (order_id,))
    conn.commit()


def test_an_older_sale_of_a_normal_product_uses_the_lines_frozen_cost(test_db):
    product = stocked_product(test_db, stock=5, unit_cost=100)
    order_id = _sell(test_db, product, 1)
    _forget_movement_costs(test_db, order_id)
    record_product_purchase(test_db, product, 4, 800)
    void_order(test_db, order_id, "x")
    assert _stock(test_db, "products", product)["unit_cost"] == 144


def test_an_older_mixed_made_to_order_sale_and_older_materials_come_back_at_todays_cost(test_db, poster):
    order_id = _sell(test_db, poster["product"], 3)  # 1 from stock + 2 made: the line cost is a blend
    _forget_movement_costs(test_db, order_id)
    record_stock_adjustment(test_db, "PRODUCT", poster["product"], 2, "ADJUSTMENT", unit_cost=30_000)
    record_material_purchase(test_db, poster["paper"], 46, 46 * 2_000)
    product_cost = _stock(test_db, "products", poster["product"])["unit_cost"]
    paper_cost = get_material(test_db, poster["paper"])["unit_cost"]

    plan = plan_void(test_db, order_id)
    assert [p["frozen_cost_known"] for p in plan["products"]] == [False]
    assert [m["frozen_cost_known"] for m in plan["materials"]] == [False]
    void_order(test_db, order_id, "x")

    assert _stock(test_db, "products", poster["product"])["unit_cost"] == product_cost
    assert get_material(test_db, poster["paper"])["unit_cost"] == paper_cost
    assert test_db.execute(
        "SELECT COUNT(*) FROM stock_movements WHERE reason = 'RETURN' AND unit_cost_at_time IS NULL"
    ).fetchone()[0] == 2


def test_one_audit_operation_holds_the_whole_void(test_db, poster):
    order_id = _sell(test_db, poster["product"], 3)
    void_order(test_db, order_id, "x")
    rows = list_audit_log(test_db, operation="void_order", limit=500)["items"]
    assert len({row["op_id"] for row in rows}) == 1
    assert {row["entity_type"] for row in rows} == {"orders", "products", "materials", "stock_movements"}


# ------------------------------------------------------------------ refusals


def test_a_voided_order_is_refused_the_second_time(test_db):
    order_id = _sell(test_db, stocked_product(test_db))
    void_order(test_db, order_id, "x")
    details = _refused(test_db, order_id, ErrorCode.ORDER_ALREADY_VOIDED)
    assert details == {"order_id": order_id, "voided_at": _order(test_db, order_id)["voided_at"],
                       "replaced_by_order_id": None}


@pytest.mark.parametrize("returned, start", [("CANCELLED", "PAID"), ("REFUNDED", "COMPLETED")])
def test_an_order_with_a_return_is_refused(test_db, returned, start):
    order_id = _sell(test_db, stocked_product(test_db), status=start)
    process_return(test_db, order_id, returned)
    assert _refused(test_db, order_id, ErrorCode.ORDER_HAS_RETURN) == {"order_id": order_id, "status": returned}


def test_a_draft_is_refused(test_db):
    order_id = _sell(test_db, stocked_product(test_db), status="DRAFT")
    assert _refused(test_db, order_id, ErrorCode.ORDER_NOT_COMMITTED) == {"order_id": order_id, "status": "DRAFT"}


def test_a_settled_order_is_refused(test_db):
    method = add_payment_method(test_db, "Card", "IMMEDIATE")
    order_id = _sell(test_db, stocked_product(test_db), payment_method_id=method)
    settlement = record_settlement(test_db, method, DAY, 3000, order_ids=[order_id])
    assert _refused(test_db, order_id, ErrorCode.ORDER_ALREADY_SETTLED) == {
        "order_id": order_id, "settlement_id": settlement}


def test_a_closed_day_is_refused_and_the_day_after_period_end_is_not(test_db):
    product = stocked_product(test_db)
    on_end = _sell(test_db, product, order_date="2026-10-05")
    after_end = _sell(test_db, product, order_date="2026-10-06")
    add_partner(test_db, "Solo", 100.0)
    distribution = record_profit_distribution(test_db, "2026-10-01", "2026-10-05", 0, allow_exceeding=True)
    assert _refused(test_db, on_end, ErrorCode.PERIOD_ALREADY_DISTRIBUTED) == {
        "distribution_id": distribution, "period_end": "2026-10-05", "date": "2026-10-05"}
    void_order(test_db, after_end, "x")


def _count(conn, product, counted):
    apply_stocktake(conn, [{"item_type": "PRODUCT", "item_id": product, "counted": counted,
                            "system_quantity": get_product(conn, product)["current_stock"]}])


def test_a_stocktake_recorded_after_the_sale_on_an_affected_item_is_refused(test_db):
    product = stocked_product(test_db, name="Counted LP", stock=10)
    order_id = _sell(test_db, product, 2)
    _count(test_db, product, 7)
    details = _refused(test_db, order_id, ErrorCode.STOCKTAKE_AFTER_SALE)
    assert {k: details[k] for k in ("order_id", "item_type", "item_id", "item_name")} == {
        "order_id": order_id, "item_type": "PRODUCT", "item_id": product, "item_name": "Counted LP"}
    assert len(details["stocktake_date"]) == 10


def test_a_stocktake_of_another_item_or_before_the_sale_and_a_manual_adjustment_do_not_block(test_db):
    product = stocked_product(test_db, stock=10)
    other = stocked_product(test_db, name="Other LP", stock=10)
    _count(test_db, product, 9)  # before the sale
    order_id = _sell(test_db, product, 2)
    _count(test_db, other, 8)  # another item
    record_stock_adjustment(test_db, "PRODUCT", product, -1, "ADJUSTMENT")  # manual, not a count
    assert plan_void(test_db, order_id)["blockers"] == []
    void_order(test_db, order_id, "x")


def test_a_refusal_writes_nothing(test_db):
    product = stocked_product(test_db, stock=10)
    order_id = _sell(test_db, product, 2)
    _count(test_db, product, 7)
    audit_before = test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    _refused(test_db, order_id, ErrorCode.STOCKTAKE_AFTER_SALE)
    assert test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == audit_before
    assert _order(test_db, order_id)["status"] == "COMPLETED"
    assert _stock(test_db, "products", product)["current_stock"] == 7


# ------------------------------------------------------------------ the plan


def test_the_plan_lists_what_comes_back_and_writes_nothing(test_db, poster):
    order_id = _sell(test_db, poster["product"], 3, price=50_000)
    record_material_purchase(test_db, poster["paper"], 46, 46 * 2_000)
    audit_before = test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

    plan = plan_void(test_db, order_id)

    assert test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == audit_before
    assert plan["blockers"] == []
    assert plan["products"] == [{
        "item_id": poster["product"], "name": "Poster", "quantity": 1, "unit_cost_before": 20_000,
        "unit_cost_after": 20_000, "frozen_cost_known": True}]
    assert plan["materials"] == [{
        "item_id": poster["paper"], "name": "Paper", "quantity": 4, "unit_cost_before": 1_625,
        "unit_cost_after": blend_unit_cost(92, 1_625, 4, 5_000), "frozen_cost_known": True,
        "unit": "piece", "reasons": {"PRODUCTION_CONSUMPTION": 4}}]
    detail = get_order(test_db, order_id)
    assert (plan["customer_total"], plan["profit"]) == (detail["customer_total"], detail["profit"])
    assert (plan["order_day"], plan["order_jalali_year"], plan["order_jalali_month"]) == (DAY, 1405, 7)


def test_the_plan_lists_every_blocker(test_db):
    method = add_payment_method(test_db, "Card", "IMMEDIATE")
    order_id = _sell(test_db, stocked_product(test_db), payment_method_id=method)
    record_settlement(test_db, method, DAY, 3000, order_ids=[order_id])
    add_partner(test_db, "Solo", 100.0)
    record_profit_distribution(test_db, "2026-10-01", "2026-10-15", 0, allow_exceeding=True)
    codes = [b["code"] for b in plan_void(test_db, order_id)["blockers"]]
    assert codes == ["ORDER_ALREADY_SETTLED", "PERIOD_ALREADY_DISTRIBUTED"]


def test_the_plan_says_when_the_order_waits_for_settlement(test_db):
    method = add_payment_method(test_db, "Card", "IMMEDIATE")
    product = stocked_product(test_db)
    assert plan_void(test_db, _sell(test_db, product, payment_method_id=method))["pending_settlement"] is True
    assert plan_void(test_db, _sell(test_db, product, payment_method_id=None))["pending_settlement"] is False


# ------------------------------------------------------------------ VOIDED and the other rules


def test_a_voided_order_cannot_be_returned_or_moved_and_nothing_else_sets_voided(test_db):
    product = stocked_product(test_db)
    order_id = _sell(test_db, product, status="PAID")
    void_order(test_db, order_id, "x")
    with pytest.raises(ConflictError) as exc_info:
        process_return(test_db, order_id, "REFUNDED")
    assert exc_info.value.code == ErrorCode.ORDER_ALREADY_VOIDED
    with pytest.raises(ConflictError):
        update_order_status(test_db, order_id, "COMPLETED")
    with pytest.raises(ConflictError) as exc_info:
        set_paid_date(test_db, order_id, DAY)
    assert exc_info.value.code == ErrorCode.ORDER_NOT_PAID
    other = _sell(test_db, product, status="PENDING")
    with pytest.raises(ConflictError):
        update_order_status(test_db, other, "VOIDED")
    with pytest.raises(ValidationError):
        _sell(test_db, product, status="VOIDED")


def test_the_order_list_leaves_voided_orders_out_unless_asked(test_db):
    product = stocked_product(test_db)
    kept, voided = _sell(test_db, product), _sell(test_db, product)
    void_order(test_db, voided, "x")
    assert [o["id"] for o in list_orders(test_db)] == [kept]
    assert {o["id"] for o in list_orders(test_db, include_voided=True)} == {kept, voided}
    rows = list_orders(test_db, status="VOIDED")
    assert [(o["id"], o["profit"]) for o in rows] == [(voided, None)]
    assert rows[0]["void_reason"] == "x"


def test_a_voided_order_leaves_pending_settlement(test_db):
    method = add_payment_method(test_db, "Card", "IMMEDIATE")
    order_id = _sell(test_db, stocked_product(test_db), payment_method_id=method)
    assert get_pending(test_db)[0]["total_expected"] == 3000
    void_order(test_db, order_id, "x")
    assert get_pending(test_db) == []
    with pytest.raises(ConflictError) as exc_info:
        record_settlement(test_db, method, DAY, 3000, order_ids=[order_id])
    assert exc_info.value.code == ErrorCode.ORDER_NOT_PAID


def test_an_order_without_a_correction_has_no_links(test_db):
    order = get_order(test_db, _sell(test_db, stocked_product(test_db)))["order"]
    assert (order["replaces_invoice_number"], order["replaced_by_order_id"], order["replaced_by_invoice_number"]) == (
        None, None, None)
