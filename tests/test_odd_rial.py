"""Odd Rial amounts (not whole Toman) round-trip exactly through the money paths.

Money is integer Rial since migration 009; every formula is the same integer
arithmetic as before, with rounding (Python round(), half-even) now to the Rial.
"""

from datetime import date

import pytest

import db.orders
import db.settlements
from db.costing import blend_unit_cost
from db.orders import get_order, record_order
from db.payment_methods import add_payment_method, compute_fee, preview_fee
from db.products import get_product
from db.purchases import get_product_purchase, record_product_purchase
from db.reports import get_profit_and_loss
from db.settlements import get_settlement, record_settlement
from tests.helpers import stocked_product

TODAY = date(2026, 10, 6)


@pytest.fixture
def fixed_today(monkeypatch):
    for module in (db.orders, db.settlements):
        monkeypatch.setattr(module, "today_local", lambda conn=None: TODAY)


def test_order_with_odd_rial_amounts(test_db):
    product_id = stocked_product(test_db, unit_cost=5003)
    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 3, "unit_price": 12_345, "discount_amount": 7}],
        shipping_charge=1_800_005,
        postage_cost=3_333,
        transaction_fee=4_567,
        packaging_kit_id=None,
    )
    detail = get_order(test_db, order_id)
    order, item = detail["order"], detail["items"][0]
    assert item["list_price"] == 37_035  # 3 x 12,345
    assert item["discount_amount"] == 7
    assert item["unit_price"] == 12_342  # (37,035 - 7) // 3, floored to the Rial
    assert item["unit_cost_at_time"] == 5_003
    assert (order["shipping_charge"], order["postage_cost"], order["transaction_fee"]) == (1_800_005, 3_333, 4_567)
    # customer_total = 37,035 - 7 + 1,800,005
    assert detail["customer_total"] == 1_837_033
    # profit = 1,837,033 - 3 x 5,003 - 0 - 3,333 - 4,567
    assert detail["profit"] == 1_814_124

    pnl = get_profit_and_loss(test_db)
    assert pnl["total_revenue"] == 1_837_033
    assert pnl["gross_profit"] == 1_814_124


def test_purchase_unit_cost_and_weighted_average_round_half_even_to_the_rial(test_db):
    product_id = stocked_product(test_db, stock=0, unit_cost=500)
    test_db.execute("UPDATE products SET unit_cost = NULL WHERE id = ?", (product_id,))
    test_db.commit()

    # 100,005 / 2 = 50,002.5 -> 50,002 (the even neighbour).
    first = record_product_purchase(test_db, product_id, 2, 100_005)
    assert get_product_purchase(test_db, first)["unit_cost"] == 50_002
    assert get_product(test_db, product_id)["unit_cost"] == 50_002

    # (2 x 50,002 + 100,006) / 4 = 50,002.5 -> 50,002 (even), an exact tie.
    second = record_product_purchase(test_db, product_id, 2, 100_006)
    assert get_product_purchase(test_db, second)["unit_cost"] == 50_003
    assert get_product(test_db, product_id)["unit_cost"] == 50_002
    assert get_product(test_db, product_id)["current_stock"] == 4

    # Not a tie: (4 x 50,002 + 50,011) / 5 = 50,003.8 -> 50,004 (the nearest Rial).
    record_product_purchase(test_db, product_id, 1, 50_011)
    assert get_product(test_db, product_id)["unit_cost"] == 50_004


def test_weighted_average_in_rial_is_finer_than_old_toman_times_ten():
    # The same stock in Toman: 3 @ 1,001 + 1 @ 1,000 -> 1,000.75 -> 1,001 Toman = 10,010 Rial.
    assert blend_unit_cost(3, 1_001, 1, 1_000) * 10 == 10_010
    # In Rial: 3 @ 10,010 + 1 @ 10,000 -> 10,007.5 -> 10,008 (half-even), 2 Rial finer.
    assert blend_unit_cost(3, 10_010, 1, 10_000) == 10_008


def test_payment_method_fee_on_an_odd_rial_total(test_db, fixed_today):
    method_id = add_payment_method(test_db, "Gateway", "IMMEDIATE", fee_bps=150, fee_fixed=5_005)
    method = {"fee_bps": 150, "fee_fixed": 5_005, "fee_cap": None}
    # 1,234,567 x 150 / 10,000 = 18,518.505 -> 18,519 (above half), + 5,005
    assert compute_fee(1_234_567, method) == 23_524
    assert preview_fee(test_db, method_id, 1_234_567)["expected_amount"] == 1_211_043
    # Exact halves go to the even neighbour, to the Rial: 7 x 5,000 / 10,000 = 3.5 -> 4; 5 -> 2.5 -> 2.
    assert compute_fee(7, {"fee_bps": 5_000, "fee_fixed": 0, "fee_cap": None}) == 4
    assert compute_fee(5, {"fee_bps": 5_000, "fee_fixed": 0, "fee_cap": None}) == 2

    product_id = stocked_product(test_db, unit_cost=1)
    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": product_id, "quantity": 1, "unit_price": 1_234_567}],
        shipping_charge=0,
        packaging_kit_id=None,
        postage_cost=0,
        payment_method_id=method_id,
    )
    assert get_order(test_db, order_id)["order"]["transaction_fee"] == 23_524


def test_settlement_of_odd_rial_orders(test_db, fixed_today):
    method_id = add_payment_method(test_db, "Gateway", "IMMEDIATE", fee_bps=150, fee_fixed=5_005)
    product_id = stocked_product(test_db, unit_cost=1)

    def sale(price):
        return record_order(
            test_db,
            "IN_PERSON",
            [{"product_id": product_id, "quantity": 1, "unit_price": price}],
            order_date="2026-10-01",
            shipping_charge=0,
            packaging_kit_id=None,
            postage_cost=0,
            payment_method_id=method_id,
        )

    a = sale(1_234_567)  # fee 23,524 -> expected 1,211,043
    b = sale(7)  # fee 0 + 5,005 -> expected -4,998
    settlement_id = record_settlement(test_db, method_id, "2026-10-02", 1_206_040, order_ids=[a, b])
    settlement = get_settlement(test_db, settlement_id)
    assert settlement["expected_amount"] == 1_211_043 - 4_998 == 1_206_045
    assert settlement["amount_received"] == 1_206_040
    assert settlement["difference"] == -5
