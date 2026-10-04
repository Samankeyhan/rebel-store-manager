import sqlite3
from pathlib import Path

import pytest

from db.connection import MIGRATIONS_DIR, get_connection, init_db

BEFORE_008 = tuple(
    name for name in sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql")) if name < "008"
)

NEW_ORDER_COLUMNS = {
    "payment_method_id",
    "payment_reference",
    "paid_date",
    "expected_settlement_date",
    "paid_jalali_year",
    "paid_jalali_month",
    "settlement_id",
}

_INSERT_METHOD = (
    "INSERT INTO payment_methods (name, settlement_rule, settlement_days) VALUES (?, ?, ?)"
)
_INSERT_SETTLEMENT = (
    "INSERT INTO settlements "
    "(payment_method_id, settled_date, jalali_year, jalali_month, expected_amount, amount_received) "
    "VALUES (?, '2026-10-01', ?, ?, 1000, 1000)"
)


def _migrations_dir(tmp_path: Path, name: str, filenames) -> Path:
    dest = tmp_path / name
    dest.mkdir()
    for filename in filenames:
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        (dest / filename).write_text(content, encoding="utf-8")
    return dest


def _method(conn, rule="DAY_OF_NEXT_MONTH", days=7, name="Gateway"):
    return conn.execute(_INSERT_METHOD, (name, rule, days)).lastrowid


def test_008_adds_columns_and_touches_no_existing_row(tmp_path):
    assert BEFORE_008[-1] == "007_display_currency.sql"
    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "at_007", BEFORE_008)))

    conn = get_connection(str(db_path))
    try:
        conn.execute(
            "INSERT INTO orders (invoice_number, order_date, status, channel, customer_name, "
            "shipping_charge, transaction_fee) "
            "VALUES ('INV-000001', '2026-09-01 08:00:00', 'COMPLETED', 'INSTAGRAM', 'Test Buyer', 180000, 2500)"
        )
        conn.execute(
            "INSERT INTO orders (invoice_number, order_date, status, channel) "
            "VALUES ('INV-000002', '2026-09-02 08:00:00', 'REFUNDED', 'WEBSITE')"
        )
        conn.commit()
        orders_before = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY id")]
        channels_before = [dict(r) for r in conn.execute("SELECT * FROM channel_settings ORDER BY channel")]
        settings_before = [dict(r) for r in conn.execute("SELECT * FROM settings ORDER BY key")]
    finally:
        conn.close()

    init_db(str(db_path))

    conn = get_connection(str(db_path))
    try:
        orders_after = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY id")]
        channels_after = [dict(r) for r in conn.execute("SELECT * FROM channel_settings ORDER BY channel")]
        settings_after = [dict(r) for r in conn.execute("SELECT * FROM settings ORDER BY key")]
        applied = [r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")]
        method_count = conn.execute("SELECT COUNT(*) FROM payment_methods").fetchone()[0]
        settlement_count = conn.execute("SELECT COUNT(*) FROM settlements").fetchone()[0]
    finally:
        conn.close()

    assert "008_payment_methods_settlements.sql" in applied
    # Old columns byte-identical; every new column NULL (no backfill).
    for before, after in zip(orders_before, orders_after, strict=True):
        assert set(after) - set(before) == NEW_ORDER_COLUMNS
        assert {k: after[k] for k in before} == before
        assert all(after[k] is None for k in NEW_ORDER_COLUMNS)
    for before, after in zip(channels_before, channels_after, strict=True):
        assert set(after) - set(before) == {"default_payment_method_id"}
        assert {k: after[k] for k in before} == before
        assert after["default_payment_method_id"] is None
    assert settings_after == settings_before
    # Rates and rules are owner data: nothing is seeded.
    assert method_count == 0
    assert settlement_count == 0


def test_008_payment_method_defaults_including_updated_at(test_db):
    columns = {r["name"]: r for r in test_db.execute("PRAGMA table_info(payment_methods)")}
    assert columns["updated_at"]["notnull"] == 1
    assert columns["updated_at"]["dflt_value"] == "datetime('now')"
    assert columns["created_at"]["dflt_value"] == "datetime('now')"

    method_id = _method(test_db, "IMMEDIATE", None, "Card to card")
    row = test_db.execute("SELECT * FROM payment_methods WHERE id = ?", (method_id,)).fetchone()
    assert row["fee_bps"] == 0
    assert row["fee_fixed"] == 0
    assert row["is_active"] == 1
    assert row["created_at"] is not None
    assert row["updated_at"] == row["created_at"]


@pytest.mark.parametrize(
    "rule, days",
    [
        ("DAYS_AFTER", None),          # the NULL trap
        ("DAY_OF_NEXT_MONTH", None),   # the NULL trap
        ("IMMEDIATE", 1),
        ("IMMEDIATE", 0),
        ("DAYS_AFTER", 0),
        ("DAYS_AFTER", 366),
        ("DAY_OF_NEXT_MONTH", 0),
        ("DAY_OF_NEXT_MONTH", 32),
    ],
)
def test_008_rule_days_check_rejects(test_db, rule, days):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        test_db.execute(_INSERT_METHOD, ("Bad method", rule, days))


@pytest.mark.parametrize(
    "rule, days",
    [
        ("IMMEDIATE", None),
        ("DAYS_AFTER", 1),
        ("DAYS_AFTER", 365),
        ("DAY_OF_NEXT_MONTH", 1),
        ("DAY_OF_NEXT_MONTH", 31),
    ],
)
def test_008_rule_days_check_accepts_the_boundaries(test_db, rule, days):
    test_db.execute(_INSERT_METHOD, (f"{rule}-{days}", rule, days))
    row = test_db.execute(
        "SELECT settlement_rule, settlement_days FROM payment_methods WHERE name = ?",
        (f"{rule}-{days}",),
    ).fetchone()
    assert (row["settlement_rule"], row["settlement_days"]) == (rule, days)


@pytest.mark.parametrize(
    "column, value",
    [("fee_bps", -1), ("fee_bps", 10001), ("fee_fixed", -1), ("is_active", 2)],
)
def test_008_fee_and_active_checks(test_db, column, value):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        test_db.execute(
            f"INSERT INTO payment_methods (name, settlement_rule, {column}) VALUES ('Bad', 'IMMEDIATE', ?)",
            (value,),
        )


def test_008_unknown_settlement_rule_rejected(test_db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        test_db.execute(_INSERT_METHOD, ("Bad", "WEEKLY", 7))


def test_008_payment_method_name_is_unique(test_db):
    _method(test_db, name="Zarinpal")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        _method(test_db, name="Zarinpal")


@pytest.mark.parametrize("month", [0, 13])
def test_008_settlement_month_out_of_range_rejected(test_db, month):
    method_id = _method(test_db)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        test_db.execute(_INSERT_SETTLEMENT, (method_id, 1405, month))


@pytest.mark.parametrize("year, month", [(1405, None), (None, 6)])
def test_008_settlement_year_and_month_come_together(test_db, year, month):
    method_id = _method(test_db)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        test_db.execute(_INSERT_SETTLEMENT, (method_id, year, month))


@pytest.mark.parametrize("year, month", [(1405, 1), (1405, 12), (None, None)])
def test_008_settlement_valid_month_or_none_accepted(test_db, year, month):
    method_id = _method(test_db)
    test_db.execute(_INSERT_SETTLEMENT, (method_id, year, month))


def test_008_settlement_amount_received_not_negative(test_db):
    method_id = _method(test_db)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        test_db.execute(
            "INSERT INTO settlements (payment_method_id, settled_date, expected_amount, amount_received) "
            "VALUES (?, '2026-10-01', 1000, -1)",
            (method_id,),
        )


def test_008_settlement_expected_amount_may_be_negative(test_db):
    method_id = _method(test_db)
    test_db.execute(
        "INSERT INTO settlements (payment_method_id, settled_date, expected_amount, amount_received) "
        "VALUES (?, '2026-10-01', -500, 0)",
        (method_id,),
    )


def test_008_one_settlement_per_method_and_month(test_db):
    method_id = _method(test_db)
    other_id = _method(test_db, name="Other gateway")
    test_db.execute(_INSERT_SETTLEMENT, (method_id, 1405, 6))
    # Another month, or the same month for another method, is fine.
    test_db.execute(_INSERT_SETTLEMENT, (method_id, 1405, 7))
    test_db.execute(_INSERT_SETTLEMENT, (other_id, 1405, 6))
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        test_db.execute(_INSERT_SETTLEMENT, (method_id, 1405, 6))
    # Settlements without a month are not limited by the index.
    test_db.execute(_INSERT_SETTLEMENT, (method_id, None, None))
    test_db.execute(_INSERT_SETTLEMENT, (method_id, None, None))


def test_008_settlement_method_cannot_be_deleted(test_db):
    method_id = _method(test_db)
    test_db.execute(_INSERT_SETTLEMENT, (method_id, 1405, 6))
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        test_db.execute("DELETE FROM payment_methods WHERE id = ?", (method_id,))
