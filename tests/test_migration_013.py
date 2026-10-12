"""Migration 013 (name_key columns, unique indexes, updated_at triggers) and the init_db backfill
(db/name_keys.py): existing names are never rewritten, colliding rows stay NULL, updated_at and
audit_log are untouched, and re-running changes nothing."""

import re
import shutil

import pytest

from db import name_keys
from db.audit import stale_audit_tables
from db.connection import MIGRATIONS_DIR, get_connection, init_db
from db.names import name_key

OLD_TS = "2026-01-02 03:04:05"
NAME_TABLES = tuple(name_keys.NAME_KEY_TABLES)
TRIGGER_TABLES = (
    "suppliers", "expense_categories", "products", "materials", "categories", "packaging_kits", "partners",
)


@pytest.fixture
def old_db(tmp_path):
    """A database at version 012 (migrations before 013) holding fictional rows, some of
    which collide once spelling variants are folded."""
    old_dir = tmp_path / "migrations_to_012"
    old_dir.mkdir()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name < "013":
            shutil.copy(path, old_dir / path.name)
    db_path = str(tmp_path / "old.db")
    init_db(db_path, migrations_dir=old_dir)
    conn = get_connection(db_path)
    category = conn.execute("SELECT id FROM categories WHERE parent_id IS NULL ORDER BY id").fetchone()[0]
    other = conn.execute("SELECT id FROM categories WHERE parent_id IS NULL ORDER BY id").fetchall()[1][0]
    ts = {"updated_at": OLD_TS}

    def add(table, **cols):
        cols = {**cols, **ts}
        conn.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            list(cols.values()),
        )

    for name in ("كتاب ٣", "کتاب 3", "Solo Print Co"):
        add("suppliers", name=name)
    for name in ("پوستر علي", "پوستر علی", "Fictional Tee"):
        add("products", name=name, category_id=category, category="OTHER", retail_price=1, wholesale_price=1)
    for name in ("جعبه", "جعبه‌", "Tape"):
        add("materials", name=name, type="SERVICE", unit_cost=1)
    for name in ("شریک ۱", "شریک ١"):
        add("partners", name=name, current_percentage=50)
    add("categories", kind="PRODUCT", name="Sub A", parent_id=category)
    add("categories", kind="PRODUCT", name="sub a", parent_id=category)  # sibling collision
    add("categories", kind="PRODUCT", name="Sub A", parent_id=other)  # other parent: fine
    add("payment_methods", name="Fictional Pay", fee_bps=0, fee_fixed=0,
        settlement_rule="IMMEDIATE")
    add("packaging_kits", name="Kit")
    add("expense_categories", name="Rent")
    conn.commit()
    yield db_path, conn
    conn.close()


def _rows(conn, table):
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]


def test_upgrade_keeps_names_and_updated_at_logs_nothing_and_reports_collisions(old_db):
    db_path, conn = old_db
    before = {t: _rows(conn, t) for t in NAME_TABLES}
    audit_before = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert audit_before > 0  # audit triggers were active while the fixture rows went in
    conn.close()

    collisions = init_db(db_path)  # applies 013, then the backfill

    conn = get_connection(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == audit_before
        assert conn.execute("SELECT allow_purge FROM audit_control").fetchone()[0] == 0
        for table in NAME_TABLES:
            after = _rows(conn, table)
            assert len(after) == len(before[table])
            for old, new in zip(before[table], after):
                assert {k: v for k, v in new.items() if k != "name_key"} == {
                    k: v for k, v in old.items() if k != "name_key"
                }, table  # name, updated_at, everything else byte-identical
        keyed = {t: {r["name"]: r["name_key"] for r in _rows(conn, t)} for t in NAME_TABLES}
        assert keyed["suppliers"] == {"كتاب ٣": None, "کتاب 3": None, "Solo Print Co": "solo print co"}
        assert keyed["products"]["Fictional Tee"] == "fictional tee"
        assert keyed["products"]["پوستر علي"] is None and keyed["products"]["پوستر علی"] is None
        assert keyed["materials"] == {"جعبه": None, "جعبه‌": None, "Tape": "tape"}
        assert keyed["partners"] == {"شریک ۱": None, "شریک ١": None}
        assert keyed["payment_methods"] == {"Fictional Pay": "fictional pay"}
        sub = conn.execute("SELECT parent_id, name, name_key FROM categories WHERE name LIKE '%ub%'").fetchall()
        assert sorted((r["name"], r["name_key"]) for r in sub if r["parent_id"] != sub[0]["parent_id"]) == [
            ("Sub A", "sub a")
        ]  # the same name under another parent got its key
        assert stale_audit_tables(conn) == []
    finally:
        conn.close()

    by_table = {c["table"]: c for c in collisions}
    assert len(collisions) == 5
    assert by_table["suppliers"]["ids"] == [1, 2] and by_table["products"]["ids"] == [1, 2]
    assert by_table["materials"]["ids"] == [1, 2] and by_table["partners"]["ids"] == [1, 2]
    assert {c["table"] for c in collisions} == {"suppliers", "products", "materials", "partners", "categories"}
    assert all(c["reason"] == "duplicate" and len(c["ids"]) == 2 and len(c["names"]) == 2 for c in collisions)


def test_backfill_is_idempotent_and_retries_after_a_collision_is_resolved(old_db):
    db_path, conn = old_db
    conn.close()
    first = init_db(db_path)
    conn = get_connection(db_path)
    snapshot = {t: _rows(conn, t) for t in NAME_TABLES}
    conn.close()

    second = init_db(db_path)  # nothing pending changes
    conn = get_connection(db_path)
    try:
        assert second == first
        assert {t: _rows(conn, t) for t in NAME_TABLES} == snapshot
        conn.execute("DELETE FROM suppliers WHERE id = 1")  # resolve one collision pair
        conn.commit()
    finally:
        conn.close()

    third = init_db(db_path)
    conn = get_connection(db_path)
    try:
        assert "suppliers" not in {c["table"] for c in third}
        assert conn.execute("SELECT name_key FROM suppliers WHERE id = 2").fetchone()[0] == name_key("کتاب 3")
    finally:
        conn.close()


def test_a_null_key_row_colliding_with_an_already_keyed_row_stays_null(old_db):
    db_path, conn = old_db
    conn.close()
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO suppliers (name) VALUES ('Solo  print co')")  # raw write, no key
        conn.commit()
        found = name_keys.find_name_collisions(conn)
        assert [c["ids"] for c in found if c["table"] == "suppliers"] == [[1, 2], [3, 4]]
        assert name_keys.backfill_name_keys(conn) == found
        row = conn.execute("SELECT name_key FROM suppliers WHERE name = 'Solo  print co'").fetchone()
        assert row[0] is None
    finally:
        conn.close()


def test_an_empty_key_is_left_null_and_reported(tmp_path):
    db_path = str(tmp_path / "e.db")
    init_db(db_path)
    conn = get_connection(db_path)
    conn.execute("INSERT INTO suppliers (name) VALUES ('​‎')")
    conn.commit()
    conn.close()
    collisions = init_db(db_path)
    assert [(c["table"], c["reason"]) for c in collisions] == [("suppliers", "empty")]


def test_migration_adds_columns_and_partial_unique_indexes(test_db):
    for table in NAME_TABLES:
        assert any(r["name"] == "name_key" for r in test_db.execute(f"PRAGMA table_info({table})"))
    indexes = {
        r["name"]: r["sql"] for r in test_db.execute("SELECT name, sql FROM sqlite_master WHERE type = 'index' AND name LIKE 'ux_%name_key'")
    }
    assert len(indexes) == 9  # 8 tables, categories has two
    assert all("UNIQUE" in sql and "name_key IS NOT NULL" in sql for sql in indexes.values())
    # NULL keys never collide
    test_db.execute("INSERT INTO suppliers (name) VALUES ('x')")
    test_db.execute("INSERT INTO suppliers (name) VALUES ('x')")


# ------------------------------------------------------------------ triggers


def _trigger_sql(conn, table):
    return conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?", (f"trg_{table}_updated_at",)
    ).fetchone()[0]


def test_updated_at_triggers_fire_only_on_business_columns(test_db):
    for table in TRIGGER_TABLES:
        sql = _trigger_sql(test_db, table)
        listed = re.search(r"AFTER UPDATE OF (.+?) ON", sql, re.S).group(1)
        listed = {c.strip() for c in listed.split(",")}
        expected = {r["name"] for r in test_db.execute(f"PRAGMA table_info({table})")} - {"updated_at", "name_key"}
        assert listed == expected, table
        assert f"UPDATE {table} SET updated_at = datetime('now') WHERE id = NEW.id" in " ".join(sql.split())


def test_a_business_update_stamps_updated_at_and_a_name_key_only_update_does_not(test_db):
    test_db.execute("INSERT INTO suppliers (name, updated_at) VALUES ('S', ?)", (OLD_TS,))
    test_db.execute("UPDATE suppliers SET name_key = 's'")
    assert test_db.execute("SELECT updated_at FROM suppliers").fetchone()[0] == OLD_TS
    test_db.execute("UPDATE suppliers SET phone = '1'")
    assert test_db.execute("SELECT updated_at FROM suppliers").fetchone()[0] != OLD_TS
    # payment_methods stamps updated_at in code, not a trigger; a key-only update leaves it
    test_db.execute(
        "INSERT INTO payment_methods (name, settlement_rule, updated_at) VALUES ('P', 'IMMEDIATE', ?)", (OLD_TS,)
    )
    test_db.execute("UPDATE payment_methods SET name_key = 'p'")
    assert test_db.execute("SELECT updated_at FROM payment_methods").fetchone()[0] == OLD_TS


def test_backfill_update_writes_no_audit_row_with_the_real_triggers(test_db):
    """The real trg_audit_*_upd run on a name_key change: its diff holds only tracked columns,
    so it inserts nothing (and audit_control stays in its normal state)."""
    test_db.execute("INSERT INTO suppliers (name) VALUES ('Quiet Supplier')")
    before = test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert "UNION ALL SELECT 'name'" in " ".join(
        test_db.execute("SELECT sql FROM sqlite_master WHERE name = 'trg_audit_suppliers_upd'").fetchone()[0].split()
    )
    name_keys.backfill_name_keys(test_db)
    assert test_db.execute("SELECT name_key FROM suppliers").fetchone()[0] == "quiet supplier"
    assert test_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == before
    assert test_db.execute("SELECT allow_purge FROM audit_control").fetchone()[0] == 0
