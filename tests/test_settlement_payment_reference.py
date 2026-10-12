"""Pending and settled order rows carry the order's payment_reference (null when none); no total moves."""

from db.orders import record_order
from tests.test_money_bounds import world  # noqa: F401  (fixture)


def _pay(conn, ids, reference):
    return record_order(
        conn, "WEBSITE", [{"product_id": ids["product"], "quantity": 1, "unit_price": 100_000}],
        shipping_charge=0, postage_cost=0, packaging_kit_id=None,
        payment_method_id=ids["method"], status="COMPLETED", payment_reference=reference,
    )


def _pending_rows(client, method_id):
    body = client.get("/settlements/pending").json()
    (method,) = [m for m in body if m["payment_method_id"] == method_id]
    return [o for group in method["groups"] for o in group["orders"]]


def test_pending_rows_have_the_reference_or_null_and_the_same_money(world):  # noqa: F811
    client, ids, conn = world
    with_ref = _pay(conn, ids, "REF-A-1")
    without = _pay(conn, ids, None)
    rows = {o["id"]: o for o in _pending_rows(client, ids["method"])}
    assert rows[with_ref]["payment_reference"] == "REF-A-1"
    assert rows[without]["payment_reference"] is None
    money = ("customer_total", "transaction_fee", "expected_amount")
    assert [rows[with_ref][k] for k in money] == [rows[without][k] for k in money]
    assert all("payment_reference" in o for o in rows.values())  # the fixture order too


def test_settled_detail_rows_have_the_reference_or_null_and_totals_are_unchanged(world):  # noqa: F811
    client, ids, conn = world
    with_ref = _pay(conn, ids, "REF-B-2")
    without = _pay(conn, ids, None)
    mine = [o for o in _pending_rows(client, ids["method"]) if o["id"] in (with_ref, without)]
    pending_total = sum(o["expected_amount"] for o in mine)
    settled_date = max(o["paid_date"] for o in mine)
    response = client.post("/settlements", json={
        "payment_method_id": ids["method"], "settled_date": settled_date,
        "amount_received": pending_total, "order_ids": [with_ref, without],
    })
    assert response.status_code == 201, response.text[:300]
    detail = client.get(f"/settlements/{response.json()['id']}").json()
    rows = {o["id"]: o for o in detail["orders"]}
    assert rows[with_ref]["payment_reference"] == "REF-B-2"
    assert rows[without]["payment_reference"] is None
    assert detail["expected_amount"] == pending_total and detail["difference"] == 0
    assert sum(o["expected_amount"] for o in detail["orders"]) == detail["expected_amount"]
