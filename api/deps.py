"""`db_path()` reads `REBEL_DB` (default `data/shop.db`); `get_db()` opens one connection per request and closes it after."""

import os
from typing import Iterator

import sqlite3

from db.connection import get_connection


def db_path() -> str:
    """The database the API serves: $REBEL_DB, default data/shop.db."""
    return os.environ.get("REBEL_DB", "data/shop.db")


def get_db() -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path())
    try:
        yield conn
    finally:
        conn.close()
