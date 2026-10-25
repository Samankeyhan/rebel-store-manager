"""Tests that use a copy of this laptop's data/shop.db (the owner's test database). Whatever branch the app was last run
on, that file may be at any migration, so a test decides "upgrade or skip" from the database's schema_migrations rows
only — never by reading a table's columns first. The file is only ever read through SQLite immutable mode, and the
copy lives in the test's own temporary folder."""

import re
import sqlite3
from pathlib import Path

import pytest

from db.connection import MIGRATIONS_DIR

LAPTOP_DB = Path(__file__).resolve().parent.parent / "data" / "shop.db"

needs_laptop_db = pytest.mark.skipif(not LAPTOP_DB.is_file(), reason="this laptop's data/shop.db is not here")


def _open_readonly() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{LAPTOP_DB.as_posix()}?mode=ro&immutable=1", uri=True)


def applied_migrations() -> set[str]:
    """The migration files data/shop.db has applied (its schema_migrations rows), read-only."""
    conn = _open_readonly()
    try:
        return {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}
    finally:
        conn.close()


def _number(filename: str) -> int:
    match = re.match(r"(\d+)_", filename)
    return int(match.group(1)) if match else -1


def skip_unless_before(migration: str) -> None:
    """Skip the calling test, with the reason, unless data/shop.db is still before `migration` (its file name): once the
    database is at that migration or past it, there is nothing to upgrade."""
    applied = applied_migrations()
    latest = max(applied, key=_number, default="none")
    if migration in applied or _number(latest) >= _number(migration):
        pytest.skip(
            f"this laptop's data/shop.db is already at {latest}, at or past {migration}: no upgrade to test"
        )


def pending_migrations() -> list[str]:
    """The migration files of this checkout that data/shop.db has not applied yet."""
    applied = applied_migrations()
    return sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql") if p.name not in applied)


def copy_laptop_db(folder: Path) -> str:
    """A copy of data/shop.db in `folder`, made with the backup API from an immutable read (the file itself is never
    opened for writing). Returns the copy's path."""
    folder.mkdir(parents=True, exist_ok=True)
    copy = folder / "shop.db"
    source = _open_readonly()
    target = sqlite3.connect(copy)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return str(copy)
