"""The integrity check is read-only by construction (proofs), has the documented exit codes and CLI behaviour, and prints
Persian names without crashing a console."""

import ast
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import db.connection
from tools.integrity_check import __main__ as cli
from tools.integrity_check import checks
from tools.integrity_check.readonly import open_readonly
from tools.integrity_check.report import CheckResult, Row, final_line

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def db_file(conn) -> str:
    return next(row["file"] for row in conn.execute("PRAGMA database_list") if row["name"] == "main")


@pytest.fixture
def populated(test_db):
    test_db.execute("INSERT INTO suppliers (name) VALUES ('Fictional Supply')")
    test_db.execute("INSERT INTO expense_categories (name) VALUES ('Fictional Rent')")
    return test_db


def run_cli(*args, env=None):
    full_env = {**os.environ, "PYTHONIOENCODING": "cp1252", **(env or {})}
    full_env.pop("REBEL_DB", None) if env is None else None
    return subprocess.run(
        [sys.executable, "-m", "tools.integrity_check", *args], cwd=ROOT, env=full_env, capture_output=True, timeout=120
    )


# ------------------------------------------------------------------ proofs


def test_a_full_run_leaves_the_database_file_and_its_folder_untouched(populated, capsys):
    path = db_file(populated)
    before_hash, before_folder = sha(path), sorted(os.listdir(Path(path).parent))
    before_stat = os.stat(path)
    assert cli.main(["--db", path]) == 0
    capsys.readouterr()
    assert sha(path) == before_hash
    assert os.stat(path).st_mtime_ns == before_stat.st_mtime_ns and os.stat(path).st_size == before_stat.st_size
    assert sorted(os.listdir(Path(path).parent)) == before_folder  # no -journal / -wal / -shm side files


def test_a_write_through_the_tools_connection_raises(populated):
    conn = open_readonly(db_file(populated))
    try:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        for sql in ("INSERT INTO suppliers (name) VALUES ('x')", "UPDATE suppliers SET name = 'y'",
                    "DELETE FROM suppliers", "CREATE TABLE t (a)", "DROP TABLE suppliers"):
            with pytest.raises(sqlite3.OperationalError):
                conn.execute(sql)
    finally:
        conn.close()
    assert populated.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 1


def test_a_read_only_open_with_query_only_off_still_cannot_write(populated):
    """mode=ro alone refuses writes too (the two guards are independent)."""
    conn = open_readonly(db_file(populated))
    try:
        conn.execute("PRAGMA query_only = OFF")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO suppliers (name) VALUES ('x')")
    finally:
        conn.close()


def test_init_db_and_every_writer_are_never_called(populated, monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise AssertionError("the integrity check must not call this")

    for name in ("init_db", "get_connection", "transaction", "next_counter"):
        monkeypatch.setattr(db.connection, name, boom)
    import db.name_keys as name_keys_module

    monkeypatch.setattr(name_keys_module, "backfill_name_keys", boom)
    assert cli.main(["--db", db_file(populated)]) == 0
    capsys.readouterr()


FORBIDDEN_CALLS = {
    "init_db", "get_connection", "transaction", "commit", "rollback", "executescript", "executemany",
    "backfill_name_keys", "next_counter", "reset_audit_log", "audit_operation", "audited",
}
FORBIDDEN_SQL = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|VACUUM|ATTACH|DETACH|REINDEX)\b")
ALLOWED_PRAGMAS = {"integrity_check", "foreign_key_check", "query_only", "table_info", "database_list"}


def _tool_sources():
    # go_live_reset and update_app are deliberate writers (they reset, migrate or restore a database; their own tests prove what they
    # write); every other tool stays read-only
    return sorted(p for p in TOOLS.rglob("*.py") if not {"go_live_reset", "update_app"} & set(p.parts))


def _sql_text(node):
    """The literal text of a string / f-string argument, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


@pytest.mark.parametrize("path", _tool_sources(), ids=lambda p: str(p.relative_to(ROOT)))
def test_the_tool_source_never_imports_or_calls_a_writer_and_runs_only_select_and_read_pragmas(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not {a.name for a in node.names} & FORBIDDEN_CALLS, f"{path.name}:{node.lineno} imports a writer"
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            assert name not in FORBIDDEN_CALLS, f"{path.name}:{node.lineno} calls {name}"
            if name == "execute" and node.args:
                text = _sql_text(node.args[0])
                assert text is not None, f"{path.name}:{node.lineno} executes SQL that is not a literal"
                assert re.match(r"\s*(SELECT|WITH|PRAGMA)\b", text), f"{path.name}:{node.lineno} runs non-read SQL"
                for pragma in re.findall(r"PRAGMA\s+(\w+)", text):
                    assert pragma in ALLOWED_PRAGMAS, f"{path.name}:{node.lineno} PRAGMA {pragma}"
    # Every SQL-looking literal (uppercase whole words only; docstrings are not SQL) must be free of write keywords.
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            # A quoted value is data ('INSERT' as an audit action), not a statement: drop it before looking for keywords.
            statement = re.sub(r"'[^']*'", "''", node.value)
            assert not FORBIDDEN_SQL.search(statement), f"{path.name}:{node.lineno} contains a write keyword: {node.value[:60]!r}"


def test_the_scan_itself_would_catch_a_writer():
    """The scan above is only worth something if it fires: feed it bad source."""
    bad = ast.parse("from db.connection import init_db\nconn.execute('DELETE FROM orders')\nconn.commit()")
    names = [n.func.attr for n in ast.walk(bad) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert "commit" in names and FORBIDDEN_SQL.search("DELETE FROM orders")
    assert {a.name for n in ast.walk(bad) if isinstance(n, ast.ImportFrom) for a in n.names} & FORBIDDEN_CALLS


# ------------------------------------------------------------- exit codes


def test_a_missing_file_is_exit_2_and_is_never_created(tmp_path, capsys):
    missing = tmp_path / "nothing.db"
    assert cli.main(["--db", str(missing)]) == 2
    out = capsys.readouterr().out
    assert "CANNOT RUN" in out and "not found" in out and not missing.exists()
    assert list(tmp_path.iterdir()) == []


def test_a_folder_a_text_file_and_an_empty_sqlite_file_are_exit_2_and_unchanged(tmp_path, capsys):
    garbage = tmp_path / "garbage.db"
    garbage.write_bytes(b"this is not a database" * 50)
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    other = tmp_path / "other.db"
    raw = sqlite3.connect(other)
    raw.execute("CREATE TABLE t (a)")
    raw.commit()
    raw.close()
    hashes = {p: sha(p) for p in (garbage, empty, other)}
    for target in (tmp_path, garbage, empty, other):
        assert cli.main(["--db", str(target)]) == 2, target
        assert "CANNOT RUN" in capsys.readouterr().out
    assert {p: sha(p) for p in hashes} == hashes


def test_a_check_that_cannot_run_is_reported_and_makes_the_exit_code_2_but_fail_rows_still_print(populated, monkeypatch, capsys):
    raw = sqlite3.connect(db_file(populated), isolation_level=None)
    raw.execute("PRAGMA foreign_keys = OFF")
    raw.execute("INSERT INTO order_items (order_id, product_id, quantity, list_price, unit_price, unit_cost_at_time) "
                "VALUES (99, 99, 1, 1, 1, 0)")
    raw.close()

    def broken(conn, schema):
        raise RuntimeError("boom")

    monkeypatch.setattr(checks, "CHECKS", [
        checks.Check("a", "Database health", 0, checks.check_database_health, ""),
        checks.Check("c", "Orders", 0, broken, ""),
    ])
    code = cli.main(["--db", db_file(populated)])
    out = capsys.readouterr().out
    assert code == 2
    assert "ERROR   c. Orders - could not run: RuntimeError: boom" in out
    assert "FAIL order_items" in out
    assert out.strip().splitlines()[-1] == "INCOMPLETE: 1 checks failed to run; 2 problems found"


def test_final_line_and_exit_codes():
    ok = CheckResult("a", "A")
    bad = CheckResult("b", "B")
    bad.fails = [Row("t", 1, "f", 2, 1, 1), Row("t", 2, "f", 3, 1, 2)]
    warn = CheckResult("c", "C")
    warn.warns = [Row("t", 3, "f", 1, 2)]
    broken = CheckResult("d", "D")
    broken.error = "boom"
    skipped = CheckResult("e", "E")
    skipped.skipped = "needs migration 013"
    assert final_line([ok, warn, skipped]) == ("OK", 0)
    assert final_line([ok, bad]) == ("FAILED: 2 problems", 1)
    assert final_line([bad, broken]) == ("INCOMPLETE: 1 checks failed to run; 2 problems found", 2)
    assert final_line([broken]) == ("INCOMPLETE: 1 checks failed to run; 0 problems found", 2)


# ----------------------------------------------------------- CLI through a subprocess


def test_cli_exit_codes_and_database_precedence(populated, tmp_path):
    path = db_file(populated)
    clean = run_cli("--db", path)
    assert clean.returncode == 0, clean.stdout.decode("utf-8", "replace")
    assert clean.stdout.decode("utf-8").strip().splitlines()[-1] == "OK"

    # REBEL_DB is used when --db is absent; --db wins over it.
    via_env = run_cli(env={"REBEL_DB": path})
    assert via_env.returncode == 0 and path.encode() in via_env.stdout
    wins = run_cli("--db", path, env={"REBEL_DB": str(tmp_path / "other.db")})
    assert wins.returncode == 0 and path.encode() in wins.stdout
    assert run_cli(env={"REBEL_DB": str(tmp_path / "nope.db")}).returncode == 2

    raw = sqlite3.connect(path, isolation_level=None)
    raw.execute("PRAGMA foreign_keys = OFF")
    raw.execute("INSERT INTO order_items (order_id, product_id, quantity, list_price, unit_price, unit_cost_at_time) "
                "VALUES (99, 99, 1, 1, 1, 0)")
    raw.close()
    broken = run_cli("--db", path)
    assert broken.returncode == 1
    last = broken.stdout.decode("utf-8").strip().splitlines()[-1]
    assert last == "FAILED: 2 problems"  # the dangling row breaks two foreign keys
    assert run_cli("--db", str(tmp_path / "missing.db")).returncode == 2


def test_persian_names_are_printed_as_utf_8_even_when_the_console_is_not(test_db):
    test_db.execute("INSERT INTO suppliers (name) VALUES ('کتاب ٣')")
    raw = sqlite3.connect(db_file(test_db), isolation_level=None)
    raw.execute("INSERT INTO suppliers (name) VALUES ('کتاب 3')")  # same name key once backfilled: raw rows have none
    raw.close()
    for encoding in ("cp1252", "ascii"):
        result = run_cli("--db", db_file(test_db), env={"PYTHONIOENCODING": encoding})
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        text = result.stdout.decode("utf-8")
        assert "suppliers id=[1, 2] field=name" in text  # the ids are always there
        assert "کتاب" in text


def test_the_header_is_followed_by_the_report_so_two_days_can_be_compared(populated, capsys):
    cli.main(["--db", db_file(populated)])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines[: cli.HEADER_LINES]) == 9 and lines[8] == "-" * 60
    assert lines[9].startswith("PASS    a. Database health")


def test_resolve_path_prefers_the_argument_then_the_environment_then_the_shop_database(monkeypatch, tmp_path):
    monkeypatch.setenv("REBEL_DB", str(tmp_path / "else.db"))
    assert cli.resolve_path("given.db") == Path("given.db")
    assert cli.resolve_path(None) == tmp_path / "else.db"
    monkeypatch.delenv("REBEL_DB")
    assert cli.resolve_path(None) == db.connection.PROJECT_ROOT / "data" / "shop.db"
