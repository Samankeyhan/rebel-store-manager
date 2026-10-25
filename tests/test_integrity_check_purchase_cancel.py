"""Integrity checks d2 (PURCHASE movements vs the lines of ACTIVE invoices) and k (cancelled and corrected purchases),
accounting rules sections 18 and 23: a shop with a cancel and a correction passes, and each broken invariant, written
straight into the tables, is a failure."""

import pytest

from db.materials import add_material
from db.products import add_product
from db.purchase_cancel import cancel_purchase, correct_purchase
from db.purchases import record_purchase
from db.suppliers import add_supplier
from tests.helpers import cat
from tools.integrity_check.checks import CHECKS, check_cancelled_purchases, check_stock_documents

DAY = "2026-10-10"


def line(item_id, quantity=10, total=1000, kind="MATERIAL"):
    return {"kind": kind, "item_id": item_id, "quantity_bought": quantity, "total_paid": total}


@pytest.fixture
def shop(test_db):
    paper = add_material(test_db, "K Paper", "STOCK", 0)
    printing = add_material(test_db, "K Printing", "SERVICE", 10)
    tee = add_product(test_db, "K Tee", cat(test_db, "TSHIRT"), 3000, 2000)
    acme = add_supplier(test_db, "K Acme")
    gone = record_purchase(test_db, [line(paper), line(printing, 2, 400), line(tee, 3, 900, "PRODUCT")], supplier_id=acme,
                           purchase_date=DAY, payment={"mode": "NONE"})
    cancel_purchase(test_db, gone, "entered twice")
    fixed = record_purchase(test_db, [line(paper, 5, 500)], supplier_id=acme, purchase_date=DAY)
    new = correct_purchase(test_db, fixed, "wrong count", [line(paper, 6, 600)], supplier_id=acme, purchase_date=DAY)
    return test_db, {"paper": paper, "printing": printing, "tee": tee, "acme": acme, "gone": gone, "fixed": fixed, "new": new}


def _fails(conn, check=check_cancelled_purchases):
    result = check(conn, 16)
    assert result.error is None and result.skipped is None
    return [(row.table, row.field) for row in result.fails]


def test_k_is_registered_for_schema_16():
    (check,) = [c for c in CHECKS if c.key == "k"]
    assert (check.name, check.min_schema) == ("Cancelled and corrected purchases", 16)


def test_a_cancel_and_a_correction_pass_d2_and_k(shop):
    conn, _ = shop
    assert _fails(conn) == [] and _fails(conn, check_stock_documents) == []
    assert check_cancelled_purchases(conn, 16).summary == "2 cancelled purchases, 1 corrections checked"


def test_d2_fails_when_a_cancelled_line_lost_its_cancel_movement(shop):
    conn, ids = shop
    movement = conn.execute("SELECT cancel_movement_id FROM product_purchases WHERE purchase_invoice_id = ?", (ids["gone"],)).fetchone()[0]
    conn.execute("UPDATE product_purchases SET cancel_movement_id = NULL WHERE purchase_invoice_id = ?", (ids["gone"],))
    conn.execute("DELETE FROM stock_movements WHERE id = ?", (movement,))
    assert ("stock_movements", "sum PURCHASE quantity") in _fails(conn, check_stock_documents)
    assert ("product_purchases", "cancel_movement_id") in _fails(conn)


def test_a_cancel_movement_that_does_not_net_to_zero(shop):
    conn, ids = shop
    conn.execute(
        "UPDATE stock_movements SET quantity_change = -9 WHERE id = (SELECT cancel_movement_id FROM material_purchases "
        "WHERE purchase_invoice_id = ? AND material_id = ?)",
        (ids["gone"], ids["paper"]),
    )
    assert ("material_purchases", "movements") in _fails(conn)


def test_an_allocation_on_a_cancelled_invoice(shop):
    conn, ids = shop
    conn.execute("INSERT INTO supplier_payments (supplier_id, payment_date, amount, method) VALUES (?, '2026-10-10 08:00:00', 100, 'CASH')", (ids["acme"],))
    payment = conn.execute("SELECT MAX(id) FROM supplier_payments").fetchone()[0]
    conn.execute("INSERT INTO supplier_payment_allocations (payment_id, purchase_invoice_id, amount) VALUES (?, ?, 100)", (payment, ids["gone"]))
    assert ("purchase_invoices", "paid") in _fails(conn)


def test_a_service_line_with_a_movement_and_an_active_line_with_a_cancel_movement(shop):
    conn, ids = shop
    movement = conn.execute(
        "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason) VALUES ('MATERIAL', ?, 2, 'PURCHASE')",
        (ids["printing"],),
    ).lastrowid
    conn.execute("UPDATE material_purchases SET stock_movement_id = ? WHERE material_id = ?", (movement, ids["printing"]))
    conn.execute("UPDATE material_purchases SET cancel_movement_id = stock_movement_id WHERE purchase_invoice_id = ?", (ids["new"],))
    fails = _fails(conn)
    assert ("material_purchases", "cancel_movement_id") in fails
    assert sum(1 for f in fails if f == ("material_purchases", "cancel_movement_id")) == 2


def test_a_replacement_of_an_active_invoice(shop):
    conn, ids = shop
    conn.execute("UPDATE purchase_invoices SET replaces_invoice_id = ? WHERE id = ?", (ids["new"], ids["gone"]))
    assert ("purchase_invoices", "replaces_invoice_id") in _fails(conn)


def test_a_line_recorded_with_its_history_that_lost_it_fails_and_an_old_line_is_info(shop):
    conn, ids = shop
    conn.execute("UPDATE material_purchases SET item_cost_after = NULL, item_cost_before = NULL WHERE purchase_invoice_id = ?", (ids["new"],))
    assert ("material_purchases", "item_cost_after") in _fails(conn)
    conn.execute("UPDATE material_purchases SET item_cost_after = 100 WHERE purchase_invoice_id = ?", (ids["new"],))
    # a line written before the cost history existed: no audit INSERT with item_cost_after
    conn.execute("INSERT INTO purchase_invoices (invoice_number, purchase_date) VALUES ('PUR-000099', '2026-10-01 08:00:00')")
    invoice = conn.execute("SELECT MAX(id) FROM purchase_invoices").fetchone()[0]
    conn.execute(
        "INSERT INTO product_purchases (purchase_invoice_id, product_id, quantity_bought, total_paid, unit_cost) VALUES (?, ?, 1, 0, 0)",
        (invoice, ids["tee"]),
    )
    result = check_cancelled_purchases(conn, 16)
    assert result.fails == []
    assert result.infos == ["1 purchase lines were recorded before their cost history was kept: they cannot be cancelled"]
