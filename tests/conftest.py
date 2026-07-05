import os
import tempfile

import pytest

from db.connection import get_connection, init_db


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
