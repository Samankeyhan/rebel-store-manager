import contextlib
import hashlib
import itertools
import sqlite3
from pathlib import Path

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


def init_db(db_path: str = "data/shop.db") -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_MIGRATIONS_TABLE)

        applied_rows = conn.execute(
            "SELECT filename, content_hash FROM schema_migrations"
        ).fetchall()
        applied = {row["filename"]: row["content_hash"] for row in applied_rows}

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for migration_file in migration_files:
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

            conn.executescript(content)
            conn.execute(
                "INSERT INTO schema_migrations (filename, content_hash) VALUES (?, ?)",
                (filename, content_hash),
            )

        conn.commit()
    finally:
        conn.close()
