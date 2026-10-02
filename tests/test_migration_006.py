from pathlib import Path

import pytest

from db.connection import MIGRATIONS_DIR, get_connection, init_db

BEFORE_006 = tuple(
    name for name in sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql")) if name < "006"
)


def _migrations_dir(tmp_path: Path, name: str, filenames) -> Path:
    dest = tmp_path / name
    dest.mkdir()
    for filename in filenames:
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        (dest / filename).write_text(content, encoding="utf-8")
    return dest


def test_006_adds_nullable_created_at_and_total_cost(tmp_path):
    assert BEFORE_006[-1] == "005_categories.sql"
    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "at_005", BEFORE_006)))

    conn = get_connection(str(db_path))
    try:
        category_id = conn.execute("SELECT id FROM categories LIMIT 1").fetchone()[0]
        product_id = conn.execute(
            "INSERT INTO products (name, category_id, retail_price, wholesale_price, current_stock, unit_cost) "
            "VALUES ('Old Vinyl', ?, 3000, 2000, 10, 500)",
            (category_id,),
        ).lastrowid
        material_id = conn.execute(
            "INSERT INTO materials (name, type, unit, current_stock, unit_cost) "
            "VALUES ('Disc', 'STOCK', 'piece', 50, 400)"
        ).lastrowid
        today_batch = conn.execute(
            "INSERT INTO production_batches (product_id, quantity_produced, unit_cost, notes) "
            "VALUES (?, 10, 400, 'first')",
            (product_id,),
        ).lastrowid
        backdated_batch = conn.execute(
            "INSERT INTO production_batches (product_id, quantity_produced, unit_cost, production_date) "
            "VALUES (?, 5, 400, '2025-01-09 20:30:00')",
            (product_id,),
        ).lastrowid
        conn.execute(
            "INSERT INTO production_batch_materials (production_batch_id, material_id, quantity_used, unit_cost_at_time) "
            "VALUES (?, ?, 10, 400)",
            (today_batch, material_id),
        )
        conn.execute(
            "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason, reference_production_batch_id) "
            "VALUES ('PRODUCT', ?, 10, 'PRODUCTION_OUTPUT', ?)",
            (product_id, today_batch),
        )
        before = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM production_batches")}
    finally:
        conn.close()

    init_db(str(db_path))

    conn = get_connection(str(db_path))
    try:
        applied = {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")}
        assert "006_production_batch_created_at_and_total.sql" in applied
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(production_batches)")}
        assert {"created_at", "total_cost"} <= columns

        for batch_id in (today_batch, backdated_batch):
            row = dict(conn.execute("SELECT * FROM production_batches WHERE id = ?", (batch_id,)).fetchone())
            # Unknown for batches recorded before the migration — never invented.
            assert row.pop("created_at") is None
            assert row.pop("total_cost") is None
            assert row == before[batch_id]

        assert conn.execute(
            "SELECT COUNT(*) FROM production_batch_materials WHERE production_batch_id = ?", (today_batch,)
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT reference_production_batch_id FROM stock_movements WHERE reason = 'PRODUCTION_OUTPUT'"
        ).fetchone()[0] == today_batch
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

        with pytest.raises(Exception, match="CHECK"):
            conn.execute("UPDATE production_batches SET total_cost = -1 WHERE id = ?", (today_batch,))
    finally:
        conn.close()
