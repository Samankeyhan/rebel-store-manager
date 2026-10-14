import os
import tempfile
from pathlib import Path

import pytest

from db.connection import get_connection, init_db


REAL_DATA = Path(__file__).resolve().parent.parent / "data"


def _real_data_snapshot() -> dict:
    """What the real data folder looks like (read-only): the shop database and the listings of backups/ and logs/."""
    snapshot: dict = {}
    shop = REAL_DATA / "shop.db"
    snapshot["shop.db"] = (shop.stat().st_size, shop.stat().st_mtime_ns) if shop.is_file() else None
    for name in ("backups", "logs"):
        folder = REAL_DATA / name
        snapshot[name] = (
            sorted((f.name, f.stat().st_size, f.stat().st_mtime_ns) for f in folder.iterdir()) if folder.is_dir() else None
        )
    return snapshot


@pytest.fixture(scope="session", autouse=True)
def _real_data_folders_are_never_written():
    """No test may write the real shop database, data/backups or data/logs: compare before and after the whole run."""
    before = _real_data_snapshot()
    yield
    assert _real_data_snapshot() == before, "a test wrote into the real data folder (shop.db, backups/ or logs/)"


@pytest.fixture(autouse=True)
def _api_db_in_tmp(monkeypatch, tmp_path):
    """The API's startup runs init_db on $REBEL_DB (default data/shop.db).
    Point it at a throwaway file for every test, so a TestClient used as a
    context manager can never migrate the real database."""
    monkeypatch.setenv("REBEL_DB", str(tmp_path / "rebel_db_guard.db"))


@pytest.fixture
def test_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        init_db(db_path)
        conn = get_connection(db_path)
        yield conn
        conn.close()
    finally:
        os.unlink(db_path)
