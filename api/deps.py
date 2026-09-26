import os
from typing import Iterator

import sqlite3

from db.connection import get_connection


def get_db() -> Iterator[sqlite3.Connection]:
    conn = get_connection(os.environ.get("REBEL_DB", "data/shop.db"))
    try:
        yield conn
    finally:
        conn.close()
