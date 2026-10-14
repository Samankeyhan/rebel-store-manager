"""A test shop with every kind of data the go-live reset has to clear or keep (fictional names only)."""

import sqlite3

from db.distributions import record_profit_distribution
from db.expenses import add_expense, add_expense_category
from db.materials import add_material
from db.orders import record_order
from db.packaging import add_kit_item, create_kit
from db.partners import add_partner
from db.payment_methods import add_payment_method
from db.postage import record_postage_batch
from db.production import run_production_batch
from db.products import add_product
from db.purchases import record_material_purchase, record_product_purchase
from db.recipes import add_recipe_item
from db.settlements import record_settlement
from db.suppliers import add_supplier
from db.timeutil import today_local
from tests.helpers import cat


def build_shop(conn: sqlite3.Connection) -> dict:
    """Setup data (kept) and test transactions (cleared), including the DigiPay / digipay duplicate."""
    ids: dict = {}
    ids["supplier"] = add_supplier(conn, "Test Supplier")
    ids["partner_a"] = add_partner(conn, "Partner A", 60)
    ids["partner_b"] = add_partner(conn, "Partner B", 40)
    ids["expense_category"] = add_expense_category(conn, "Courier")

    ids["paper"] = add_material(conn, "Paper", "STOCK", 1000, initial_stock=50)
    ids["ink"] = add_material(conn, "Ink", "STOCK", 2000, initial_stock=10)
    ids["labour"] = add_material(conn, "Labour", "SERVICE", 5000)
    ids["kit"] = create_kit(conn, "Box")
    add_kit_item(conn, ids["kit"], ids["paper"], 1)

    ids["lp"] = add_product(conn, "Test LP", cat(conn, "VINYL"), 3000000, 2000000)
    ids["shirt"] = add_product(conn, "Test Shirt", cat(conn, "OTHER"), 1000000, 800000)
    ids["made"] = add_product(conn, "Made To Order", cat(conn, "OTHER"), 900000, 700000)
    add_recipe_item(conn, ids["lp"], ids["paper"], 2)
    add_recipe_item(conn, ids["lp"], ids["labour"], 1, "PER_BATCH")
    add_recipe_item(conn, ids["made"], ids["ink"], 1)
    conn.execute("UPDATE products SET made_to_order = 1 WHERE id = ?", (ids["made"],))
    conn.execute("UPDATE products SET current_stock = 20, unit_cost = 300000 WHERE id = ?", (ids["shirt"],))

    # the same payment method typed twice: neither has a name_key, as in the real database
    ids["zarinpal"] = add_payment_method(conn, "ZarinPal", "DAYS_AFTER", 1, fee_bps=50, fee_fixed=5000)
    ids["digipay"] = add_payment_method(conn, "DigiPay", "DAY_OF_NEXT_MONTH", 7, fee_bps=1300)
    ids["card"] = add_payment_method(conn, "Card to card", "IMMEDIATE")
    conn.execute("UPDATE payment_methods SET name_key = NULL WHERE id = ?", (ids["digipay"],))
    cursor = conn.execute(
        "INSERT INTO payment_methods (name, fee_bps, fee_fixed, settlement_rule) VALUES ('digipay', 0, 0, 'IMMEDIATE')"
    )
    ids["digipay_dup"] = cursor.lastrowid
    conn.execute("UPDATE channel_settings SET default_payment_method_id = ? WHERE channel = 'WEBSITE'", (ids["digipay_dup"],))

    # transactions
    record_material_purchase(conn, ids["paper"], 20, 30000, supplier_id=ids["supplier"])
    record_product_purchase(conn, ids["shirt"], 5, 2000000, supplier_id=ids["supplier"])
    run_production_batch(conn, ids["lp"], 5)
    day = today_local(conn).isoformat()
    ids["orders"] = [
        record_order(conn, "WEBSITE", [{"product_id": ids["shirt"], "quantity": 2, "unit_price": 1000000}], payment_method_id=ids["zarinpal"],
                     status="PAID"),
        record_order(conn, "WEBSITE", [{"product_id": ids["lp"], "quantity": 1, "unit_price": 3000000}], payment_method_id=ids["digipay_dup"],
                     status="PAID"),
        record_order(conn, "IN_PERSON", [{"product_id": ids["made"], "quantity": 1, "unit_price": 900000}], status="COMPLETED"),
    ]
    ids["settlement"] = record_settlement(conn, ids["zarinpal"], day, 100, order_ids=[ids["orders"][0]])
    add_expense(conn, ids["expense_category"], 400000, "courier", day)
    record_postage_batch(conn, 1000000, 3, day)
    ids["distribution"] = record_profit_distribution(conn, day, day, 1000, allow_exceeding=True)
    return ids


def dump(conn: sqlite3.Connection, tables: list[str]) -> dict:
    return {t: [tuple(r) for r in conn.execute(f'SELECT * FROM "{t}" ORDER BY 1')] for t in tables}


def db_file(conn: sqlite3.Connection) -> str:
    return next(row["file"] for row in conn.execute("PRAGMA database_list") if row["name"] == "main")
