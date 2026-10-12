"""A name that differs only in spelling is refused over HTTP: 409 with a stable code and
{entity, existing_id}; `name_key` never appears in a response."""

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from db.connection import get_connection, init_db

ARABIC = "كتاب ٣"
PERSIAN = "کتاب 3"


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "api_names.db")
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


def _category_id(client):
    return client.get("/categories", params={"kind": "PRODUCT"}).json()[0]["id"]


def _bodies(client):
    return [
        ("/products", {"name": ARABIC, "category_id": _category_id(client), "retail_price": 3000, "wholesale_price": 2000}, "NAME_DUPLICATE", "product"),
        ("/materials", {"name": ARABIC, "type": "STOCK", "unit_cost": 1000}, "NAME_DUPLICATE", "material"),
        ("/suppliers", {"name": ARABIC}, "NAME_DUPLICATE", "supplier"),
        ("/partners", {"name": ARABIC, "current_percentage": 10}, "NAME_DUPLICATE", "partner"),
        ("/categories", {"kind": "PRODUCT", "name": ARABIC}, "CATEGORY_DUPLICATE_NAME", "category"),
        ("/payment-methods", {"name": ARABIC, "settlement_rule": "IMMEDIATE"}, "PAYMENT_METHOD_DUPLICATE_NAME", "payment_method"),
        ("/packaging/kits", {"name": ARABIC}, "NAME_DUPLICATE", "packaging_kit"),
        ("/expense-categories", {"name": ARABIC}, "NAME_DUPLICATE", "expense_category"),
    ]


def test_a_spelling_variant_is_409_with_code_and_existing_id_and_no_name_key_leaks(client):
    for path, body, code, entity in _bodies(client):
        created = client.post(path, json=body)
        assert created.status_code == 201, (path, created.text)
        assert "name_key" not in created.text, path
        first_id = created.json()["id"]

        again = client.post(path, json={**body, "name": PERSIAN})
        assert again.status_code == 409, (path, again.text)
        error = again.json()["error"]
        assert error["code"] == code, path
        assert error["details"] == {"entity": entity, "existing_id": first_id}, path


def test_listing_never_exposes_name_key(client):
    for path, body, _, _ in _bodies(client):
        client.post(path, json=body)
    for path in ("/products", "/materials", "/suppliers", "/partners", "/payment-methods"):
        response = client.get(path)
        assert response.status_code == 200 and "name_key" not in response.text, path
    assert "name_key" not in client.get("/categories", params={"kind": "PRODUCT"}).text
    assert "name_key" not in client.get("/categories/tree", params={"kind": "PRODUCT"}).text
    assert "name_key" not in client.get("/packaging/kits").text


def test_rename_to_a_variant_of_another_is_409_and_nothing_changes(client):
    other = client.post("/suppliers", json={"name": ARABIC}).json()["id"]
    mine = client.post("/suppliers", json={"name": "Mine"}).json()["id"]
    response = client.patch(f"/suppliers/{mine}", json={"name": PERSIAN})
    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"entity": "supplier", "existing_id": other}
    assert client.get(f"/suppliers/{mine}").json()["name"] == "Mine"
    assert client.patch(f"/suppliers/{mine}", json={"name": "Mine 2"}).status_code == 200


def test_the_error_code_is_in_the_openapi_enum(client):
    assert "NAME_DUPLICATE" in client.get("/openapi.json").json()["components"]["schemas"]["ErrorCode"]["enum"]
