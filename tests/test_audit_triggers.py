"""Migration 012 and the audit triggers: every audited table and column is covered
(against a database built by ALL migrations), rows are written in the same
transaction as the change, and the log is append-only."""

import json
import re
import shutil
import sqlite3

import pytest

from db import audit
from db.audit import UNAUDITED_COLUMNS, UNAUDITED_TABLES, audit_trigger_sql, audited_table_columns
from db.connection import MIGRATIONS_DIR, get_connection, init_db, transaction


def _log(conn, where: str = "1 = 1", params=()) -> list[dict]:
    rows = conn.execute(f"SELECT * FROM audit_log WHERE {where} ORDER BY id", params).fetchall()
    return [
        {**dict(r),
         "before": json.loads(r["before_json"]) if r["before_json"] else None,
         "after": json.loads(r["after_json"]) if r["after_json"] else None}
        for r in rows
    ]


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _trigger_sql(conn, name: str) -> str | None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?", (name,)
    ).fetchone()
    return row[0] if row else None


# ------------------------------------------------------------------ coverage


def test_migration_012_creates_the_audit_tables_and_append_only_triggers(test_db):
    tables = {r[0] for r in test_db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"audit_log", "audit_context", "audit_control"} <= tables
    assert test_db.execute("SELECT allow_purge FROM audit_control").fetchall()[0][0] == 0
    assert _trigger_sql(test_db, "trg_audit_log_no_update") is not None
    assert _trigger_sql(test_db, "trg_audit_log_no_delete") is not None


def test_every_audited_table_has_exactly_the_generated_triggers(test_db):
    """The coverage test: a table or column added by a later migration without regenerated
    triggers fails here. UNAUDITED_TABLES / UNAUDITED_COLUMNS in db/audit.py are the only
    places to list an exception."""
    covered = audited_table_columns(test_db)
    assert len(covered) >= 24  # the accounting tables as of migration 012
    for table, columns in covered.items():
        generated = _normalize(audit_trigger_sql(table, columns))
        actual = " ".join(
            _normalize(_trigger_sql(test_db, f"trg_audit_{table}_{kind}") or "MISSING") + ";"
            for kind in ("ins", "upd", "del")
        )
        assert actual == generated, table


def test_unaudited_tables_have_no_audit_triggers_and_the_rest_do(test_db):
    all_tables = {
        r[0] for r in test_db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    with_triggers = {
        re.match(r"trg_audit_(.+)_(ins|upd|del)$", r[0]).group(1)
        for r in test_db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' "
            "AND name LIKE 'trg_audit_%' AND name NOT LIKE 'trg_audit_log_%'"
        )
    }
    assert with_triggers == all_tables - UNAUDITED_TABLES
    assert {"orders", "settings", "stock_movements", "payment_methods"} <= with_triggers
    assert {"counters", "schema_migrations", "audit_log"} <= UNAUDITED_TABLES


def test_unaudited_columns_never_appear_in_a_trigger(test_db):
    for table in audited_table_columns(test_db):
        for kind in ("ins", "upd", "del"):
            sql = _trigger_sql(test_db, f"trg_audit_{table}_{kind}")
            for column in UNAUDITED_COLUMNS:
                assert f"'{column}'" not in sql, (table, kind, column)


# --------------------------------------------------------------- the rows


def test_insert_update_delete_rows_hold_the_row_and_the_changed_columns(test_db):
    test_db.execute("INSERT INTO suppliers (name, phone) VALUES ('Fictional Print Co', '021')")
    supplier_id = test_db.execute("SELECT id FROM suppliers").fetchone()[0]
    test_db.execute("UPDATE suppliers SET phone = '031', notes = 'moved' WHERE id = ?", (supplier_id,))
    test_db.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))

    insert, update, delete = _log(test_db, "entity_type = 'suppliers'")
    assert (insert["action"], insert["entity_id"]) == ("INSERT", str(supplier_id))
    assert insert["after"]["name"] == "Fictional Print Co" and insert["before"] is None
    assert update["action"] == "UPDATE"
    assert update["before"] == {"phone": "021", "notes": None}
    assert update["after"] == {"phone": "031", "notes": "moved"}
    assert delete["action"] == "DELETE" and delete["after"] is None
    assert delete["before"]["name"] == "Fictional Print Co"
    assert [e["operation"] for e in (insert, update, delete)] == ["UNLABELLED"] * 3


def test_a_no_op_update_and_an_updated_at_only_change_log_nothing(test_db):
    test_db.execute("INSERT INTO suppliers (name) VALUES ('Quiet Co')")
    before = len(_log(test_db))
    test_db.execute("UPDATE suppliers SET name = 'Quiet Co'")  # same value; updated_at trigger fires
    test_db.execute("UPDATE suppliers SET updated_at = '2030-01-01 00:00:00'")
    assert len(_log(test_db)) == before


def test_money_is_logged_as_an_integer_and_quantities_as_numbers(test_db):
    test_db.execute(
        "INSERT INTO materials (name, type, unit, current_stock, unit_cost) "
        "VALUES ('Fictional Box', 'STOCK', 'piece', 2.5, 1800005)"
    )
    entry = _log(test_db, "entity_type = 'materials'")[0]
    assert entry["after"]["unit_cost"] == 1_800_005 and isinstance(entry["after"]["unit_cost"], int)
    assert entry["after"]["current_stock"] == 2.5
    assert '"unit_cost":1800005,' in entry["after_json"]  # no ".0"


def test_text_keyed_tables_log_the_key(test_db):
    test_db.execute("UPDATE settings SET value = '7' WHERE key = 'postage_estimate_window'")
    entry = _log(test_db, "entity_type = 'settings'")[0]
    assert (entry["entity_id"], entry["action"]) == ("postage_estimate_window", "UPDATE")
    assert entry["after"] == {"value": "7"}


def test_updated_at_stamping_trigger_does_not_add_a_second_row(test_db):
    test_db.execute("INSERT INTO partners (name, current_percentage) VALUES ('Fictional Partner', 50)")
    test_db.execute("UPDATE partners SET current_percentage = 40")
    updates = _log(test_db, "entity_type = 'partners' AND action = 'UPDATE'")
    assert len(updates) == 1 and updates[0]["after"] == {"current_percentage": 40}


# ------------------------------------------------------- same transaction


def test_a_rolled_back_change_leaves_no_row(test_db):
    with pytest.raises(RuntimeError):
        with transaction(test_db):
            test_db.execute("INSERT INTO suppliers (name) VALUES ('Never Saved')")
            raise RuntimeError("fail after the write")
    assert _log(test_db) == []
    assert test_db.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 0


def test_a_rolled_back_savepoint_removes_only_its_own_rows(test_db):
    with transaction(test_db):
        test_db.execute("INSERT INTO suppliers (name) VALUES ('Kept')")
        with pytest.raises(RuntimeError):
            with transaction(test_db):
                test_db.execute("INSERT INTO suppliers (name) VALUES ('Dropped')")
                raise RuntimeError("inner failure")
    assert [e["after"]["name"] for e in _log(test_db)] == ["Kept"]


def test_a_failing_log_insert_undoes_the_change(test_db):
    test_db.execute(
        "CREATE TEMP TRIGGER boom BEFORE INSERT ON main.audit_log "
        "BEGIN SELECT RAISE(ABORT, 'audit write failed'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="audit write failed"):
        test_db.execute("INSERT INTO suppliers (name) VALUES ('Unlogged')")
    assert test_db.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 0


# ----------------------------------------------------------- append-only


def test_audit_log_rows_cannot_be_updated_or_deleted(test_db):
    test_db.execute("INSERT INTO suppliers (name) VALUES ('Fixed Co')")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        test_db.execute("UPDATE audit_log SET operation = 'edited'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        test_db.execute("DELETE FROM audit_log")
    assert len(_log(test_db)) == 1


# ---------------------------------------------------- migrating existing data


def test_migration_012_on_an_existing_database_logs_nothing_and_touches_no_updated_at(tmp_path):
    old_dir = tmp_path / "migrations_to_011"
    old_dir.mkdir()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name < "012":
            shutil.copy(path, old_dir / path.name)
    db_path = str(tmp_path / "existing.db")
    init_db(db_path, migrations_dir=old_dir)
    conn = get_connection(db_path)
    conn.execute("INSERT INTO suppliers (name, updated_at) VALUES ('Old Co', '2026-01-02 03:04:05')")
    conn.close()

    init_db(db_path)  # applies 012 (and backs the copy up first)

    conn = get_connection(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0
        assert conn.execute("SELECT updated_at FROM suppliers").fetchone()[0] == "2026-01-02 03:04:05"
        conn.execute("UPDATE suppliers SET phone = '1'")
        assert len(_log(conn)) == 1
    finally:
        conn.close()
