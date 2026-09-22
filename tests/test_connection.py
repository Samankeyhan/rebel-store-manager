import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

import db.connection as connection_module
from db.connection import MIGRATIONS_DIR, get_connection, init_db, transaction
from db.errors import InsufficientStockError
from db.materials import add_material, get_material
from db.partners import add_partner, list_partners
from db.production import list_production_batches, run_production_batch
from db.products import add_product, get_product
from db.recipes import add_recipe_item


def test_init_db_raises_on_modified_migration_hash():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        init_db(db_path)

        conn = get_connection(db_path)
        conn.execute(
            "UPDATE schema_migrations SET content_hash = ? WHERE filename = ?",
            ("deadbeef", "001_initial_schema.sql"),
        )
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError, match="has been modified after being applied"):
            init_db(db_path)
    finally:
        os.unlink(db_path)


def test_transaction_nested_call_joins_without_committing(test_db):
    test_db.execute("BEGIN")
    try:
        add_partner(test_db, "Alice", 50.0)
        assert test_db.in_transaction  # inner call used SAVEPOINT+RELEASE, not a
                                        # real commit — outer transaction still open
    finally:
        test_db.rollback()

    assert not any(
        p["name"] == "Alice" for p in list_partners(test_db, active_only=False)
    )


def test_transaction_outer_failure_rolls_back_nested_work(test_db):
    with pytest.raises(RuntimeError):
        with transaction(test_db):
            add_partner(test_db, "Bob", 50.0)
            raise RuntimeError("simulated failure after nested write")

    assert not any(
        p["name"] == "Bob" for p in list_partners(test_db, active_only=False)
    )


def test_transaction_standalone_failure_leaves_db_unchanged(test_db):
    product_id = add_product(test_db, "Widget", "OTHER", 1000, 800)
    material_id = add_material(test_db, "Wire", "STOCK", 100, initial_stock=1)
    add_recipe_item(test_db, product_id, material_id, quantity_needed=5)

    with pytest.raises(InsufficientStockError):
        run_production_batch(test_db, product_id, quantity_produced=1)

    assert get_product(test_db, product_id)["current_stock"] == 0
    assert get_material(test_db, material_id)["current_stock"] == 1
    assert list_production_batches(test_db) == []


def test_transaction_nested_failure_caught_by_caller_undoes_only_inner_work(test_db):
    with transaction(test_db):
        add_partner(test_db, "Alice", 50.0)
        try:
            with transaction(test_db):
                add_partner(test_db, "Bob", 50.0)
                raise RuntimeError("simulated failure")
        except RuntimeError:
            pass  # caller catches it and continues — outer transaction keeps going

    partners = list_partners(test_db, active_only=False)
    assert any(p["name"] == "Alice" for p in partners)
    assert not any(p["name"] == "Bob" for p in partners)


def _copy_real_migration(dest_dir: Path, filename: str) -> None:
    content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    (dest_dir / filename).write_text(content, encoding="utf-8")


def test_broken_migration_leaves_db_and_schema_migrations_unchanged(tmp_path):
    db_path = tmp_path / "broken.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_broken.sql").write_text(
        "CREATE TABLE widgets (id INTEGER PRIMARY KEY);\n"
        "INSERT INTO widgets (id) VALUES (1);\n"
        "THIS IS NOT VALID SQL;\n",
        encoding="utf-8",
    )

    with pytest.raises(sqlite3.OperationalError):
        init_db(str(db_path), migrations_dir=str(migrations_dir))

    conn = get_connection(str(db_path))
    try:
        assert conn.execute("SELECT * FROM schema_migrations").fetchall() == []
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'widgets'"
        ).fetchall()
        assert tables == []
    finally:
        conn.close()


def test_fresh_db_migration_produces_no_backup(tmp_path):
    db_path = tmp_path / "shop.db"
    init_db(str(db_path))  # first-ever run: schema_migrations starts empty
    assert not (tmp_path / "backups").exists()


def test_already_migrated_db_gets_backup_on_new_pending_migration(tmp_path):
    db_path = tmp_path / "shop.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_first.sql").write_text(
        "CREATE TABLE widgets (id INTEGER PRIMARY KEY);\n", encoding="utf-8"
    )

    init_db(str(db_path), migrations_dir=str(migrations_dir))
    assert not (tmp_path / "backups").exists()  # nothing applied before -> no backup

    (migrations_dir / "002_second.sql").write_text(
        "CREATE TABLE gadgets (id INTEGER PRIMARY KEY);\n", encoding="utf-8"
    )
    init_db(str(db_path), migrations_dir=str(migrations_dir))

    backups_dir = tmp_path / "backups"
    assert backups_dir.exists()
    backups = list(backups_dir.glob("shop-*.db"))
    assert len(backups) == 1

    backup_conn = sqlite3.connect(backups[0])
    try:
        tables = {
            row[0]
            for row in backup_conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "widgets" in tables
        assert "gadgets" not in tables  # backup taken before the second migration ran
    finally:
        backup_conn.close()


def test_backup_suffixes_avoid_overwriting_existing_file(tmp_path, monkeypatch):
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 1, 12, 0, 0)

    monkeypatch.setattr(connection_module, "datetime", _FixedDatetime)

    db_path = tmp_path / "shop.db"
    db_path.write_bytes(b"first-version")
    first = connection_module._backup_db(db_path)

    db_path.write_bytes(b"second-version")
    second = connection_module._backup_db(db_path)

    assert first != second
    assert first.name == "shop-20260101-120000.db"
    assert second.name == "shop-20260101-120000-1.db"
    assert first.read_bytes() == b"first-version"
    assert second.read_bytes() == b"second-version"


def test_full_migration_run_has_no_foreign_key_violations(tmp_path):
    db_path = tmp_path / "shop.db"
    init_db(str(db_path))

    conn = get_connection(str(db_path))
    try:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_upgrade_from_only_001_applies_002_and_003_in_one_run(tmp_path):
    # Simulate data/shop.db's real current state: only 001 has been applied.
    only_001_dir = tmp_path / "only_001"
    only_001_dir.mkdir()
    _copy_real_migration(only_001_dir, "001_initial_schema.sql")

    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(only_001_dir))

    conn = get_connection(str(db_path))
    try:
        product_id = conn.execute(
            """
            INSERT INTO products
                (name, category, retail_price, wholesale_price, current_stock, unit_cost)
            VALUES ('Legacy Vinyl', 'VINYL', 3000, 2000, 10, 500)
            """
        ).lastrowid
        material_id = conn.execute(
            """
            INSERT INTO materials (name, type, unit, current_stock, unit_cost)
            VALUES ('Legacy Material', 'STOCK', 'piece', 50, 200)
            """
        ).lastrowid
        supplier_id = conn.execute(
            "INSERT INTO suppliers (name) VALUES ('Legacy Supplier')"
        ).lastrowid

        order_id = conn.execute(
            """
            INSERT INTO orders (invoice_number, order_date, status, channel)
            VALUES ('INV-000001', '2026-03-10', 'COMPLETED', 'INSTAGRAM')
            """
        ).lastrowid
        conn.execute(
            """
            INSERT INTO order_items
                (order_id, product_id, quantity, list_price, unit_price, unit_cost_at_time)
            VALUES (?, ?, 2, 6000, 3000, 500)
            """,
            (order_id, product_id),
        )

        purchase_id = conn.execute(
            """
            INSERT INTO material_purchases
                (material_id, supplier_id, invoice_number, purchase_date,
                 quantity_bought, total_paid, unit_cost)
            VALUES (?, ?, 'PUR-000001', '2026-03-05', 10, 2000, 200)
            """,
            (material_id, supplier_id),
        ).lastrowid

        movement_id = conn.execute(
            """
            INSERT INTO stock_movements
                (item_type, item_id, quantity_change, reason, movement_date)
            VALUES ('MATERIAL', ?, -3, 'WASTE', '2026-03-06')
            """,
            (material_id,),
        ).lastrowid
        conn.commit()
    finally:
        conn.close()

    # Apply the full, real migration set: 002 and 003 both pending in one run.
    init_db(str(db_path))

    conn = get_connection(str(db_path))
    try:
        applied = {
            row["filename"]
            for row in conn.execute("SELECT filename FROM schema_migrations")
        }
        assert "001_initial_schema.sql" in applied
        assert "002_partner_distributions.sql" in applied
        assert "003_accounting_v2.sql" in applied

        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        assert order["order_date"] == "2026-03-09 20:30:00"
        assert order["invoice_number"] == "INV-000001"
        assert order["stock_committed"] == 1

        order_item = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchone()
        assert order_item["quantity"] == 2
        assert order_item["unit_cost_at_time"] == 500

        purchase = conn.execute(
            "SELECT * FROM material_purchases WHERE id = ?", (purchase_id,)
        ).fetchone()
        assert purchase["purchase_date"] == "2026-03-04 20:30:00"
        assert purchase["total_paid"] == 2000

        movement = conn.execute(
            "SELECT * FROM stock_movements WHERE id = ?", (movement_id,)
        ).fetchone()
        assert movement["movement_date"] == "2026-03-05 20:30:00"
        assert movement["quantity_change"] == -3
        assert movement["unit_cost_at_time"] == 200  # backfilled from materials.unit_cost

        counters = {
            row["name"]: row["value"] for row in conn.execute("SELECT * FROM counters")
        }
        assert counters["INV"] == 1
        assert counters["PUR"] == 1

        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()

    backups_dir = tmp_path / "backups"
    assert backups_dir.exists()
    assert list(backups_dir.glob("shop-*.db"))
