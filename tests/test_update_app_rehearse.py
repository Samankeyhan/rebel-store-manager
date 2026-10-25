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


def test_a_rehearsal_of_migration_015_compares_purchases_and_reports_the_backfill(tmp_path):
    """A shop database before 015 (fictional purchases written the 014 way), rehearsed with the real migrations:
    nothing owed after the backfill, one payment per purchase with a total, every purchase row unchanged."""
    from tests.test_migration_015 import _add_fictional_purchases

    root = tmp_path / "proj"
    (root / "data" / "restore-test" / "real").mkdir(parents=True)
    shutil.copytree(MIGRATIONS_DIR, root / "migrations")
    old = tmp_path / "to_014"
    old.mkdir()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name < "015":
            shutil.copy(path, old / path.name)
    source = root / "data" / "restore-test" / "real" / "shop.db"
    init_db(str(source), migrations_dir=str(old))
    _add_fictional_purchases(str(source))
    init_db(str(source), migrations_dir=str(old))  # the startup backfill gives the raw rows their name_key
    ctx = FakeCtx(root)

    def migrate(db):
        init_db(str(db), migrations_dir=str(root / "migrations"))
        return 0, "MIGRATION OK\n"

    ctx.migrate = migrate
    ctx.integrity = lambda db: (0, "OK\n")
    assert rehearse(ctx, str(source)) == 0, ctx.text
    assert "REHEARSAL OK" in ctx.text
    assert "INFO supplier payments backfilled: 3 (purchases with a total: 3)" in ctx.text
    assert "INFO purchases without a movement link: 0" in ctx.text
    assert "INFO purchases without a cost snapshot (cannot be cancelled later): 1" in ctx.text
    assert "INFO new table supplier_payments: 3 rows" in ctx.text


def _payables(**overrides):
    return {"outstanding": 0, "by_supplier": {}, "payments": 2, "purchases_with_total": 2, "without_movement_link": 0, "without_cost_snapshot": 0, **overrides}


def test_the_purchase_rows_and_the_backfill_are_compared():
    base = {
        "migrations": ["001"], "counts": {"a": 1}, "profit_and_loss": {}, "settlements": {}, "materials": {}, "products": {},
        "orders": {}, "purchases": {"MATERIAL:1": {"id": 1, "total_paid": 500, "notes": None}}, "payables": None,
    }
    after = {**base, "migrations": ["001", "015"],
             "purchases": {"MATERIAL:1": {"id": 1, "total_paid": 500, "notes": None, "status": "ACTIVE"}}, "payables": _payables()}
    failures, info = invariants.compare(base, after, ["015"])
    assert failures == [] and "supplier payments backfilled: 2 (purchases with a total: 2)" in info
    changed = {**after, "purchases": {"MATERIAL:1": {"id": 1, "total_paid": 400, "notes": None}}}
    assert invariants.compare(base, changed, ["015"])[0] == ["purchases.MATERIAL:1.total_paid: 500 -> 400"]
    assert invariants.compare(base, {**after, "purchases": {}}, ["015"])[0] == ["purchases id MATERIAL:1 disappeared"]
    owed = invariants.compare(base, {**after, "payables": _payables(outstanding=7)}, ["015"])[0]
    assert owed == ["payables: 7 owed to suppliers right after the backfill (must be 0)"]
    missing = invariants.compare(base, {**after, "payables": _payables(payments=1)}, ["015"])[0]
    assert missing == ["payables: 1 payments backfilled for 2 purchases with a total"]
    # a later migration: the payables figures must not move at all
    later = invariants.compare({**after, "payables": _payables()}, {**after, "payables": _payables(outstanding=3)}, [])[0]
    assert later == ["payables.outstanding: 0 -> 3"]


def test_a_rehearsal_of_migration_016_keeps_every_purchase_payment_and_allocation(tmp_path):
    """A shop database at 015 (purchases, payments and allocations written the 015 way, a cancelled purchase and its
    replacement included), rehearsed with the real migrations: one invoice per purchase, every purchase row, payment,
    allocation, payable and summary figure identical."""
    from tests.test_migration_016 import _add_fictional_rows, _migrations_upto

    root = tmp_path / "proj"
    (root / "data" / "restore-test" / "real").mkdir(parents=True)
    shutil.copytree(MIGRATIONS_DIR, root / "migrations")
    to_015 = _migrations_upto(tmp_path / "to_015", "015")
    source = root / "data" / "restore-test" / "real" / "shop.db"
    init_db(str(source), migrations_dir=str(to_015))
    _add_fictional_rows(str(source), cancelled=True)
    init_db(str(source), migrations_dir=str(to_015))  # the startup backfill gives the raw rows their name_key
    ctx = FakeCtx(root)

    def migrate(db):
        init_db(str(db), migrations_dir=str(root / "migrations"))
        return 0, "MIGRATION OK\n"

    ctx.migrate = migrate
    ctx.integrity = lambda db: (0, "OK\n")
    assert rehearse(ctx, str(source)) == 0, ctx.text
    assert "REHEARSAL OK" in ctx.text
    assert "INFO purchase invoices created: 7 (one per purchase)" in ctx.text
    assert "INFO new table purchase_invoices: 7 rows" in ctx.text
    assert "INFO purchases without a movement link: 1" in ctx.text  # the legacy purchase whose movement is not linked
    assert "DIFF" not in ctx.text


def _purchase_figures(**overrides):
    base = {
        "migrations": ["015"], "counts": {"material_purchases": 1, "product_purchases": 0}, "counters": {"PUR": 1},
        "profit_and_loss": {}, "settlements": {}, "materials": {}, "products": {}, "orders": {},
        "purchases": {"MATERIAL:1": {"id": 1, "material_id": 7, "supplier_id": 2, "invoice_number": "PUR-000001",
                                     "total_paid": 500, "replaces_purchase_id": None}},
        "payments": {1: {"id": 1, "amount": 500}},
        "allocations": {1: {"payment_id": 1, "purchase": "MATERIAL:1", "amount": 500}},
        "purchases_summary": {"material_purchases_total": 500, "material_purchases_count": 1},
        "invoices": None,
        "payables": _payables(outstanding=0, payments=1, purchases_with_total=1, by_supplier=[]),
    }
    return {**base, **overrides}


def test_the_016_figures_fail_on_a_lost_column_a_moved_allocation_or_a_wrong_invoice_count():
    before = _purchase_figures()
    row = {"id": 1, "material_id": 7, "supplier_id": 2, "invoice_number": "PUR-000001", "total_paid": 500,
           "replaces_purchase_id": None, "purchase_invoice_id": 1}
    after = {**before, "migrations": ["015", "016"], "counts": {**before["counts"], "purchase_invoices": 1},
             "purchases": {"MATERIAL:1": row}, "invoices": {"count": 1, "lines": 1}}
    failures, info = invariants.compare(before, after, ["016"])
    assert failures == [] and "purchase invoices created: 1 (one per purchase)" in info
    # the line lost a column it had (here the supplier), or changed one
    lost = {k: v for k, v in row.items() if k != "supplier_id"}
    assert invariants.compare(before, {**after, "purchases": {"MATERIAL:1": lost}}, ["016"])[0] == ["purchases.MATERIAL:1.supplier_id: the column is gone"]
    assert invariants.compare(before, {**after, "purchases": {"MATERIAL:1": {**row, "invoice_number": "PUR-000009"}}}, ["016"])[0] == [
        "purchases.MATERIAL:1.invoice_number: 'PUR-000001' -> 'PUR-000009'"
    ]
    # an allocation now paying another line, one that disappeared
    moved = {1: {"payment_id": 1, "purchase": "PRODUCT:3", "amount": 500}}
    assert invariants.compare(before, {**after, "allocations": moved}, ["016"])[0] == ["allocations.1.purchase: 'MATERIAL:1' -> 'PRODUCT:3'"]
    assert invariants.compare(before, {**after, "allocations": {}}, ["016"])[0] == ["allocations id 1 disappeared"]
    assert invariants.compare(before, {**after, "allocations": {1: {**moved[1], "purchase": "INVOICE:1"}}}, ["016"])[0][-1].startswith(
        "allocations.1: pays an invoice that does not have exactly one line"
    )
    # the invoice count, the payables per supplier, the summary and the counters must not move
    assert "purchase invoices: 2 invoices for 1 purchases (one each)" in invariants.compare(
        before, {**after, "invoices": {"count": 2, "lines": 1}}, ["016"])[0]
    owed = invariants.compare(before, {**after, "payables": _payables(by_supplier=[("2", 40)], payments=1, purchases_with_total=1)}, ["016"])[0]
    assert owed == ["payables.by_supplier: [] -> [('2', 40)]"]
    summary = {**after, "purchases_summary": {"material_purchases_total": 400, "material_purchases_count": 1}}
    assert invariants.compare(before, summary, ["016"])[0] == ["purchases summary.material_purchases_total: 500 -> 400"]
    assert invariants.compare(before, {**after, "counters": {"PUR": 2}}, ["016"])[0] == ["counters.PUR: 1 -> 2"]


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
