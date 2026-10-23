"""GET /orders/{id}/void-preview, POST /orders/{id}/void and /orders/{id}/correct, and VOIDED in GET /orders: the
HTTP contract of voiding and correcting a sale entered by mistake (accounting-rules section 20)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from api.main import app
from api.schemas.errors import ErrorEnvelope

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
def product(client):
    category = client.get("/categories", params={"kind": "PRODUCT"}).json()[0]["id"]
    created = client.post("/products", json={"name": "Fictional LP", "category_id": category,
                                             "retail_price": 30_000, "wholesale_price": 20_000})
    assert created.status_code == 201, created.text
    stocked = client.post("/adjustments", json={"item_type": "PRODUCT", "item_id": created.json()["id"],
                                                "quantity_change": 10, "reason": "ADJUSTMENT", "unit_cost": 9_000})
    assert stocked.status_code == 201, stocked.text
    return created.json()["id"]


def _sale(product, quantity=2, price=30_000, **extra):
    return {"channel": "IN_PERSON", "items": [{"product_id": product, "quantity": quantity, "unit_price": price}],
            "order_date": DAY, "packaging_kit_id": None, "payment_method_id": None, **extra}


@pytest.fixture
def order(client, product):
    created = client.post("/orders", json=_sale(product))
    assert created.status_code == 201, created.text
    return created.json()["order"]


def _stock(client, product):
    return next(p["current_stock"] for p in client.get("/products").json() if p["id"] == product)


def test_the_preview_lists_what_comes_back_and_no_blocker(client, order, product):
    response = client.get(f"/orders/{order['id']}/void-preview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["blockers"] == [] and body["materials"] == []
    assert body["products"] == [{"item_id": product, "name": "Fictional LP", "quantity": 2, "unit_cost_before": 9_000,
                                 "unit_cost_after": 9_000, "frozen_cost_known": 1}]
    assert (body["customer_total"], body["order_day"], body["pending_settlement"]) == (60_000, DAY, 0)


def test_the_preview_of_an_unknown_order_is_404(client):
    assert client.get("/orders/999/void-preview").status_code == 404


def test_the_preview_names_a_blocker_with_its_details(client, product):
    method = client.post("/payment-methods", json={"name": "Card", "settlement_rule": "IMMEDIATE"}).json()["id"]
    order_id = client.post("/orders", json=_sale(product, payment_method_id=method)).json()["order"]["id"]
    settlement = client.post("/settlements", json={"payment_method_id": method, "settled_date": DAY,
                                                   "amount_received": 60_000, "order_ids": [order_id]})
    assert settlement.status_code == 201, settlement.text
    blockers = client.get(f"/orders/{order_id}/void-preview").json()["blockers"]
    assert blockers == [{"code": "ORDER_ALREADY_SETTLED",
                         "details": {"order_id": order_id, "settlement_id": settlement.json()["id"]}}]
    refused = client.post(f"/orders/{order_id}/void", json={"reason": "x"})
    assert refused.status_code == 409 and _error(refused)["code"] == "ORDER_ALREADY_SETTLED"


def test_void_returns_the_voided_order_and_its_stock(client, order, product):
    assert _stock(client, product) == 8
    response = client.post(f"/orders/{order['id']}/void", json={"reason": " entered  twice "})
    assert response.status_code == 200, response.text
    voided = response.json()["order"]
    assert (voided["status"], voided["void_reason"]) == ("VOIDED", "entered twice")
    assert voided["voided_at"] is not None and voided["replaced_by_order_id"] is None
    assert _stock(client, product) == 10


def test_a_blank_reason_is_422_and_a_missing_one_a_request_error(client, order):
    blank = client.post(f"/orders/{order['id']}/void", json={"reason": "   "})
    assert blank.status_code == 422
    error = _error(blank)
    assert (error["code"], error["field"], error["details"]) == ("VOID_REASON_REQUIRED", "reason", {})
    missing = client.post(f"/orders/{order['id']}/void", json={})
    assert missing.status_code == 422 and _error(missing)["type"] == "RequestValidationError"


def test_a_second_void_and_a_draft_are_409_with_typed_details(client, order, product):
    client.post(f"/orders/{order['id']}/void", json={"reason": "x"})
    again = client.post(f"/orders/{order['id']}/void", json={"reason": "x"})
    assert again.status_code == 409
    error = _error(again)
    assert error["code"] == "ORDER_ALREADY_VOIDED" and error["details"]["order_id"] == order["id"]
    draft = client.post("/orders", json=_sale(product, status="DRAFT")).json()["order"]["id"]
    refused = client.post(f"/orders/{draft}/void", json={"reason": "x"})
    assert (refused.status_code, _error(refused)["code"]) == (409, "ORDER_NOT_COMMITTED")


def test_correct_records_the_new_order_and_links_both_sides(client, order, product):
    response = client.post(f"/orders/{order['id']}/correct",
                           json={"reason": "wrong price", "order": _sale(product, price=25_000)})
    assert response.status_code == 201, response.text
    new = response.json()
    assert new["customer_total"] == 50_000
    assert (new["order"]["replaces_order_id"], new["order"]["replaces_invoice_number"]) == (
        order["id"], order["invoice_number"])
    old = client.get(f"/orders/{order['id']}").json()["order"]
    assert (old["status"], old["replaced_by_order_id"], old["replaced_by_invoice_number"]) == (
        "VOIDED", new["order"]["id"], new["order"]["invoice_number"])
    assert _stock(client, product) == 8


def test_correct_takes_the_channel_defaults_like_post_orders(client, order, product):
    body = _sale(product, packaging_kit_id="default", payment_method_id="default")
    response = client.post(f"/orders/{order['id']}/correct", json={"reason": "x", "order": body})
    assert response.status_code == 201, response.text
    assert response.json()["order"]["payment_method_id"] is None  # IN_PERSON has no default method


def test_a_refused_correction_leaves_the_old_order_as_it_was(client, order, product):
    future = client.post(f"/orders/{order['id']}/correct",
                         json={"reason": "x", "order": _sale(product, order_date="2099-01-01")})
    assert future.status_code == 422
    assert (_error(future)["code"], _error(future)["field"]) == ("DATE_IN_FUTURE", "order_date")
    draft = client.post(f"/orders/{order['id']}/correct", json={"reason": "x", "order": _sale(product, status="DRAFT")})
    assert (draft.status_code, _error(draft)["field"]) == (422, "status")
    short = client.post(f"/orders/{order['id']}/correct", json={"reason": "x", "order": _sale(product, quantity=50)})
    assert (short.status_code, _error(short)["type"]) == (409, "InsufficientStockError")
    assert client.get(f"/orders/{order['id']}").json()["order"]["status"] == "COMPLETED"
    assert _stock(client, product) == 8


def test_the_order_list_hides_voided_orders_unless_asked(client, order, product):
    kept = client.post("/orders", json=_sale(product, quantity=1)).json()["order"]["id"]
    client.post(f"/orders/{order['id']}/void", json={"reason": "x"})
    assert [o["id"] for o in client.get("/orders").json()] == [kept]
    every = client.get("/orders", params={"include_voided": "true"}).json()
    assert {o["id"] for o in every} == {kept, order["id"]}
    voided = client.get("/orders", params={"status": "VOIDED"}).json()
    assert [(o["id"], o["profit"], o["void_reason"]) for o in voided] == [(order["id"], None, "x")]


def test_the_invoice_of_a_voided_order_still_prints(client, order):
    client.post(f"/orders/{order['id']}/void", json={"reason": "x"})
    response = client.get(f"/orders/{order['id']}/invoice.pdf")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")


def test_return_and_status_change_refuse_a_voided_order(client, order):
    client.post(f"/orders/{order['id']}/void", json={"reason": "x"})
    returned = client.post(f"/orders/{order['id']}/return", json={"status": "REFUNDED"})
    assert (returned.status_code, _error(returned)["code"]) == (409, "ORDER_ALREADY_VOIDED")
    moved = client.post(f"/orders/{order['id']}/status", json={"status": "COMPLETED"})
    assert moved.status_code == 409
