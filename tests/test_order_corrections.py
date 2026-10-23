"""Correcting a sale (db/order_voids.py correct_order, accounting-rules section 20): the old order is voided and
the right one recorded in one operation; any refusal leaves both as they were."""

from datetime import date

import pytest

import db.orders
import db.settlements
from db.audit import list_audit_log
from db.distributions import record_profit_distribution
from db.errors import ConflictError, ErrorCode, InsufficientStockError, ValidationError
from db.order_voids import correct_order, void_order
from db.orders import get_order, record_order
from db.partners import add_partner
from db.payment_methods import add_payment_method
from db.products import deactivate_product, get_product
from db.purchases import record_product_purchase
from db.reports import get_profit_and_loss
from db.settlements import record_settlement
from tests.helpers import stocked_product

TODAY = date(2026, 10, 23)  # 1 Aban 1405
DAY = "2026-10-10"  # Mehr 1405


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    for module in (db.orders, db.settlements):
        monkeypatch.setattr(module, "today_local", lambda conn=None: TODAY)


def _line(product, quantity=1, price=3000):
    return [{"product_id": product, "quantity": quantity, "unit_price": price}]


def _sell(conn, product, quantity=1, price=3000, **kwargs):
    kwargs.setdefault("packaging_kit_id", None)
    kwargs.setdefault("order_date", DAY)
    return record_order(conn, "IN_PERSON", _line(product, quantity, price), **kwargs)


def _correct(conn, order_id, product, quantity=1, price=3000, reason="wrong price", **kwargs):
    kwargs.setdefault("packaging_kit_id", None)
    kwargs.setdefault("order_date", DAY)
    return correct_order(conn, order_id, reason, "IN_PERSON", _line(product, quantity, price), **kwargs)


def _status(conn, order_id):
    return conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()[0]


def _orders(conn):
    return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]


def test_a_correction_voids_the_old_order_records_the_new_one_and_links_both(test_db):
    product = stocked_product(test_db, stock=10)
    old = _sell(test_db, product, price=3000)
    new = _correct(test_db, old, product, price=2500)

    assert _status(test_db, old) == "VOIDED"
    old_order, new_order = get_order(test_db, old)["order"], get_order(test_db, new)["order"]
    assert old_order["void_reason"] == "wrong price"
    assert (new_order["replaces_order_id"], new_order["replaces_invoice_number"]) == (old, old_order["invoice_number"])
    assert (old_order["replaced_by_order_id"], old_order["replaced_by_invoice_number"]) == (
        new, new_order["invoice_number"])
    assert new_order["invoice_number"] != old_order["invoice_number"]
    assert get_order(test_db, new)["customer_total"] == 2500


def test_the_whole_correction_is_one_audit_operation(test_db):
    product = stocked_product(test_db, stock=10)
    old = _sell(test_db, product)
    _correct(test_db, old, product, quantity=2)
    rows = list_audit_log(test_db, operation="correct_order", limit=500)["items"]
    assert len({row["op_id"] for row in rows}) == 1
    actions = {(row["entity_type"], row["action"]) for row in rows}
    assert {("orders", "UPDATE"), ("orders", "INSERT"), ("order_items", "INSERT"), ("stock_movements", "INSERT")} <= actions
    assert list_audit_log(test_db, operation="void_order")["total"] == 0  # nested: one label


def test_a_price_only_correction_keeps_stock_and_cost_of_goods(test_db):
    product = stocked_product(test_db, stock=10, unit_cost=700)
    old = _sell(test_db, product, quantity=3, price=3000)
    new = _correct(test_db, old, product, quantity=3, price=2800)
    assert get_product(test_db, product)["current_stock"] == 7
    assert [i["unit_cost_at_time"] for i in get_order(test_db, new)["items"]] == [700]


def test_the_wrong_product_comes_back_and_the_right_one_goes_out(test_db):
    wrong = stocked_product(test_db, name="Wrong LP", stock=5)
    right = stocked_product(test_db, name="Right LP", stock=5)
    old = _sell(test_db, wrong, quantity=2)
    _correct(test_db, old, right, quantity=2)
    assert (get_product(test_db, wrong)["current_stock"], get_product(test_db, right)["current_stock"]) == (5, 3)


def test_the_new_order_can_use_the_stock_the_void_returned(test_db):
    product = stocked_product(test_db, stock=2)
    old = _sell(test_db, product, quantity=2)
    assert get_product(test_db, product)["current_stock"] == 0
    _correct(test_db, old, product, quantity=2, price=1000)
    assert get_product(test_db, product)["current_stock"] == 0


def test_the_new_order_is_dated_as_picked_and_costed_as_of_today(test_db):
    product = stocked_product(test_db, stock=5, unit_cost=100)
    old = _sell(test_db, product, quantity=1)
    record_product_purchase(test_db, product, 4, 800)  # 8 at 150
    new = _correct(test_db, old, product, quantity=1, order_date="2026-10-01")
    detail = get_order(test_db, new)
    assert detail["order"]["order_date"].startswith("2026-09-30")  # local midnight of 1 Oct, as UTC
    # the void blended the unit back at 100: (8 × 150 + 100) ÷ 9 = 144; the new sale freezes that
    assert [i["unit_cost_at_time"] for i in detail["items"]] == [144]


def _unchanged(conn, old, orders_before, stock_before, product):
    assert _status(conn, old) == "COMPLETED"
    assert _orders(conn) == orders_before
    assert get_product(conn, product)["current_stock"] == stock_before


def test_a_future_day_is_refused_and_nothing_changes(test_db):
    product = stocked_product(test_db, stock=5)
    old = _sell(test_db, product)
    before = (_orders(test_db), get_product(test_db, product)["current_stock"])
    with pytest.raises(ValidationError) as exc_info:
        _correct(test_db, old, product, order_date="2026-10-24")
    assert (exc_info.value.code, exc_info.value.field) == (ErrorCode.DATE_IN_FUTURE, "order_date")
    _unchanged(test_db, old, *before, product)


def test_a_closed_new_day_is_refused_even_when_the_old_day_is_open(test_db):
    product = stocked_product(test_db, stock=5)
    old = _sell(test_db, product, order_date="2026-10-20")
    add_partner(test_db, "Solo", 100.0)
    record_profit_distribution(test_db, "2026-10-01", "2026-10-15", 0, allow_exceeding=True)
    before = (_orders(test_db), get_product(test_db, product)["current_stock"])
    with pytest.raises(ConflictError) as exc_info:
        _correct(test_db, old, product, order_date="2026-10-12")
    assert exc_info.value.code == ErrorCode.PERIOD_ALREADY_DISTRIBUTED
    assert exc_info.value.details["date"] == "2026-10-12"
    _unchanged(test_db, old, *before, product)
    _correct(test_db, old, product, order_date="2026-10-16")


def test_a_closed_old_day_is_refused(test_db):
    product = stocked_product(test_db, stock=5)
    old = _sell(test_db, product, order_date="2026-10-05")
    add_partner(test_db, "Solo", 100.0)
    record_profit_distribution(test_db, "2026-10-01", "2026-10-05", 0, allow_exceeding=True)
    with pytest.raises(ConflictError) as exc_info:
        _correct(test_db, old, product, order_date="2026-10-20")
    assert exc_info.value.code == ErrorCode.PERIOD_ALREADY_DISTRIBUTED


def test_a_draft_correction_is_refused(test_db):
    product = stocked_product(test_db, stock=5)
    old = _sell(test_db, product)
    with pytest.raises(ValidationError) as exc_info:
        _correct(test_db, old, product, status="DRAFT")
    assert exc_info.value.field == "status"
    assert _status(test_db, old) == "COMPLETED"


def test_a_refused_new_order_rolls_the_void_back(test_db):
    product = stocked_product(test_db, stock=3)
    other = stocked_product(test_db, name="Archived LP", stock=3)
    deactivate_product(test_db, other)
    old = _sell(test_db, product, quantity=1)
    before = (_orders(test_db), get_product(test_db, product)["current_stock"])
    with pytest.raises(InsufficientStockError):
        _correct(test_db, old, product, quantity=5)
    _unchanged(test_db, old, *before, product)
    with pytest.raises(ValidationError):
        _correct(test_db, old, other)
    _unchanged(test_db, old, *before, product)


def test_a_paid_day_in_a_settled_month_is_refused(test_db):
    monthly = add_payment_method(test_db, "Monthly Pay", "DAY_OF_NEXT_MONTH", settlement_days=7)
    product = stocked_product(test_db, stock=5)
    settled = _sell(test_db, product, payment_method_id=monthly)  # paid in Mehr
    record_settlement(test_db, monthly, "2026-10-23", 3000, jalali_year=1405, jalali_month=7)
    old = _sell(test_db, product, order_date="2026-10-23", payment_method_id=monthly)
    with pytest.raises(ConflictError) as exc_info:
        _correct(test_db, old, product, payment_method_id=monthly, paid_date=DAY)
    assert exc_info.value.code == ErrorCode.MONTH_ALREADY_SETTLED
    assert _status(test_db, old) == "COMPLETED" and _status(test_db, settled) == "COMPLETED"


def test_a_voided_order_cannot_be_corrected_but_its_replacement_can(test_db):
    product = stocked_product(test_db, stock=5)
    old = _sell(test_db, product)
    first = _correct(test_db, old, product, price=2000)
    with pytest.raises(ConflictError) as exc_info:
        _correct(test_db, old, product)
    assert exc_info.value.code == ErrorCode.ORDER_ALREADY_VOIDED
    assert exc_info.value.details["replaced_by_order_id"] == first
    second = _correct(test_db, first, product, price=1500)
    assert get_order(test_db, second)["order"]["replaces_order_id"] == first


def test_a_blank_reason_is_refused_before_anything_is_written(test_db):
    product = stocked_product(test_db, stock=5)
    old = _sell(test_db, product)
    audit_before = test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    with pytest.raises(ValidationError) as exc_info:
        _correct(test_db, old, product, reason="  ")
    assert exc_info.value.code == ErrorCode.VOID_REASON_REQUIRED
    assert test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == audit_before


def test_the_new_fee_is_computed_from_the_method_as_it_is_today(test_db):
    method = add_payment_method(test_db, "Gateway", "IMMEDIATE", fee_bps=100)
    product = stocked_product(test_db, stock=5)
    old = _sell(test_db, product, price=10_000, payment_method_id=method, transaction_fee=0)
    new = _correct(test_db, old, product, price=10_000, payment_method_id=method)
    assert get_order(test_db, new)["order"]["transaction_fee"] == 100


def test_only_the_new_order_reaches_the_profit_and_loss(test_db):
    product = stocked_product(test_db, stock=5, unit_cost=1000)
    old = _sell(test_db, product, price=3000)
    pnl_before = get_profit_and_loss(test_db, DAY, DAY)
    _correct(test_db, old, product, price=2000)
    pnl = get_profit_and_loss(test_db, DAY, DAY)
    assert (pnl_before["order_count"], pnl_before["total_revenue"]) == (1, 3000)
    assert (pnl["order_count"], pnl["total_revenue"], pnl["cogs"]) == (1, 2000, 1000)
    assert pnl["refund_losses"] == 0


def test_void_order_alone_is_still_its_own_operation(test_db):
    product = stocked_product(test_db, stock=5)
    void_order(test_db, _sell(test_db, product), "x")
    assert list_audit_log(test_db, operation="void_order")["total"] > 0
