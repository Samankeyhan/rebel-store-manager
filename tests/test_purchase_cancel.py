"""Cancelling a purchase invoice entered by mistake (db/purchase_cancel.py, accounting rules section 23): what goes back
out, the exact cost restore, what is refused and in which order, payments, and how a cancelled invoice leaves the
purchase figures."""

import pytest

from db.adjustments import record_service_waste, record_stock_adjustment
from db.distributions import record_profit_distribution
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.materials import add_material, get_material, set_material_cost
from db.order_voids import void_order
from db.orders import get_order, record_order
from db.partners import add_partner
from db.production import run_production_batch
from db.products import add_product, get_product
from db.purchase_cancel import cancel_purchase, plan_cancel_purchase
from db.purchases import get_purchase, list_purchases, record_purchase
from db.recipes import add_recipe_item
from db.reports import get_purchases_summary
from db.stocktake import apply_stocktake
from db.supplier_payments import get_payables, list_supplier_payments, record_supplier_payment
from db.suppliers import add_supplier
from tests.helpers import cat

DAY = "2026-10-10"


def line(item_id, quantity=10, total=1000, kind="MATERIAL"):
    return {"kind": kind, "item_id": item_id, "quantity_bought": quantity, "total_paid": total}


@pytest.fixture
def shop(test_db):
    ids = {
        "paper": add_material(test_db, "Cancel Paper", "STOCK", 0),
        "ink": add_material(test_db, "Cancel Ink", "STOCK", 50, initial_stock=4),
        "print": add_material(test_db, "Cancel Printing", "SERVICE", 70),
        "tee": add_product(test_db, "Cancel Tee", cat(test_db, "TSHIRT"), 3000, 2000),
        "acme": add_supplier(test_db, "Cancel Acme"),
        "other": add_supplier(test_db, "Cancel Other"),
    }
    return test_db, ids


def buy(conn, ids, lines, **kwargs):
    """A purchase on credit from Cancel Acme (no payment to get in the way) unless the test says otherwise."""
    kwargs.setdefault("supplier_id", ids["acme"])
    kwargs.setdefault("payment", {"mode": "NONE"})
    return record_purchase(conn, lines, **kwargs)


def _item(conn, kind, item_id):
    item = get_material(conn, item_id) if kind == "MATERIAL" else get_product(conn, item_id)
    return item["current_stock"], item["unit_cost"]


def _codes(conn, purchase_id):
    return [b["code"] for b in plan_cancel_purchase(conn, purchase_id)["blockers"]]


def _refused(conn, purchase_id, code, **kwargs):
    with pytest.raises(ConflictError) as exc:
        cancel_purchase(conn, purchase_id, "wrong", **kwargs)
    assert exc.value.code == code
    return exc.value.details


# ---------------------------------------------------------------- what a cancel writes


def test_a_multi_line_invoice_goes_back_out_in_one_operation(shop):
    conn, ids = shop
    before = {k: _item(conn, kind, ids[k]) for k, kind in (("paper", "MATERIAL"), ("ink", "MATERIAL"), ("print", "MATERIAL"), ("tee", "PRODUCT"))}
    purchase = buy(
        conn, ids,
        [line(ids["paper"], 10, 5000), line(ids["ink"], 6, 600), line(ids["print"], 3, 900), line(ids["tee"], 2, 800, "PRODUCT")],
        supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"},
    )
    assert _codes(conn, purchase) == []
    cancel_purchase(conn, purchase, "  wrong   supplier invoice ")
    after = {k: _item(conn, kind, ids[k]) for k, kind in (("paper", "MATERIAL"), ("ink", "MATERIAL"), ("print", "MATERIAL"), ("tee", "PRODUCT"))}
    assert after == before  # stock and cost exactly as before: paper 0 / 0, ink 4 / 50, printing NULL / 70, tee 0 / NULL
    invoice = get_purchase(conn, purchase)
    assert (invoice["status"], invoice["cancel_reason"]) == ("CANCELLED", "wrong supplier invoice")
    assert invoice["cancelled_at"] is not None and invoice["total"] == 7300  # every figure stays
    cancels = conn.execute(
        "SELECT item_type, item_id, quantity_change, reason, notes FROM stock_movements WHERE notes LIKE 'ابطال خرید%' ORDER BY id"
    ).fetchall()
    assert [(c["item_type"], c["item_id"], c["quantity_change"], c["reason"]) for c in cancels] == [
        ("MATERIAL", ids["paper"], -10, "PURCHASE"), ("MATERIAL", ids["ink"], -6, "PURCHASE"), ("PRODUCT", ids["tee"], -2, "PURCHASE"),
    ]  # the service line writes none
    assert cancels[0]["notes"] == f"ابطال خرید {invoice['invoice_number']} — wrong supplier invoice"
    links = conn.execute("SELECT cancel_movement_id FROM material_purchases WHERE purchase_invoice_id = ? ORDER BY id", (purchase,)).fetchall()
    assert [r[0] is not None for r in links] == [True, True, False]
    ops = {r[0] for r in conn.execute("SELECT op_id FROM audit_log WHERE operation = 'cancel_purchase'")}
    assert len(ops) == 1


def test_an_unchanged_cost_and_a_fractional_stock_to_exactly_zero(shop):
    conn, ids = shop
    record_stock_adjustment(conn, "MATERIAL", ids["ink"], -4, "ADJUSTMENT")
    purchase = buy(conn, ids, [line(ids["ink"], 0.3, 15)])  # bought at its own cost: 50 stays 50
    record_stock_adjustment(conn, "MATERIAL", ids["paper"], 0.1, "ADJUSTMENT")
    second = buy(conn, ids, [line(ids["paper"], 0.2, 20)])
    cancel_purchase(conn, purchase, "x")
    cancel_purchase(conn, second, "x")
    assert _item(conn, "MATERIAL", ids["ink"]) == (0, 50)
    assert _item(conn, "MATERIAL", ids["paper"])[0] == pytest.approx(0.1)


def test_a_sale_between_keeps_its_frozen_cogs(shop):
    conn, ids = shop
    tee = ids["tee"]
    old = buy(conn, ids, [line(tee, 5, 1000, "PRODUCT")], purchase_date=DAY)  # tee cost 200
    purchase = buy(conn, ids, [line(tee, 5, 3000, "PRODUCT")], purchase_date=DAY)  # tee cost 400
    order = record_order(conn, "IN_PERSON", [{"product_id": tee, "quantity": 2, "unit_price": 3000}], packaging_kit_id=None, order_date=DAY)
    frozen = get_order(conn, order)["items"][0]["unit_cost_at_time"]
    assert frozen == 400  # (5 x 200 + 3000) / 10
    cancel_purchase(conn, purchase, "x")  # 8 in stock, 5 go back out
    assert _item(conn, "PRODUCT", tee) == (3, 200)
    assert get_order(conn, order)["items"][0]["unit_cost_at_time"] == frozen
    assert get_purchase(conn, old)["status"] == "ACTIVE"


def test_a_service_line_restores_the_price_and_the_waste_after_it_stays(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["print"], 4, 2000)])  # price 70 -> 500
    record_service_waste(conn, ids["print"], 1)  # frozen at 500
    cancel_purchase(conn, purchase, "x")
    assert get_material(conn, ids["print"])["unit_cost"] == 70
    waste = conn.execute("SELECT unit_cost_at_time FROM stock_movements WHERE reason = 'WASTE'").fetchone()[0]
    assert waste == 500


# ---------------------------------------------------------------- refusals, in order


def test_an_unknown_or_already_cancelled_purchase(shop):
    conn, ids = shop
    with pytest.raises(NotFoundError) as exc:
        cancel_purchase(conn, 999, "x")
    assert exc.value.code == ErrorCode.PURCHASE_NOT_FOUND
    purchase = buy(conn, ids, [line(ids["paper"])])
    cancel_purchase(conn, purchase, "x")
    details = _refused(conn, purchase, ErrorCode.PURCHASE_ALREADY_CANCELLED)
    assert details["purchase_id"] == purchase and details["replaced_by_purchase_id"] is None


def test_a_blank_or_long_reason(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["paper"])])
    with pytest.raises(ValidationError) as exc:
        cancel_purchase(conn, purchase, "   ")
    assert exc.value.code == ErrorCode.VOID_REASON_REQUIRED and exc.value.field == "reason"
    with pytest.raises(ValidationError):
        cancel_purchase(conn, purchase, "x" * 501)


def test_payments_need_with_payments_and_then_go_with_it(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "PARTIAL", "amount": 1000})
    record_supplier_payment(conn, ids["acme"], DAY, 500, "CASH")
    details = _refused(conn, purchase, ErrorCode.PURCHASE_HAS_PAYMENTS)
    assert (details["paid"], details["shared"], len(details["payment_ids"])) == (1500, 0, 2)
    preview = plan_cancel_purchase(conn, purchase)
    assert [(p["amount"], p["method"], p["shared"]) for p in preview["payments"]] == [(1000, "OTHER", 0), (500, "CASH", 0)]
    cancel_purchase(conn, purchase, "x", with_payments=True)
    assert list_supplier_payments(conn) == []
    assert get_payables(conn)["outstanding_total"] == 0
    rows = conn.execute("SELECT DISTINCT operation FROM audit_log WHERE entity_type = 'supplier_payments' AND action = 'DELETE'").fetchall()
    assert [r[0] for r in rows] == ["cancel_purchase"]


def test_a_shared_payment_refuses_even_with_payments(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    buy(conn, ids, [line(ids["ink"], 1, 100)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    record_supplier_payment(conn, ids["acme"], DAY, 4100, "CASH")
    details = _refused(conn, purchase, ErrorCode.PURCHASE_HAS_PAYMENTS, with_payments=True)
    assert details["shared"] == 1
    assert len(list_supplier_payments(conn)) == 1


def test_a_closed_day(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["paper"])], purchase_date="2026-10-05")
    add_partner(conn, "Solo", 100.0)
    record_profit_distribution(conn, "2026-10-01", "2026-10-05", 0, allow_exceeding=True)
    _refused(conn, purchase, ErrorCode.PERIOD_ALREADY_DISTRIBUTED)


def test_stock_used(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["ink"], 6, 600), line(ids["paper"], 10, 1000)])
    record_stock_adjustment(conn, "MATERIAL", ids["paper"], -1, "WASTE")
    details = _refused(conn, purchase, ErrorCode.PURCHASE_STOCK_USED)
    assert (details["line_index"], details["item_id"], details["current_stock"], details["quantity_bought"]) == (1, ids["paper"], 9, 10)


def test_a_stocktake_loss_after(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["paper"], 10, 1000)])
    apply_stocktake(conn, [{"item_type": "MATERIAL", "item_id": ids["ink"], "counted": 4, "system_quantity": 4}])  # no change
    record_stock_adjustment(conn, "MATERIAL", ids["paper"], 5, "ADJUSTMENT")
    apply_stocktake(conn, [{"item_type": "MATERIAL", "item_id": ids["paper"], "counted": 14, "system_quantity": 15}])
    details = _refused(conn, purchase, ErrorCode.STOCKTAKE_AFTER_PURCHASE)
    assert details["item_id"] == ids["paper"] and details["stocktake_date"]


@pytest.mark.parametrize("event", ["purchase", "production", "costed_adjustment", "plain_gain", "void_return"])
def test_a_later_stock_in_is_a_later_cost_event(shop, event):
    conn, ids = shop
    tee = ids["tee"]
    purchase = buy(conn, ids, [line(tee, 5, 1000, "PRODUCT")], purchase_date=DAY)
    if event == "purchase":
        later = buy(conn, ids, [line(tee, 1, 300, "PRODUCT")], purchase_date=DAY)
    elif event == "production":
        add_recipe_item(conn, tee, ids["print"], 1)
        run_production_batch(conn, tee, 1)
    elif event == "costed_adjustment":
        record_stock_adjustment(conn, "PRODUCT", tee, 1, "ADJUSTMENT", unit_cost=500)
    elif event == "plain_gain":
        record_stock_adjustment(conn, "PRODUCT", tee, 1, "ADJUSTMENT")
    else:
        order = record_order(conn, "IN_PERSON", [{"product_id": tee, "quantity": 1, "unit_price": 3000}], packaging_kit_id=None, order_date=DAY)
        void_order(conn, order, "mistake")
    details = _refused(conn, purchase, ErrorCode.PURCHASE_COST_CHANGED_SINCE)
    assert details["later"] and details["item_id"] == tee
    if event == "purchase":
        assert details["later"][0]["purchase_id"] == later and details["later"][0]["invoice_number"].startswith("PUR-")


def test_newest_first_then_the_older_one_d1(shop):
    conn, ids = shop
    first = buy(conn, ids, [line(ids["paper"], 10, 1000)])
    second = buy(conn, ids, [line(ids["paper"], 10, 3000)])
    assert "PURCHASE_COST_CHANGED_SINCE" in _codes(conn, first)
    cancel_purchase(conn, second, "x")
    assert _codes(conn, first) == []  # the cancelled later purchase no longer blocks
    cancel_purchase(conn, first, "x")
    assert _item(conn, "MATERIAL", ids["paper"]) == (0, 0)


def test_a_cost_changed_without_a_movement(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["paper"], 3, 1)])  # 0.33 rounds to 0: the material stays "not entered"
    set_material_cost(conn, ids["paper"], 900)
    details = _refused(conn, purchase, ErrorCode.PURCHASE_COST_CHANGED_SINCE)
    assert details["later"] == [] and details["cost_changed_without_movement"] == 1


def test_a_later_line_of_the_same_service(shop):
    conn, ids = shop
    first = buy(conn, ids, [line(ids["print"], 2, 400)])
    second = buy(conn, ids, [line(ids["print"], 2, 800)])
    details = _refused(conn, first, ErrorCode.PURCHASE_COST_CHANGED_SINCE)
    assert details["later"][0]["purchase_id"] == second and details["later"][0]["movement_id"] is None
    cancel_purchase(conn, second, "x")
    cancel_purchase(conn, first, "x")
    assert get_material(conn, ids["print"])["unit_cost"] == 70


def test_a_legacy_line_without_cost_history(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["paper"])])
    conn.execute("UPDATE material_purchases SET item_cost_before = NULL, item_cost_after = NULL WHERE purchase_invoice_id = ?", (purchase,))
    _refused(conn, purchase, ErrorCode.PURCHASE_COST_HISTORY_UNKNOWN)
    other = buy(conn, ids, [line(ids["ink"], 1, 50)])
    conn.execute("UPDATE material_purchases SET stock_movement_id = NULL WHERE purchase_invoice_id = ?", (other,))
    assert _codes(conn, other) == ["PURCHASE_COST_HISTORY_UNKNOWN"]


def test_one_blocked_line_refuses_the_whole_invoice_and_writes_nothing(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["ink"], 6, 600), line(ids["paper"], 10, 1000)])
    buy(conn, ids, [line(ids["paper"], 1, 100)])
    before = (_item(conn, "MATERIAL", ids["ink"]), conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0])
    _refused(conn, purchase, ErrorCode.PURCHASE_COST_CHANGED_SINCE)
    assert (_item(conn, "MATERIAL", ids["ink"]), conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]) == before
    assert get_purchase(conn, purchase)["status"] == "ACTIVE"


def test_the_preview_lists_every_blocker_in_order_and_what_would_change(shop):
    conn, ids = shop
    purchase = buy(conn, ids, [line(ids["paper"], 10, 1000), line(ids["print"], 2, 400)], purchase_date="2026-10-05", payment=None)
    record_stock_adjustment(conn, "MATERIAL", ids["paper"], -2, "WASTE")
    buy(conn, ids, [line(ids["paper"], 1, 100)])
    add_partner(conn, "Solo", 100.0)
    record_profit_distribution(conn, "2026-10-01", "2026-10-05", 0, allow_exceeding=True)
    preview = plan_cancel_purchase(conn, purchase)
    assert [b["code"] for b in preview["blockers"]] == [
        "PURCHASE_HAS_PAYMENTS", "PERIOD_ALREADY_DISTRIBUTED", "PURCHASE_STOCK_USED", "PURCHASE_COST_CHANGED_SINCE",
    ]
    paper, printing = preview["lines"]
    assert (paper["item_type"], paper["quantity"], paper["stock_before"], paper["cost_after"]) == ("STOCK", 10, 9, 0)  # 10 bought, 2 wasted, 1 bought later
    assert (printing["item_type"], printing["stock_before"], printing["stock_after"], printing["cost_before"], printing["cost_after"]) == (
        "SERVICE", None, None, 200, 70)
    assert preview["paid"] == 1400


# ---------------------------------------------------------------- reads


def test_a_cancelled_invoice_leaves_the_list_and_the_summary(shop):
    conn, ids = shop
    keep = buy(conn, ids, [line(ids["ink"], 1, 50)], purchase_date=DAY)
    gone = buy(conn, ids, [line(ids["paper"], 10, 1000), line(ids["print"], 1, 300)], purchase_date=DAY)
    cancel_purchase(conn, gone, "x")
    assert [p["id"] for p in list_purchases(conn)] == [keep]
    assert {p["id"] for p in list_purchases(conn, include_cancelled=True)} == {keep, gone}
    summary = get_purchases_summary(conn)
    assert (summary["material_purchases_total"], summary["service_purchases_total"], summary["purchase_invoices_count"]) == (50, 0, 1)
