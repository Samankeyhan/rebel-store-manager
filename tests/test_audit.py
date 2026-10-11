"""db/audit.py: operation labels and grouping, the actor, reading, and the deliberate reset."""

import hashlib
import json
import sqlite3

import pytest

from db import audit
from db.audit import audit_operation, audited, list_audit_log, reset_audit_log
from db.connection import get_connection, init_db, transaction
from db.errors import ValidationError


def _rows(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY id")]


def _supplier(conn, name):
    return conn.execute("INSERT INTO suppliers (name) VALUES (?)", (name,)).lastrowid


# ------------------------------------------------------- labels and grouping


def test_rows_of_one_operation_share_the_label_and_op_id(test_db):
    with audit_operation(test_db, "demo_operation"):
        _supplier(test_db, "A")
        _supplier(test_db, "B")
    first, second = _rows(test_db)
    assert first["operation"] == second["operation"] == "demo_operation"
    assert first["op_id"] and first["op_id"] == second["op_id"]
    assert first["actor"] is None


def test_separate_operations_get_separate_op_ids(test_db):
    with audit_operation(test_db, "one"):
        _supplier(test_db, "A")
    with audit_operation(test_db, "two"):
        _supplier(test_db, "B")
    first, second = _rows(test_db)
    assert first["op_id"] != second["op_id"]
    assert (first["operation"], second["operation"]) == ("one", "two")


def test_a_nested_operation_joins_the_outer_one(test_db):
    with audit_operation(test_db, "outer"):
        _supplier(test_db, "A")
        with audit_operation(test_db, "inner"):
            _supplier(test_db, "B")
    first, second = _rows(test_db)
    assert first["op_id"] == second["op_id"]
    assert (first["operation"], second["operation"]) == ("outer", "outer")


def test_the_context_is_gone_after_the_operation_and_after_a_failure(test_db):
    with audit_operation(test_db, "ok"):
        _supplier(test_db, "A")
    assert test_db.execute("SELECT COUNT(*) FROM audit_context").fetchone()[0] == 0
    with pytest.raises(RuntimeError):
        with audit_operation(test_db, "fails"):
            _supplier(test_db, "B")
            raise RuntimeError("boom")
    assert test_db.execute("SELECT COUNT(*) FROM audit_context").fetchone()[0] == 0
    assert [r["operation"] for r in _rows(test_db)] == ["ok"]  # the failed one left nothing
    _supplier(test_db, "C")
    assert _rows(test_db)[-1]["operation"] == "UNLABELLED"


def test_a_failed_nested_operation_inside_an_open_transaction_is_rolled_back_alone(test_db):
    with transaction(test_db):
        with audit_operation(test_db, "outer"):
            _supplier(test_db, "Kept")
            with pytest.raises(RuntimeError):
                with audit_operation(test_db, "inner"):
                    _supplier(test_db, "Dropped")
                    raise RuntimeError("boom")
    assert [json.loads(r["after_json"])["name"] for r in _rows(test_db)] == ["Kept"]


def test_the_actor_comes_from_the_argument_or_the_context_variable(test_db):
    with audit_operation(test_db, "explicit", actor="amir"):
        _supplier(test_db, "A")
    token = audit.current_actor.set("sara")
    try:
        with audit_operation(test_db, "implicit"):
            _supplier(test_db, "B")
    finally:
        audit.current_actor.reset(token)
    assert [r["actor"] for r in _rows(test_db)] == ["amir", "sara"]


def test_audited_decorator_labels_with_the_function_name_or_a_given_label(test_db):
    @audited()
    def add_something(conn, name):
        return _supplier(conn, name)

    @audited("custom_label")
    def add_other(conn, name):
        return _supplier(conn, name)

    assert add_something(test_db, "A") == 1
    add_other(test_db, "B")
    assert [r["operation"] for r in _rows(test_db)] == ["add_something", "custom_label"]


# ------------------------------------------------------------------ reading


def _seed_rows(conn):
    """Four rows at chosen moments (the log accepts inserts; only update/delete are blocked)."""
    for entity_type, entity_id, op_id, operation, ts in (
        ("orders", "1", "op-a", "record_order", "2026-03-01 08:00:00"),
        ("orders", "1", "op-b", "update_order_status", "2026-03-02 08:00:00"),
        ("orders", "2", "op-c", "record_order", "2026-03-03 08:00:00"),
        ("products", "1", "op-a", "record_order", "2026-03-03 09:00:00"),
    ):
        conn.execute(
            "INSERT INTO audit_log (ts, entity_type, entity_id, action, operation, op_id, after_json) "
            "VALUES (?, ?, ?, 'UPDATE', ?, ?, '{\"x\": 1}')",
            (ts, entity_type, entity_id, operation, op_id),
        )


def test_list_returns_newest_first_with_parsed_json_and_a_total(test_db):
    _seed_rows(test_db)
    page = list_audit_log(test_db)
    assert page["total"] == 4
    assert [e["id"] for e in page["items"]] == [4, 3, 2, 1]
    assert page["items"][0]["after"] == {"x": 1} and page["items"][0]["before"] is None
    assert "after_json" not in page["items"][0]


@pytest.mark.parametrize("filters, expected_ids", [
    ({"entity_type": "orders"}, [3, 2, 1]),
    ({"entity_type": "orders", "entity_id": 1}, [2, 1]),
    ({"entity_id": "1"}, [4, 2, 1]),
    ({"op_id": "op-a"}, [4, 1]),
    ({"operation": "record_order"}, [4, 3, 1]),
    ({"start_date": "2026-03-03"}, [4, 3]),
    ({"end_date": "2026-03-01"}, [1]),
    ({"start_date": "2026-03-02", "end_date": "2026-03-02"}, [2]),
    ({"entity_type": "nothing"}, []),
])
def test_list_filters(test_db, filters, expected_ids):
    _seed_rows(test_db)
    page = list_audit_log(test_db, **filters)
    assert [e["id"] for e in page["items"]] == expected_ids
    assert page["total"] == len(expected_ids)


def test_list_pagination_keeps_the_total(test_db):
    _seed_rows(test_db)
    first = list_audit_log(test_db, entity_type="orders", limit=2)
    second = list_audit_log(test_db, entity_type="orders", limit=2, offset=2)
    assert (first["total"], second["total"]) == (3, 3)
    assert [e["id"] for e in first["items"]] == [3, 2]
    assert [e["id"] for e in second["items"]] == [1]


@pytest.mark.parametrize("bad", [
    {"limit": 0}, {"limit": 501}, {"limit": True}, {"limit": "5"}, {"offset": -1}, {"offset": 1.5},
])
def test_list_rejects_bad_paging(test_db, bad):
    with pytest.raises(ValidationError) as exc_info:
        list_audit_log(test_db, **bad)
    assert exc_info.value.field in ("limit", "offset")


# -------------------------------------------------------------------- reset


def _file_db(tmp_path):
    path = str(tmp_path / "shop.db")
    init_db(path)
    return get_connection(path)


def test_reset_archives_every_row_then_leaves_one_reset_row(tmp_path):
    conn = _file_db(tmp_path)
    try:
        with audit_operation(conn, "demo"):
            _supplier(conn, "Archived Co")
        before = _rows(conn)

        result = reset_audit_log(conn)

        # Default: <database folder>/backups/, next to the database backups (gitignored).
        archive = tmp_path / "backups" / result["archive"]
        assert archive.exists() and result["archive"].startswith("audit-archive-")
        assert result["rows"] == len(before) == 1
        lines = archive.read_text(encoding="utf-8").splitlines()
        assert [json.loads(line) for line in lines] == before
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == result["sha256"]

        (marker,) = _rows(conn)
        assert (marker["operation"], marker["entity_type"], marker["entity_id"]) == (
            "reset_audit_log", "audit_log", "reset"
        )
        assert json.loads(marker["before_json"]) == {
            "archive": result["archive"], "rows": 1, "sha256": result["sha256"]
        }
    finally:
        conn.close()


def test_the_log_is_append_only_again_after_a_reset_and_ids_keep_growing(tmp_path):
    conn = _file_db(tmp_path)
    try:
        _supplier(conn, "A")
        old_max = conn.execute("SELECT MAX(id) FROM audit_log").fetchone()[0]
        reset_audit_log(conn)
        assert conn.execute("SELECT allow_purge FROM audit_control").fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM audit_log")
        _supplier(conn, "B")
        assert conn.execute("SELECT MAX(id) FROM audit_log").fetchone()[0] > old_max
    finally:
        conn.close()


def test_reset_with_an_explicit_archive_path_never_overwrites_an_archive(tmp_path):
    conn = _file_db(tmp_path)
    try:
        _supplier(conn, "A")
        target = tmp_path / "elsewhere" / "log.jsonl"
        reset_audit_log(conn, archive_path=target)
        assert target.exists()
        _supplier(conn, "B")
        before = _rows(conn)
        with pytest.raises(ValidationError, match="already exists"):
            reset_audit_log(conn, archive_path=target)
        assert _rows(conn) == before  # nothing cleared
    finally:
        conn.close()


def test_a_reset_that_fails_midway_leaves_the_log_as_it_was(tmp_path):
    conn = _file_db(tmp_path)
    try:
        _supplier(conn, "A")
        before = _rows(conn)
        conn.execute(
            "CREATE TEMP TRIGGER block_marker BEFORE INSERT ON main.audit_log "
            "WHEN NEW.operation = 'reset_audit_log' BEGIN SELECT RAISE(ABORT, 'marker failed'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="marker failed"):
            reset_audit_log(conn)
        assert _rows(conn) == before
        assert conn.execute("SELECT allow_purge FROM audit_control").fetchone()[0] == 0
    finally:
        conn.close()


def test_reset_of_an_in_memory_database_needs_an_explicit_path():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    with pytest.raises(ValidationError, match="archive_path"):
        reset_audit_log(conn)
