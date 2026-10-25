"""The HTTP contract of purchase edit, cancel preview, cancel and correct (accounting rules section 23), with typed
error envelopes."""

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
def world(client):
    paper = client.post("/materials", json={"name": "Api Paper", "type": "STOCK", "unit_cost": 0}).json()["id"]
    service = client.post("/materials", json={"name": "Api Printing", "type": "SERVICE", "unit_cost": 70}).json()["id"]
    acme = client.post("/suppliers", json={"name": "Api Acme"}).json()["id"]
    other = client.post("/suppliers", json={"name": "Api Other"}).json()["id"]
    return {"paper": paper, "service": service, "acme": acme, "other": other}


def line(item_id, quantity=10, total=1000, kind="MATERIAL"):
    return {"kind": kind, "item_id": item_id, "quantity_bought": quantity, "total_paid": total}


def _buy(client, world, lines, **body):
    body = {"lines": lines, "supplier_id": world["acme"], "purchase_date": DAY, **body}
    response = client.post("/purchases", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_patch_changes_only_the_fields_sent(client, world):
    purchase = _buy(client, world, [line(world["paper"])])
    patched = client.patch(f"/purchases/{purchase['id']}", json={"notes": "fixed"})
    assert patched.status_code == 200 and patched.json()["notes"] == "fixed" and patched.json()["supplier_id"] == world["acme"]
    moved = client.patch(f"/purchases/{purchase['id']}", json={"supplier_id": world["other"], "purchase_date": "2026-10-11"})
    assert moved.status_code == 200 and moved.json()["supplier_id"] == world["other"]
    assert moved.json()["payments"][0]["payment_date"] == moved.json()["purchase_date"]  # the payment made with it moved
    assert client.patch(f"/purchases/{purchase['id']}", json={"invoice_number": "x"}).status_code == 422
    assert client.patch("/purchases/999", json={"notes": "x"}).status_code == 404


def test_the_preview_lists_lines_payments_and_blockers(client, world):
    purchase = _buy(client, world, [line(world["paper"], 10, 4000), line(world["service"], 2, 400)])
    preview = client.get(f"/purchases/{purchase['id']}/cancel-preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert [b["code"] for b in body["blockers"]] == ["PURCHASE_HAS_PAYMENTS"]
    assert body["blockers"][0]["details"]["shared"] == 0
    paper, printing = body["lines"]
    assert (paper["stock_before"], paper["stock_after"], paper["cost_before"], paper["cost_after"]) == (10, 0, 400, 0)
    assert (printing["item_type"], printing["stock_before"], printing["cost_before"], printing["cost_after"]) == ("SERVICE", None, 200, 70)
    assert [(p["amount"], p["method"], p["shared"]) for p in body["payments"]] == [(4400, "OTHER", 0)]
    assert body["paid"] == 4400


def test_cancel_needs_the_tick_for_payments_and_then_takes_them(client, world):
    purchase = _buy(client, world, [line(world["paper"])])
    refused = client.post(f"/purchases/{purchase['id']}/cancel", json={"reason": "twice"})
    assert refused.status_code == 409
    error = _error(refused)
    assert error["code"] == "PURCHASE_HAS_PAYMENTS" and error["details"]["paid"] == 1000
    done = client.post(f"/purchases/{purchase['id']}/cancel", json={"reason": "twice", "with_payments": True})
    assert done.status_code == 200, done.text
    assert (done.json()["status"], done.json()["cancel_reason"], done.json()["payments"]) == ("CANCELLED", "twice", [])
    assert client.get("/supplier-payments").json() == []
    again = client.post(f"/purchases/{purchase['id']}/cancel", json={"reason": "x"})
    assert again.status_code == 409 and _error(again)["code"] == "PURCHASE_ALREADY_CANCELLED"


def test_a_blank_reason_is_422(client, world):
    purchase = _buy(client, world, [line(world["paper"])], payment={"mode": "NONE"})
    response = client.post(f"/purchases/{purchase['id']}/cancel", json={"reason": "  "})
    assert response.status_code == 422
    assert (_error(response)["code"], _error(response)["field"]) == ("VOID_REASON_REQUIRED", "reason")
    assert client.post(f"/purchases/{purchase['id']}/cancel", json={}).status_code == 422


def test_the_cancelled_list_and_the_summary(client, world):
    keep = _buy(client, world, [line(world["paper"], 1, 100)], payment={"mode": "NONE"})
    gone = _buy(client, world, [line(world["service"], 1, 300)], payment={"mode": "NONE"})
    assert client.post(f"/purchases/{gone['id']}/cancel", json={"reason": "x"}).status_code == 200
    assert [p["id"] for p in client.get("/purchases").json()] == [keep["id"]]
    assert {p["id"] for p in client.get("/purchases", params={"include_cancelled": True}).json()} == {keep["id"], gone["id"]}
    summary = client.get("/reports/purchases").json()
    assert (summary["service_purchases_total"], summary["purchase_invoices_count"]) == (0, 1)


def test_a_later_purchase_refuses_with_its_invoice_named(client, world):
    first = _buy(client, world, [line(world["paper"])], payment={"mode": "NONE"})
    later = _buy(client, world, [line(world["paper"], 1, 300)], payment={"mode": "NONE"})
    response = client.post(f"/purchases/{first['id']}/cancel", json={"reason": "x"})
    assert response.status_code == 409
    error = _error(response)
    assert error["code"] == "PURCHASE_COST_CHANGED_SINCE"
    assert error["details"]["later"][0]["invoice_number"] == later["invoice_number"] and error["details"]["line_index"] == 0


def test_correct_returns_the_new_purchase_and_links_both(client, world):
    old = _buy(client, world, [line(world["paper"], 10, 4000)], payment={"mode": "PARTIAL", "amount": 1000})
    response = client.post(f"/purchases/{old['id']}/correct", json={
        "reason": "wrong price", "lines": [line(world["paper"], 10, 5000)], "supplier_id": world["acme"], "purchase_date": DAY,
        "payment": {"mode": "NONE"},
    })
    assert response.status_code == 201, response.text
    new = response.json()
    assert (new["replaces_invoice_id"], new["total"], new["paid"], new["payment_status"]) == (old["id"], 5000, 1000, "PARTIAL")
    old_now = client.get(f"/purchases/{old['id']}").json()
    assert (old_now["status"], old_now["replaced_by_invoice_id"]) == ("CANCELLED", new["id"])


def test_a_correction_below_what_was_paid_is_422_and_changes_nothing(client, world):
    old = _buy(client, world, [line(world["paper"], 10, 4000)])
    response = client.post(f"/purchases/{old['id']}/correct", json={
        "reason": "x", "lines": [line(world["paper"], 10, 3000)], "supplier_id": world["acme"], "purchase_date": DAY,
    })
    assert response.status_code == 422
    error = _error(response)
    assert (error["code"], error["field"], error["details"]) == (
        "PURCHASE_CORRECTION_BELOW_PAID", "lines", {"purchase_id": old["id"], "paid": 4000, "new_total": 3000})
    assert client.get(f"/purchases/{old['id']}").json()["status"] == "ACTIVE"


def test_stock_used_and_history_unknown_details(client, world):
    purchase = _buy(client, world, [line(world["paper"])], payment={"mode": "NONE"})
    client.post("/adjustments", json={"item_type": "MATERIAL", "item_id": world["paper"], "quantity_change": -1, "reason": "WASTE"})
    response = client.post(f"/purchases/{purchase['id']}/cancel", json={"reason": "x"})
    assert response.status_code == 409
    error = _error(response)
    assert error["code"] == "PURCHASE_STOCK_USED" and (error["details"]["current_stock"], error["details"]["quantity_bought"]) == (9, 10)


def test_the_openapi_names_the_new_routes(client, world):
    paths = app.openapi()["paths"]
    assert {"patch"} <= set(paths["/purchases/{purchase_id}"])
    assert "/purchases/{purchase_id}/cancel-preview" in paths and "/purchases/{purchase_id}/cancel" in paths
    assert "/purchases/{purchase_id}/correct" in paths
