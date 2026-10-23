"""Product → material bill of materials: add/update/remove recipe items, compute recipe cost."""

import sqlite3

from db.audit import audited
from db.connection import transaction
from db.costing import check_quantity, per_unit_cost, recipe_batch_total
from db.errors import ConflictError, NotFoundError, ValidationError
from db.materials import get_material
from db.products import get_product


VALID_COST_BASIS = ("PER_UNIT", "PER_BATCH")


def _validate_quantity(quantity_needed: float) -> None:
    check_quantity(quantity_needed, "quantity_needed")


def _validate_cost_basis(cost_basis: str) -> None:
    if cost_basis not in VALID_COST_BASIS:
        valid = ", ".join(VALID_COST_BASIS)
        raise ValidationError(
            f"Invalid cost_basis '{cost_basis}'. Must be one of: {valid}",
            field="cost_basis",
        )


@audited()
def add_recipe_item(
    conn: sqlite3.Connection,
    product_id: int,
    material_id: int,
    quantity_needed: float,
    cost_basis: str = "PER_UNIT",
) -> int:
    _validate_quantity(quantity_needed)
    _validate_cost_basis(cost_basis)

    product = get_product(conn, product_id)
    if product is None:
        raise NotFoundError(f"Product with id {product_id} does not exist")

    material = get_material(conn, material_id)
    if material is None:
        raise NotFoundError(f"Material with id {material_id} does not exist")

    try:
        with transaction(conn):
            cursor = conn.execute(
                """
                INSERT INTO product_recipe
                    (product_id, material_id, quantity_needed, cost_basis)
                VALUES (?, ?, ?, ?)
                """,
                (product_id, material_id, quantity_needed, cost_basis),
            )
    except sqlite3.IntegrityError:
        raise ConflictError(
            f"Material '{material['name']}' is already in the recipe for "
            f"'{product['name']}' — use update_recipe_item to change its "
            f"quantity instead."
        ) from None
    return cursor.lastrowid


@audited()
def update_recipe_item(
    conn: sqlite3.Connection,
    product_id: int,
    material_id: int,
    quantity_needed: float,
    cost_basis: str | None = None,
) -> None:
    _validate_quantity(quantity_needed)
    if cost_basis is not None:
        _validate_cost_basis(cost_basis)

    with transaction(conn):
        if cost_basis is not None:
            cursor = conn.execute(
                """
                UPDATE product_recipe
                SET quantity_needed = ?, cost_basis = ?
                WHERE product_id = ? AND material_id = ?
                """,
                (quantity_needed, cost_basis, product_id, material_id),
            )
        else:
            cursor = conn.execute(
                """
                UPDATE product_recipe
                SET quantity_needed = ?
                WHERE product_id = ? AND material_id = ?
                """,
                (quantity_needed, product_id, material_id),
            )
        if cursor.rowcount == 0:
            raise NotFoundError(
                f"No recipe item found for product_id {product_id} and "
                f"material_id {material_id}. Use add_recipe_item to create one first."
            )


@audited()
def remove_recipe_item(
    conn: sqlite3.Connection, product_id: int, material_id: int
) -> None:
    with transaction(conn):
        cursor = conn.execute(
            """
            DELETE FROM product_recipe
            WHERE product_id = ? AND material_id = ?
            """,
            (product_id, material_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(
                f"No recipe item found for product_id {product_id} and "
                f"material_id {material_id}."
            )


def get_recipe(conn: sqlite3.Connection, product_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            product_recipe.id,
            product_recipe.product_id,
            product_recipe.material_id,
            product_recipe.quantity_needed,
            product_recipe.cost_basis,
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
    return [dict(row) for row in rows]


def recipe_costs(conn: sqlite3.Connection, product_ids: list[int] | None = None) -> dict[int, dict]:
    """What one unit of each product costs to make from its recipe today, for display only (accounting rules section 13).

    One query. Per product id: `recipe_cost` (int Rial, `recipe_batch_total` for a batch of 1), `recipe_cost_status`
    (NONE: no recipe; INCOMPLETE: some line's material has unit_cost 0 or NULL, meaning "not entered", section 2;
    COMPLETE) and `recipe_cost_missing` (a list of {id, name} of those materials). INCOMPLETE gives `recipe_cost` None,
    never a cheap-looking number. Never written anywhere: products.unit_cost is only ever the stored weighted average.
    `product_ids=None` is every product; an id that does not exist is absent from the result."""
    query = """
        SELECT products.id AS product_id,
               product_recipe.quantity_needed,
               product_recipe.cost_basis,
               materials.id AS material_id,
               materials.name AS material_name,
               materials.unit_cost AS material_unit_cost
        FROM products
        LEFT JOIN product_recipe ON product_recipe.product_id = products.id
        LEFT JOIN materials ON materials.id = product_recipe.material_id
    """
    params: list = []
    if product_ids is not None:
        ids = sorted(set(product_ids))
        if not ids:
            return {}
        query += f" WHERE products.id IN ({', '.join('?' * len(ids))})"
        params = ids
    query += " ORDER BY products.id, materials.name"

    lines: dict[int, list] = {}
    for row in conn.execute(query, params):
        bucket = lines.setdefault(row["product_id"], [])
        if row["material_id"] is not None:
            bucket.append(row)

    result = {}
    for product_id, rows in lines.items():
        missing = [
            {"id": r["material_id"], "name": r["material_name"]} for r in rows if not r["material_unit_cost"]
        ]
        if not rows:
            status, cost = "NONE", None
        elif missing:
            status, cost = "INCOMPLETE", None
        else:
            status = "COMPLETE"
            cost = recipe_batch_total(
                [(r["quantity_needed"], r["cost_basis"], r["material_unit_cost"]) for r in rows], 1
            )
        result[product_id] = {"recipe_cost": cost, "recipe_cost_status": status, "recipe_cost_missing": missing}
    return result


def calculate_recipe_cost(
    conn: sqlite3.Connection, product_id: int, batch_qty: float = 1
) -> int:
    if get_product(conn, product_id) is None:
        raise NotFoundError(f"Product with id {product_id} does not exist")
    if batch_qty <= 0:
        raise ValidationError(
            f"batch_qty must be > 0, got {batch_qty}", field="batch_qty"
        )

    rows = conn.execute(
        """
        SELECT
            product_recipe.quantity_needed,
            product_recipe.cost_basis,
            materials.unit_cost AS material_unit_cost
        FROM product_recipe
        JOIN materials ON materials.id = product_recipe.material_id
        WHERE product_recipe.product_id = ?
        """,
        (product_id,),
    ).fetchall()

    batch_total_cost = recipe_batch_total(
        [(row["quantity_needed"], row["cost_basis"], row["material_unit_cost"]) for row in rows],
        batch_qty,
    )
    return per_unit_cost(batch_total_cost, batch_qty)
