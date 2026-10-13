"""Opening the database read-only. `mode=ro` in the SQLite URI (a missing file is an error, never created) plus
`PRAGMA query_only = ON`: any write raises. Nothing here (or anywhere in tools/) calls init_db, get_connection,
migrations, the name_key backfill or anything else that writes.
The shop database uses the default rollback journal (file-format version 1, not WAL), so a read-only open creates no
side files. The connection is in autocommit mode, so it holds a read lock only while a statement runs: the app can
keep writing, but a write that lands mid-run can show up as a false mismatch; run it when the app is idle (evening)."""

import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from tools.integrity_check.report import CannotRun

BUSY_TIMEOUT_SECONDS = 5


def open_readonly(path: str | os.PathLike) -> sqlite3.Connection:
    target = Path(path)
    if not target.is_file():
        raise CannotRun(f"database file not found: {target}")
    uri = target.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=BUSY_TIMEOUT_SECONDS)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
    except sqlite3.DatabaseError as exc:
        raise CannotRun(f"cannot open {target} read-only: {exc}") from None
    return conn


def fingerprint(path: str | os.PathLike) -> dict:
    """Size, modification time and the first 16 hex digits of the SHA-256 of the file (read only)."""
    target = Path(path)
    digest = hashlib.sha256()
    with open(target, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    stat = target.stat()
    return {
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "sha256": digest.hexdigest()[:16],
    }


def schema_version(conn: sqlite3.Connection) -> tuple[int, str]:
    """(number, file name) of the highest applied migration; (0, "none") for a database with no migrations."""
    try:
        names = [row[0] for row in conn.execute("SELECT filename FROM schema_migrations")]
    except sqlite3.DatabaseError:
        raise CannotRun("not a Rebel Store Manager database (no schema_migrations table)") from None
    if not names:
        return 0, "none"
    latest = max(names)
    try:
        return int(latest.split("_", 1)[0]), latest
    except ValueError:
        raise CannotRun(f"unreadable migration name in schema_migrations: {latest!r}") from None
