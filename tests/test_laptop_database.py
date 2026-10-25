"""Always run (when this laptop's data/shop.db is here), whatever migration that database is at: a copy goes through
init_db, the foreign-key check and the integrity check, and nothing in it changes — every figure the rehearsal compares
(tools/update_app/invariants.py), and, when no migration is pending, every row of every table and the user_version.
data/shop.db itself is only read (immutable mode); the copy is in a temporary folder."""

import shutil
import sqlite3

import pytest

import tests.laptop_db as laptop_db
from db.connection import MIGRATIONS_DIR, get_connection, init_db
from tests.laptop_db import copy_laptop_db, needs_laptop_db, pending_migrations, skip_unless_before
from tools.integrity_check.__main__ import main as integrity_main
from tools.update_app import invariants


def _every_row(path: str) -> dict:
    conn = sqlite3.connect(path)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        rows = {table: conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall() for table in tables}
        rows["user_version"] = conn.execute("PRAGMA user_version").fetchone()[0]
        return rows
    finally:
        conn.close()


@needs_laptop_db
def test_a_copy_of_the_laptop_database_survives_init_db(tmp_path):
    pending = pending_migrations()
    path = copy_laptop_db(tmp_path / "laptop")
    rows_before = _every_row(path)
    figures_before = invariants.collect(path)

    init_db(path)

    conn = get_connection(path)
    try:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()
    assert integrity_main(["--db", path]) == 0
    failures, _ = invariants.compare(figures_before, invariants.collect(path), pending)
    assert failures == []
    if not pending:
        assert _every_row(path) == rows_before  # nothing to migrate: init_db wrote nothing at all


@pytest.fixture
def laptop_at_015(tmp_path, monkeypatch):
    """data/shop.db stood in for by a fresh database at migration 015 (the real file is not touched)."""
    old = tmp_path / "to_015"
    old.mkdir()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name[:3] <= "015":
            shutil.copy(path, old / path.name)
    db_path = tmp_path / "stand-in" / "shop.db"
    db_path.parent.mkdir()
    init_db(str(db_path), migrations_dir=old)
    monkeypatch.setattr(laptop_db, "LAPTOP_DB", db_path)
    return db_path


def test_upgrade_or_skip_is_decided_from_schema_migrations_alone(laptop_at_015):
    skip_unless_before("016_purchase_invoices.sql")  # still before 016: the upgrade test runs
    for done in ("015_supplier_payables_purchase_status.sql", "014_order_void.sql", "001_initial_schema.sql"):
        with pytest.raises(pytest.skip.Exception, match="already at 015_supplier_payables_purchase_status.sql"):
            skip_unless_before(done)
    assert pending_migrations() == sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql") if p.name[:3] > "015")


def test_the_always_run_check_also_passes_on_a_database_with_a_pending_migration(laptop_at_015, tmp_path):
    test_a_copy_of_the_laptop_database_survives_init_db(tmp_path)  # 016 is pending: the figures must not move
    copy = sqlite3.connect(tmp_path / "laptop" / "shop.db")
    try:
        assert "016_purchase_invoices.sql" in {r[0] for r in copy.execute("SELECT filename FROM schema_migrations")}
    finally:
        copy.close()
    original = sqlite3.connect(laptop_at_015)
    try:  # the stand-in itself was only read
        assert "016_purchase_invoices.sql" not in {r[0] for r in original.execute("SELECT filename FROM schema_migrations")}
    finally:
        original.close()
