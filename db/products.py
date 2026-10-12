"""Finished goods: add/list/get (with `category_name`, `parent_category_name` joined in), update prices, move category, deactivate/reactivate.
Every product has `category_id`. `products.category` is a legacy column (NULL after migration 005); don't read it — it will be dropped."""

import sqlite3

from db.audit import audited
from db.categories import validate_assignable
from db.connection import transaction
from db.costing import check_money
from db.errors import ErrorCode, NotFoundError, ValidationError
from db.name_keys import duplicate_guard
from db.names import name_key, stored_form

# Products carry their category's name (and its parent's, for a subcategory)
# so callers never need a second lookup. products.category is the legacy code
# column from before migration 005; new products store NULL there.
_SELECT = """
    SELECT products.*,
           c.name AS category_name,
           c.parent_id AS parent_category_id,
           pc.name AS parent_category_name
    FROM products
    JOIN categories c ON c.id = products.category_id
    LEFT JOIN categories pc ON pc.id = c.parent_id
"""


def _validate_name(name: str) -> str:
    stored = stored_form(name) if isinstance(name, str) else ""
    if not stored:
        raise ValidationError("name is required and cannot be empty", field="name")
    return stored


def _validate_price(price: int, field_name: str) -> None:
    check_money(price, field_name)
    if price < 0:
        raise ValidationError(f"{field_name} must be >= 0, got {price}", field=field_name)


@audited()
def add_product(
    conn: sqlite3.Connection,
    name: str,
    category_id: int,
    retail_price: int,
    wholesale_price: int,
    made_to_order: bool = False,
) -> int:
    name = _validate_name(name)
    validate_assignable(conn, category_id, "PRODUCT")
    _validate_price(retail_price, "retail_price")
    _validate_price(wholesale_price, "wholesale_price")

    with duplicate_guard(conn, "products", name):
        with transaction(conn):
            cursor = conn.execute(
                """
                INSERT INTO products
                    (name, name_key, category_id, retail_price, wholesale_price, made_to_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, name_key(name), category_id, retail_price, wholesale_price, int(made_to_order)),
            )
    return cursor.lastrowid


def list_products(
    conn: sqlite3.Connection, active_only: bool = True
) -> list[dict]:
    if active_only:
        rows = conn.execute(
            f"{_SELECT} WHERE products.is_active = 1 ORDER BY products.name"
        ).fetchall()
    else:
        rows = conn.execute(f"{_SELECT} ORDER BY products.name").fetchall()
    return [dict(row) for row in rows]


def get_product(conn: sqlite3.Connection, product_id: int) -> dict | None:
    row = conn.execute(f"{_SELECT} WHERE products.id = ?", (product_id,)).fetchone()
    return dict(row) if row is not None else None


@audited()
def update_product_prices(
    conn: sqlite3.Connection,
    product_id: int,
    retail_price: int | None = None,
    wholesale_price: int | None = None,
) -> None:
    if retail_price is None and wholesale_price is None:
        return

    if get_product(conn, product_id) is None:
        raise NotFoundError(f"Product with id {product_id} does not exist")

    updates: list[str] = []
    params: list[int] = []

    if retail_price is not None:
        _validate_price(retail_price, "retail_price")
        updates.append("retail_price = ?")
        params.append(retail_price)

    if wholesale_price is not None:
        _validate_price(wholesale_price, "wholesale_price")
        updates.append("wholesale_price = ?")
        params.append(wholesale_price)

    params.append(product_id)
    with transaction(conn):
        conn.execute(
            f"UPDATE products SET {', '.join(updates)} WHERE id = ?",
            params,
        )


@audited()
def deactivate_product(conn: sqlite3.Connection, product_id: int) -> None:
    with transaction(conn):
        conn.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))


@audited()
def reactivate_product(conn: sqlite3.Connection, product_id: int) -> None:
    with transaction(conn):
        conn.execute("UPDATE products SET is_active = 1 WHERE id = ?", (product_id,))


@audited()
def set_made_to_order(
    conn: sqlite3.Connection, product_id: int, made_to_order: bool
) -> None:
    product = get_product(conn, product_id)
    if product is None:
        raise NotFoundError(f"Product with id {product_id} does not exist")

    if made_to_order:
        has_recipe = conn.execute(
            "SELECT 1 FROM product_recipe WHERE product_id = ? LIMIT 1",
            (product_id,),
        ).fetchone()
        if has_recipe is None:
            raise ValidationError(
                f"Product '{product['name']}' has no recipe — add one before "
                f"marking it made-to-order.",
                field="made_to_order",
                code=ErrorCode.PRODUCT_NO_RECIPE,
                details={"product_id": product["id"], "product_name": product["name"]},
            )

    with transaction(conn):
        conn.execute(
            "UPDATE products SET made_to_order = ? WHERE id = ?",
            (int(made_to_order), product_id),
        )


@audited()
def set_product_category(
    conn: sqlite3.Connection, product_id: int, category_id: int
) -> None:
    if get_product(conn, product_id) is None:
        raise NotFoundError(f"Product with id {product_id} does not exist")
    validate_assignable(conn, category_id, "PRODUCT")
    with transaction(conn):
        conn.execute(
            "UPDATE products SET category_id = ? WHERE id = ?", (category_id, product_id)
        )
