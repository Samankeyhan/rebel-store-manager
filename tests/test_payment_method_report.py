"""db/reports.py::get_payment_method_report and its reconciliation with the
P&L (accounting-rules.md sections 9 and 14)."""

from datetime import date

import pytest

import db.orders
import db.settlements
from db.orders import get_revenue_summary, record_order
from db.payment_methods import add_payment_method, deactivate_payment_method
from db.reports import get_payment_method_report, get_profit_and_loss
from db.returns import process_return
from db.settlements import record_settlement
from db.timeutil import to_utc_range
from tests.helpers import stocked_product

TODAY = date(2026, 10, 6)

RANGES = [
    (None, None),
    ("2026-10-01", "2026-10-31"),
    ("2026-09-01", "2026-09-30"),
    ("2026-10-03", "2026-10-03"),
    ("2026-11-01", None),
]


@pytest.fixture
def fixed_today(monkeypatch):
    for module in (db.orders, db.settlements):
        monkeypatch.setattr(module, "today_local", lambda conn=None: TODAY)


def _order(conn, product_id, method_id, order_date, price=100000, **kwargs):
    kwargs.setdefault("shipping_charge", 0)
    kwargs.setdefault("postage_cost", 0)
    return record_order(
        conn,
        "WEBSITE",
        [{"product_id": product_id, "quantity": 1, "unit_price": price}],
        order_date=order_date,
        packaging_kit_id=None,
        payment_method_id=method_id,
        **kwargs,
    )


@pytest.fixture
def report_data(test_db, fixed_today):
    conn = test_db
    product_id = stocked_product(conn, stock=1000)
    card = add_payment_method(conn, "Card to card", "IMMEDIATE")
    zarinpal = add_payment_method(conn, "Zarinpal", "DAYS_AFTER", 1, fee_bps=150, fee_fixed=500)
    digipay = add_payment_method(conn, "Digipay", "DAY_OF_NEXT_MONTH", 7, fee_bps=300)
    unused_old = add_payment_method(conn, "Unused old", "IMMEDIATE")
    used_old = add_payment_method(conn, "Used old", "IMMEDIATE", fee_fixed=250)

    # Zarinpal: fee = 1.5% + 500.
    z1 = _order(conn, product_id, zarinpal, "2026-10-01")                     # fee 2000, settled
    z2 = _order(conn, product_id, zarinpal, "2026-10-02", price=200000, status="PAID")  # fee 3500, pending
    z3 = _order(conn, product_id, zarinpal, "2026-10-03", postage_cost=5000)  # fee 2000, refunded
    z4 = _order(conn, product_id, zarinpal, "2026-10-03", status="PAID")      # fee 2000, cancelled
    _order(conn, product_id, zarinpal, "2026-10-04", status="PENDING")       # fee 2000, eligible, not paid
    _order(conn, product_id, zarinpal, "2026-10-04", status="DRAFT")         # not eligible
    process_return(conn, z3, "REFUNDED")
    process_return(conn, z4, "CANCELLED")
    record_settlement(conn, zarinpal, "2026-10-03", 97000, order_ids=[z1])   # expected 98000

    # Digipay: fee = 3%; Shahrivar settled as a whole month.
    _order(conn, product_id, digipay, "2026-09-10")                          # fee 3000
    _order(conn, product_id, digipay, "2026-09-20", price=50000)             # fee 1500
    _order(conn, product_id, digipay, "2026-10-01")                          # fee 3000, pending
    record_settlement(conn, digipay, "2026-09-29", 145000, jalali_year=1405, jalali_month=6)

    # Card to card: no fee, pending.
    _order(conn, product_id, card, "2026-10-05", shipping_charge=20000)

    # A method that is now inactive but has an order.
    _order(conn, product_id, used_old, "2026-10-02")                         # fee 250, pending
    deactivate_payment_method(conn, used_old)
    deactivate_payment_method(conn, unused_old)

    # No method: manual fees.
    _order(conn, product_id, None, "2026-10-01", transaction_fee=700)
    refunded_no_method = _order(conn, product_id, None, "2026-10-02", transaction_fee=300)
    process_return(conn, refunded_no_method, "REFUNDED")

    return {"card": card, "zarinpal": zarinpal, "digipay": digipay, "used_old": used_old}


def _figures(row):
    return {
        k: row[k]
        for k in (
            "order_count", "customer_total", "transaction_fees", "fees_lost_on_returns",
            "pending_expected", "settled_expected", "settled_received", "settlement_difference",
        )
    }


def test_report_rows_and_figures(test_db, report_data):
    rows = get_payment_method_report(test_db)
    assert [(r["name"], r["is_active"]) for r in rows] == [
        ("Card to card", 1),
        ("Digipay", 1),
        ("Used old", 0),
        ("Zarinpal", 1),
        (None, None),
    ]
    by_name = {r["name"]: r for r in rows}

    assert by_name["Card to card"]["payment_method_id"] == report_data["card"]
    assert by_name["Card to card"]["settlement_rule"] == "IMMEDIATE"
    assert _figures(by_name["Card to card"]) == {
        "order_count": 1, "customer_total": 120000, "transaction_fees": 0,
        "fees_lost_on_returns": 0, "pending_expected": 120000,
        "settled_expected": 0, "settled_received": 0, "settlement_difference": 0,
    }
    assert _figures(by_name["Digipay"]) == {
        "order_count": 3, "customer_total": 250000, "transaction_fees": 7500,
        "fees_lost_on_returns": 0, "pending_expected": 97000,
        "settled_expected": 145500, "settled_received": 145000, "settlement_difference": -500,
    }
    assert _figures(by_name["Used old"]) == {
        "order_count": 1, "customer_total": 100000, "transaction_fees": 250,
        "fees_lost_on_returns": 0, "pending_expected": 99750,
        "settled_expected": 0, "settled_received": 0, "settlement_difference": 0,
    }
    # z1 (settled), z2 (pending), z5 (PENDING status: eligible, not pending settlement).
    assert _figures(by_name["Zarinpal"]) == {
        "order_count": 3, "customer_total": 400000, "transaction_fees": 7500,
        "fees_lost_on_returns": 4000, "pending_expected": 196500,
        "settled_expected": 98000, "settled_received": 97000, "settlement_difference": -1000,
    }
    assert by_name[None]["payment_method_id"] is None
    assert by_name[None]["settlement_rule"] is None
    assert _figures(by_name[None]) == {
        "order_count": 1, "customer_total": 100000, "transaction_fees": 700,
        "fees_lost_on_returns": 300, "pending_expected": 0,
        "settled_expected": 0, "settled_received": 0, "settlement_difference": 0,
    }


def test_report_date_range_filters_orders_by_order_date_and_settlements_by_settled_date(
    test_db, report_data
):
    by_name = {r["name"]: r for r in get_payment_method_report(test_db, "2026-10-01", "2026-10-31")}
    # Shahrivar orders and the 2026-09-29 settlement fall outside October.
    assert _figures(by_name["Digipay"]) == {
        "order_count": 1, "customer_total": 100000, "transaction_fees": 3000,
        "fees_lost_on_returns": 0, "pending_expected": 97000,
        "settled_expected": 0, "settled_received": 0, "settlement_difference": 0,
    }
    september = {r["name"]: r for r in get_payment_method_report(test_db, "2026-09-01", "2026-09-30")}
    assert september["Digipay"]["settled_received"] == 145000
    assert september["Digipay"]["pending_expected"] == 0
    assert september["Zarinpal"]["order_count"] == 0


def test_report_hides_inactive_method_without_figures(test_db, report_data):
    names = [r["name"] for r in get_payment_method_report(test_db, "2026-11-01", None)]
    # Active methods always show; "Used old" has nothing after November 1.
    assert names == ["Card to card", "Digipay", "Zarinpal", None]


def test_report_with_no_data_has_only_the_no_method_row(test_db):
    (row,) = get_payment_method_report(test_db)
    assert row["payment_method_id"] is None
    assert set(_figures(row).values()) == {0}


@pytest.mark.parametrize("start_date, end_date", RANGES)
def test_transaction_fees_reconcile_with_profit_and_loss(test_db, report_data, start_date, end_date):
    rows = get_payment_method_report(test_db, start_date, end_date)
    pnl = get_profit_and_loss(test_db, start_date, end_date)
    assert sum(r["transaction_fees"] for r in rows) == pnl["transaction_fees"]
    assert sum(r["order_count"] for r in rows) == pnl["order_count"]


def test_reconciliation_data_includes_refunded_and_paid_then_cancelled_orders(test_db, report_data):
    statuses = {r[0] for r in test_db.execute("SELECT status FROM orders")}
    assert {"REFUNDED", "CANCELLED"} <= statuses
    assert get_profit_and_loss(test_db)["transaction_fees"] == 15950


@pytest.mark.parametrize("start_date, end_date", RANGES)
def test_fees_lost_on_returns_reconcile_with_refund_losses(test_db, report_data, start_date, end_date):
    rows = get_payment_method_report(test_db, start_date, end_date)
    pnl = get_profit_and_loss(test_db, start_date, end_date)
    # refund_losses = REFUNDED (packaging + postage + fee) + committed CANCELLED fee;
    # take away the non-fee part of the REFUNDED orders in the same range.
    start_utc, end_utc = to_utc_range(start_date, end_date, test_db)
    non_fee = test_db.execute(
        """
        SELECT COALESCE(SUM(packaging_cost + postage_cost), 0) FROM orders
        WHERE status = 'REFUNDED'
          AND (? IS NULL OR order_date >= ?) AND (? IS NULL OR order_date < ?)
        """,
        (start_utc, start_utc, end_utc, end_utc),
    ).fetchone()[0]
    assert sum(r["fees_lost_on_returns"] for r in rows) == pnl["refund_losses"] - non_fee


def test_fees_lost_on_returns_whole_range_values(test_db, report_data):
    pnl = get_profit_and_loss(test_db)
    # Refunded z3: postage 5000 + fee 2000; cancelled z4: fee 2000; refunded no-method: fee 300.
    assert pnl["refund_losses"] == 9300
    assert sum(r["fees_lost_on_returns"] for r in get_payment_method_report(test_db)) == 4300


@pytest.mark.parametrize("start_date, end_date", RANGES)
def test_customer_total_reconciles_with_revenue(test_db, report_data, start_date, end_date):
    """customer_total = sum(items_net) + shipping_charge over revenue-eligible
    orders by order_date: the same definition as the P&L total_revenue and the
    revenue summary's total_revenue, so the sums match exactly."""
    rows = get_payment_method_report(test_db, start_date, end_date)
    total = sum(r["customer_total"] for r in rows)
    assert total == get_profit_and_loss(test_db, start_date, end_date)["total_revenue"]
    assert total == get_revenue_summary(test_db, start_date, end_date)["total_revenue"]


def test_capped_fees_reconcile_with_the_profit_and_loss(test_db, fixed_today):
    from db.payment_methods import update_payment_method

    product_id = stocked_product(test_db, stock=100)
    capped = add_payment_method(
        test_db, "Zarinpal capped", "DAYS_AFTER", 1, fee_bps=50, fee_cap=160_000, fee_fixed=5_000
    )
    plain = add_payment_method(test_db, "Percent", "IMMEDIATE", fee_bps=150)
    for price in (94_900_000, 18_300_000, 31_999_900, 32_000_300):
        _order(test_db, product_id, capped, "2026-10-02", price=price, status="COMPLETED")
    update_payment_method(test_db, capped, fee_cap=None)
    _order(test_db, product_id, capped, "2026-10-02", price=94_900_000, status="COMPLETED")
    _order(test_db, product_id, plain, "2026-10-02", price=94_900_000, status="COMPLETED")

    rows = {r["payment_method_id"]: r for r in get_payment_method_report(test_db)}
    # 165,000 + 96,500 + 165,000 + 165,000, then uncapped 479,500.
    assert rows[capped]["transaction_fees"] == 165_000 + 96_500 + 165_000 + 165_000 + 479_500
    assert rows[plain]["transaction_fees"] == 1_423_500
    assert sum(r["transaction_fees"] for r in rows.values()) == get_profit_and_loss(test_db)["transaction_fees"]
