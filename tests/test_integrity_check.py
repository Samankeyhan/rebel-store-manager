"""python -m tools.integrity_check: a clean fictional shop passes every check, and one deliberate corruption per check is
named by table, id and field (stored, expected, difference), with exit code 1."""

import json
import shutil
import sqlite3
from datetime import date

import pytest

import db.orders
import db.settlements
from db.adjustments import record_service_waste, record_stock_adjustment
from db.connection import MIGRATIONS_DIR, get_connection, init_db
from db.distributions import compute_share_amounts, record_profit_distribution
from db.materials import add_material
from db.orders import record_order
from db.partners import add_partner
from db.payment_methods import add_payment_method
from db.production import run_production_batch
from db.products import add_product
from db.purchases import record_material_purchase, record_product_purchase
from db.recipes import add_recipe_item
from db.returns import process_return
from db.settlements import record_settlement
from tests.helpers import cat, stocked_product
from tools.integrity_check import __main__ as cli
from tools.integrity_check.checks import run_checks, stock_tolerance
from tools.integrity_check.readonly import open_readonly, schema_version

TODAY = date(2026, 10, 6)  # 14 Mehr 1405; Shahrivar 1405 = 2026-08-23..2026-09-22


def db_file(conn) -> str:
    return next(row["file"] for row in conn.execute("PRAGMA database_list") if row["name"] == "main")


@pytest.fixture
def shop(test_db, monkeypatch):
    """A fictional shop that is consistent: every check passes."""
    for module in (db.orders, db.settlements):
        monkeypatch.setattr(module, "today_local", lambda conn=None: TODAY)
    conn = test_db
    ids = {}
    ids["product"] = stocked_product(conn, "Fictional LP", stock=0, unit_cost=0)
    conn.execute("UPDATE products SET current_stock = 0, unit_cost = NULL WHERE id = ?", (ids["product"],))
    ids["made"] = add_product(conn, "Fictional Tee", cat(conn, "TSHIRT"), 3_000_000, 2_000_000)
    ids["box"] = add_material(conn, "Fictional Box", "STOCK", 12_000, initial_stock=100)
    ids["ink"] = add_material(conn, "Fictional Ink", "STOCK", 700, initial_stock=0.5)
    ids["print"] = add_material(conn, "Fictional Printing", "SERVICE", 90_000)
    add_recipe_item(conn, ids["made"], ids["box"], 2)
    add_recipe_item(conn, ids["made"], ids["ink"], 0.25)
    add_recipe_item(conn, ids["made"], ids["print"], 1)
    record_material_purchase(conn, ids["box"], 10, 150_000)
    record_material_purchase(conn, ids["ink"], 2.5, 3_333)
    record_product_purchase(conn, ids["product"], 40, 4_000_000)
    ids["batch"] = conn.execute("SELECT 1").fetchone() and None
    run_production_batch(conn, ids["made"], 5)
    ids["batch"] = conn.execute("SELECT MAX(id) FROM production_batches").fetchone()[0]
    record_stock_adjustment(conn, "MATERIAL", ids["box"], -3, "WASTE")
    record_stock_adjustment(conn, "MATERIAL", ids["ink"], 0.1, "ADJUSTMENT")

    ids["card"] = add_payment_method(conn, "Card to card", "IMMEDIATE")
    ids["zarinpal"] = add_payment_method(conn, "Zarinpal", "DAYS_AFTER", 1, fee_bps=50, fee_cap=160_000, fee_fixed=5_000)
    ids["digipay"] = add_payment_method(conn, "Digipay", "DAY_OF_NEXT_MONTH", 7, fee_bps=300)

    def order(method, paid, price, status="COMPLETED", product=None, quantity=1, **extra):
        return record_order(
            conn, "WEBSITE", [{"product_id": product or ids["product"], "quantity": quantity, "unit_price": price}],
            order_date=paid, shipping_charge=extra.pop("shipping_charge", 30_000), packaging_kit_id=None,
            postage_cost=0, payment_method_id=ids[method] if method else None, status=status, **extra,
        )

    ids["card_order"] = order("card", "2026-09-01", 1_000_000)
    ids["zarinpal_order"] = order("zarinpal", "2026-09-30", 9_490_000, payment_reference="ZP-1")
    ids["digi_a"] = order("digipay", "2026-09-10", 2_500_000, quantity=2)
    ids["digi_b"] = order("digipay", "2026-09-12", 640_000)
    ids["pending_order"] = order("digipay", "2026-10-01", 700_000)
    ids["draft"] = order(None, "2026-10-02", 100_000, status="DRAFT")
    ids["cancelled"] = order("card", "2026-10-02", 100_000, status="PENDING")
    process_return(conn, ids["cancelled"], "CANCELLED")
    ids["refunded"] = order("card", "2026-09-02", 200_000)
    process_return(conn, ids["refunded"], "REFUNDED")

    ids["s_card"] = record_settlement(conn, ids["card"], "2026-09-05", 1_030_000, order_ids=[ids["card_order"]])
    ids["s_digi"] = record_settlement(conn, ids["digipay"], "2026-09-28", 5_400_000, jalali_year=1405, jalali_month=6)

    ids["partner_a"] = add_partner(conn, "Fictional Partner A", 60)
    ids["partner_b"] = add_partner(conn, "Fictional Partner B", 40)
    ids["distribution"] = record_profit_distribution(conn, "2026-08-01", "2026-08-31", 100_001, allow_exceeding=True)
    conn.commit()
    return ids


def writable(conn_or_path):
    path = conn_or_path if isinstance(conn_or_path, str) else db_file(conn_or_path)
    raw = sqlite3.connect(path, isolation_level=None)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA ignore_check_constraints = ON")  # corruption that the CHECK constraints would refuse
    return raw


def run(conn):
    """(results by key, the CLI's exit code, its text) for the database behind `conn`."""
    path = db_file(conn)
    reader = open_readonly(path)
    try:
        number, _ = schema_version(reader)
        results = {r.key: r for r in run_checks(reader, number)}
    finally:
        reader.close()
    return results


def fails(results, key):
    return [row.render() for row in results[key].fails]


def cli_run(conn, capsys):
    code = cli.main(["--db", db_file(conn)])
    return code, capsys.readouterr().out


# ----------------------------------------------------------------------- clean


def test_a_consistent_shop_passes_every_check(shop, test_db, capsys):
    code, text = cli_run(test_db, capsys)
    assert code == 0, text
    assert text.strip().splitlines()[-1] == "OK"
    results = run(test_db)
    statuses = {key: r.status for key, r in results.items()}
    assert statuses == {"a": "PASS", "b": "PASS", "c": "PASS", "d1": "PASS", "d2": "PASS", "d3": "SKIPPED",
                        "d4": "PASS", "e": "PASS", "f": "PASS", "g": "PASS", "h": "PASS", "i": "PASS"}, text
    assert results["b"].summary == "2 settlements checked"
    # The audit log knows what the two materials were created with, so there is nothing to guess.
    assert results["d1"].infos == []


def test_the_header_has_a_fixed_length_and_the_report_ends_with_one_final_line(shop, test_db, capsys):
    code, text = cli_run(test_db, capsys)
    lines = text.splitlines()
    assert lines[cli.HEADER_LINES - 1] == "-" * 60
    assert lines[0].startswith("Rebel Store Manager - integrity check")
    assert any(line.startswith("Schema   : 015_supplier_payables_purchase_status.sql (version 15)") for line in lines[:cli.HEADER_LINES])
    assert sum(line in ("OK",) or line.startswith(("FAILED:", "INCOMPLETE:")) for line in lines) == 1


def test_stock_tolerance_is_relative_with_an_absolute_floor():
    from fractions import Fraction

    assert stock_tolerance(0, 0) == Fraction(1, 10**6)
    assert stock_tolerance(5, 5) == Fraction(1, 10**6)
    assert stock_tolerance(10**9, 0) == Fraction(1)


# ------------------------------------------------------------- a. database health


def test_a_foreign_key_violation_is_named(shop, test_db):
    raw = writable(test_db)
    raw.execute("PRAGMA foreign_keys = OFF")
    raw.execute("INSERT INTO order_items (order_id, product_id, quantity, list_price, unit_price, unit_cost_at_time) "
                "VALUES (?, 99999, 1, 1000, 1000, 0)", (shop["card_order"],))
    item_id = raw.execute("SELECT MAX(id) FROM order_items").fetchone()[0]
    raw.close()
    results = run(test_db)
    assert results["a"].status == "FAIL"
    assert any(f"order_items id={item_id} field=foreign key -> products" in line for line in fails(results, "a"))


def test_a_damaged_integrity_check_message_is_a_failure():
    from tools.integrity_check.checks import check_database_health

    class Fake:
        def execute(self, sql):
            return [("*** in database main *** Page 2: btree corrupt",)] if "integrity" in sql else []

    result = check_database_health(Fake(), 13)
    assert result.status == "FAIL" and "btree corrupt" in result.fails[0].render()


# ---------------------------------------------------------------- b. settlements


def test_a_settlement_total_that_does_not_match_its_orders_is_named(shop, test_db):
    raw = writable(test_db)
    stored = raw.execute("SELECT expected_amount FROM settlements WHERE id = ?", (shop["s_digi"],)).fetchone()[0]
    raw.execute("UPDATE settlements SET expected_amount = expected_amount + 1 WHERE id = ?", (shop["s_digi"],))
    raw.close()
    (line,) = fails(run(test_db), "b")
    assert f"settlements id={shop['s_digi']} field=expected_amount stored={stored + 1} expected={stored} diff=1" in line


def test_a_changed_fee_after_settlement_moves_the_recomputed_total(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE orders SET transaction_fee = transaction_fee + 7 WHERE id = ?", (shop["digi_a"],))
    raw.close()
    (line,) = fails(run(test_db), "b")
    assert f"settlements id={shop['s_digi']} field=expected_amount" in line and "diff=7" in line


def test_an_order_in_a_settlement_of_another_method_or_month_is_named(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE orders SET payment_method_id = ? WHERE id = ?", (shop["card"], shop["digi_b"]))
    raw.execute("UPDATE orders SET paid_jalali_month = 5 WHERE id = ?", (shop["digi_a"],))
    raw.close()
    lines = fails(run(test_db), "b")
    assert any(f"orders id={shop['digi_b']} field=payment_method_id" in line for line in lines)
    assert any(f"orders id={shop['digi_a']} field=paid_jalali_year/month" in line for line in lines)


# ---------------------------------------------------------------------- c. orders


def test_a_wrong_jalali_month_on_a_paid_order_is_named(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE orders SET paid_jalali_month = 12 WHERE id = ?", (shop["zarinpal_order"],))
    raw.close()
    (line,) = fails(run(test_db), "c")
    assert f"orders id={shop['zarinpal_order']} field=paid_jalali_year/month" in line


def test_a_wrong_expected_settlement_date_on_a_pending_order_is_named_but_not_on_a_settled_one(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE orders SET expected_settlement_date = '2030-01-01' WHERE id IN (?, ?)",
                (shop["zarinpal_order"], shop["card_order"]))  # the card order is settled: not checked
    raw.close()
    (line,) = fails(run(test_db), "c")
    assert f"orders id={shop['zarinpal_order']} field=expected_settlement_date stored=\"2030-01-01\" expected=\"2026-10-01\"" in line


def test_a_missing_paid_date_on_a_paid_order_with_a_method_is_named(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE orders SET paid_date = NULL WHERE id = ?", (shop["zarinpal_order"],))
    raw.close()
    (line,) = fails(run(test_db), "c")
    assert f"orders id={shop['zarinpal_order']} field=paid_date stored=NULL" in line


def test_a_paid_order_with_no_method_and_no_paid_date_is_legacy_info_listing_the_ids(shop, test_db, capsys):
    no_method = record_order(
        test_db, "WEBSITE", [{"product_id": shop["product"], "quantity": 1, "unit_price": 1000}],
        shipping_charge=0, packaging_kit_id=None, postage_cost=0, payment_method_id=None, status="COMPLETED",
    )
    test_db.commit()
    raw = writable(test_db)
    raw.execute("UPDATE orders SET paid_date = NULL, paid_jalali_year = NULL, paid_jalali_month = NULL WHERE id IN (?, ?)",
                (no_method, shop["draft"]))  # the draft is not paid: not listed
    raw.close()
    results = run(test_db)
    assert results["c"].status == "PASS" and not results["c"].fails
    (info,) = [i for i in results["c"].infos if "legacy" in i]
    assert f"orders ids=[{no_method}]" in info
    for _ in range(2):  # listed on every run, and the exit code stays 0
        code, text = cli_run(test_db, capsys)
        assert code == 0 and text.strip().splitlines()[-1] == "OK"
        assert f"INFO orders ids=[{no_method}]" in text

    raw = writable(test_db)
    raw.execute("UPDATE orders SET paid_date = NULL WHERE id = ?", (shop["card_order"],))  # has a method: still a failure
    raw.close()
    results = run(test_db)
    assert any(f"orders id={shop['card_order']} field=paid_date" in line for line in fails(results, "c"))
    assert f"orders ids=[{no_method}]" in [i for i in results["c"].infos if "legacy" in i][0]


def test_a_line_price_that_is_not_a_multiple_of_its_quantity_is_named(shop, test_db):
    raw = writable(test_db)
    item_id = raw.execute("SELECT id FROM order_items WHERE order_id = ?", (shop["digi_a"],)).fetchone()[0]
    raw.execute("UPDATE order_items SET list_price = list_price + 1 WHERE id = ?", (item_id,))
    raw.close()
    assert any(f"order_items id={item_id} field=list_price" in line for line in fails(run(test_db), "c"))


def test_a_negative_fee_is_a_failure_but_a_fee_off_the_rule_is_only_a_warning(shop, test_db, capsys):
    raw = writable(test_db)
    raw.execute("UPDATE orders SET transaction_fee = -1 WHERE id = ?", (shop["pending_order"],))
    raw.close()
    assert any(f"orders id={shop['pending_order']} field=transaction_fee stored=-1" in line for line in fails(run(test_db), "c"))

    raw = writable(test_db)
    raw.execute("UPDATE orders SET transaction_fee = 123 WHERE id = ?", (shop["pending_order"],))
    raw.close()
    results = run(test_db)
    assert results["c"].status == "WARN" and not results["c"].fails
    (warn,) = results["c"].warns
    assert f"orders id={shop['pending_order']} field=transaction_fee stored=123" in warn.render()
    code, text = cli_run(test_db, capsys)
    assert code == 0 and text.strip().splitlines()[-1] == "OK"  # a warning never changes the exit code


def test_a_fee_larger_than_the_order_total_is_a_warning(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE orders SET transaction_fee = 999999999 WHERE id = ?", (shop["pending_order"],))
    raw.close()
    results = run(test_db)
    assert not results["c"].fails
    assert any("fee larger than the order total" in row.render() for row in results["c"].warns)


# ----------------------------------------------------------------------- d. stock


def test_a_product_stock_that_does_not_match_its_history_is_named(shop, test_db):
    raw = writable(test_db)
    stored = raw.execute("SELECT current_stock FROM products WHERE id = ?", (shop["product"],)).fetchone()[0]
    raw.execute("UPDATE products SET current_stock = current_stock + 1 WHERE id = ?", (shop["product"],))
    raw.close()
    (line,) = fails(run(test_db), "d1")
    assert f"products id={shop['product']} field=current_stock stored={stored + 1} expected={stored}" in line and "diff=1" in line


def test_a_deleted_movement_is_found_through_the_stock_it_leaves_behind(shop, test_db):
    raw = writable(test_db)
    movement = raw.execute("SELECT id FROM stock_movements WHERE item_type = 'PRODUCT' AND reason = 'SALE' ORDER BY id LIMIT 1").fetchone()[0]
    raw.execute("DELETE FROM stock_movements WHERE id = ?", (movement,))
    raw.close()
    results = run(test_db)
    assert any(f"products id={shop['product']} field=current_stock" in line for line in fails(results, "d1"))


def test_a_material_created_with_stock_is_reported_as_info_and_its_audit_opening_is_checked(shop, test_db):
    results = run(test_db)
    assert not results["d1"].fails
    raw = writable(test_db)
    raw.execute("UPDATE materials SET current_stock = current_stock + 5 WHERE id = ?", (shop["box"],))
    raw.close()
    (line,) = fails(run(test_db), "d1")  # the audit log says it was created with 100
    assert f"materials id={shop['box']} field=current_stock" in line and "created with 100" in line


def forget_audit(conn):
    """As on a database older than migration 012 (or after the go-live reset): no audit INSERT rows for materials."""
    raw = writable(conn)
    raw.execute("DROP TRIGGER trg_audit_log_no_delete")
    raw.execute("DELETE FROM audit_log WHERE entity_type = 'materials'")
    raw.close()


def test_without_an_audit_row_the_opening_balance_is_information(shop, test_db):
    forget_audit(test_db)
    results = run(test_db)
    assert results["d1"].status == "PASS"
    infos = results["d1"].infos
    assert len(infos) == 2 and all("implied opening balance" in i and "not in the ledger" in i for i in infos)
    assert any(f"materials id={shop['box']}: implied opening balance 100" in i for i in infos)


def test_an_impossible_opening_balance_fails(shop, test_db):
    forget_audit(test_db)
    raw = writable(test_db)
    raw.execute("UPDATE materials SET current_stock = 0.2 WHERE id = ?", (shop["ink"],))  # its history adds 1.35: it would have started below 0
    raw.close()
    lines = fails(run(test_db), "d1")
    assert any(f"materials id={shop['ink']} field=implied_opening_balance" in line for line in lines)


def test_a_running_balance_that_goes_below_zero_names_the_movement(shop, test_db):
    forget_audit(test_db)
    raw = writable(test_db)
    # Same total, different order: a big consumption before the adjustment that pays for it.
    consumption = raw.execute("SELECT id FROM stock_movements WHERE reason = 'PRODUCTION_CONSUMPTION' AND item_id = ? AND item_type = 'MATERIAL'", (shop["ink"],)).fetchone()[0]
    raw.execute("UPDATE stock_movements SET quantity_change = -100 WHERE id = ?", (consumption,))
    raw.execute("UPDATE stock_movements SET quantity_change = quantity_change + 98.75 WHERE reason = 'ADJUSTMENT' AND item_id = ? AND item_type = 'MATERIAL'", (shop["ink"],))
    raw.close()
    lines = fails(run(test_db), "d1")
    assert any(f"stock_movements id={consumption} field=running_balance" in line for line in lines), lines


def test_float_noise_is_inside_the_tolerance_and_a_real_difference_is_not(shop, test_db):
    # With the audit opening known, current_stock must equal opening + movements within the tolerance.
    raw = writable(test_db)
    raw.execute("UPDATE materials SET current_stock = current_stock + 1e-9 WHERE id = ?", (shop["ink"],))
    raw.close()
    assert not fails(run(test_db), "d1")
    raw = writable(test_db)
    raw.execute("UPDATE materials SET current_stock = current_stock + 1e-3 WHERE id = ?", (shop["ink"],))
    raw.close()
    (line,) = fails(run(test_db), "d1")
    assert f"materials id={shop['ink']} field=current_stock" in line


def test_a_purchase_without_its_movement_is_named(shop, test_db):
    raw = writable(test_db)
    movement = raw.execute("SELECT id FROM stock_movements WHERE item_type = 'MATERIAL' AND item_id = ? AND reason = 'PURCHASE'", (shop["box"],)).fetchone()[0]
    raw.execute("DELETE FROM stock_movements WHERE id = ?", (movement,))
    raw.close()
    lines = fails(run(test_db), "d2")
    assert any("field=sum PURCHASE quantity" in line and f"material id {shop['box']}" in line for line in lines)


def test_a_production_batch_whose_movements_do_not_match_is_named(shop, test_db):
    raw = writable(test_db)
    raw.execute("DELETE FROM stock_movements WHERE reason = 'PRODUCTION_OUTPUT' AND reference_production_batch_id = ?", (shop["batch"],))
    raw.close()
    lines = fails(run(test_db), "d2")
    assert any(f"production_batches id={shop['batch']} field=quantity_produced vs PRODUCTION_OUTPUT" in line for line in lines)

    raw = writable(test_db)
    raw.execute("UPDATE stock_movements SET quantity_change = quantity_change - 1 WHERE reason = 'PRODUCTION_CONSUMPTION' AND item_id = ?", (shop["box"],))
    raw.close()
    lines = fails(run(test_db), "d2")
    assert any(f"production_batches id={shop['batch']} field=material {shop['box']} consumed" in line for line in lines)


def test_per_order_stock_movements_are_reported_as_skipped(shop, test_db):
    assert run(test_db)["d3"].status == "SKIPPED"


# ----------------------------------------------------------------------- e. costs


def test_a_purchase_unit_cost_that_does_not_match_is_named(shop, test_db):
    raw = writable(test_db)
    stored = raw.execute("SELECT unit_cost FROM material_purchases WHERE material_id = ?", (shop["box"],)).fetchone()[0]
    raw.execute("UPDATE material_purchases SET unit_cost = unit_cost + 1 WHERE material_id = ?", (shop["box"],))
    raw.close()
    (line,) = fails(run(test_db), "e")
    assert f"material_purchases id=" in line and f"field=unit_cost stored={stored + 1} expected={stored} diff=1" in line


def test_a_batch_unit_cost_or_total_cost_that_does_not_match_is_named(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE production_batches SET unit_cost = unit_cost + 1 WHERE id = ?", (shop["batch"],))
    raw.execute("UPDATE production_batch_materials SET unit_cost_at_time = unit_cost_at_time + 10 WHERE production_batch_id = ? "
                "AND material_id = ?", (shop["batch"], shop["box"]))
    raw.close()
    lines = fails(run(test_db), "e")
    assert any(f"production_batches id={shop['batch']} field=unit_cost" in line for line in lines)
    assert any(f"production_batches id={shop['batch']} field=total_cost" in line for line in lines)


# --------------------------------------------------------------- f. invoice numbers


def test_a_counter_that_is_behind_the_highest_number_is_named(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE counters SET value = 2 WHERE name = 'INV'")
    raw.close()
    lines = fails(run(test_db), "f")
    assert any("counters id=\"INV\" field=value stored=2 expected=\">= " in line for line in lines)


def test_a_duplicate_or_malformed_invoice_number_is_named(shop, test_db):
    raw = writable(test_db)
    raw.execute("DROP INDEX idx_orders_invoice_number_unique")
    first = raw.execute("SELECT invoice_number FROM orders WHERE id = ?", (shop["card_order"],)).fetchone()[0]
    raw.execute("UPDATE orders SET invoice_number = ? WHERE id = ?", (first, shop["digi_a"]))
    raw.execute("UPDATE orders SET invoice_number = 'X-1' WHERE id = ?", (shop["digi_b"],))
    raw.close()
    lines = fails(run(test_db), "f")
    assert any(f"orders id={shop['digi_a']} field=invoice_number" in line and "unique" in line for line in lines)
    assert any(f"orders id={shop['digi_b']} field=invoice_number stored=\"X-1\"" in line for line in lines)


def test_a_gap_in_the_numbers_is_only_information(shop, test_db):
    raw = writable(test_db)
    raw.execute("DROP INDEX idx_orders_invoice_number_unique")
    raw.execute("UPDATE orders SET invoice_number = 'INV-000099' WHERE id = ?", (shop["card_order"],))
    raw.execute("UPDATE counters SET value = 99 WHERE name = 'INV'")
    raw.close()
    results = run(test_db)
    assert not results["f"].fails and any("INV numbers below the highest are unused" in i for i in results["f"].infos)


# ----------------------------------------------------------------- g. distributions


def test_a_share_that_does_not_match_the_total_or_the_rule_is_named(shop, test_db):
    raw = writable(test_db)
    share = raw.execute("SELECT id FROM distribution_shares WHERE distribution_id = ? ORDER BY percentage_at_time DESC", (shop["distribution"],)).fetchone()[0]
    raw.execute("UPDATE distribution_shares SET amount = amount + 1 WHERE id = ?", (share,))
    raw.close()
    lines = fails(run(test_db), "g")
    assert any(f"profit_distributions id={shop['distribution']} field=total_amount_distributed" in line and "diff=-1" in line for line in lines)
    assert any(f"distribution_shares id={share} field=amount" in line for line in lines)


def test_overlapping_distribution_periods_are_named(shop, test_db):
    raw = writable(test_db)
    raw.execute("INSERT INTO profit_distributions (period_start, period_end, total_profit_available, total_amount_distributed) "
                "VALUES ('2026-08-15', '2026-09-15', 0, 0)")
    new_id = raw.execute("SELECT MAX(id) FROM profit_distributions").fetchone()[0]
    raw.close()
    (line,) = fails(run(test_db), "g")
    assert f"profit_distributions id={new_id} field=period" in line and f"no overlap with distribution {shop['distribution']}" in line


def test_percentages_that_do_not_sum_to_100_are_information_only(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE distribution_shares SET percentage_at_time = 59.995 WHERE distribution_id = ? AND percentage_at_time = 60", (shop["distribution"],))
    raw.close()
    results = run(test_db)
    assert results["g"].status == "PASS"
    assert any("not exactly 100" in info for info in results["g"].infos)


def test_the_share_calculation_the_check_uses_is_the_one_in_db():
    shares = compute_share_amounts([{"id": 1, "current_percentage": 60}, {"id": 2, "current_percentage": 40}], 100_001)
    assert {s["partner_id"]: s["amount"] for s in shares} == {1: 60_001, 2: 40_000}


# --------------------------------------------------------------- h. name collisions


def test_name_collisions_are_warnings_listed_every_run_and_never_change_the_exit_code(shop, test_db, capsys):
    raw = writable(test_db)
    raw.execute("INSERT INTO suppliers (name) VALUES ('Fictional Supply')")
    raw.execute("INSERT INTO suppliers (name) VALUES ('fictional  supply')")
    raw.close()
    for _ in range(2):
        code, text = cli_run(test_db, capsys)
        assert code == 0 and text.strip().splitlines()[-1] == "OK"
        assert "WARN" in text and "suppliers id=[1, 2] field=name" in text
    results = run(test_db)
    assert results["h"].status == "WARN" and not results["h"].fails


# --------------------------------------------------------- reuse of db/ (no copies)


@pytest.mark.parametrize(
    "target, key, wrong",
    [
        ("tools.integrity_check.checks.compute_fee", "c", lambda *a, **k: 424242),
        ("tools.integrity_check.checks.per_unit_cost", "e", lambda *a, **k: 1),
        ("tools.integrity_check.checks.get_settlement", "b", None),
        ("tools.integrity_check.checks.recipe_batch_total", "e", lambda *a, **k: 7),
        ("tools.integrity_check.checks.compute_expected_settlement_date", "c", lambda paid, method: date(2001, 1, 1)),
        ("tools.integrity_check.checks.compute_share_amounts", "g", lambda partners, total: [
            {"partner_id": p["id"], "percentage_at_time": p["current_percentage"], "amount": 1} for p in partners]),
    ],
)
def test_the_checks_use_the_db_functions_rather_than_a_copy(shop, test_db, monkeypatch, target, key, wrong):
    import importlib

    module_name, name = target.rsplit(".", 1)
    module = importlib.import_module(module_name)
    if wrong is None:
        real = module.get_settlement

        def wrong(conn, settlement_id):
            settlement = real(conn, settlement_id)
            settlement["orders"][0]["expected_amount"] += 1
            return settlement

    monkeypatch.setattr(module, name, wrong)
    results = run(test_db)
    if key == "c" and name == "compute_fee":
        assert results["c"].warns  # the fee comparison is a WARN
    else:
        assert results[key].fails, f"{name} is not used by check {key}"


# ---------------------------------------------------------------- old schemas


def _old_database(tmp_path, last):
    old_dir = tmp_path / f"migrations_to_{last}"
    old_dir.mkdir()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name[:3] <= last:
            shutil.copy(path, old_dir / path.name)
    path = str(tmp_path / f"v{last}.db")
    init_db(path, migrations_dir=old_dir)
    return path


@pytest.mark.parametrize("last, skipped", [("013", {"d3", "i"}), ("011", {"d3", "h", "i"}), ("008", {"b", "c", "d3", "e", "g", "h", "i"}), ("002", {"b", "c", "d1", "d2", "d3", "d4", "e", "f", "g", "h", "i"})])
def test_a_database_at_an_older_schema_skips_what_needs_a_newer_one_and_never_crashes(tmp_path, capsys, last, skipped):
    path = _old_database(tmp_path, last)
    code = cli.main(["--db", path])
    text = capsys.readouterr().out
    assert code == 0, text
    assert f"(version {int(last)})" in text
    for line in text.splitlines():
        for key in ("b", "c", "d1", "d2", "d3", "d4", "e", "f", "g", "h", "i"):
            if line.startswith(("SKIPPED", "PASS", "WARN", "FAIL")) and line.split()[1] == f"{key}.":
                assert line.startswith("SKIPPED") == (key in skipped), line
    assert "needs migration 014" in text
    assert text.strip().splitlines()[-1] == "OK"


def test_a_database_without_migration_013_still_reports_the_real_shape(tmp_path):
    path = _old_database(tmp_path, "011")
    reader = open_readonly(path)
    try:
        number, name = schema_version(reader)
        assert (number, name) == (11, "011_material_min_stock.sql")
        assert not any(row["name"] == "name_key" for row in reader.execute("PRAGMA table_info(suppliers)"))
    finally:
        reader.close()


def test_the_audit_opening_is_read_from_the_json_the_audit_log_holds(shop, test_db):
    row = test_db.execute("SELECT after_json FROM audit_log WHERE entity_type = 'materials' AND entity_id = ? AND action = 'INSERT'", (str(shop["box"]),)).fetchone()
    assert json.loads(row["after_json"])["current_stock"] == 100


# ------------------------------------------------------------------ d4. service waste


def test_a_service_waste_passes_d4_and_leaves_d1_alone(shop, test_db):
    record_service_waste(test_db, shop["print"], 2, movement_date="2026-10-01")
    record_service_waste(test_db, shop["print"], 0.5, unit_cost=333)
    test_db.commit()
    results = run(test_db)
    assert results["d4"].status == "PASS"
    assert results["d4"].summary.endswith("2 service movements checked")
    assert results["d1"].status == "PASS"
    assert all(r.status in ("PASS", "SKIPPED") for r in results.values())


def test_a_service_holding_stock_fails_d4(shop, test_db):
    raw = writable(test_db)
    raw.execute("UPDATE materials SET current_stock = 3 WHERE id = ?", (shop["print"],))
    raw.close()
    lines = fails(run(test_db), "d4")
    assert any(f"materials id={shop['print']} field=current_stock" in line for line in lines)


def test_a_service_adjustment_movement_fails_d4(shop, test_db):
    movement = record_service_waste(test_db, shop["print"], 1)
    test_db.commit()
    raw = writable(test_db)
    raw.execute("UPDATE stock_movements SET reason = 'ADJUSTMENT' WHERE id = ?", (movement,))
    raw.close()
    lines = fails(run(test_db), "d4")
    assert any(f"stock_movements id={movement} field=reason" in line and "ADJUSTMENT" in line for line in lines)


@pytest.mark.parametrize("column, value", [("unit_cost_at_time", "NULL"), ("unit_cost_at_time", "0"), ("quantity_change", "1")])
def test_a_service_waste_without_a_price_or_with_the_wrong_sign_fails_d4(shop, test_db, column, value):
    movement = record_service_waste(test_db, shop["print"], 1)
    test_db.commit()
    raw = writable(test_db)
    raw.execute(f"UPDATE stock_movements SET {column} = {value} WHERE id = ?", (movement,))
    raw.close()
    lines = fails(run(test_db), "d4")
    assert any(f"stock_movements id={movement} field={column}" in line for line in lines)
