"""Daily backups (db/backup.py): consistent, verified, rotated, and safe to fail. Every test works in tmp_path:
nothing here may touch the real data/backups (tests/conftest.py guards that)."""

import errno
import hashlib
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import db.backup as backup
from db.backup import (
    DEFAULT_KEEP, STATUS_FILE, backup_if_none_today, backups_dir_for, has_backup_for, list_backups, make_backup, read_status,
)
from db.connection import get_connection, init_db
from db.errors import BackupError, ErrorCode

TEHRAN = ZoneInfo("Asia/Tehran")


@pytest.fixture
def shop(tmp_path):
    folder = tmp_path / "shop"
    folder.mkdir()
    path = folder / "shop.db"
    init_db(str(path))
    conn = get_connection(str(path))
    conn.execute("INSERT INTO suppliers (name) VALUES ('Fictional Supply')")
    conn.close()
    return path


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def when(day=1, hour=8, minute=30, second=0):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=TEHRAN)


def fake_backups(folder: Path, count: int) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    names = [f"daily-2026-08-{n // 24 + 1:02d}-{n % 24:02d}0000.db" for n in range(count)]
    for name in names:
        (folder / name).write_bytes(b"old backup")
    return names


# --------------------------------------------------------------------- a backup


def test_the_default_keep_is_sixty_and_the_folder_sits_next_to_the_database(shop):
    assert DEFAULT_KEEP == 60
    assert backups_dir_for(shop) == shop.parent / "backups"


def test_a_backup_is_a_valid_complete_copy_named_with_the_store_local_time(shop):
    before = sha(shop)
    result = make_backup(shop, now=when(day=5, hour=7, minute=4, second=3))
    assert result["name"] == "daily-2026-10-05-070403.db"
    path = shop.parent / "backups" / result["name"]
    assert path.is_file() and result["size"] == path.stat().st_size and result["kept"] == 1
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        assert [r[0] for r in conn.execute("PRAGMA integrity_check")] == ["ok"]
        assert conn.execute("SELECT name FROM suppliers").fetchone()[0] == "Fictional Supply"
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] >= 13
    finally:
        conn.close()
    assert sha(shop) == before  # the source is only read
    assert not list((shop.parent / "backups").glob("*.partial"))
    assert read_status(shop.parent / "backups")["ok"] is True


def test_without_a_given_time_the_name_follows_the_pattern(shop):
    result = make_backup(shop)
    assert len(result["name"]) == len("daily-2026-10-05-070403.db") and result["name"].startswith("daily-20")


def test_two_backups_in_the_same_second_get_distinct_names(shop):
    names = {make_backup(shop, now=when())["name"] for _ in range(3)}
    assert names == {"daily-2026-10-01-083000.db", "daily-2026-10-01-083000-1.db", "daily-2026-10-01-083000-2.db"}


def test_a_missing_backups_folder_is_created(shop, tmp_path):
    target = tmp_path / "deep" / "er" / "backups"
    make_backup(shop, target)
    assert len(list_backups(target)) == 1


# --------------------------------------------------------------------- rotation


def test_rotation_keeps_exactly_the_newest_sixty_and_touches_nothing_else(shop):
    folder = shop.parent / "backups"
    old = fake_backups(folder, 65)
    others = {
        "shop-20261001-101010.db": b"migration backup",
        "audit-archive-20261001-101010.jsonl": b"{}",
        "daily-2026-08-01-000000.db.partial": b"somebody else's partial",
        "daily-notes.txt": b"stranger",
        "readme.txt": b"stranger",
    }
    for name, data in others.items():
        (folder / name).write_bytes(data)
    result = make_backup(shop, now=when(day=9))
    names = [i["name"] for i in list_backups(folder)]
    assert len(names) == 60 and names[0] == result["name"]
    assert set(result["deleted"]) == set(old[:6])  # of the 66 the 6 oldest go
    for name, data in others.items():
        assert (folder / name).read_bytes() == data
    assert (folder / STATUS_FILE).is_file()


def test_rotation_goes_by_the_timestamp_in_the_name_not_the_file_time(shop):
    folder = shop.parent / "backups"
    fake_backups(folder, 5)
    soon = time.time() + 1000
    os.utime(folder / "daily-2026-08-01-000000.db", (soon, soon))  # the oldest name, touched last
    make_backup(shop, now=when(day=2), keep=3)
    kept = {i["name"] for i in list_backups(folder)}
    assert len(kept) == 3 and "daily-2026-10-02-083000.db" in kept and "daily-2026-08-01-040000.db" in kept
    assert "daily-2026-08-01-000000.db" not in kept


def test_a_keep_larger_than_the_number_of_files_deletes_nothing(shop):
    fake_backups(shop.parent / "backups", 3)
    assert make_backup(shop, now=when())["deleted"] == []


# ---------------------------------------------------------------------- failure


def _assert_failed_cleanly(folder, old, reason):
    assert sorted(i["name"] for i in list_backups(folder)) == sorted(old)  # no older backup deleted, no new one
    assert not list(folder.glob("*.partial"))
    status = read_status(folder)
    assert status["ok"] is False and status["reason"] == reason and status["message"]


def test_a_failed_integrity_check_removes_the_partial_and_deletes_no_older_backup(shop, monkeypatch):
    folder = shop.parent / "backups"
    old = fake_backups(folder, 60)

    def refuse(path):
        raise BackupError("integrity_check said no", "integrity")

    monkeypatch.setattr(backup, "_verify", refuse)
    with pytest.raises(BackupError) as exc_info:
        make_backup(shop, now=when(day=9))
    assert exc_info.value.reason == "integrity" and exc_info.value.code == ErrorCode.BACKUP_FAILED
    assert exc_info.value.details == {"reason": "integrity"}
    _assert_failed_cleanly(folder, old, "integrity")


@pytest.mark.parametrize("error, reason", [
    (sqlite3.OperationalError("database or disk is full"), "disk_full"),
    (OSError(errno.ENOSPC, "No space left on device"), "disk_full"),
    (sqlite3.OperationalError("disk I/O error"), "unknown"),
])
def test_a_failure_while_copying_is_reported_with_its_reason(shop, monkeypatch, error, reason):
    folder = shop.parent / "backups"
    old = fake_backups(folder, 60)

    def broken(source, target):
        target.write_bytes(b"half")
        raise error

    monkeypatch.setattr(backup, "_copy", broken)
    with pytest.raises(BackupError) as exc_info:
        make_backup(shop, now=when(day=9))
    assert exc_info.value.reason == reason
    _assert_failed_cleanly(folder, old, reason)


def test_a_backups_folder_that_cannot_be_created_is_the_folder_reason(shop, tmp_path):
    blocker = tmp_path / "backups"
    blocker.write_text("a file where the folder should be")
    with pytest.raises(BackupError) as exc_info:
        make_backup(shop, blocker)
    assert exc_info.value.reason == "folder"


def test_a_missing_database_is_a_failure_not_a_crash(tmp_path):
    with pytest.raises(BackupError):
        make_backup(tmp_path / "nothing.db")


def test_a_corrupt_new_file_is_caught_by_the_real_verification(shop, monkeypatch):
    folder = shop.parent / "backups"
    old = fake_backups(folder, 2)
    real_copy = backup._copy

    def corrupting(source, target):
        real_copy(source, target)
        data = bytearray(target.read_bytes())
        data[:100] = bytes(100)  # wipes the SQLite header
        target.write_bytes(bytes(data))

    monkeypatch.setattr(backup, "_copy", corrupting)
    with pytest.raises(BackupError) as exc_info:
        make_backup(shop, now=when())
    assert exc_info.value.reason == "integrity"
    _assert_failed_cleanly(folder, old, "integrity")


def test_a_locked_source_is_retried_then_reported(shop, monkeypatch):
    monkeypatch.setattr(backup, "BUSY_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(backup, "LOCK_WAIT_SECONDS", 0.01)
    blocker = sqlite3.connect(shop, isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(BackupError) as exc_info:
            make_backup(shop, now=when())
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
    assert exc_info.value.reason == "locked"
    assert not list((shop.parent / "backups").glob("*.partial"))


# ---------------------------------------------------------------- concurrency


def test_backups_taken_while_another_connection_writes_are_consistent(shop):
    setup = get_connection(str(shop))
    setup.execute("CREATE TABLE pair_a (n INTEGER)")
    setup.execute("CREATE TABLE pair_b (n INTEGER)")
    setup.close()
    stop = threading.Event()
    errors: list[BaseException] = []

    def writer():
        n = 0
        w = get_connection(str(shop))
        try:
            while not stop.is_set():
                n += 1
                try:
                    w.execute("BEGIN")
                    w.execute("INSERT INTO pair_a VALUES (?)", (n,))
                    w.execute("INSERT INTO pair_b VALUES (?)", (n,))
                    w.execute("COMMIT")
                except sqlite3.OperationalError:
                    if w.in_transaction:
                        w.execute("ROLLBACK")
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)
        finally:
            w.close()

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        results = [make_backup(shop, now=when(day=1 + i)) for i in range(5)]
    finally:
        stop.set()
        thread.join()
    assert not errors
    for result in results:
        copy = sqlite3.connect(f"{Path(result['path']).as_uri()}?mode=ro", uri=True)
        try:
            assert [r[0] for r in copy.execute("PRAGMA integrity_check")] == ["ok"]
            a = copy.execute("SELECT COUNT(*), COALESCE(SUM(n), 0) FROM pair_a").fetchone()
            b = copy.execute("SELECT COUNT(*), COALESCE(SUM(n), 0) FROM pair_b").fetchone()
            assert a == b  # both inserts of a transaction, or neither
        finally:
            copy.close()


def test_two_backups_started_together_both_succeed_and_are_distinct(shop):
    results, errors = [], []

    def run():
        try:
            results.append(make_backup(shop, now=when()))
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len({r["name"] for r in results}) == 2
    assert len(list_backups(shop.parent / "backups")) == 2


# ---------------------------------------------------------------- today check


def test_backup_if_none_today_makes_one_then_skips(shop):
    first = backup_if_none_today(shop)
    assert first is not None
    assert backup_if_none_today(shop) is None
    folder = shop.parent / "backups"
    assert len(list_backups(folder)) == 1
    today = first["name"][len("daily-"):len("daily-") + 10]
    assert has_backup_for(folder, today) and not has_backup_for(folder, "1999-01-01")


def test_backup_if_none_today_ignores_an_old_days_file(shop):
    fake_backups(shop.parent / "backups", 2)  # August files
    assert backup_if_none_today(shop) is not None


def test_backup_if_none_today_raises_when_the_attempt_fails(shop, monkeypatch):
    def full(source, target):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(backup, "_copy", full)
    with pytest.raises(BackupError):
        backup_if_none_today(shop)


# ------------------------------------------------------------------- listing


def test_listing_an_absent_folder_and_a_bad_status_file(tmp_path):
    assert list_backups(tmp_path / "none") == []
    assert read_status(tmp_path / "none") is None
    (tmp_path / STATUS_FILE).write_text("{not json")
    assert read_status(tmp_path) is None
