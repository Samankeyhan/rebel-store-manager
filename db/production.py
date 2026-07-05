import sqlite3

from db.products import get_product


def _fetch_recipe_for_production(
    conn: sqlite3.Connection, product_id: int
) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT
            product_recipe.material_id,
            product_recipe.quantity_needed,
            materials.name AS material_name,
            materials.type AS material_type,
            materials.current_stock,
            materials.unit_cost AS material_unit_cost
        FROM product_recipe
        JOIN materials ON materials.id = product_recipe.material_id
        WHERE product_recipe.product_id = ?
        ORDER BY materials.name
        """,
        (product_id,),
    ).fetchall()
    return list(rows)


def run_production_batch(
    conn: sqlite3.Connection,
    product_id: int,
    quantity_produced: int,
    notes: str | None = None,
) -> int:
    product = get_product(conn, product_id)
    if product is None:
        raise ValueError(f"Product with id {product_id} does not exist")

    if quantity_produced <= 0:
        raise ValueError(f"quantity_produced must be > 0, got {quantity_produced}")

    conn.execute("BEGIN")
    try:
        recipe = _fetch_recipe_for_production(conn, product_id)
        if not recipe:
            raise ValueError(
                f"Product '{product['name']}' has no recipe defined — "
                f"add one before running production."
            )

        requirements: list[dict] = []
        for row in recipe:
            total_needed = row["quantity_needed"] * quantity_produced
            requirements.append(
                {
                    "material_id": row["material_id"],
                    "material_name": row["material_name"],
                    "material_type": row["material_type"],
                    "current_stock": row["current_stock"],
                    "unit_cost": row["material_unit_cost"],
                    "total_needed": total_needed,
                }
            )

        for req in requirements:
            if req["material_type"] == "STOCK":
                available = req["current_stock"]
                needed = req["total_needed"]
                if available < needed:
                    raise ValueError(
                        f"Insufficient stock for '{req['material_name']}': "
                        f"need {needed}, available {available}"
                    )

        total_batch_cost = sum(
            int(req["total_needed"] * req["unit_cost"]) for req in requirements
        )
        unit_cost = total_batch_cost // quantity_produced

        cursor = conn.execute(
            """
            INSERT INTO production_batches
                (product_id, quantity_produced, unit_cost, notes)
            VALUES (?, ?, ?, ?)
            """,
            (product_id, quantity_produced, unit_cost, notes),
        )
        batch_id = cursor.lastrowid

        for req in requirements:
            conn.execute(
                """
                INSERT INTO production_batch_materials
                    (production_batch_id, material_id, quantity_used, unit_cost_at_time)
                VALUES (?, ?, ?, ?)
                """,
                (
                    batch_id,
                    req["material_id"],
                    req["total_needed"],
                    req["unit_cost"],
                ),
            )

            if req["material_type"] == "STOCK":
                conn.execute(
                    """
                    UPDATE materials
                    SET current_stock = current_stock - ?
                    WHERE id = ?
                    """,
                    (req["total_needed"], req["material_id"]),
                )
                conn.execute(
                    """
                    INSERT INTO stock_movements
                        (item_type, item_id, quantity_change, reason,
                         reference_production_batch_id)
                    VALUES ('MATERIAL', ?, ?, 'PRODUCTION_CONSUMPTION', ?)
                    """,
                    (
                        req["material_id"],
                        -req["total_needed"],
                        batch_id,
                    ),
                )

        conn.execute(
            """
            UPDATE products
            SET current_stock = current_stock + ?, unit_cost = ?
            WHERE id = ?
            """,
            (quantity_produced, unit_cost, product_id),
        )

        conn.execute(
            """
            INSERT INTO stock_movements
                (item_type, item_id, quantity_change, reason,
                 reference_production_batch_id)
            VALUES ('PRODUCT', ?, ?, 'PRODUCTION_OUTPUT', ?)
            """,
            (product_id, quantity_produced, batch_id),
        )

        conn.commit()
        return batch_id
    except Exception:
        conn.rollback()
        raise


def get_production_batch(conn: sqlite3.Connection, batch_id: int) -> dict:
    batch = conn.execute(
        "SELECT * FROM production_batches WHERE id = ?", (batch_id,)
    ).fetchone()
    if batch is None:
        raise ValueError(f"Production batch with id {batch_id} does not exist")

    materials = conn.execute(
        """
        SELECT
            production_batch_materials.*,
            materials.name AS material_name,
            materials.type AS material_type
        FROM production_batch_materials
        JOIN materials ON materials.id = production_batch_materials.material_id
        WHERE production_batch_materials.production_batch_id = ?
        ORDER BY materials.name
        """,
        (batch_id,),
    ).fetchall()

    return {"batch": batch, "materials": list(materials)}


def list_production_batches(
    conn: sqlite3.Connection, product_id: int | None = None
) -> list[sqlite3.Row]:
    if product_id is not None:
        rows = conn.execute(
            """
            SELECT
                production_batches.*,
                products.name AS product_name
            FROM production_batches
            JOIN products ON products.id = production_batches.product_id
            WHERE production_batches.product_id = ?
            ORDER BY production_batches.production_date DESC,
                     production_batches.id DESC
            """,
            (product_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                production_batches.*,
                products.name AS product_name
            FROM production_batches
            JOIN products ON products.id = production_batches.product_id
            ORDER BY production_batches.production_date DESC,
                     production_batches.id DESC
            """
        ).fetchall()
    return list(rows)
