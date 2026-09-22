import contextlib
import hashlib
import itertools
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from db.errors import NotFoundError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"

SCHEMA_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _resolve_db_path(db_path: str) -> Path:
    path = Path(db_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _hash_migration_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_connection(db_path: str = "data/shop.db") -> sqlite3.Connection:
    path = _resolve_db_path(db_path)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_savepoint_counter = itertools.count()


@contextlib.contextmanager
def transaction(conn: sqlite3.Connection):
    """Manual transaction control for isolation_level=None connections.

    When no transaction is open, behaves like a normal BEGIN/COMMIT/ROLLBACK
    block. When called while a transaction is already open (i.e. this call is
    nested inside an outer `transaction(conn)`), it uses a SAVEPOINT instead,
    so a failure here only undoes this call's own work — even if the caller
    catches the exception and the outer transaction goes on to commit.
    """
    if conn.in_transaction:
        savepoint = f"sp_{next(_savepoint_counter)}"
        conn.execute(f"SAVEPOINT {savepoint}")
        try:
            yield
            conn.execute(f"RELEASE {savepoint}")
        except Exception:
            conn.execute(f"ROLLBACK TO {savepoint}")
            conn.execute(f"RELEASE {savepoint}")
            raise
        return

    conn.execute("BEGIN")
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _backup_db(path: Path) -> Path:
    """Copy *path* to a sibling backups/ directory before applying a migration.

    Never overwrites an existing backup file — appends a numeric suffix instead.
    """
    backups_dir = path.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backups_dir / f"shop-{stamp}.db"
    suffix = 1
    while backup_path.exists():
        backup_path = backups_dir / f"shop-{stamp}-{suffix}.db"
        suffix += 1
    shutil.copy2(path, backup_path)
    return backup_path


def _apply_migration(
    conn: sqlite3.Connection, filename: str, content: str, content_hash: str
) -> None:
    """Apply one migration file and record it, atomically.

    Everything (the migration's own DDL/DML plus the schema_migrations row) is
    wrapped in a single BEGIN...COMMIT inside one executescript() call, since
    executescript() implicitly commits any transaction that is already open
    before it runs — issuing our own `conn.execute("BEGIN")` first and then
    calling executescript() would silently commit that BEGIN before the
    migration's statements ever ran, defeating atomicity. executescript() has
    no parameter binding, so the schema_migrations values are inlined as
    escaped string literals.

    PRAGMA foreign_keys is a no-op while a transaction is open, so it must be
    toggled here, outside the BEGIN...COMMIT — not inside the migration file —
    to support migrations that rebuild a table per SQLite's documented
    12-step procedure.
    """
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        escaped_filename = filename.replace("'", "''")
        insert_stmt = (
            "INSERT INTO schema_migrations (filename, content_hash) "
            f"VALUES ('{escaped_filename}', '{content_hash}');"
        )
        script = f"BEGIN;\n{content}\n{insert_stmt}\nCOMMIT;\n"
        try:
            conn.executescript(script)
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def init_db(
    db_path: str = "data/shop.db",
    migrations_dir: str | Path | None = None,
) -> None:
    migrations_path = Path(migrations_dir) if migrations_dir is not None else MIGRATIONS_DIR
    path = _resolve_db_path(db_path)

    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_MIGRATIONS_TABLE)

        applied_rows = conn.execute(
            "SELECT filename, content_hash FROM schema_migrations"
        ).fetchall()
        applied = {row["filename"]: row["content_hash"] for row in applied_rows}
        already_migrated = len(applied) > 0

        to_apply: list[tuple[str, str, str]] = []
        for migration_file in sorted(migrations_path.glob("*.sql")):
            filename = migration_file.name
            content = migration_file.read_text(encoding="utf-8")
            content_hash = _hash_migration_content(content)

            if filename in applied:
                if applied[filename] != content_hash:
                    raise RuntimeError(
                        f"Migration file migrations/{filename} has been modified "
                        f"after being applied. Changes to already-applied migrations "
                        f"must go in a new numbered file instead "
                        f"(e.g. 002_..., 003_...)."
                    )
                continue

            to_apply.append((filename, content, content_hash))

        if to_apply and already_migrated:
            _backup_db(path)

        for filename, content, content_hash in to_apply:
            _apply_migration(conn, filename, content, content_hash)

        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                f"Foreign key violations found after applying migrations: "
                f"{[dict(row) for row in violations]}"
            )
    finally:
        conn.close()


def next_counter(conn: sqlite3.Connection, name: str) -> int:
    """Atomically increment and return the named counter (invoice numbering)."""
    with transaction(conn):
        conn.execute("UPDATE counters SET value = value + 1 WHERE name = ?", (name,))
        row = conn.execute(
            "SELECT value FROM counters WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Counter '{name}' does not exist")
        value = row["value"]
    return value
