"""Migration 011: materials.min_stock (optional minimum stock per material)."""

import sqlite3
from pathlib import Path

import pytest

from db.connection import MIGRATIONS_DIR, get_connection, init_db

UP_TO_010 = tuple(
    name for name in sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql")) if name < "011"
)
OLD_STAMP = "2025-01-02 03:04:05"


def _migrations_dir(tmp_path: Path, name: str, filenames) -> Path:
    dest = tmp_path / name
    dest.mkdir()
    for filename in filenames:
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        (dest / filename).write_text(content, encoding="utf-8")
    return dest


def _snapshot(conn) -> dict:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT IN ('sqlite_sequence', 'schema_migrations')"
    )]
    return {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in tables}


def _schema_objects(conn, kind: str) -> dict:
    return {r["name"]: r["sql"] for r in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = ? AND name NOT LIKE 'sqlite_%'", (kind,)
    )}


def _at_010_with_materials(tmp_path) -> Path:
    assert UP_TO_010[-1] == "010_payment_method_fee_cap.sql"
    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "at_010", UP_TO_010)))
    conn = get_connection(str(db_path))
    try:
        x = conn.execute
        # The updated_at trigger fires on UPDATE only, so the stamp set here stays.
        x(
            "INSERT INTO materials (name, type, unit, current_stock, unit_cost, updated_at) "
            f"VALUES ('Test Box', 'STOCK', 'piece', 12.5, 45000, '{OLD_STAMP}')"
        )
        x(
            "INSERT INTO materials (name, type, unit, current_stock, unit_cost, updated_at) "
            f"VALUES ('Test Tape', 'STOCK', 'roll', 0, 120005, '{OLD_STAMP}')"
        )
        x(
            "INSERT INTO materials (name, type, unit, current_stock, unit_cost, updated_at) "
            f"VALUES ('Test Print Service', 'SERVICE', 'piece', NULL, 300000, '{OLD_STAMP}')"
        )
        x(
            "INSERT INTO materials (name, type, unit, current_stock, unit_cost, is_active, updated_at) "
            f"VALUES ('Test Old Filler', 'STOCK', 'kg', 3, 9000, 0, '{OLD_STAMP}')"
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_011_adds_min_stock_null_and_changes_nothing_else(tmp_path):
    db_path = _at_010_with_materials(tmp_path)
    conn = get_connection(str(db_path))
    try:
        before = _snapshot(conn)
        triggers_before = _schema_objects(conn, "trigger")
        indexes_before = _schema_objects(conn, "index")
    finally:
        conn.close()

    init_db(str(db_path))

    conn = get_connection(str(db_path))
    try:
        after = _snapshot(conn)
        applied = [r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")]
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        triggers_after = _schema_objects(conn, "trigger")
        indexes_after = _schema_objects(conn, "index")
    finally:
        conn.close()

    assert "011_material_min_stock.sql" in applied
    assert [tuple(r) for r in integrity] == [("ok",)]
    assert fk == []
    assert triggers_after == triggers_before
    assert indexes_after == indexes_before
    assert set(after) == set(before)
    assert len(after["materials"]) == 4
    for table, rows_before in before.items():
        rows_after = after[table]
        assert len(rows_after) == len(rows_before), table
        for row_before, row_after in zip(rows_before, rows_after, strict=True):
            if table == "materials":
                assert row_after.pop("min_stock") is None
            assert row_after == row_before, table

    assert {m["updated_at"] for m in after["materials"]} == {OLD_STAMP}


def test_011_check_refuses_negative(tmp_path):
    db_path = _at_010_with_materials(tmp_path)
    init_db(str(db_path))
    conn = get_connection(str(db_path))
    try:
        for bad in (-1, -0.001):
            with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
                conn.execute("UPDATE materials SET min_stock = ? WHERE name = 'Test Box'", (bad,))
        for ok in (0, 2.5, None):
            conn.execute("UPDATE materials SET min_stock = ? WHERE name = 'Test Box'", (ok,))
        conn.execute("UPDATE materials SET min_stock = 10 WHERE name = 'Test Box'")
        conn.commit()
        assert conn.execute(
            "SELECT min_stock FROM materials WHERE name = 'Test Box'"
        ).fetchone()[0] == 10
    finally:
        conn.close()


def test_011_rerun_passes_the_hash_check_of_every_earlier_migration(tmp_path):
    db_path = _at_010_with_materials(tmp_path)
    init_db(str(db_path))
    init_db(str(db_path))  # would raise if any applied file's hash differed
    conn = get_connection(str(db_path))
    try:
        applied = [r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations ORDER BY filename")]
    finally:
        conn.close()
    # Migrations after 011 apply too; every file in MIGRATIONS_DIR is applied once, in order.
    assert applied[: len(UP_TO_010) + 1] == [*UP_TO_010, "011_material_min_stock.sql"]
    assert applied == sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
