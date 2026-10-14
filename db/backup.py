"""Daily database backups: a consistent copy of the SQLite file made with SQLite's online backup API (never a file copy), verified, then rotated.
The backups folder sits next to the database file in use (`backups/`), so a scratch copy never writes into the real one. Backups are named `daily-YYYY-MM-DD-HHMMSS.db` (store-local time); rotation keeps the newest `DEFAULT_KEEP` of exactly those names and touches nothing else (migration backups `shop-*.db`, audit archives, `backup-status.json`, strangers).
A backup is written as `.partial`, reopened read-only and checked with PRAGMA integrity_check, and only then renamed and rotated; a failed run removes its partial file, deletes no older backup, records the failure in `backup-status.json` and raises `BackupError`. Nothing here writes to the database itself."""

import errno
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from db.connection import PROJECT_ROOT
from db.errors import BackupError, ErrorCode
from db.timeutil import now_local

# The error code the API answers with when a backup fails (BackupError carries it).
FAILURE_CODE = ErrorCode.BACKUP_FAILED
BACKUP_PREFIX = "daily-"
DEFAULT_KEEP = 60
STATUS_FILE = "backup-status.json"
LOCK_RETRIES = 3
LOCK_WAIT_SECONDS = 0.5
BUSY_TIMEOUT_SECONDS = 5

_NAME = re.compile(r"^daily-(\d{4}-\d{2}-\d{2})-(\d{6})(?:-(\d+))?\.db$")


def absolute_db_path(db_path: str | os.PathLike) -> Path:
    """The database file as init_db sees it: a relative path (the default data/shop.db) is relative to the project folder."""
    path = Path(db_path)
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def backups_dir_for(db_path: str | os.PathLike) -> Path:
    """The backups folder of a database file: `backups/` next to it."""
    return absolute_db_path(db_path).parent / "backups"


def _sort_key(name: str) -> tuple:
    match = _NAME.match(name)
    return (match.group(1), match.group(2), int(match.group(3) or 0)) if match else ("", "", 0)


def list_backups(backups_dir: str | os.PathLike) -> list[dict]:
    """Every `daily-*.db` in the folder, newest first: name, size, created_at (UTC, from the file's modification time)."""
    folder = Path(backups_dir)
    if not folder.is_dir():
        return []
    items = []
    for entry in folder.iterdir():
        if _NAME.match(entry.name) and entry.is_file():
            stat = entry.stat()
            created = datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            items.append({"name": entry.name, "size": stat.st_size, "created_at": created})
    return sorted(items, key=lambda item: _sort_key(item["name"]), reverse=True)


def has_backup_for(backups_dir: str | os.PathLike, day: str) -> bool:
    """A daily backup named for the store-local day `day` ("YYYY-MM-DD") exists."""
    return any(item["name"].startswith(f"{BACKUP_PREFIX}{day}-") for item in list_backups(backups_dir))


def read_status(backups_dir: str | os.PathLike) -> dict | None:
    """The outcome of the last backup attempt ({at, ok, name, reason, message}), or None."""
    try:
        return json.loads((Path(backups_dir) / STATUS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_status(folder: Path, ok: bool, name: str | None, reason: str | None, message: str | None) -> None:
    status = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "ok": ok,
        "name": name,
        "reason": reason,
        "message": message,
    }
    try:
        folder.mkdir(parents=True, exist_ok=True)
        temp = folder / (STATUS_FILE + ".tmp")
        temp.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, folder / STATUS_FILE)
    except OSError:
        pass  # the status is a convenience; a backup outcome never depends on it


def _reason(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, OSError) and exc.errno in (errno.ENOSPC, errno.EDQUOT):
        return "disk_full"
    if "full" in text:
        return "disk_full"
    if "locked" in text or "busy" in text:
        return "locked"
    return "unknown"


def _verify(path: Path) -> None:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        result = [row[0] for row in conn.execute("PRAGMA integrity_check")]
        if result != ["ok"]:
            raise BackupError(f"the new backup failed PRAGMA integrity_check: {result[:3]}", "integrity")
        conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"the new backup cannot be read: {exc}", "integrity") from None
    finally:
        conn.close()


def _rotate(folder: Path, keep: int) -> list[str]:
    deleted = []
    for item in list_backups(folder)[keep:]:
        try:
            (folder / item["name"]).unlink()
            deleted.append(item["name"])
        except FileNotFoundError:
            pass  # another instance rotated it first
        except OSError:
            pass  # an undeletable old file is not a failed backup
    return deleted


def _copy(source: Path, target: Path) -> None:
    last: BaseException | None = None
    for attempt in range(LOCK_RETRIES):
        src = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_SECONDS)
        dst = sqlite3.connect(target)
        started = time.monotonic()

        def give_up_when_locked(status, remaining, total):
            # sqlite3's backup() waits for a busy source forever; this bounds the wait.
            if status in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) and time.monotonic() - started > BUSY_TIMEOUT_SECONDS:
                raise sqlite3.OperationalError("database is locked")

        try:
            src.backup(dst, pages=-1, progress=give_up_when_locked, sleep=0.05)  # one step: one consistent snapshot even while the app writes
            return
        except sqlite3.OperationalError as exc:
            last = exc
            if _reason(exc) != "locked":
                raise
            time.sleep(LOCK_WAIT_SECONDS)
        finally:
            dst.close()
            src.close()
    raise last  # type: ignore[misc]


def make_backup(
    db_path: str | os.PathLike,
    backups_dir: str | os.PathLike | None = None,
    keep: int = DEFAULT_KEEP,
    now: datetime | None = None,
) -> dict:
    """Back the database up now. Returns {name, size, created_at, kept, deleted}; raises BackupError (nothing older is deleted)."""
    source = absolute_db_path(db_path)
    folder = Path(backups_dir) if backups_dir is not None else backups_dir_for(source)
    partial: Path | None = None
    try:
        if not source.is_file():
            raise BackupError(f"database file not found: {source}", "unknown")
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BackupError(f"cannot create the backups folder {folder}: {exc}", "folder") from None
        probe = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_SECONDS)
        try:
            stamp = now or now_local(probe)
        finally:
            probe.close()
        base = f"{BACKUP_PREFIX}{stamp:%Y-%m-%d-%H%M%S}"
        # a private partial name (process + thread), so two simultaneous backups never share a file
        partial = folder / f"{base}.{os.getpid()}-{threading.get_ident()}.partial"
        _copy(source, partial)
        _verify(partial)
        name = _publish(partial, folder, base)
        partial = None
        deleted = _rotate(folder, keep)
    except BackupError as exc:
        _cleanup(partial)
        _write_status(folder, False, None, exc.reason, str(exc))
        raise
    except (OSError, sqlite3.Error) as exc:
        _cleanup(partial)
        reason = _reason(exc)
        _write_status(folder, False, None, reason, str(exc))
        raise BackupError(f"backup failed: {exc}", reason) from None
    final = folder / name
    item = next(i for i in list_backups(folder) if i["name"] == name)
    _write_status(folder, True, name, None, None)
    return {**item, "path": str(final), "kept": len(list_backups(folder)), "deleted": deleted}


def _publish(partial: Path, folder: Path, base: str) -> str:
    """Give the verified partial its final name without ever overwriting another backup (-1, -2 … on a clash)."""
    suffix = 0
    while True:
        name = f"{base}.db" if suffix == 0 else f"{base}-{suffix}.db"
        final = folder / name
        try:
            os.link(partial, final)  # fails if the name is taken: the check and the claim are one step
        except FileExistsError:
            suffix += 1
            continue
        except OSError:
            if final.exists():  # a filesystem without hard links: fall back to check-then-rename
                suffix += 1
                continue
            os.replace(partial, final)
            return name
        partial.unlink()
        return name


def _cleanup(partial: Path | None) -> None:
    if partial is not None:
        try:
            partial.unlink()
        except OSError:
            pass


def backup_if_none_today(db_path: str | os.PathLike, backups_dir: str | os.PathLike | None = None, keep: int = DEFAULT_KEEP) -> dict | None:
    """Make a backup unless one named for today (store-local) exists. Returns the result, or None when skipped.
    Raises BackupError when the attempt fails; callers that must not stop (startup, the hourly check) catch it."""
    source = absolute_db_path(db_path)
    folder = Path(backups_dir) if backups_dir is not None else backups_dir_for(source)
    if source.is_file():
        probe = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_SECONDS)
        try:
            today = f"{now_local(probe):%Y-%m-%d}"
        finally:
            probe.close()
        if has_backup_for(folder, today):
            return None
    return make_backup(source, folder, keep)
