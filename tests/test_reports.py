import pytest

from db import packaging, postage
from db.adjustments import record_stock_adjustment
from db.expenses import add_expense, add_expense_category
from db.materials import add_material
from db.orders import record_order
from db.products import add_product, deactivate_product, get_product
from db.purchases import record_material_purchase, record_product_purchase
from db.reports import (
    get_channel_breakdown,
    get_expense_breakdown,
    get_low_stock_products,
    get_product_performance,
    get_profit_and_loss,
    get_purchases_summary,
    get_shipping_by_channel,
    get_shipping_summary,
    get_waste_report,
)
from db.returns import process_return
from db.settings import update_channel_settings
from db.timeutil import to_utc_range
from tests.helpers import cat


@pytest.fixture
def report_setup(test_db):
    product_a_id = add_product(test_db, "Report Vinyl", cat(test_db, "VINYL"), 3000, 2000)
    product_b_id = add_product(test_db, "Report Cassette", cat(test_db, "CASSETTE"), 1500, 1000)
    test_db.execute(
        "UPDATE products SET current_stock = 100, unit_cost = 500 WHERE id = ?",
        (product_a_id,),
    )
    test_db.execute(
        "UPDATE products SET current_stock = 100, unit_cost = 300 WHERE id = ?",
        (product_b_id,),
    )
    test_db.commit()

    low_stock_id = add_product(test_db, "Low Stock Item", cat(test_db, "OTHER"), 500, 400)
    test_db.execute(
        "UPDATE products SET current_stock = 2, unit_cost = 100 WHERE id = ?",
        (low_stock_id,),
    )
    inactive_id = add_product(test_db, "Inactive Low", cat(test_db, "OTHER"), 500, 400)
    test_db.execute(
        "UPDATE products SET current_stock = 1, unit_cost = 100 WHERE id = ?",
        (inactive_id,),
    )
    deactivate_product(test_db, inactive_id)

    material_id = add_material(test_db, "Waste Material", "STOCK", 200, initial_stock=50)

    ads_id = add_expense_category(test_db, "Ads")
    tools_id = add_expense_category(test_db, "Tools")
    add_expense(test_db, ads_id, 500, expense_date="2026-03-01")
    add_expense(test_db, tools_id, 200, expense_date="2026-03-15")

    order_instagram = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_a_id, "quantity": 2, "unit_price": 3000}],
        shipping_charge=100,
        postage_cost=50,
        transaction_fee=20,
    )
    test_db.execute(
        "UPDATE orders SET order_date = ? WHERE id = ?",
        ("2026-03-10 08:00:00", order_instagram),
    )
    test_db.commit()

    order_website = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": product_b_id, "quantity": 1, "unit_price": 1500}],
    )
    test_db.execute(
        "UPDATE orders SET order_date = ? WHERE id = ?",
        ("2026-03-12 08:00:00", order_website),
    )
    test_db.commit()

    cancelled_id = test_db.execute(
        """
        INSERT INTO orders (status, channel, order_date)
        VALUES ('CANCELLED', 'OTHER', '2026-03-11 08:00:00')
        """
    ).lastrowid
    test_db.execute(
        """
        INSERT INTO order_items
            (order_id, product_id, quantity, list_price, unit_price, unit_cost_at_time)
        VALUES (?, ?, 5, 15000, 3000, 500)
        """,
        (cancelled_id, product_a_id),
    )

    # unit_cost_at_time is frozen at the moment of waste (section 8) — set it
    # explicitly here to the item's cost at that time (200 for the material,
    # 500 for the product), since get_waste_report now values waste using
    # this frozen figure, never the item's current cost.
    test_db.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, movement_date, unit_cost_at_time)
        VALUES ('MATERIAL', ?, -3, 'WASTE', '2026-03-05 08:00:00', 200)
        """,
        (material_id,),
    )
    test_db.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, movement_date, unit_cost_at_time)
        VALUES ('MATERIAL', ?, -2, 'WASTE', '2026-03-20 08:00:00', 200)
        """,
        (material_id,),
    )
    test_db.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, movement_date, unit_cost_at_time)
        VALUES ('PRODUCT', ?, -1, 'WASTE', '2026-03-08 08:00:00', 500)
        """,
        (product_a_id,),
    )
    test_db.commit()

    return {
        "product_a_id": product_a_id,
        "product_b_id": product_b_id,
        "low_stock_id": low_stock_id,
        "inactive_id": inactive_id,
        "material_id": material_id,
        "ads_id": ads_id,
        "tools_id": tools_id,
        "order_instagram": order_instagram,
        "order_website": order_website,
    }


def test_get_product_performance(report_setup, test_db):
    rows = get_product_performance(test_db)
    assert len(rows) == 2

    by_name = {row["product_name"]: row for row in rows}
    vinyl = by_name["Report Vinyl"]
    assert vinyl["units_sold"] == 2
    assert vinyl["total_revenue"] == 6000
    assert vinyl["total_cost"] == 1000
    assert vinyl["total_profit"] == 5000

    cassette = by_name["Report Cassette"]
    assert cassette["units_sold"] == 1
    assert cassette["total_revenue"] == 1500
    assert cassette["total_cost"] == 300
    assert cassette["total_profit"] == 1200

    assert rows[0]["product_name"] == "Report Vinyl"


def test_get_product_performance_excludes_cancelled_and_date_filter(report_setup, test_db):
    assert get_product_performance(test_db, start_date="2099-01-01") == []

    in_range = get_product_performance(
        test_db, start_date="2026-03-10", end_date="2026-03-12"
    )
    assert len(in_range) == 2
    assert sum(row["units_sold"] for row in in_range) == 3


def test_get_channel_breakdown(report_setup, test_db):
    # INSTAGRAM order: shipping/postage/fee were passed explicitly (100/50/20),
    # so those overrides are used regardless of channel defaults.
    # revenue = items_net(6000) + shipping(100) = 6100
    # profit = 6100 - cogs(1000) - packaging(0) - postage(50) - fee(20) = 5030
    #
    # WEBSITE order: no overrides given, so it picks up WEBSITE's channel
    # defaults — shipping_charge = default_shipping_charge (1,800,000 Rial: the
    # 180,000 seed x 10 by migration 009), postage estimate = 0 (no postage
    # batches recorded in this fixture).
    # revenue = items_net(1500) + shipping(1,800,000) = 1,801,500
    # profit = 1,801,500 - cogs(300) - packaging(0) - postage(0) - fee(0) = 1,801,200
    rows = get_channel_breakdown(test_db)
    assert len(rows) == 2

    by_channel = {row["channel"]: row for row in rows}
    assert by_channel["INSTAGRAM"]["order_count"] == 1
    assert by_channel["INSTAGRAM"]["total_revenue"] == 6100
    assert by_channel["INSTAGRAM"]["total_profit"] == 5030
    assert by_channel["INSTAGRAM"]["avg_order_value"] == 6100

    assert by_channel["WEBSITE"]["order_count"] == 1
    assert by_channel["WEBSITE"]["total_revenue"] == 1_801_500
    assert by_channel["WEBSITE"]["total_profit"] == 1_801_200
    assert by_channel["WEBSITE"]["avg_order_value"] == 1_801_500

    # Sorted by total_revenue desc — WEBSITE's default shipping charge now
    # puts it ahead of INSTAGRAM.
    assert rows[0]["channel"] == "WEBSITE"


def test_get_channel_breakdown_excludes_cancelled_and_empty_range(report_setup, test_db):
    assert "OTHER" not in {row["channel"] for row in get_channel_breakdown(test_db)}
    assert get_channel_breakdown(test_db, start_date="2099-01-01") == []


def _channel_order(conn, product_id, channel, price):
    return record_order(
        conn,
        channel,
        [{"product_id": product_id, "quantity": 1, "unit_price": price}],
        shipping_charge=0,
        postage_cost=0,
        transaction_fee=0,
        packaging_kit_id=None,
        order_date="2026-03-10",
    )


@pytest.mark.parametrize(
    "prices, expected",
    [
        ((1000, 2000, 4000), 2333),  # 7000 / 3 = 2333.33 -> 2333
        ((1000, 1001), 1000),  # 2001 / 2 = 1000.5 -> 1000 (tie, to even)
        ((1000, 1003), 1002),  # 2003 / 2 = 1001.5 -> 1002 (tie, to even)
        ((1000, 2001), 1500),  # 3001 / 2 = 1500.5 -> 1500 (tie, to even)
    ],
)
def test_channel_avg_order_value_rounds_half_even(test_db, prices, expected):
    product_id = add_product(test_db, "AOV Tee", cat(test_db, "OTHER"), 1000, 500)
    test_db.execute(
        "UPDATE products SET current_stock = 100, unit_cost = 100 WHERE id = ?", (product_id,)
    )
    test_db.commit()
    for price in prices:
        _channel_order(test_db, product_id, "INSTAGRAM", price)

    (row,) = get_channel_breakdown(test_db)
    assert row["total_revenue"] == sum(prices)
    assert row["order_count"] == len(prices)
    assert row["avg_order_value"] == expected
    assert type(row["avg_order_value"]) is int


def test_get_low_stock_products(report_setup, test_db):
    rows = get_low_stock_products(test_db, threshold=5)
    names = {row["name"] for row in rows}
    assert "Low Stock Item" in names
    assert "Report Vinyl" not in names
    assert "Inactive Low" not in names


def test_get_waste_report(report_setup, test_db):
    rows = get_waste_report(test_db)
    assert len(rows) == 2

    by_key = {(row["item_type"], row["item_name"]): row for row in rows}
    material = by_key[("MATERIAL", "Waste Material")]
    assert material["item_id"] == report_setup["material_id"]
    assert material["unit"] == "piece"
    assert material["total_wasted"] == 5
    assert material["waste_event_count"] == 2
    assert material["cost"] == 1000
    assert material["unknown_cost_count"] == 0

    product = by_key[("PRODUCT", "Report Vinyl")]
    assert product["item_id"] == report_setup["product_a_id"]
    assert product["unit"] == "piece"
    assert product["total_wasted"] == 1
    assert product["waste_event_count"] == 1
    assert product["cost"] == 500
    assert product["unknown_cost_count"] == 0

    assert rows[0]["item_name"] == "Waste Material"


def test_get_waste_report_unknown_cost_excluded_from_total(report_setup, test_db):
    material_id = report_setup["material_id"]

    # A WASTE movement with no frozen unit_cost_at_time (unknown).
    test_db.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, movement_date, unit_cost_at_time)
        VALUES ('MATERIAL', ?, -1, 'WASTE', '2026-03-06 08:00:00', NULL)
        """,
        (material_id,),
    )
    test_db.commit()

    rows = get_waste_report(test_db)
    by_key = {(row["item_type"], row["item_name"]): row for row in rows}
    material = by_key[("MATERIAL", "Waste Material")]

    # total_wasted/waste_event_count include the unknown-cost row; cost does
    # not (it stays 1000 — the sum of only the two known-cost events).
    assert material["total_wasted"] == 6
    assert material["waste_event_count"] == 3
    assert material["cost"] == 1000
    assert material["unknown_cost_count"] == 1


def test_get_waste_report_all_unknown_cost_reports_none(test_db):
    material_id = add_material(test_db, "Mystery Material", "STOCK", 200, initial_stock=10)
    test_db.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, unit_cost_at_time)
        VALUES ('MATERIAL', ?, -1, 'WASTE', NULL)
        """,
        (material_id,),
    )
    test_db.commit()

    rows = get_waste_report(test_db)
    assert len(rows) == 1
    assert rows[0]["cost"] is None
    assert rows[0]["unknown_cost_count"] == 1


def test_get_waste_report_date_filter_and_empty(report_setup, test_db):
    early = get_waste_report(test_db, start_date="2026-03-01", end_date="2026-03-07")
    assert len(early) == 1
    assert early[0]["item_type"] == "MATERIAL"
    assert early[0]["total_wasted"] == 3

    assert get_waste_report(test_db, start_date="2099-01-01") == []


def test_get_expense_breakdown(report_setup, test_db):
    rows = get_expense_breakdown(test_db)
    assert len(rows) == 2

    by_name = {row["category_name"]: row for row in rows}
    assert by_name["Ads"]["category_id"] == report_setup["ads_id"]
    assert by_name["Tools"]["category_id"] == report_setup["tools_id"]
    assert by_name["Ads"]["total_amount"] == 500
    assert by_name["Ads"]["expense_count"] == 1
    assert by_name["Tools"]["total_amount"] == 200
    assert by_name["Tools"]["expense_count"] == 1
    assert rows[0]["category_name"] == "Ads"


def test_get_expense_breakdown_date_filter_and_empty(report_setup, test_db):
    march = get_expense_breakdown(
        test_db, start_date="2026-03-01", end_date="2026-03-10"
    )
    assert len(march) == 1
    assert march[0]["category_name"] == "Ads"
    assert march[0]["category_id"] == report_setup["ads_id"]

    assert get_expense_breakdown(test_db, start_date="2099-01-01") == []


def test_get_profit_and_loss_hand_calculated(report_setup, test_db):
    # Order A (INSTAGRAM): items_revenue 6000, shipping 100, cogs 1000,
    #   packaging 0, postage_estimated 50, fee 20.
    # Order B (WEBSITE, no overrides): items_revenue 1500, shipping 1,800,000
    #   (channel default: the 180,000 seed x 10 by migration 009), cogs 300,
    #   packaging 0, postage_estimated 0.
    # (Cancelled order excluded from all of the above — not eligible.)
    #
    # items_revenue = 6000 + 1500 = 7500
    # shipping_revenue = 100 + 1,800,000 = 1,800,100
    # total_revenue = 1,807,600
    # cogs = 1000 + 300 = 1300; packaging_cost = 0
    # postage_estimated = 50 + 0 = 50; transaction_fees = 20 + 0 = 20
    # gross_profit = 1,807,600 - 1300 - 0 - 50 - 20 = 1,806,230
    #
    # postage_actual = 0 (no postage batches in this fixture)
    # postage committed on shipped (eligible+REFUNDED) orders = 50 (order A) + 0
    # postage_variance = 0 - 50 = -50
    #
    # refund_losses = 0 (no REFUNDED orders; the CANCELLED order's fee is 0)
    # waste_cost = material 5*200 + product 1*500 = 1000 + 500 = 1500
    # operating_expenses = 500 + 200 = 700
    #
    # net_profit = 1,806,230 - (-50) - 0 - 1500 - 700 = 1,804,080
    pnl = get_profit_and_loss(test_db)

    assert pnl["order_count"] == 2
    assert pnl["items_revenue"] == 7500
    assert pnl["shipping_revenue"] == 1_800_100
    assert pnl["total_revenue"] == 1_807_600
    assert pnl["cogs"] == 1300
    assert pnl["packaging_cost"] == 0
    assert pnl["postage_estimated"] == 50
    assert pnl["transaction_fees"] == 20
    assert pnl["gross_profit"] == 1_806_230
    assert pnl["postage_actual"] == 0
    assert pnl["postage_committed"] == 50
    assert pnl["postage_variance"] == -50
    assert pnl["refund_losses"] == 0
    assert pnl["refund_fee_losses"] == 0
    assert pnl["waste_cost"] == 1500
    assert pnl["operating_expenses"] == 700
    assert pnl["net_profit"] == 1_804_080


def test_get_profit_and_loss_date_filter(report_setup, test_db):
    # Only order A falls in this one-day range; no waste/expenses/postage
    # batches fall in it either.
    # gross_profit = 6100 - 1000 - 0 - 50 - 20 = 5030
    # postage_variance = 0 - 50 = -50
    # net_profit = 5030 - (-50) - 0 - 0 - 0 = 5080
    instagram_only = get_profit_and_loss(
        test_db, start_date="2026-03-10", end_date="2026-03-10"
    )
    assert instagram_only["order_count"] == 1
    assert instagram_only["items_revenue"] == 6000
    assert instagram_only["shipping_revenue"] == 100
    assert instagram_only["total_revenue"] == 6100
    assert instagram_only["cogs"] == 1000
    assert instagram_only["gross_profit"] == 5030
    assert instagram_only["postage_committed"] == 50
    assert instagram_only["postage_variance"] == -50
    assert instagram_only["refund_losses"] == 0
    assert instagram_only["refund_fee_losses"] == 0
    assert instagram_only["waste_cost"] == 0
    assert instagram_only["operating_expenses"] == 0
    assert instagram_only["net_profit"] == 5080

    empty = get_profit_and_loss(test_db, start_date="2099-01-01")
    assert empty == {
        "items_revenue": 0,
        "shipping_revenue": 0,
        "total_revenue": 0,
        "cogs": 0,
        "packaging_cost": 0,
        "postage_estimated": 0,
        "transaction_fees": 0,
        "gross_profit": 0,
        "postage_actual": 0,
        "postage_committed": 0,
        "postage_variance": 0,
        "refund_losses": 0,
        "refund_fee_losses": 0,
        "waste_cost": 0,
        "operating_expenses": 0,
        "net_profit": 0,
        "order_count": 0,
    }


def test_get_shipping_summary_shipped_order_count(test_db):
    # IN_PERSON does not apply postage (never shipped); WEBSITE does. Both
    # orders are revenue-eligible, so order_count counts both, but only the
    # WEBSITE order actually shipped, so shipped_order_count is 1 and every
    # avg_* figure is based on that, not on order_count.
    product_id = add_product(test_db, "Shipping Test Item", cat(test_db, "OTHER"), 1000, 800)
    test_db.execute(
        "UPDATE products SET current_stock = 10, unit_cost = 100 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()

    record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
        status="COMPLETED",
    )
    record_order(
        test_db,
        "WEBSITE",
        [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
        status="COMPLETED",
    )

    shipping = get_shipping_summary(test_db)
    assert shipping["order_count"] == 2
    assert shipping["shipped_order_count"] == 1
    # shipping_revenue = WEBSITE's default shipping charge only (IN_PERSON
    # doesn't apply one); dividing by shipped_order_count (1), not
    # order_count (2), the average equals the total. The default is the
    # seeded 1,800,000 Rial (180,000 x 10, migration 009).
    assert shipping["shipping_revenue"] == 1_800_000
    assert shipping["avg_shipping_revenue"] == 1_800_000
    assert shipping["net_shipping_result"] == 1_800_000
    assert shipping["avg_net_shipping_result"] == 1_800_000


def test_get_shipping_summary_excludes_non_shipping_channel_costs(test_db):
    # One IN_PERSON order uses the packaging kit (and, by override, carries a
    # shipping charge and postage), plus two WEBSITE orders with the same kit.
    # IN_PERSON doesn't apply postage, so it never ships: none of its money
    # belongs in the shipping economics. Before the fix its packaging inflated
    # packaging_cost (180,000) and avg_packaging_cost (90,000).
    product_id = add_product(test_db, "Ship Scope Item", cat(test_db, "OTHER"), 1_000_000, 800_000)
    test_db.execute(
        "UPDATE products SET current_stock = 10, unit_cost = 400000 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()
    box_id = add_material(test_db, "Scope Box", "STOCK", 60_000, initial_stock=10)
    kit_id = packaging.create_kit(test_db, "Scope kit")
    packaging.add_kit_item(test_db, kit_id, box_id, 1)
    item = [{"product_id": product_id, "quantity": 1, "unit_price": 1_000_000}]

    record_order(
        test_db, "IN_PERSON", item,
        packaging_kit_id=kit_id, shipping_charge=50_000, postage_cost=30_000,
    )
    for _ in range(2):
        record_order(test_db, "WEBSITE", item, packaging_kit_id=kit_id, postage_cost=200_000)
    postage.record_postage_batch(test_db, total_paid=200_000, order_count=1)

    shipping = get_shipping_summary(test_db)
    assert shipping["order_count"] == 3
    assert shipping["shipped_order_count"] == 2
    # 2 × the seeded 1,800,000 Rial (180,000 x 10, migration 009); not the 50,000 in-person charge.
    assert shipping["shipping_revenue"] == 3_600_000
    assert shipping["packaging_cost"] == 120_000  # 2 × 60,000; not 180,000
    assert shipping["postage_estimated"] == 400_000  # not the 30,000 in-person override
    assert shipping["postage_actual"] == 200_000
    assert shipping["net_shipping_result"] == 3_600_000 - 120_000 - 200_000
    assert shipping["avg_shipping_revenue"] == 1_800_000
    assert shipping["avg_packaging_cost"] == 60_000
    assert shipping["avg_postage_actual"] == 100_000
    assert shipping["avg_net_shipping_result"] == 1_640_000  # (3,600,000 − 120,000 − 200,000) / 2

    # The summary is the per-channel report, totalled.
    by_channel = get_shipping_by_channel(test_db)
    assert [r["channel"] for r in by_channel] == ["WEBSITE"]
    for key in ("shipped_order_count", "shipping_revenue", "packaging_cost", "postage_estimated"):
        assert shipping[key] == sum(r[key] for r in by_channel)
    assert shipping["shipping_revenue"] - shipping["packaging_cost"] - shipping["postage_estimated"] == sum(
        r["net"] for r in by_channel
    )

    # The P&L still counts every eligible order's packaging and shipping.
    pnl = get_profit_and_loss(test_db)
    assert pnl["packaging_cost"] == 180_000
    assert pnl["shipping_revenue"] == 3_650_000  # 2 × 1,800,000 + the 50,000 in-person override
    assert pnl["order_count"] == 3


def test_get_shipping_summary_estimated_fields_exclude_non_shipping_channel(test_db):
    # The estimate-based figures are derived from the shipped-only sums too:
    # the IN_PERSON order's kit (60,000), shipping charge (50,000) and postage
    # override (30,000) must not reach net_shipping_result_estimated, its
    # average or postage_gap.
    product_id = add_product(test_db, "Ship Est Scope Item", cat(test_db, "OTHER"), 1_000_000, 800_000)
    test_db.execute(
        "UPDATE products SET current_stock = 10, unit_cost = 400000 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()
    box_id = add_material(test_db, "Est Scope Box", "STOCK", 60_000, initial_stock=10)
    kit_id = packaging.create_kit(test_db, "Est scope kit")
    packaging.add_kit_item(test_db, kit_id, box_id, 1)
    item = [{"product_id": product_id, "quantity": 1, "unit_price": 1_000_000}]

    record_order(
        test_db, "IN_PERSON", item,
        packaging_kit_id=kit_id, shipping_charge=50_000, postage_cost=30_000,
    )
    for _ in range(2):
        record_order(test_db, "WEBSITE", item, packaging_kit_id=kit_id, postage_cost=200_000)
    postage.record_postage_batch(test_db, total_paid=150_000, order_count=1)

    shipping = get_shipping_summary(test_db)
    # Shipped-only totals: 2 WEBSITE orders at the seeded 1,800,000 Rial (migration 009).
    assert shipping["shipping_revenue"] == 3_600_000
    assert shipping["packaging_cost"] == 120_000
    assert shipping["postage_estimated"] == 400_000
    assert shipping["net_shipping_result_estimated"] == (
        shipping["shipping_revenue"] - shipping["packaging_cost"] - shipping["postage_estimated"]
    )
    # 3,600,000 − 120,000 − 400,000; not 3,650,000 − 180,000 − 430,000 (the P&L figures).
    assert shipping["net_shipping_result_estimated"] == 3_080_000
    assert shipping["avg_net_shipping_result_estimated"] == 1_540_000
    assert shipping["postage_gap"] == 400_000 - 150_000
    assert shipping["net_shipping_result_estimated"] == sum(
        r["net"] for r in get_shipping_by_channel(test_db)
    )


def test_get_shipping_summary_estimated_result_with_unpaid_postage(test_db):
    # Three shipped WEBSITE orders carry 100,000 estimated postage each, but
    # only one postage batch (100,000) has been paid in the range. The
    # actual-based result looks profitable; the estimated one charges every
    # shipped order its frozen postage. postage_gap is what's still unpaid.
    product_id = add_product(test_db, "Shipping Est Item", cat(test_db, "OTHER"), 1000, 800)
    test_db.execute(
        "UPDATE products SET current_stock = 10, unit_cost = 100 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()
    for _ in range(3):
        record_order(
            test_db,
            "WEBSITE",
            [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
            shipping_charge=50_000,
            packaging_kit_id=None,
            postage_cost=100_000,
            status="PAID",
        )
    postage.record_postage_batch(test_db, total_paid=100_000, order_count=1)

    shipping = get_shipping_summary(test_db)
    assert shipping["shipped_order_count"] == 3
    assert shipping["shipping_revenue"] == 150_000
    assert shipping["packaging_cost"] == 0
    assert shipping["postage_estimated"] == 300_000
    assert shipping["postage_actual"] == 100_000
    assert shipping["net_shipping_result"] == 50_000
    # 150,000 - 0 - 300,000
    assert shipping["net_shipping_result_estimated"] == -150_000
    assert shipping["avg_net_shipping_result_estimated"] == -50_000
    assert shipping["postage_gap"] == 200_000


def test_get_shipping_summary_estimated_average_rounds_like_by_channel(test_db):
    # Same per-order average rule as get_shipping_by_channel's net_per_order:
    # round(net / shipped_order_count).
    product_id = add_product(test_db, "Shipping Round Item", cat(test_db, "OTHER"), 1000, 800)
    test_db.execute(
        "UPDATE products SET current_stock = 10, unit_cost = 100 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()
    for postage_cost in (10_000, 10_001, 10_001):
        record_order(
            test_db,
            "WEBSITE",
            [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
            shipping_charge=0,
            packaging_kit_id=None,
            postage_cost=postage_cost,
        )

    shipping = get_shipping_summary(test_db)
    by_channel = get_shipping_by_channel(test_db)
    assert shipping["net_shipping_result_estimated"] == -30_002 == by_channel[0]["net"]
    assert shipping["avg_net_shipping_result_estimated"] == round(-30_002 / 3)
    assert shipping["avg_net_shipping_result_estimated"] == by_channel[0]["net_per_order"]
    # No postage paid at all: the whole estimate is outstanding.
    assert shipping["postage_gap"] == 30_002


def test_get_shipping_summary_no_shipped_orders(test_db):
    shipping = get_shipping_summary(test_db)
    assert shipping["net_shipping_result_estimated"] == 0
    assert shipping["avg_net_shipping_result_estimated"] == 0
    assert shipping["postage_gap"] == 0


def test_get_shipping_by_channel(test_db):
    product_id = add_product(test_db, "Shipping Test Item", cat(test_db, "OTHER"), 1000, 800)
    test_db.execute(
        "UPDATE products SET current_stock = 10, unit_cost = 100 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()

    record_order(
        test_db,
        "WEBSITE",
        [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
        status="COMPLETED",
    )
    record_order(
        test_db,
        "WHOLESALE",
        [{"product_id": product_id, "quantity": 2, "unit_price": 1000}],
        status="COMPLETED",
    )
    # IN_PERSON never ships (applies_postage = 0) — must not appear at all.
    record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
        status="COMPLETED",
    )

    rows = get_shipping_by_channel(test_db)
    by_channel = {row["channel"]: row for row in rows}
    assert set(by_channel) == {"WEBSITE", "WHOLESALE"}

    website = by_channel["WEBSITE"]
    assert website["shipped_order_count"] == 1
    # The seeded default shipping charge: 1,800,000 Rial (180,000 x 10, migration 009).
    assert website["shipping_revenue"] == 1_800_000
    assert website["packaging_cost"] == 0
    assert website["postage_estimated"] == 0
    assert website["net"] == 1_800_000
    assert website["net_per_order"] == 1_800_000

    wholesale = by_channel["WHOLESALE"]
    assert wholesale["shipped_order_count"] == 1
    assert wholesale["shipping_revenue"] == 0
    assert wholesale["net"] == 0

    # Sorted by shipping_revenue desc, matching get_channel_breakdown's
    # precedent of sorting by total_revenue desc.
    assert rows[0]["channel"] == "WEBSITE"


# ---------------------------------------------------------------------------
# Full-scenario test (canonical fixture, built via real function calls only)
# ---------------------------------------------------------------------------


@pytest.fixture
def full_scenario_setup(test_db):
    vinyl_id = add_product(test_db, "Vinyl", cat(test_db, "VINYL"), 3_000_000, 2_500_000)
    record_product_purchase(test_db, vinyl_id, quantity_bought=10, total_paid=12_000_000)

    box_id = add_material(test_db, "Box", "STOCK", unit_cost=0)
    record_material_purchase(test_db, box_id, quantity_bought=100, total_paid=3_000_000)

    tape_id = add_material(test_db, "Tape", "STOCK", unit_cost=0, unit="m")
    record_material_purchase(test_db, tape_id, quantity_bought=100, total_paid=250_000)

    filler_id = add_material(test_db, "Filler", "STOCK", unit_cost=0)
    record_material_purchase(test_db, filler_id, quantity_bought=50, total_paid=500_000)

    kit_id = packaging.create_kit(test_db, "Standard box")
    packaging.add_kit_item(test_db, kit_id, box_id, 1)
    packaging.add_kit_item(test_db, kit_id, tape_id, 2)
    packaging.add_kit_item(test_db, kit_id, filler_id, 1)
    update_channel_settings(test_db, "WEBSITE", default_packaging_kit_id=kit_id)

    # B1: estimate = round(10,000,000 / 40) = 250,000
    postage.record_postage_batch(
        test_db, total_paid=10_000_000, order_count=40, paid_date="2026-03-01"
    )

    order_a_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 2, "unit_price": 2_500_000}],
        transaction_fee=50_000,
        order_date="2026-03-10",
        status="COMPLETED",
    )

    order_b_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        transaction_fee=30_000,
        order_date="2026-03-11",
        status="COMPLETED",
    )
    process_return(test_db, order_b_id, "REFUNDED")

    record_stock_adjustment(
        test_db, "PRODUCT", vinyl_id, -1, "WASTE", movement_date="2026-03-12"
    )

    ads_id = add_expense_category(test_db, "Ads")
    add_expense(test_db, ads_id, 500_000, expense_date="2026-03-15")

    # B2: with B1, estimate = round(10,600,000 / 42) = 252,381 afterwards —
    # but that's irrelevant to A/B, already committed before B2 existed.
    postage.record_postage_batch(
        test_db, total_paid=600_000, order_count=2, paid_date="2026-03-20"
    )

    return {
        "vinyl_id": vinyl_id,
        "box_id": box_id,
        "tape_id": tape_id,
        "filler_id": filler_id,
        "kit_id": kit_id,
        "order_a_id": order_a_id,
        "order_b_id": order_b_id,
    }


def test_full_scenario_profit_and_loss(full_scenario_setup, test_db):
    pnl = get_profit_and_loss(test_db, "2026-03-05", "2026-03-31")

    assert pnl["items_revenue"] == 5_000_000
    # Order A takes the seeded shipping charge: 1,800,000 Rial (180,000 x 10, migration 009).
    assert pnl["shipping_revenue"] == 1_800_000
    assert pnl["total_revenue"] == 6_800_000
    assert pnl["cogs"] == 2_400_000
    assert pnl["packaging_cost"] == 45_000
    assert pnl["postage_estimated"] == 250_000
    assert pnl["transaction_fees"] == 50_000
    assert pnl["gross_profit"] == 4_055_000
    assert pnl["postage_actual"] == 600_000
    # Order A (eligible) and order B (REFUNDED) each froze the 250,000 estimate.
    assert pnl["postage_committed"] == 500_000
    assert pnl["postage_variance"] == 100_000
    # Order B: packaging 45,000 + postage 250,000 + fee 30,000; the fee part is 30,000.
    assert pnl["refund_losses"] == 325_000
    assert pnl["refund_fee_losses"] == 30_000
    assert pnl["waste_cost"] == 1_200_000
    assert pnl["operating_expenses"] == 500_000
    assert pnl["net_profit"] == 1_930_000
    assert pnl["order_count"] == 1


def test_full_scenario_stock_and_reconciliation(full_scenario_setup, test_db):
    vinyl_id = full_scenario_setup["vinyl_id"]
    order_b_id = full_scenario_setup["order_b_id"]

    # 10 - 2 (order A) - 1 (order B) + 1 (order B refunded) - 1 (waste) = 7
    assert get_product(test_db, vinyl_id)["current_stock"] == 7

    performance = get_product_performance(test_db, "2026-03-05", "2026-03-31")
    assert len(performance) == 1
    vinyl_performance = performance[0]
    assert vinyl_performance["product_name"] == "Vinyl"
    assert vinyl_performance["total_revenue"] == 5_000_000
    assert vinyl_performance["total_cost"] == 2_400_000

    shipping = get_shipping_summary(test_db, "2026-03-05", "2026-03-31")
    # Seeded shipping charge: 1,800,000 Rial (180,000 x 10, migration 009).
    assert shipping["shipping_revenue"] == 1_800_000
    assert shipping["packaging_cost"] == 45_000
    assert shipping["postage_actual"] == 600_000
    assert shipping["net_shipping_result"] == 1_155_000  # 1,800,000 − 45,000 − 600,000
    assert shipping["net_shipping_result_estimated"] == (
        1_800_000 - 45_000 - shipping["postage_estimated"]
    )
    assert shipping["postage_gap"] == shipping["postage_estimated"] - 600_000

    pnl = get_profit_and_loss(test_db, "2026-03-05", "2026-03-31")
    refunded_postage_cost = test_db.execute(
        "SELECT postage_cost FROM orders WHERE id = ?", (order_b_id,)
    ).fetchone()["postage_cost"]
    assert (
        pnl["postage_estimated"] + refunded_postage_cost + pnl["postage_variance"]
        == pnl["postage_actual"]
    )


def test_full_scenario_cancellation_contributes_fee_only_to_refund_losses(
    full_scenario_setup, test_db
):
    vinyl_id = full_scenario_setup["vinyl_id"]
    stock_before = get_product(test_db, vinyl_id)["current_stock"]

    order_c_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        transaction_fee=25_000,
        order_date="2026-04-01",
        status="PAID",
    )
    assert get_product(test_db, vinyl_id)["current_stock"] == stock_before - 1

    process_return(test_db, order_c_id, "CANCELLED")

    assert get_product(test_db, vinyl_id)["current_stock"] == stock_before

    pnl = get_profit_and_loss(test_db, "2026-04-01", "2026-04-30")
    assert pnl["refund_losses"] == 25_000
    assert pnl["refund_fee_losses"] == 25_000
    # A cancelled order never shipped, so its frozen postage is not committed.
    assert pnl["postage_committed"] == 0
    # "and nothing else": the cancelled order is excluded from every other
    # eligible-order figure, so all of these stay at 0.
    assert pnl["items_revenue"] == 0
    assert pnl["cogs"] == 0
    assert pnl["packaging_cost"] == 0
    assert pnl["postage_estimated"] == 0
    assert pnl["postage_variance"] == 0
    assert pnl["net_profit"] == -25_000
    _assert_pnl_breakdowns_match_orders(test_db, "2026-04-01", "2026-04-30")
    _assert_pnl_breakdowns_match_orders(test_db, None, None)


def test_full_scenario_waste_rows_carry_item_id_and_unit(full_scenario_setup, test_db):
    tape_id = full_scenario_setup["tape_id"]
    record_stock_adjustment(
        test_db, "MATERIAL", tape_id, -3, "WASTE", movement_date="2026-03-12"
    )
    rows = get_waste_report(test_db, "2026-03-05", "2026-03-31")
    by_type = {row["item_type"]: row for row in rows}

    tape = by_type["MATERIAL"]
    assert tape["item_id"] == tape_id
    assert tape["item_name"] == "Tape"
    assert tape["unit"] == "m"

    vinyl = by_type["PRODUCT"]
    assert vinyl["item_id"] == full_scenario_setup["vinyl_id"]
    assert vinyl["unit"] == "piece"


@pytest.mark.parametrize(
    "start_date, end_date",
    [(None, None), ("2026-03-01", "2026-03-10"), ("2026-03-11", "2026-03-31"), ("2099-01-01", None)],
)
def test_expense_breakdown_sums_to_operating_expenses(report_setup, test_db, start_date, end_date):
    rows = get_expense_breakdown(test_db, start_date, end_date)
    pnl = get_profit_and_loss(test_db, start_date, end_date)
    assert sum(row["total_amount"] for row in rows) == pnl["operating_expenses"]


# ---------------------------------------------------------------------------
# postage_committed / refund_fee_losses, and channel breakdown vs P&L (section 9)
# ---------------------------------------------------------------------------

PNL_RANGES = [
    (None, None),
    ("2026-03-05", "2026-03-31"),
    ("2026-03-10", "2026-03-10"),
    ("2026-03-11", "2026-03-13"),
    ("2099-01-01", None),
]


def _order_sum(conn, expression, status_sql, start_date, end_date):
    """SUM(expression) straight from the orders table, order_date in range."""
    start_utc, end_utc = to_utc_range(start_date, end_date, conn)
    return conn.execute(
        f"""
        SELECT COALESCE(SUM({expression}), 0) FROM orders
        WHERE ({status_sql})
          AND (? IS NULL OR order_date >= ?) AND (? IS NULL OR order_date < ?)
        """,
        (start_utc, start_utc, end_utc, end_utc),
    ).fetchone()[0]


def _assert_pnl_breakdowns_match_orders(conn, start_date, end_date):
    pnl = get_profit_and_loss(conn, start_date, end_date)
    postage_committed = _order_sum(
        conn,
        "postage_cost",
        "status IN ('PENDING', 'PAID', 'COMPLETED', 'REFUNDED')",
        start_date,
        end_date,
    )
    refund_fee_losses = _order_sum(
        conn,
        "transaction_fee",
        "status = 'REFUNDED' OR (status = 'CANCELLED' AND stock_committed = 1)",
        start_date,
        end_date,
    )
    refunded_non_fee = _order_sum(
        conn, "packaging_cost + postage_cost", "status = 'REFUNDED'", start_date, end_date
    )
    assert pnl["postage_committed"] == postage_committed
    assert pnl["refund_fee_losses"] == refund_fee_losses
    assert pnl["postage_variance"] == pnl["postage_actual"] - pnl["postage_committed"]
    assert pnl["refund_losses"] - pnl["refund_fee_losses"] == refunded_non_fee


def _assert_channels_sum_to_gross_profit(conn, start_date, end_date):
    rows = get_channel_breakdown(conn, start_date, end_date)
    pnl = get_profit_and_loss(conn, start_date, end_date)
    assert sum(row["order_count"] for row in rows) == pnl["order_count"]
    assert sum(row["total_revenue"] for row in rows) == pnl["total_revenue"]
    assert sum(row["total_profit"] for row in rows) == pnl["gross_profit"]


@pytest.mark.parametrize("start_date, end_date", PNL_RANGES)
def test_pnl_breakdowns_match_orders_report_setup(report_setup, test_db, start_date, end_date):
    _assert_pnl_breakdowns_match_orders(test_db, start_date, end_date)


@pytest.mark.parametrize("start_date, end_date", PNL_RANGES)
def test_pnl_breakdowns_match_orders_full_scenario(
    full_scenario_setup, test_db, start_date, end_date
):
    _assert_pnl_breakdowns_match_orders(test_db, start_date, end_date)


@pytest.fixture
def channel_scenario(full_scenario_setup, test_db):
    """full_scenario_setup (one eligible WEBSITE order, one REFUNDED) plus an
    eligible INSTAGRAM order and a committed CANCELLED order with a fee."""
    vinyl_id = full_scenario_setup["vinyl_id"]
    instagram_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_800_000}],
        transaction_fee=40_000,
        order_date="2026-03-13",
        status="PAID",
    )
    cancelled_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_800_000}],
        transaction_fee=15_000,
        order_date="2026-03-13",
        status="PAID",
    )
    process_return(test_db, cancelled_id, "CANCELLED")
    return {**full_scenario_setup, "instagram_id": instagram_id, "cancelled_id": cancelled_id}


@pytest.mark.parametrize("start_date, end_date", PNL_RANGES)
def test_channel_breakdown_reconciles_with_pnl(channel_scenario, test_db, start_date, end_date):
    _assert_channels_sum_to_gross_profit(test_db, start_date, end_date)
    _assert_pnl_breakdowns_match_orders(test_db, start_date, end_date)


def test_channel_breakdown_is_gross_not_net(channel_scenario, test_db):
    statuses = {r[0] for r in test_db.execute("SELECT status FROM orders")}
    assert {"REFUNDED", "CANCELLED"} <= statuses
    rows = get_channel_breakdown(test_db, "2026-03-05", "2026-03-31")
    assert {row["channel"] for row in rows} == {"WEBSITE", "INSTAGRAM"}

    pnl = get_profit_and_loss(test_db, "2026-03-05", "2026-03-31")
    assert pnl["gross_profit"] != pnl["net_profit"]
    assert sum(row["total_profit"] for row in rows) == pnl["gross_profit"]
    # Refunded order B's 30,000 fee + the cancelled order's 15,000 fee.
    assert pnl["refund_fee_losses"] == 45_000
    # Order B's 325,000 (section 9 hand value above) + the cancelled fee.
    assert pnl["refund_losses"] == 340_000


@pytest.mark.parametrize("start_date, end_date", PNL_RANGES)
def test_channel_breakdown_reconciles_with_pnl_report_setup(
    report_setup, test_db, start_date, end_date
):
    # report_setup's CANCELLED order was never committed.
    _assert_channels_sum_to_gross_profit(test_db, start_date, end_date)
    pnl = get_profit_and_loss(test_db)
    assert pnl["gross_profit"] != pnl["net_profit"]


@pytest.fixture
def purchase_items(test_db):
    material_id = add_material(test_db, "Purchase Report Box", "STOCK", 10_000, initial_stock=0)
    product_id = add_product(test_db, "Purchase Report Vinyl", cat(test_db, "VINYL"), 3000, 2000)
    return material_id, product_id


def test_get_purchases_summary_totals_and_counts_per_range(test_db, purchase_items):
    material_id, product_id = purchase_items
    # March: two material purchases, one product purchase.
    record_material_purchase(test_db, material_id, 10, 100_000, purchase_date="2026-03-02")
    record_material_purchase(test_db, material_id, 5, 55_000, purchase_date="2026-03-20")
    record_product_purchase(test_db, product_id, 4, 800_000, purchase_date="2026-03-15")
    # April: one of each.
    record_material_purchase(test_db, material_id, 1, 12_000, purchase_date="2026-04-01")
    record_product_purchase(test_db, product_id, 2, 450_000, purchase_date="2026-04-10")

    assert get_purchases_summary(test_db, "2026-03-01", "2026-03-31") == {
        "material_purchases_total": 155_000,
        "material_purchases_count": 2,
        "product_purchases_total": 800_000,
        "product_purchases_count": 1,
    }
    assert get_purchases_summary(test_db, "2026-04-01", "2026-04-30") == {
        "material_purchases_total": 12_000,
        "material_purchases_count": 1,
        "product_purchases_total": 450_000,
        "product_purchases_count": 1,
    }
    # No range: everything.
    assert get_purchases_summary(test_db)["material_purchases_total"] == 167_000
    assert get_purchases_summary(test_db)["product_purchases_count"] == 2


def test_get_purchases_summary_boundary_days_are_whole_local_days(test_db, purchase_items):
    material_id, product_id = purchase_items
    # "2026-03-31" is stored as local midnight (2026-03-30 20:30 UTC in
    # Asia/Tehran): it belongs to the 31st, so March includes it and April
    # does not.
    record_material_purchase(test_db, material_id, 1, 30_000, purchase_date="2026-03-31")
    record_product_purchase(test_db, product_id, 1, 70_000, purchase_date="2026-04-01")

    march = get_purchases_summary(test_db, "2026-03-01", "2026-03-31")
    april = get_purchases_summary(test_db, "2026-04-01", "2026-04-30")
    assert (march["material_purchases_total"], march["product_purchases_total"]) == (30_000, 0)
    assert (april["material_purchases_total"], april["product_purchases_total"]) == (0, 70_000)
    single_day = get_purchases_summary(test_db, "2026-03-31", "2026-03-31")
    assert single_day["material_purchases_count"] == 1
    assert single_day["product_purchases_count"] == 0


def test_get_purchases_summary_empty_range(test_db, purchase_items):
    material_id, _ = purchase_items
    record_material_purchase(test_db, material_id, 1, 30_000, purchase_date="2026-03-10")
    assert get_purchases_summary(test_db, "2025-01-01", "2025-01-31") == {
        "material_purchases_total": 0,
        "material_purchases_count": 0,
        "product_purchases_total": 0,
        "product_purchases_count": 0,
    }


def test_get_purchases_summary_backdated_purchase_lands_in_its_own_period(test_db, purchase_items):
    material_id, product_id = purchase_items
    # Recorded now (today) but dated in January: it counts in January, not
    # in the period it was entered.
    record_product_purchase(test_db, product_id, 3, 600_000, purchase_date="2026-01-15")
    record_material_purchase(test_db, material_id, 2, 20_000)  # no date: now

    january = get_purchases_summary(test_db, "2026-01-01", "2026-01-31")
    assert january["product_purchases_total"] == 600_000
    assert january["material_purchases_count"] == 0
    february = get_purchases_summary(test_db, "2026-02-01", "2026-02-28")
    assert february["product_purchases_count"] == 0


def test_get_purchases_summary_is_not_in_profit_and_loss(test_db, purchase_items):
    material_id, product_id = purchase_items
    record_material_purchase(test_db, material_id, 10, 100_000, purchase_date="2026-03-02")
    record_product_purchase(test_db, product_id, 4, 800_000, purchase_date="2026-03-15")
    pnl = get_profit_and_loss(test_db, "2026-03-01", "2026-03-31")
    assert pnl["operating_expenses"] == 0
    assert pnl["net_profit"] == 0


# ---------------------------------------------------------------- waste cost rounding


def _waste(conn, item_type, item_id, quantity, unit_cost, day="2026-03-05"):
    conn.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, movement_date, unit_cost_at_time)
        VALUES (?, ?, ?, 'WASTE', ?, ?)
        """,
        (item_type, item_id, -quantity, f"{day} 08:00:00", unit_cost),
    )


@pytest.fixture
def fractional_waste(test_db):
    """Fractional material waste across several items (accounting rules section 8)."""
    ids = {
        name: add_material(test_db, name, "STOCK", 1, initial_stock=100)
        for name in ("Glue", "Tape", "Ink", "Foil", "Film", "Never known")
    }
    _waste(test_db, "MATERIAL", ids["Glue"], 2.5, 333)          # 832.5 -> 832 (tie, even)
    _waste(test_db, "MATERIAL", ids["Tape"], 0.5, 7)            # 3.5 + 3.5 = 7 -> 7, rounded once per
    _waste(test_db, "MATERIAL", ids["Tape"], 0.5, 7)            #   item, not per movement (4 + 4 = 8)
    _waste(test_db, "MATERIAL", ids["Ink"], 2.4, 3)             # 7.2 + 0.3 = 7.5 -> 8 (floats give
    _waste(test_db, "MATERIAL", ids["Ink"], 0.1, 3)             #   7.4999... -> 7)
    _waste(test_db, "MATERIAL", ids["Foil"], 3.2, 3)            # 9.6 + 0.9 = 10.5 -> 10 (floats give
    _waste(test_db, "MATERIAL", ids["Foil"], 0.3, 3)            #   10.5000...02 -> 11)
    _waste(test_db, "MATERIAL", ids["Film"], 0.5, 1)            # 0.5 -> 0
    _waste(test_db, "MATERIAL", ids["Film"], 1, None)           # unknown cost: excluded
    _waste(test_db, "MATERIAL", ids["Never known"], 1.5, None)  # every cost unknown: None
    product_id = add_product(test_db, "Waste LP", cat(test_db, "OTHER"), 1000, 800)
    _waste(test_db, "PRODUCT", product_id, 1, 100_001, day="2026-03-20")
    test_db.commit()
    return ids


def test_waste_report_cost_is_integer_rial_rounded_once_per_item(fractional_waste, test_db):
    costs = {row["item_name"]: row["cost"] for row in get_waste_report(test_db)}
    assert costs == {
        "Glue": 832, "Tape": 7, "Ink": 8, "Foil": 10, "Film": 0, "Never known": None, "Waste LP": 100_001,
    }
    assert all(isinstance(c, int) for c in costs.values() if c is not None)


@pytest.mark.parametrize(
    "start, end",
    [(None, None), ("2026-03-01", "2026-03-10"), ("2026-03-15", "2026-03-31"), ("2026-04-01", None)],
)
def test_pnl_waste_cost_is_the_sum_of_the_waste_report(fractional_waste, test_db, start, end):
    report_total = sum(
        row["cost"] for row in get_waste_report(test_db, start, end) if row["cost"] is not None
    )
    pnl = get_profit_and_loss(test_db, start, end)
    assert pnl["waste_cost"] == report_total
    assert isinstance(pnl["waste_cost"], int)
    assert isinstance(pnl["net_profit"], int)


def test_pnl_waste_cost_values(fractional_waste, test_db):
    # 832 + 7 + 8 + 10 + 0 + 100,001. The exact grand total (858 + 100,001 =
    # 100,859) would differ; the sum of the per-item rounded costs is the rule.
    assert get_profit_and_loss(test_db)["waste_cost"] == 100_858
    assert get_profit_and_loss(test_db, "2026-03-01", "2026-03-10")["waste_cost"] == 857
