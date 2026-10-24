"""Every public write function in db/ runs as one labelled audit operation, and a new
write function that forgets `@audited()` fails the scan below."""

import inspect
import re

import pytest

import db
from db import (
    adjustments, categories, distributions, expenses, materials, orders, packaging, partners,
    payment_methods, postage, production, products, purchases, recipes, returns, settings,
    settlements, stocktake, suppliers,
)
from db.audit import list_audit_log
from tests.helpers import cat, stocked_product

# Public functions that write but are deliberately not one labelled operation.
NOT_AUDITED_OPERATIONS = {
    "next_counter",     # invoice numbering (counters table is not audited)
    "reset_audit_log",  # the log's own deliberate reset
    "audit_operation",  # the helper itself
    "init_db",          # migrations
    "transaction",
    "audit_trigger_sql",  # builds migration SQL text; writes nothing
}

_WRITES = re.compile(r"\b(INSERT|UPDATE|DELETE)\b|\btransaction\(")


def _public_writers():
    found = []
    for module_name in sorted(
        m for m in (
            "adjustments", "categories", "connection", "distributions", "expenses", "materials",
            "order_voids", "orders", "packaging", "partners", "payment_methods", "postage", "production",
            "products", "purchases", "recipes", "returns", "settings", "settlements", "stocktake", "suppliers",
            "audit",
        )
    ):
        module = getattr(__import__(f"db.{module_name}", fromlist=["x"]), "__dict__")
        for name, func in module.items():
            if (
                inspect.isfunction(func)
                and not name.startswith("_")
                and getattr(func, "__module__", "") == f"db.{module_name}"
                and _WRITES.search(inspect.getsource(getattr(func, "__wrapped__", func)))
            ):
                found.append((module_name, name, func))
    return found


def test_every_public_write_function_is_an_audited_operation():
    unwrapped = [
        f"db.{module}.{name}"
        for module, name, func in _public_writers()
        if name not in NOT_AUDITED_OPERATIONS and not hasattr(func, "__wrapped__")
    ]
    assert unwrapped == [], f"add @audited() to: {unwrapped}"


def test_the_scan_finds_the_known_writers():
    names = {name for _, name, _ in _public_writers()}
    assert {"record_order", "process_return", "record_settlement", "set_setting",
            "add_payment_method", "run_production_batch"} <= names


# ----------------------------------------------------------------- behaviour


def _order(conn, status="COMPLETED"):
    product_id = stocked_product(conn)
    return orders.record_order(
        conn, "IN_PERSON",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
        status=status, packaging_kit_id=None,
    )


def _kit_material(conn):
    return materials.add_material(conn, "Audit Box", "STOCK", 1000, initial_stock=10)


def _recipe_product(conn):
    product_id = products.add_product(conn, "Audit Album", cat(conn, "VINYL"), 3000, 2000)
    material_id = materials.add_material(conn, "Audit Paper", "STOCK", 100, initial_stock=50)
    recipes.add_recipe_item(conn, product_id, material_id, 2)
    return product_id, material_id


def _two_partners(conn):
    partners.add_partner(conn, "Audit Partner A", 60.0)
    partners.add_partner(conn, "Audit Partner B", 40.0)


CASES = {
    "record_order": (lambda c: _order(c), {"orders", "order_items", "products", "stock_movements"}),
    "update_order_status": (
        lambda c: orders.update_order_status(c, _order(c, "PENDING"), "PAID"), {"orders"},
    ),
    "process_return": (
        lambda c: returns.process_return(c, _order(c), "REFUNDED"), {"orders", "products"},
    ),
    "add_payment_method": (
        lambda c: payment_methods.add_payment_method(c, "Audit Pay", "IMMEDIATE"),
        {"payment_methods"},
    ),
    "record_material_purchase": (
        lambda c: purchases.record_material_purchase(
            c, materials.add_material(c, "Audit Glue", "STOCK", 0), 5, 50_000
        ),
        {"material_purchases", "materials", "stock_movements"},
    ),
    "run_production_batch": (
        lambda c: production.run_production_batch(c, _recipe_product(c)[0], 2),
        {"production_batches", "production_batch_materials", "materials", "products", "stock_movements"},
    ),
    "record_stock_adjustment": (
        lambda c: adjustments.record_stock_adjustment(c, "MATERIAL", _kit_material(c), -1, "WASTE"),
        {"stock_movements", "materials"},
    ),
    "record_service_waste": (
        lambda c: adjustments.record_service_waste(c, materials.add_material(c, "Audit Printing", "SERVICE", 90_000), 2),
        {"stock_movements"},
    ),
    "add_expense": (
        lambda c: expenses.add_expense(c, expenses.add_expense_category(c, "Audit Ads"), 5000),
        {"expenses"},
    ),
    "record_postage_batch": (
        lambda c: postage.record_postage_batch(c, 100_000, 4), {"postage_batches"},
    ),
    "add_partner": (lambda c: partners.add_partner(c, "Audit Partner", 100.0), {"partners"}),
    "update_supplier": (
        lambda c: suppliers.update_supplier(c, suppliers.add_supplier(c, "Audit Supplier"), phone="021"),
        {"suppliers"},
    ),
    "add_product": (
        lambda c: products.add_product(c, "Audit Tee", cat(c, "VINYL"), 3000, 2000), {"products"},
    ),
    "add_recipe_item": (lambda c: _recipe_product(c), {"product_recipe"}),
    "add_kit_item": (
        lambda c: packaging.add_kit_item(c, packaging.create_kit(c, "Audit Kit"), _kit_material(c), 1),
        {"packaging_kit_items"},
    ),
    "create_category": (
        lambda c: categories.create_category(c, "PRODUCT", "Audit Category"), {"categories"},
    ),
    "set_setting": (lambda c: settings.set_setting(c, "postage_estimate_window", 4), {"settings"}),
    "record_profit_distribution": (
        lambda c: (_two_partners(c), distributions.record_profit_distribution(
            c, "2026-01-01", "2026-01-31", 1000, distribution_date="2026-02-01", allow_exceeding=True
        )),
        {"profit_distributions", "distribution_shares"},
    ),
}


@pytest.mark.parametrize("label", sorted(CASES))
def test_public_write_is_logged_as_one_labelled_operation(test_db, label):
    action, expected_entities = CASES[label]
    action(test_db)

    page = list_audit_log(test_db, operation=label, limit=500)
    assert page["total"] > 0, f"no audit rows labelled {label}"
    entities = {entry["entity_type"] for entry in page["items"]}
    assert expected_entities <= entities
    # Every row of the call carries one shared op_id (setup calls log their own operations).
    assert all(entry["op_id"] for entry in page["items"])
    assert len({entry["op_id"] for entry in page["items"]}) == 1


def test_a_failed_public_write_leaves_no_audit_rows(test_db):
    product_id = stocked_product(test_db, stock=1)
    before = test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    with pytest.raises(Exception):
        orders.record_order(
            test_db, "IN_PERSON",
            [{"product_id": product_id, "quantity": 5, "unit_price": 3000}],
            packaging_kit_id=None,
        )
    assert test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == before
    assert test_db.execute("SELECT COUNT(*) FROM audit_context").fetchone()[0] == 0
