"""API: «ثبت بها» — POST /materials/{id}/cost and POST /products/{id}/cost (accounting rules section 2)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from api.deps import get_db
from api.main import app
from api.schemas.errors import ErrorEnvelope
from db.connection import get_connection, init_db
from tests.helpers import cat


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test_api_set_cost.db")
    init_db(db_path)

    def override_get_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    conn = get_connection(db_path)
    try:
        client = TestClient(app)
        client.category_id = cat(conn, "VINYL")
        yield client
    finally:
        conn.close()
        app.dependency_overrides.clear()


def _material(client, cost=0, stock=20, name="Sticker"):
    response = client.post(
        "/materials", json={"name": name, "type": "STOCK", "unit_cost": cost, "initial_stock": stock}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _product(client, name="LP"):
    response = client.post(
        "/products",
        json={"name": name, "category_id": client.category_id, "retail_price": 3000, "wholesale_price": 2000},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_a_material_gets_its_cost(client):
    material = _material(client)
    response = client.post(f"/materials/{material}/cost", json={"unit_cost": 500})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["unit_cost"], body["current_stock"]) == (500, 20)


def test_a_material_with_a_cost_is_a_typed_409(client):
    material = _material(client, cost=1_000, name="Box")
    response = client.post(f"/materials/{material}/cost", json={"unit_cost": 500})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "COST_ALREADY_SET"
    assert error["details"] == {"item_type": "MATERIAL", "item_id": material, "item_name": "Box", "unit_cost": 1_000}
    assert client.get(f"/materials/{material}").json()["unit_cost"] == 1_000


def test_a_material_cost_of_zero_is_a_422_on_unit_cost(client):
    material = _material(client)
    response = client.post(f"/materials/{material}/cost", json={"unit_cost": 0})
    assert response.status_code == 422
    assert response.json()["error"]["field"] == "unit_cost"
    assert client.get(f"/materials/{material}").json()["unit_cost"] == 0


@pytest.mark.parametrize("value", [1.5, "500", True])
def test_a_material_cost_must_be_an_integer(client, value):
    material = _material(client)
    response = client.post(f"/materials/{material}/cost", json={"unit_cost": value})
    assert response.status_code == 422


def test_a_material_cost_request_takes_no_other_field(client):
    material = _material(client)
    response = client.post(f"/materials/{material}/cost", json={"unit_cost": 500, "notes": "x"})
    assert response.status_code == 422


def test_an_unknown_material_is_a_404(client):
    assert client.post("/materials/999/cost", json={"unit_cost": 500}).status_code == 404


def test_a_product_gets_its_cost(client):
    product = _product(client)
    assert client.get(f"/products/{product}").json()["unit_cost"] is None
    response = client.post(f"/products/{product}/cost", json={"unit_cost": 250_000})
    assert response.status_code == 200, response.text
    assert response.json()["unit_cost"] == 250_000


def test_a_product_with_a_cost_is_a_typed_409(client):
    product = _product(client, name="Costed LP")
    assert client.post(f"/products/{product}/cost", json={"unit_cost": 250_000}).status_code == 200
    response = client.post(f"/products/{product}/cost", json={"unit_cost": 300_000})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "COST_ALREADY_SET"
    assert error["details"] == {"item_type": "PRODUCT", "item_id": product, "item_name": "Costed LP", "unit_cost": 250_000}
    assert client.get(f"/products/{product}").json()["unit_cost"] == 250_000


def test_a_product_cost_of_zero_is_a_422_on_unit_cost(client):
    product = _product(client)
    response = client.post(f"/products/{product}/cost", json={"unit_cost": 0})
    assert response.status_code == 422
    assert response.json()["error"]["field"] == "unit_cost"
    assert client.get(f"/products/{product}").json()["unit_cost"] is None


def test_an_unknown_product_is_a_404(client):
    assert client.post("/products/999/cost", json={"unit_cost": 500}).status_code == 404


def test_the_refusal_validates_against_the_typed_envelope(client):
    material = _material(client, cost=1_000)
    response = client.post(f"/materials/{material}/cost", json={"unit_cost": 500})
    envelope = TypeAdapter(ErrorEnvelope).validate_python(response.json())
    assert envelope.error.code == "COST_ALREADY_SET"
