import sqlite3

from db.connection import transaction
from db.constants import VALID_CATEGORIES  # re-exported for existing importers
from db.errors import NotFoundError, ValidationError


def _validate_category(category: str) -> None:
    if category not in VALID_CATEGORIES:
        valid = ", ".join(VALID_CATEGORIES)
        raise ValidationError(
            f"Invalid category '{category}'. Must be one of: {valid}",
            field="category",
        )


def _validate_price(price: int, field_name: str) -> None:
    if price < 0:
        raise ValidationError(f"{field_name} must be >= 0, got {price}", field=field_name)


def add_product(
    conn: sqlite3.Connection,
    name: str,
    category: str,
    retail_price: int,
    wholesale_price: int,
    made_to_order: bool = False,
) -> int:
    _validate_category(category)
    _validate_price(retail_price, "retail_price")
    _validate_price(wholesale_price, "wholesale_price")

    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO products
                (name, category, retail_price, wholesale_price, made_to_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, category, retail_price, wholesale_price, int(made_to_order)),
        )
    return cursor.lastrowid


def list_products(
    conn: sqlite3.Connection, active_only: bool = True
) -> list[dict]:
    if active_only:
        rows = conn.execute(
            "SELECT * FROM products WHERE is_active = 1 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def get_product(conn: sqlite3.Connection, product_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    return dict(row) if row is not None else None


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


def deactivate_product(conn: sqlite3.Connection, product_id: int) -> None:
    with transaction(conn):
        conn.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))


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
            )

    with transaction(conn):
        conn.execute(
            "UPDATE products SET made_to_order = ? WHERE id = ?",
            (int(made_to_order), product_id),
        )
