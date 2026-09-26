import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app
from db import packaging, postage
from db.adjustments import record_stock_adjustment
from db.connection import get_connection, init_db
from db.distributions import record_profit_distribution
from db.expenses import add_expense, add_expense_category
from db.materials import add_material
from db.orders import record_order
from db.partners import add_partner
from db.products import add_product
from db.purchases import record_material_purchase, record_product_purchase
from db.recipes import add_recipe_item
from db.reports import get_profit_and_loss
from db.suppliers import add_supplier


@pytest.fixture
def api(tmp_path):
    """Self-contained TestClient fixture — does not touch tests/conftest.py.

    Every simulated request opens its own connection against the same
    temp-file DB (via the overridden get_db dependency); `conn` here is a
    separate connection used only for seeding through real db/ functions.
    """
    db_path = str(tmp_path / "test_api.db")
    init_db(db_path)

    def override_get_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    seed_conn = get_connection(db_path)
    client = TestClient(app)
    try:
        yield client, seed_conn
    finally:
        seed_conn.close()
        app.dependency_overrides.clear()


@pytest.fixture
def seeded(api):
    client, conn = api

    supplier_id = add_supplier(conn, "Acme Supplies", phone="0912-000-0000")

    product_id = add_product(conn, "Widget", "OTHER", 1000, 800)
    record_product_purchase(conn, product_id, quantity_bought=20, total_paid=16_000,
                             supplier_id=supplier_id)

    material_id = add_material(conn, "Glue", "STOCK", unit_cost=0, initial_stock=0)
    record_material_purchase(conn, material_id, quantity_bought=100, total_paid=10_000,
                              supplier_id=supplier_id)

    kit_id = packaging.create_kit(conn, "Standard box")
    packaging.add_kit_item(conn, kit_id, material_id, 2)

    postage.record_postage_batch(conn, total_paid=100_000, order_count=10)

    ads_id = add_expense_category(conn, "Ads")
    add_expense(conn, ads_id, 5_000)

    record_stock_adjustment(conn, "MATERIAL", material_id, -1, "WASTE")

    order_id = record_order(
        conn, "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
    )

    draft_order_id = record_order(
        conn, "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
        status="DRAFT",
    )

    partner_id = add_partner(conn, "Alex", 100)
    distribution_id = record_profit_distribution(
        conn, "2020-01-01", "2020-01-31", 0, allow_exceeding=True
    )

    material_purchase_id = conn.execute(
        "SELECT id FROM material_purchases WHERE material_id = ?", (material_id,)
    ).fetchone()["id"]
    product_purchase_id = conn.execute(
        "SELECT id FROM product_purchases WHERE product_id = ?", (product_id,)
    ).fetchone()["id"]

    return {
        "client": client,
        "conn": conn,
        "supplier_id": supplier_id,
        "product_id": product_id,
        "material_id": material_id,
        "kit_id": kit_id,
        "order_id": order_id,
        "draft_order_id": draft_order_id,
        "partner_id": partner_id,
        "distribution_id": distribution_id,
        "material_purchase_id": material_purchase_id,
        "product_purchase_id": product_purchase_id,
    }


def test_health(api):
    client, _ = api
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok"}


def test_profit_and_loss_key_parity(seeded):
    client, conn = seeded["client"], seeded["conn"]
    expected_keys = set(
        get_profit_and_loss(conn, "2020-01-01", "2030-01-01").keys()
    )

    resp = client.get(
        "/reports/profit-and-loss",
        params={"start_date": "2020-01-01", "end_date": "2030-01-01"},
    )
    assert resp.status_code == 200
    assert set(resp.json().keys()) == expected_keys


def test_products_list_and_detail(seeded):
    client, product_id = seeded["client"], seeded["product_id"]

    listed = client.get("/products")
    assert listed.status_code == 200
    names = {p["name"] for p in listed.json()}
    assert "Widget" in names

    detail = client.get(f"/products/{product_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == product_id
    assert body["name"] == "Widget"
    assert body["made_to_order"] in (0, 1)


def test_materials_list_and_low_stock(seeded):
    client, material_id = seeded["client"], seeded["material_id"]

    listed = client.get("/materials")
    assert listed.status_code == 200
    assert any(m["id"] == material_id for m in listed.json())

    detail = client.get(f"/materials/{material_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Glue"

    low_stock = client.get("/materials/low-stock", params={"threshold": 1000})
    assert low_stock.status_code == 200
    assert any(m["id"] == material_id for m in low_stock.json())


def test_orders_list_and_detail(seeded):
    client = seeded["client"]
    order_id, draft_order_id = seeded["order_id"], seeded["draft_order_id"]

    listed = client.get("/orders", params={"channel": "INSTAGRAM"})
    assert listed.status_code == 200
    rows_by_id = {o["id"]: o for o in listed.json()}
    row = rows_by_id[order_id]
    assert row["customer_total"] > 0
    assert row["profit"] is not None
    # DRAFT orders commit nothing, so profit is meaningless — None, not 0.
    assert rows_by_id[draft_order_id]["profit"] is None

    detail = client.get(f"/orders/{order_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["order"]["id"] == order_id
    assert "items" in body and len(body["items"]) == 1
    assert body["customer_total"] == row["customer_total"]


def test_suppliers_list_and_detail(seeded):
    client, supplier_id = seeded["client"], seeded["supplier_id"]

    listed = client.get("/suppliers")
    assert listed.status_code == 200
    assert any(s["id"] == supplier_id for s in listed.json())

    detail = client.get(f"/suppliers/{supplier_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Acme Supplies"


def test_material_and_product_purchases(seeded):
    client = seeded["client"]

    material_list = client.get("/purchases/materials")
    assert material_list.status_code == 200
    assert len(material_list.json()) >= 1

    material_detail = client.get(
        f"/purchases/materials/{seeded['material_purchase_id']}"
    )
    assert material_detail.status_code == 200
    assert material_detail.json()["material_name"] == "Glue"

    product_list = client.get("/purchases/products")
    assert product_list.status_code == 200

    product_detail = client.get(
        f"/purchases/products/{seeded['product_purchase_id']}"
    )
    assert product_detail.status_code == 200
    assert product_detail.json()["product_name"] == "Widget"


def test_adjustments_list(seeded):
    client, material_id = seeded["client"], seeded["material_id"]

    resp = client.get("/adjustments", params={"item_type": "MATERIAL", "reason": "WASTE"})
    assert resp.status_code == 200
    assert any(a["item_id"] == material_id for a in resp.json())


def test_expenses_and_categories(seeded):
    client = seeded["client"]

    categories = client.get("/expense-categories")
    assert categories.status_code == 200
    assert any(c["name"] == "Ads" for c in categories.json())

    expenses = client.get("/expenses")
    assert expenses.status_code == 200
    assert any(e["category_name"] == "Ads" for e in expenses.json())


def test_packaging_kits_list_and_detail(seeded):
    client, kit_id = seeded["client"], seeded["kit_id"]

    listed = client.get("/packaging/kits")
    assert listed.status_code == 200
    assert any(k["id"] == kit_id for k in listed.json())

    detail = client.get(f"/packaging/kits/{kit_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["kit_cost"] >= 0
    assert len(body["items"]) == 1


def test_postage_batches_and_estimate(seeded):
    client = seeded["client"]

    batches = client.get("/postage/batches")
    assert batches.status_code == 200
    assert len(batches.json()) == 1

    estimate = client.get("/postage/estimate")
    assert estimate.status_code == 200
    body = estimate.json()
    assert body["estimate"] == 10_000
    assert body["window"] == 3


def test_partners_totals_and_payouts(seeded):
    client, partner_id = seeded["client"], seeded["partner_id"]

    listed = client.get("/partners")
    assert listed.status_code == 200
    assert any(p["id"] == partner_id for p in listed.json())

    totals = client.get("/partners/totals")
    assert totals.status_code == 200

    payouts = client.get(f"/partners/{partner_id}/payouts")
    assert payouts.status_code == 200


def test_distributions_list_detail_and_undistributed(seeded):
    client, distribution_id = seeded["client"], seeded["distribution_id"]

    listed = client.get("/distributions")
    assert listed.status_code == 200
    assert any(d["id"] == distribution_id for d in listed.json())

    detail = client.get(f"/distributions/{distribution_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == distribution_id
    assert len(body["shares"]) == 1

    undistributed = client.get(
        "/distributions/undistributed", params={"as_of": "2026-01-01"}
    )
    assert undistributed.status_code == 200
    assert undistributed.json()["as_of"] == "2026-01-01"


def test_settings(seeded):
    client = seeded["client"]

    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "Asia/Tehran"
    assert set(body["channels"]) == {
        "INSTAGRAM", "WEBSITE", "WHOLESALE", "IN_PERSON", "OTHER",
    }


def test_404_auto_raising_getter(seeded):
    client = seeded["client"]
    resp = client.get("/orders/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["type"] == "NotFoundError"


def test_404_manual_check_getter(seeded):
    client = seeded["client"]
    resp = client.get("/products/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["type"] == "NotFoundError"


def test_404_partner_payouts_manual_check(seeded):
    client = seeded["client"]
    resp = client.get("/partners/999999/payouts")
    assert resp.status_code == 404


def test_422_malformed_date(seeded):
    client = seeded["client"]
    resp = client.get("/orders", params={"start_date": "not-a-date"})
    assert resp.status_code == 422
    # FastAPI's own validation error shape, distinct from the custom
    # {"error": {...}} body the db/errors.py handlers produce.
    assert "detail" in resp.json()
    assert "error" not in resp.json()


def test_made_to_order_recipe_cost(api):
    """Replicates tests/test_made_to_order.py's cd_album_setup fixture
    inline (per instructions, rather than importing across test files) to
    verify the API surfaces the same recipe cost."""
    client, conn = api

    blank_cd_id = add_material(conn, "Blank CD", "STOCK", 53_393, initial_stock=100)
    cd_case_id = add_material(conn, "CD Case", "STOCK", 77_333, initial_stock=105)
    a3_print_id = add_material(conn, "A3 Print", "SERVICE", 80_000)
    a4_print_id = add_material(conn, "A4 Print", "SERVICE", 40_000)
    branding_id = add_material(conn, "Branding Sticker", "STOCK", 3_750, initial_stock=128)
    qr_id = add_material(conn, "QR Sticker", "STOCK", 1_290, initial_stock=186)
    disc_dye_id = add_material(conn, "Disc Dye", "SERVICE", 10_000)
    shrink_nylon_id = add_material(
        conn, "Shrink Nylon", "STOCK", 1_200_000, unit="kg", initial_stock=1
    )

    product_id = add_product(conn, "CD Album", "ALBUM", 570_000, 285_000, made_to_order=True)
    add_recipe_item(conn, product_id, blank_cd_id, 1)
    add_recipe_item(conn, product_id, cd_case_id, 1)
    add_recipe_item(conn, product_id, a3_print_id, 0.3333)
    add_recipe_item(conn, product_id, a4_print_id, 0.5)
    add_recipe_item(conn, product_id, branding_id, 1)
    add_recipe_item(conn, product_id, qr_id, 1)
    add_recipe_item(conn, product_id, disc_dye_id, 1)
    add_recipe_item(conn, product_id, shrink_nylon_id, 0.008)

    resp = client.get(f"/products/{product_id}/recipe")
    assert resp.status_code == 200
    body = resp.json()
    assert body["unit_cost_at_qty_1"] == 202_030
    assert len(body["items"]) == 8


def test_catalog(seeded):
    client = seeded["client"]

    resp = client.get("/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "products", "materials", "kits", "settings", "postage_estimate",
    }
    assert len(body["products"]) >= 1
    assert all("made_to_order" in p for p in body["products"])
