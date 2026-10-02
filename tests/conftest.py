import os
import tempfile

import pytest

from db.connection import get_connection, init_db


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
