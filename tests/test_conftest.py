def test_test_db_fixture(test_db):
    rows = test_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    assert rows
