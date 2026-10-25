"""Correcting a purchase invoice (db/purchase_cancel.py `correct_purchase`, accounting rules section 23): one operation
that cancels the invoice and records the right one; the allocations move, the payment chosen on the form is on the
remainder, a new supplier takes the payments wholly on the invoice, and any refusal leaves both as they were."""

import pytest

from db.distributions import record_profit_distribution
from db.errors import ConflictError, ErrorCode, ValidationError
from db.materials import add_material, get_material
from db.partners import add_partner
from db.products import add_product, get_product
from db.purchase_cancel import cancel_purchase, correct_purchase
from db.purchases import get_purchase, list_purchases, record_purchase
from db.supplier_payments import get_payables, list_supplier_payments, record_supplier_payment
from db.suppliers import add_supplier
from tests.helpers import cat

DAY = "2026-10-10"


def line(item_id, quantity=10, total=1000, kind="MATERIAL"):
    return {"kind": kind, "item_id": item_id, "quantity_bought": quantity, "total_paid": total}


@pytest.fixture
def shop(test_db):
    ids = {
        "paper": add_material(test_db, "Fix Paper", "STOCK", 0),
        "ink": add_material(test_db, "Fix Ink", "STOCK", 0),
        "print": add_material(test_db, "Fix Printing", "SERVICE", 70),
        "tee": add_product(test_db, "Fix Tee", cat(test_db, "TSHIRT"), 3000, 2000),
        "acme": add_supplier(test_db, "Fix Acme"),
        "other": add_supplier(test_db, "Fix Other"),
    }
    return test_db, ids


def test_a_corrected_quantity_and_price_on_the_same_item(shop):
    conn, ids = shop
    old = record_purchase(conn, [line(ids["paper"], 10, 1000)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    new = correct_purchase(conn, old, "typed 10 for 12", [line(ids["paper"], 12, 1800)], supplier_id=ids["acme"], purchase_date=DAY,
                           payment={"mode": "NONE"})
    assert get_material(conn, ids["paper"])["current_stock"] == 12 and get_material(conn, ids["paper"])["unit_cost"] == 150
    old_p, new_p = get_purchase(conn, old), get_purchase(conn, new)
    assert (old_p["status"], old_p["replaced_by_invoice_id"]) == ("CANCELLED", new)
    assert (new_p["status"], new_p["replaces_invoice_id"], new_p["total"]) == ("ACTIVE", old, 1800)
    assert new_p["invoice_number"] != old_p["invoice_number"]
    ops = {r[0] for r in conn.execute("SELECT op_id FROM audit_log WHERE operation = 'correct_purchase'")}
    assert len(ops) == 1


def test_lines_added_removed_and_another_kind(shop):
    conn, ids = shop
    old = record_purchase(conn, [line(ids["paper"]), line(ids["print"], 2, 400)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    new = correct_purchase(conn, old, "x", [line(ids["ink"], 5, 500), line(ids["tee"], 2, 600, "PRODUCT")],
                           supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    assert get_material(conn, ids["paper"])["current_stock"] == 0
    assert get_material(conn, ids["print"])["unit_cost"] == 70  # the service price is restored
    assert (get_material(conn, ids["ink"])["current_stock"], get_product(conn, ids["tee"])["current_stock"]) == (5, 2)
    assert [l["item_type"] for l in get_purchase(conn, new)["lines"]] == ["STOCK", "PRODUCT"]


def test_the_allocations_move_and_the_form_payment_is_on_the_remainder(shop):
    conn, ids = shop
    old = record_purchase(conn, [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date=DAY,
                          payment={"mode": "PARTIAL", "amount": 1000})
    record_supplier_payment(conn, ids["acme"], DAY, 500, "CASH")
    payments_before = list_supplier_payments(conn)
    new = correct_purchase(conn, old, "x", [line(ids["paper"], 10, 5000)], supplier_id=ids["acme"], purchase_date=DAY)  # FULL
    p = get_purchase(conn, new)
    assert (p["total"], p["paid"], p["payment_status"]) == (5000, 5000, "PAID")
    assert [x["amount"] for x in p["payments"]] == [1000, 500, 3500]  # the old payments unchanged, the remainder paid now
    assert {x["id"]: x["amount"] for x in list_supplier_payments(conn) if x["id"] in {y["id"] for y in payments_before}} == {
        y["id"]: y["amount"] for y in payments_before}
    assert get_purchase(conn, old)["paid"] == 0


@pytest.mark.parametrize("payment, paid, status", [
    ({"mode": "NONE"}, 1500, "PARTIAL"),
    ({"mode": "PARTIAL", "amount": 2000}, 3500, "PARTIAL"),
])
def test_on_credit_or_partly_on_the_remainder(shop, payment, paid, status):
    conn, ids = shop
    old = record_purchase(conn, [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date=DAY,
                          payment={"mode": "PARTIAL", "amount": 1500})
    new = correct_purchase(conn, old, "x", [line(ids["paper"], 10, 5000)], supplier_id=ids["acme"], purchase_date=DAY, payment=payment)
    p = get_purchase(conn, new)
    assert (p["paid"], p["payment_status"]) == (paid, status)
    with pytest.raises(ValidationError) as exc:  # a partial payment must be below the remainder (3500 left after 1500)
        correct_purchase(conn, new, "x", [line(ids["paper"], 10, 5000)], supplier_id=ids["acme"], purchase_date=DAY,
                         payment={"mode": "PARTIAL", "amount": 5000 - paid})
    assert exc.value.field == "payment.amount"


def test_below_what_was_paid_is_refused_and_both_stay(shop):
    conn, ids = shop
    old = record_purchase(conn, [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date=DAY)
    with pytest.raises(ValidationError) as exc:
        correct_purchase(conn, old, "x", [line(ids["paper"], 10, 3000)], supplier_id=ids["acme"], purchase_date=DAY)
    assert exc.value.code == ErrorCode.PURCHASE_CORRECTION_BELOW_PAID
    assert exc.value.details == {"purchase_id": old, "paid": 4000, "new_total": 3000}
    assert get_purchase(conn, old)["status"] == "ACTIVE"
    assert get_material(conn, ids["paper"])["current_stock"] == 10
    assert len(list_purchases(conn, include_cancelled=True)) == 1


def test_a_new_supplier_takes_the_payments_wholly_on_the_invoice(shop):
    conn, ids = shop
    old = record_purchase(conn, [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date=DAY)
    new = correct_purchase(conn, old, "wrong supplier", [line(ids["paper"], 10, 4000)], supplier_id=ids["other"], purchase_date=DAY)
    (payment,) = list_supplier_payments(conn)
    assert payment["supplier_id"] == ids["other"] and get_purchase(conn, new)["payment_status"] == "PAID"
    assert get_payables(conn)["outstanding_total"] == 0


def test_a_shared_payment_refuses_a_new_supplier(shop):
    conn, ids = shop
    old = record_purchase(conn, [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    record_purchase(conn, [line(ids["ink"], 1, 100)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    record_supplier_payment(conn, ids["acme"], DAY, 4100, "CASH")
    with pytest.raises(ConflictError) as exc:
        correct_purchase(conn, old, "x", [line(ids["paper"], 10, 4000)], supplier_id=ids["other"], purchase_date=DAY)
    assert exc.value.code == ErrorCode.PURCHASE_HAS_PAYMENTS and exc.value.details["shared"] == 1
    # the same supplier is fine: the shared payment's allocation moves to the new invoice
    new = correct_purchase(conn, old, "x", [line(ids["paper"], 10, 4100)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    assert get_purchase(conn, new)["paid"] == 4000


def test_a_new_day_moves_the_payment_made_with_it_and_rechecks_the_others(shop):
    conn, ids = shop
    old = record_purchase(conn, [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date="2026-10-01",
                          payment={"mode": "PARTIAL", "amount": 1000})
    record_supplier_payment(conn, ids["acme"], "2026-10-02", 500, "CASH")
    with pytest.raises(ValidationError) as exc:  # the separate payment would be before the new day
        correct_purchase(conn, old, "x", [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date="2026-10-03", payment={"mode": "NONE"})
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_BEFORE_PURCHASE
    new = correct_purchase(conn, old, "x", [line(ids["paper"], 10, 4000)], supplier_id=ids["acme"], purchase_date="2026-10-02", payment={"mode": "NONE"})
    p = get_purchase(conn, new)
    assert [x["payment_date"] for x in p["payments"]] == [p["purchase_date"], p["purchase_date"]]  # the one made with it moved


def test_a_closed_old_or_new_day_is_refused(shop):
    conn, ids = shop
    closed = record_purchase(conn, [line(ids["paper"])], supplier_id=ids["acme"], purchase_date="2026-10-05", payment={"mode": "NONE"})
    open_ = record_purchase(conn, [line(ids["ink"])], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    add_partner(conn, "Solo", 100.0)
    record_profit_distribution(conn, "2026-10-01", "2026-10-05", 0, allow_exceeding=True)
    with pytest.raises(ConflictError) as exc:
        correct_purchase(conn, closed, "x", [line(ids["paper"])], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    assert exc.value.code == ErrorCode.PERIOD_ALREADY_DISTRIBUTED
    with pytest.raises(ConflictError) as exc:
        correct_purchase(conn, open_, "x", [line(ids["ink"])], supplier_id=ids["acme"], purchase_date="2026-10-04", payment={"mode": "NONE"})
    assert exc.value.code == ErrorCode.PERIOD_ALREADY_DISTRIBUTED
    assert get_purchase(conn, open_)["status"] == "ACTIVE" and get_material(conn, ids["ink"])["current_stock"] == 10


def test_a_chain_of_corrections_and_a_cancelled_one_cannot_be_corrected(shop):
    conn, ids = shop
    first = record_purchase(conn, [line(ids["paper"])], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    second = correct_purchase(conn, first, "x", [line(ids["paper"], 9, 900)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    third = correct_purchase(conn, second, "y", [line(ids["paper"], 8, 800)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    assert get_purchase(conn, third)["replaces_invoice_id"] == second and get_purchase(conn, second)["replaces_invoice_id"] == first
    assert get_material(conn, ids["paper"])["current_stock"] == 8
    with pytest.raises(ConflictError) as exc:
        correct_purchase(conn, first, "z", [line(ids["paper"])], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    assert exc.value.code == ErrorCode.PURCHASE_ALREADY_CANCELLED and exc.value.details["replaced_by_purchase_id"] == second
    cancel_purchase(conn, third, "gone")
    assert get_material(conn, ids["paper"])["current_stock"] == 0


def test_a_bad_new_line_leaves_both_as_they_were(shop):
    conn, ids = shop
    old = record_purchase(conn, [line(ids["paper"])], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    movements = conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]
    with pytest.raises(ValidationError) as exc:
        correct_purchase(conn, old, "x", [line(ids["print"], 1, 0)], supplier_id=ids["acme"], purchase_date=DAY, payment={"mode": "NONE"})
    assert exc.value.code == ErrorCode.SERVICE_PURCHASE_NEEDS_TOTAL
    assert get_purchase(conn, old)["status"] == "ACTIVE"
    assert conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0] == movements
    assert get_material(conn, ids["paper"])["current_stock"] == 10
    with pytest.raises(ValidationError) as exc:
        correct_purchase(conn, old, " ", [line(ids["paper"])], supplier_id=ids["acme"], purchase_date=DAY)
    assert exc.value.code == ErrorCode.VOID_REASON_REQUIRED
