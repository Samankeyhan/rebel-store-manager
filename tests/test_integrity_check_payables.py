"""Integrity check j (supplier payables, accounting rules section 18): a clean shop passes, and each broken invariant,
written straight into the tables, is a failure."""

import pytest

from db.materials import add_material
from db.purchases import record_material_purchase
from db.supplier_payments import record_supplier_payment
from db.suppliers import add_supplier
from tools.integrity_check.checks import CHECKS, check_supplier_payables


@pytest.fixture
def shop(test_db):
    paper = add_material(test_db, "Fictional Paper", "STOCK", 0)
    acme = add_supplier(test_db, "Acme Paper")
    other = add_supplier(test_db, "Other Supplier")
    first = record_material_purchase(test_db, paper, 10, 4000, supplier_id=acme, purchase_date="2026-05-02",
                                     payment={"mode": "NONE"})
    second = record_material_purchase(test_db, paper, 5, 1000, supplier_id=other, purchase_date="2026-05-03")
    payment = record_supplier_payment(test_db, acme, "2026-05-04", 1500, "CASH")
    return test_db, {"paper": paper, "acme": acme, "other": other, "first": first, "second": second, "payment": payment}


def _fails(conn):
    result = check_supplier_payables(conn, 15)
    assert result.error is None and result.skipped is None
    return [(row.table, row.field) for row in result.fails]


def test_j_is_registered_for_schema_15():
    (check,) = [c for c in CHECKS if c.key == "j"]
    assert (check.name, check.min_schema) == ("Supplier payables", 15)


def test_a_clean_shop_passes(shop):
    conn, _ = shop
    assert _fails(conn) == []
    assert check_supplier_payables(conn, 15).summary == "2 payments, 2 allocations, 1 suppliers owed"


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
    assert ("material_purchases", "paid") in _fails(conn)


def test_an_allocation_on_a_cancelled_purchase_fails(shop):
    conn, ids = shop
    conn.execute(
        "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason) VALUES ('MATERIAL', ?, -10, 'PURCHASE')",
        (ids["paper"],),
    )
    movement = conn.execute("SELECT MAX(id) FROM stock_movements").fetchone()[0]
    conn.execute(
        "UPDATE material_purchases SET status = 'CANCELLED', cancelled_at = '2026-05-05 08:00:00', cancel_reason = 'x', "
        "cancel_movement_id = ? WHERE id = ?",
        (movement, ids["first"]),
    )
    assert ("supplier_payment_allocations", "purchase status") in _fails(conn)
