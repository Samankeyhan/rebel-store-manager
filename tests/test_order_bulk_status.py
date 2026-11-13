"""bulk_update_order_status: PAID -> COMPLETED for many orders in one transaction and one audit operation,
all or nothing, through `update_order_status` (the single-order rules are the only rules)."""

import json

import pytest

import db.orders
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.order_voids import void_order
from db.orders import BULK_STATUS_MAX, bulk_update_order_status, record_order, update_order_status
from db.returns import process_return
from db.settlements import record_settlement
from tests.helpers import sale_method, stocked_product


@pytest.fixture
def shop(test_db):
    return {"product": stocked_product(test_db, stock=100), "method": sale_method(test_db)}


def _sell(conn, shop, status="PAID", price=3000, **kwargs):
    return record_order(
        conn, "WEBSITE", [{"product_id": shop["product"], "quantity": 1, "unit_price": price}],
        packaging_kit_id=None, payment_method_id=shop["method"], status=status,
        order_date="2026-10-01", shipping_charge=0, **kwargs,
    )


def _row(conn, order_id):
    return dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())


def _status(conn, order_id):
    return _row(conn, order_id)["status"]


def _audit_count(conn):
    return conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]


def _stock_state(conn):
    return (
        conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0],
        [tuple(r) for r in conn.execute("SELECT id, current_stock, unit_cost FROM products ORDER BY id")],
        [tuple(r) for r in conn.execute("SELECT id, current_stock, unit_cost FROM materials ORDER BY id")],
    )


# ------------------------------------------------------------------ the change


def test_paid_orders_become_completed_and_the_result_lists_them_in_order(test_db, shop):
    ids = [_sell(test_db, shop) for _ in range(3)]
    result = bulk_update_order_status(test_db, [ids[2], ids[0], ids[1]], "COMPLETED")
    assert [r["id"] for r in result] == [ids[2], ids[0], ids[1]]
    assert all(r["status"] == "COMPLETED" and r["invoice_number"].startswith("INV-") for r in result)
    assert [_status(test_db, i) for i in ids] == ["COMPLETED"] * 3


def test_the_whole_change_is_one_audit_operation_with_one_row_per_order(test_db, shop):
    ids = [_sell(test_db, shop) for _ in range(3)]
    before = _audit_count(test_db)
    bulk_update_order_status(test_db, ids, "COMPLETED")

    rows = test_db.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (_audit_count(test_db) - before,)
    ).fetchall()
    assert len(rows) == 3  # nothing but the three status updates
    assert len({r["op_id"] for r in rows}) == 1 and rows[0]["op_id"]
    assert {r["operation"] for r in rows} == {"bulk_update_order_status"}
    assert sorted(int(r["entity_id"]) for r in rows) == sorted(ids)
    assert {(r["entity_type"], r["action"]) for r in rows} == {("orders", "UPDATE")}
    # only the status changed: no stock, paid date, settlement, fee or cost column is in the log
    assert all(
        json.loads(r["before_json"]) == {"status": "PAID"} and json.loads(r["after_json"]) == {"status": "COMPLETED"}
        for r in rows
    )
    assert test_db.execute("SELECT COUNT(*) FROM audit_context").fetchone()[0] == 0


def test_nothing_but_the_status_changes(test_db, shop):
    """PAID -> COMPLETED is not a payment and moves no stock: no movement, no paid date, settlement, fee or cost change."""
    ids = [_sell(test_db, shop, price=3000 + i) for i in range(3)]
    before_rows = {i: _row(test_db, i) for i in ids}
    before_stock = _stock_state(test_db)
    bulk_update_order_status(test_db, ids, "COMPLETED")
    for i in ids:
        after = _row(test_db, i)
        changed = {k for k in after if after[k] != before_rows[i][k]}
        assert changed <= {"status", "updated_at"}, changed
        assert after["status"] == "COMPLETED"
        for money_or_date in ("shipping_charge", "packaging_cost", "postage_cost", "transaction_fee", "paid_date",
                              "expected_settlement_date", "settlement_id", "paid_jalali_year", "paid_jalali_month",
                              "stock_committed", "payment_method_id"):
            assert after[money_or_date] == before_rows[i][money_or_date]
    assert _stock_state(test_db) == before_stock
    items_before = test_db.execute("SELECT SUM(list_price), SUM(unit_cost_at_time) FROM order_items").fetchone()
    assert tuple(items_before) == (3000 * 3 + 3, 500 * 3)


def test_it_gives_the_same_result_as_changing_each_order_on_its_own(test_db, shop):
    single, bulk = _sell(test_db, shop), _sell(test_db, shop)
    update_order_status(test_db, single, "COMPLETED")
    bulk_update_order_status(test_db, [bulk], "COMPLETED")
    skip = {"id", "invoice_number", "updated_at"}
    assert {k: v for k, v in _row(test_db, single).items() if k not in skip} == {
        k: v for k, v in _row(test_db, bulk).items() if k not in skip
    }


def test_each_order_goes_through_update_order_status(test_db, shop, monkeypatch):
    ids = [_sell(test_db, shop) for _ in range(3)]
    calls = []
    original = db.orders.update_order_status

    def spy(conn, order_id, new_status, paid_date=None):
        calls.append((order_id, new_status, paid_date))
        return original(conn, order_id, new_status, paid_date)

    monkeypatch.setattr(db.orders, "update_order_status", spy)
    bulk_update_order_status(test_db, ids, "COMPLETED")
    assert calls == [(i, "COMPLETED", None) for i in ids]


def test_a_settled_paid_order_completes_like_it_does_on_its_own(test_db, shop):
    settled, plain = _sell(test_db, shop), _sell(test_db, shop)
    record_settlement(test_db, shop["method"], "2026-10-05", 3000, order_ids=[settled])
    bulk_update_order_status(test_db, [settled, plain], "COMPLETED")
    row = _row(test_db, settled)
    assert (row["status"], row["settlement_id"] is not None) == ("COMPLETED", True)


# ------------------------------------------------------------------ all or nothing


def test_one_order_that_is_not_paid_refuses_the_whole_call_and_changes_nothing(test_db, shop):
    a, b, pending = _sell(test_db, shop), _sell(test_db, shop), _sell(test_db, shop, status="PENDING")
    audit, stock = _audit_count(test_db), _stock_state(test_db)
    with pytest.raises(ConflictError) as exc_info:
        bulk_update_order_status(test_db, [a, pending, b], "COMPLETED")
    assert exc_info.value.code == ErrorCode.ORDER_BULK_NOT_ELIGIBLE
    (entry,) = exc_info.value.details["ineligible"]
    assert (entry["order_id"], entry["status"], entry["invoice_number"]) == (
        pending, "PENDING", _row(test_db, pending)["invoice_number"])
    assert [_status(test_db, i) for i in (a, b, pending)] == ["PAID", "PAID", "PENDING"]
    assert _audit_count(test_db) == audit and _stock_state(test_db) == stock


def test_every_order_that_is_not_paid_is_listed_whatever_its_status(test_db, shop):
    paid = _sell(test_db, shop)
    completed = _sell(test_db, shop, status="COMPLETED")
    draft = _sell(test_db, shop, status="DRAFT")
    pending = _sell(test_db, shop, status="PENDING")
    cancelled = _sell(test_db, shop, status="PENDING")
    process_return(test_db, cancelled, "CANCELLED")
    voided = _sell(test_db, shop)
    void_order(test_db, voided, "entered twice")
    with pytest.raises(ConflictError) as exc_info:
        bulk_update_order_status(test_db, [paid, completed, draft, pending, cancelled, voided], "COMPLETED")
    found = {e["order_id"]: e["status"] for e in exc_info.value.details["ineligible"]}
    assert found == {completed: "COMPLETED", draft: "DRAFT", pending: "PENDING", cancelled: "CANCELLED",
                     voided: "VOIDED"}
    assert _status(test_db, paid) == "PAID"


def test_a_failure_part_way_undoes_the_orders_already_changed(test_db, shop, monkeypatch):
    ids = [_sell(test_db, shop) for _ in range(3)]
    audit = _audit_count(test_db)
    original = db.orders.update_order_status
    seen = []

    def failing(conn, order_id, new_status, paid_date=None):
        seen.append(order_id)
        if len(seen) == 2:
            raise RuntimeError("boom")
        return original(conn, order_id, new_status, paid_date)

    monkeypatch.setattr(db.orders, "update_order_status", failing)
    with pytest.raises(RuntimeError):
        bulk_update_order_status(test_db, ids, "COMPLETED")
    assert [_status(test_db, i) for i in ids] == ["PAID"] * 3
    assert _audit_count(test_db) == audit
    assert test_db.execute("SELECT COUNT(*) FROM audit_context").fetchone()[0] == 0


# ------------------------------------------------------------------ the request itself


def test_an_unknown_order_is_not_found_and_nothing_changes(test_db, shop):
    a = _sell(test_db, shop)
    with pytest.raises(NotFoundError):
        bulk_update_order_status(test_db, [a, 9999], "COMPLETED")
    assert _status(test_db, a) == "PAID"


@pytest.mark.parametrize("ids, field", [
    ([], "order_ids"),
    (None, "order_ids"),
    ("1", "order_ids"),
    ([1, 1], "order_ids"),
    ([True], "order_ids"),
    (["1"], "order_ids"),
    ([1.0], "order_ids"),
    (list(range(1, BULK_STATUS_MAX + 2)), "order_ids"),
])
def test_a_bad_list_is_a_validation_error_on_order_ids(test_db, ids, field):
    with pytest.raises(ValidationError) as exc_info:
        bulk_update_order_status(test_db, ids, "COMPLETED")
    assert exc_info.value.field == field


@pytest.mark.parametrize("status", ["PAID", "PENDING", "CANCELLED", "REFUNDED", "VOIDED", "DRAFT", "NOPE"])
def test_only_completed_is_a_bulk_target(test_db, shop, status):
    a = _sell(test_db, shop)
    with pytest.raises(ValidationError) as exc_info:
        bulk_update_order_status(test_db, [a], status)
    assert exc_info.value.field == "status"
    assert _status(test_db, a) == "PAID"


def test_a_list_of_the_largest_size_is_not_refused_for_its_size(test_db, shop):
    ids = [_sell(test_db, shop) for _ in range(5)]
    assert len(bulk_update_order_status(test_db, ids[:BULK_STATUS_MAX], "COMPLETED")) == 5
