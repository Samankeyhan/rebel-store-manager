"""The service lifespan shared by `api.main:app` and the one-process `api.serve:app`: bring the database up to date, make
today's backup, keep checking hourly while running, and stop the checker on shutdown.
A backup problem never stops the app: it is logged (and recorded in the backups folder's status file) and the app starts."""

import logging
import os
import sqlite3
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.deps import db_path
from api.logsetup import remove_logging, setup_logging
from db.backup import absolute_db_path, backup_if_none_today
from db.connection import init_db

log = logging.getLogger("rebel.backup")
app_log = logging.getLogger("rebel.app")

CHECK_INTERVAL_SECONDS = 3600


def check_interval() -> float:
    """Seconds between the hourly backup checks ($REBEL_BACKUP_CHECK_SECONDS overrides it, for tests)."""
    try:
        return float(os.environ.get("REBEL_BACKUP_CHECK_SECONDS", CHECK_INTERVAL_SECONDS))
    except ValueError:
        return CHECK_INTERVAL_SECONDS


def backup_once_a_day(path: str, when: str) -> bool:
    """Make today's backup if there is none. Never raises: the result is logged. True when a backup was made."""
    try:
        result = backup_if_none_today(path)
    except Exception as exc:  # BackupError, or anything unexpected: the app keeps running either way
        log.error("daily backup failed (%s): %s", when, getattr(exc, "reason", type(exc).__name__))
        return False
    if result is None:
        return False
    log.info("daily backup made (%s): %s, %d bytes, %d kept", when, result["name"], result["size"], result["kept"])
    return True


class BackupChecker(threading.Thread):
    """Wakes up every `interval` seconds and makes today's backup if none exists. A daemon thread whose every step
    is wrapped: it cannot block or crash the app."""

    def __init__(self, path: str, interval: float):
        super().__init__(name="backup-checker", daemon=True)
        self._path = path
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.wait(self._interval):
            try:
                backup_once_a_day(self._path, "hourly check")
            except BaseException:  # pragma: no cover - backup_once_a_day already catches everything it can
                log.exception("backup check crashed")

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=10)


def _applied_migrations(path: str) -> list[str]:
    """The migration files recorded in the database (read-only; [] when the file or table is missing)."""
    try:
        conn = sqlite3.connect(f"{absolute_db_path(path).as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        return sorted(row[0] for row in conn.execute("SELECT filename FROM schema_migrations"))
    except sqlite3.Error:
        return []
    finally:
        conn.close()


@asynccontextmanager
async def service_lifespan(app: FastAPI):
    """Bring the database up to date before serving any request.

    Pending migrations are applied (init_db backs the file up first). If that fails — a broken migration, or an
    applied file whose content changed — the server refuses to start rather than run against a half-migrated
    schema and 500 on every request. Then today's backup is made (best effort) and the hourly checker starts.
    """
    path = db_path()
    handler = setup_logging(path)
    app_log.info("starting; database file: %s", absolute_db_path(path))
    before = set(_applied_migrations(path))
    try:
        init_db(path)
    except Exception as exc:
        app_log.error("migrations could not be applied (%s); refusing to start", type(exc).__name__)
        remove_logging(handler)
        raise RuntimeError(
            f"Could not apply database migrations to {path}; refusing to start: {exc}"
        ) from exc
    after = _applied_migrations(path)
    new = [name for name in after if name not in before]
    app_log.info("schema: %s; migrations applied now: %s", after[-1] if after else "none", ", ".join(new) if new else "none")
    backup_once_a_day(path, "startup")
    checker = BackupChecker(path, check_interval())
    checker.start()
    try:
        yield
    finally:
        checker.stop()
        app_log.info("stopped")
        remove_logging(handler)
