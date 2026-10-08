"""HTTP tests for payment methods, settlements, the order payment fields, the
channel default method and the payment-method report."""

import io
from datetime import date

import pdfplumber
import pytest
from fastapi.testclient import TestClient

import db.orders
import db.settlements
from api.deps import get_db
from api.main import app
from db.connection import get_connection, init_db
from db.currency import format_display_number
from pdf import invoice as invoice_module
from tests.helpers import stocked_product

TODAY = date(2026, 10, 6)  # 14 Mehr 1405


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Temp-file database behind the app, and "today" fixed in db/."""
    for module in (db.orders, db.settlements):
        monkeypatch.setattr(module, "today_local", lambda conn=None: TODAY)
    db_path = str(tmp_path / "test_api_payments.db")
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


@pytest.fixture
def shop(api):
    client, conn = api
    return {
        "product_id": stocked_product(conn, stock=1000),
        "card": _method(client, "Card to card", "IMMEDIATE")["id"],
        "zarinpal": _method(client, "Zarinpal", "DAYS_AFTER", 1, fee_bps=150, fee_fixed=500)["id"],
        "digipay": _method(client, "Digipay", "DAY_OF_NEXT_MONTH", 7, fee_bps=300)["id"],
    }


def _call(client, method, path, expected, **kwargs):
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == expected, response.text
    return response.json()


def _method(client, name, rule, days=None, **extra):
    body = {"name": name, "settlement_rule": rule, "settlement_days": days, **extra}
    return _call(client, "post", "/payment-methods", 201, json=body)


def _order(client, shop, expected=201, price=100000, **extra):
    body = {
        "channel": "WEBSITE",
        "items": [{"product_id": shop["product_id"], "quantity": 1, "unit_price": price}],
        "shipping_charge": 0,
        "postage_cost": 0,
        "packaging_kit_id": None,
        **extra,
    }
    return _call(client, "post", "/orders", expected, json=body)


def _error(response_json):
    return response_json["error"]


def _pydantic_fields(response_json):
    """The body field names a FastAPI request-validation 422 points at."""
    return {err["loc"][1] for err in response_json["detail"] if err["loc"][0] == "body"}


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ================================================================ payment methods


def test_create_and_read_payment_method(api):
    client, _ = api
    created = _method(client, "  Zarinpal ", "DAYS_AFTER", 1, fee_bps=150, fee_fixed=500)
    assert {k: created[k] for k in created if k not in ("id", "created_at", "updated_at")} == {
        "name": "Zarinpal",
        "fee_bps": 150,
        "fee_fixed": 500,
        "settlement_rule": "DAYS_AFTER",
        "settlement_days": 1,
        "is_active": 1,
        "pending_order_count": 0,
    }
    assert _call(client, "get", f"/payment-methods/{created['id']}", 200) == created


def test_payment_method_defaults(api):
    client, _ = api
    created = _call(
        client, "post", "/payment-methods", 201, json={"name": "Card", "settlement_rule": "IMMEDIATE"}
    )
    assert (created["fee_bps"], created["fee_fixed"], created["settlement_days"]) == (0, 0, None)


def test_list_payment_methods_and_inactive(api, shop):
    client, _ = api
    _call(client, "post", f"/payment-methods/{shop['zarinpal']}/deactivate", 200)
    names = [m["name"] for m in _call(client, "get", "/payment-methods", 200)]
    assert names == ["Card to card", "Digipay"]
    every = _call(client, "get", "/payment-methods", 200, params={"include_inactive": True})
    assert [(m["name"], m["is_active"]) for m in every] == [
        ("Card to card", 1), ("Digipay", 1), ("Zarinpal", 0),
    ]


def test_deactivate_and_reactivate(api, shop):
    client, _ = api
    assert _call(client, "post", f"/payment-methods/{shop['card']}/deactivate", 200)["is_active"] == 0
    assert _call(client, "post", f"/payment-methods/{shop['card']}/reactivate", 200)["is_active"] == 1
    _call(client, "post", "/payment-methods/999/deactivate", 404)
    _call(client, "post", "/payment-methods/999/reactivate", 404)


def test_get_missing_payment_method_is_404(api):
    client, _ = api
    assert _error(_call(client, "get", "/payment-methods/999", 404))["type"] == "NotFoundError"


@pytest.mark.parametrize(
    "body, field",
    [
        ({"name": "", "settlement_rule": "IMMEDIATE"}, "name"),
        ({"name": "X", "settlement_rule": "WEEKLY"}, "settlement_rule"),
        ({"name": "X", "settlement_rule": "IMMEDIATE", "settlement_days": 3}, "settlement_days"),
        ({"name": "X", "settlement_rule": "DAYS_AFTER"}, "settlement_days"),
        ({"name": "X", "settlement_rule": "DAY_OF_NEXT_MONTH", "settlement_days": 32}, "settlement_days"),
        ({"name": "X", "settlement_rule": "IMMEDIATE", "fee_bps": 10001}, "fee_bps"),
        ({"name": "X", "settlement_rule": "IMMEDIATE", "fee_fixed": -1}, "fee_fixed"),
    ],
)
def test_create_payment_method_db_validation_is_422_with_field(api, body, field):
    client, conn = api
    assert _error(_call(client, "post", "/payment-methods", 422, json=body))["field"] == field
    assert _count(conn, "payment_methods") == 0


@pytest.mark.parametrize(
    "extra, field",
    [
        ({"fee_fixed": 500.5}, "fee_fixed"),
        ({"fee_fixed": 500.0}, "fee_fixed"),
        ({"fee_fixed": "500"}, "fee_fixed"),
        ({"fee_fixed": True}, "fee_fixed"),
        ({"fee_bps": 1.5}, "fee_bps"),
        ({"fee_bps": "150"}, "fee_bps"),
        ({"settlement_days": "1", "settlement_rule": "DAYS_AFTER"}, "settlement_days"),
        ({"surprise": 1}, "surprise"),
    ],
)
def test_create_payment_method_strict_types(api, extra, field):
    client, conn = api
    body = {"name": "X", "settlement_rule": "IMMEDIATE", **extra}
    assert field in _pydantic_fields(_call(client, "post", "/payment-methods", 422, json=body))
    assert _count(conn, "payment_methods") == 0


def test_duplicate_payment_method_name_is_409(api, shop):
    client, _ = api
    body = {"name": "Digipay", "settlement_rule": "IMMEDIATE"}
    assert "already exists" in _error(_call(client, "post", "/payment-methods", 409, json=body))["message"]


def test_patch_payment_method_partial(api, shop):
    client, _ = api
    patched = _call(client, "patch", f"/payment-methods/{shop['zarinpal']}", 200, json={"fee_bps": 200})
    assert (patched["fee_bps"], patched["fee_fixed"], patched["settlement_days"]) == (200, 500, 1)
    patched = _call(
        client, "patch", f"/payment-methods/{shop['zarinpal']}", 200,
        json={"settlement_rule": "IMMEDIATE", "settlement_days": None},
    )
    assert (patched["settlement_rule"], patched["settlement_days"]) == ("IMMEDIATE", None)


def test_patch_payment_method_rule_while_pending_is_409(api, shop):
    client, _ = api
    _order(client, shop, payment_method_id=shop["zarinpal"])
    method = _call(client, "get", f"/payment-methods/{shop['zarinpal']}", 200)
    assert method["pending_order_count"] == 1
    error = _error(
        _call(client, "patch", f"/payment-methods/{shop['zarinpal']}", 409, json={"settlement_days": 2})
    )
    assert "1 paid order is still pending settlement" in error["message"]
    assert "create a new one with the new rule" in error["message"]
    # Fees still change; the unchanged rule never conflicts.
    _call(
        client, "patch", f"/payment-methods/{shop['zarinpal']}", 200,
        json={"fee_bps": 100, "settlement_rule": "DAYS_AFTER", "settlement_days": 1},
    )


@pytest.mark.parametrize("body", [{"is_active": 0}, {"fee_fixed": 1.5}, {"fee_bps": True}])
def test_patch_payment_method_bad_body_is_422(api, shop, body):
    client, _ = api
    _call(client, "patch", f"/payment-methods/{shop['card']}", 422, json=body)


def test_patch_missing_payment_method_is_404(api):
    client, _ = api
    _call(client, "patch", "/payment-methods/999", 404, json={"fee_bps": 1})


def test_fee_preview(api, shop):
    client, _ = api
    preview = _call(
        client, "get", f"/payment-methods/{shop['zarinpal']}/fee-preview", 200,
        params={"amount": 240000},
    )
    assert preview == {
        "payment_method_id": shop["zarinpal"],
        "amount": 240000,
        "transaction_fee": 4100,
        "expected_amount": 235900,
    }


def test_fee_preview_half_even(api):
    client, _ = api
    method_id = _method(client, "Tiny", "IMMEDIATE", fee_bps=5)["id"]
    path = f"/payment-methods/{method_id}/fee-preview"
    assert _call(client, "get", path, 200, params={"amount": 1000})["transaction_fee"] == 0
    assert _call(client, "get", path, 200, params={"amount": 3000})["transaction_fee"] == 2


def test_fee_preview_errors(api, shop):
    client, _ = api
    path = f"/payment-methods/{shop['zarinpal']}/fee-preview"
    assert _error(_call(client, "get", path, 422, params={"amount": -1}))["field"] == "amount"
    for bad in ("1.5", "abc"):
        _call(client, "get", path, 422, params={"amount": bad})
    _call(client, "get", path, 422)
    _call(client, "get", "/payment-methods/999/fee-preview", 404, params={"amount": 1})


# ================================================================ orders


def _fee(order_json):
    return order_json["order"]["transaction_fee"]


@pytest.mark.parametrize("fee_body, expected", [({}, 2000), ({"transaction_fee": None}, 2000),
                                               ({"transaction_fee": 0}, 0), ({"transaction_fee": 777}, 777)])
def test_order_fee_computed_unless_given(api, shop, fee_body, expected):
    client, _ = api
    created = _order(client, shop, payment_method_id=shop["zarinpal"], **fee_body)
    assert _fee(created) == expected


def test_null_fee_is_computed_on_customer_total_including_shipping(api, shop):
    client, _ = api
    created = _order(
        client, shop,
        payment_method_id=shop["zarinpal"],
        shipping_charge=50000,
        items=[{"product_id": shop["product_id"], "quantity": 2, "unit_price": 100000,
                "discount_amount": 10000}],
        transaction_fee=None,
    )
    assert created["customer_total"] == 240000
    assert _fee(created) == 4100


@pytest.mark.parametrize("bad", [1000.5, 1000.0, "1000", True])
def test_order_fee_must_be_strict_int(api, shop, bad):
    client, conn = api
    response = _order(client, shop, expected=422, payment_method_id=shop["card"], transaction_fee=bad)
    assert "transaction_fee" in _pydantic_fields(response)
    assert _count(conn, "orders") == 0


def test_order_without_method_field_uses_channel_default(api, shop):
    client, _ = api
    # No channel default: "default" means no method, fee 0.
    created = _order(client, shop)
    assert created["order"]["payment_method_id"] is None
    assert _fee(created) == 0

    _call(client, "patch", "/settings/channels/WEBSITE", 200, json={"default_payment_method_id": shop["zarinpal"]})
    for extra in ({}, {"payment_method_id": "default"}):
        created = _order(client, shop, **extra)
        assert created["order"]["payment_method_id"] == shop["zarinpal"]
        assert created["order"]["payment_method_name"] == "Zarinpal"
        assert _fee(created) == 2000


def test_order_explicit_null_and_int_method(api, shop):
    client, _ = api
    _call(client, "patch", "/settings/channels/WEBSITE", 200, json={"default_payment_method_id": shop["zarinpal"]})
    assert _order(client, shop, payment_method_id=None)["order"]["payment_method_id"] is None
    created = _order(client, shop, payment_method_id=shop["digipay"], payment_reference="DG-1")
    assert created["order"]["payment_method_id"] == shop["digipay"]
    assert created["order"]["payment_reference"] == "DG-1"
    assert _fee(created) == 3000


@pytest.mark.parametrize("bad", [True, False, 1.0, "1", "Default", "", [1]])
def test_order_payment_method_id_must_be_strict(api, shop, bad):
    client, conn = api
    response = _order(client, shop, expected=422, payment_method_id=bad)
    assert "payment_method_id" in _pydantic_fields(response)
    assert _count(conn, "orders") == 0


def test_order_inactive_or_missing_method(api, shop):
    client, conn = api
    _call(client, "post", f"/payment-methods/{shop['card']}/deactivate", 200)
    error = _error(_order(client, shop, expected=422, payment_method_id=shop["card"]))
    assert error["field"] == "payment_method_id"
    assert "'Card to card' is not active" in error["message"]
    _order(client, shop, expected=404, payment_method_id=999)
    assert _count(conn, "orders") == 0


def test_order_paid_fields_on_create(api, shop):
    client, _ = api
    order = _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-09-01",
                   paid_date="2026-09-22")["order"]
    assert (order["paid_date"], order["expected_settlement_date"],
            order["paid_jalali_year"], order["paid_jalali_month"]) == ("2026-09-22", "2026-09-29", 1405, 6)
    defaulted = _order(client, shop, payment_method_id=shop["card"], order_date="2026-09-23")["order"]
    assert defaulted["paid_date"] == "2026-09-23"


@pytest.mark.parametrize(
    "extra",
    [
        {"paid_date": "2026-10-07"},
        {"paid_date": "2026-10-01", "status": "PENDING"},
        {"paid_date": "2026-10-01", "status": "DRAFT"},
        {"paid_date": "2026-02-30"},
    ],
)
def test_order_paid_date_refused_with_field(api, shop, extra):
    client, conn = api
    error = _error(_order(client, shop, expected=422, payment_method_id=shop["card"], **extra))
    assert error["field"] == "paid_date"
    assert _count(conn, "orders") == 0


def test_order_paid_date_format_is_422(api, shop):
    client, _ = api
    response = _order(client, shop, expected=422, paid_date="06/10/2026")
    assert "paid_date" in _pydantic_fields(response)


def test_order_paid_in_closed_month_is_409(api, shop):
    client, conn = api
    _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-09-10")
    _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["digipay"], "settled_date": "2026-09-29",
        "amount_received": 97000, "jalali_year": 1405, "jalali_month": 6,
    })
    before = _count(conn, "orders")
    error = _error(_order(client, shop, expected=409, payment_method_id=shop["digipay"],
                          order_date="2026-09-22"))
    assert "1405/06 is already settled" in error["message"]
    assert _count(conn, "orders") == before


def test_status_change_sets_paid_date(api, shop):
    client, _ = api
    order_id = _order(client, shop, payment_method_id=shop["zarinpal"], status="PENDING")["order"]["id"]
    changed = _call(client, "post", f"/orders/{order_id}/status", 200,
                    json={"status": "PAID", "paid_date": "2026-10-02"})["order"]
    assert (changed["status"], changed["paid_date"], changed["expected_settlement_date"]) == (
        "PAID", "2026-10-02", "2026-10-03",
    )
    error = _error(_call(client, "post", f"/orders/{order_id}/status", 422,
                         json={"status": "COMPLETED", "paid_date": "2026-10-03"}))
    assert error["field"] == "paid_date"
    completed = _call(client, "post", f"/orders/{order_id}/status", 200, json={"status": "COMPLETED"})
    assert completed["order"]["paid_date"] == "2026-10-02"


def test_status_change_without_paid_date_uses_today(api, shop):
    client, _ = api
    order_id = _order(client, shop, payment_method_id=shop["card"], status="DRAFT")["order"]["id"]
    changed = _call(client, "post", f"/orders/{order_id}/status", 200, json={"status": "COMPLETED"})
    assert changed["order"]["paid_date"] == "2026-10-06"


def test_status_change_rejects_unknown_fields(api, shop):
    client, _ = api
    order_id = _order(client, shop, status="PENDING")["order"]["id"]
    response = _call(client, "post", f"/orders/{order_id}/status", 422, json={"status": "PAID", "paid": True})
    assert "paid" in _pydantic_fields(response)


def test_patch_paid_date(api, shop):
    client, _ = api
    order_id = _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-09-23")["order"]["id"]
    order = _call(client, "patch", f"/orders/{order_id}/paid-date", 200, json={"paid_date": "2026-09-22"})["order"]
    assert (order["paid_date"], order["expected_settlement_date"], order["paid_jalali_month"]) == (
        "2026-09-22", "2026-09-29", 6,
    )


def test_patch_paid_date_errors(api, shop):
    client, _ = api
    unpaid = _order(client, shop, payment_method_id=shop["card"], status="PENDING")["order"]["id"]
    assert "not paid" in _error(
        _call(client, "patch", f"/orders/{unpaid}/paid-date", 409, json={"paid_date": "2026-10-01"})
    )["message"]

    settled = _order(client, shop, payment_method_id=shop["card"], order_date="2026-10-01")["order"]["id"]
    _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["card"], "settled_date": "2026-10-02",
        "amount_received": 100000, "order_ids": [settled],
    })
    _call(client, "patch", f"/orders/{settled}/paid-date", 409, json={"paid_date": "2026-09-30"})

    paid = _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-10-01")["order"]["id"]
    _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-09-10")
    _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["digipay"], "settled_date": "2026-09-29",
        "amount_received": 97000, "jalali_year": 1405, "jalali_month": 6,
    })
    _call(client, "patch", f"/orders/{paid}/paid-date", 409, json={"paid_date": "2026-09-22"})

    assert _error(_call(client, "patch", f"/orders/{paid}/paid-date", 422,
                        json={"paid_date": "2026-10-07"}))["field"] == "paid_date"
    _call(client, "patch", "/orders/999/paid-date", 404, json={"paid_date": "2026-10-01"})
    _call(client, "patch", f"/orders/{paid}/paid-date", 422, json={})
    _call(client, "patch", f"/orders/{paid}/paid-date", 422, json={"paid_date": "2026-10-01", "x": 1})


def test_list_orders_filters(api, shop):
    client, _ = api
    a = _order(client, shop, payment_method_id=shop["card"], order_date="2026-10-01")["order"]["id"]
    b = _order(client, shop, payment_method_id=shop["card"], order_date="2026-10-02")["order"]["id"]
    c = _order(client, shop, payment_method_id=shop["zarinpal"], order_date="2026-10-02")["order"]["id"]
    _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["card"], "settled_date": "2026-10-03",
        "amount_received": 100000, "order_ids": [a],
    })

    def ids(**params):
        return sorted(o["id"] for o in _call(client, "get", "/orders", 200, params=params))

    assert ids(payment_method_id=shop["card"]) == [a, b]
    assert ids(settlement_state="pending") == [b, c]
    assert ids(settlement_state="settled") == [a]
    assert ids(payment_method_id=shop["card"], settlement_state="pending") == [b]
    listed = _call(client, "get", "/orders", 200, params={"settlement_state": "settled"})
    assert listed[0]["payment_method_name"] == "Card to card"
    assert listed[0]["settlement_id"] is not None
    error = _error(_call(client, "get", "/orders", 422, params={"settlement_state": "open"}))
    assert error["field"] == "settlement_state"


# ================================================================ channel default method


def test_channel_default_method_set_clear_and_omit(api, shop):
    client, _ = api
    path = "/settings/channels/WEBSITE"
    assert _call(client, "patch", path, 200, json={"default_payment_method_id": shop["card"]})[
        "default_payment_method_id"] == shop["card"]
    # Omitted: unchanged.
    assert _call(client, "patch", path, 200, json={"applies_postage": 0})[
        "default_payment_method_id"] == shop["card"]
    settings = _call(client, "get", "/settings", 200)
    assert settings["channels"]["WEBSITE"]["default_payment_method_id"] == shop["card"]
    assert settings["channels"]["INSTAGRAM"]["default_payment_method_id"] is None
    # Explicit null: cleared.
    assert _call(client, "patch", path, 200, json={"default_payment_method_id": None})[
        "default_payment_method_id"] is None


def test_channel_default_method_errors(api, shop):
    client, _ = api
    path = "/settings/channels/WEBSITE"
    _call(client, "patch", path, 404, json={"default_payment_method_id": 999})
    _call(client, "post", f"/payment-methods/{shop['card']}/deactivate", 200)
    error = _error(_call(client, "patch", path, 422, json={"default_payment_method_id": shop["card"]}))
    assert error["field"] == "default_payment_method_id"
    for bad in ("1", 1.0, True):
        response = _call(client, "patch", path, 422, json={"default_payment_method_id": bad})
        assert "default_payment_method_id" in _pydantic_fields(response)
    assert _call(client, "get", "/settings", 200)["channels"]["WEBSITE"]["default_payment_method_id"] is None


def test_deactivated_channel_default_refuses_new_orders(api, shop):
    client, _ = api
    _call(client, "patch", "/settings/channels/WEBSITE", 200, json={"default_payment_method_id": shop["digipay"]})
    _call(client, "post", f"/payment-methods/{shop['digipay']}/deactivate", 200)
    error = _error(_order(client, shop, expected=422))
    assert error["field"] == "payment_method_id"
    assert "'Digipay' is not active" in error["message"]


# ================================================================ settlements


def test_pending_groups_for_both_rule_kinds(api, shop):
    client, _ = api
    _order(client, shop, payment_method_id=shop["zarinpal"], order_date="2026-10-01")
    _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-09-10")
    pending = {p["name"]: p for p in _call(client, "get", "/settlements/pending", 200)}
    assert list(pending) == ["Digipay", "Zarinpal"]

    (date_group,) = pending["Zarinpal"]["groups"]
    assert set(date_group) == {
        "expected_date", "due", "overdue", "order_count", "customer_total_sum", "fee_sum",
        "expected_amount", "orders",
    }
    assert (date_group["expected_date"], date_group["overdue"], date_group["expected_amount"]) == (
        "2026-10-02", True, 98000,
    )
    (month_group,) = pending["Digipay"]["groups"]
    assert (month_group["jalali_year"], month_group["jalali_month"], month_group["can_settle"]) == (1405, 6, True)
    assert month_group["orders"][0]["expected_amount"] == 97000

    only = _call(client, "get", "/settlements/pending", 200, params={"payment_method_id": shop["digipay"]})
    assert [p["name"] for p in only] == ["Digipay"]
    _call(client, "get", "/settlements/pending", 404, params={"payment_method_id": 999})


def test_settle_subset(api, shop):
    client, conn = api
    a = _order(client, shop, payment_method_id=shop["zarinpal"], order_date="2026-10-01")["order"]["id"]
    b = _order(client, shop, payment_method_id=shop["zarinpal"], order_date="2026-10-02")["order"]["id"]
    settlement = _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["zarinpal"], "settled_date": "2026-10-03",
        "amount_received": 97500, "order_ids": [a], "note": "bank",
    })
    assert (settlement["expected_amount"], settlement["amount_received"], settlement["difference"]) == (
        98000, 97500, -500,
    )
    assert settlement["note"] == "bank"
    assert [o["id"] for o in settlement["orders"]] == [a]
    (group,) = _call(client, "get", "/settlements/pending", 200)[0]["groups"]
    assert [o["id"] for o in group["orders"]] == [b]
    assert _call(client, "get", f"/settlements/{settlement['id']}", 200) == settlement


def test_settle_whole_month(api, shop):
    client, _ = api
    for paid in ("2026-08-23", "2026-09-10", "2026-09-22"):
        _order(client, shop, payment_method_id=shop["digipay"], order_date=paid)
    _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-09-23")
    settlement = _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["digipay"], "settled_date": "2026-09-29",
        "amount_received": 290000, "jalali_year": 1405, "jalali_month": 6,
    })
    assert (settlement["expected_amount"], settlement["difference"], len(settlement["orders"])) == (
        291000, -1000, 3,
    )
    (group,) = _call(client, "get", "/settlements/pending", 200)[0]["groups"]
    assert (group["jalali_month"], group["can_settle"]) == (7, False)


def test_monthly_partial_settlement_is_422_and_writes_nothing(api, shop):
    client, conn = api
    order_id = _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-09-10")["order"]["id"]
    error = _error(_call(client, "post", "/settlements", 422, json={
        "payment_method_id": shop["digipay"], "settled_date": "2026-09-29",
        "amount_received": 97000, "order_ids": [order_id], "jalali_year": 1405, "jalali_month": 6,
    }))
    assert error["field"] == "order_ids"
    assert "whole months only" in error["message"]
    assert _count(conn, "settlements") == 0


def test_monthly_settlement_conflicts(api, shop):
    client, conn = api
    _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-09-10")
    _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-10-01")
    base = {"payment_method_id": shop["digipay"], "amount_received": 97000}
    # Mehr has not ended.
    assert "has not ended" in _error(_call(client, "post", "/settlements", 409, json={
        **base, "settled_date": "2026-10-06", "jalali_year": 1405, "jalali_month": 7,
    }))["message"]
    # Empty ended month.
    assert "Nothing to settle" in _error(_call(client, "post", "/settlements", 409, json={
        **base, "settled_date": "2026-09-29", "jalali_year": 1405, "jalali_month": 5,
    }))["message"]
    # Inside the (ended) month.
    assert _error(_call(client, "post", "/settlements", 422, json={
        **base, "settled_date": "2026-09-22", "jalali_year": 1405, "jalali_month": 6,
    }))["field"] == "settled_date"
    _call(client, "post", "/settlements", 201, json={
        **base, "settled_date": "2026-09-29", "jalali_year": 1405, "jalali_month": 6,
    })
    assert "already settled" in _error(_call(client, "post", "/settlements", 409, json={
        **base, "settled_date": "2026-09-30", "jalali_year": 1405, "jalali_month": 6,
    }))["message"]
    assert _count(conn, "settlements") == 1


def test_subset_settlement_refusals(api, shop):
    client, conn = api
    mine = _order(client, shop, payment_method_id=shop["card"], order_date="2026-10-01")["order"]["id"]
    foreign = _order(client, shop, payment_method_id=shop["zarinpal"], order_date="2026-10-01")["order"]["id"]
    cancelled = _order(client, shop, payment_method_id=shop["card"], order_date="2026-10-01",
                       status="PAID")["order"]["id"]
    _call(client, "post", f"/orders/{cancelled}/return", 200, json={"status": "CANCELLED"})
    base = {"payment_method_id": shop["card"], "settled_date": "2026-10-02", "amount_received": 1}

    for order_ids, status, field in (
        ([mine, foreign], 422, "order_ids"),
        ([mine, mine], 422, "order_ids"),
        ([999], 422, "order_ids"),
        ([], 422, "order_ids"),
        ([mine, cancelled], 409, None),
    ):
        error = _error(_call(client, "post", "/settlements", status, json={**base, "order_ids": order_ids}))
        assert error["field"] == field
    assert _error(_call(client, "post", "/settlements", 422, json={**base, "jalali_month": 7,
                                                                   "order_ids": [mine]}))["field"] == "jalali_month"
    assert _error(_call(client, "post", "/settlements", 422, json={
        **base, "order_ids": [mine], "settled_date": "2026-10-07",
    }))["field"] == "settled_date"
    assert _count(conn, "settlements") == 0

    _call(client, "post", "/settlements", 201, json={**base, "order_ids": [mine]})
    assert "already in settlement" in _error(
        _call(client, "post", "/settlements", 409, json={**base, "order_ids": [mine]})
    )["message"]


@pytest.mark.parametrize(
    "override, field",
    [
        ({"order_ids": [True]}, "order_ids"),
        ({"order_ids": ["1"]}, "order_ids"),
        ({"order_ids": [1.0]}, "order_ids"),
        ({"order_ids": "1"}, "order_ids"),
        ({"payment_method_id": "1"}, "payment_method_id"),
        ({"payment_method_id": True}, "payment_method_id"),
        ({"payment_method_id": 1.0}, "payment_method_id"),
        ({"amount_received": 1000.5}, "amount_received"),
        ({"amount_received": 1000.0}, "amount_received"),
        ({"amount_received": "1000"}, "amount_received"),
        ({"amount_received": True}, "amount_received"),
        ({"settled_date": "02/10/2026"}, "settled_date"),
        ({"jalali_year": "1405"}, "jalali_year"),
        ({"expected_amount": 1}, "expected_amount"),
    ],
)
def test_settlement_create_strict_body(api, shop, override, field):
    client, conn = api
    order_id = _order(client, shop, payment_method_id=shop["card"], order_date="2026-10-01")["order"]["id"]
    body = {"payment_method_id": shop["card"], "settled_date": "2026-10-02",
            "amount_received": 1000, "order_ids": [order_id], **override}
    assert field in _pydantic_fields(_call(client, "post", "/settlements", 422, json=body))
    assert _count(conn, "settlements") == 0


def test_settlement_for_missing_method_is_404(api, shop):
    client, _ = api
    _call(client, "post", "/settlements", 404, json={
        "payment_method_id": 999, "settled_date": "2026-10-02", "amount_received": 1, "order_ids": [1],
    })


def test_list_and_get_settlements(api, shop):
    client, _ = api
    a = _order(client, shop, payment_method_id=shop["card"], order_date="2026-10-01")["order"]["id"]
    b = _order(client, shop, payment_method_id=shop["zarinpal"], order_date="2026-10-01")["order"]["id"]
    s1 = _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["card"], "settled_date": "2026-10-02",
        "amount_received": 100000, "order_ids": [a]})["id"]
    s2 = _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["zarinpal"], "settled_date": "2026-10-04",
        "amount_received": 99000, "order_ids": [b]})["id"]

    listed = _call(client, "get", "/settlements", 200)
    assert [s["id"] for s in listed] == [s2, s1]
    assert (listed[0]["order_count"], listed[0]["difference"]) == (1, 1000)
    assert [s["id"] for s in _call(client, "get", "/settlements", 200,
                                   params={"payment_method_id": shop["card"]})] == [s1]
    assert [s["id"] for s in _call(client, "get", "/settlements", 200,
                                   params={"start_date": "2026-10-03", "end_date": "2026-10-04"})] == [s2]
    _call(client, "get", "/settlements", 422, params={"start_date": "2026/10/01"})
    _call(client, "get", "/settlements/999", 404)


def test_patch_settlement(api, shop):
    client, _ = api
    a = _order(client, shop, payment_method_id=shop["card"], order_date="2026-10-01")["order"]["id"]
    created = _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["card"], "settled_date": "2026-10-02",
        "amount_received": 100000, "order_ids": [a], "note": "first"})
    path = f"/settlements/{created['id']}"

    patched = _call(client, "patch", path, 200, json={"amount_received": 95000})
    assert (patched["amount_received"], patched["difference"], patched["note"]) == (95000, -5000, "first")
    patched = _call(client, "patch", path, 200, json={"settled_date": "2026-10-05", "note": None})
    assert (patched["settled_date"], patched["note"]) == ("2026-10-05", None)
    assert (patched["expected_amount"], [o["id"] for o in patched["orders"]]) == (100000, [a])

    assert _error(_call(client, "patch", path, 422, json={"settled_date": "2026-09-30"}))["field"] == "settled_date"
    assert _error(_call(client, "patch", path, 422, json={"settled_date": "2026-10-07"}))["field"] == "settled_date"
    assert _error(_call(client, "patch", path, 422, json={"amount_received": -1}))["field"] == "amount_received"
    assert _error(_call(client, "patch", path, 422, json={"amount_received": None}))["field"] == "amount_received"
    for body, field in (({"amount_received": 1.5}, "amount_received"),
                        ({"order_ids": [a]}, "order_ids"),
                        ({"expected_amount": 1}, "expected_amount")):
        assert field in _pydantic_fields(_call(client, "patch", path, 422, json=body))
    _call(client, "patch", "/settlements/999", 404, json={"note": "x"})
    assert _call(client, "get", path, 200) == patched


def test_patch_monthly_settlement_date_rule(api, shop):
    client, _ = api
    _order(client, shop, payment_method_id=shop["digipay"], order_date="2026-09-10")
    created = _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["digipay"], "settled_date": "2026-09-29",
        "amount_received": 97000, "jalali_year": 1405, "jalali_month": 6})
    path = f"/settlements/{created['id']}"
    assert _error(_call(client, "patch", path, 422, json={"settled_date": "2026-09-22"}))["field"] == "settled_date"
    assert _call(client, "patch", path, 200, json={"settled_date": "2026-09-23"})["settled_date"] == "2026-09-23"


def test_deactivated_method_still_settles_over_http(api, shop):
    client, _ = api
    a = _order(client, shop, payment_method_id=shop["card"], order_date="2026-10-01")["order"]["id"]
    _call(client, "post", f"/payment-methods/{shop['card']}/deactivate", 200)
    pending = _call(client, "get", "/settlements/pending", 200)
    assert (pending[0]["name"], pending[0]["is_active"]) == ("Card to card", 0)
    created = _call(client, "post", "/settlements", 201, json={
        "payment_method_id": shop["card"], "settled_date": "2026-10-02",
        "amount_received": 100000, "order_ids": [a]})
    _call(client, "patch", f"/settlements/{created['id']}", 200, json={"note": "ok"})


# ================================================================ report


def test_payment_method_report_endpoint(api, shop):
    client, _ = api
    _order(client, shop, payment_method_id=shop["zarinpal"], order_date="2026-10-01")
    _order(client, shop, payment_method_id=None, order_date="2026-10-01", transaction_fee=700)
    rows = _call(client, "get", "/reports/payment-methods", 200)
    assert [r["name"] for r in rows] == ["Card to card", "Digipay", "Zarinpal", None]
    zarinpal = rows[2]
    assert (zarinpal["order_count"], zarinpal["transaction_fees"], zarinpal["pending_expected"]) == (1, 2000, 98000)
    assert rows[3]["payment_method_id"] is None and rows[3]["transaction_fees"] == 700
    pnl = _call(client, "get", "/reports/profit-and-loss", 200)
    assert sum(r["transaction_fees"] for r in rows) == pnl["transaction_fees"]
    assert sum(r["customer_total"] for r in rows) == pnl["total_revenue"]

    empty = _call(client, "get", "/reports/payment-methods", 200,
                  params={"start_date": "2026-11-01", "end_date": "2026-11-30"})
    assert all(r["order_count"] == 0 for r in empty)
    _call(client, "get", "/reports/payment-methods", 422, params={"start_date": "2026/11/01"})


# ================================================================ invoice


def test_invoice_pdf_never_shows_computed_fee(api, shop):
    client, _ = api
    method_id = _method(client, "Odd fee", "IMMEDIATE", fee_fixed=7777)["id"]
    created = _order(client, shop, payment_method_id=method_id, price=123000, shipping_charge=45000,
                     payment_reference="REF-998877")
    assert created["order"]["transaction_fee"] == 7777

    response = client.get(f"/orders/{created['order']['id']}/invoice.pdf")
    assert response.status_code == 200
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    def shown(rial, currency="TOMAN"):
        # The invoice prints stored Rial in the display currency (Toman by default).
        return format_display_number(
            rial, currency, decimal_mark=invoice_module.PERSIAN_DECIMAL_MARK
        ).translate(invoice_module.PERSIAN_DIGIT_MAP)

    assert shown(45000) in text
    assert shown(created["customer_total"]) in text
    for hidden in (
        shown(7777), shown(7777, "RIAL"), "7,777", "7777",
        shown(created["customer_total"] - 7777), shown(created["customer_total"] - 7777, "RIAL"),
    ):
        assert hidden not in text
    assert "Odd fee" not in text
