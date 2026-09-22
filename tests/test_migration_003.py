from pathlib import Path

from db.connection import MIGRATIONS_DIR, get_connection, init_db


def _copy_real_migration(dest_dir: Path, filename: str) -> None:
    content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    (dest_dir / filename).write_text(content, encoding="utf-8")


def test_003_normalizes_dates_backfills_stock_movements_and_seeds_counters(tmp_path):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    _copy_real_migration(baseline_dir, "001_initial_schema.sql")
    _copy_real_migration(baseline_dir, "002_partner_distributions.sql")

    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(baseline_dir))

    conn = get_connection(str(db_path))
    try:
        material_id = conn.execute(
            """
            INSERT INTO materials (name, type, unit, current_stock, unit_cost)
            VALUES ('Mat', 'STOCK', 'piece', 40, 150)
            """
        ).lastrowid
        product_id = conn.execute(
            """
            INSERT INTO products
                (name, category, retail_price, wholesale_price, current_stock, unit_cost)
            VALUES ('Prod', 'VINYL', 3000, 2000, 20, 600)
            """
        ).lastrowid

        order_id = conn.execute(
            """
            INSERT INTO orders (invoice_number, order_date, status, channel)
            VALUES ('INV-000001', '2026-02-01', 'COMPLETED', 'WEBSITE')
            """
        ).lastrowid

        purchase_id = conn.execute(
            """
            INSERT INTO material_purchases
                (material_id, invoice_number, purchase_date, quantity_bought,
                 total_paid, unit_cost)
            VALUES (?, 'PUR-000001', '2026-02-02', 5, 750, 150)
            """,
            (material_id,),
        ).lastrowid

        product_purchase_id = conn.execute(
            """
            INSERT INTO product_purchases
                (product_id, invoice_number, purchase_date, quantity_bought,
                 total_paid, unit_cost)
            VALUES (?, 'PUR-000002', '2026-02-03', 3, 1800, 600)
            """,
            (product_id,),
        ).lastrowid

        waste_id = conn.execute(
            """
            INSERT INTO stock_movements
                (item_type, item_id, quantity_change, reason, movement_date)
            VALUES ('MATERIAL', ?, -4, 'WASTE', '2026-02-04')
            """,
            (material_id,),
        ).lastrowid

        adjustment_id = conn.execute(
            """
            INSERT INTO stock_movements
                (item_type, item_id, quantity_change, reason, movement_date)
            VALUES ('PRODUCT', ?, 2, 'ADJUSTMENT', '2026-02-05')
            """,
            (product_id,),
        ).lastrowid

        already_utc_id = conn.execute(
            """
            INSERT INTO stock_movements
                (item_type, item_id, quantity_change, reason, movement_date)
            VALUES ('MATERIAL', ?, -1, 'WASTE', '2026-02-06 09:15:30')
            """,
            (material_id,),
        ).lastrowid

        partner_id = conn.execute(
            "INSERT INTO partners (name, current_percentage) VALUES ('Solo Partner', 100.0)"
        ).lastrowid
        distribution_id = conn.execute(
            """
            INSERT INTO profit_distributions
                (distribution_date, period_start, period_end,
                 total_profit_available, total_amount_distributed)
            VALUES ('2026-02-10 12:00:00', '2026-02-01', '2026-02-28', 1000, 500)
            """
        ).lastrowid
        conn.execute(
            """
            INSERT INTO distribution_shares
                (distribution_id, partner_id, percentage_at_time, amount)
            VALUES (?, ?, 100.0, 500)
            """,
            (distribution_id, partner_id),
        )
        conn.commit()
    finally:
        conn.close()

    with_003_dir = tmp_path / "with_003"
    with_003_dir.mkdir()
    _copy_real_migration(with_003_dir, "001_initial_schema.sql")
    _copy_real_migration(with_003_dir, "002_partner_distributions.sql")
    _copy_real_migration(with_003_dir, "003_accounting_v2.sql")

    init_db(str(db_path), migrations_dir=str(with_003_dir))

    conn = get_connection(str(db_path))
    try:
        applied = {
            row["filename"]
            for row in conn.execute("SELECT filename FROM schema_migrations")
        }
        assert "003_accounting_v2.sql" in applied

        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        assert order["order_date"] == "2026-01-31 20:30:00"

        purchase = conn.execute(
            "SELECT * FROM material_purchases WHERE id = ?", (purchase_id,)
        ).fetchone()
        assert purchase["purchase_date"] == "2026-02-01 20:30:00"

        product_purchase = conn.execute(
            "SELECT * FROM product_purchases WHERE id = ?", (product_purchase_id,)
        ).fetchone()
        assert product_purchase["purchase_date"] == "2026-02-02 20:30:00"

        waste = conn.execute(
            "SELECT * FROM stock_movements WHERE id = ?", (waste_id,)
        ).fetchone()
        assert waste["movement_date"] == "2026-02-03 20:30:00"
        assert waste["quantity_change"] == -4
        assert waste["reason"] == "WASTE"
        assert waste["unit_cost_at_time"] == 150

        adjustment = conn.execute(
            "SELECT * FROM stock_movements WHERE id = ?", (adjustment_id,)
        ).fetchone()
        assert adjustment["movement_date"] == "2026-02-04 20:30:00"
        assert adjustment["quantity_change"] == 2
        assert adjustment["reason"] == "ADJUSTMENT"
        assert adjustment["unit_cost_at_time"] == 600

        already_utc = conn.execute(
            "SELECT * FROM stock_movements WHERE id = ?", (already_utc_id,)
        ).fetchone()
        assert already_utc["movement_date"] == "2026-02-06 09:15:30"

        distribution = conn.execute(
            "SELECT * FROM profit_distributions WHERE id = ?", (distribution_id,)
        ).fetchone()
        assert distribution["period_start"] == "2026-02-01"
        assert distribution["period_end"] == "2026-02-28"
        assert distribution["distribution_date"] == "2026-02-10 12:00:00"

        counters = {
            row["name"]: row["value"] for row in conn.execute("SELECT * FROM counters")
        }
        assert counters["INV"] == 1
        assert counters["PUR"] == 2

        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()
