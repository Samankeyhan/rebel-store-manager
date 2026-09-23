from pathlib import Path

from db.connection import MIGRATIONS_DIR, get_connection, init_db


def _copy_real_migration(dest_dir: Path, filename: str) -> None:
    content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    (dest_dir / filename).write_text(content, encoding="utf-8")


def test_004_rebuilds_products_preserving_rows_and_adds_made_to_order(tmp_path):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    _copy_real_migration(baseline_dir, "001_initial_schema.sql")
    _copy_real_migration(baseline_dir, "002_partner_distributions.sql")
    _copy_real_migration(baseline_dir, "003_accounting_v2.sql")

    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(baseline_dir))

    conn = get_connection(str(db_path))
    try:
        vinyl_id = conn.execute(
            """
            INSERT INTO products
                (name, category, retail_price, wholesale_price,
                 current_stock, unit_cost, is_active)
            VALUES ('Vinyl', 'VINYL', 3000, 2000, 10, 500, 1)
            """
        ).lastrowid
        poster_id = conn.execute(
            """
            INSERT INTO products
                (name, category, retail_price, wholesale_price,
                 current_stock, unit_cost, is_active)
            VALUES ('Poster', 'POSTER', 1000, 800, 0, NULL, 1)
            """
        ).lastrowid
        inactive_id = conn.execute(
            """
            INSERT INTO products
                (name, category, retail_price, wholesale_price,
                 current_stock, unit_cost, is_active)
            VALUES ('Old Tee', 'TSHIRT', 2000, 1500, 3, 900, 0)
            """
        ).lastrowid

        order_id = conn.execute(
            """
            INSERT INTO orders (invoice_number, status, channel)
            VALUES ('INV-000001', 'COMPLETED', 'WEBSITE')
            """
        ).lastrowid
        conn.execute(
            """
            INSERT INTO order_items
                (order_id, product_id, quantity, list_price, unit_price, unit_cost_at_time)
            VALUES (?, ?, 1, 3000, 3000, 500)
            """,
            (order_id, vinyl_id),
        )
        conn.commit()
    finally:
        conn.close()

    with_004_dir = tmp_path / "with_004"
    with_004_dir.mkdir()
    _copy_real_migration(with_004_dir, "001_initial_schema.sql")
    _copy_real_migration(with_004_dir, "002_partner_distributions.sql")
    _copy_real_migration(with_004_dir, "003_accounting_v2.sql")
    _copy_real_migration(with_004_dir, "004_made_to_order.sql")

    init_db(str(db_path), migrations_dir=str(with_004_dir))

    conn = get_connection(str(db_path))
    try:
        applied = {
            row["filename"]
            for row in conn.execute("SELECT filename FROM schema_migrations")
        }
        assert "004_made_to_order.sql" in applied

        vinyl = conn.execute("SELECT * FROM products WHERE id = ?", (vinyl_id,)).fetchone()
        assert vinyl["name"] == "Vinyl"
        assert vinyl["category"] == "VINYL"
        assert vinyl["retail_price"] == 3000
        assert vinyl["wholesale_price"] == 2000
        assert vinyl["current_stock"] == 10
        assert vinyl["unit_cost"] == 500
        assert vinyl["is_active"] == 1
        assert vinyl["made_to_order"] == 0

        poster = conn.execute("SELECT * FROM products WHERE id = ?", (poster_id,)).fetchone()
        assert poster["unit_cost"] is None
        assert poster["made_to_order"] == 0

        inactive = conn.execute(
            "SELECT * FROM products WHERE id = ?", (inactive_id,)
        ).fetchone()
        assert inactive["is_active"] == 0

        # order_items referencing products survived the rebuild.
        item = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchone()
        assert item["product_id"] == vinyl_id

        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

        lighter_id = conn.execute(
            """
            INSERT INTO products
                (name, category, retail_price, wholesale_price)
            VALUES ('Zippo', 'فندک', 500000, 400000)
            """
        ).lastrowid
        lighter = conn.execute(
            "SELECT * FROM products WHERE id = ?", (lighter_id,)
        ).fetchone()
        assert lighter["category"] == "فندک"
        assert lighter["made_to_order"] == 0

        conn.execute(
            "UPDATE products SET made_to_order = 1 WHERE id = ?", (lighter_id,)
        )
        conn.commit()
        assert conn.execute(
            "SELECT made_to_order FROM products WHERE id = ?", (lighter_id,)
        ).fetchone()["made_to_order"] == 1

        # trg_products_updated_at survived the rebuild.
        conn.execute("UPDATE products SET retail_price = 550000 WHERE id = ?", (lighter_id,))
        conn.commit()
        updated_lighter = conn.execute(
            "SELECT updated_at FROM products WHERE id = ?", (lighter_id,)
        ).fetchone()
        assert updated_lighter["updated_at"] is not None
    finally:
        conn.close()
