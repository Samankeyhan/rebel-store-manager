"""db/go_live.py: the go-live reset clears exactly the transaction tables, keeps the setup data, merges the duplicate payment
method, resets stock / costs / counters / the audit log in ONE transaction, and never erases a database that went live."""

import json
import sqlite3
from pathlib import Path

import pytest

import db.go_live as go_live
from db.audit import reset_audit_log
from db.backup import make_backup
from db.connection import get_connection, init_db
from db.errors import ConflictError, ValidationError
from db.go_live import (
    ARCHIVE_PREFIX, CLEAR_ORDER, GO_LIVE_USER_VERSION, KEEP, TABLE_CLASS, apply_go_live, assess, live_markers,
    unclassified_tables,
)
from db.orders import record_order
from db.purchases import record_material_purchase
from tests.go_live_fixture import build_shop, db_file, dump
from tools.go_live_reset.__main__ import integrity_verifier
from tools.integrity_check.checks import run_checks


@pytest.fixture
def shop(test_db):
    ids = build_shop(test_db)
    return test_db, ids


_ARCHIVES: dict = {}


@pytest.fixture(autouse=True)
def _archive_folder(tmp_path):
    """Archives go into the test's own folder (the test database itself sits in the shared temp folder)."""
    _ARCHIVES["dir"] = tmp_path
    yield
    _ARCHIVES.clear()


def archive(conn, name="a") -> Path:
    return _ARCHIVES["dir"] / f"{ARCHIVE_PREFIX}test-{name}.jsonl"


def keep_tables() -> list[str]:
    return sorted(t for t, c in TABLE_CLASS.items() if c == KEEP)


def counts(conn, tables) -> dict:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


# ---------------------------------------------------------------- classification


def test_every_table_of_a_fresh_database_has_exactly_one_class(test_db):
    assert unclassified_tables(test_db) == []
    assert {t for t in go_live.user_tables(test_db)} == set(TABLE_CLASS)
    assert set(CLEAR_ORDER) == {t for t, c in TABLE_CLASS.items() if c == go_live.CLEAR}


def test_a_table_without_a_class_is_reported_and_blocks_the_reset(shop):
    conn, _ = shop
    conn.execute("CREATE TABLE brand_new (id INTEGER PRIMARY KEY)")
    assert unclassified_tables(conn) == ["brand_new"]
    with pytest.raises(ValidationError):
        apply_go_live(conn, archive(conn))
    assert counts(conn, ["orders"])["orders"] == 3


# ------------------------------------------------------------------- what is cleared


def test_apply_clears_exactly_the_clear_tables_and_nothing_else_loses_rows(shop):
    conn, _ = shop
    before = counts(conn, go_live.user_tables(conn))
    assert all(before[t] > 0 for t in CLEAR_ORDER), {t: before[t] for t in CLEAR_ORDER}
    result = apply_go_live(conn, archive(conn))
    after = counts(conn, go_live.user_tables(conn))
    assert all(after[t] == 0 for t in CLEAR_ORDER)
    for table in go_live.user_tables(conn):
        if table in CLEAR_ORDER:
            continue
        if table == "audit_log":
            assert after[table] == 1
        elif table == "payment_methods":
            assert after[table] == before[table] - 1
        elif table == "settings":
            assert after[table] == before[table] + 1  # the go-live marker row
        else:
            assert after[table] == before[table], table
    assert result["before"] == before and result["after"] == after


def test_keep_tables_are_unchanged_row_for_row(shop):
    conn, _ = shop
    # channel_settings: only a default payment method pointing at the merged duplicate moves (own test below)
    tables = [t for t in keep_tables() if t not in ("channel_settings", "settings")] + ["schema_migrations", "audit_control"]
    settings = "SELECT key, value FROM settings WHERE key != 'go_live_marker' ORDER BY key"
    settings_before = [tuple(r) for r in conn.execute(settings)]
    channels = "SELECT channel, applies_shipping_charge, applies_postage, default_packaging_kit_id FROM channel_settings ORDER BY channel"
    before, channels_before = dump(conn, tables), [tuple(r) for r in conn.execute(channels)]
    apply_go_live(conn, archive(conn))
    assert dump(conn, tables) == before
    assert [tuple(r) for r in conn.execute(settings)] == settings_before  # the marker row is the only addition
    assert [tuple(r) for r in conn.execute(channels)] == channels_before


def test_catalogue_rows_keep_every_column_except_stock_and_unit_cost(shop):
    conn, _ = shop
    columns = {
        "products": "id, name, category_id, retail_price, wholesale_price, is_active, made_to_order, created_at, updated_at, name_key",
        "materials": "id, name, type, unit, is_active, created_at, updated_at, category_id, min_stock, name_key",
    }
    before = {t: [tuple(r) for r in conn.execute(f"SELECT {c} FROM {t} ORDER BY id")] for t, c in columns.items()}
    apply_go_live(conn, archive(conn))
    for table, cols in columns.items():
        assert [tuple(r) for r in conn.execute(f"SELECT {cols} FROM {table} ORDER BY id")] == before[table], table


def test_stock_goes_to_zero_and_a_service_material_has_no_stock(shop):
    conn, _ = shop
    apply_go_live(conn, archive(conn))
    assert conn.execute("SELECT COUNT(*) FROM products WHERE current_stock != 0").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM materials WHERE type = 'STOCK' AND current_stock != 0").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM materials WHERE type = 'SERVICE' AND current_stock IS NOT NULL").fetchone()[0] == 0


def test_product_unit_cost_becomes_null_by_default_and_zero_on_request(test_db):
    build_shop(test_db)
    assert test_db.execute("SELECT COUNT(*) FROM products WHERE unit_cost > 0").fetchone()[0] > 0
    apply_go_live(test_db, archive(test_db, "null"))
    assert test_db.execute("SELECT COUNT(*) FROM products WHERE unit_cost IS NOT NULL").fetchone()[0] == 0


def test_product_unit_cost_zero_option(test_db):
    build_shop(test_db)
    apply_go_live(test_db, archive(test_db, "zero"), product_unit_cost="zero")
    assert test_db.execute("SELECT COUNT(*) FROM products WHERE unit_cost IS NOT 0").fetchone()[0] == 0


def test_an_unknown_product_unit_cost_choice_is_refused(shop):
    conn, _ = shop
    with pytest.raises(ValidationError):
        apply_go_live(conn, archive(conn), product_unit_cost="free")


def test_stock_materials_cost_zero_and_service_cost_is_kept_by_default(shop):
    conn, ids = shop
    apply_go_live(conn, archive(conn))
    rows = {r["type"]: r["unit_cost"] for r in conn.execute("SELECT type, MAX(unit_cost) AS unit_cost FROM materials GROUP BY type")}
    assert rows == {"STOCK": 0, "SERVICE": 5000}


def test_service_costs_can_be_reset_too(shop):
    conn, _ = shop
    apply_go_live(conn, archive(conn), reset_service_costs=True)
    assert conn.execute("SELECT COUNT(*) FROM materials WHERE unit_cost != 0").fetchone()[0] == 0


def test_updated_at_is_restored_after_the_stock_and_cost_reset(shop):
    conn, _ = shop
    before = {t: [r[0] for r in conn.execute(f"SELECT updated_at FROM {t} ORDER BY id")] for t in ("products", "materials")}
    assert any(v is not None for v in before["products"] + before["materials"])
    apply_go_live(conn, archive(conn))
    for table, stamps in before.items():
        assert [r[0] for r in conn.execute(f"SELECT updated_at FROM {table} ORDER BY id")] == stamps


# -------------------------------------------------------------- counters and ids


def test_counters_restart_and_the_next_documents_start_at_one(shop):
    conn, ids = shop
    assert {r["name"]: r["value"] for r in conn.execute("SELECT * FROM counters")} == {"INV": 3, "PUR": 2}
    apply_go_live(conn, archive(conn))
    assert {r["name"]: r["value"] for r in conn.execute("SELECT * FROM counters")} == {"INV": 0, "PUR": 0}
    conn.execute("UPDATE products SET current_stock = 5, unit_cost = 1 WHERE id = ?", (ids["shirt"],))
    order = record_order(conn, "IN_PERSON", [{"product_id": ids["shirt"], "quantity": 1, "unit_price": 1000000}])
    purchase = record_material_purchase(conn, ids["paper"], 1, 1000)
    assert order == 1 and purchase == 1
    assert conn.execute("SELECT invoice_number FROM orders WHERE id = 1").fetchone()[0] == "INV-000001"
    assert conn.execute("SELECT invoice_number FROM material_purchases WHERE id = 1").fetchone()[0] == "PUR-000001"


def test_cleared_tables_restart_their_ids_and_kept_tables_do_not(shop):
    conn, ids = shop
    products = conn.execute("SELECT MAX(id) FROM products").fetchone()[0]
    methods = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'payment_methods'").fetchone()[0]
    apply_go_live(conn, archive(conn))
    sequences = {r["name"]: r["seq"] for r in conn.execute("SELECT name, seq FROM sqlite_sequence")}
    assert not set(CLEAR_ORDER) & set(sequences)
    assert sequences["products"] == products and sequences["payment_methods"] == methods


# ----------------------------------------------------------- payment method merge


def test_the_duplicate_payment_method_is_merged_into_digipay(shop):
    conn, ids = shop
    apply_go_live(conn, archive(conn))
    rows = {r["id"]: r for r in conn.execute("SELECT * FROM payment_methods")}
    assert ids["digipay_dup"] not in rows and set(rows) == {ids["zarinpal"], ids["digipay"], ids["card"]}
    survivor = rows[ids["digipay"]]
    assert survivor["name"] == "DigiPay" and survivor["name_key"] == "digipay"
    assert (survivor["fee_bps"], survivor["settlement_rule"], survivor["settlement_days"]) == (1300, "DAY_OF_NEXT_MONTH", 7)
    assert all(r["name_key"] for r in rows.values())
    assert go_live.find_name_collisions(conn) == []


def test_references_to_the_duplicate_are_re_pointed_to_the_survivor(shop):
    conn, ids = shop
    result = apply_go_live(conn, archive(conn))
    assert result["merge"] == {"survivor_id": ids["digipay"], "duplicate_id": ids["digipay_dup"], "names": ["DigiPay", "digipay"]}
    assert conn.execute("SELECT default_payment_method_id FROM channel_settings WHERE channel = 'WEBSITE'").fetchone()[0] == ids["digipay"]
    assert result["references_repointed"] >= 1
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_a_different_name_collision_blocks_the_reset(shop):
    conn, _ = shop
    conn.execute("UPDATE products SET name_key = NULL WHERE name IN ('Test LP', 'Test Shirt')")
    conn.execute("UPDATE products SET name = 'Test LP' WHERE name = 'Test Shirt'")
    before = counts(conn, ["orders"])
    with pytest.raises(ConflictError):
        apply_go_live(conn, archive(conn))
    assert counts(conn, ["orders"]) == before
    assert not archive(conn).exists()


# ----------------------------------------------------------------------- audit log


def test_the_audit_log_keeps_one_row_and_the_archive_holds_the_rest(shop):
    conn, _ = shop
    path = archive(conn)
    old_rows = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    result = apply_go_live(conn, path)
    rows = conn.execute("SELECT entity_type, entity_id, action, operation, op_id, before_json FROM audit_log").fetchall()
    assert len(rows) == 1 and rows[0]["operation"] == "reset_audit_log" and rows[0]["op_id"] is None
    summary = json.loads(rows[0]["before_json"])
    assert summary["archive"] == path.name and path.name.startswith(ARCHIVE_PREFIX)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == result["archive"]["rows"] == summary["rows"] > old_rows
    operations = {line["operation"] for line in lines}
    assert "go_live_reset" in operations and {"record_order"} <= operations


def test_the_marker_is_set_by_the_reset(shop):
    conn, _ = shop
    assert live_markers(conn) == []
    result = apply_go_live(conn, archive(conn))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == GO_LIVE_USER_VERSION
    assert result["markers"] == ["user_version", "audit_archive_tag", "settings_flag"]


# ------------------------------------------------------------------ all or nothing


def snapshot(conn):
    return dump(conn, go_live.user_tables(conn)), conn.execute("PRAGMA user_version").fetchone()[0]


@pytest.mark.parametrize("step", ["_clear", "_merge_payment_methods", "_reset_values", "reset_audit_log"])
def test_a_failure_in_any_step_rolls_everything_back_and_removes_the_archive(shop, monkeypatch, step):
    conn, _ = shop
    before = snapshot(conn)
    path = archive(conn, step)

    def boom(*args, **kwargs):
        raise RuntimeError(f"{step} failed")

    if step == "reset_audit_log":
        def late_boom(conn_, archive_path):
            reset_audit_log(conn_, archive_path=archive_path)  # the archive file exists, then it fails
            raise RuntimeError("after the archive")
        monkeypatch.setattr(go_live, "reset_audit_log", lambda c, archive_path=None: late_boom(c, archive_path))
    else:
        monkeypatch.setattr(go_live, step, boom)
    with pytest.raises(RuntimeError):
        apply_go_live(conn, path)
    assert snapshot(conn) == before
    assert not path.exists() and not conn.in_transaction


def test_a_problem_found_by_the_verification_rolls_everything_back(shop):
    conn, _ = shop
    before = snapshot(conn)
    path = archive(conn)
    with pytest.raises(ConflictError, match="rolled back"):
        apply_go_live(conn, path, verify=lambda c: ["a check failed"])
    assert snapshot(conn) == before and not path.exists()


def test_an_existing_archive_file_is_never_overwritten_or_deleted(shop):
    conn, _ = shop
    path = archive(conn)
    path.write_text("precious", encoding="utf-8")
    with pytest.raises(ValidationError):
        apply_go_live(conn, path)
    assert path.read_text(encoding="utf-8") == "precious"
    assert counts(conn, ["orders"])["orders"] == 3


def test_the_result_passes_every_integrity_check(shop):
    conn, _ = shop
    apply_go_live(conn, archive(conn), verify=integrity_verifier)
    results = run_checks(conn, 15)
    assert [(r.key, r.status) for r in results if r.status not in ("PASS", "SKIPPED")] == []
    assert [r.key for r in results if r.status == "SKIPPED"] == ["d3"]
    assert all(not r.infos for r in results)


# --------------------------------------------------- idempotency and the live marker


def test_a_second_run_on_a_reset_database_is_reported_and_changes_nothing(shop):
    conn, _ = shop
    apply_go_live(conn, archive(conn, "1"))
    assert assess(conn)["state"] == "already_reset"
    before = snapshot(conn)
    with pytest.raises(ConflictError, match="already reset"):
        apply_go_live(conn, archive(conn, "2"))
    assert snapshot(conn) == before and not archive(conn, "2").exists()


def test_a_plain_older_audit_reset_does_not_count_as_going_live(shop):
    conn, _ = shop
    reset_audit_log(conn, archive_path=_ARCHIVES["dir"] / "audit-archive-plain.jsonl")
    assert live_markers(conn) == []
    assert assess(conn)["state"] == "ready"
    apply_go_live(conn, archive(conn))
    assert counts(conn, ["orders"])["orders"] == 0


def test_a_live_database_with_data_is_refused_even_after_a_later_plain_audit_reset(shop):
    conn, ids = shop
    apply_go_live(conn, archive(conn))
    conn.execute("UPDATE products SET current_stock = 5, unit_cost = 1 WHERE id = ?", (ids["shirt"],))
    record_order(conn, "IN_PERSON", [{"product_id": ids["shirt"], "quantity": 1, "unit_price": 1000000}])
    reset_audit_log(conn, archive_path=_ARCHIVES["dir"] / "audit-archive-later.jsonl")
    assert [r["before_json"] for r in conn.execute("SELECT before_json FROM audit_log")][0].find(ARCHIVE_PREFIX) < 0
    assert live_markers(conn) == ["user_version", "settings_flag"]  # the audit tag is gone, the other two survive
    before = snapshot(conn)
    assert assess(conn)["state"] == "live"
    with pytest.raises(ConflictError, match="already went live"):
        apply_go_live(conn, archive(conn, "again"))
    assert snapshot(conn) == before


def test_the_audit_tag_alone_also_marks_a_database_as_live(shop):
    conn, ids = shop
    apply_go_live(conn, archive(conn))
    conn.execute("PRAGMA user_version = 0")
    conn.execute("DELETE FROM settings WHERE key = 'go_live_marker'")
    conn.execute("UPDATE products SET current_stock = 5 WHERE id = ?", (ids["shirt"],))
    assert live_markers(conn) == ["audit_archive_tag"]
    assert assess(conn)["state"] == "live"


def test_the_marker_survives_an_online_backup_and_a_new_connection(shop, tmp_path):
    conn, _ = shop
    apply_go_live(conn, archive(conn))
    made = make_backup(db_file(conn), backups_dir=tmp_path / "bk")
    copy = sqlite3.connect(made["path"])
    try:
        assert copy.execute("PRAGMA user_version").fetchone()[0] == GO_LIVE_USER_VERSION
    finally:
        copy.close()
    again = get_connection(db_file(conn))
    try:
        assert again.execute("PRAGMA user_version").fetchone()[0] == GO_LIVE_USER_VERSION
    finally:
        again.close()


def test_init_db_does_not_disturb_the_marker(shop):
    conn, _ = shop
    apply_go_live(conn, archive(conn))
    init_db(db_file(conn))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == GO_LIVE_USER_VERSION


def test_nothing_else_in_the_repo_uses_user_version():
    root = Path(__file__).resolve().parent.parent
    users = [
        str(p.relative_to(root))
        for folder in ("db", "api", "tools", "migrations", "pdf")
        for p in (root / folder).rglob("*")
        if p.suffix in {".py", ".sql"} and "user_version" in p.read_text(encoding="utf-8")
    ]
    # db/go_live.py reads and writes the header; the CLI only prints the word (facts and the marker list)
    assert sorted(u.replace("\\", "/") for u in users) == ["db/go_live.py", "tools/go_live_reset/__main__.py"]


def test_assess_of_a_fresh_shop_is_ready_and_lists_nothing_to_hide(shop):
    conn, _ = shop
    state = assess(conn)
    assert state["state"] == "ready" and state["markers"] == [] and state["problems"]


# ------------------------------------------------------- the settings flag, heal_marker, mark_live


def all_rows(conn):
    return dump(conn, go_live.user_tables(conn))


def flag(conn):
    row = conn.execute("SELECT value FROM settings WHERE key = 'go_live_marker'").fetchone()
    return None if row is None else json.loads(row[0])


def test_the_reset_writes_the_settings_flag_with_method_reset(shop):
    conn, _ = shop
    assert flag(conn) is None
    apply_go_live(conn, archive(conn))
    value = flag(conn)
    assert value["method"] == "reset" and value["at"]
    assert go_live.marker_method(conn) == "reset"
    assert go_live.TABLE_CLASS["settings"] == go_live.KEEP


def test_a_database_with_only_the_settings_flag_is_live_and_the_reset_refuses(shop):
    conn, ids = shop
    apply_go_live(conn, archive(conn))
    conn.execute("PRAGMA user_version = 0")
    conn.execute("UPDATE products SET current_stock = 5, unit_cost = 1 WHERE id = ?", (ids["shirt"],))
    record_order(conn, "IN_PERSON", [{"product_id": ids["shirt"], "quantity": 1, "unit_price": 1000000}])
    reset_audit_log(conn, archive_path=_ARCHIVES["dir"] / "audit-archive-later.jsonl")  # the audit tag goes too
    assert live_markers(conn) == ["settings_flag"]
    before = snapshot(conn)
    assert assess(conn)["state"] == "live"
    with pytest.raises(ConflictError, match="already went live"):
        apply_go_live(conn, archive(conn, "again"))
    assert snapshot(conn) == before


@pytest.mark.parametrize("keep_flag", [True, False])
def test_init_db_puts_the_header_back_when_the_audit_tag_or_the_flag_survives(shop, keep_flag):
    conn, _ = shop
    apply_go_live(conn, archive(conn))
    conn.execute("PRAGMA user_version = 0")
    if not keep_flag:
        conn.execute("DELETE FROM settings WHERE key = 'go_live_marker'")  # the audit tag is still there
    before = all_rows(conn)
    init_db(db_file(conn))
    fresh = get_connection(db_file(conn))
    try:
        assert fresh.execute("PRAGMA user_version").fetchone()[0] == GO_LIVE_USER_VERSION
        assert dump(fresh, go_live.user_tables(fresh)) == before  # not one row, audit entry or updated_at moved
    finally:
        fresh.close()


def test_heal_marker_never_sets_the_header_from_nothing(shop):
    conn, _ = shop
    before = all_rows(conn)
    assert go_live.heal_marker(conn) is False
    init_db(db_file(conn))
    assert all_rows(conn) == before
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0


def test_heal_marker_leaves_a_foreign_header_value_alone(shop):
    conn, _ = shop
    apply_go_live(conn, archive(conn))
    conn.execute("PRAGMA user_version = 7")
    assert go_live.heal_marker(conn) is False
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 7


def test_heal_marker_is_idempotent_and_writes_nothing_else(shop):
    conn, _ = shop
    apply_go_live(conn, archive(conn))
    conn.execute("PRAGMA user_version = 0")
    before = all_rows(conn)
    assert go_live.heal_marker(conn) is True
    assert go_live.heal_marker(conn) is False
    assert all_rows(conn) == before


def test_heal_marker_copes_with_a_database_without_the_tables(tmp_path):
    bare = sqlite3.connect(tmp_path / "bare.db")
    try:
        assert go_live.heal_marker(bare) is False
    finally:
        bare.close()


def test_mark_live_marks_a_database_with_orders_and_changes_nothing_else(shop):
    conn, _ = shop
    facts = go_live.database_facts(conn)
    assert facts["orders"] > 0 and facts["user_version"] == 0 and facts["markers"] == []
    assert facts["first_order_day"] and facts["last_order_day"]
    others = [t for t in go_live.user_tables(conn) if t not in ("settings", "audit_log")]
    before = dump(conn, others)
    audit_before = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    settings_before = [tuple(r) for r in conn.execute("SELECT key, value FROM settings ORDER BY key")]
    result = go_live.mark_live(conn)
    assert result["markers"] == ["user_version", "settings_flag"]
    assert conn.execute("PRAGMA user_version").fetchone()[0] == GO_LIVE_USER_VERSION
    assert flag(conn)["method"] == "mark_live" and go_live.marker_method(conn) == "mark_live"
    added = conn.execute("SELECT operation, entity_type FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    assert tuple(added) == ("mark_live", "settings")
    assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == audit_before + 1
    assert dump(conn, others) == before
    settings_after = [tuple(r) for r in conn.execute("SELECT key, value FROM settings WHERE key != 'go_live_marker' ORDER BY key")]
    assert settings_after == settings_before


def test_mark_live_refuses_a_marked_database(shop):
    conn, _ = shop
    go_live.mark_live(conn)
    before = snapshot(conn)
    with pytest.raises(ConflictError, match="already marked"):
        go_live.mark_live(conn)
    assert snapshot(conn) == before


def test_mark_live_refuses_a_database_without_orders_and_an_open_transaction(test_db):
    with pytest.raises(ConflictError, match="no orders"):
        go_live.mark_live(test_db)
    assert live_markers(test_db) == []
    test_db.execute("BEGIN")
    with pytest.raises(ValidationError):
        go_live.mark_live(test_db)
    test_db.execute("ROLLBACK")


def test_the_reset_refuses_a_database_that_was_marked_live(shop):
    conn, _ = shop
    go_live.mark_live(conn)
    before = snapshot(conn)
    assert assess(conn)["state"] == "live"
    with pytest.raises(ConflictError, match="already went live"):
        apply_go_live(conn, archive(conn))
    assert snapshot(conn) == before


def test_every_copy_path_keeps_the_header(shop, tmp_path):
    import shutil

    from tools.update_app.fsutil import sqlite_copy

    conn, _ = shop
    go_live.mark_live(conn)
    source = Path(db_file(conn))
    sqlite_copy(source, tmp_path / "sqlite_copy.db")
    shutil.copyfile(source, tmp_path / "copyfile.db")
    for name in ("sqlite_copy.db", "copyfile.db"):
        copy = sqlite3.connect(tmp_path / name)
        try:
            assert copy.execute("PRAGMA user_version").fetchone()[0] == GO_LIVE_USER_VERSION, name
        finally:
            copy.close()
