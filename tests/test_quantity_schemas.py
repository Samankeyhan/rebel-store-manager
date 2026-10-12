"""Quantity fields on the wire: whole-number fields are strict integers in 1..1,000,000, material
quantities strict finite numbers in (0, 1e9] (JSON 5 and 5.5 both pass), stock fields 0..1e9, stock
adjustments +-1e9. A bad value is a 422 in the error envelope with QUANTITY_NOT_WHOLE or
QUANTITY_OUT_OF_RANGE (details min, max), never a 500."""

import json

import pytest

from db.constants import MAX_QUANTITY, MAX_WHOLE_QUANTITY
from db.errors import ErrorCode, ValidationError
from db.orders import record_order
from db.materials import add_material
from db.packaging import add_kit_item, create_kit
from tests.test_money_bounds import world  # noqa: F401  (fixture)


def _order(i, v):
    return {"channel": "WEBSITE", "shipping_charge": 0, "postage_cost": 0, "packaging_kit_id": None,
            "payment_method_id": None,
            "items": [{"product_id": i["product"], "quantity": v, "unit_price": 1}]}


# name -> (method, path(ids), body(ids, value), field, kind) kind: whole | positive | stock | signed
FIELDS = {
    "order.quantity": ("post", lambda i: "/orders", _order, "items.0.quantity", "whole"),
    "production.quantity_produced": ("post", lambda i: "/production",
                                     lambda i, v: {"product_id": i["product"], "quantity_produced": v},
                                     "quantity_produced", "whole"),
    "purchase.product.quantity_bought": ("post", lambda i: "/purchases/products",
                                         lambda i, v: {"product_id": i["product"], "quantity_bought": v, "total_paid": 1},
                                         "quantity_bought", "whole"),
    "purchase.material.quantity_bought": ("post", lambda i: "/purchases/materials",
                                          lambda i, v: {"material_id": i["material"], "quantity_bought": v, "total_paid": 1},
                                          "quantity_bought", "positive"),
    "recipe.create": ("post", lambda i: f"/products/{i['product']}/recipe/items",
                      lambda i, v: {"material_id": i["material"], "quantity_needed": v}, "quantity_needed", "positive"),
    "kit.item_create": ("post", lambda i: f"/packaging/kits/{i['kit']}/items",
                        lambda i, v: {"material_id": i["material"], "quantity": v}, "quantity", "positive"),
    "kit.item_update": ("patch", lambda i: f"/packaging/kits/{i['kit']}/items/{i['in_kit']}",
                        lambda i, v: {"quantity": v}, "quantity", "positive"),
    "material.initial_stock": ("post", lambda i: "/materials",
                               lambda i, v: {"name": "Q Box", "type": "STOCK", "unit_cost": 1, "initial_stock": v},
                               "initial_stock", "stock"),
    "material.min_stock": ("post", lambda i: "/materials",
                           lambda i, v: {"name": "Q Tape", "type": "STOCK", "unit_cost": 1, "min_stock": v},
                           "min_stock", "stock"),
    "adjustment.quantity_change": ("post", lambda i: "/adjustments",
                                   lambda i, v: {"item_type": "MATERIAL", "item_id": i["material"],
                                                 "quantity_change": v, "reason": "ADJUSTMENT"},
                                   "quantity_change", "signed"),
}


@pytest.fixture
def ids(world):  # noqa: F811
    client, base, conn = world
    kit = create_kit(conn, "Q Kit")
    in_kit = add_material(conn, "Q Kit Box", "STOCK", 1, initial_stock=10)
    add_kit_item(conn, kit, in_kit, 1)
    return client, {**base, "kit": kit, "in_kit": in_kit}, conn


def _send(client, ids_, name, value):
    method, path, body, _, _ = FIELDS[name]
    payload = body(ids_, value)
    # json.dumps keeps NaN / Infinity (a client may send them); TestClient's json= would refuse.
    return getattr(client, method)(
        path(ids_), content=json.dumps(payload), headers={"Content-Type": "application/json"}
    )


def _of_kind(*kinds):
    return [n for n, spec in FIELDS.items() if spec[4] in kinds]


def _error(response):
    assert response.status_code == 422, response.text[:300]
    return response.json()["error"]


@pytest.mark.parametrize("name", _of_kind("whole", "positive"))
@pytest.mark.parametrize("value", [0, -1, -MAX_WHOLE_QUANTITY])
def test_zero_or_negative_is_out_of_range_with_the_minimum(ids, name, value):
    client, i, _ = ids
    error = _error(_send(client, i, name, value))
    assert error["code"] == "QUANTITY_OUT_OF_RANGE"
    assert error["field"] == FIELDS[name][3]
    assert error["details"]["min"] == 0 and error["details"]["max"] is None


@pytest.mark.parametrize("name", _of_kind("whole"))
@pytest.mark.parametrize("value", [MAX_WHOLE_QUANTITY + 1, 10**30])
def test_a_whole_quantity_above_the_maximum_is_out_of_range(ids, name, value):
    client, i, _ = ids
    error = _error(_send(client, i, name, value))
    assert error["code"] == "QUANTITY_OUT_OF_RANGE"
    assert error["details"]["max"] == MAX_WHOLE_QUANTITY


@pytest.mark.parametrize("name", _of_kind("positive", "stock", "signed"))
@pytest.mark.parametrize("value", [MAX_QUANTITY + 1, 1e30])
def test_a_fractional_quantity_above_the_maximum_is_out_of_range(ids, name, value):
    client, i, _ = ids
    error = _error(_send(client, i, name, value))
    assert error["code"] == "QUANTITY_OUT_OF_RANGE"
    assert error["details"]["max"] == MAX_QUANTITY


@pytest.mark.parametrize("name", _of_kind("stock"))
def test_a_negative_stock_quantity_is_out_of_range(ids, name):
    client, i, _ = ids
    error = _error(_send(client, i, name, -1))
    assert error["code"] == "QUANTITY_OUT_OF_RANGE" and error["details"]["min"] == 0


def test_a_stock_adjustment_may_be_negative_but_not_zero_or_beyond_the_maximum(ids):
    client, i, conn = ids
    assert _send(client, i, "adjustment.quantity_change", 5).status_code == 201
    response = _send(client, i, "adjustment.quantity_change", -3)
    assert response.status_code == 201, response.text[:300]
    error = _error(_send(client, i, "adjustment.quantity_change", 0))
    assert error["field"] == "quantity_change" and error["code"] == "VALIDATION_FAILED"
    error = _error(_send(client, i, "adjustment.quantity_change", -MAX_QUANTITY - 1))
    assert error["code"] == "QUANTITY_OUT_OF_RANGE"
    assert error["details"]["min"] == -MAX_QUANTITY


@pytest.mark.parametrize("name", _of_kind("whole"))
@pytest.mark.parametrize("value", [2.5, 2.0, "2", True, None, [1]])
def test_a_whole_quantity_must_be_an_integer(ids, name, value):
    client, i, _ = ids
    error = _error(_send(client, i, name, value))
    assert error["code"] in ("QUANTITY_NOT_WHOLE", "VALIDATION_FAILED")
    if value is not None and value != [1]:
        assert error["code"] == "QUANTITY_NOT_WHOLE", (value, error)
    assert error["field"] == FIELDS[name][3]


@pytest.mark.parametrize("name", _of_kind("positive", "stock", "signed"))
@pytest.mark.parametrize("value", ["5", True, [1], float("inf"), float("nan")])
def test_a_fractional_quantity_must_be_a_finite_number(ids, name, value):
    client, i, _ = ids
    error = _error(_send(client, i, name, value))
    assert error["code"] == "VALIDATION_FAILED"
    assert error["field"] == FIELDS[name][3]


@pytest.mark.parametrize("name", _of_kind("positive", "stock", "signed"))
@pytest.mark.parametrize("value", [5, 5.5])
def test_a_fractional_quantity_accepts_both_json_5_and_5_5(ids, name, value):
    client, i, _ = ids
    response = _send(client, i, name, value)
    assert response.status_code in (200, 201), (name, value, response.text[:300])


@pytest.mark.parametrize("name", _of_kind("whole"))
@pytest.mark.parametrize("value", [1, MAX_WHOLE_QUANTITY])
def test_a_whole_quantity_at_one_and_at_the_maximum_is_not_a_quantity_error(ids, name, value):
    client, i, _ = ids
    response = _send(client, i, name, value)
    assert response.status_code != 500, (name, value, response.text[:300])
    if response.status_code >= 400:
        assert not response.json()["error"]["code"].startswith("QUANTITY_"), (name, value)


@pytest.mark.parametrize("name", _of_kind("positive", "stock", "signed"))
def test_a_fractional_quantity_at_the_maximum_is_not_a_quantity_error(ids, name):
    client, i, _ = ids
    response = _send(client, i, name, MAX_QUANTITY)
    assert response.status_code != 500, (name, response.text[:300])
    if response.status_code >= 400:
        assert not response.json()["error"]["code"].startswith("QUANTITY_"), name


def test_the_most_units_at_the_highest_price_is_refused_as_an_amount_not_a_crash(ids):
    client, i, _ = ids
    body = _order(i, MAX_WHOLE_QUANTITY)
    body["items"][0]["unit_price"] = 2**53 - 1
    error = _error(client.post("/orders", json=body))
    assert error["code"] == "AMOUNT_TOO_LARGE"


# ---------------------------------------------------------------- db level


def test_db_refuses_a_non_integer_order_quantity_with_its_code(world):  # noqa: F811
    _, i, conn = world
    for bad in (2.5, True, "2"):
        with pytest.raises(ValidationError) as exc_info:
            record_order(conn, "WEBSITE", [{"product_id": i["product"], "quantity": bad, "unit_price": 1}],
                         shipping_charge=0, postage_cost=0, packaging_kit_id=None, payment_method_id=None)
        assert exc_info.value.code == ErrorCode.QUANTITY_NOT_WHOLE and exc_info.value.field == "quantity"


def test_db_refuses_an_out_of_range_quantity_with_min_and_max(world):  # noqa: F811
    _, i, conn = world
    for bad, expected in ((0, {"min": 0, "max": None}), (MAX_WHOLE_QUANTITY + 1, {"min": None, "max": MAX_WHOLE_QUANTITY})):
        with pytest.raises(ValidationError) as exc_info:
            record_order(conn, "WEBSITE", [{"product_id": i["product"], "quantity": bad, "unit_price": 1}],
                         shipping_charge=0, postage_cost=0, packaging_kit_id=None, payment_method_id=None)
        assert exc_info.value.code == ErrorCode.QUANTITY_OUT_OF_RANGE
        assert exc_info.value.details == expected
