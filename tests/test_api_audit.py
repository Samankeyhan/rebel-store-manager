"""GET /audit-log: read-only history of writes, with filters and pagination."""

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from db.connection import get_connection, init_db


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test_api_audit.db")
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


def _material(client, name="Audit Box"):
    response = client.post("/materials", json={"name": name, "type": "STOCK", "unit_cost": 1_800_005})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_an_empty_log_is_an_empty_page(client):
    body = client.get("/audit-log").json()
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_a_write_through_the_api_shows_up_with_its_operation_and_integer_money(client):
    material_id = _material(client)

    body = client.get("/audit-log", params={"entity_type": "materials"}).json()

    assert body["total"] == 1
    (entry,) = body["items"]
    assert (entry["action"], entry["operation"], entry["entity_id"]) == (
        "INSERT", "add_material", str(material_id)
    )
    assert entry["after"]["unit_cost"] == 1_800_005 and isinstance(entry["after"]["unit_cost"], int)
    assert entry["before"] is None and entry["actor"] is None and entry["op_id"]
    assert entry["ts"].count("-") == 2 and ":" in entry["ts"]


def test_filters_pagination_and_newest_first(client):
    first = _material(client, "First")
    _material(client, "Second")
    client.patch(f"/materials/{first}", json={"min_stock": 3})

    everything = client.get("/audit-log").json()
    assert everything["total"] == 3
    assert [e["id"] for e in everything["items"]] == sorted((e["id"] for e in everything["items"]), reverse=True)

    one_entity = client.get(
        "/audit-log", params={"entity_type": "materials", "entity_id": str(first)}
    ).json()
    assert [e["action"] for e in one_entity["items"]] == ["UPDATE", "INSERT"]
    assert one_entity["items"][0]["before"] == {"min_stock": None}
    assert one_entity["items"][0]["after"] == {"min_stock": 3}

    page = client.get("/audit-log", params={"limit": 2, "offset": 2}).json()
    assert (page["total"], len(page["items"]), page["limit"], page["offset"]) == (3, 1, 2, 2)

    by_op = client.get("/audit-log", params={"op_id": everything["items"][0]["op_id"]}).json()
    assert by_op["total"] == 1
    assert client.get("/audit-log", params={"operation": "add_material"}).json()["total"] == 2


def test_date_range_uses_local_days(client):
    _material(client)
    assert client.get("/audit-log", params={"start_date": "2000-01-01", "end_date": "2000-01-31"}).json()["total"] == 0
    assert client.get("/audit-log", params={"start_date": "2000-01-01"}).json()["total"] == 1


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 501}, {"offset": -1}, {"start_date": "10/10/2026"}, {"limit": "many"},
])
def test_bad_parameters_are_422(client, params):
    assert client.get("/audit-log", params=params).status_code == 422


def test_the_log_cannot_be_written_through_the_api(client):
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/audit-log").status_code == 405
