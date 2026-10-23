"""PATCH / DELETE /expenses/{id} and /postage/batches/{id}: the HTTP contract of fixing a mistaken entry."""

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from api.main import app
from api.schemas.errors import ErrorEnvelope

ENVELOPE = TypeAdapter(ErrorEnvelope)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _error(response):
    ENVELOPE.validate_python(response.json())
    return response.json()["error"]


@pytest.fixture
def expense(client):
    category = client.post("/expense-categories", json={"name": "Ads"}).json()
    created = client.post(
        "/expenses",
        json={"expense_category_id": category["id"], "amount": 1_000, "expense_date": "2026-01-10", "description": "x"},
    )
    assert created.status_code == 201
    return created.json()


@pytest.fixture
def batch(client):
    created = client.post(
        "/postage/batches", json={"total_paid": 900, "order_count": 3, "paid_date": "2026-01-10", "notes": "n"}
    )
    assert created.status_code == 201
    return created.json()


def _close_january(client):
    assert client.post("/partners", json={"name": "Solo", "current_percentage": 100}).status_code == 201
    body = {"period_start": "2026-01-01", "period_end": "2026-01-31", "total_amount_distributed": 0, "allow_exceeding": True}
    assert client.post("/distributions", json=body).status_code == 201


# ------------------------------------------------------------------ expenses


def test_patch_expense_returns_the_updated_row(client, expense):
    response = client.patch(f"/expenses/{expense['id']}", json={"amount": 2_500, "description": None})
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] == 2_500 and body["description"] is None
    assert body["expense_category_id"] == expense["expense_category_id"]


def test_patch_expense_unknown_id_and_category_are_404(client, expense):
    assert client.patch("/expenses/999", json={"amount": 1}).status_code == 404
    assert client.delete("/expenses/999").status_code == 404
    response = client.patch(f"/expenses/{expense['id']}", json={"expense_category_id": 999})
    assert response.status_code == 404


def test_patch_expense_request_shape_errors_are_422(client, expense):
    url = f"/expenses/{expense['id']}"
    assert client.patch(url, json={"amount": 1.5}).status_code == 422
    assert client.patch(url, json={"nope": 1}).status_code == 422
    response = client.patch(url, json={"amount": None})
    assert response.status_code == 422
    assert _error(response)["field"] == "amount" or _error(response)["code"] == "VALIDATION_FAILED"


def test_patch_expense_future_date_is_date_in_future(client, expense):
    response = client.patch(f"/expenses/{expense['id']}", json={"expense_date": "2999-01-01"})
    assert response.status_code == 422
    error = _error(response)
    assert error["code"] == "DATE_IN_FUTURE" and error["field"] == "expense_date"


def test_post_expense_future_date_is_date_in_future(client, expense):
    body = {"expense_category_id": expense["expense_category_id"], "amount": 1, "expense_date": "2999-01-01"}
    response = client.post("/expenses", json=body)
    assert response.status_code == 422 and _error(response)["code"] == "DATE_IN_FUTURE"


def test_patch_and_delete_expense_on_a_closed_day_are_409(client, expense):
    _close_january(client)
    url = f"/expenses/{expense['id']}"
    for response in (client.patch(url, json={"amount": 1}), client.delete(url)):
        assert response.status_code == 409
        error = _error(response)
        assert error["code"] == "PERIOD_ALREADY_DISTRIBUTED"
        assert error["details"]["period_end"] == "2026-01-31" and error["details"]["date"] == "2026-01-10"
    assert client.patch(url, json={"description": "still fine"}).status_code == 200


def test_delete_expense_is_204_and_removes_it(client, expense):
    assert client.delete(f"/expenses/{expense['id']}").status_code == 204
    assert client.get("/expenses").json() == []


# ------------------------------------------------------------------ postage


def test_patch_postage_batch_returns_the_updated_row_and_moves_the_estimate(client, batch):
    assert client.get("/postage/estimate").json()["estimate"] == 300
    response = client.patch(f"/postage/batches/{batch['id']}", json={"total_paid": 1_500, "notes": None})
    assert response.status_code == 200
    assert response.json()["total_paid"] == 1_500 and response.json()["notes"] is None
    assert client.get("/postage/estimate").json()["estimate"] == 500


def test_patch_postage_batch_errors(client, batch):
    assert client.patch("/postage/batches/999", json={"notes": "x"}).status_code == 404
    assert client.delete("/postage/batches/999").status_code == 404
    url = f"/postage/batches/{batch['id']}"
    response = client.patch(url, json={"order_count": 0})
    assert response.status_code == 422 and _error(response)["field"] == "order_count"
    assert client.patch(url, json={"total_paid": "1"}).status_code == 422
    response = client.patch(url, json={"paid_date": "2999-01-01"})
    assert response.status_code == 422
    assert (_error(response)["code"], _error(response)["field"]) == ("DATE_IN_FUTURE", "paid_date")


def test_patch_and_delete_postage_batch_on_a_closed_day_are_409(client, batch):
    _close_january(client)
    url = f"/postage/batches/{batch['id']}"
    for response in (client.patch(url, json={"total_paid": 1}), client.delete(url)):
        assert response.status_code == 409
        assert _error(response)["code"] == "PERIOD_ALREADY_DISTRIBUTED"
    assert client.patch(url, json={"order_count": 9, "notes": "ok"}).status_code == 200


def test_delete_postage_batch_is_204_and_resets_the_estimate(client, batch):
    assert client.delete(f"/postage/batches/{batch['id']}").status_code == 204
    assert client.get("/postage/batches").json() == []
    assert client.get("/postage/estimate").json()["estimate"] == 0
