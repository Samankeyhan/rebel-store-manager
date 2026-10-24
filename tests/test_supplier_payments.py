"""db/supplier_payments.py and the payment terms of a purchase (accounting rules section 21): paid / outstanding /
status are derived; a payment is wholly allocated (given, or oldest first), never more than is owed, only to that
supplier's purchases and never before them; edit changes date / method / reference / note only; delete cascades."""

import json
import sqlite3

import pytest

from db.constants import MAX_MONEY
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.materials import add_material
from db.products import add_product
from db.purchases import get_material_purchase, get_product_purchase, list_material_purchases, record_material_purchase, record_product_purchase
from db.reports import get_profit_and_loss
from db.supplier_payments import (
    allocate_oldest_first,
    delete_supplier_payment,
    get_payables,
    get_supplier_payment,
    list_supplier_payments,
    open_purchases,
    payables_outstanding,
    payment_status,
    record_supplier_payment,
    update_supplier_payment,
)
from db.suppliers import add_supplier
from tests.helpers import cat


@pytest.fixture
def shop(test_db):
    ids = {
        "paper": add_material(test_db, "Fictional Paper", "STOCK", 0),
        "ink": add_material(test_db, "Fictional Ink", "STOCK", 0),
        "tee": add_product(test_db, "Fictional Tee", cat(test_db, "TSHIRT"), 3000, 2000),
        "acme": add_supplier(test_db, "Acme Paper"),
        "other": add_supplier(test_db, "Other Supplier"),
    }
    return test_db, ids


def credit(conn, ids, total, date="2026-05-01", item="paper", supplier="acme", mode="NONE", **payment):
    """A material purchase of 10 units for `total`, on credit unless `mode` says otherwise."""
    return record_material_purchase(
        conn, ids[item], 10, total, supplier_id=ids[supplier], purchase_date=date,
        payment={"mode": mode, **payment},
    )


def _paid(conn, purchase_id):
    p = get_material_purchase(conn, purchase_id)
    return p["paid"], p["outstanding"], p["payment_status"]


# ---------------------------------------------------------------- purchase payment terms


def test_a_purchase_is_paid_in_full_by_default_with_one_payment_in_the_same_operation(shop):
    conn, ids = shop
    purchase_id = record_material_purchase(conn, ids["paper"], 4, 8000, supplier_id=ids["acme"], purchase_date="2026-05-02")
    assert _paid(conn, purchase_id) == (8000, 0, "PAID")
    (payment,) = list_supplier_payments(conn)
    assert (payment["amount"], payment["method"], payment["supplier_id"]) == (8000, "OTHER", ids["acme"])
    assert payment["payment_date"] == get_material_purchase(conn, purchase_id)["purchase_date"]
    ops = {r[0] for r in conn.execute(
        "SELECT op_id FROM audit_log WHERE entity_type IN ('material_purchases', 'supplier_payments', 'supplier_payment_allocations')"
    )}
    assert len(ops) == 1
    operations = {r[0] for r in conn.execute("SELECT operation FROM audit_log WHERE entity_type = 'supplier_payments'")}
    assert operations == {"record_material_purchase"}


def test_full_payment_without_a_supplier_is_allowed(shop):
    conn, ids = shop
    purchase_id = record_material_purchase(conn, ids["paper"], 1, 500, payment={"mode": "FULL", "method": "CASH", "reference": "R1"})
    payment = list_supplier_payments(conn)[0]
    assert payment["supplier_id"] is None and payment["method"] == "CASH" and payment["reference"] == "R1"
    assert _paid(conn, purchase_id) == (500, 0, "PAID")


def test_on_credit_and_partial(shop):
    conn, ids = shop
    unpaid = credit(conn, ids, 10000)
    partial = credit(conn, ids, 6000, mode="PARTIAL", amount=2500, method="CARD")
    assert _paid(conn, unpaid) == (0, 10000, "UNPAID")
    assert _paid(conn, partial) == (2500, 3500, "PARTIAL")
    assert get_material_purchase(conn, partial)["payments"][0]["method"] == "CARD"


@pytest.mark.parametrize("mode", ["NONE", "PARTIAL"])
def test_credit_needs_a_supplier(shop, mode):
    conn, ids = shop
    with pytest.raises(ValidationError) as exc:
        record_material_purchase(conn, ids["paper"], 1, 500, payment={"mode": mode, "amount": 100 if mode == "PARTIAL" else None})
    assert exc.value.code == ErrorCode.SUPPLIER_REQUIRED_FOR_CREDIT and exc.value.field == "supplier_id"
    assert exc.value.details == {}
    assert conn.execute("SELECT COUNT(*) FROM material_purchases").fetchone()[0] == 0


@pytest.mark.parametrize("payment, field", [
    ({"mode": "PARTIAL", "amount": 500}, "payment.amount"),  # the whole total is FULL
    ({"mode": "PARTIAL", "amount": 0}, "payment.amount"),
    ({"mode": "PARTIAL"}, "payment.amount"),
    ({"mode": "FULL", "amount": 100}, "payment.amount"),
    ({"mode": "SOON"}, "payment.mode"),
    ({"mode": "FULL", "method": "BITCOIN"}, "payment.method"),
])
def test_bad_purchase_payments_write_nothing(shop, payment, field):
    conn, ids = shop
    with pytest.raises(ValidationError) as exc:
        record_material_purchase(conn, ids["paper"], 1, 500, supplier_id=ids["acme"], payment=payment)
    assert exc.value.field == field
    assert conn.execute("SELECT COUNT(*) FROM material_purchases").fetchone()[0] == 0


def test_a_purchase_of_total_0_is_paid_and_has_no_payment(shop):
    conn, ids = shop
    purchase_id = credit(conn, ids, 0, mode="FULL")
    assert _paid(conn, purchase_id) == (0, 0, "PAID")
    assert list_supplier_payments(conn) == []
    assert payment_status(0, 0) == "PAID"


def test_a_product_purchase_on_credit(shop):
    conn, ids = shop
    purchase_id = record_product_purchase(conn, ids["tee"], 3, 900, supplier_id=ids["acme"], payment={"mode": "NONE"})
    p = get_product_purchase(conn, purchase_id)
    assert (p["paid"], p["outstanding"], p["payment_status"], p["payments"]) == (0, 900, "UNPAID", [])


def test_the_purchase_stores_its_movement_and_the_cost_snapshot(shop):
    conn, ids = shop
    first = credit(conn, ids, 1000)
    second = credit(conn, ids, 3000)
    rows = {r["id"]: r for r in conn.execute("SELECT * FROM material_purchases")}
    assert (rows[first]["item_cost_before"], rows[first]["item_cost_after"]) == (0, 100)
    assert (rows[second]["item_cost_before"], rows[second]["item_cost_after"]) == (100, 200)
    movement = conn.execute("SELECT * FROM stock_movements WHERE id = ?", (rows[second]["stock_movement_id"],)).fetchone()
    assert (movement["reason"], movement["quantity_change"], movement["movement_date"]) == ("PURCHASE", 10, rows[second]["purchase_date"])
    product = record_product_purchase(conn, ids["tee"], 2, 600)
    row = conn.execute("SELECT item_cost_before, item_cost_after FROM product_purchases WHERE id = ?", (product,)).fetchone()
    assert tuple(row) == (None, 300)


# ---------------------------------------------------------------- payments


def test_oldest_first_allocation(shop):
    conn, ids = shop
    old = credit(conn, ids, 4000, date="2026-05-01")
    newer = credit(conn, ids, 5000, date="2026-05-03")
    assert allocate_oldest_first(conn, ids["acme"], 6000) == [
        {"purchase_kind": "MATERIAL", "purchase_id": old, "amount": 4000},
        {"purchase_kind": "MATERIAL", "purchase_id": newer, "amount": 2000},
    ]
    payment_id = record_supplier_payment(conn, ids["acme"], "2026-05-04", 6000, "BANK_TRANSFER", reference="T-9")
    assert _paid(conn, old) == (4000, 0, "PAID") and _paid(conn, newer) == (2000, 3000, "PARTIAL")
    payment = get_supplier_payment(conn, payment_id)
    assert [a["amount"] for a in payment["allocations"]] == [4000, 2000]
    assert payment["supplier_name"] == "Acme Paper"


def test_explicit_allocation_over_material_and_product_purchases(shop):
    conn, ids = shop
    material = credit(conn, ids, 4000)
    product = record_product_purchase(conn, ids["tee"], 1, 700, supplier_id=ids["acme"], purchase_date="2026-05-01", payment={"mode": "NONE"})
    record_supplier_payment(conn, ids["acme"], "2026-05-02", 1700, "CASH", allocations=[
        {"purchase_kind": "PRODUCT", "purchase_id": product, "amount": 700},
        {"purchase_kind": "MATERIAL", "purchase_id": material, "amount": 1000},
    ])
    assert _paid(conn, material) == (1000, 3000, "PARTIAL")
    assert get_product_purchase(conn, product)["payment_status"] == "PAID"


def test_allocations_must_add_up_to_the_payment(shop):
    conn, ids = shop
    purchase = credit(conn, ids, 4000)
    with pytest.raises(ValidationError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-02", 1000, "CASH",
                                allocations=[{"purchase_kind": "MATERIAL", "purchase_id": purchase, "amount": 900}])
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_ALLOCATION_MISMATCH
    assert exc.value.details == {"amount": 1000, "allocated": 900}


def test_an_allocation_above_what_the_purchase_owes_is_refused(shop):
    conn, ids = shop
    purchase = credit(conn, ids, 4000, mode="PARTIAL", amount=3000)
    with pytest.raises(ConflictError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-02", 1500, "CASH",
                                allocations=[{"purchase_kind": "MATERIAL", "purchase_id": purchase, "amount": 1500}])
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_EXCEEDS_DUE
    assert exc.value.details == {"purchase_kind": "MATERIAL", "purchase_id": purchase, "outstanding": 1000}
    assert conn.execute("SELECT COUNT(*) FROM supplier_payments").fetchone()[0] == 1  # only the purchase's own


def test_no_advance_a_payment_above_the_whole_balance_is_refused(shop):
    conn, ids = shop
    credit(conn, ids, 4000)
    with pytest.raises(ConflictError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-02", 4001, "CASH")
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_EXCEEDS_BALANCE
    assert exc.value.details == {"supplier_id": ids["acme"], "outstanding": 4000}
    with pytest.raises(ConflictError):
        record_supplier_payment(conn, ids["other"], "2026-05-02", 1, "CASH")  # owes nothing


def test_a_purchase_of_another_supplier_is_refused(shop):
    conn, ids = shop
    purchase = credit(conn, ids, 4000, supplier="other")
    with pytest.raises(ValidationError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-02", 100, "CASH",
                                allocations=[{"purchase_kind": "MATERIAL", "purchase_id": purchase, "amount": 100}])
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_SUPPLIER_MISMATCH
    assert exc.value.details == {"purchase_kind": "MATERIAL", "purchase_id": purchase, "supplier_id": ids["other"]}


def test_a_payment_before_the_purchase_day_is_refused(shop):
    conn, ids = shop
    purchase = credit(conn, ids, 4000, date="2026-05-10")
    with pytest.raises(ValidationError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-09", 100, "CASH")
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_BEFORE_PURCHASE
    assert exc.value.details == {"purchase_kind": "MATERIAL", "purchase_id": purchase, "purchase_date": "2026-05-10"}
    record_supplier_payment(conn, ids["acme"], "2026-05-10", 100, "CASH")  # the same day is fine


def test_future_dates_and_unknown_things_are_refused(shop):
    conn, ids = shop
    purchase = credit(conn, ids, 4000)
    with pytest.raises(ValidationError) as exc:
        record_supplier_payment(conn, ids["acme"], "2999-01-01", 100, "CASH")
    assert exc.value.code == ErrorCode.DATE_IN_FUTURE and exc.value.field == "payment_date"
    with pytest.raises(NotFoundError) as exc:
        record_supplier_payment(conn, 999, "2026-05-02", 100, "CASH")
    assert exc.value.code == ErrorCode.SUPPLIER_NOT_FOUND
    with pytest.raises(NotFoundError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-02", 100, "CASH",
                                allocations=[{"purchase_kind": "PRODUCT", "purchase_id": purchase, "amount": 100}])
    assert exc.value.code == ErrorCode.PURCHASE_NOT_FOUND
    assert exc.value.details == {"purchase_kind": "PRODUCT", "purchase_id": purchase}
    with pytest.raises(ValidationError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-02", 100, "GOLD")
    assert exc.value.field == "method"
    with pytest.raises(ValidationError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-02", 200, "CASH", allocations=[
            {"purchase_kind": "MATERIAL", "purchase_id": purchase, "amount": 100},
            {"purchase_kind": "MATERIAL", "purchase_id": purchase, "amount": 100},
        ])
    assert exc.value.field == "allocations"


@pytest.mark.parametrize("amount", [0, -5, MAX_MONEY + 1, -MAX_MONEY - 1, 10.5, True])
def test_amounts_are_bounded_on_both_sides(shop, amount):
    conn, ids = shop
    credit(conn, ids, 4000)
    with pytest.raises(ValidationError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-02", amount, "CASH")
    assert exc.value.field == "amount"
    if isinstance(amount, int) and not isinstance(amount, bool) and abs(amount) > MAX_MONEY:
        assert exc.value.code == ErrorCode.AMOUNT_TOO_LARGE


def test_a_payment_racing_another_cannot_overpay(shop):
    """The outstanding is re-read inside the payment's own transaction: after a first payment took it all, a second
    payment planned against the old figure is refused and writes nothing."""
    conn, ids = shop
    purchase = credit(conn, ids, 4000)
    planned = [{"purchase_kind": "MATERIAL", "purchase_id": purchase, "amount": 4000}]
    record_supplier_payment(conn, ids["acme"], "2026-05-02", 4000, "CASH", allocations=planned)
    with pytest.raises(ConflictError) as exc:
        record_supplier_payment(conn, ids["acme"], "2026-05-02", 4000, "CASH", allocations=planned)
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_EXCEEDS_DUE
    assert conn.execute("SELECT COUNT(*) FROM supplier_payments").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM supplier_payment_allocations").fetchone()[0] == 1


def test_a_payment_is_one_audited_operation(shop):
    conn, ids = shop
    credit(conn, ids, 4000)
    payment_id = record_supplier_payment(conn, ids["acme"], "2026-05-02", 1000, "CASH")
    rows = conn.execute(
        "SELECT entity_type, operation, op_id FROM audit_log WHERE entity_type LIKE 'supplier_payment%' "
        "AND operation = 'record_supplier_payment'"
    ).fetchall()
    assert {r["entity_type"] for r in rows} == {"supplier_payments", "supplier_payment_allocations"}
    assert len({r["op_id"] for r in rows}) == 1
    assert get_supplier_payment(conn, payment_id)["amount"] == 1000


# ---------------------------------------------------------------- edit and delete


def test_edit_changes_only_date_method_reference_and_note(shop):
    conn, ids = shop
    credit(conn, ids, 4000, date="2026-05-01")
    payment_id = record_supplier_payment(conn, ids["acme"], "2026-05-03", 1000, "CASH")
    before = get_supplier_payment(conn, payment_id)
    update_supplier_payment(conn, payment_id, method="CHEQUE", reference="CH-1", note="fixed", payment_date="2026-05-02")
    after = get_supplier_payment(conn, payment_id)
    assert (after["method"], after["reference"], after["note"]) == ("CHEQUE", "CH-1", "fixed")
    assert after["payment_date"] != before["payment_date"] and after["amount"] == 1000
    with pytest.raises(ValidationError) as exc:
        update_supplier_payment(conn, payment_id, amount=5)
    assert exc.value.field == "amount"
    with pytest.raises(ValidationError) as exc:
        update_supplier_payment(conn, payment_id, payment_date="2026-04-30")
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_BEFORE_PURCHASE
    with pytest.raises(ValidationError) as exc:
        update_supplier_payment(conn, payment_id, payment_date="2999-01-01")
    assert exc.value.code == ErrorCode.DATE_IN_FUTURE
    update_supplier_payment(conn, payment_id, payment_date="2026-05-02")  # same day: the stored time stays
    assert get_supplier_payment(conn, payment_id)["payment_date"] == after["payment_date"]


def test_delete_removes_the_allocations_and_the_audit_log_keeps_them(shop):
    conn, ids = shop
    purchase = credit(conn, ids, 4000)
    payment_id = record_supplier_payment(conn, ids["acme"], "2026-05-02", 1000, "CASH")
    delete_supplier_payment(conn, payment_id)
    assert _paid(conn, purchase) == (0, 4000, "UNPAID")
    deleted = conn.execute(
        "SELECT entity_type, before_json FROM audit_log WHERE action = 'DELETE' AND operation = 'delete_supplier_payment'"
    ).fetchall()
    assert {r["entity_type"] for r in deleted} == {"supplier_payments", "supplier_payment_allocations"}
    assert json.loads([r for r in deleted if r["entity_type"] == "supplier_payments"][0]["before_json"])["amount"] == 1000
    with pytest.raises(NotFoundError) as exc:
        delete_supplier_payment(conn, payment_id)
    assert exc.value.code == ErrorCode.SUPPLIER_PAYMENT_NOT_FOUND and exc.value.details == {"payment_id": payment_id}


def test_a_supplier_with_payments_cannot_be_deleted(shop):
    conn, ids = shop
    credit(conn, ids, 4000, mode="PARTIAL", amount=100)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM suppliers WHERE id = ?", (ids["acme"],))


# ---------------------------------------------------------------- reads


def test_payables_per_supplier_and_open_purchases(shop):
    conn, ids = shop
    later = credit(conn, ids, 4000, date="2026-05-03")
    oldest = credit(conn, ids, 1000, date="2026-05-01", mode="PARTIAL", amount=400)
    credit(conn, ids, 2000, supplier="other")
    credit(conn, ids, 9000, mode="FULL")  # paid: not open
    payables = get_payables(conn)
    assert payables["outstanding_total"] == 4000 + 600 + 2000 == payables_outstanding(conn)
    acme, other = payables["suppliers"]
    assert (acme["supplier_id"], acme["outstanding"], acme["purchases_total"], acme["paid_total"]) == (ids["acme"], 4600, 14000, 9400)
    assert acme["oldest_unpaid_date"] == get_material_purchase(conn, oldest)["purchase_date"]
    assert [p["purchase_id"] for p in acme["open_purchases"]] == [oldest, later]  # oldest first, by purchase day
    assert acme["open_purchases"][0]["outstanding"] == 600 and acme["open_purchases"][0]["item_name"] == "Fictional Paper"
    assert other["supplier_name"] == "Other Supplier" and other["outstanding"] == 2000
    assert [p["purchase_id"] for p in open_purchases(conn, ids["other"])] == [other["open_purchases"][0]["purchase_id"]]


def test_list_purchases_carries_the_payment_figures_and_the_list_of_payments_filters(shop):
    conn, ids = shop
    credit(conn, ids, 4000, date="2026-05-01")
    record_supplier_payment(conn, ids["acme"], "2026-05-05", 1000, "CASH")
    credit(conn, ids, 500, supplier="other", mode="FULL", date="2026-06-01")
    rows = list_material_purchases(conn)
    assert {(r["supplier_id"], r["payment_status"], r["outstanding"]) for r in rows} == {(ids["acme"], "PARTIAL", 3000), (ids["other"], "PAID", 0)}
    assert [p["amount"] for p in list_supplier_payments(conn)] == [500, 1000]  # newest first
    assert [p["amount"] for p in list_supplier_payments(conn, supplier_id=ids["acme"])] == [1000]
    assert [p["amount"] for p in list_supplier_payments(conn, start_date="2026-06-01")] == [500]
    assert [p["amount"] for p in list_supplier_payments(conn, end_date="2026-05-31")] == [1000]


def test_payments_never_reach_the_profit_and_loss(shop):
    conn, ids = shop
    credit(conn, ids, 4000)
    before = get_profit_and_loss(conn)
    record_supplier_payment(conn, ids["acme"], "2026-05-02", 4000, "CASH")
    payment_id = list_supplier_payments(conn)[0]["id"]
    update_supplier_payment(conn, payment_id, note="x")
    assert get_profit_and_loss(conn) == before
