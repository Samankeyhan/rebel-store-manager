"""File helpers: sha256 of a file, and a consistent SQLite copy (backup API, verified) used for the rehearsal and the failed-update copy."""

import hashlib
import sqlite3
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_copy(source: Path, target: Path) -> None:
    """Copy a database with SQLite's backup API (never a file copy) and check the copy with PRAGMA integrity_check.
    Raises OSError / sqlite3.Error; the partial target is removed on failure."""
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst, pages=-1)
    except (OSError, sqlite3.Error):
        dst.close()
        src.close()
        target.unlink(missing_ok=True)
        raise
    dst.close()
    src.close()
    check = sqlite3.connect(f"{target.resolve().as_uri()}?mode=ro", uri=True)
    try:
        result = [row[0] for row in check.execute("PRAGMA integrity_check")]
    finally:
        check.close()
    if result != ["ok"]:
        target.unlink(missing_ok=True)
        raise sqlite3.DatabaseError(f"the copy failed PRAGMA integrity_check: {result[:3]}")
