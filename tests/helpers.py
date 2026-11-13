"""Shared test helpers (plain functions; fixtures live in conftest.py)."""

import sqlite3

from db.constants import LEGACY_PRODUCT_CATEGORIES
from db.payment_methods import add_payment_method
from db.products import add_product

SALE_METHOD_NAME = "Test cash"


def sale_method(conn: sqlite3.Connection) -> int:
    """Id of an active zero-fee IMMEDIATE payment method for tests that only need *a* method on a sale
    (a new order always has one). Created once per database; nothing else in the shop depends on it."""
    row = conn.execute("SELECT id FROM payment_methods WHERE name = ?", (SALE_METHOD_NAME,)).fetchone()
    return row["id"] if row else add_payment_method(conn, SALE_METHOD_NAME, "IMMEDIATE")


def api_sale_method(client) -> int:
    """`sale_method` over HTTP, for API tests that have a client and no connection."""
    for method in client.get("/payment-methods").json():
        if method["name"] == SALE_METHOD_NAME:
            return method["id"]
    created = client.post("/payment-methods", json={"name": SALE_METHOD_NAME, "settlement_rule": "IMMEDIATE"})
    assert created.status_code == 201, created.text
    return created.json()["id"]


def make_legacy_no_method(conn: sqlite3.Connection, order_id: int) -> int:
    """Turn an order into one recorded before the payment-method rule: no method and so no expected
    settlement date (the state `record_order` left when no method was given). A new order can no longer be
    recorded that way, so a test that needs such a legacy order records it with a method and calls this."""
    conn.execute(
        "UPDATE orders SET payment_method_id = NULL, expected_settlement_date = NULL WHERE id = ?", (order_id,)
    )
    return order_id


def cat(conn: sqlite3.Connection, code: str = "OTHER") -> int:
    """Id of the top-level PRODUCT category migration 005 seeded for a legacy code."""
    row = conn.execute(
        "SELECT id FROM categories WHERE kind = 'PRODUCT' AND parent_id IS NULL AND name = ?",
        (LEGACY_PRODUCT_CATEGORIES[code],),
    ).fetchone()
    return row["id"]


def stocked_product(
    conn: sqlite3.Connection, name: str = "Test LP", stock: int = 100, unit_cost: int = 500
) -> int:
    """An active VINYL product with stock and a unit cost, ready to sell."""
    product_id = add_product(conn, name, cat(conn, "VINYL"), 3000, 2000)
    conn.execute(
        "UPDATE products SET current_stock = ?, unit_cost = ? WHERE id = ?",
        (stock, unit_cost, product_id),
    )
    conn.commit()
    return product_id
