import pytest

from db.expenses import add_expense, add_expense_category
from db.materials import add_material
from db.orders import record_order
from db.products import add_product, deactivate_product
from db.reports import (
    get_channel_breakdown,
    get_expense_breakdown,
    get_low_stock_products,
    get_product_performance,
    get_profit_and_loss,
    get_waste_report,
)


@pytest.fixture
def report_setup(test_db):
    product_a_id = add_product(test_db, "Report Vinyl", "VINYL", 3000, 2000)
    product_b_id = add_product(test_db, "Report Cassette", "CASSETTE", 1500, 1000)
    test_db.execute(
        "UPDATE products SET current_stock = 100, unit_cost = 500 WHERE id = ?",
        (product_a_id,),
    )
    test_db.execute(
        "UPDATE products SET current_stock = 100, unit_cost = 300 WHERE id = ?",
        (product_b_id,),
    )
    test_db.commit()

    low_stock_id = add_product(test_db, "Low Stock Item", "OTHER", 500, 400)
    test_db.execute(
        "UPDATE products SET current_stock = 2, unit_cost = 100 WHERE id = ?",
        (low_stock_id,),
    )
    inactive_id = add_product(test_db, "Inactive Low", "OTHER", 500, 400)
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

    test_db.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, movement_date)
        VALUES ('MATERIAL', ?, -3, 'WASTE', '2026-03-05 08:00:00')
        """,
        (material_id,),
    )
    test_db.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, movement_date)
        VALUES ('MATERIAL', ?, -2, 'WASTE', '2026-03-20 08:00:00')
        """,
        (material_id,),
    )
    test_db.execute(
        """
        INSERT INTO stock_movements
            (item_type, item_id, quantity_change, reason, movement_date)
        VALUES ('PRODUCT', ?, -1, 'WASTE', '2026-03-08 08:00:00')
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
    # defaults — shipping_charge = default_shipping_charge (180,000), postage
    # estimate = 0 (no postage batches recorded in this fixture).
    # revenue = items_net(1500) + shipping(180,000) = 181,500
    # profit = 181,500 - cogs(300) - packaging(0) - postage(0) - fee(0) = 181,200
    rows = get_channel_breakdown(test_db)
    assert len(rows) == 2

    by_channel = {row["channel"]: row for row in rows}
    assert by_channel["INSTAGRAM"]["order_count"] == 1
    assert by_channel["INSTAGRAM"]["total_revenue"] == 6100
    assert by_channel["INSTAGRAM"]["total_profit"] == 5030

    assert by_channel["WEBSITE"]["order_count"] == 1
    assert by_channel["WEBSITE"]["total_revenue"] == 181_500
    assert by_channel["WEBSITE"]["total_profit"] == 181_200

    # Sorted by total_revenue desc — WEBSITE's default shipping charge now
    # puts it ahead of INSTAGRAM.
    assert rows[0]["channel"] == "WEBSITE"


def test_get_channel_breakdown_excludes_cancelled_and_empty_range(report_setup, test_db):
    assert "OTHER" not in {row["channel"] for row in get_channel_breakdown(test_db)}
    assert get_channel_breakdown(test_db, start_date="2099-01-01") == []


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
    assert material["total_wasted"] == 5
    assert material["waste_event_count"] == 2
    assert material["estimated_cost"] == 1000

    product = by_key[("PRODUCT", "Report Vinyl")]
    assert product["total_wasted"] == 1
    assert product["waste_event_count"] == 1
    assert product["estimated_cost"] == 500

    assert rows[0]["item_name"] == "Waste Material"


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

    assert get_expense_breakdown(test_db, start_date="2099-01-01") == []


def test_get_profit_and_loss_hand_calculated(report_setup, test_db):
    # Order INSTAGRAM: revenue = 6000 + shipping(100) = 6100
    #                  profit = 6100 - cogs(1000) - postage(50) - fee(20) = 5030
    # Order WEBSITE: no overrides given, so it picks up the channel's default
    #                shipping charge (180,000) and a postage estimate of 0.
    #                revenue = 1500 + 180,000 = 181,500
    #                profit = 181,500 - cogs(300) = 181,200
    # Cancelled order excluded. Expenses: Ads 500 + Tools 200 = 700.
    # total_revenue = 6100 + 181,500 = 187,600
    # total_profit = 5030 + 181,200 = 186,230
    # total_cost_of_goods = total_revenue - total_profit = 1,370
    # net_profit = total_profit - expenses = 186,230 - 700 = 185,530
    pnl = get_profit_and_loss(test_db)

    assert pnl["order_count"] == 2
    assert pnl["total_revenue"] == 187_600
    assert pnl["total_cost_of_goods"] == 1370
    assert pnl["total_expenses"] == 700
    assert pnl["net_profit"] == 185_530


def test_get_profit_and_loss_date_filter(report_setup, test_db):
    # Only the INSTAGRAM order falls in this one-day range.
    # revenue 6100, cogs+postage+fee = 1070, profit 5030.
    instagram_only = get_profit_and_loss(
        test_db, start_date="2026-03-10", end_date="2026-03-10"
    )
    assert instagram_only["order_count"] == 1
    assert instagram_only["total_revenue"] == 6100
    assert instagram_only["total_cost_of_goods"] == 1070
    assert instagram_only["total_expenses"] == 0
    assert instagram_only["net_profit"] == 5030

    assert get_profit_and_loss(test_db, start_date="2099-01-01") == {
        "total_revenue": 0,
        "total_cost_of_goods": 0,
        "total_expenses": 0,
        "net_profit": 0,
        "order_count": 0,
    }
