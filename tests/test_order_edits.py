"""Light order edit (db/order_edits.py, accounting-rules section 20 "Light edit"): what each field changes, what
stays frozen, every refusal, the preview and the audit trail."""

from datetime import date

import pytest

import db.orders
import db.settlements
import db.timeutil
from db import jalali
from db.audit import list_audit_log
from db.distributions import record_profit_distribution
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.order_edits import edit_order, plan_order_edit
from db.order_voids import void_order
from db.orders import get_order, record_order
from db.partners import add_partner
from db.payment_methods import add_payment_method, deactivate_payment_method
from db.reports import get_profit_and_loss
from db.returns import process_return
from db.settlements import get_pending, record_settlement
from db.timeutil import local_day
from tests.helpers import make_legacy_no_method, stocked_product

TODAY = date(2026, 11, 13)  # 22 Aban 1405
MEHR_LAST = "2026-10-22"  # 30 Mehr 1405
ABAN_FIRST = "2026-10-23"  # 1 Aban 1405


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    for module in (db.orders, db.timeutil, db.settlements):
        monkeypatch.setattr(module, "today_local", lambda conn=None: TODAY)


@pytest.fixture
def shop(test_db):
    return {
        "product": stocked_product(test_db, stock=50, unit_cost=400_000),
        "card": add_payment_method(test_db, "Card", "IMMEDIATE"),
        "zarinpal": add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1, fee_bps=50, fee_fixed=5_000, fee_cap=160_000),
        "digipay": add_payment_method(test_db, "Digipay", "DAY_OF_NEXT_MONTH", 7, fee_bps=1320),
    }


def _sell(conn, shop, method="card", price=1_000_000, quantity=1, **kwargs):
    kwargs.setdefault("order_date", "2026-11-01")
    kwargs.setdefault("packaging_kit_id", None)
    kwargs.setdefault("shipping_charge", 0)
    kwargs.setdefault("postage_cost", 0)
    kwargs.setdefault("status", "PAID")
    return record_order(
        conn, "INSTAGRAM", [{"product_id": shop["product"], "quantity": quantity, "unit_price": price}],
        payment_method_id=shop[method], **kwargs,
    )


def _row(conn, order_id):
    return dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())


def _refused(conn, order_id, code, **changes):
    with pytest.raises(ConflictError) as exc_info:
        edit_order(conn, order_id, **changes)
    assert exc_info.value.code == code
    return exc_info.value.details


def _close(conn, period_end):
    add_partner(conn, "Solo", 100.0)
    return record_profit_distribution(conn, "2026-10-01", period_end, 0, allow_exceeding=True)


def _audit_count(conn):
    return conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]


def test_the_test_days_are_the_jalali_month_end():
    assert jalali.to_jalali(date.fromisoformat(MEHR_LAST)) == (1405, 7, 30)
    assert jalali.to_jalali(date.fromisoformat(ABAN_FIRST)) == (1405, 8, 1)


# ------------------------------------------------------------------ order_date


def test_a_shop_midnight_date_moves_across_the_jalali_month_end_and_stays_midnight(test_db, shop):
    order_id = _sell(test_db, shop, order_date=MEHR_LAST)
    assert _row(test_db, order_id)["order_date"] == "2026-10-21 20:30:00"  # Tehran midnight of 30 Mehr

    edit_order(test_db, order_id, order_date=ABAN_FIRST)

    row = _row(test_db, order_id)
    assert row["order_date"] == "2026-10-22 20:30:00"
    assert local_day(row["order_date"], test_db).isoformat() == ABAN_FIRST


def test_a_shop_midnight_date_moves_back_across_the_month_end(test_db, shop):
    order_id = _sell(test_db, shop, order_date=ABAN_FIRST)
    edit_order(test_db, order_id, order_date=MEHR_LAST)
    row = _row(test_db, order_id)
    assert row["order_date"] == "2026-10-21 20:30:00"
    assert local_day(row["order_date"], test_db).isoformat() == MEHR_LAST


@pytest.mark.parametrize("new_day", [ABAN_FIRST, "2026-10-01", "2026-11-13", "2026-03-20", "2026-03-21"])
def test_a_daytime_order_keeps_its_local_time_of_day(test_db, shop, new_day):
    order_id = _sell(test_db, shop, order_date=f"{MEHR_LAST} 14:15")
    assert _row(test_db, order_id)["order_date"] == "2026-10-22 10:45:00"

    edit_order(test_db, order_id, order_date=new_day)

    row = _row(test_db, order_id)
    assert local_day(row["order_date"], test_db).isoformat() == new_day
    assert row["order_date"][11:] == "10:45:00"


def test_a_late_evening_order_keeps_its_day_exactly(test_db, shop):
    # 23:59 Tehran is 20:29 UTC of the same day: the day must not slip.
    order_id = _sell(test_db, shop, order_date=f"{MEHR_LAST} 23:59")
    edit_order(test_db, order_id, order_date=ABAN_FIRST)
    row = _row(test_db, order_id)
    assert row["order_date"] == "2026-10-23 20:29:00"
    assert local_day(row["order_date"], test_db).isoformat() == ABAN_FIRST


def test_the_same_day_is_no_change_and_writes_nothing(test_db, shop):
    order_id = _sell(test_db, shop, order_date=f"{MEHR_LAST} 14:15")
    before, audit = _row(test_db, order_id), _audit_count(test_db)
    edit_order(test_db, order_id, order_date=MEHR_LAST)
    assert _row(test_db, order_id) == before
    assert _audit_count(test_db) == audit


def test_a_future_order_date_is_refused(test_db, shop):
    order_id = _sell(test_db, shop)
    with pytest.raises(ValidationError) as exc_info:
        edit_order(test_db, order_id, order_date="2026-11-14")
    assert exc_info.value.code == ErrorCode.DATE_IN_FUTURE
    assert exc_info.value.field == "order_date"


@pytest.mark.parametrize("bad", ["2026/10/22", "2026-10-22 10:00", "", 20261022, None])
def test_a_bad_order_date_is_refused(test_db, shop, bad):
    order_id = _sell(test_db, shop)
    with pytest.raises(ValidationError) as exc_info:
        edit_order(test_db, order_id, order_date=bad)
    assert exc_info.value.field == "order_date"


def test_a_date_edit_moves_the_whole_order_in_the_p_and_l_and_keeps_paid_date(test_db, shop):
    order_id = _sell(test_db, shop, method="zarinpal", order_date="2026-11-01", shipping_charge=200_000, postage_cost=150_000)
    old = get_profit_and_loss(test_db, "2026-11-01", "2026-11-01")
    before = _row(test_db, order_id)

    edit_order(test_db, order_id, order_date="2026-10-20")

    assert get_profit_and_loss(test_db, "2026-11-01", "2026-11-01")["total_revenue"] == 0
    moved = get_profit_and_loss(test_db, "2026-10-20", "2026-10-20")
    for key in ("total_revenue", "cogs", "postage_estimated", "transaction_fees", "gross_profit"):
        assert moved[key] == old[key], key
    after = _row(test_db, order_id)
    for column in ("paid_date", "expected_settlement_date", "transaction_fee", "paid_jalali_month"):
        assert after[column] == before[column], column


# ------------------------------------------------------------------ frozen figures


def test_an_edit_never_touches_items_costs_or_stock(test_db, shop):
    order_id = _sell(test_db, shop, method="zarinpal", quantity=2)
    items = get_order(test_db, order_id)["items"]
    movements = test_db.execute("SELECT * FROM stock_movements ORDER BY id").fetchall()
    stock = test_db.execute("SELECT current_stock, unit_cost FROM products").fetchall()
    before = _row(test_db, order_id)

    edit_order(
        test_db, order_id, order_date="2026-10-02", payment_method_id=shop["digipay"], paid_date="2026-10-03",
        shipping_charge=90_000, postage_cost=120_000, customer_name="Test Customer", notes="n", payment_reference="r",
    )

    assert get_order(test_db, order_id)["items"] == items
    assert [tuple(m) for m in test_db.execute("SELECT * FROM stock_movements ORDER BY id")] == [tuple(m) for m in movements]
    assert [tuple(s) for s in test_db.execute("SELECT current_stock, unit_cost FROM products")] == [tuple(s) for s in stock]
    row = _row(test_db, order_id)
    for column in ("invoice_number", "status", "packaging_kit_id", "packaging_cost", "stock_committed", "settlement_id"):
        assert row[column] == before[column], column


# ------------------------------------------------------------------ payment method and fee


def test_a_method_change_recomputes_the_fee_and_the_expected_date(test_db, shop):
    order_id = _sell(test_db, shop, method="card", price=94_900_000, order_date="2026-11-01")
    assert _row(test_db, order_id)["transaction_fee"] == 0

    edit_order(test_db, order_id, payment_method_id=shop["zarinpal"])

    row = _row(test_db, order_id)
    assert row["payment_method_id"] == shop["zarinpal"]
    assert row["transaction_fee"] == 165_000  # 0.5% capped at 160,000 + 5,000 (section 14 example)
    assert row["expected_settlement_date"] == "2026-11-02"
    assert row["paid_date"] == "2026-11-01"


def test_a_method_change_to_a_monthly_method_follows_its_rule(test_db, shop):
    order_id = _sell(test_db, shop, method="zarinpal", price=18_300_000, order_date="2026-11-01")
    edit_order(test_db, order_id, payment_method_id=shop["digipay"])
    row = _row(test_db, order_id)
    assert row["transaction_fee"] == 2_415_600  # 18,300,000 × 13.2%
    assert row["expected_settlement_date"] == "2026-11-28"  # 7 Azar 1405
    assert (row["paid_jalali_year"], row["paid_jalali_month"]) == (1405, 8)


def test_the_fee_rounds_half_even_to_the_rial(test_db, shop):
    method = add_payment_method(test_db, "Half", "IMMEDIATE", fee_bps=5)
    shop["half"] = method
    even = _sell(test_db, shop, price=1_000)  # 0.5 → 0
    odd = _sell(test_db, shop, price=3_000)  # 1.5 → 2
    edit_order(test_db, even, payment_method_id=method)
    edit_order(test_db, odd, payment_method_id=method)
    assert _row(test_db, even)["transaction_fee"] == 0
    assert _row(test_db, odd)["transaction_fee"] == 2


def test_a_hand_fee_can_be_kept_with_a_method_change(test_db, shop):
    order_id = _sell(test_db, shop, method="card")
    edit_order(test_db, order_id, payment_method_id=shop["zarinpal"], transaction_fee=0)
    assert _row(test_db, order_id)["transaction_fee"] == 0


def test_a_fee_alone_is_refused(test_db, shop):
    order_id = _sell(test_db, shop)
    with pytest.raises(ValidationError) as exc_info:
        edit_order(test_db, order_id, transaction_fee=10)
    assert exc_info.value.field == "transaction_fee"


def test_a_method_cannot_be_cleared_and_must_be_active(test_db, shop):
    order_id = _sell(test_db, shop)
    with pytest.raises(ValidationError) as exc_info:
        edit_order(test_db, order_id, payment_method_id=None)
    assert exc_info.value.code == ErrorCode.PAYMENT_METHOD_REQUIRED
    deactivate_payment_method(test_db, shop["zarinpal"])
    with pytest.raises(ValidationError) as exc_info:
        edit_order(test_db, order_id, payment_method_id=shop["zarinpal"])
    assert exc_info.value.code == ErrorCode.PAYMENT_METHOD_INACTIVE
    with pytest.raises(NotFoundError):
        edit_order(test_db, order_id, payment_method_id=9999)


def test_the_order_moves_to_the_new_methods_pending_list(test_db, shop):
    order_id = _sell(test_db, shop, method="card")
    edit_order(test_db, order_id, payment_method_id=shop["zarinpal"])
    pending = {p["payment_method_id"] for p in get_pending(test_db)}
    assert pending == {shop["zarinpal"]}


def test_a_method_on_a_legacy_order_without_paid_date_takes_the_order_day(test_db, shop):
    order_id = make_legacy_no_method(test_db, _sell(test_db, shop, order_date="2026-10-25"))
    test_db.execute("UPDATE orders SET paid_date = NULL, paid_jalali_year = NULL, paid_jalali_month = NULL WHERE id = ?", (order_id,))

    edit_order(test_db, order_id, payment_method_id=shop["digipay"], order_date="2026-10-26")

    row = _row(test_db, order_id)
    assert row["paid_date"] == "2026-10-26"
    assert row["expected_settlement_date"] == "2026-11-28"
    assert (row["paid_jalali_year"], row["paid_jalali_month"]) == (1405, 8)


def test_a_method_on_a_pending_order_changes_only_method_and_fee(test_db, shop):
    order_id = _sell(test_db, shop, method="card", status="PENDING")
    edit_order(test_db, order_id, payment_method_id=shop["zarinpal"])
    row = _row(test_db, order_id)
    assert row["transaction_fee"] == 10_000
    assert row["paid_date"] is None and row["expected_settlement_date"] is None


def test_a_method_into_a_settled_month_is_refused(test_db, shop):
    mehr = _sell(test_db, shop, method="digipay", order_date="2026-10-10")
    record_settlement(test_db, shop["digipay"], "2026-10-29", 0, jalali_year=1405, jalali_month=7)
    order_id = _sell(test_db, shop, method="card", order_date="2026-10-11")
    details = _refused(test_db, order_id, ErrorCode.MONTH_ALREADY_SETTLED, payment_method_id=shop["digipay"])
    assert (details["jalali_year"], details["jalali_month"]) == (1405, 7)
    assert _row(test_db, mehr)["settlement_id"] is not None


# ------------------------------------------------------------------ paid_date


def test_a_paid_date_edit_recomputes_the_expected_date_and_month(test_db, shop):
    order_id = _sell(test_db, shop, method="digipay", order_date="2026-10-20")
    assert _row(test_db, order_id)["paid_jalali_month"] == 7
    edit_order(test_db, order_id, paid_date=ABAN_FIRST)
    row = _row(test_db, order_id)
    assert row["paid_date"] == ABAN_FIRST
    assert (row["paid_jalali_month"], row["expected_settlement_date"]) == (8, "2026-11-28")
    assert row["transaction_fee"] == 132_000


def test_a_paid_date_on_an_unpaid_order_is_refused(test_db, shop):
    order_id = _sell(test_db, shop, status="PENDING")
    details = _refused(test_db, order_id, ErrorCode.ORDER_NOT_PAID, paid_date="2026-11-02")
    assert details == {"order_id": order_id, "status": "PENDING"}


def test_a_paid_date_cannot_be_cleared_or_in_the_future(test_db, shop):
    order_id = _sell(test_db, shop)
    with pytest.raises(ValidationError):
        edit_order(test_db, order_id, paid_date=None)
    with pytest.raises(ValidationError) as exc_info:
        edit_order(test_db, order_id, paid_date="2026-11-14")
    assert exc_info.value.code == ErrorCode.DATE_IN_FUTURE


# ------------------------------------------------------------------ shipping and postage


def test_a_shipping_change_moves_revenue_fee_and_the_pending_amount(test_db, shop):
    order_id = _sell(test_db, shop, method="zarinpal", price=1_000_000, shipping_charge=0)
    edit_order(test_db, order_id, shipping_charge=180_000)
    detail = get_order(test_db, order_id)
    assert detail["customer_total"] == 1_180_000
    assert detail["order"]["transaction_fee"] == 5_900 + 5_000
    group = get_pending(test_db)[0]
    assert sum(o["expected_amount"] for g in group["groups"] for o in g["orders"]) == 1_180_000 - 10_900


def test_a_shipping_change_on_a_legacy_no_method_order_keeps_its_fee(test_db, shop):
    order_id = make_legacy_no_method(test_db, _sell(test_db, shop, method="zarinpal"))
    fee = _row(test_db, order_id)["transaction_fee"]
    edit_order(test_db, order_id, shipping_charge=50_000)
    assert _row(test_db, order_id)["transaction_fee"] == fee


def test_a_postage_change_moves_only_profit(test_db, shop):
    order_id = _sell(test_db, shop, method="zarinpal", postage_cost=100_000)
    before = get_order(test_db, order_id)
    edit_order(test_db, order_id, postage_cost=130_000)
    after = get_order(test_db, order_id)
    assert after["profit"] == before["profit"] - 30_000
    assert after["customer_total"] == before["customer_total"]
    assert after["order"]["transaction_fee"] == before["order"]["transaction_fee"]


@pytest.mark.parametrize("field", ["shipping_charge", "postage_cost"])
@pytest.mark.parametrize("bad", [-1, 1.5, "10", True, None, 2**53])
def test_a_bad_amount_is_refused(test_db, shop, field, bad):
    order_id = _sell(test_db, shop)
    before = _row(test_db, order_id)
    with pytest.raises(ValidationError):
        edit_order(test_db, order_id, **{field: bad})
    assert _row(test_db, order_id) == before


# ------------------------------------------------------------------ text fields


def test_text_fields_are_stripped_and_blank_clears_them(test_db, shop):
    order_id = _sell(test_db, shop, customer_name="Old", notes="note")
    edit_order(test_db, order_id, customer_name="  New Name ", notes="   ", payment_reference=" ref-1 ")
    row = _row(test_db, order_id)
    assert (row["customer_name"], row["notes"], row["payment_reference"]) == ("New Name", None, "ref-1")


def test_text_is_limited_in_length(test_db, shop):
    order_id = _sell(test_db, shop)
    with pytest.raises(ValidationError) as exc_info:
        edit_order(test_db, order_id, notes="x" * 501)
    assert exc_info.value.field == "notes"


# ------------------------------------------------------------------ refusals


def _settled(conn, shop):
    order_id = _sell(conn, shop, method="card", order_date="2026-11-01", postage_cost=100_000)
    record_settlement(conn, shop["card"], "2026-11-02", 1_000_000, order_ids=[order_id])
    return order_id


@pytest.mark.parametrize("changes", [
    {"shipping_charge": 1}, {"order_date": "2026-11-02"}, {"paid_date": "2026-11-02"},
    {"payment_method_id": "zarinpal"}, {"postage_cost": 5, "shipping_charge": 1},
])
def test_a_settled_order_refuses_money_and_dates(test_db, shop, changes):
    order_id = _settled(test_db, shop)
    changes = {k: shop[v] if k == "payment_method_id" else v for k, v in changes.items()}
    before = _row(test_db, order_id)
    details = _refused(test_db, order_id, ErrorCode.ORDER_ALREADY_SETTLED, **changes)
    assert details == {"order_id": order_id, "settlement_id": before["settlement_id"]}
    assert _row(test_db, order_id) == before


def test_a_settled_order_still_takes_postage_and_text(test_db, shop):
    order_id = _settled(test_db, shop)
    settlement = dict(test_db.execute("SELECT * FROM settlements").fetchone())
    edit_order(test_db, order_id, postage_cost=140_000, customer_name="C", notes="N", payment_reference="R")
    row = _row(test_db, order_id)
    assert (row["postage_cost"], row["customer_name"], row["notes"], row["payment_reference"]) == (140_000, "C", "N", "R")
    assert dict(test_db.execute("SELECT * FROM settlements").fetchone()) == settlement


def test_a_voided_order_refuses_every_field(test_db, shop):
    order_id = _sell(test_db, shop)
    void_order(test_db, order_id, "wrong")
    for changes in ({"notes": "x"}, {"postage_cost": 1}):
        details = _refused(test_db, order_id, ErrorCode.ORDER_ALREADY_VOIDED, **changes)
        assert details["order_id"] == order_id


@pytest.mark.parametrize("status", ["DRAFT", "CANCELLED", "REFUNDED"])
def test_draft_and_returned_orders_refuse_money_and_dates_but_take_text(test_db, shop, status):
    if status == "DRAFT":
        order_id = _sell(test_db, shop, status="DRAFT")
    else:
        order_id = _sell(test_db, shop, status="PAID")
        process_return(test_db, order_id, status, "back")
    details = _refused(test_db, order_id, ErrorCode.ORDER_EDIT_NOT_ALLOWED, shipping_charge=7, postage_cost=9)
    assert details == {"order_id": order_id, "status": status, "fields": ["shipping_charge", "postage_cost"]}
    edit_order(test_db, order_id, notes="kept", customer_name="Name")
    assert _row(test_db, order_id)["notes"] == "kept"


@pytest.mark.parametrize("old_day, new_day", [("2026-10-05", "2026-11-01"), ("2026-11-01", "2026-10-05")])
def test_a_closed_old_or_new_day_is_refused(test_db, shop, old_day, new_day):
    order_id = _sell(test_db, shop, order_date=old_day)
    distribution = _close(test_db, "2026-10-15")
    details = _refused(test_db, order_id, ErrorCode.PERIOD_ALREADY_DISTRIBUTED, order_date=new_day)
    assert details == {"distribution_id": distribution, "period_end": "2026-10-15", "date": "2026-10-05"}


def test_a_closed_day_refuses_postage_but_takes_text(test_db, shop):
    order_id = _sell(test_db, shop, order_date="2026-10-05")
    _close(test_db, "2026-10-15")
    _refused(test_db, order_id, ErrorCode.PERIOD_ALREADY_DISTRIBUTED, postage_cost=1)
    edit_order(test_db, order_id, customer_name="Fine", notes="ok")
    assert _row(test_db, order_id)["customer_name"] == "Fine"


@pytest.mark.parametrize("changes", [{}, {"items": []}, {"packaging_kit_id": None}, {"status": "PAID"}])
def test_an_empty_or_unknown_edit_is_refused(test_db, shop, changes):
    order_id = _sell(test_db, shop)
    with pytest.raises(ValidationError):
        edit_order(test_db, order_id, **changes)


def test_an_unknown_order_is_not_found(test_db):
    with pytest.raises(NotFoundError):
        edit_order(test_db, 404, notes="x")
    with pytest.raises(NotFoundError):
        plan_order_edit(test_db, 404, {"notes": "x"})


# ------------------------------------------------------------------ audit and preview


def test_an_edit_is_one_audited_operation_with_before_and_after(test_db, shop):
    order_id = _sell(test_db, shop, method="card", order_date=MEHR_LAST)
    edit_order(test_db, order_id, order_date=ABAN_FIRST, payment_method_id=shop["zarinpal"], notes="fixed")

    rows = list_audit_log(test_db, operation="edit_order")["items"]
    assert len({r["op_id"] for r in rows}) == 1
    assert [(r["entity_type"], r["action"]) for r in rows] == [("orders", "UPDATE")]
    before, after = rows[0]["before"], rows[0]["after"]
    assert before["order_date"] == "2026-10-21 20:30:00" and after["order_date"] == "2026-10-22 20:30:00"
    assert (before["payment_method_id"], after["payment_method_id"]) == (shop["card"], shop["zarinpal"])
    assert (before["transaction_fee"], after["transaction_fee"]) == (0, 10_000)
    assert after["notes"] == "fixed"


def test_the_preview_writes_nothing_and_matches_the_edit(test_db, shop):
    order_id = _sell(test_db, shop, method="card", order_date=MEHR_LAST)
    changes = {"order_date": ABAN_FIRST, "payment_method_id": shop["digipay"], "paid_date": ABAN_FIRST,
               "shipping_charge": 180_000, "customer_name": "C"}
    before, audit = _row(test_db, order_id), _audit_count(test_db)

    preview = plan_order_edit(test_db, order_id, changes)

    assert _row(test_db, order_id) == before and _audit_count(test_db) == audit
    assert preview["blockers"] == []
    assert [c["field"] for c in preview["changes"]] == [
        "order_date", "payment_method_id", "transaction_fee", "paid_date", "shipping_charge", "customer_name",
    ]
    assert preview["changes"][0] == {"field": "order_date", "before": MEHR_LAST, "after": ABAN_FIRST}
    edit_order(test_db, order_id, **changes)
    detail = get_order(test_db, order_id)
    figures = preview["figures"]
    assert figures["customer_total"] == {"before": 1_000_000, "after": detail["customer_total"]}
    assert figures["profit"]["after"] == detail["profit"]
    assert figures["transaction_fee"]["after"] == detail["order"]["transaction_fee"]
    assert figures["expected_settlement_date"]["after"] == detail["order"]["expected_settlement_date"] == "2026-11-28"
    assert figures["order_day"] == {"before": MEHR_LAST, "after": ABAN_FIRST}
    assert figures["settlement_amount"]["after"] == detail["customer_total"] - detail["order"]["transaction_fee"]


def test_the_preview_lists_every_blocker(test_db, shop):
    order_id = _settled(test_db, shop)
    _close(test_db, "2026-11-05")
    preview = plan_order_edit(test_db, order_id, {"shipping_charge": 5})
    assert [b["code"] for b in preview["blockers"]] == ["ORDER_ALREADY_SETTLED", "PERIOD_ALREADY_DISTRIBUTED"]


def test_the_preview_raises_input_errors(test_db, shop):
    order_id = _sell(test_db, shop)
    with pytest.raises(ValidationError):
        plan_order_edit(test_db, order_id, {"shipping_charge": -5})
