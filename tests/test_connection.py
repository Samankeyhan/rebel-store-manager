import os
import tempfile

import pytest

from db.connection import get_connection, init_db


def test_init_db_raises_on_modified_migration_hash():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        init_db(db_path)

        conn = get_connection(db_path)
        conn.execute(
            "UPDATE schema_migrations SET content_hash = ? WHERE filename = ?",
            ("deadbeef", "001_initial_schema.sql"),
        )
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError, match="has been modified after being applied"):
            init_db(db_path)
    finally:
        os.unlink(db_path)
