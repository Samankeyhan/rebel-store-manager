"""Integrity checks j (supplier payables), d2 (services write no movement) and f (PUR numbers per invoice), accounting
rules sections 18, 21 and 22: a clean shop passes, and each broken invariant, written straight into the tables, is a
failure."""

import pytest

from db.materials import add_material
from db.products import add_product
from db.purchases import record_purchase
from db.supplier_payments import get_payables, record_supplier_payment
from db.suppliers import add_supplier
from tests.helpers import cat
from tools.integrity_check.checks import CHECKS, check_invoice_numbers, check_stock_documents, check_supplier_payables


def line(kind, item_id, quantity, total):
    return {"kind": kind, "item_id": item_id, "quantity_bought": quantity, "total_paid": total}


@pytest.fixture
def shop(test_db):
    paper = add_material(test_db, "Fictional Paper", "STOCK", 0)
    printing = add_material(test_db, "Fictional Printing", "SERVICE", 0)
    tee = add_product(test_db, "Fictional Tee", cat(test_db, "TSHIRT"), 3000, 2000)
    acme = add_supplier(test_db, "Acme Paper")
    other = add_supplier(test_db, "Other Supplier")
    first = record_purchase(
        test_db, [line("MATERIAL", paper, 10, 3000), line("MATERIAL", printing, 2, 1000)],
        supplier_id=acme, purchase_date="2026-05-02", payment={"mode": "NONE"},
    )
    second = record_purchase(test_db, [line("MATERIAL", paper, 5, 1000)], supplier_id=other, purchase_date="2026-05-03")
    payment = record_supplier_payment(test_db, acme, "2026-05-04", 1500, "CASH")
    return test_db, {
        "paper": paper, "printing": printing, "tee": tee, "acme": acme, "other": other,
        "first": first, "second": second, "payment": payment,
    }


def _fails(conn, check=check_supplier_payables, schema=16):
    result = check(conn, schema)
    assert result.error is None and result.skipped is None
    return [(row.table, row.field) for row in result.fails]


def test_j_is_registered_for_schema_16():
    (check,) = [c for c in CHECKS if c.key == "j"]
    assert (check.name, check.min_schema) == ("Supplier payables", 16)


def test_a_clean_shop_passes(shop):
    conn, _ = shop
    assert _fails(conn) == []
    assert check_supplier_payables(conn, 16).summary == "2 purchases, 2 payments, 2 allocations, 1 suppliers owed"
    assert _fails(conn, check_stock_documents) == []
    assert _fails(conn, check_invoice_numbers) == []


def test_an_invoice_owes_the_sum_of_its_lines(shop):
    conn, ids = shop
    # 4000 over two lines, 1500 paid: 2500 owed, whichever line it is
    assert get_payables(conn)["outstanding_total"] == 2500
    conn.execute("UPDATE material_purchases SET total_paid = total_paid + 100 WHERE id = 1")
    assert get_payables(conn)["outstanding_total"] == 2600
    assert _fails(conn) == []  # the invoice total follows its lines; the payables follow the invoice


def test_a_payment_not_wholly_allocated_fails(shop):
    conn, ids = shop
    conn.execute("UPDATE supplier_payments SET amount = 1600 WHERE id = ?", (ids["payment"],))
    assert ("supplier_payments", "amount") in _fails(conn)


def test_an_allocation_to_another_suppliers_purchase_fails(shop):
    conn, ids = shop
    conn.execute("UPDATE supplier_payments SET supplier_id = ? WHERE id = ?", (ids["other"], ids["payment"]))
    assert ("supplier_payment_allocations", "supplier_id") in _fails(conn)


def test_a_payment_before_its_purchase_fails(shop):
    conn, ids = shop
    conn.execute("UPDATE supplier_payments SET payment_date = '2026-04-01 08:00:00' WHERE id = ?", (ids["payment"],))
    assert ("supplier_payments", "payment_date") in _fails(conn)


def test_a_purchase_paid_above_its_total_fails(shop):
    conn, ids = shop
    conn.execute("UPDATE supplier_payment_allocations SET amount = 5000 WHERE payment_id = ?", (ids["payment"],))
    conn.execute("UPDATE supplier_payments SET amount = 5000 WHERE id = ?", (ids["payment"],))
    assert ("purchase_invoices", "paid") in _fails(conn)


def test_an_allocation_on_a_cancelled_purchase_fails(shop):
    conn, ids = shop
    conn.execute(
        "UPDATE purchase_invoices SET status = 'CANCELLED', cancelled_at = '2026-05-05 08:00:00', cancel_reason = 'x' WHERE id = ?",
        (ids["first"],),
    )
    assert ("supplier_payment_allocations", "purchase status") in _fails(conn)


def test_a_purchase_without_a_line_fails(shop):
    conn, ids = shop
    conn.execute("INSERT INTO purchase_invoices (invoice_number) VALUES ('PUR-000099')")
    assert ("purchase_invoices", "lines") in _fails(conn)


# ---------------------------------------------------------------- services in d2, PUR numbers in f


def test_a_service_line_with_a_movement_link_fails_d2(shop):
    conn, ids = shop
    conn.execute("INSERT INTO stock_movements (item_type, item_id, quantity_change, reason) VALUES ('MATERIAL', ?, 2, 'PURCHASE')", (ids["printing"],))
    movement = conn.execute("SELECT MAX(id) FROM stock_movements").fetchone()[0]
    conn.execute(
        "UPDATE material_purchases SET stock_movement_id = ? WHERE material_id = ?", (movement, ids["printing"])
    )
    assert ("material_purchases", "stock_movement_id") in _fails(conn, check_stock_documents)


def test_a_service_purchase_is_left_out_of_the_stock_sums(shop):
    conn, ids = shop
    # the service's 2 units are bought but there is no movement: d2 compares only the stock material
    assert conn.execute("SELECT SUM(quantity_bought) FROM material_purchases WHERE material_id = ?", (ids["printing"],)).fetchone()[0] == 2
    assert _fails(conn, check_stock_documents) == []
    # a stock material's movement that differs from its lines still fails
    conn.execute(
        "UPDATE stock_movements SET quantity_change = quantity_change + 1 WHERE item_type = 'MATERIAL' AND item_id = ? AND reason = 'PURCHASE'",
        (ids["paper"],),
    )
    assert ("stock_movements", "sum PURCHASE quantity") in _fails(conn, check_stock_documents)


def test_a_malformed_pur_number_fails_f(shop):
    conn, ids = shop
    # the unique index refuses a hand-made duplicate, so a malformed number is what the check can still find
    conn.execute("UPDATE purchase_invoices SET invoice_number = 'X-1' WHERE id = ?", (ids["second"],))
    assert ("purchase_invoices", "invoice_number") in _fails(conn, check_invoice_numbers)
