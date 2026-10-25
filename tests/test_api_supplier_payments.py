"""The HTTP contract of purchase invoices and supplier payables: POST /purchases with lines (STOCK materials, services,
products), purchase payment terms, /supplier-payments, /payables and its allocation preview, typed error envelopes."""

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
def world(client):
    material = client.post("/materials", json={"name": "Fictional Paper", "type": "STOCK", "unit_cost": 0}).json()
    service = client.post("/materials", json={"name": "Fictional Printing", "type": "SERVICE", "unit_cost": 0}).json()
    category = client.get("/categories", params={"kind": "PRODUCT"}).json()[0]["id"]
    product = client.post("/products", json={
        "name": "Fictional Tee", "category_id": category, "retail_price": 3000, "wholesale_price": 2000}).json()
    acme = client.post("/suppliers", json={"name": "Acme Paper"}).json()
    other = client.post("/suppliers", json={"name": "Other Supplier"}).json()
    return {"material": material["id"], "service": service["id"], "product": product["id"], "acme": acme["id"], "other": other["id"]}


def line(kind, item_id, quantity, total):
    return {"kind": kind, "item_id": item_id, "quantity_bought": quantity, "total_paid": total}


def _purchase(client, world, total, date="2026-05-01", supplier="acme", **payment):
    body = {"lines": [line("MATERIAL", world["material"], 10, total)], "supplier_id": world[supplier], "purchase_date": date}
    if payment:
        body["payment"] = payment
    return client.post("/purchases", json=body)


def test_a_purchase_without_payment_terms_is_paid_in_full(client, world):
    created = _purchase(client, world, 4000)
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["total"], body["paid"], body["outstanding"], body["payment_status"], body["status"]) == (4000, 4000, 0, "PAID", "ACTIVE")
    assert [p["amount"] for p in body["payments"]] == [4000] and body["payments"][0]["method"] == "OTHER"
    assert body["replaced_by_invoice_id"] is None and body["replaces_invoice_id"] is None and "item_cost_after" not in body
    assert body["invoice_number"] == "PUR-000001"
    assert [(l["kind"], l["item_type"], l["item_name"], l["unit_cost"]) for l in body["lines"]] == [("MATERIAL", "STOCK", "Fictional Paper", 400)]


def test_one_invoice_with_a_stock_material_a_service_and_a_product(client, world):
    created = client.post("/purchases", json={
        "supplier_id": world["acme"], "purchase_date": "2026-05-02", "notes": "one bill", "payment": {"mode": "NONE"},
        "lines": [
            line("MATERIAL", world["material"], 10, 4000),
            line("MATERIAL", world["service"], 2.5, 1000),
            line("PRODUCT", world["product"], 3.0, 900),  # a whole number sent as 3.0 is 3 units
        ],
    })
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["total"], body["paid"], body["payment_status"], body["notes"]) == (5900, 0, "UNPAID", "one bill")
    assert [(l["kind"], l["item_type"], l["quantity_bought"], l["total_paid"], l["unit_cost"]) for l in body["lines"]] == [
        ("MATERIAL", "STOCK", 10, 4000, 400), ("MATERIAL", "SERVICE", 2.5, 1000, 400), ("PRODUCT", "PRODUCT", 3, 900, 300),
    ]
    # the service has no stock, only a price
    service = client.get(f"/materials/{world['service']}").json()
    assert (service["current_stock"], service["unit_cost"]) == (None, 400)
    rows = client.get("/purchases", params={"item_type": "SERVICE"}).json()
    assert [r["id"] for r in rows] == [body["id"]] and rows[0]["total"] == 5900
    assert client.get("/purchases", params={"item_type": "PRODUCT", "item_id": world["product"]}).json()[0]["id"] == body["id"]
    assert client.get("/purchases", params={"item_type": "GADGET"}).status_code == 422


def test_on_credit_partial_and_the_list(client, world):
    _purchase(client, world, 4000, mode="NONE")
    partial = _purchase(client, world, 3000, mode="PARTIAL", amount=1000, method="CARD", reference="R-7").json()
    assert (partial["paid"], partial["outstanding"], partial["payment_status"]) == (1000, 2000, "PARTIAL")
    assert partial["payments"][0]["reference"] == "R-7"
    rows = client.get("/purchases").json()
    assert sorted(r["payment_status"] for r in rows) == ["PARTIAL", "UNPAID"]
    assert "payments" not in rows[0]
    assert client.get(f"/purchases/{partial['id']}").json() == partial


def test_credit_without_a_supplier_is_422_with_empty_details(client, world):
    response = client.post("/purchases", json={"lines": [line("MATERIAL", world["material"], 1, 100)], "payment": {"mode": "NONE"}})
    assert response.status_code == 422
    error = _error(response)
    assert (error["code"], error["field"], error["details"]) == ("SUPPLIER_REQUIRED_FOR_CREDIT", "supplier_id", {})


def test_the_new_refusals_have_typed_details(client, world):
    twice = client.post("/purchases", json={"lines": [line("MATERIAL", world["material"], 1, 100), line("MATERIAL", world["material"], 2, 200)]})
    assert twice.status_code == 422
    error = _error(twice)
    assert (error["code"], error["field"]) == ("PURCHASE_DUPLICATE_ITEM", "lines.1.item_id")
    assert error["details"] == {"index": 1, "item_type": "MATERIAL", "item_id": world["material"]}
    free = client.post("/purchases", json={"lines": [line("MATERIAL", world["material"], 1, 100), line("MATERIAL", world["service"], 2, 0)]})
    assert free.status_code == 422
    error = _error(free)
    assert (error["code"], error["field"]) == ("SERVICE_PURCHASE_NEEDS_TOTAL", "lines.1.total_paid")
    assert error["details"] == {"index": 1, "material_id": world["service"], "material_name": "Fictional Printing"}
    whole = client.post("/purchases", json={"lines": [line("PRODUCT", world["product"], 1.5, 100)]})
    assert whole.status_code == 422 and _error(whole)["code"] == "QUANTITY_NOT_WHOLE" and _error(whole)["field"] == "lines.0.quantity_bought"
    assert client.get("/purchases").json() == []  # nothing was written


def test_bad_bodies_are_422(client, world):
    for body in (
        {"lines": []},
        {},
        {"lines": [{**line("MATERIAL", world["material"], 1, 100), "total_paid": 10.5}]},
        {"lines": [{**line("MATERIAL", world["material"], 1, 100), "total_paid": "100"}]},
        {"lines": [{**line("MATERIAL", world["material"], 0, 100)}]},
        {"lines": [line("WIDGET", world["material"], 1, 100)]},
        {"lines": [line("MATERIAL", world["material"], 1, 100)], "supplier_id": "x"},
        {"lines": [line("MATERIAL", world["material"], 1, 100)], "invoice_number": "PUR-9"},
    ):
        assert client.post("/purchases", json=body).status_code == 422, body


def test_record_a_payment_oldest_first_and_read_it_back(client, world):
    old = _purchase(client, world, 4000, date="2026-05-01", mode="NONE").json()
    new = _purchase(client, world, 5000, date="2026-05-03", mode="NONE").json()
    preview = client.get("/payables/allocation-preview", params={"supplier_id": world["acme"], "amount": 6000})
    assert preview.status_code == 200
    assert preview.json() == [
        {"purchase_id": old["id"], "amount": 4000},
        {"purchase_id": new["id"], "amount": 2000},
    ]
    created = client.post("/supplier-payments", json={
        "supplier_id": world["acme"], "payment_date": "2026-05-04", "amount": 6000, "method": "BANK_TRANSFER",
    })
    assert created.status_code == 201, created.text
    payment = created.json()
    assert [a["amount"] for a in payment["allocations"]] == [4000, 2000]
    assert payment["allocations"][0]["item_names"] == ["Fictional Paper"] and payment["supplier_name"] == "Acme Paper"
    assert payment["allocations"][0]["invoice_number"] == old["invoice_number"]
    assert client.get(f"/supplier-payments/{payment['id']}").json() == payment
    assert [p["id"] for p in client.get("/supplier-payments", params={"supplier_id": world["acme"]}).json()] == [payment["id"]]


def test_explicit_allocations_and_their_refusals(client, world):
    purchase = _purchase(client, world, 4000, mode="NONE").json()
    other = _purchase(client, world, 1000, supplier="other", mode="NONE").json()

    def pay(amount, allocations, supplier="acme", date="2026-05-02"):
        return client.post("/supplier-payments", json={
            "supplier_id": world[supplier], "payment_date": date, "amount": amount, "method": "CASH",
            "allocations": allocations,
        })

    one = [{"purchase_id": purchase["id"], "amount": 900}]
    mismatch = pay(1000, one)
    assert mismatch.status_code == 422
    assert _error(mismatch)["details"] == {"amount": 1000, "allocated": 900}
    due = pay(5000, [{"purchase_id": purchase["id"], "amount": 5000}])
    assert due.status_code == 409 and _error(due)["code"] == "SUPPLIER_PAYMENT_EXCEEDS_DUE"
    assert _error(due)["details"] == {"purchase_id": purchase["id"], "outstanding": 4000}
    wrong = pay(100, [{"purchase_id": other["id"], "amount": 100}])
    assert wrong.status_code == 422 and _error(wrong)["code"] == "SUPPLIER_PAYMENT_SUPPLIER_MISMATCH"
    early = pay(100, [{"purchase_id": purchase["id"], "amount": 100}], date="2026-04-01")
    assert early.status_code == 422 and _error(early)["code"] == "SUPPLIER_PAYMENT_BEFORE_PURCHASE"
    assert _error(early)["details"] == {"purchase_id": purchase["id"], "purchase_date": "2026-05-01"}
    missing = pay(100, [{"purchase_id": 999, "amount": 100}])
    assert missing.status_code == 404 and _error(missing)["details"] == {"purchase_id": 999}
    assert pay(100, [{"purchase_kind": "MATERIAL", "purchase_id": purchase["id"], "amount": 100}]).status_code == 422  # the kind is gone
    assert pay(900, one).status_code == 201


def test_no_advance_and_future_dates(client, world):
    _purchase(client, world, 4000, mode="NONE")
    too_much = client.post("/supplier-payments", json={
        "supplier_id": world["acme"], "payment_date": "2026-05-02", "amount": 4001, "method": "CASH"})
    assert too_much.status_code == 409
    assert _error(too_much)["details"] == {"supplier_id": world["acme"], "outstanding": 4000}
    preview = client.get("/payables/allocation-preview", params={"supplier_id": world["acme"], "amount": 4001})
    assert preview.status_code == 409 and _error(preview)["code"] == "SUPPLIER_PAYMENT_EXCEEDS_BALANCE"
    future = client.post("/supplier-payments", json={
        "supplier_id": world["acme"], "payment_date": "2999-01-01", "amount": 1, "method": "CASH"})
    assert future.status_code == 422 and _error(future)["code"] == "DATE_IN_FUTURE"
    bad = client.post("/supplier-payments", json={
        "supplier_id": world["acme"], "payment_date": "2026-05-02", "amount": 1.5, "method": "CASH"})
    assert bad.status_code == 422
    unknown = client.post("/supplier-payments", json={
        "supplier_id": world["acme"], "payment_date": "2026-05-02", "amount": 1, "method": "GOLD"})
    assert unknown.status_code == 422


def test_patch_and_delete(client, world):
    purchase = _purchase(client, world, 4000, mode="NONE").json()
    payment = client.post("/supplier-payments", json={
        "supplier_id": world["acme"], "payment_date": "2026-05-02", "amount": 1000, "method": "CASH", "note": "n"}).json()
    patched = client.patch(f"/supplier-payments/{payment['id']}", json={"method": "CHEQUE", "reference": "CH-1", "note": None})
    assert patched.status_code == 200
    assert (patched.json()["method"], patched.json()["reference"], patched.json()["note"]) == ("CHEQUE", "CH-1", None)
    assert client.patch(f"/supplier-payments/{payment['id']}", json={"amount": 5}).status_code == 422
    assert client.delete(f"/supplier-payments/{payment['id']}").status_code == 204
    gone = client.get(f"/supplier-payments/{payment['id']}")
    assert gone.status_code == 404 and _error(gone)["code"] == "SUPPLIER_PAYMENT_NOT_FOUND"
    assert client.get(f"/purchases/{purchase['id']}").json()["outstanding"] == 4000


def test_payables_and_the_purchases_summary(client, world):
    _purchase(client, world, 4000, date="2026-05-03", mode="NONE")
    _purchase(client, world, 1000, date="2026-05-01", mode="PARTIAL", amount=400)
    _purchase(client, world, 2000, supplier="other", mode="NONE")
    payables = client.get("/payables").json()
    assert payables["outstanding_total"] == 6600
    acme = payables["suppliers"][0]
    assert (acme["supplier_name"], acme["outstanding"], acme["paid_total"], acme["purchases_total"]) == ("Acme Paper", 4600, 400, 5000)
    assert [p["outstanding"] for p in acme["open_purchases"]] == [600, 4000]
    assert [p["item_names"] for p in acme["open_purchases"]] == [["Fictional Paper"], ["Fictional Paper"]]
    assert [(p["total"], p["paid"]) for p in acme["open_purchases"]] == [(1000, 400), (4000, 0)]
    summary = client.get("/reports/purchases", params={"start_date": "2026-05-01", "end_date": "2026-05-31"}).json()
    assert (summary["supplier_payments_total"], summary["supplier_payments_count"], summary["payables_outstanding"]) == (400, 1, 6600)
    assert (summary["purchase_invoices_count"], summary["material_purchases_count"], summary["service_purchases_count"]) == (3, 3, 0)


def test_the_summary_keeps_services_apart(client, world):
    client.post("/purchases", json={"lines": [line("MATERIAL", world["material"], 1, 1000), line("MATERIAL", world["service"], 1, 300)],
                                    "purchase_date": "2026-05-02"})
    summary = client.get("/reports/purchases", params={"start_date": "2026-05-01", "end_date": "2026-05-31"}).json()
    assert (summary["material_purchases_total"], summary["service_purchases_total"], summary["service_purchases_count"]) == (1000, 300, 1)
    assert summary["purchase_invoices_count"] == 1


def test_unknown_purchase_is_404(client, world):
    response = client.get("/purchases/999")
    assert response.status_code == 404
    assert _error(response)["code"] == "PURCHASE_NOT_FOUND"
    assert _error(response)["details"] == {"purchase_id": 999}


def test_the_per_kind_routes_are_gone(client, world):
    assert client.post("/purchases/materials", json={"material_id": world["material"], "quantity_bought": 1, "total_paid": 1}).status_code in (404, 405, 422)
    assert client.get("/purchases/products/1").status_code == 404
    assert client.get("/purchases/materials").status_code == 422  # "materials" is read as an invoice id
