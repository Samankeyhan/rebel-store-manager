"""POST /orders/bulk-status: the HTTP contract of the PAID -> COMPLETED bulk change."""

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from api.main import app
from api.schemas.errors import ErrorEnvelope
from tests.helpers import api_sale_method

ENVELOPE = TypeAdapter(ErrorEnvelope)


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
                                                "quantity_change": 50, "reason": "ADJUSTMENT", "unit_cost": 9_000})
    assert stocked.status_code == 201, stocked.text
    return created.json()["id"]


def _sell(client, product, status="PAID"):
    body = {"channel": "WEBSITE", "items": [{"product_id": product, "quantity": 1, "unit_price": 30_000}],
            "packaging_kit_id": None, "payment_method_id": api_sale_method(client), "status": status}
    created = client.post("/orders", json=body)
    assert created.status_code == 201, created.text
    return created.json()["order"]


def _error(response, status):
    assert response.status_code == status, response.text
    ENVELOPE.validate_python(response.json())
    return response.json()["error"]


def test_paid_orders_are_completed_in_one_call(client, product):
    orders = [_sell(client, product) for _ in range(3)]
    ids = [o["id"] for o in orders]
    response = client.post("/orders/bulk-status", json={"order_ids": ids, "status": "COMPLETED"})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "count": 3,
        "orders": [{"id": o["id"], "invoice_number": o["invoice_number"], "status": "COMPLETED"} for o in orders],
    }
    for i in ids:
        assert client.get(f"/orders/{i}").json()["order"]["status"] == "COMPLETED"


def test_one_order_that_is_not_paid_is_a_409_for_the_whole_call(client, product):
    paid, pending = _sell(client, product), _sell(client, product, status="PENDING")
    error = _error(client.post("/orders/bulk-status", json={"order_ids": [paid["id"], pending["id"]],
                                                            "status": "COMPLETED"}), 409)
    assert error["code"] == "ORDER_BULK_NOT_ELIGIBLE"
    assert error["details"] == {"ineligible": [
        {"order_id": pending["id"], "invoice_number": pending["invoice_number"], "status": "PENDING"}]}
    assert client.get(f"/orders/{paid['id']}").json()["order"]["status"] == "PAID"
    assert client.get(f"/orders/{pending['id']}").json()["order"]["status"] == "PENDING"


def test_an_unknown_order_is_404(client, product):
    paid = _sell(client, product)
    error = _error(client.post("/orders/bulk-status", json={"order_ids": [paid["id"], 9999],
                                                            "status": "COMPLETED"}), 404)
    assert error["code"] == "NOT_FOUND"
    assert client.get(f"/orders/{paid['id']}").json()["order"]["status"] == "PAID"


@pytest.mark.parametrize("body", [
    {"order_ids": [], "status": "COMPLETED"},
    {"order_ids": list(range(1, 202)), "status": "COMPLETED"},
    {"order_ids": [1.5], "status": "COMPLETED"},
    {"order_ids": ["1"], "status": "COMPLETED"},
    {"order_ids": [True], "status": "COMPLETED"},
    {"order_ids": [1], "status": "PAID"},
    {"order_ids": [1], "status": "CANCELLED"},
    {"order_ids": [1]},
    {"status": "COMPLETED"},
    {"order_ids": [1], "status": "COMPLETED", "paid_date": "2026-10-01"},
])
def test_a_bad_request_is_a_422_in_the_error_envelope(client, body):
    _error(client.post("/orders/bulk-status", json=body), 422)


def test_the_same_order_twice_is_a_422_on_order_ids(client, product):
    paid = _sell(client, product)
    error = _error(client.post("/orders/bulk-status", json={"order_ids": [paid["id"]] * 2, "status": "COMPLETED"}), 422)
    assert error["field"] == "order_ids"
    assert client.get(f"/orders/{paid['id']}").json()["order"]["status"] == "PAID"


def test_the_single_order_routes_are_unchanged(client, product):
    paid = _sell(client, product)
    changed = client.post(f"/orders/{paid['id']}/status", json={"status": "COMPLETED"})
    assert changed.status_code == 200 and changed.json()["order"]["status"] == "COMPLETED"
    assert client.get(f"/orders/{paid['id']}").status_code == 200
