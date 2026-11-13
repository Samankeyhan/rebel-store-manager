"""POST /orders/{id}/edit-preview and PATCH /orders/{id}: the HTTP contract of the light order edit
(accounting-rules section 20, "Light edit")."""

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from api.main import app
from api.schemas.errors import ErrorEnvelope
from tests.helpers import api_sale_method

ENVELOPE = TypeAdapter(ErrorEnvelope)
DAY = "2026-10-10"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _error(response):
    ENVELOPE.validate_python(response.json())
    return response.json()["error"]


@pytest.fixture
def order(client):
    category = client.get("/categories", params={"kind": "PRODUCT"}).json()[0]["id"]
    product = client.post("/products", json={"name": "Fictional LP", "category_id": category,
                                             "retail_price": 30_000, "wholesale_price": 20_000}).json()["id"]
    client.post("/adjustments", json={"item_type": "PRODUCT", "item_id": product, "quantity_change": 10,
                                      "reason": "ADJUSTMENT", "unit_cost": 9_000})
    created = client.post("/orders", json={
        "channel": "IN_PERSON", "items": [{"product_id": product, "quantity": 1, "unit_price": 30_000}],
        "order_date": DAY, "packaging_kit_id": None, "payment_method_id": api_sale_method(client),
        "status": "PAID", "postage_cost": 0, "shipping_charge": 0,
    })
    assert created.status_code == 201, created.text
    return created.json()["order"]


def test_patch_changes_the_sent_fields_and_returns_the_detail(client, order):
    response = client.patch(f"/orders/{order['id']}", json={"order_date": "2026-10-11", "shipping_charge": 5_000,
                                                            "customer_name": "Test Customer"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["order"]["order_date"] == "2026-10-10 20:30:00"
    assert body["order"]["shipping_charge"] == 5_000
    assert body["order"]["customer_name"] == "Test Customer"
    assert body["customer_total"] == 35_000
    assert body["order"]["paid_date"] == order["paid_date"]


def test_the_preview_shape_and_no_write(client, order):
    response = client.post(f"/orders/{order['id']}/edit-preview", json={"postage_cost": 7_000, "notes": "n"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["blockers"] == []
    assert body["changes"] == [{"field": "postage_cost", "before": 0, "after": 7_000},
                               {"field": "notes", "before": None, "after": "n"}]
    assert body["figures"]["profit"]["after"] == body["figures"]["profit"]["before"] - 7_000
    assert body["figures"]["order_day"] == {"before": DAY, "after": DAY}
    assert client.get(f"/orders/{order['id']}").json()["order"]["postage_cost"] == 0


def test_the_preview_reports_a_blocker_with_list_details(client, order):
    client.post(f"/orders/{order['id']}/return", json={"status": "CANCELLED", "reason": "x"})
    body = client.post(f"/orders/{order['id']}/edit-preview", json={"postage_cost": 1}).json()
    assert body["blockers"] == [{"code": "ORDER_EDIT_NOT_ALLOWED",
                                 "details": {"order_id": order["id"], "status": "CANCELLED", "fields": ["postage_cost"]}}]


def test_a_refusal_is_a_409_envelope_with_its_details_model(client, order):
    client.post(f"/orders/{order['id']}/return", json={"status": "CANCELLED", "reason": "x"})
    response = client.patch(f"/orders/{order['id']}", json={"shipping_charge": 1})
    assert response.status_code == 409
    error = _error(response)
    assert error["code"] == "ORDER_EDIT_NOT_ALLOWED"
    assert error["details"] == {"order_id": order["id"], "status": "CANCELLED", "fields": ["shipping_charge"]}


@pytest.mark.parametrize("body", [
    {}, {"shipping_charge": 1.5}, {"shipping_charge": "10"}, {"shipping_charge": True}, {"postage_cost": -1},
    {"order_date": "10/11/2026"}, {"payment_method_id": "1"}, {"packaging_kit_id": None}, {"items": []},
    {"payment_method_id": None}, {"paid_date": None}, {"transaction_fee": 5},
])
def test_bad_bodies_are_422_envelopes_and_write_nothing(client, order, body):
    response = client.patch(f"/orders/{order['id']}", json=body)
    assert response.status_code == 422, response.text
    _error(response)
    assert client.get(f"/orders/{order['id']}").json()["order"] == order | {"payment_method_name": order["payment_method_name"]}


def test_a_future_date_is_422_date_in_future(client, order):
    response = client.patch(f"/orders/{order['id']}", json={"order_date": "2999-01-01"})
    assert response.status_code == 422
    error = _error(response)
    assert (error["code"], error["field"]) == ("DATE_IN_FUTURE", "order_date")


def test_an_unknown_order_is_404(client):
    assert client.patch("/orders/999", json={"notes": "x"}).status_code == 404
    assert client.post("/orders/999/edit-preview", json={"notes": "x"}).status_code == 404
