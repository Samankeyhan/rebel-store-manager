import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from db.connection import get_connection, init_db

CD_ALBUM_UNIT_COST = 202_030


@pytest.fixture
def api(tmp_path):
    """Self-contained TestClient fixture — does not touch tests/conftest.py.

    All setup goes through HTTP so the write path is what's exercised; `conn`
    is a separate connection used only to read back rows the API doesn't
    expose (e.g. stock_movements for PACKAGING).
    """
    db_path = str(tmp_path / "test_api_write.db")
    init_db(db_path)

    def override_get_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    read_conn = get_connection(db_path)
    client = TestClient(app)
    try:
        yield client, read_conn
    finally:
        read_conn.close()
        app.dependency_overrides.clear()


def _post(client, path, body, expected=201):
    response = client.post(path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def _create_material(client, name, type_, unit_cost, **extra):
    body = {"name": name, "type": type_, "unit_cost": unit_cost, **extra}
    return _post(client, "/materials", body)["id"]


def _create_product(client, name, category="OTHER", retail=1000, wholesale=800, **extra):
    body = {
        "name": name,
        "category": category,
        "retail_price": retail,
        "wholesale_price": wholesale,
        **extra,
    }
    return _post(client, "/products", body)["id"]


def _order(client, channel, product_id, quantity=1, unit_price=1000, expected=201, **extra):
    body = {
        "channel": channel,
        "items": [
            {"product_id": product_id, "quantity": quantity, "unit_price": unit_price}
        ],
        **extra,
    }
    response = client.post("/orders", json=body)
    assert response.status_code == expected, response.text
    return response.json()


def _error(response):
    return response.json()["error"]


@pytest.fixture
def cd_album(api):
    """The made-to-order CD Album from tests/test_made_to_order.py, built over HTTP."""
    client, _ = api
    ids = {
        "blank_cd": _create_material(client, "Blank CD", "STOCK", 53_393, initial_stock=100),
        "cd_case": _create_material(client, "CD Case", "STOCK", 77_333, initial_stock=105),
        "a3_print": _create_material(client, "A3 Print", "SERVICE", 80_000),
        "a4_print": _create_material(client, "A4 Print", "SERVICE", 40_000),
        "branding": _create_material(
            client, "Branding Sticker", "STOCK", 3_750, initial_stock=128
        ),
        "qr": _create_material(client, "QR Sticker", "STOCK", 1_290, initial_stock=186),
        "disc_dye": _create_material(client, "Disc Dye", "SERVICE", 10_000),
        "shrink_nylon": _create_material(
            client, "Shrink Nylon", "STOCK", 1_200_000, unit="kg", initial_stock=1
        ),
    }
    product_id = _create_product(
        client, "CD Album", "ALBUM", 570_000, 285_000, made_to_order=True
    )
    for key, qty in [
        ("blank_cd", 1),
        ("cd_case", 1),
        ("a3_print", 0.3333),
        ("a4_print", 0.5),
        ("branding", 1),
        ("qr", 1),
        ("disc_dye", 1),
        ("shrink_nylon", 0.008),
    ]:
        _post(
            client,
            f"/products/{product_id}/recipe/items",
            {"material_id": ids[key], "quantity_needed": qty},
        )
    return {"product_id": product_id, **ids}


@pytest.fixture
def shop(api):
    """A stocked product, two packaging kits (WEBSITE defaults to "Standard"),
    and one postage batch giving an estimate of 10,000."""
    client, _ = api

    product_id = _create_product(client, "Widget")
    _post(
        client,
        "/purchases/products",
        {"product_id": product_id, "quantity_bought": 10, "total_paid": 60_000},
    )

    box_id = _create_material(client, "Box", "STOCK", 5_000, initial_stock=50)
    tape_id = _create_material(client, "Tape", "STOCK", 1_000, initial_stock=100)

    standard_id = _post(client, "/packaging/kits", {"name": "Standard"})["id"]
    _post(client, f"/packaging/kits/{standard_id}/items", {"material_id": box_id, "quantity": 1})
    standard = _post(
        client, f"/packaging/kits/{standard_id}/items", {"material_id": tape_id, "quantity": 2}
    )
    assert standard["kit_cost"] == 7_000

    deluxe_id = _post(client, "/packaging/kits", {"name": "Deluxe"})["id"]
    deluxe = _post(
        client, f"/packaging/kits/{deluxe_id}/items", {"material_id": box_id, "quantity": 2}
    )
    assert deluxe["kit_cost"] == 10_000

    response = client.patch(
        "/settings/channels/WEBSITE", json={"default_packaging_kit_id": standard_id}
    )
    assert response.status_code == 200, response.text
    assert response.json()["default_packaging_kit_id"] == standard_id

    _post(client, "/postage/batches", {"total_paid": 100_000, "order_count": 10})
    assert client.get("/postage/estimate").json()["estimate"] == 10_000

    return {
        "product_id": product_id,
        "box_id": box_id,
        "tape_id": tape_id,
        "standard_id": standard_id,
        "deluxe_id": deluxe_id,
    }


def _packaging_movement_count(conn, order_id):
    return conn.execute(
        "SELECT COUNT(*) FROM stock_movements "
        "WHERE reason = 'PACKAGING' AND reference_order_id = ?",
        (order_id,),
    ).fetchone()[0]


# ------------------------------------------------------------------ creates


def test_create_product_returns_201_matching_get(api):
    client, _ = api
    created = _post(
        client,
        "/products",
        {"name": "Poster", "category": "POSTER", "retail_price": 1000, "wholesale_price": 700},
    )
    assert created["made_to_order"] == 0
    assert created["is_active"] == 1
    assert created == client.get(f"/products/{created['id']}").json()


def test_create_material_returns_201_matching_get(api):
    client, _ = api
    created = _post(
        client,
        "/materials",
        {"name": "Ink", "type": "STOCK", "unit_cost": 250, "unit": "ml", "initial_stock": 12.5},
    )
    assert created["current_stock"] == 12.5
    assert created == client.get(f"/materials/{created['id']}").json()


def test_create_supplier_returns_201_matching_get(api):
    client, _ = api
    created = _post(client, "/suppliers", {"name": "Acme Supplies", "website": "acme.test"})
    assert created["website"] == "acme.test"
    assert created == client.get(f"/suppliers/{created['id']}").json()


def test_create_kit_returns_201_matching_get(api):
    client, _ = api
    created = _post(client, "/packaging/kits", {"name": "Mailer"})
    assert created["items"] == []
    assert created["kit_cost"] == 0
    assert created == client.get(f"/packaging/kits/{created['id']}").json()


def test_create_postage_batch_returns_201_matching_list(api):
    client, _ = api
    created = _post(
        client,
        "/postage/batches",
        {"total_paid": 90_000, "order_count": 3, "paid_date": "2026-01-15", "notes": "Jan"},
    )
    assert created["paid_date"] == "2026-01-14 20:30:00"
    assert client.get("/postage/batches").json() == [created]


def test_create_expense_category_and_expense_return_201(api):
    client, _ = api
    category = _post(client, "/expense-categories", {"name": "Ads"})
    assert category["name"] == "Ads"
    assert category["is_active"] == 1

    expense = _post(
        client,
        "/expenses",
        {
            "expense_category_id": category["id"],
            "amount": 5_000,
            "expense_date": "2026-01-15",
            "description": "Campaign",
        },
    )
    assert expense["category_name"] == "Ads"
    assert expense["amount"] == 5_000
    assert client.get("/expenses").json() == [expense]


# ------------------------------------------------------------------ orders


def test_made_to_order_flow_over_http(api, cd_album):
    client, _ = api
    product_id = cd_album["product_id"]
    assert client.get(f"/products/{product_id}").json()["current_stock"] == 0

    order = _order(client, "IN_PERSON", product_id, 1, 570_000)

    assert order["items"][0]["unit_cost_at_time"] == CD_ALBUM_UNIT_COST
    stock = {m["name"]: m["current_stock"] for m in client.get("/materials").json()}
    assert stock["Blank CD"] == 99
    assert stock["CD Case"] == 104
    assert stock["Branding Sticker"] == 127
    assert stock["QR Sticker"] == 185
    assert stock["Shrink Nylon"] == 0.992
    assert stock["A3 Print"] is None  # SERVICE materials have no stock


def test_website_order_with_defaults_freezes_costs(api, shop):
    client, _ = api
    order = _order(client, "WEBSITE", shop["product_id"])["order"]

    assert order["shipping_charge"] == 180_000
    assert order["packaging_kit_id"] == shop["standard_id"]
    assert order["packaging_cost"] == 7_000
    assert order["postage_cost"] == 10_000
    assert order["stock_committed"] == 1


def test_packaging_kit_null_means_no_packaging(api, shop):
    client, conn = api
    order = _order(client, "WEBSITE", shop["product_id"], packaging_kit_id=None)["order"]

    assert order["packaging_kit_id"] is None
    assert order["packaging_cost"] == 0
    assert _packaging_movement_count(conn, order["id"]) == 0


def test_packaging_kit_default_uses_channel_kit(api, shop):
    client, conn = api
    order = _order(client, "WEBSITE", shop["product_id"], packaging_kit_id="default")["order"]

    assert order["packaging_kit_id"] == shop["standard_id"]
    assert order["packaging_cost"] == 7_000
    assert _packaging_movement_count(conn, order["id"]) == 2  # box + tape


def test_packaging_kit_explicit_id_uses_that_kit(api, shop):
    client, conn = api
    order = _order(
        client, "WEBSITE", shop["product_id"], packaging_kit_id=shop["deluxe_id"]
    )["order"]

    assert order["packaging_kit_id"] == shop["deluxe_id"]
    assert order["packaging_cost"] == 10_000
    assert _packaging_movement_count(conn, order["id"]) == 1


def test_packaging_kit_rejects_other_strings(api, shop):
    client, _ = api
    _order(client, "WEBSITE", shop["product_id"], packaging_kit_id="none", expected=422)


def test_shipping_charge_zero_is_a_real_zero(api, shop):
    client, _ = api
    order = _order(client, "WEBSITE", shop["product_id"], shipping_charge=0)["order"]
    assert order["shipping_charge"] == 0


def test_postage_cost_zero_is_a_real_zero(api, shop):
    client, _ = api
    order = _order(client, "WEBSITE", shop["product_id"], postage_cost=0)["order"]
    assert order["postage_cost"] == 0


def test_insufficient_stock_is_409_with_details(api, shop):
    client, _ = api
    response = client.post(
        "/orders",
        json={
            "channel": "IN_PERSON",
            "items": [{"product_id": shop["product_id"], "quantity": 11, "unit_price": 1000}],
        },
    )

    assert response.status_code == 409
    error = _error(response)
    assert error["type"] == "InsufficientStockError"
    assert error["details"] == {"item_name": "Widget", "needed": 11, "available": 10}
    # Nothing was written.
    assert client.get(f"/products/{shop['product_id']}").json()["current_stock"] == 10
    assert client.get("/orders").json() == []


def test_illegal_status_transition_is_409(api, shop):
    client, _ = api
    order_id = _order(client, "IN_PERSON", shop["product_id"])["order"]["id"]

    response = client.post(f"/orders/{order_id}/status", json={"status": "PENDING"})
    assert response.status_code == 409
    assert _error(response)["type"] == "ConflictError"


def test_status_update_commits_draft(api, shop):
    client, _ = api
    draft = _order(client, "IN_PERSON", shop["product_id"], status="DRAFT")["order"]
    assert draft["stock_committed"] == 0

    response = client.post(f"/orders/{draft['id']}/status", json={"status": "PAID"})
    assert response.status_code == 200
    assert response.json()["order"]["status"] == "PAID"
    assert response.json()["order"]["stock_committed"] == 1
    assert client.get(f"/products/{shop['product_id']}").json()["current_stock"] == 9


def test_refund_from_draft_is_409(api, shop):
    client, _ = api
    order_id = _order(client, "IN_PERSON", shop["product_id"], status="DRAFT")["order"]["id"]

    response = client.post(f"/orders/{order_id}/return", json={"status": "REFUNDED"})
    assert response.status_code == 409
    assert _error(response)["type"] == "ConflictError"


def test_refund_restores_stock(api, shop):
    client, _ = api
    order_id = _order(client, "IN_PERSON", shop["product_id"], 3)["order"]["id"]
    assert client.get(f"/products/{shop['product_id']}").json()["current_stock"] == 7

    response = client.post(
        f"/orders/{order_id}/return", json={"status": "REFUNDED", "reason": "Damaged"}
    )
    assert response.status_code == 200
    assert response.json()["order"]["status"] == "REFUNDED"
    assert client.get(f"/products/{shop['product_id']}").json()["current_stock"] == 10


def test_return_rejects_non_return_status(api, shop):
    client, _ = api
    order_id = _order(client, "IN_PERSON", shop["product_id"])["order"]["id"]
    response = client.post(f"/orders/{order_id}/return", json={"status": "PAID"})
    assert response.status_code == 422


# ------------------------------------------------------------------ distributions


def test_distribution_exceeding_profit_needs_allow_exceeding(api):
    client, _ = api
    _post(client, "/partners", {"name": "Partner A", "current_percentage": 60})
    _post(client, "/partners", {"name": "Partner B", "current_percentage": 40})
    body = {
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "total_amount_distributed": 1_000,
    }

    response = client.post("/distributions", json=body)
    assert response.status_code == 422
    assert _error(response)["field"] == "total_amount_distributed"
    assert client.get("/distributions").json() == []

    created = _post(client, "/distributions", {**body, "allow_exceeding": True})
    assert created["total_amount_distributed"] == 1_000
    assert sorted(s["amount"] for s in created["shares"]) == [400, 600]
    assert created == client.get(f"/distributions/{created['id']}").json()


# ------------------------------------------------------------------ recipes


def test_patch_recipe_item_without_cost_basis_keeps_per_batch(api):
    client, _ = api
    product_id = _create_product(client, "Vinyl", "VINYL")
    mastering_id = _create_material(client, "Mastering", "SERVICE", 5_000)
    _post(
        client,
        f"/products/{product_id}/recipe/items",
        {"material_id": mastering_id, "quantity_needed": 1, "cost_basis": "PER_BATCH"},
    )

    response = client.patch(
        f"/products/{product_id}/recipe/items/{mastering_id}", json={"quantity_needed": 2}
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["cost_basis"] == "PER_BATCH"
    assert item["quantity_needed"] == 2


def test_delete_recipe_item_returns_updated_recipe(api):
    client, _ = api
    product_id = _create_product(client, "Vinyl", "VINYL")
    sleeve_id = _create_material(client, "Sleeve", "STOCK", 100, initial_stock=10)
    label_id = _create_material(client, "Label", "STOCK", 10, initial_stock=10)
    for material_id in (sleeve_id, label_id):
        _post(
            client,
            f"/products/{product_id}/recipe/items",
            {"material_id": material_id, "quantity_needed": 1},
        )

    response = client.delete(f"/products/{product_id}/recipe/items/{sleeve_id}")

    assert response.status_code == 200
    assert [i["material_id"] for i in response.json()["items"]] == [label_id]
    assert response.json()["unit_cost_at_qty_1"] == 10


def test_delete_kit_item_returns_updated_kit(api, shop):
    client, _ = api
    response = client.delete(
        f"/packaging/kits/{shop['standard_id']}/items/{shop['tape_id']}"
    )
    assert response.status_code == 200
    assert [i["material_id"] for i in response.json()["items"]] == [shop["box_id"]]
    assert response.json()["kit_cost"] == 5_000


# ------------------------------------------------------------------ validation


@pytest.mark.parametrize("bad_value", [1000.5, 1000.0, "1000", True])
def test_non_int_money_is_422(api, bad_value):
    client, _ = api
    response = client.post(
        "/products",
        json={"name": "X", "category": "OTHER", "retail_price": bad_value, "wholesale_price": 1},
    )
    assert response.status_code == 422
    assert client.get("/products").json() == []


def test_float_unit_price_on_order_is_422(api, shop):
    client, _ = api
    _order(client, "IN_PERSON", shop["product_id"], unit_price=1000.5, expected=422)


def test_unknown_body_field_is_422(api):
    client, _ = api
    response = client.post(
        "/expenses", json={"category_id": 1, "amount": 100}
    )
    assert response.status_code == 422


def test_unknown_setting_key_is_422(api):
    client, _ = api
    response = client.put("/settings/default_shiping_charge", json={"value": 200_000})
    assert response.status_code == 422
    assert _error(response)["field"] == "key"
    assert client.get("/settings").json()["default_shipping_charge"] == 180_000


def test_put_setting_updates_value(api):
    client, _ = api
    response = client.put("/settings/default_shipping_charge", json={"value": 200_000})
    assert response.status_code == 200
    assert response.json()["default_shipping_charge"] == 200_000


# ------------------------------------------------------------------ misc writes


def test_production_date_is_stored(api, cd_album):
    client, _ = api
    batch = _post(
        client,
        "/production",
        {
            "product_id": cd_album["product_id"],
            "quantity_produced": 1,
            "production_date": "2026-01-15",
        },
    )
    assert batch["batch"]["production_date"] == "2026-01-14 20:30:00"
    assert batch["batch"]["unit_cost"] == CD_ALBUM_UNIT_COST


def test_patch_supplier_changes_only_sent_fields(api):
    client, _ = api
    supplier_id = _post(
        client, "/suppliers", {"name": "Acme", "phone": "0000", "notes": "keep"}
    )["id"]

    response = client.patch(f"/suppliers/{supplier_id}", json={"phone": None})
    assert response.status_code == 200
    assert response.json()["phone"] is None
    assert response.json()["notes"] == "keep"
    assert response.json()["name"] == "Acme"

    assert client.patch(f"/suppliers/{supplier_id}", json={"name": None}).status_code == 422


def test_deactivate_unknown_product_is_404(api):
    client, _ = api
    assert client.post("/products/999/deactivate").status_code == 404


def test_channel_settings_patch_only_changes_sent_fields(api, shop):
    client, _ = api
    response = client.patch("/settings/channels/WEBSITE", json={"applies_postage": 0})
    assert response.status_code == 200
    assert response.json()["applies_postage"] == 0
    assert response.json()["default_packaging_kit_id"] == shop["standard_id"]

    response = client.patch(
        "/settings/channels/WEBSITE", json={"default_packaging_kit_id": None}
    )
    assert response.json()["default_packaging_kit_id"] is None


def test_adjustment_create_returns_movement(api, shop):
    client, _ = api
    movement = _post(
        client,
        "/adjustments",
        {"item_type": "MATERIAL", "item_id": shop["box_id"], "quantity_change": -2, "reason": "WASTE"},
    )
    assert movement["item_name"] == "Box"
    assert movement["unit_cost_at_time"] == 5_000
    assert client.get(f"/materials/{shop['box_id']}").json()["current_stock"] == 48


# ------------------------------------------------------------------ invoice


def test_invoice_pdf(api, shop):
    client, _ = api
    order = _order(client, "WEBSITE", shop["product_id"])["order"]

    response = client.get(f"/orders/{order['id']}/invoice.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert f'filename="invoice_{order["invoice_number"]}.pdf"' in (
        response.headers["content-disposition"]
    )


def test_invoice_pdf_unknown_order_is_404(api):
    client, _ = api
    assert client.get("/orders/999/invoice.pdf").status_code == 404
