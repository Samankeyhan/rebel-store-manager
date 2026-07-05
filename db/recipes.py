import sqlite3

from db.materials import get_material
from db.products import get_product


def _validate_quantity(quantity_needed: float) -> None:
    if quantity_needed <= 0:
        raise ValueError(f"quantity_needed must be > 0, got {quantity_needed}")


def add_recipe_item(
    conn: sqlite3.Connection,
    product_id: int,
    material_id: int,
    quantity_needed: float,
) -> int:
    _validate_quantity(quantity_needed)

    product = get_product(conn, product_id)
    if product is None:
        raise ValueError(f"Product with id {product_id} does not exist")

    material = get_material(conn, material_id)
    if material is None:
        raise ValueError(f"Material with id {material_id} does not exist")

    try:
        cursor = conn.execute(
            """
            INSERT INTO product_recipe (product_id, material_id, quantity_needed)
            VALUES (?, ?, ?)
            """,
            (product_id, material_id, quantity_needed),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(
            f"Material '{material['name']}' is already in the recipe for "
            f"'{product['name']}' — use update_recipe_item to change its "
            f"quantity instead."
        ) from None


def update_recipe_item(
    conn: sqlite3.Connection,
    product_id: int,
    material_id: int,
    quantity_needed: float,
) -> None:
    _validate_quantity(quantity_needed)

    cursor = conn.execute(
        """
        UPDATE product_recipe
        SET quantity_needed = ?
        WHERE product_id = ? AND material_id = ?
        """,
        (quantity_needed, product_id, material_id),
    )
    if cursor.rowcount == 0:
        raise ValueError(
            f"No recipe item found for product_id {product_id} and "
            f"material_id {material_id}. Use add_recipe_item to create one first."
        )
    conn.commit()


def remove_recipe_item(
    conn: sqlite3.Connection, product_id: int, material_id: int
) -> None:
    cursor = conn.execute(
        """
        DELETE FROM product_recipe
        WHERE product_id = ? AND material_id = ?
        """,
        (product_id, material_id),
    )
    if cursor.rowcount == 0:
        raise ValueError(
            f"No recipe item found for product_id {product_id} and "
            f"material_id {material_id}."
        )
    conn.commit()


def get_recipe(conn: sqlite3.Connection, product_id: int) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT
            product_recipe.id,
            product_recipe.product_id,
            product_recipe.material_id,
            product_recipe.quantity_needed,
            materials.name AS material_name,
            materials.type AS material_type,
            materials.unit AS material_unit,
            materials.unit_cost AS material_unit_cost
        FROM product_recipe
        JOIN materials ON materials.id = product_recipe.material_id
        WHERE product_recipe.product_id = ?
        ORDER BY materials.name
        """,
        (product_id,),
    ).fetchall()
    return list(rows)


def calculate_recipe_cost(conn: sqlite3.Connection, product_id: int) -> int:
    if get_product(conn, product_id) is None:
        raise ValueError(f"Product with id {product_id} does not exist")

    row = conn.execute(
        """
        SELECT COALESCE(SUM(product_recipe.quantity_needed * materials.unit_cost), 0)
        FROM product_recipe
        JOIN materials ON materials.id = product_recipe.material_id
        WHERE product_recipe.product_id = ?
        """,
        (product_id,),
    ).fetchone()
    return int(row[0])
