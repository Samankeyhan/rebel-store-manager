"""API: waste of a service, POST /adjustments/service-waste (accounting rules section 8)."""

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from db.connection import get_connection, init_db


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test_api_service_waste.db")
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


def _service(client, cost=90_000, name="Fictional Printing"):
    response = client.post("/materials", json={"name": name, "type": "SERVICE", "unit_cost": cost, "unit": "sheet"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_it_records_a_waste_with_no_stock_change(client):
    service = _service(client)
    response = client.post(
        "/adjustments/service-waste",
        json={"material_id": service, "quantity": 2, "notes": "failed job", "movement_date": "2026-10-01"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["item_type"], body["item_id"], body["quantity_change"], body["reason"]) == ("MATERIAL", service, -2, "WASTE")
    assert body["unit_cost_at_time"] == 90_000
    assert body["item_name"] == "Fictional Printing"
    material = client.get(f"/materials/{service}").json()
    assert material["current_stock"] is None and material["unit_cost"] == 90_000


def test_the_price_override_is_stored(client):
    service = _service(client)
    body = client.post("/adjustments/service-waste", json={"material_id": service, "quantity": 0.5, "unit_cost": 333}).json()
    assert (body["quantity_change"], body["unit_cost_at_time"]) == (-0.5, 333)


def test_it_shows_in_the_history_and_the_waste_report(client):
    service = _service(client)
    client.post("/adjustments/service-waste", json={"material_id": service, "quantity": 3, "movement_date": "2026-10-01"})
    history = client.get("/adjustments", params={"reason": "WASTE"}).json()
    assert [(row["item_id"], row["quantity_change"]) for row in history] == [(service, -3)]
    report = client.get("/reports/waste", params={"start_date": "2026-10-01", "end_date": "2026-10-31"}).json()
    assert [(row["item_id"], row["cost"]) for row in report] == [(service, 270_000)]
    pnl = client.get("/reports/profit-and-loss", params={"start_date": "2026-10-01", "end_date": "2026-10-31"}).json()
    assert pnl["waste_cost"] == 270_000


def test_a_service_without_a_cost_has_its_code_and_details(client):
    service = _service(client, cost=0, name="Fictional Free Service")
    response = client.post("/adjustments/service-waste", json={"material_id": service, "quantity": 1})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "MATERIAL_NO_UNIT_COST"
    assert error["details"] == {"material_id": service, "material_name": "Fictional Free Service"}


def test_a_future_date_is_422_with_its_code(client):
    service = _service(client)
    response = client.post(
        "/adjustments/service-waste", json={"material_id": service, "quantity": 1, "movement_date": "2999-01-01"}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert (error["code"], error["field"]) == ("DATE_IN_FUTURE", "movement_date")


def test_a_stock_material_and_a_missing_material_are_refused(client):
    stock = client.post("/materials", json={"name": "Fictional Ink", "type": "STOCK", "unit_cost": 100, "initial_stock": 5}).json()["id"]
    assert client.post("/adjustments/service-waste", json={"material_id": stock, "quantity": 1}).status_code == 422
    assert client.post("/adjustments/service-waste", json={"material_id": 999, "quantity": 1}).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"quantity": 0},
        {"quantity": -1},
        {"quantity": "2"},
        {"quantity": True},
        {"quantity": 1, "unit_cost": 1.5},
        {"quantity": 1, "unit_cost": "100"},
        {"quantity": 1, "unit_cost": 0},
        {"quantity": 1, "extra": 1},
        {"quantity": 1, "movement_date": "10/01/2026"},
        {},
    ],
)
def test_a_bad_body_is_422_and_writes_nothing(client, body):
    service = _service(client)
    response = client.post("/adjustments/service-waste", json={"material_id": service, **body})
    assert response.status_code == 422, response.text
    assert client.get("/adjustments").json() == []


def test_the_stock_adjustment_endpoint_still_refuses_a_service(client):
    service = _service(client)
    response = client.post(
        "/adjustments", json={"item_type": "MATERIAL", "item_id": service, "quantity_change": -1, "reason": "WASTE"}
    )
    assert response.status_code == 422


def test_a_material_type_cannot_be_patched(client):
    service = _service(client)
    response = client.patch(f"/materials/{service}", json={"type": "STOCK"})
    assert response.status_code == 422
    assert client.get(f"/materials/{service}").json()["type"] == "SERVICE"
