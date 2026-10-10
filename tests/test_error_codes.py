"""Stable error codes (db/errors.py ErrorCode) and the API error envelope.

Each raise site the UI tells apart carries a specific code and details; the
English message is unchanged (the matches below are the old message texts)."""

import re
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import db.orders
import db.settlements
from api.main import app
from db import jalali
from db.categories import create_category, deactivate_category, reactivate_category, validate_assignable
from db.distributions import preview_profit_distribution, record_profit_distribution
from db.errors import (
    DEFAULT_CODES,
    AppError,
    ConflictError,
    ErrorCode,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from db.materials import add_material
from db.orders import record_order, set_paid_date
from db.partners import add_partner
from db.payment_methods import (
    add_payment_method,
    deactivate_payment_method,
    get_payment_method,
    update_payment_method,
)
from db.production import run_production_batch
from db.products import add_product, set_made_to_order
from db.purchases import record_material_purchase
from db.recipes import add_recipe_item
from db.settings import update_channel_settings
from db.settlements import record_settlement
from db.suppliers import update_supplier
from tests.helpers import stocked_product

TODAY = date(2026, 10, 6)  # 14 Mehr 1405; Shahrivar 1405 = 2026-08-23..2026-09-22

SPECIFIC_CODES = [c for c in ErrorCode if c not in DEFAULT_CODES]


def _raises(fn, cls, code, match, *, field=None, details=None):
    with pytest.raises(cls, match=match) as exc_info:
        fn()
    exc = exc_info.value
    assert type(exc) is cls
    assert exc.code == code
    if field is not None:
        assert exc.field == field
    assert exc.details == (details or {})
    return exc


# ---------------------------------------------------------------- the classes


@pytest.mark.parametrize(
    "exc, code",
    [
        (AppError("x"), ErrorCode.APP_ERROR),
        (NotFoundError("x"), ErrorCode.NOT_FOUND),
        (ValidationError("x", field="f"), ErrorCode.VALIDATION_FAILED),
        (ConflictError("x"), ErrorCode.CONFLICT),
        (InsufficientStockError("x", "Widget", 3, 1), ErrorCode.INSUFFICIENT_STOCK),
    ],
)
def test_class_default_codes(exc, code):
    assert exc.code == code
    assert str(exc) == "x"
    expected = {"item_name": "Widget", "needed": 3, "available": 1} if code == ErrorCode.INSUFFICIENT_STOCK else {}
    assert exc.details == expected


def test_explicit_code_and_details_override_the_default():
    exc = ValidationError("msg", "f", code=ErrorCode.DATE_IN_FUTURE, details={"today": "2026-10-06"})
    assert (exc.code, exc.field, exc.details, str(exc)) == (
        ErrorCode.DATE_IN_FUTURE, "f", {"today": "2026-10-06"}, "msg"
    )
    assert ConflictError("m", details=None).details == {}


def test_every_specific_code_is_raised_in_db():
    """The 29 specific codes, not the class defaults (covered above)."""
    assert len(SPECIFIC_CODES) == 29
    source = "\n".join(p.read_text(encoding="utf-8") for p in Path("db").glob("*.py") if p.name != "errors.py")
    unused = [c.name for c in SPECIFIC_CODES if not re.search(rf"ErrorCode\.{c.name}\b", source)]
    assert unused == []


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def set_today(monkeypatch):
    for module in (db.orders, db.settlements):
        monkeypatch.setattr(module, "today_local", lambda conn=None: TODAY)


@pytest.fixture
def setup(test_db, set_today):
    return {
        "product_id": stocked_product(test_db, stock=1000),
        "card": add_payment_method(test_db, "Card to card", "IMMEDIATE"),
        "zarinpal": add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1, fee_bps=100),
        "digipay": add_payment_method(test_db, "Digipay", "DAY_OF_NEXT_MONTH", 7, fee_bps=300),
    }


def _order(conn, product_id, method_id, paid, status="COMPLETED", **kwargs):
    return record_order(
        conn,
        "WEBSITE",
        [{"product_id": product_id, "quantity": 1, "unit_price": 100000}],
        order_date=paid,
        shipping_charge=0,
        packaging_kit_id=None,
        postage_cost=0,
        payment_method_id=method_id,
        status=status,
        **kwargs,
    )


# ---------------------------------------------------------------- orders / payment methods


def test_paid_date_in_future(test_db, setup):
    _raises(
        lambda: _order(test_db, setup["product_id"], setup["card"], "2026-10-01", paid_date="2026-10-07"),
        ValidationError, ErrorCode.DATE_IN_FUTURE, "is in the future",
        field="paid_date", details={"today": "2026-10-06"},
    )


def test_paid_date_in_settled_month(test_db, setup):
    _order(test_db, setup["product_id"], setup["digipay"], "2026-09-10")
    sid = record_settlement(test_db, setup["digipay"], "2026-10-01", 1, jalali_year=1405, jalali_month=6)
    _raises(
        lambda: _order(test_db, setup["product_id"], setup["digipay"], "2026-09-15"),
        ConflictError, ErrorCode.MONTH_ALREADY_SETTLED, r"month 1405/06 is already settled \(settlement #",
        details={"jalali_year": 1405, "jalali_month": 6, "settlement_id": sid},
    )


def test_set_paid_date_on_unpaid_order(test_db, setup):
    oid = _order(test_db, setup["product_id"], setup["card"], "2026-10-01", status="PENDING")
    _raises(
        lambda: set_paid_date(test_db, oid, "2026-10-02"),
        ConflictError, ErrorCode.ORDER_NOT_PAID, ", not paid",
        details={"order_id": oid, "status": "PENDING"},
    )


def test_set_paid_date_on_settled_order(test_db, setup):
    oid = _order(test_db, setup["product_id"], setup["card"], "2026-10-01")
    sid = record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[oid])
    _raises(
        lambda: set_paid_date(test_db, oid, "2026-10-02"),
        ConflictError, ErrorCode.ORDER_ALREADY_SETTLED, rf"is part of settlement #{sid}",
        details={"order_id": oid, "settlement_id": sid},
    )


def test_order_with_inactive_method(test_db, setup):
    deactivate_payment_method(test_db, setup["card"])
    _raises(
        lambda: _order(test_db, setup["product_id"], setup["card"], "2026-10-01"),
        ValidationError, ErrorCode.PAYMENT_METHOD_INACTIVE, "is not active",
        field="payment_method_id", details={"payment_method_id": setup["card"]},
    )


def test_channel_default_inactive_method(test_db, setup):
    deactivate_payment_method(test_db, setup["card"])
    _raises(
        lambda: update_channel_settings(test_db, "WEBSITE", default_payment_method_id=setup["card"]),
        ValidationError, ErrorCode.PAYMENT_METHOD_INACTIVE, "is not active",
        field="default_payment_method_id", details={"payment_method_id": setup["card"]},
    )


def test_payment_method_not_found(test_db):
    _raises(
        lambda: get_payment_method(test_db, 999),
        NotFoundError, ErrorCode.PAYMENT_METHOD_NOT_FOUND, "Payment method with id 999 does not exist",
        details={"payment_method_id": 999},
    )


def test_payment_method_rule_change_with_pending_orders(test_db, setup):
    _order(test_db, setup["product_id"], setup["zarinpal"], "2026-10-01")
    _raises(
        lambda: update_payment_method(test_db, setup["zarinpal"], settlement_days=3),
        ConflictError, ErrorCode.PAYMENT_METHOD_RULE_PENDING, "1 paid order is still pending settlement",
        details={"pending_count": 1},
    )


def test_payment_method_duplicate_name(test_db, setup):
    _raises(
        lambda: add_payment_method(test_db, "Card to card", "IMMEDIATE"),
        ConflictError, ErrorCode.PAYMENT_METHOD_DUPLICATE_NAME, "payment method named .* already exists",
    )


def test_duplicate_name_on_rename(test_db, setup):
    _raises(
        lambda: update_payment_method(test_db, setup["zarinpal"], name="Card to card"),
        ConflictError, ErrorCode.PAYMENT_METHOD_DUPLICATE_NAME, "already exists",
    )


# ---------------------------------------------------------------- settlements


def test_settled_date_in_future(test_db, setup):
    oid = _order(test_db, setup["product_id"], setup["card"], "2026-10-01")
    _raises(
        lambda: record_settlement(test_db, setup["card"], "2026-10-07", 1, order_ids=[oid]),
        ValidationError, ErrorCode.DATE_IN_FUTURE, "is in the future",
        field="settled_date", details={"today": "2026-10-06"},
    )


def test_settled_date_before_month_end(test_db, setup):
    _order(test_db, setup["product_id"], setup["digipay"], "2026-09-10")
    _, last = jalali.month_range(1405, 6)
    _raises(
        lambda: record_settlement(test_db, setup["digipay"], "2026-09-20", 1, jalali_year=1405, jalali_month=6),
        ValidationError, ErrorCode.SETTLEMENT_DATE_BEFORE_MONTH_END, "must be after the end of month 1405/06",
        field="settled_date", details={"jalali_year": 1405, "jalali_month": 6, "month_end": last.isoformat()},
    )


def test_settled_date_before_paid(test_db, setup):
    oid = _order(test_db, setup["product_id"], setup["card"], "2026-10-05")
    _raises(
        lambda: record_settlement(test_db, setup["card"], "2026-10-04", 1, order_ids=[oid]),
        ValidationError, ErrorCode.SETTLEMENT_DATE_BEFORE_PAID, r"before the latest paid date of its orders \(2026-10-05\)",
        field="settled_date", details={"latest_paid_date": "2026-10-05"},
    )


def test_settlement_wrong_method(test_db, setup):
    oid = _order(test_db, setup["product_id"], setup["zarinpal"], "2026-10-01")
    _raises(
        lambda: record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[oid]),
        ValidationError, ErrorCode.SETTLEMENT_ORDER_WRONG_METHOD, rf"Order #{oid} was not paid with",
        field="order_ids", details={"order_id": oid},
    )


def test_settlement_unpaid_order(test_db, setup):
    oid = _order(test_db, setup["product_id"], setup["card"], "2026-10-01", status="PENDING")
    _raises(
        lambda: record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[oid]),
        ConflictError, ErrorCode.ORDER_NOT_PAID, rf"Order #{oid} is PENDING, not paid",
        details={"order_id": oid, "status": "PENDING"},
    )


def test_settlement_order_already_settled(test_db, setup):
    oid = _order(test_db, setup["product_id"], setup["card"], "2026-10-01")
    sid = record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[oid])
    _raises(
        lambda: record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[oid]),
        ConflictError, ErrorCode.ORDER_ALREADY_SETTLED, rf"Order #{oid} is already in settlement #{sid}",
        details={"order_id": oid, "settlement_id": sid},
    )


def test_settlement_month_not_ended(test_db, setup):
    _, last = jalali.month_range(1405, 7)
    _raises(
        lambda: record_settlement(test_db, setup["digipay"], "2026-10-06", 1, jalali_year=1405, jalali_month=7),
        ConflictError, ErrorCode.SETTLEMENT_MONTH_NOT_ENDED, rf"Month 1405/07 has not ended yet \(it ends {last.isoformat()}\)",
        details={"jalali_year": 1405, "jalali_month": 7, "month_end": last.isoformat()},
    )


def test_settlement_month_already_settled(test_db, setup):
    _order(test_db, setup["product_id"], setup["digipay"], "2026-09-10")
    sid = record_settlement(test_db, setup["digipay"], "2026-10-01", 1, jalali_year=1405, jalali_month=6)
    _raises(
        lambda: record_settlement(test_db, setup["digipay"], "2026-10-01", 1, jalali_year=1405, jalali_month=6),
        ConflictError, ErrorCode.MONTH_ALREADY_SETTLED, rf"month 1405/06 is already settled \(settlement #{sid}\)",
        details={"jalali_year": 1405, "jalali_month": 6, "settlement_id": sid},
    )


def test_settlement_month_integrity_race(test_db, setup, monkeypatch):
    def boom(*args, **kwargs):
        raise sqlite3.IntegrityError("UNIQUE constraint failed")

    monkeypatch.setattr(db.settlements, "_orders_for_month", boom)
    _raises(
        lambda: record_settlement(test_db, setup["digipay"], "2026-10-01", 1, jalali_year=1405, jalali_month=6),
        ConflictError, ErrorCode.MONTH_ALREADY_SETTLED, r"month 1405/06 is already settled\.$",
        details={"jalali_year": 1405, "jalali_month": 6, "settlement_id": None},
    )


def test_settlement_integrity_conflict(test_db, setup, monkeypatch):
    def boom(*args, **kwargs):
        raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")

    monkeypatch.setattr(db.settlements, "_orders_for_subset", boom)
    _raises(
        lambda: record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[1]),
        ConflictError, ErrorCode.SETTLEMENT_CONFLICT, "conflicts with existing data",
    )


def test_settlement_raced(test_db, setup, monkeypatch):
    first = _order(test_db, setup["product_id"], setup["card"], "2026-10-01")
    second = _order(test_db, setup["product_id"], setup["card"], "2026-10-01")
    earlier = record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[first])
    original = db.settlements._orders_for_subset

    def settled_meanwhile(conn, *args, **kwargs):
        orders = original(conn, *args, **kwargs)
        conn.execute("UPDATE orders SET settlement_id = ? WHERE id = ?", (earlier, second))
        return orders

    monkeypatch.setattr(db.settlements, "_orders_for_subset", settled_meanwhile)
    _raises(
        lambda: record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[second]),
        ConflictError, ErrorCode.SETTLEMENT_RACED, "settled meanwhile",
    )


def test_settlement_nothing_pending(test_db, setup):
    _raises(
        lambda: record_settlement(test_db, setup["digipay"], "2026-10-01", 1, jalali_year=1405, jalali_month=5),
        ConflictError, ErrorCode.SETTLEMENT_NOTHING_PENDING, "^Nothing to settle",
        details={"jalali_year": 1405, "jalali_month": 5},
    )


def test_settlement_whole_months_only(test_db, setup):
    _raises(
        lambda: record_settlement(test_db, setup["digipay"], "2026-10-01", 1, order_ids=[1]),
        ValidationError, ErrorCode.SETTLEMENT_WHOLE_MONTHS_ONLY, "settles whole months only",
        field="order_ids",
    )


@pytest.mark.parametrize("field", ["jalali_year", "jalali_month"])
def test_settlement_not_monthly(test_db, setup, field):
    _raises(
        lambda: record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[1], **{field: 6}),
        ValidationError, ErrorCode.SETTLEMENT_NOT_MONTHLY, "applies only to a method that settles whole months",
        field=field,
    )


# ---------------------------------------------------------------- distributions


def test_distribution_period_overlap(test_db):
    add_partner(test_db, "Alice", 60)
    add_partner(test_db, "Bob", 40)
    did = record_profit_distribution(test_db, "2026-01-01", "2026-01-31", 0)
    _raises(
        lambda: record_profit_distribution(test_db, "2026-01-15", "2026-02-15", 0),
        ConflictError, ErrorCode.DISTRIBUTION_PERIOD_OVERLAP, rf"overlaps distribution #{did} \(2026-01-01\.\.2026-01-31\)",
        details={"distribution_id": did, "period_start": "2026-01-01", "period_end": "2026-01-31"},
    )


def test_distribution_no_active_partners(test_db):
    _raises(
        lambda: preview_profit_distribution(test_db, "2026-01-01", "2026-01-31", 0),
        ValidationError, ErrorCode.DISTRIBUTION_NO_ACTIVE_PARTNERS, "^No active partners",
    )


def test_distribution_percent_sum(test_db):
    add_partner(test_db, "Alice", 50)
    _raises(
        lambda: preview_profit_distribution(test_db, "2026-01-01", "2026-01-31", 0),
        ValidationError, ErrorCode.DISTRIBUTION_PERCENT_SUM, "must sum to 100%",
    )


def test_distribution_exceeds_undistributed(test_db):
    add_partner(test_db, "Alice", 100)
    _raises(
        lambda: record_profit_distribution(test_db, "2026-01-01", "2026-01-31", 1000),
        ValidationError, ErrorCode.DISTRIBUTION_EXCEEDS_UNDISTRIBUTED, "exceeds undistributed profit",
        field="total_amount_distributed",
    )


def test_distribution_period_order(test_db):
    _raises(
        lambda: preview_profit_distribution(test_db, "2026-02-01", "2026-01-31", 0),
        ValidationError, ErrorCode.DISTRIBUTION_PERIOD_ORDER, "cannot be before",
        field="period_end",
    )


# ---------------------------------------------------------------- categories


def test_category_duplicate_name(test_db):
    create_category(test_db, "PRODUCT", "Posters")
    _raises(
        lambda: create_category(test_db, "PRODUCT", "Posters"),
        ConflictError, ErrorCode.CATEGORY_DUPLICATE_NAME, "already exists at this level",
    )


def test_category_create_under_inactive_parent(test_db):
    parent = create_category(test_db, "PRODUCT", "Posters")
    deactivate_category(test_db, parent)
    _raises(
        lambda: create_category(test_db, "PRODUCT", "A3", parent),
        ValidationError, ErrorCode.CATEGORY_PARENT_INACTIVE, "^Parent category .* is inactive",
        field="parent_id",
    )


def test_category_reactivate_under_inactive_parent(test_db):
    parent = create_category(test_db, "PRODUCT", "Posters")
    child = create_category(test_db, "PRODUCT", "A3", parent)
    deactivate_category(test_db, child)
    deactivate_category(test_db, parent)
    _raises(
        lambda: reactivate_category(test_db, child),
        ConflictError, ErrorCode.CATEGORY_PARENT_INACTIVE, "^Parent category .* is inactive",
    )


def test_category_in_use(test_db):
    category = create_category(test_db, "PRODUCT", "Posters")
    add_product(test_db, "Tour poster", category, 1000, 800)
    add_product(test_db, "Album poster", category, 1000, 800)
    _raises(
        lambda: deactivate_category(test_db, category),
        ConflictError, ErrorCode.CATEGORY_IN_USE, "is used by 2",
        details={"item_count": 2},
    )


def test_category_deactivate_with_active_children(test_db):
    parent = create_category(test_db, "PRODUCT", "Posters")
    create_category(test_db, "PRODUCT", "A3", parent)
    _raises(
        lambda: deactivate_category(test_db, parent),
        ConflictError, ErrorCode.CATEGORY_HAS_SUBCATEGORIES, "active subcategories",
    )


def test_category_assign_to_split_category(test_db):
    parent = create_category(test_db, "PRODUCT", "Posters")
    create_category(test_db, "PRODUCT", "A3", parent)
    _raises(
        lambda: validate_assignable(test_db, parent, "PRODUCT"),
        ValidationError, ErrorCode.CATEGORY_HAS_SUBCATEGORIES, "subcategories",
        field="category_id",
    )


# ---------------------------------------------------------------- products / production / suppliers


def _product_details(product_id):
    return {"product_id": product_id, "product_name": "Test LP"}


def test_production_without_recipe(test_db):
    pid = stocked_product(test_db)
    _raises(
        lambda: run_production_batch(test_db, pid, 1),
        ValidationError, ErrorCode.PRODUCT_NO_RECIPE, "no recipe",
        details=_product_details(pid),
    )


def test_made_to_order_without_recipe(test_db):
    pid = stocked_product(test_db)
    _raises(
        lambda: set_made_to_order(test_db, pid, True),
        ValidationError, ErrorCode.PRODUCT_NO_RECIPE, "no recipe",
        field="made_to_order", details=_product_details(pid),
    )


def test_order_made_to_order_without_recipe(test_db, set_today):
    pid = stocked_product(test_db, stock=0)
    test_db.execute("UPDATE products SET made_to_order = 1 WHERE id = ?", (pid,))
    test_db.commit()
    _raises(
        lambda: _order(test_db, pid, None, "2026-10-01"),
        ValidationError, ErrorCode.PRODUCT_NO_RECIPE, "made-to-order but has no recipe",
        field="made_to_order", details=_product_details(pid),
    )


def test_order_without_unit_cost(test_db, set_today):
    pid = stocked_product(test_db)
    test_db.execute("UPDATE products SET unit_cost = NULL WHERE id = ?", (pid,))
    test_db.commit()
    _raises(
        lambda: _order(test_db, pid, None, "2026-10-01"),
        ValidationError, ErrorCode.PRODUCT_NO_UNIT_COST, "has no unit_cost",
        field="unit_cost", details=_product_details(pid),
    )


def test_order_made_to_order_from_stock_without_unit_cost(test_db, set_today):
    pid = stocked_product(test_db, stock=5)
    material = add_material(test_db, "Sleeve", "STOCK", 100, initial_stock=50)
    add_recipe_item(test_db, pid, material, 1)
    test_db.execute("UPDATE products SET made_to_order = 1, unit_cost = NULL WHERE id = ?", (pid,))
    test_db.commit()
    _raises(
        lambda: _order(test_db, pid, None, "2026-10-01"),
        ValidationError, ErrorCode.PRODUCT_NO_UNIT_COST, "has no unit_cost",
        field="unit_cost", details=_product_details(pid),
    )


def test_purchase_with_unknown_supplier(test_db):
    material = add_material(test_db, "Sleeve", "STOCK", 100)
    _raises(
        lambda: record_material_purchase(test_db, material, 10, 1000, supplier_id=999),
        NotFoundError, ErrorCode.SUPPLIER_NOT_FOUND, "Supplier with id 999 does not exist",
        details={"supplier_id": 999},
    )


def test_update_unknown_supplier(test_db):
    _raises(
        lambda: update_supplier(test_db, 999, name="Pressing plant"),
        NotFoundError, ErrorCode.SUPPLIER_NOT_FOUND, "Supplier with id 999 does not exist",
        details={"supplier_id": 999},
    )


# ---------------------------------------------------------------- API envelope


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _error(resp, status):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert list(body) == ["error"]
    assert set(body["error"]) == {"type", "code", "message", "field", "details"}
    return body["error"]


def test_api_404_envelope(client):
    error = _error(client.get("/products/999"), 404)
    assert error == {
        "type": "NotFoundError",
        "code": "NOT_FOUND",
        "message": "Product with id 999 does not exist",
        "field": None,
        "details": {},
    }


def test_api_404_specific_code(client):
    error = _error(client.get("/payment-methods/999"), 404)
    assert (error["type"], error["code"], error["details"]) == (
        "NotFoundError", "PAYMENT_METHOD_NOT_FOUND", {"payment_method_id": 999}
    )


def test_api_409_envelope(client):
    body = {"name": "Card", "settlement_rule": "IMMEDIATE"}
    assert client.post("/payment-methods", json=body).status_code == 201
    error = _error(client.post("/payment-methods", json=body), 409)
    assert error == {
        "type": "ConflictError",
        "code": "PAYMENT_METHOD_DUPLICATE_NAME",
        "message": "A payment method named 'Card' already exists",
        "field": None,
        "details": {},
    }


def test_api_422_envelope(client):
    error = _error(client.post("/suppliers", json={"name": "   "}), 422)
    assert (error["type"], error["code"], error["field"]) == ("ValidationError", "VALIDATION_FAILED", "name")


def test_api_400_envelope(monkeypatch, client):
    import api.routers.suppliers as suppliers_router

    def boom(conn):
        raise AppError("generic failure")

    monkeypatch.setattr(suppliers_router, "list_suppliers", boom)
    error = _error(client.get("/suppliers"), 400)
    assert error == {"type": "AppError", "code": "APP_ERROR", "message": "generic failure", "field": None, "details": {}}


def test_fastapi_request_validation_body_unchanged(client):
    resp = client.post("/suppliers", json={})
    assert resp.status_code == 422
    assert list(resp.json()) == ["detail"]


def test_openapi_lists_every_error_code():
    schemas = app.openapi()["components"]["schemas"]
    assert sorted(schemas["ErrorCode"]["enum"]) == sorted(c.value for c in ErrorCode)
    assert len(schemas["ErrorCode"]["enum"]) == 34
    assert schemas["ErrorBody"]["properties"]["code"] == {"$ref": "#/components/schemas/ErrorCode"}
    assert "ErrorEnvelope" in schemas
