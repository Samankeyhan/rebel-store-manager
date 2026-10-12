"""Money on the wire is bounded to +-MAX_MONEY (2^53 - 1 Rial): anything larger is a 422
AMOUNT_TOO_LARGE, never a 500 (SQLite stores 64-bit integers; before this limit a value of
2^63 or more overflowed on INSERT). Results that leave the bound (a quantity times a price, a
total, a fee) are refused the same way before they are written."""

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from db.connection import get_connection, init_db
from db.constants import MAX_MONEY
from db.errors import ErrorCode, ValidationError
from db.expenses import add_expense_category
from db.materials import add_material
from db.orders import record_order
from db.partners import add_partner
from db.payment_methods import add_payment_method
from tests.helpers import cat, stocked_product

TOO_BIG = [MAX_MONEY + 1, 2**63 - 1, 2**63, 2**64, 10**30]


@pytest.fixture
def world(tmp_path):
    """A temp database with one of everything a money field needs, and a client that
    answers a crash with a 500 response (so a 500 is an assertion failure, not an exception)."""
    db_path = str(tmp_path / "bounds.db")
    init_db(db_path)
    conn = get_connection(db_path)
    ids = {
        "product": stocked_product(conn, "Bounds LP", stock=1000),
        "material": add_material(conn, "Bounds Box", "STOCK", 1000, initial_stock=1000),
        "expense_category": add_expense_category(conn, "Bounds Rent"),
        "method": add_payment_method(conn, "Bounds Pay", "IMMEDIATE", fee_bps=100),
        "category": cat(conn, "VINYL"),
    }
    add_partner(conn, "Bounds Partner", 100)
    order = record_order(
        conn, "WEBSITE", [{"product_id": ids["product"], "quantity": 1, "unit_price": 100_000}],
        shipping_charge=0, postage_cost=0, packaging_kit_id=None,
        payment_method_id=ids["method"], status="COMPLETED",
    )
    ids["order"] = order if isinstance(order, int) else order["id"]

    def override_get_db():
        c = get_connection(db_path)
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, ids, conn
    finally:
        conn.close()
        app.dependency_overrides.clear()


def _order_body(ids, **item):
    return {
        "channel": "WEBSITE", "shipping_charge": 0, "postage_cost": 0, "packaging_kit_id": None,
        "payment_method_id": None,
        "items": [{"product_id": ids["product"], "quantity": 1, "unit_price": 1000, **item}],
    }


# name -> (method, path(ids), body(ids, value), field expected in the error)
CASES = {
    "expense.amount": ("post", lambda i: "/expenses",
                       lambda i, v: {"expense_category_id": i["expense_category"], "amount": v}, "amount"),
    "product.retail_price": ("post", lambda i: "/products",
                             lambda i, v: {"name": "P1", "category_id": i["category"], "retail_price": v, "wholesale_price": 1},
                             "retail_price"),
    "product.wholesale_price": ("post", lambda i: "/products",
                                lambda i, v: {"name": "P2", "category_id": i["category"], "retail_price": 1, "wholesale_price": v},
                                "wholesale_price"),
    "product.prices_patch": ("patch", lambda i: f"/products/{i['product']}/prices",
                             lambda i, v: {"retail_price": v}, "retail_price"),
    "material.unit_cost": ("post", lambda i: "/materials",
                           lambda i, v: {"name": "M1", "type": "STOCK", "unit_cost": v}, "unit_cost"),
    "purchase.material.total_paid": ("post", lambda i: "/purchases/materials",
                                     lambda i, v: {"material_id": i["material"], "quantity_bought": 1, "total_paid": v}, "total_paid"),
    "purchase.product.total_paid": ("post", lambda i: "/purchases/products",
                                    lambda i, v: {"product_id": i["product"], "quantity_bought": 1, "total_paid": v}, "total_paid"),
    "adjustment.unit_cost": ("post", lambda i: "/adjustments",
                             lambda i, v: {"item_type": "MATERIAL", "item_id": i["material"], "quantity_change": 1,
                                           "reason": "ADJUSTMENT", "unit_cost": v}, "unit_cost"),
    "postage.total_paid": ("post", lambda i: "/postage/batches",
                           lambda i, v: {"total_paid": v, "order_count": 1}, "total_paid"),
    "order.unit_price": ("post", lambda i: "/orders", lambda i, v: _order_body(i, unit_price=v), "unit_price"),
    "order.discount_amount": ("post", lambda i: "/orders", lambda i, v: _order_body(i, discount_amount=v), "discount_amount"),
    "order.shipping_charge": ("post", lambda i: "/orders",
                              lambda i, v: {**_order_body(i), "shipping_charge": v}, "shipping_charge"),
    "order.postage_cost": ("post", lambda i: "/orders",
                           lambda i, v: {**_order_body(i), "postage_cost": v}, "postage_cost"),
    "order.transaction_fee": ("post", lambda i: "/orders",
                              lambda i, v: {**_order_body(i), "transaction_fee": v}, "transaction_fee"),
    "payment_method.fee_fixed": ("post", lambda i: "/payment-methods",
                                 lambda i, v: {"name": "PM1", "settlement_rule": "IMMEDIATE", "fee_fixed": v}, "fee_fixed"),
    "payment_method.fee_cap": ("post", lambda i: "/payment-methods",
                               lambda i, v: {"name": "PM2", "settlement_rule": "IMMEDIATE", "fee_bps": 10, "fee_cap": v}, "fee_cap"),
    "payment_method.fee_fixed_patch": ("patch", lambda i: f"/payment-methods/{i['method']}",
                                       lambda i, v: {"fee_fixed": v}, "fee_fixed"),
    "settlement.amount_received": ("post", lambda i: "/settlements",
                                   lambda i, v: {"payment_method_id": i["method"], "settled_date": "2026-01-01",
                                                 "amount_received": v, "order_ids": [i["order"]]}, "amount_received"),
    "distribution.total_amount_distributed": ("post", lambda i: "/distributions",
                                              lambda i, v: {"period_start": "2026-01-01", "period_end": "2026-01-31",
                                                            "total_amount_distributed": v}, "total_amount_distributed"),
    "distribution_preview.total_amount_distributed": ("post", lambda i: "/distributions/preview",
                                                      lambda i, v: {"period_start": "2026-01-01", "period_end": "2026-01-31",
                                                                    "total_amount_distributed": v}, "total_amount_distributed"),
    "setting.default_shipping_charge": ("put", lambda i: "/settings/default_shipping_charge",
                                        lambda i, v: {"value": v}, "value"),
    "setting.default_postage_estimate": ("put", lambda i: "/settings/default_postage_estimate",
                                         lambda i, v: {"value": str(v)}, "value"),
}


def _send(client, ids, name, value):
    method, path, body, _ = CASES[name]
    return getattr(client, method)(path(ids), json=body(ids, value))


@pytest.mark.parametrize("name", CASES)
@pytest.mark.parametrize("value", TOO_BIG)
def test_an_amount_beyond_the_bound_is_422_amount_too_large(world, name, value):
    client, ids, _ = world
    response = _send(client, ids, name, value)
    assert response.status_code == 422, (name, value, response.status_code, response.text[:300])
    error = response.json()["error"]
    assert error["code"] == "AMOUNT_TOO_LARGE"
    assert error["details"]["max"] == MAX_MONEY
    assert str(value) not in response.text  # a huge input is never echoed back


@pytest.mark.parametrize("name", CASES)
def test_an_amount_below_minus_the_bound_is_422_amount_too_large(world, name):
    client, ids, _ = world
    response = _send(client, ids, name, -MAX_MONEY - 1)
    assert response.status_code == 422, (name, response.text[:300])
    assert response.json()["error"]["code"] == "AMOUNT_TOO_LARGE"


@pytest.mark.parametrize("name", [n for n in CASES if not n.startswith(("setting.", "distribution"))])
def test_a_negative_amount_inside_the_bound_stays_a_per_field_422_from_db(world, name):
    """>= 0 is still decided in db/ (it runs before any write): 422 on the field, not the bound code."""
    client, ids, conn = world
    before = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    response = _send(client, ids, name, -1)
    assert response.status_code == 422, (name, response.text[:300])
    error = response.json()["error"]
    assert error["code"] != "AMOUNT_TOO_LARGE"
    assert error["field"] == CASES[name][3]
    assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == before  # nothing written


@pytest.mark.parametrize("name", list(CASES))
def test_the_bound_itself_and_one_below_are_not_a_bound_error_or_a_crash(world, name):
    client, ids, _ = world
    if name == "order.shipping_charge":
        pytest.skip("shipping at the bound plus a line is a total beyond it (covered below)")
    for value in (MAX_MONEY - 1, MAX_MONEY):
        response = _send(client, ids, name, value)
        assert response.status_code != 500, (name, value, response.text[:300])
        if response.status_code >= 400:
            assert response.json()["error"]["code"] != "AMOUNT_TOO_LARGE", (name, value)


def test_the_fee_preview_amount_is_bounded(world):
    client, ids, _ = world
    path = f"/payment-methods/{ids['method']}/fee-preview"
    assert client.get(path, params={"amount": MAX_MONEY}).status_code == 200
    for value in (MAX_MONEY + 1, 2**63, 10**30):
        response = client.get(path, params={"amount": value})
        assert response.status_code == 422, (value, response.text[:300])
        assert response.json()["error"]["code"] == "AMOUNT_TOO_LARGE"


# ------------------------------------------------------ results that leave the bound


def test_a_line_total_beyond_the_bound_is_refused_before_anything_is_written(world):
    client, ids, conn = world
    stock = conn.execute("SELECT current_stock FROM products WHERE id = ?", (ids["product"],)).fetchone()[0]
    body = _order_body(ids, unit_price=MAX_MONEY, quantity=2)
    response = client.post("/orders", json=body)
    assert response.status_code == 422, response.text[:300]
    error = response.json()["error"]
    assert error["code"] == "AMOUNT_TOO_LARGE" and error["field"] == "unit_price"
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 1  # only the fixture order
    assert conn.execute("SELECT current_stock FROM products WHERE id = ?", (ids["product"],)).fetchone()[0] == stock


def test_a_huge_quantity_times_a_normal_price_is_refused_not_a_500(world):
    client, ids, _ = world
    response = client.post("/orders", json=_order_body(ids, quantity=10**30, unit_price=1000))
    assert response.status_code == 422, response.text[:300]
    assert response.json()["error"]["code"] in ("QUANTITY_OUT_OF_RANGE", "AMOUNT_TOO_LARGE")


def test_items_that_sum_past_the_bound_are_refused(world):
    client, ids, conn = world
    second = stocked_product(conn, "Bounds LP 2", stock=1000)
    body = _order_body(ids, unit_price=MAX_MONEY - 10)
    body["items"].append({"product_id": second, "quantity": 1, "unit_price": MAX_MONEY - 10})
    response = client.post("/orders", json=body)
    assert response.status_code == 422, response.text[:300]
    assert response.json()["error"]["code"] == "AMOUNT_TOO_LARGE"


def test_shipping_that_pushes_the_total_past_the_bound_is_refused(world):
    client, ids, _ = world
    body = {**_order_body(ids, unit_price=MAX_MONEY), "shipping_charge": 1}
    response = client.post("/orders", json=body)
    assert response.status_code == 422, response.text[:300]
    assert response.json()["error"]["code"] == "AMOUNT_TOO_LARGE"
    assert response.json()["error"]["field"] == "shipping_charge"


def test_an_order_exactly_at_the_bound_is_recorded(world):
    client, ids, _ = world
    response = client.post("/orders", json=_order_body(ids, unit_price=MAX_MONEY))
    assert response.status_code == 201, response.text[:300]


def test_a_material_purchase_whose_cost_exceeds_the_bound_per_unit_is_not_a_crash(world):
    client, ids, _ = world
    response = client.post(
        "/purchases/materials",
        json={"material_id": ids["material"], "quantity_bought": 0.001, "total_paid": MAX_MONEY},
    )
    assert response.status_code == 422, response.text[:300]  # unit cost = 9e18 > bound
    assert response.json()["error"]["code"] == "AMOUNT_TOO_LARGE"
    assert response.json()["error"]["field"] == "total_paid"


def test_a_fee_plus_fixed_fee_beyond_the_bound_is_refused(world):
    client, ids, conn = world
    method = add_payment_method(conn, "Big Fixed", "IMMEDIATE", fee_bps=100, fee_fixed=MAX_MONEY)
    body = {**_order_body(ids, unit_price=MAX_MONEY), "payment_method_id": method}
    response = client.post("/orders", json=body)
    assert response.status_code == 422, response.text[:300]
    assert response.json()["error"]["code"] == "AMOUNT_TOO_LARGE"


def test_reports_over_several_maximal_rows_do_not_crash(world):
    client, ids, conn = world
    for n in range(3):
        product = stocked_product(conn, f"Max {n}", stock=10)
        response = client.post("/orders", json={
            **_order_body(ids, unit_price=MAX_MONEY), "items": [
                {"product_id": product, "quantity": 1, "unit_price": MAX_MONEY}],
        })
        assert response.status_code == 201, response.text[:300]
    for path in ("/orders", "/reports/profit-and-loss", "/settlements/pending"):
        response = client.get(path)
        assert response.status_code != 500, (path, response.text[:300])


def test_db_functions_refuse_the_bound_too(world):
    """Defence in depth: a direct caller (not through the API schema) gets the same refusal."""
    _, ids, conn = world
    from db.expenses import add_expense

    with pytest.raises(ValidationError) as exc_info:
        add_expense(conn, ids["expense_category"], 2**63)
    assert exc_info.value.code == ErrorCode.AMOUNT_TOO_LARGE
    assert exc_info.value.details == {"max": MAX_MONEY}
    assert exc_info.value.field == "amount"
