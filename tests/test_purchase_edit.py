"""db/purchases.py `update_purchase` (accounting rules section 23): an invoice's supplier, day and note; the payments
wholly on the invoice follow a new supplier, the payment made with the purchase moves with its day, a shared payment
refuses; the lines' PURCHASE movements follow the day; a cancelled invoice is refused."""

import pytest

from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.materials import add_material
from db.purchases import get_purchase, record_purchase, update_purchase
from db.supplier_payments import get_supplier_payment, list_supplier_payments, record_supplier_payment
from db.suppliers import add_supplier


def line(item_id, quantity=10, total=1000, kind="MATERIAL"):
    return {"kind": kind, "item_id": item_id, "quantity_bought": quantity, "total_paid": total}


@pytest.fixture
def shop(test_db):
    ids = {
        "paper": add_material(test_db, "Edit Paper", "STOCK", 0),
        "print": add_material(test_db, "Edit Printing", "SERVICE", 0),
        "acme": add_supplier(test_db, "Edit Acme"),
        "other": add_supplier(test_db, "Edit Other"),
    }
    return test_db, ids


def _movement_dates(conn, purchase_id):
    return [r[0] for r in conn.execute(
        "SELECT m.movement_date FROM material_purchases l JOIN stock_movements m ON m.id = l.stock_movement_id "
        "WHERE l.purchase_invoice_id = ?", (purchase_id,))]


def test_the_note_and_a_new_supplier_on_an_unpaid_purchase(shop):
    conn, ids = shop
    purchase = record_purchase(conn, [line(ids["paper"])], supplier_id=ids["acme"], purchase_date="2026-05-01", payment={"mode": "NONE"})
    update_purchase(conn, purchase, notes="fixed note", supplier_id=ids["other"])
    p = get_purchase(conn, purchase)
    assert (p["notes"], p["supplier_id"], p["outstanding"]) == ("fixed note", ids["other"], 1000)
    with pytest.raises(ValidationError) as exc:  # something is owed: it needs a supplier
        update_purchase(conn, purchase, supplier_id=None)
    assert exc.value.code == ErrorCode.SUPPLIER_REQUIRED_FOR_CREDIT
    with pytest.raises(NotFoundError) as exc:
        update_purchase(conn, purchase, supplier_id=9999)
    assert exc.value.code == ErrorCode.SUPPLIER_NOT_FOUND
    with pytest.raises(ValidationError) as exc:
        update_purchase(conn, purchase, invoice_number="PUR-9")
    assert exc.value.field == "invoice_number"


def test_the_payment_made_with_a_full_purchase_follows_a_new_supplier(shop):
    conn, ids = shop
    purchase = record_purchase(conn, [line(ids["paper"])], supplier_id=ids["acme"], purchase_date="2026-05-01")
    update_purchase(conn, purchase, supplier_id=ids["other"])
    (payment,) = list_supplier_payments(conn)
    assert payment["supplier_id"] == ids["other"]
    assert get_purchase(conn, purchase)["payment_status"] == "PAID"
    update_purchase(conn, purchase, supplier_id=None)  # paid in full: no supplier is allowed, the payment follows
    assert list_supplier_payments(conn)[0]["supplier_id"] is None


def test_a_shared_payment_refuses_a_supplier_change(shop):
    conn, ids = shop
    first = record_purchase(conn, [line(ids["paper"])], supplier_id=ids["acme"], purchase_date="2026-05-01", payment={"mode": "NONE"})
    record_purchase(conn, [line(ids["print"], 2, 500)], supplier_id=ids["acme"], purchase_date="2026-05-01", payment={"mode": "NONE"})
    record_supplier_payment(conn, ids["acme"], "2026-05-02", 1500, "CASH")
    with pytest.raises(ConflictError) as exc:
        update_purchase(conn, first, supplier_id=ids["other"])
    assert exc.value.code == ErrorCode.PURCHASE_HAS_PAYMENTS and exc.value.details["shared"] == 1
    assert get_purchase(conn, first)["supplier_id"] == ids["acme"]


def test_a_new_day_moves_the_movements_and_the_payment_made_with_it(shop):
    conn, ids = shop
    purchase = record_purchase(conn, [line(ids["paper"]), line(ids["print"], 2, 500)], supplier_id=ids["acme"], purchase_date="2026-05-01")
    old = get_purchase(conn, purchase)["purchase_date"]
    update_purchase(conn, purchase, purchase_date="2026-05-04")
    new = get_purchase(conn, purchase)["purchase_date"]
    assert new != old and new.startswith("2026-05-03")  # local midnight of 05-04 in Asia/Tehran is 05-03 20:30 UTC
    assert _movement_dates(conn, purchase) == [new]  # the service line has no movement
    assert list_supplier_payments(conn)[0]["payment_date"] == new
    update_purchase(conn, purchase, purchase_date="2026-05-04")  # the same day keeps the stored moment
    assert get_purchase(conn, purchase)["purchase_date"] == new


def test_a_later_payment_is_rechecked_against_the_new_day(shop):
    conn, ids = shop
    purchase = record_purchase(conn, [line(ids["paper"])], supplier_id=ids["acme"], purchase_date="2026-05-01", payment={"mode": "NONE"})
    payment = record_supplier_payment(conn, ids["acme"], "2026-05-03", 400, "CASH")
    update_purchase(conn, purchase, purchase_date="2026-05-03")  # the payment's own day is fine
    with pytest.raises(ValidationError) as exc:
        update_purchase(conn, purchase, purchase_date="2026-05-05")
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_BEFORE_PURCHASE
    assert get_supplier_payment(conn, payment)["payment_date"].startswith("2026-05-02")  # not moved


def test_a_separate_payment_on_the_purchase_day_stays_and_the_015_backfill_payment_moves(shop):
    conn, ids = shop
    # a backdated purchase and a payment recorded on its own the same day share the moment (local midnight)
    purchase = record_purchase(conn, [line(ids["paper"])], supplier_id=ids["acme"], purchase_date="2026-05-01", payment={"mode": "NONE"})
    separate = record_supplier_payment(conn, ids["acme"], "2026-05-01", 300, "CASH")
    with pytest.raises(ValidationError) as exc:
        update_purchase(conn, purchase, purchase_date="2026-05-02")
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_BEFORE_PURCHASE
    conn.execute("DELETE FROM supplier_payments WHERE id = ?", (separate,))
    # the payment migration 015 backfilled for an old purchase is the one made with it
    date = get_purchase(conn, purchase)["purchase_date"]
    pid = conn.execute(
        "INSERT INTO supplier_payments (supplier_id, payment_date, amount, method, note) VALUES (?, ?, 1000, 'OTHER', ?)",
        (ids["acme"], date, "پیش از ثبت بدهی‌ها"),
    ).lastrowid
    conn.execute("INSERT INTO supplier_payment_allocations (payment_id, purchase_invoice_id, amount) VALUES (?, ?, 1000)", (pid, purchase))
    update_purchase(conn, purchase, purchase_date="2026-05-02")
    assert get_supplier_payment(conn, pid)["payment_date"] == get_purchase(conn, purchase)["purchase_date"]


def test_a_future_day_and_a_bad_day_are_refused(shop):
    conn, ids = shop
    purchase = record_purchase(conn, [line(ids["paper"])], purchase_date="2026-05-01")
    with pytest.raises(ValidationError) as exc:
        update_purchase(conn, purchase, purchase_date="2999-01-01")
    assert exc.value.code == ErrorCode.DATE_IN_FUTURE
    with pytest.raises(ValidationError):
        update_purchase(conn, purchase, purchase_date=5)


def test_an_unknown_or_cancelled_purchase_is_refused(shop):
    conn, ids = shop
    with pytest.raises(NotFoundError) as exc:
        update_purchase(conn, 999, notes="x")
    assert exc.value.code == ErrorCode.PURCHASE_NOT_FOUND
    purchase = record_purchase(conn, [line(ids["paper"])])
    conn.execute("UPDATE purchase_invoices SET status = 'CANCELLED', cancel_reason = 'x', cancelled_at = '2026-05-02 10:00:00' WHERE id = ?", (purchase,))
    with pytest.raises(ConflictError) as exc:
        update_purchase(conn, purchase, notes="y")
    assert exc.value.code == ErrorCode.PURCHASE_ALREADY_CANCELLED
    assert exc.value.details == {"purchase_id": purchase, "cancelled_at": "2026-05-02 10:00:00", "replaced_by_purchase_id": None}


def test_an_edit_is_one_audited_operation(shop):
    conn, ids = shop
    purchase = record_purchase(conn, [line(ids["paper"])], supplier_id=ids["acme"], purchase_date="2026-05-01")
    update_purchase(conn, purchase, supplier_id=ids["other"], purchase_date="2026-05-02", notes="n")
    rows = conn.execute("SELECT entity_type, op_id FROM audit_log WHERE operation = 'update_purchase'").fetchall()
    assert {r["entity_type"] for r in rows} == {"purchase_invoices", "supplier_payments", "stock_movements"}
    assert len({r["op_id"] for r in rows}) == 1
