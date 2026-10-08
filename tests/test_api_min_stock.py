"""API: min_stock on POST/PATCH /materials and GET /materials/low-stock."""

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from db.connection import get_connection, init_db


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test_api_min_stock.db")
    init_db(db_path)

    def override_get_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _create(client, name, stock=None, type_="STOCK", expected=201, **extra):
    body = {"name": name, "type": type_, "unit_cost": 1000, **extra}
    if stock is not None:
        body["initial_stock"] = stock
    response = client.post("/materials", json=body)
    assert response.status_code == expected, response.text
    return response.json()


def _error_field(response) -> str | None:
    """The field of a 422: pydantic's loc or the db ValidationError envelope."""
    body = response.json()
    if "detail" in body:
        return body["detail"][0]["loc"][-1]
    return body["error"]["field"]


def test_create_with_min_stock(client):
    created = _create(client, "Test Box", stock=3, min_stock=5)
    assert created["min_stock"] == 5
    assert created["is_low_stock"] == 1
    fractional = _create(client, "Test Filler", stock=3, min_stock=2.5)
    assert fractional["min_stock"] == 2.5
    assert fractional["is_low_stock"] == 0
    plain = _create(client, "Test Tape", stock=3)
    assert plain["min_stock"] is None
    assert plain["is_low_stock"] == 0


@pytest.mark.parametrize("bad", [-1, "5", True, None])
def test_create_refuses_bad_min_stock(client, bad):
    if bad is None:  # SERVICE with a minimum
        response = client.post(
            "/materials", json={"name": "Test Print", "type": "SERVICE", "unit_cost": 1000, "min_stock": 0}
        )
    else:
        response = client.post(
            "/materials",
            json={"name": "Test Box", "type": "STOCK", "unit_cost": 1000, "initial_stock": 1, "min_stock": bad},
        )
    assert response.status_code == 422, response.text
    assert _error_field(response) == "min_stock"
    assert client.get("/materials", params={"active_only": False}).json() == []


def test_patch_set_clear_omit(client):
    material = _create(client, "Test Box", stock=4)
    url = f"/materials/{material['id']}"

    set_ = client.patch(url, json={"min_stock": 4})
    assert set_.status_code == 200, set_.text
    assert set_.json()["min_stock"] == 4
    assert set_.json()["is_low_stock"] == 1
    assert client.get(url).json() == set_.json()

    omitted = client.patch(url, json={})
    assert omitted.status_code == 200
    assert omitted.json()["min_stock"] == 4

    cleared = client.patch(url, json={"min_stock": None})
    assert cleared.status_code == 200
    assert cleared.json()["min_stock"] is None
    assert cleared.json()["is_low_stock"] == 0


@pytest.mark.parametrize("body", [{"min_stock": -0.5}, {"min_stock": "3"}, {"min_stock": False}])
def test_patch_refuses_bad_min_stock(client, body):
    material = _create(client, "Test Box", stock=4, min_stock=2)
    response = client.patch(f"/materials/{material['id']}", json=body)
    assert response.status_code == 422, response.text
    assert _error_field(response) == "min_stock"
    assert client.get(f"/materials/{material['id']}").json()["min_stock"] == 2


def test_patch_service_refuses_min_stock(client):
    service = _create(client, "Test Print", type_="SERVICE")
    response = client.patch(f"/materials/{service['id']}", json={"min_stock": 1})
    assert response.status_code == 422, response.text
    assert _error_field(response) == "min_stock"


def test_patch_unknown_field_and_missing_material(client):
    material = _create(client, "Test Box", stock=4)
    response = client.patch(f"/materials/{material['id']}", json={"unit_cost": 5})
    assert response.status_code == 422
    assert client.patch("/materials/9999", json={"min_stock": 1}).status_code == 404


def test_low_stock_endpoint_uses_each_minimum(client):
    at_min = _create(client, "A at min", stock=5, min_stock=5)
    below = _create(client, "B below", stock=1, min_stock=4)
    _create(client, "C above", stock=9, min_stock=5)
    out_no_min = _create(client, "D out", stock=0)
    _create(client, "E plenty no min", stock=20)
    _create(client, "F service", type_="SERVICE")
    inactive = _create(client, "G inactive", stock=0, min_stock=3)
    assert client.post(f"/materials/{inactive['id']}/deactivate").status_code == 200

    response = client.get("/materials/low-stock")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [r["id"] for r in rows] == [out_no_min["id"], below["id"], at_min["id"]]
    assert {k: rows[1][k] for k in ("name", "unit", "current_stock", "min_stock")} == {
        "name": "B below",
        "unit": "piece",
        "current_stock": 1,
        "min_stock": 4,
    }

    listed = client.get("/materials", params={"active_only": False}).json()
    assert {m["id"] for m in listed if m["is_low_stock"] == 1} == {r["id"] for r in rows}


def test_low_stock_endpoint_empty(client):
    _create(client, "Test Box", stock=9, min_stock=5)
    response = client.get("/materials/low-stock")
    assert response.status_code == 200
    assert response.json() == []


def test_low_stock_threshold_keeps_legacy_behaviour(client):
    _create(client, "B high min", stock=50, min_stock=100)
    low = _create(client, "A low", stock=5)
    rows = client.get("/materials/low-stock", params={"threshold": 10}).json()
    assert [r["id"] for r in rows] == [low["id"]]


def test_catalog_carries_the_new_fields(client):
    _create(client, "Test Box", stock=1, min_stock=2)
    response = client.get("/catalog")
    assert response.status_code == 200, response.text
    (material,) = response.json()["materials"]
    assert material["min_stock"] == 2
    assert material["is_low_stock"] == 1
