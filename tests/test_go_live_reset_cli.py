"""python -m tools.go_live_reset: dry-run by default, guards, typed confirmation, backup first, exit codes, the integrity result.
Everything runs on temp copies; the real data folder is guarded by tests/conftest.py."""

import hashlib
import http.server
import json
import sqlite3
import threading
from pathlib import Path

import pytest

import tools.go_live_reset.__main__ as cli
from db.connection import get_connection, init_db
from db.errors import BackupError
from tests.go_live_fixture import build_shop
from tools.integrity_check import __main__ as integrity_cli


@pytest.fixture
def shop_file(tmp_path):
    folder = tmp_path / "shop"
    folder.mkdir()
    path = folder / "shop.db"
    init_db(str(path))
    conn = get_connection(str(path))
    build_shop(conn)
    conn.close()
    return path


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(path, *args, answer="RESET shop.db", server=None, backup=None):
    lines: list[str] = []

    def input_fn(prompt=""):
        if answer is None:
            raise EOFError
        return answer

    code = cli.main(
        ["--db", str(path), *args], input_fn=input_fn, out=lines.append,
        server_check=server or (lambda p: None), backup=backup,
    )
    return code, "\n".join(lines)


def orders(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------- dry-run


def test_dry_run_is_the_default_and_changes_nothing(shop_file):
    before = sha(shop_file)
    code, text = run(shop_file)
    assert code == 0 and "dry-run" in text and "unchanged" in text
    assert sha(shop_file) == before
    assert not (shop_file.parent / "backups").exists()


def test_dry_run_prints_before_and_after_for_every_table(shop_file):
    _, text = run(shop_file, "--dry-run")
    assert "table" in text and "before" in text and "after" in text
    line = next(l for l in text.splitlines() if l.strip().startswith("orders"))
    assert line.split()[:4] == ["orders", "CLEAR", "3", "0"]
    assert "id 4 merged into id 2" in text or "merged into" in text
    assert "products_with_stock" in text and "INV-000001" in text


def test_dry_run_and_apply_print_the_reminders(shop_file):
    for args in ((), ("--apply",)):
        _, text = run(shop_file, *args)
        assert "stocktake draft in EVERY browser" in text
        assert "Move the old invoice PDFs" in text and "Old invoice PDFs in the project's invoices folder:" in text
        assert "python -m tools.integrity_check" in text
        assert "MATERIAL does not ask for a cost" in text


def test_the_dry_run_rehearsal_fails_loudly_when_the_result_would_not_pass_the_checks(shop_file, monkeypatch):
    monkeypatch.setattr(cli, "integrity_verifier", lambda conn: ["c. Orders: FAIL"])
    before = sha(shop_file)
    code, text = run(shop_file)
    assert code == 1 and "REFUSED by the rehearsal" in text and sha(shop_file) == before


# ----------------------------------------------------------------- cannot run (2)


def test_a_missing_file_cannot_run(tmp_path):
    code, text = run(tmp_path / "nope.db")
    assert code == 2 and "CANNOT RUN" in text


def test_a_file_that_is_not_a_rebel_database_cannot_run(tmp_path):
    path = tmp_path / "other.db"
    sqlite3.connect(path).execute("CREATE TABLE t (x)").connection.close()
    code, text = run(path)
    assert code == 2 and "not a Rebel Store Manager database" in text


def test_an_older_schema_cannot_run(shop_file, monkeypatch):
    monkeypatch.setattr(cli, "head_schema", lambda: 99)
    code, text = run(shop_file, "--apply")
    assert code == 2 and "migrated" in text


def test_an_unclassified_table_cannot_run(shop_file):
    conn = sqlite3.connect(shop_file)
    conn.execute("CREATE TABLE brand_new (id INTEGER)")
    conn.commit()
    conn.close()
    code, text = run(shop_file, "--apply")
    assert code == 2 and "brand_new" in text


# --------------------------------------------------------------- apply: guards (1)


def test_apply_with_the_wrong_confirmation_changes_nothing(shop_file):
    before = sha(shop_file)
    code, text = run(shop_file, "--apply", answer="yes")
    assert code == 1 and "Cancelled" in text and sha(shop_file) == before
    assert not (shop_file.parent / "backups").exists()


def test_a_piped_confirmation_with_a_byte_order_mark_is_accepted(shop_file):
    code, _ = run(shop_file, "--apply", answer="﻿RESET shop.db")
    assert code == 0 and orders(shop_file) == 0


def test_apply_without_input_changes_nothing(shop_file):
    before = sha(shop_file)
    code, text = run(shop_file, "--apply", answer=None)
    assert code == 1 and "Cancelled" in text and sha(shop_file) == before


def test_the_confirmation_names_the_database_file(shop_file):
    _, text = run(shop_file, "--apply", answer="x")
    assert "RESET shop.db" in text
    code, _ = run(shop_file, "--apply", answer="RESET other.db")
    assert code == 1 and orders(shop_file) == 3


def test_apply_is_refused_while_the_app_runs(shop_file):
    before = sha(shop_file)
    code, text = run(shop_file, "--apply", server=lambda p: "the app is running (pid 1, port 8000)")
    assert code == 1 and "REFUSED" in text and "stop-rebel.cmd" in text and sha(shop_file) == before


def test_the_server_check_finds_the_pid_file_process(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "rebel.pid.json").write_text(json.dumps({"pid": 4242, "port": 8123, "db": "x", "started": "now"}), encoding="utf-8")
    monkeypatch.setattr(cli.procs, "is_ours", lambda info: True)
    reason = cli.server_running(tmp_path / "shop.db")
    assert "pid 4242" in reason


def test_the_server_check_finds_a_server_that_answers_on_the_recorded_port(tmp_path, monkeypatch):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "run-state.json").write_text(json.dumps({"last_port": port}), encoding="utf-8")
        monkeypatch.setattr(cli, "PORTS", range(0))
        assert f"port {port}" in cli.server_running(tmp_path / "shop.db")
    finally:
        server.shutdown()
        server.server_close()


def test_the_server_check_is_quiet_when_nothing_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "PORTS", range(0))
    assert cli.server_running(tmp_path / "shop.db") is None


def test_apply_is_refused_when_the_database_is_locked(shop_file, monkeypatch):
    monkeypatch.setattr(cli, "LOCK_SECONDS", 0.1)
    blocker = sqlite3.connect(shop_file, isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        before_orders = 3
        code, text = run(shop_file, "--apply")
        assert code == 1 and "locked" in text and "Nothing was changed" in text
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
    assert orders(shop_file) == before_orders
    assert not (shop_file.parent / "backups").exists()


def test_a_failed_backup_aborts_with_nothing_changed(shop_file):
    def failing(path, backups_dir=None):
        raise BackupError("disk full", "disk_full")

    before = sha(shop_file)
    code, text = run(shop_file, "--apply", backup=failing)
    assert code == 1 and "ABORTED: the backup failed" in text and sha(shop_file) == before


# ---------------------------------------------------------------------- apply (0)


def test_apply_makes_a_verified_backup_first_then_resets(shop_file):
    code, text = run(shop_file, "--apply")
    assert code == 0 and "DONE" in text and text.rstrip().splitlines()[-1] != "OK"  # reminders come last
    assert orders(shop_file) == 0
    folder = shop_file.parent / "backups" / "pre-go-live"
    made = sorted(folder.glob("daily-*.db"))
    assert len(made) == 1
    copy = sqlite3.connect(made[0])
    try:
        assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert copy.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 3  # the backup holds the data as it was
        assert copy.execute("PRAGMA user_version").fetchone()[0] == 0
    finally:
        copy.close()
    assert "Backup   :" in text and "pre-go-live" in text


def test_apply_leaves_a_tagged_audit_archive_and_the_marker(shop_file):
    code, text = run(shop_file, "--apply")
    archives = list((shop_file.parent / "backups").glob("audit-archive-golive-*.jsonl"))
    assert code == 0 and len(archives) == 1 and archives[0].name in text
    assert "user_version, audit_archive_tag" in text


def test_the_database_after_apply_passes_the_integrity_tool(shop_file, capsys):
    assert run(shop_file, "--apply")[0] == 0
    capsys.readouterr()
    assert integrity_cli.main(["--db", str(shop_file)]) == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith("OK") and "WARN" not in out and "FAIL" not in out and "INFO" not in out
    assert "PASS    h. Name collisions - 0 collision groups" in out


def test_apply_prints_the_integrity_result_and_the_counters(shop_file):
    _, text = run(shop_file, "--apply")
    assert "PASS    h. Name collisions" in text and "\nOK\n" in text
    assert "INV and PUR at 0" in text


def test_the_product_cost_option_reaches_the_reset(shop_file):
    assert run(shop_file, "--apply", "--product-unit-cost", "zero")[0] == 0
    conn = sqlite3.connect(shop_file)
    try:
        assert conn.execute("SELECT COUNT(*) FROM products WHERE unit_cost IS NOT 0").fetchone()[0] == 0
    finally:
        conn.close()


def test_the_service_cost_option_reaches_the_reset(shop_file):
    assert run(shop_file, "--apply", "--reset-service-costs")[0] == 0
    conn = sqlite3.connect(shop_file)
    try:
        assert conn.execute("SELECT COUNT(*) FROM materials WHERE unit_cost != 0").fetchone()[0] == 0
    finally:
        conn.close()


def test_a_failure_in_the_real_run_rolls_back_and_keeps_the_backup(shop_file, monkeypatch):
    import db.go_live as go_live

    real = go_live._reset_values
    calls = []

    def fail_second_time(*args, **kwargs):
        calls.append(1)
        if len(calls) > 1:  # the first call is the dry rehearsal in memory
            raise RuntimeError("disk error")
        return real(*args, **kwargs)

    monkeypatch.setattr(go_live, "_reset_values", fail_second_time)
    code, text = run(shop_file, "--apply")
    assert code == 1 and "ROLLED BACK" in text and "disk error" in text
    assert orders(shop_file) == 3
    assert list((shop_file.parent / "backups" / "pre-go-live").glob("daily-*.db"))
    assert not list((shop_file.parent / "backups").glob("audit-archive-golive-*.jsonl"))


# ----------------------------------------------------- idempotent and never twice


def test_a_second_apply_on_a_reset_database_says_so_and_touches_nothing(shop_file):
    assert run(shop_file, "--apply")[0] == 0
    before = sha(shop_file)
    backups = sorted(p.name for p in (shop_file.parent / "backups").rglob("*"))
    code, text = run(shop_file, "--apply")
    assert code == 0 and "Already reset" in text
    assert sha(shop_file) == before and sorted(p.name for p in (shop_file.parent / "backups").rglob("*")) == backups


def test_a_dry_run_on_a_reset_database_says_so(shop_file):
    run(shop_file, "--apply")
    code, text = run(shop_file)
    assert code == 0 and "Already reset" in text


def test_a_live_database_is_refused_and_keeps_its_data(shop_file):
    run(shop_file, "--apply")
    conn = get_connection(str(shop_file))
    conn.execute("UPDATE products SET current_stock = 3, unit_cost = 5 WHERE id = 1")
    conn.close()
    before = sha(shop_file)
    for args in ((), ("--apply",)):
        code, text = run(shop_file, *args)
        assert code == 1 and "already went live" in text
    assert sha(shop_file) == before


# ------------------------------------------------------------------ the tool itself


def test_resolve_path_prefers_the_argument_then_rebel_db(monkeypatch, tmp_path):
    monkeypatch.setenv("REBEL_DB", str(tmp_path / "env.db"))
    assert cli.resolve_path(None) == tmp_path / "env.db"
    assert cli.resolve_path("x.db") == Path("x.db")


def test_the_tool_can_be_started_as_a_module_and_defaults_to_a_dry_run(shop_file):
    import subprocess
    import sys

    root = Path(__file__).resolve().parent.parent
    before = sha(shop_file)
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "tools.go_live_reset", "--db", str(shop_file)],
        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0 and "dry-run" in result.stdout and sha(shop_file) == before


def test_the_lock_probe_sees_another_writer_and_releases_at_once(shop_file, monkeypatch):
    monkeypatch.setattr(cli, "LOCK_SECONDS", 0.1)
    assert cli.lock_problem(shop_file) is None
    blocker = sqlite3.connect(shop_file, isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        assert "locked" in cli.lock_problem(shop_file)
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
    assert cli.lock_problem(shop_file) is None


# ------------------------------------------------------------------ --mark-live


def header(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def test_mark_live_dry_run_is_the_default_prints_the_facts_and_changes_nothing(shop_file):
    before = sha(shop_file)
    code, text = run(shop_file, "--mark-live")
    assert code == 0 and "dry-run" in text and "unchanged" in text
    assert "Orders        : 3" in text and "first day" in text and "user_version  : 0" in text and "Markers found : none" in text
    assert "--mark-live --apply" in text
    assert sha(shop_file) == before and not (shop_file.parent / "backups").exists()


def test_mark_live_apply_backs_up_asks_for_the_phrase_and_marks_without_touching_data(shop_file):
    code, text = run(shop_file, "--mark-live", "--apply", answer="MARK LIVE shop.db")
    assert code == 0 and "DONE" in text and "user_version, settings_flag" in text
    assert header(shop_file) == 1 and orders(shop_file) == 3
    backups = list((shop_file.parent / "backups" / "pre-go-live").glob("daily-*.db"))
    assert len(backups) == 1 and header(backups[0]) == 0
    conn = sqlite3.connect(shop_file)
    try:
        assert json.loads(conn.execute("SELECT value FROM settings WHERE key = 'go_live_marker'").fetchone()[0])["method"] == "mark_live"
    finally:
        conn.close()
    code, text = run(shop_file, "--apply")  # the reset now refuses it
    assert code == 1 and "already went live" in text and orders(shop_file) == 3


@pytest.mark.parametrize("answer", ["﻿MARK LIVE shop.db\r", "MARK LIVE shop.db\r\n"])
def test_mark_live_accepts_a_confirmation_piped_from_powershell(shop_file, answer):
    code, _ = run(shop_file, "--mark-live", "--apply", answer=answer)
    assert code == 0 and header(shop_file) == 1


@pytest.mark.parametrize("answer", ["yes", "RESET shop.db", "MARK LIVE other.db", None])
def test_mark_live_with_the_wrong_confirmation_changes_nothing(shop_file, answer):
    before = sha(shop_file)
    code, text = run(shop_file, "--mark-live", "--apply", answer=answer)
    assert code == 1 and "Cancelled" in text and sha(shop_file) == before
    assert not (shop_file.parent / "backups").exists()


def test_mark_live_is_refused_while_the_app_runs_or_the_database_is_locked(shop_file, monkeypatch):
    before = sha(shop_file)
    code, text = run(shop_file, "--mark-live", "--apply", server=lambda p: "the app is running (pid 1, port 8000)")
    assert code == 1 and "REFUSED" in text and "stop-rebel.cmd" in text and sha(shop_file) == before
    monkeypatch.setattr(cli, "lock_problem", lambda p: "the database is locked (test)")
    code, text = run(shop_file, "--mark-live", "--apply")
    assert code == 1 and "locked" in text and sha(shop_file) == before


def test_mark_live_failed_backup_aborts_with_nothing_changed(shop_file):
    def failing(path, backups_dir=None):
        raise BackupError("disk full", "disk_full")

    before = sha(shop_file)
    code, text = run(shop_file, "--mark-live", "--apply", answer="MARK LIVE shop.db", backup=failing)
    assert code == 1 and "ABORTED: the backup failed" in text and sha(shop_file) == before


def test_mark_live_refuses_a_database_without_orders(tmp_path):
    path = tmp_path / "empty" / "shop.db"
    path.parent.mkdir()
    init_db(str(path))
    before = sha(path)
    for args in (("--mark-live",), ("--mark-live", "--apply")):
        code, text = run(path, *args, answer="MARK LIVE shop.db")
        assert code == 1 and "no orders" in text
    assert sha(path) == before


def test_mark_live_refuses_a_database_that_is_already_marked(shop_file):
    run(shop_file, "--mark-live", "--apply", answer="MARK LIVE shop.db")
    before = sha(shop_file)
    for args in (("--mark-live",), ("--mark-live", "--apply")):
        code, text = run(shop_file, *args, answer="MARK LIVE shop.db")
        assert code == 1 and "already marked live" in text
    assert sha(shop_file) == before


def test_mark_live_says_the_header_comes_back_by_itself_when_only_the_flag_is_left(shop_file):
    run(shop_file, "--mark-live", "--apply", answer="MARK LIVE shop.db")
    conn = sqlite3.connect(shop_file)
    conn.execute("PRAGMA user_version = 0")
    conn.close()
    code, text = run(shop_file, "--mark-live")
    assert code == 1 and "settings_flag" in text and "next time the app starts" in text
    init_db(str(shop_file))
    assert header(shop_file) == 1


def test_an_older_schema_cannot_mark_live(shop_file, monkeypatch):
    monkeypatch.setattr(cli, "head_schema", lambda: 999)
    code, text = run(shop_file, "--mark-live")
    assert code == 2 and "CANNOT RUN" in text


def test_the_reset_lists_the_markers_and_refuses_on_a_database_with_only_the_settings_flag(shop_file):
    run(shop_file, "--apply")
    conn = get_connection(str(shop_file))
    conn.execute("PRAGMA user_version = 0")
    conn.execute("UPDATE products SET current_stock = 3, unit_cost = 5 WHERE id = 1")
    conn.close()
    before = sha(shop_file)
    for args in ((), ("--apply",)):
        code, text = run(shop_file, *args)
        assert code == 1 and "already went live" in text and "settings_flag" in text
    assert sha(shop_file) == before
