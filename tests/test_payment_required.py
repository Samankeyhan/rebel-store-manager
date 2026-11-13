"""A new or corrected sale always has a payment method (accounting-rules sections 7 and 14): no method is
PAYMENT_METHOD_REQUIRED for every status, DRAFT included, through db/ and through the API. Orders recorded before
the rule may have none and stay fully usable."""

import os

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from api.main import app
from api.schemas.errors import ErrorEnvelope
from db.connection import get_connection
from db.errors import ErrorCode, ValidationError
from db.order_voids import correct_order, void_order
from db.orders import get_order, list_orders, record_order, update_order_status
from db.settings import update_channel_settings
from tests.helpers import api_sale_method, make_legacy_no_method, sale_method, stocked_product

ENVELOPE = TypeAdapter(ErrorEnvelope)
ITEM = {"quantity": 1, "unit_price": 3000}


def _items(product):
    return [{"product_id": product, **ITEM}]


def _counts(conn):
    return tuple(
        conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("orders", "order_items", "stock_movements", "audit_log")
    )


# ------------------------------------------------------------------ db


@pytest.mark.parametrize("status", ["DRAFT", "PENDING", "PAID", "COMPLETED"])
def test_a_sale_with_no_method_is_refused_for_every_status(test_db, status):
    product = stocked_product(test_db, stock=5)
    before = _counts(test_db)
    with pytest.raises(ValidationError) as exc_info:
        record_order(test_db, "WEBSITE", _items(product), status=status, payment_method_id=None, packaging_kit_id=None)
    assert exc_info.value.code == ErrorCode.PAYMENT_METHOD_REQUIRED
    assert exc_info.value.field == "payment_method_id"
    assert exc_info.value.details == {}
    assert _counts(test_db) == before  # nothing written, not even an audit row
    assert test_db.execute("SELECT current_stock FROM products WHERE id = ?", (product,)).fetchone()[0] == 5


def test_the_channel_default_stands_in_only_when_there_is_one(test_db):
    product = stocked_product(test_db, stock=5)
    with pytest.raises(ValidationError) as exc_info:  # omitted = the channel default, and WEBSITE has none
        record_order(test_db, "WEBSITE", _items(product), packaging_kit_id=None)
    assert exc_info.value.code == ErrorCode.PAYMENT_METHOD_REQUIRED

    method = sale_method(test_db)
    update_channel_settings(test_db, "WEBSITE", default_payment_method_id=method)
    order_id = record_order(test_db, "WEBSITE", _items(product), packaging_kit_id=None)
    assert get_order(test_db, order_id)["order"]["payment_method_id"] == method


def test_an_explicit_null_is_refused_even_when_the_channel_has_a_default(test_db):
    product = stocked_product(test_db, stock=5)
    update_channel_settings(test_db, "WEBSITE", default_payment_method_id=sale_method(test_db))
    with pytest.raises(ValidationError) as exc_info:
        record_order(test_db, "WEBSITE", _items(product), packaging_kit_id=None, payment_method_id=None)
    assert exc_info.value.code == ErrorCode.PAYMENT_METHOD_REQUIRED


def test_a_correction_with_no_method_is_refused_and_leaves_the_old_order_as_it_was(test_db):
    product = stocked_product(test_db, stock=10)
    method = sale_method(test_db)
    old = record_order(test_db, "IN_PERSON", _items(product), packaging_kit_id=None, payment_method_id=method)
    before = _counts(test_db)
    stock = test_db.execute("SELECT current_stock FROM products WHERE id = ?", (product,)).fetchone()[0]
    with pytest.raises(ValidationError) as exc_info:
        correct_order(test_db, old, "wrong price", "IN_PERSON", _items(product), packaging_kit_id=None,
                      payment_method_id=None)
    assert exc_info.value.code == ErrorCode.PAYMENT_METHOD_REQUIRED
    assert get_order(test_db, old)["order"]["status"] == "COMPLETED"  # the void was rolled back with it
    assert _counts(test_db) == before
    assert test_db.execute("SELECT current_stock FROM products WHERE id = ?", (product,)).fetchone()[0] == stock


# ------------------------------------------------------------------ legacy orders stay usable


def test_a_legacy_order_without_a_method_still_reads_lists_pays_and_voids(test_db):
    product = stocked_product(test_db, stock=10)
    method = sale_method(test_db)
    pending = make_legacy_no_method(test_db, record_order(
        test_db, "IN_PERSON", _items(product), packaging_kit_id=None, payment_method_id=method, status="PENDING"))
    paid = make_legacy_no_method(test_db, record_order(
        test_db, "IN_PERSON", _items(product), packaging_kit_id=None, payment_method_id=method, status="PAID"))

    detail = get_order(test_db, pending)["order"]
    assert (detail["payment_method_id"], detail["payment_method_name"]) == (None, None)
    listed = {o["id"]: o for o in list_orders(test_db)}
    assert listed[pending]["payment_method_name"] is None and listed[paid]["payment_method_name"] is None
    assert pending not in {o["id"] for o in list_orders(test_db, payment_method_id=method)}
    assert pending not in {o["id"] for o in list_orders(test_db, settlement_state="pending")}

    update_order_status(test_db, pending, "PAID")  # a legacy order moves on as before
    update_order_status(test_db, pending, "COMPLETED")
    void_order(test_db, paid, "entered twice")
    assert get_order(test_db, pending)["order"]["status"] == "COMPLETED"
    assert get_order(test_db, paid)["order"]["status"] == "VOIDED"


# ------------------------------------------------------------------ API


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def product(client):
    category = client.get("/categories", params={"kind": "PRODUCT"}).json()[0]["id"]
    created = client.post("/products", json={"name": "Fictional LP", "category_id": category,
                                             "retail_price": 30_000, "wholesale_price": 20_000})
    assert created.status_code == 201, created.text
    stocked = client.post("/adjustments", json={"item_type": "PRODUCT", "item_id": created.json()["id"],
                                                "quantity_change": 10, "reason": "ADJUSTMENT", "unit_cost": 9_000})
    assert stocked.status_code == 201, stocked.text
    return created.json()["id"]


def _body(product, **extra):
    return {"channel": "WEBSITE", "items": [{"product_id": product, "quantity": 1, "unit_price": 30_000}],
            "packaging_kit_id": None, **extra}


def _refused(response):
    assert response.status_code == 422, response.text
    ENVELOPE.validate_python(response.json())
    error = response.json()["error"]
    assert (error["code"], error["field"], error["details"]) == ("PAYMENT_METHOD_REQUIRED", "payment_method_id", {})


@pytest.mark.parametrize("status", ["DRAFT", "PENDING", "PAID", "COMPLETED"])
def test_the_api_refuses_a_null_method_for_every_status(client, product, status):
    _refused(client.post("/orders", json=_body(product, status=status, payment_method_id=None)))
    assert client.get("/orders").json() == []


def test_the_api_refuses_an_omitted_or_default_method_when_the_channel_has_none(client, product):
    _refused(client.post("/orders", json=_body(product)))
    _refused(client.post("/orders", json=_body(product, payment_method_id="default")))
    assert client.get("/orders").json() == []

    method = api_sale_method(client)
    assert client.patch("/settings/channels/WEBSITE", json={"default_payment_method_id": method}).status_code == 200
    created = client.post("/orders", json=_body(product))
    assert created.status_code == 201, created.text
    assert created.json()["order"]["payment_method_id"] == method


def test_the_api_refuses_a_correction_with_no_method_and_keeps_the_old_order(client, product):
    method = api_sale_method(client)
    old = client.post("/orders", json=_body(product, payment_method_id=method)).json()["order"]["id"]
    _refused(client.post(f"/orders/{old}/correct",
                         json={"reason": "wrong", "order": _body(product, payment_method_id=None)}))
    assert client.get(f"/orders/{old}").json()["order"]["status"] == "COMPLETED"
    assert len(client.get("/orders").json()) == 1


def test_a_legacy_order_without_a_method_shows_on_every_screen_endpoint(client, product):
    method = api_sale_method(client)
    created = client.post("/orders", json=_body(product, payment_method_id=method, status="PAID",
                                                order_date="2026-10-01", transaction_fee=700))
    order_id = created.json()["order"]["id"]
    conn = get_connection(os.environ["REBEL_DB"])
    try:
        make_legacy_no_method(conn, order_id)
    finally:
        conn.close()

    detail = client.get(f"/orders/{order_id}")
    assert detail.status_code == 200
    assert (detail.json()["order"]["payment_method_id"], detail.json()["order"]["payment_method_name"]) == (None, None)
    listed = [o for o in client.get("/orders").json() if o["id"] == order_id]
    assert listed and listed[0]["payment_method_name"] is None
    assert client.get("/orders", params={"payment_method_id": method}).json() == []
    assert client.get("/orders", params={"settlement_state": "pending"}).json() == []
    assert client.get("/settlements/pending").json() == []  # no method: nothing to settle
    report = client.get("/reports/payment-methods").json()
    row = next(r for r in report if r["payment_method_id"] is None)  # the "no method" row the report keeps
    assert (row["name"], row["order_count"], row["transaction_fees"]) == (None, 1, 700)
    assert client.get(f"/orders/{order_id}/invoice.pdf").status_code == 200
