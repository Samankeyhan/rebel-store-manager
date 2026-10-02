import re
from pathlib import Path

import pytest

from db.connection import MIGRATIONS_DIR, get_connection, init_db
from db.constants import LEGACY_PRODUCT_CATEGORIES

BEFORE_005 = (
    "001_initial_schema.sql",
    "002_partner_distributions.sql",
    "003_accounting_v2.sql",
    "004_made_to_order.sql",
)


def _migrations_dir(tmp_path: Path, name: str, filenames) -> Path:
    dest = tmp_path / name
    dest.mkdir()
    for filename in filenames:
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        (dest / filename).write_text(content, encoding="utf-8")
    return dest


def _db_at_004(tmp_path: Path) -> Path:
    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "at_004", BEFORE_005)))
    return db_path


def _run_005(tmp_path: Path, db_path: Path) -> None:
    init_db(
        str(db_path),
        migrations_dir=str(
            _migrations_dir(tmp_path, "with_005", BEFORE_005 + ("005_categories.sql",))
        ),
    )


def test_005_backfills_every_legacy_category(tmp_path):
    db_path = _db_at_004(tmp_path)

    conn = get_connection(str(db_path))
    try:
        ids_by_code = {}
        for i, code in enumerate(LEGACY_PRODUCT_CATEGORIES):
            ids_by_code[code] = conn.execute(
                """
                INSERT INTO products
                    (name, category, retail_price, wholesale_price,
                     current_stock, unit_cost, is_active, made_to_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"Item {code}",
                    code,
                    1000 + i,
                    800 + i,
                    i,
                    None if code == "POSTER" else 100 * i,
                    0 if code == "TSHIRT" else 1,
                    1 if code == "ALBUM" else 0,
                ),
            ).lastrowid
        material_id = conn.execute(
            """
            INSERT INTO materials (name, type, unit, current_stock, unit_cost)
            VALUES ('Blank CD', 'STOCK', 'piece', 20, 300)
            """
        ).lastrowid
        order_id = conn.execute(
            "INSERT INTO orders (invoice_number, status, channel) "
            "VALUES ('INV-000001', 'COMPLETED', 'WEBSITE')"
        ).lastrowid
        conn.execute(
            """
            INSERT INTO order_items
                (order_id, product_id, quantity, list_price, unit_price, unit_cost_at_time)
            VALUES (?, ?, 1, 1002, 1002, 200)
            """,
            (order_id, ids_by_code["VINYL"]),
        )
        before = {
            row["id"]: dict(row)
            for row in conn.execute("SELECT * FROM products").fetchall()
        }
        conn.commit()
    finally:
        conn.close()

    _run_005(tmp_path, db_path)

    conn = get_connection(str(db_path))
    try:
        applied = {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")}
        assert "005_categories.sql" in applied

        # The tree: exactly the nine seeded top-level PRODUCT categories.
        categories = [dict(r) for r in conn.execute("SELECT * FROM categories").fetchall()]
        assert {c["name"] for c in categories} == set(LEGACY_PRODUCT_CATEGORIES.values())
        assert len(categories) == 9
        assert all(
            c["kind"] == "PRODUCT" and c["parent_id"] is None and c["is_active"] == 1
            for c in categories
        )
        name_by_id = {c["id"]: c["name"] for c in categories}

        # Every product points at the row named for its old code; nothing
        # else about it changed, including its id and the legacy column.
        for code, product_id in ids_by_code.items():
            row = dict(
                conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            )
            assert name_by_id[row.pop("category_id")] == LEGACY_PRODUCT_CATEGORIES[code]
            assert row == before[product_id]
        assert conn.execute(
            "SELECT COUNT(*) FROM products WHERE category_id IS NULL"
        ).fetchone()[0] == 0

        # Materials gained a nullable category_id and got no invented categories.
        material = conn.execute(
            "SELECT * FROM materials WHERE id = ?", (material_id,)
        ).fetchone()
        assert material["category_id"] is None

        item = conn.execute(
            "SELECT product_id FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchone()
        assert item["product_id"] == ids_by_code["VINYL"]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

        # The rebuilt table kept its updated_at trigger.
        conn.execute(
            "UPDATE products SET retail_price = 5000 WHERE id = ?", (ids_by_code["VINYL"],)
        )
        assert conn.execute(
            "SELECT updated_at FROM products WHERE id = ?", (ids_by_code["VINYL"],)
        ).fetchone()["updated_at"] is not None

        # category_id is now NOT NULL; the legacy column accepts NULL and any text.
        with pytest.raises(Exception, match="NOT NULL"):
            conn.execute(
                "INSERT INTO products (name, retail_price, wholesale_price) VALUES ('X', 1, 1)"
            )
        conn.execute(
            "INSERT INTO products (name, category, category_id, retail_price, wholesale_price) "
            "VALUES ('Y', NULL, ?, 1, 1)",
            (categories[0]["id"],),
        )
    finally:
        conn.close()


def test_005_refuses_and_rolls_back_on_an_unmatched_category(tmp_path):
    db_path = _db_at_004(tmp_path)

    conn = get_connection(str(db_path))
    try:
        # Only reachable by bypassing 004's CHECK, but the migration must
        # still stop rather than drop or miscategorise such a row.
        conn.execute("PRAGMA ignore_check_constraints = ON")
        conn.execute(
            "INSERT INTO products (name, category, retail_price, wholesale_price) "
            "VALUES ('Mystery', 'GUITAR', 1000, 800)"
        )
        conn.execute("PRAGMA ignore_check_constraints = OFF")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(Exception, match="every_product_category_must_match_a_seeded_category"):
        _run_005(tmp_path, db_path)

    conn = get_connection(str(db_path))
    try:
        applied = {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")}
        assert "005_categories.sql" not in applied
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(products)")}
        assert "category_id" not in columns
        tables = {
            r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "categories" not in tables
        row = conn.execute("SELECT * FROM products WHERE name = 'Mystery'").fetchone()
        assert row["category"] == "GUITAR"
    finally:
        conn.close()


def test_legacy_map_in_constants_matches_the_migration():
    sql = (MIGRATIONS_DIR / "005_categories.sql").read_text(encoding="utf-8")
    block = sql[sql.index("INSERT INTO _legacy_category_map") :]
    block = block[: block.index(";")]
    pairs = dict(re.findall(r"\('([^']+)',\s*'([^']+)'\)", block))
    assert pairs == LEGACY_PRODUCT_CATEGORIES
