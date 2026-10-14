"""The startup backup and the hourly check: they make today's backup, never block or crash the app, and stop with it."""

import threading
import time

import pytest
from fastapi.testclient import TestClient

import api.startup as startup
from api.main import app
from db.backup import backups_dir_for, list_backups, read_status
from db.errors import BackupError


def current_db(tmp_path):
    return tmp_path / "rebel_db_guard.db"  # what tests/conftest.py points REBEL_DB at


def wait_for(condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_startup_makes_todays_backup_next_to_the_database_and_only_one(tmp_path):
    folder = backups_dir_for(current_db(tmp_path))
    assert not folder.exists()
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert len(list_backups(folder)) == 1
    with TestClient(app) as client:  # a second start the same day makes no second backup
        assert client.get("/health").status_code == 200
    assert len(list_backups(folder)) == 1
    assert read_status(folder)["ok"] is True


def test_a_failing_backup_never_stops_startup(tmp_path, monkeypatch, caplog):
    def broken(path, *args, **kwargs):
        raise BackupError("disk is full", "disk_full")

    monkeypatch.setattr(startup, "backup_if_none_today", broken)
    with caplog.at_level("ERROR", logger="rebel.backup"):
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
    assert any("daily backup failed (startup): disk_full" in r.getMessage() for r in caplog.records)


def test_an_unexpected_crash_in_the_backup_code_never_stops_startup(tmp_path, monkeypatch):
    def crash(path, *args, **kwargs):
        raise RuntimeError("anything at all")

    monkeypatch.setattr(startup, "backup_if_none_today", crash)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_the_hourly_check_makes_one_when_todays_is_missing_and_survives_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("REBEL_BACKUP_CHECK_SECONDS", "0.05")
    folder = backups_dir_for(current_db(tmp_path))
    with TestClient(app) as client:
        (first,) = list_backups(folder)
        (folder / first["name"]).unlink()  # today's backup disappears while the app runs
        assert wait_for(lambda: len(list_backups(folder)) == 1), "the hourly check did not make a new backup"

        real = startup.backup_if_none_today
        calls = []

        def flaky(path, *args, **kwargs):
            calls.append(1)
            raise RuntimeError("the checker must survive this")

        monkeypatch.setattr(startup, "backup_if_none_today", flaky)
        assert wait_for(lambda: len(calls) >= 3)  # it keeps trying, every tick
        assert client.get("/health").status_code == 200
        monkeypatch.setattr(startup, "backup_if_none_today", real)


def test_the_checker_stops_with_the_app(tmp_path, monkeypatch):
    monkeypatch.setenv("REBEL_BACKUP_CHECK_SECONDS", "0.05")
    with TestClient(app) as client:
        assert any(t.name == "backup-checker" for t in threading.enumerate())
        assert client.get("/health").status_code == 200
    assert wait_for(lambda: not any(t.name == "backup-checker" for t in threading.enumerate()))


def test_the_check_interval_reads_the_environment(monkeypatch):
    assert startup.check_interval() == 3600
    monkeypatch.setenv("REBEL_BACKUP_CHECK_SECONDS", "2.5")
    assert startup.check_interval() == 2.5
    monkeypatch.setenv("REBEL_BACKUP_CHECK_SECONDS", "soon")
    assert startup.check_interval() == 3600


def test_the_real_data_folder_is_guarded_by_the_session_fixture():
    """conftest's session fixture compares data/shop.db, data/backups and data/logs before and after the run."""
    from tests.conftest import _real_data_snapshot

    snapshot = _real_data_snapshot()
    assert set(snapshot) == {"shop.db", "backups", "logs"}
