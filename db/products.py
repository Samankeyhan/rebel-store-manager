import sqlite3

VALID_CATEGORIES = (
    "ALBUM",
    "CASSETTE",
    "VINYL",
    "MIRROR",
    "POSTER",
    "STICKER",
    "TSHIRT",
    "OTHER",
)


def _validate_category(category: str) -> None:
    if category not in VALID_CATEGORIES:
        valid = ", ".join(VALID_CATEGORIES)
        raise ValueError(f"Invalid category '{category}'. Must be one of: {valid}")


def _validate_price(price: int, field_name: str) -> None:
    if price < 0:
        raise ValueError(f"{field_name} must be >= 0, got {price}")


def add_product(
    conn: sqlite3.Connection,
    name: str,
    category: str,
    retail_price: int,
    wholesale_price: int,
) -> int:
    _validate_category(category)
    _validate_price(retail_price, "retail_price")
    _validate_price(wholesale_price, "wholesale_price")

    cursor = conn.execute(
        """
        INSERT INTO products (name, category, retail_price, wholesale_price)
        VALUES (?, ?, ?, ?)
        """,
        (name, category, retail_price, wholesale_price),
    )
    conn.commit()
    return cursor.lastrowid


def list_products(
    conn: sqlite3.Connection, active_only: bool = True
) -> list[sqlite3.Row]:
    if active_only:
        rows = conn.execute(
            "SELECT * FROM products WHERE is_active = 1 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    return list(rows)


def get_product(conn: sqlite3.Connection, product_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()


def update_product_prices(
    conn: sqlite3.Connection,
    product_id: int,
    retail_price: int | None = None,
    wholesale_price: int | None = None,
) -> None:
    if retail_price is None and wholesale_price is None:
        return

    if get_product(conn, product_id) is None:
        raise ValueError(f"Product with id {product_id} does not exist")

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
    conn.execute(
        f"UPDATE products SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()


def deactivate_product(conn: sqlite3.Connection, product_id: int) -> None:
    conn.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
    conn.commit()
