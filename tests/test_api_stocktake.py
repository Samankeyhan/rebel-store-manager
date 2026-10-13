"""POST /stocktake/preview and POST /stocktake: the HTTP contract of a stocktake."""

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from api.deps import get_db
from api.main import app
from api.schemas.errors import ErrorEnvelope
from db.adjustments import record_stock_adjustment
from db.connection import get_connection, init_db
from db.materials import add_material
from db.products import add_product
from tests.helpers import cat

ENVELOPE = TypeAdapter(ErrorEnvelope)


@pytest.fixture
def shop(tmp_path):
    db_path = str(tmp_path / "stocktake.db")
    init_db(db_path)
    conn = get_connection(db_path)
    ids = {
        "lp": add_product(conn, "Fictional LP", cat(conn, "VINYL"), 3_000_000, 2_000_000),
        "tee": add_product(conn, "Fictional Tee", cat(conn, "TSHIRT"), 1_000_000, 500_000),
        "box": add_material(conn, "Fictional Box", "STOCK", 12_000, initial_stock=10),
        "print": add_material(conn, "Fictional Printing", "SERVICE", 90_000),
    }
    record_stock_adjustment(conn, "PRODUCT", ids["tee"], 4, "ADJUSTMENT", unit_cost=700_000)
    conn.commit()

    def override():
        c = get_connection(db_path)
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app), ids, conn
    finally:
        conn.close()
        app.dependency_overrides.clear()


def row(kind, item_id, counted, system, **extra):
    return {"item_type": kind, "item_id": item_id, "counted": counted, "system_quantity": system, **extra}


def snapshot(conn):
    return (
        conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
        [tuple(r) for r in conn.execute(
            "SELECT current_stock, unit_cost FROM products UNION ALL SELECT current_stock, unit_cost FROM materials")],
    )


def test_the_preview_writes_nothing_and_apply_writes_what_the_preview_showed(shop):
    client, ids, conn = shop
    body = {"stocktake_date": "2026-10-12", "note": "قفسه ۱", "items": [
        row("PRODUCT", ids["lp"], 12, 0, unit_cost=1_500_000),
        row("PRODUCT", ids["tee"], 3, 4),
        row("MATERIAL", ids["box"], 10, 10),
    ]}
    before = snapshot(conn)
    preview = client.post("/stocktake/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert snapshot(conn) == before
    plan = preview.json()
    assert plan["note"] == "شمارش موجودی ۱۴۰۵/۰۷/۲۰ — قفسه ۱"
    assert plan["unchanged_count"] == 1 and plan["unvalued_count"] == 0
    assert [(c["item_name"], c["difference"], c["value"], c["movement_id"]) for c in plan["corrections"]] == [
        ("Fictional LP", 12, 18_000_000, None), ("Fictional Tee", -1, -700_000, None)]
    assert plan["total_value"] == 17_300_000

    applied = client.post("/stocktake", json=body)
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert [c["movement_id"] is not None for c in result["corrections"]] == [True, True]
    assert {k: v for k, v in result.items() if k != "corrections"} == {k: v for k, v in plan.items() if k != "corrections"}
    stock = {r["id"]: r["current_stock"] for r in conn.execute("SELECT id, current_stock FROM products")}
    assert stock[ids["lp"]] == 12 and stock[ids["tee"]] == 3

    listed = client.get("/adjustments", params={"reason": "ADJUSTMENT"}).json()
    assert sum(a["notes"] == plan["note"] for a in listed) == 2  # plus the fixture's own opening adjustment


def test_a_failure_applies_nothing(shop):
    client, ids, conn = shop
    before = snapshot(conn)
    body = {"items": [row("PRODUCT", ids["tee"], 1, 4), row("PRODUCT", ids["lp"], 5, 0)]}  # the second needs a cost
    response = client.post("/stocktake", json=body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert (error["code"], error["field"]) == ("PRODUCT_NO_UNIT_COST", "items.1.unit_cost")
    assert error["details"] == {"product_id": ids["lp"], "product_name": "Fictional LP"}
    ENVELOPE.validate_python(response.json())
    assert snapshot(conn) == before


def test_a_stale_count_is_409_with_the_changed_items_and_writes_nothing(shop):
    client, ids, conn = shop
    before = snapshot(conn)
    response = client.post("/stocktake", json={"items": [row("PRODUCT", ids["tee"], 1, 9), row("MATERIAL", ids["box"], 8, 10)]})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "STOCKTAKE_STALE"
    assert error["details"]["items"] == [
        {"item_type": "PRODUCT", "item_id": ids["tee"], "item_name": "Fictional Tee", "expected": 9.0, "actual": 4.0}]
    ENVELOPE.validate_python(response.json())
    assert snapshot(conn) == before


@pytest.mark.parametrize("counted, code", [
    (2.5, "QUANTITY_NOT_WHOLE"),  # a product: the db rule
    (-1, "QUANTITY_OUT_OF_RANGE"),  # the schema bound
    (10**9 + 1, "QUANTITY_OUT_OF_RANGE"),
    ("3", "VALIDATION_FAILED"),
    (True, "VALIDATION_FAILED"),
])
def test_a_bad_count_is_a_422_on_the_counted_field(shop, counted, code):
    client, ids, _ = shop
    response = client.post("/stocktake", json={"items": [row("PRODUCT", ids["tee"], counted, 4)]})
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert (error["code"], error["field"]) == (code, "items.0.counted")
    ENVELOPE.validate_python(response.json())


def test_a_material_may_be_counted_in_fractions(shop):
    client, ids, conn = shop
    response = client.post("/stocktake", json={"items": [row("MATERIAL", ids["box"], 7.25, 10)]})
    assert response.status_code == 200 and response.json()["corrections"][0]["difference"] == -2.75
    assert conn.execute("SELECT current_stock FROM materials WHERE id = ?", (ids["box"],)).fetchone()[0] == 7.25


@pytest.mark.parametrize("body, field", [
    ({"items": []}, "items"),
    ({"items": [row("MATERIAL", 1, 1, 0)] * 2001}, "items"),
    ({"items": [row("THING", 1, 1, 0)]}, "items.0.item_type"),
    ({"items": [{**row("MATERIAL", 1, 1, 0), "surprise": 1}]}, "items.0.surprise"),
    ({"items": [row("MATERIAL", 1, 1, 0)], "note": "x" * 201}, "note"),
    ({"items": [row("MATERIAL", 1, 1, 0)], "stocktake_date": "13-10-2026"}, "stocktake_date"),
])
def test_request_shape_errors_are_in_the_envelope(shop, body, field):
    client, _, _ = shop
    response = client.post("/stocktake/preview", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["field"] == field
    ENVELOPE.validate_python(response.json())


def test_services_unknown_items_duplicates_and_future_dates(shop):
    client, ids, _ = shop
    cases = [
        ([row("MATERIAL", ids["print"], 1, 0)], None, 422, "items.0.item_id"),
        ([row("PRODUCT", 9999, 1, 0)], None, 404, None),
        ([row("PRODUCT", ids["tee"], 1, 4), row("PRODUCT", ids["tee"], 2, 4)], None, 422, "items.1.item_id"),
        ([row("PRODUCT", ids["tee"], 1, 4)], "2999-01-01", 422, "stocktake_date"),
    ]
    for items, date, status, field in cases:
        response = client.post("/stocktake", json={"items": items, **({"stocktake_date": date} if date else {})})
        assert response.status_code == status, response.text
        assert response.json()["error"]["field"] == field
        ENVELOPE.validate_python(response.json())
    assert response.json()["error"]["code"] == "DATE_IN_FUTURE"


def test_a_unit_cost_over_the_limit_is_amount_too_large(shop):
    client, ids, _ = shop
    response = client.post("/stocktake", json={"items": [row("PRODUCT", ids["lp"], 3, 0, unit_cost=2**53)]})
    assert response.status_code == 422
    assert (response.json()["error"]["code"], response.json()["error"]["field"]) == ("AMOUNT_TOO_LARGE", "items.0.unit_cost")


def test_the_integrity_check_is_ok_after_a_stocktake_over_http(shop, capsys):
    from tools.integrity_check import __main__ as cli

    client, ids, conn = shop
    body = {"items": [row("PRODUCT", ids["lp"], 12, 0, unit_cost=1_500_000), row("MATERIAL", ids["box"], 4.5, 10)]}
    assert client.post("/stocktake", json=body).status_code == 200
    path = next(r["file"] for r in conn.execute("PRAGMA database_list") if r["name"] == "main")
    assert cli.main(["--db", path]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "OK"
