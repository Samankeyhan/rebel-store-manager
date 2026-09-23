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
    get_shipping_summary,
    get_waste_report,
)
from db.returns import process_return
from db.settings import update_channel_settings


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
    assert material["cost"] == 1000
    assert material["unknown_cost_count"] == 0

    product = by_key[("PRODUCT", "Report Vinyl")]
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
    # Order A (INSTAGRAM): items_revenue 6000, shipping 100, cogs 1000,
    #   packaging 0, postage_estimated 50, fee 20.
    # Order B (WEBSITE, no overrides): items_revenue 1500, shipping 180,000
    #   (channel default), cogs 300, packaging 0, postage_estimated 0.
    # (Cancelled order excluded from all of the above — not eligible.)
    #
    # items_revenue = 6000 + 1500 = 7500
    # shipping_revenue = 100 + 180,000 = 180,100
    # total_revenue = 187,600
    # cogs = 1000 + 300 = 1300; packaging_cost = 0
    # postage_estimated = 50 + 0 = 50; transaction_fees = 20 + 0 = 20
    # gross_profit = 187,600 - 1300 - 0 - 50 - 20 = 186,230
    #
    # postage_actual = 0 (no postage batches in this fixture)
    # postage committed on shipped (eligible+REFUNDED) orders = 50 (order A) + 0
    # postage_variance = 0 - 50 = -50
    #
    # refund_losses = 0 (no REFUNDED orders; the CANCELLED order's fee is 0)
    # waste_cost = material 5*200 + product 1*500 = 1000 + 500 = 1500
    # operating_expenses = 500 + 200 = 700
    #
    # net_profit = 186,230 - (-50) - 0 - 1500 - 700 = 184,080
    pnl = get_profit_and_loss(test_db)

    assert pnl["order_count"] == 2
    assert pnl["items_revenue"] == 7500
    assert pnl["shipping_revenue"] == 180_100
    assert pnl["total_revenue"] == 187_600
    assert pnl["cogs"] == 1300
    assert pnl["packaging_cost"] == 0
    assert pnl["postage_estimated"] == 50
    assert pnl["transaction_fees"] == 20
    assert pnl["gross_profit"] == 186_230
    assert pnl["postage_actual"] == 0
    assert pnl["postage_variance"] == -50
    assert pnl["refund_losses"] == 0
    assert pnl["waste_cost"] == 1500
    assert pnl["operating_expenses"] == 700
    assert pnl["net_profit"] == 184_080


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
    assert instagram_only["postage_variance"] == -50
    assert instagram_only["refund_losses"] == 0
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
        "postage_variance": 0,
        "refund_losses": 0,
        "waste_cost": 0,
        "operating_expenses": 0,
        "net_profit": 0,
        "order_count": 0,
    }


# ---------------------------------------------------------------------------
# Full-scenario test (canonical fixture, built via real function calls only)
# ---------------------------------------------------------------------------


@pytest.fixture
def full_scenario_setup(test_db):
    vinyl_id = add_product(test_db, "Vinyl", "VINYL", 3_000_000, 2_500_000)
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
    assert pnl["shipping_revenue"] == 180_000
    assert pnl["total_revenue"] == 5_180_000
    assert pnl["cogs"] == 2_400_000
    assert pnl["packaging_cost"] == 45_000
    assert pnl["postage_estimated"] == 250_000
    assert pnl["transaction_fees"] == 50_000
    assert pnl["gross_profit"] == 2_435_000
    assert pnl["postage_actual"] == 600_000
    assert pnl["postage_variance"] == 100_000
    assert pnl["refund_losses"] == 325_000
    assert pnl["waste_cost"] == 1_200_000
    assert pnl["operating_expenses"] == 500_000
    assert pnl["net_profit"] == 310_000
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
    assert shipping["shipping_revenue"] == 180_000
    assert shipping["packaging_cost"] == 45_000
    assert shipping["postage_actual"] == 600_000
    assert shipping["net_shipping_result"] == -465_000

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
    # "and nothing else": the cancelled order is excluded from every other
    # eligible-order figure, so all of these stay at 0.
    assert pnl["items_revenue"] == 0
    assert pnl["cogs"] == 0
    assert pnl["packaging_cost"] == 0
    assert pnl["postage_estimated"] == 0
    assert pnl["postage_variance"] == 0
    assert pnl["net_profit"] == -25_000
