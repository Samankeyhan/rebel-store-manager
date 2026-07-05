import hashlib
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
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
