"""PAID_DATE_NOT_ALLOWED, PACKAGING_KIT_NOT_FOUND and PACKAGING_KIT_INACTIVE: a refusal the UI
tells apart has its own code (the UI used to guess from field == "paid_date" or from the message)."""

from db.packaging import create_kit, deactivate_kit
from tests.test_money_bounds import world  # noqa: F401  (fixture)


def _order(ids, **extra):
    return {"channel": "WEBSITE", "shipping_charge": 0, "postage_cost": 0, "packaging_kit_id": None,
            "payment_method_id": None,
            "items": [{"product_id": ids["product"], "quantity": 1, "unit_price": 1000}], **extra}


def _error(response, status):
    assert response.status_code == status, response.text[:300]
    return response.json()["error"]


def test_paid_date_on_an_order_that_is_not_paid_has_its_code(world):  # noqa: F811
    client, ids, _ = world
    error = _error(client.post("/orders", json=_order(ids, status="PENDING", paid_date="2026-01-01")), 422)
    assert (error["code"], error["field"]) == ("PAID_DATE_NOT_ALLOWED", "paid_date")


def test_paid_date_on_a_status_change_that_is_not_a_payment_has_its_code(world):  # noqa: F811
    client, ids, _ = world
    created = client.post("/orders", json=_order(ids, status="PAID"))
    assert created.status_code == 201, created.text[:300]
    order_id = created.json()["order"]["id"]
    error = _error(client.post(f"/orders/{order_id}/status", json={"status": "COMPLETED", "paid_date": "2026-01-01"}), 422)
    assert (error["code"], error["field"]) == ("PAID_DATE_NOT_ALLOWED", "paid_date")


def test_a_paid_date_that_is_not_a_date_is_still_a_plain_validation_error(world):  # noqa: F811
    client, ids, _ = world
    error = _error(client.post("/orders", json=_order(ids, status="PAID", paid_date="2026-13-45")), 422)
    assert (error["code"], error["field"]) == ("VALIDATION_FAILED", "paid_date")


def test_a_missing_default_kit_is_404_with_the_kit_id(world):  # noqa: F811
    client, _, _ = world
    error = _error(client.patch("/settings/channels/WEBSITE", json={"default_packaging_kit_id": 999}), 404)
    assert error["code"] == "PACKAGING_KIT_NOT_FOUND"
    assert error["details"] == {"packaging_kit_id": 999}
    error = _error(client.get("/packaging/kits/999"), 404)
    assert error["code"] == "PACKAGING_KIT_NOT_FOUND"


def test_an_inactive_default_kit_is_422_with_its_own_code(world):  # noqa: F811
    client, _, conn = world
    kit = create_kit(conn, "Old Kit")
    deactivate_kit(conn, kit)
    error = _error(client.patch("/settings/channels/WEBSITE", json={"default_packaging_kit_id": kit}), 422)
    assert (error["code"], error["field"]) == ("PACKAGING_KIT_INACTIVE", "default_packaging_kit_id")
    assert error["details"] == {"packaging_kit_id": kit}


def test_an_order_with_an_inactive_kit_has_the_inactive_code(world):  # noqa: F811
    client, ids, conn = world
    kit = create_kit(conn, "Old Kit 2")
    deactivate_kit(conn, kit)
    error = _error(client.post("/orders", json=_order(ids, packaging_kit_id=kit)), 422)
    assert (error["code"], error["field"]) == ("PACKAGING_KIT_INACTIVE", "packaging_kit_id")
    error = _error(client.post("/orders", json=_order(ids, packaging_kit_id=99999)), 404)
    assert error["code"] == "PACKAGING_KIT_NOT_FOUND"
