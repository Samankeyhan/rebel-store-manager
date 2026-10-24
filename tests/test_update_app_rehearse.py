"""--rehearse, the figures it compares, and the rules that keep the updater honest (up-front imports, one-line .cmd, .gitignore, no kill of strangers)."""

import ast
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from db.connection import MIGRATIONS_DIR, get_connection, init_db
from tests.go_live_fixture import build_shop
from tests.update_app_harness import FakeCtx, make_root, sha
from tools.update_app import context, invariants
from tools.update_app.__main__ import main
from tools.update_app.rehearse import rehearse

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "tools" / "update_app"


@pytest.fixture
def lab(tmp_path):
    """A project folder whose migrations folder holds a copy of the real ones; a shop database built from them sits in data/restore-test/real/."""
    root = tmp_path / "proj"
    (root / "data" / "restore-test" / "real").mkdir(parents=True)
    shutil.copytree(MIGRATIONS_DIR, root / "migrations")
    source = root / "data" / "restore-test" / "real" / "shop.db"
    init_db(str(source), migrations_dir=str(root / "migrations"))
    conn = get_connection(str(source))
    build_shop(conn)
    conn.close()
    ctx = FakeCtx(root)

    def real_migrate(db):
        ctx.calls.append("migrate")
        from db.connection import init_db as run_init

        before = invariants_names(db)
        try:
            run_init(str(db), migrations_dir=str(root / "migrations"))
        except Exception as exc:
            return 1, f"MIGRATION FAILED: {type(exc).__name__}: {exc}\n"
        return 0, "".join(f"APPLIED {n}\n" for n in sorted(invariants_names(db) - before)) + "MIGRATION OK\n"

    ctx.migrate = real_migrate
    ctx.integrity = lambda db: ctx.integrity_results.pop(0) if ctx.integrity_results else (0, "OK\n")
    return SimpleNamespace(root=root, source=source, ctx=ctx)


def invariants_names(db):
    conn = sqlite3.connect(db)
    try:
        return {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
    finally:
        conn.close()


def add_migration(lab, sql, name="014_dummy.sql"):
    (lab.root / "migrations" / name).write_text(sql, encoding="utf-8")


def test_a_path_inside_data_is_refused_and_nothing_is_copied(lab):
    real = lab.root / "data" / "shop.db"
    shutil.copy(lab.source, real)
    before = sha(real)
    assert rehearse(lab.ctx, str(real)) == 1
    assert "inside the real data folder" in lab.ctx.text
    assert sha(real) == before and not list((lab.root / "data" / "restore-test").glob("rehearsal-*"))
    assert rehearse(lab.ctx, str(lab.root / "data" / "backups" / "x.db")) == 1


def test_a_missing_file_means_could_not_run(lab):
    assert rehearse(lab.ctx, str(lab.root / "nowhere.db")) == 2


def test_an_identical_database_passes_and_the_copy_is_made_in_its_own_folder(lab):
    source_hash = sha(lab.source)
    assert rehearse(lab.ctx, str(lab.source)) == 0
    assert "REHEARSAL OK" in lab.ctx.text
    (folder,) = (lab.root / "data" / "restore-test").glob("rehearsal-*")
    assert (folder / "shop.db").is_file() and sha(lab.source) == source_hash
    assert not (lab.root / "data" / "shop.db").exists()
    assert not (lab.root / "data" / "backups").exists() and not (lab.root / "data" / "logs").exists()
    assert "git" not in " ".join(lab.ctx.calls) and "stop" not in lab.ctx.calls and "start" not in lab.ctx.calls


def test_a_harmless_new_table_passes_and_is_reported_as_info(lab):
    add_migration(lab, "CREATE TABLE brand_new_notes (id INTEGER PRIMARY KEY, amount INTEGER);\nINSERT INTO brand_new_notes (amount) VALUES (5);\n")
    assert rehearse(lab.ctx, str(lab.source)) == 0
    assert "APPLIED 014_dummy.sql" in lab.ctx.text and "INFO new table brand_new_notes: 1 rows" in lab.ctx.text
    assert "new migrations applied: 1" in lab.ctx.text


def test_a_migration_that_changes_a_cost_fails(lab):
    add_migration(lab, "UPDATE materials SET unit_cost = unit_cost + 1;\n")
    assert rehearse(lab.ctx, str(lab.source)) == 1
    assert "REHEARSAL FAILED: figures changed" in lab.ctx.text and "DIFF materials." in lab.ctx.text and "unit_cost" in lab.ctx.text


def test_a_migration_that_changes_a_row_count_fails(lab):
    add_migration(lab, "DELETE FROM expenses;\n")
    assert rehearse(lab.ctx, str(lab.source)) == 1
    assert "DIFF row count.expenses" in lab.ctx.text


def test_a_failing_migration_fails_the_rehearsal(lab):
    add_migration(lab, "THIS IS NOT SQL;\n")
    assert rehearse(lab.ctx, str(lab.source)) == 1 and "the migration failed" in lab.ctx.text


def test_integrity_problems_before_block_the_rehearsal(lab):
    lab.ctx.integrity_results = [(1, "c1 FAIL stock\nFAILED: 1 problems")]
    assert rehearse(lab.ctx, str(lab.source)) == 1
    assert "integrity check before" in lab.ctx.text and "migrate" not in lab.ctx.calls


def test_integrity_problems_after_fail_the_rehearsal(lab):
    lab.ctx.integrity_results = [(0, "OK"), (1, "c2 FAIL x")]
    assert rehearse(lab.ctx, str(lab.source)) == 1 and "integrity check after" in lab.ctx.text


def test_the_figures_ignore_schema_migrations_and_time_stamps_but_catch_everything_else():
    base = {
        "migrations": ["001"], "counts": {"a": 1}, "profit_and_loss": {"x": 1}, "settlements": {"count": 0},
        "materials": {1: {"id": 1, "unit_cost": 5, "updated_at": "t1"}}, "products": {},
        "orders": {1: {"id": 1, "status": "COMPLETED", "customer_total": 100}},
    }
    changed = {**base, "migrations": ["001", "002"], "counts": {"a": 1, "b": 3},
               "materials": {1: {"id": 1, "unit_cost": 5, "updated_at": "t2", "new_column": 9}}}
    failures, info = invariants.compare(base, changed, ["002"])
    assert failures == [] and info == ["new table b: 3 rows"]
    failures, _ = invariants.compare(base, {**changed, "migrations": ["001"]}, ["002"])
    assert any("schema_migrations grew by 0" in f for f in failures)
    failures, _ = invariants.compare(base, {**changed, "profit_and_loss": {"x": 2}}, ["002"])
    assert failures == ["profit and loss.x: 1 -> 2"]
    # an order row is compared column by column; a column the migration added is not a difference
    widened = {1: {"id": 1, "status": "COMPLETED", "customer_total": 100, "void_reason": None}}
    assert invariants.compare(base, {**changed, "orders": widened}, ["002"])[0] == []
    failures, _ = invariants.compare(base, {**changed, "orders": {1: {**widened[1], "customer_total": 90}}}, ["002"])
    assert failures == ["orders.1.customer_total: 100 -> 90"]
    failures, _ = invariants.compare(base, {**changed, "orders": {}}, ["002"])
    assert failures == ["orders id 1 disappeared"]


def test_main_rehearse_goes_through_the_command_line(lab):
    assert main(["--rehearse", str(lab.source)], lab.ctx) == 0


# ------------------------------------------------------------------ the updater's own rules


def test_no_module_of_the_updater_imports_anything_lazily():
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for node in ast.walk(function):
                    assert not isinstance(node, (ast.Import, ast.ImportFrom)), f"{path.name}:{node.lineno} imports inside a function"


def test_importing_the_entry_point_loads_every_module_the_updater_needs():
    code = (
        "import sys, tools.update_app.__main__\n"
        "print(sorted(m for m in sys.modules if m.startswith('tools.update_app.')))\n"
        "print(sorted(m for m in sys.modules if m in ('db.backup','tools.run_app.procs','tools.run_app.frontend','tools.go_live_reset.__main__')))"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    loaded, others = (ast.literal_eval(line) for line in result.stdout.strip().splitlines())
    files = {f"tools.update_app.{p.stem}" for p in PACKAGE.glob("*.py") if p.stem not in ("__init__", "__main__")}
    assert files <= set(loaded)
    assert len(others) == 4


def test_the_cmd_file_has_one_effective_line_that_starts_with_the_cd_guard():
    text = (ROOT / "update-rebel.cmd").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0].startswith('@cd /d "%~dp0" && ')
    assert "-m tools.update_app %*" in lines[0] and lines[0].rstrip().endswith("& pause")


def test_python_never_pauses():
    """The single pause is the one in the .cmd file."""
    for path in PACKAGE.glob("*.py"):
        assert "pause" not in path.read_text(encoding="utf-8").lower(), path.name


def test_a_stranger_in_the_pid_file_is_never_killed_by_the_real_process_code(tmp_path):
    """Real context.Ctx methods with a fake `run`: the pid file names a notepad.exe; nothing may be stopped or killed."""
    root = make_root(tmp_path)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        text = '"notepad.exe","4242","Console","1","9,000 K"\n' if command[0] == "tasklist" else ""
        return SimpleNamespace(returncode=0, stdout=text, stderr="")

    ctx = context.Ctx(root=root, env={}, out=lambda s: None, run=run)
    (root / "data" / "logs").mkdir()
    (root / "data" / "logs" / "rebel.pid.json").write_text('{"pid": 4242, "port": 8000}', encoding="utf-8")
    info = ctx.app_info()
    assert ctx.app_is_ours(info) is False
    assert ctx.process_alive(4242) is False  # not a python image
    assert not any(c[0] == "taskkill" for c in commands)


def test_every_runtime_artifact_is_ignored_by_git(tmp_path):
    """A clone where the app has run must have a clean `git status --porcelain` (the update refuses a dirty tree)."""
    repo = tmp_path / "clone"
    (repo / "frontend").mkdir(parents=True)
    shutil.copy(ROOT / ".gitignore", repo / ".gitignore")
    shutil.copy(ROOT / "frontend" / ".gitignore", repo / "frontend" / ".gitignore")
    git = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True)  # noqa: E731
    if git("init", "-q").returncode != 0:
        pytest.skip("git is not available")
    artifacts = [
        "invoices/invoice_INV-000001.pdf", "data/shop.db", "data/shop.db-wal", "data/shop.db-shm", "data/shop.db-journal",
        "data/logs/rebel.pid.json", "data/logs/run-state.json", "data/logs/update-state.json", "data/logs/update-20261022-090000.log",
        "data/logs/app.log", "data/backups/daily-2026-10-22-090000.db", "data/backups/pre-update/shop-failed-update-x.db",
        "data/backups/pre-migration/daily-x.db", "data/restore-test/rehearsal-x/shop.db", "data/integrity-2026-10-22.txt",
        "frontend/out/index.html", "frontend/out/.rebel-build.json", "frontend/.next/cache/x", "frontend/node_modules/x/index.js",
        "frontend/tsconfig.tsbuildinfo", "frontend/next-env.d.ts", "api/__pycache__/x.pyc", "db/__pycache__/y.pyc",
        "tools/update_app/__pycache__/z.pyc", ".pytest_cache/v/x", ".venv/pyvenv.cfg", "Rebel.lnk",
    ]
    for name in artifacts:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x")
    listed = [line for line in git("status", "--porcelain", "-uall").stdout.splitlines() if line.strip()]
    assert sorted(line.split()[-1] for line in listed) == [".gitignore", "frontend/.gitignore"], listed
