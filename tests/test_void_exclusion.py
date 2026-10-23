"""A voided order is in no figure (accounting-rules section 20): two databases hold the same sales, one of them
also a sale that was voided, and every report, aggregate and dashboard endpoint answers the same for both."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

import db.orders
import db.settlements
from api.main import app
from db.adjustments import record_stock_adjustment
from db.connection import get_connection, init_db
from db.distributions import get_undistributed_profit, record_profit_distribution
from db.expenses import add_expense, add_expense_category
from db.materials import add_material, get_low_stock_materials
from db.order_voids import void_order
from db.orders import get_revenue_summary, list_orders, record_order
from db.packaging import add_kit_item, create_kit
from db.partners import add_partner
from db.payment_methods import add_payment_method
from db.postage import record_postage_batch
from db.products import add_product
from db.recipes import add_recipe_item
from db.reports import (
    get_channel_breakdown, get_expense_breakdown, get_payment_method_report, get_product_performance,
    get_profit_and_loss, get_purchases_summary, get_shipping_by_channel, get_shipping_summary, get_waste_report,
)
from db.returns import process_return
from db.settlements import get_pending, list_settlements, record_settlement
from tests.helpers import cat

TODAY = date(2026, 10, 23)
RANGE = ("2026-09-01", "2026-10-31")
IGNORED = {"created_at", "updated_at"}


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    for module in (db.orders, db.settlements):
        monkeypatch.setattr(module, "today_local", lambda conn=None: TODAY)


def _build(conn, with_voided: bool) -> None:
    card = add_payment_method(conn, "Card", "IMMEDIATE", fee_bps=100, fee_fixed=500)
    monthly = add_payment_method(conn, "Monthly", "DAY_OF_NEXT_MONTH", settlement_days=7, fee_bps=300)
    vinyl = add_product(conn, "Vinyl", cat(conn, "VINYL"), 30_000, 20_000)
    record_stock_adjustment(conn, "PRODUCT", vinyl, 20, "ADJUSTMENT", unit_cost=9_000)
    paper = add_material(conn, "Paper", "STOCK", 1_250, initial_stock=100, min_stock=99)
    box = add_material(conn, "Box", "STOCK", 3_000, initial_stock=20)
    poster = add_product(conn, "Poster", cat(conn, "POSTER"), 50_000, 40_000, made_to_order=True)
    add_recipe_item(conn, poster, paper, 2)
    kit = create_kit(conn, "Parcel")
    add_kit_item(conn, kit, box, 1)

    def sell(channel, product, quantity, **kwargs):
        return record_order(conn, channel, [{"product_id": product, "quantity": quantity, "unit_price": 30_000}],
                            **kwargs)

    settled = sell("WEBSITE", vinyl, 1, order_date="2026-10-02", payment_method_id=card, packaging_kit_id=kit)
    sell("INSTAGRAM", poster, 2, order_date="2026-10-05", payment_method_id=card, packaging_kit_id=kit)
    sell("WHOLESALE", vinyl, 3, order_date="2026-10-06", payment_method_id=monthly, status="PAID")
    sell("IN_PERSON", vinyl, 1, order_date="2026-10-07", packaging_kit_id=None, status="PENDING")
    refunded = sell("WEBSITE", poster, 1, order_date="2026-10-08", payment_method_id=card, packaging_kit_id=kit)
    cancelled = sell("INSTAGRAM", vinyl, 1, order_date="2026-10-09", payment_method_id=card, status="PAID")
    sell("OTHER", vinyl, 1, order_date="2026-10-10", status="DRAFT", packaging_kit_id=None)
    process_return(conn, refunded, "REFUNDED")
    process_return(conn, cancelled, "CANCELLED")
    record_settlement(conn, card, "2026-10-12", 29_000, order_ids=[settled])
    record_stock_adjustment(conn, "MATERIAL", paper, -1, "WASTE")
    add_expense(conn, add_expense_category(conn, "Rent"), 50_000, expense_date="2026-10-03")
    record_postage_batch(conn, 40_000, 2, paid_date="2026-10-11")
    add_partner(conn, "Solo", 100.0)
    # An explicit day: the two databases are built a moment apart, and "now" would differ between them.
    record_profit_distribution(conn, "2026-09-01", "2026-09-30", 0, distribution_date="2026-10-01", allow_exceeding=True)

    if with_voided:  # recorded last, so every other row keeps the same id in both databases
        voided = sell("WEBSITE", poster, 3, order_date="2026-10-13", payment_method_id=card, packaging_kit_id=kit,
                      status="PAID", shipping_charge=17_000)
        void_order(conn, voided, "entered by mistake")


@pytest.fixture
def pair(tmp_path):
    paths = []
    for with_voided in (False, True):
        path = str(tmp_path / f"shop-{'with' if with_voided else 'without'}-void.db")
        init_db(path)
        conn = get_connection(path)
        try:
            _build(conn, with_voided)
        finally:
            conn.close()
        paths.append(path)
    return paths


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in IGNORED}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def _db_figures(path) -> dict:
    conn = get_connection(path)
    try:
        start, end = RANGE
        return _strip({
            "pnl": get_profit_and_loss(conn, start, end),
            "pnl_all_time": get_profit_and_loss(conn),
            "channels": get_channel_breakdown(conn, start, end),
            "products": get_product_performance(conn, start, end),
            "shipping": get_shipping_summary(conn, start, end),
            "shipping_by_channel": get_shipping_by_channel(conn, start, end),
            "payment_methods": get_payment_method_report(conn, start, end),
            "waste": get_waste_report(conn, start, end),
            "expenses": get_expense_breakdown(conn, start, end),
            "purchases": get_purchases_summary(conn, start, end),
            "revenue_summary": get_revenue_summary(conn, start, end),
            "pending": get_pending(conn),
            "settlements": list_settlements(conn),
            "undistributed": get_undistributed_profit(conn, end),
            "low_stock": get_low_stock_materials(conn),
            "orders": list_orders(conn),
            "orders_in_range": list_orders(conn, start_date=start, end_date=end),
            "stock": [dict(r) for r in conn.execute(
                "SELECT 'product', id, current_stock, unit_cost FROM products UNION ALL "
                "SELECT 'material', id, current_stock, unit_cost FROM materials ORDER BY 1, 2")],
        })
    finally:
        conn.close()


DASHBOARD_AND_REPORT_ENDPOINTS = [
    "/reports/profit-and-loss", "/reports/products", "/reports/channels", "/reports/shipping",
    "/reports/shipping-by-channel", "/reports/waste", "/reports/expenses", "/reports/revenue-summary",
    "/reports/purchases", "/reports/payment-methods",
]
PLAIN_ENDPOINTS = [
    "/orders", "/settlements/pending", "/settlements", "/postage/estimate", "/materials/low-stock",
    "/partners/totals", "/distributions", f"/distributions/undistributed?as_of={RANGE[1]}",
]


def _api_figures(path, monkeypatch) -> dict:
    monkeypatch.setenv("REBEL_DB", path)
    client = TestClient(app)  # no startup: the database is already migrated
    answers = {}
    for endpoint in DASHBOARD_AND_REPORT_ENDPOINTS:
        response = client.get(endpoint, params={"start_date": RANGE[0], "end_date": RANGE[1]})
        assert response.status_code == 200, (endpoint, response.text)
        answers[endpoint] = response.json()
    for endpoint in PLAIN_ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, (endpoint, response.text)
        answers[endpoint] = response.json()
    return _strip(answers)


def test_every_figure_equals_the_same_data_without_the_voided_order(pair):
    without, with_void = (_db_figures(path) for path in pair)
    # the scenario is not empty: eligible, returned, pending and settled orders all show up
    assert without["pnl"]["order_count"] == 4 and without["pnl"]["refund_losses"] > 0
    assert without["pending"] and without["settlements"] and len(without["orders"]) == 7
    for key in without:
        assert with_void[key] == without[key], key
    # the voided sale did happen in the second database, and was really voided there
    conn = get_connection(pair[1])
    try:
        assert [o["status"] for o in list_orders(conn, status="VOIDED")] == ["VOIDED"]
    finally:
        conn.close()


def test_every_dashboard_and_report_endpoint_answers_the_same(pair, monkeypatch):
    without = _api_figures(pair[0], monkeypatch)
    with_void = _api_figures(pair[1], monkeypatch)
    for endpoint in without:
        assert with_void[endpoint] == without[endpoint], endpoint
