"""Migration 010: payment_methods.fee_cap (optional cap on the percentage part of the fee)."""

import sqlite3
from pathlib import Path

import pytest

from db.connection import MIGRATIONS_DIR, get_connection, init_db

UP_TO_009 = tuple(
    name for name in sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql")) if name < "010"
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


def _at_009_with_methods_and_orders(tmp_path) -> Path:
    assert UP_TO_009[-1] == "009_rial_storage.sql"
    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "at_009", UP_TO_009)))
    conn = get_connection(str(db_path))
    try:
        x = conn.execute
        zarinpal = x(
            "INSERT INTO payment_methods (name, fee_bps, fee_fixed, settlement_rule, settlement_days, updated_at) "
            f"VALUES ('Zarinpal', 50, 5000, 'DAYS_AFTER', 1, '{OLD_STAMP}')"
        ).lastrowid
        x(
            "INSERT INTO payment_methods (name, fee_bps, fee_fixed, settlement_rule, updated_at) "
            f"VALUES ('Card', 0, 0, 'IMMEDIATE', '{OLD_STAMP}')"
        )
        # 94,900,000 Rial paid with no cap yet: 474,500 + 5,000. It must stay frozen.
        x(
            "INSERT INTO orders (invoice_number, order_date, status, channel, customer_name, shipping_charge, "
            "postage_cost, transaction_fee, packaging_cost, stock_committed, payment_method_id, paid_date) "
            "VALUES ('INV-000001', '2026-09-10 08:00:00', 'PAID', 'WEBSITE', 'Test Buyer', 0, 0, 479500, 0, 1, ?, "
            "'2026-09-10')", (zarinpal,)
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_010_adds_fee_cap_null_and_changes_nothing_else(tmp_path):
    db_path = _at_009_with_methods_and_orders(tmp_path)
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

    assert "010_payment_method_fee_cap.sql" in applied
    assert [tuple(r) for r in integrity] == [("ok",)]
    assert fk == []
    assert triggers_after == triggers_before
    assert indexes_after == indexes_before
    assert set(after) == set(before)
    for table, rows_before in before.items():
        rows_after = after[table]
        assert len(rows_after) == len(rows_before), table
        for row_before, row_after in zip(rows_before, rows_after, strict=True):
            if table == "payment_methods":
                assert row_after.pop("fee_cap") is None
            assert row_after == row_before, table

    assert {m["updated_at"] for m in after["payment_methods"]} == {OLD_STAMP}
    assert [o["transaction_fee"] for o in after["orders"]] == [479500]


def test_010_check_refuses_zero_and_negative(tmp_path):
    db_path = _at_009_with_methods_and_orders(tmp_path)
    init_db(str(db_path))
    conn = get_connection(str(db_path))
    try:
        for bad in (0, -1):
            with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
                conn.execute("UPDATE payment_methods SET fee_cap = ? WHERE name = 'Zarinpal'", (bad,))
        conn.execute("UPDATE payment_methods SET fee_cap = 1 WHERE name = 'Zarinpal'")
        conn.execute("UPDATE payment_methods SET fee_cap = NULL WHERE name = 'Zarinpal'")
        conn.execute("UPDATE payment_methods SET fee_cap = 160000 WHERE name = 'Zarinpal'")
        conn.commit()
        assert conn.execute(
            "SELECT fee_cap FROM payment_methods WHERE name = 'Zarinpal'"
        ).fetchone()[0] == 160000
    finally:
        conn.close()


def test_010_rerun_passes_the_hash_check_of_every_earlier_migration(tmp_path):
    db_path = _at_009_with_methods_and_orders(tmp_path)
    init_db(str(db_path))
    init_db(str(db_path))  # would raise if any applied file's hash differed
    conn = get_connection(str(db_path))
    try:
        applied = [r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations ORDER BY filename")]
    finally:
        conn.close()
    assert applied == [*UP_TO_009, "010_payment_method_fee_cap.sql"]
