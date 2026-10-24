"""Migration 014 (orders rebuilt: status VOIDED, void_reason, voided_at, replaces_order_id): every row, id and
the AUTOINCREMENT mark survive, nothing is logged, the indexes and audit triggers are back, and the new CHECKs
hold. Run on a database built from 001-013 with fictional rows, and on a copy of this laptop's data/shop.db."""

import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from db.audit import stale_audit_tables
from db.connection import MIGRATIONS_DIR, get_connection, init_db
from tools.integrity_check.__main__ import main as integrity_main

REPO = Path(__file__).resolve().parent.parent
LAPTOP_DB = REPO / "data" / "shop.db"
RESTORE_TEST = REPO / "data" / "restore-test"

OLD_COLUMNS = (
    "id", "invoice_number", "order_date", "status", "channel", "customer_name", "shipping_charge",
    "postage_cost", "transaction_fee", "notes", "packaging_kit_id", "packaging_cost", "stock_committed",
    "payment_method_id", "payment_reference", "paid_date", "expected_settlement_date", "paid_jalali_year",
    "paid_jalali_month", "settlement_id",
)
NEW_COLUMNS = ("void_reason", "voided_at", "replaces_order_id")
INDEXES = {
    "idx_orders_date", "idx_orders_status", "idx_orders_channel", "idx_orders_invoice_number_unique",
    "idx_orders_settlement_pending", "ux_orders_replaces_order_id",
}


def _old_rows(conn, table):
    columns = OLD_COLUMNS if table == "orders" else ("*",)
    return [dict(r) for r in conn.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id")]


def _snapshot(conn) -> dict:
    return {
        "orders": _old_rows(conn, "orders"),
        "order_items": _old_rows(conn, "order_items"),
        "stock_movements": _old_rows(conn, "stock_movements"),
        "audit_log": conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
        "sequence": conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'orders'").fetchone(),
        "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
    }


def _check_upgraded(db_path: str, before: dict) -> None:
    conn = get_connection(db_path)
    try:
        after = _snapshot(conn)
        assert after["orders"] == before["orders"]
        assert after["order_items"] == before["order_items"]
        assert after["stock_movements"] == before["stock_movements"]
        assert after["audit_log"] == before["audit_log"]  # the copy wrote no audit rows
        assert (after["sequence"] and after["sequence"][0]) == (before["sequence"] and before["sequence"][0])
        assert after["user_version"] == before["user_version"]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert stale_audit_tables(conn) == []
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'orders'")}
        assert INDEXES <= names
        assert conn.execute(
            "SELECT COUNT(*) FROM orders WHERE void_reason IS NOT NULL OR voided_at IS NOT NULL OR replaces_order_id IS NOT NULL"
        ).fetchone()[0] == 0
    finally:
        conn.close()
    assert integrity_main(["--db", db_path]) == 0


@pytest.fixture
def db_at_013(tmp_path):
    old_dir = tmp_path / "migrations_to_013"
    old_dir.mkdir()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name < "014":
            shutil.copy(path, old_dir / path.name)
    db_path = str(tmp_path / "old.db")
    init_db(db_path, migrations_dir=old_dir)
    return db_path


def _add_fictional_orders(db_path: str) -> None:
    """Three committed orders (one with a product SALE movement), then the newest deleted, so the
    AUTOINCREMENT mark is above the highest id left."""
    conn = get_connection(db_path)
    try:
        category = conn.execute("SELECT id FROM categories WHERE kind = 'PRODUCT' ORDER BY id").fetchone()[0]
        conn.execute(
            "INSERT INTO products (name, category, category_id, retail_price, wholesale_price, current_stock, unit_cost) "
            "VALUES ('Fictional Tee', 'OTHER', ?, 100, 80, 4, 40)",
            (category,),
        )
        for number, status in ((1, "COMPLETED"), (2, "CANCELLED"), (3, "PAID")):
            conn.execute(
                "INSERT INTO orders (invoice_number, order_date, status, channel, customer_name, shipping_charge, "
                "postage_cost, transaction_fee, notes, packaging_cost, stock_committed, paid_date, paid_jalali_year, "
                "paid_jalali_month) VALUES (?, '2026-10-01 08:00:00', ?, 'WEBSITE', 'Customer A', 10, 3, 2, 'n', 0, 1, "
                "'2026-10-01', 1405, 7)",
                (f"INV-{number:06d}", status),
            )
            conn.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, list_price, discount_amount, unit_price, "
                "unit_cost_at_time) VALUES (?, 1, 1, 100, 0, 100, 40)",
                (number,),
            )
        conn.execute(
            "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason, unit_cost_at_time) "
            "VALUES ('PRODUCT', 1, 5, 'ADJUSTMENT', 40)"
        )
        conn.execute(
            "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason, reference_order_id) "
            "VALUES ('PRODUCT', 1, -1, 'SALE', 1)"
        )
        conn.execute("UPDATE counters SET value = 3 WHERE name = 'INV'")
        conn.execute("DELETE FROM order_items WHERE order_id = 3")
        conn.execute("DELETE FROM orders WHERE id = 3")
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    finally:
        conn.close()


def test_upgrade_from_013_keeps_every_row_id_and_the_autoincrement_mark(db_at_013):
    _add_fictional_orders(db_at_013)
    conn = get_connection(db_at_013)
    before = _snapshot(conn)
    conn.close()
    assert before["sequence"][0] == 3 and [o["id"] for o in before["orders"]] == [1, 2]
    # The update rehearsal runs this code's integrity check on the database BEFORE 014: orders must read.
    assert integrity_main(["--db", db_at_013]) == 0

    init_db(db_at_013)

    _check_upgraded(db_at_013, before)
    conn = get_connection(db_at_013)
    try:
        conn.execute(
            "INSERT INTO orders (status, channel) VALUES ('COMPLETED', 'WEBSITE')"
        )
        assert conn.execute("SELECT MAX(id) FROM orders").fetchone()[0] == 4  # id 3 is never reused
    finally:
        conn.close()


def test_upgrade_of_an_empty_database_leaves_no_sequence_row(db_at_013):
    init_db(db_at_013)
    conn = get_connection(db_at_013)
    try:
        assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'orders'").fetchone() is None
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_new_columns_come_last_and_old_ones_keep_their_order(test_db):
    columns = [r["name"] for r in test_db.execute("PRAGMA table_info(orders)")]
    assert tuple(columns) == OLD_COLUMNS + NEW_COLUMNS


def _insert(conn, **cols):
    cols = {"status": "COMPLETED", "channel": "WEBSITE", **cols}
    conn.execute(
        f"INSERT INTO orders ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", list(cols.values())
    )


def test_voided_needs_a_moment_and_a_reason(test_db):
    _insert(test_db, status="VOIDED", voided_at="2026-10-23 10:00:00", void_reason="wrong product")
    for bad in (
        {"status": "VOIDED", "void_reason": "x"},  # no voided_at
        {"status": "VOIDED", "voided_at": "2026-10-23 10:00:00"},  # no reason
        {"status": "VOIDED", "voided_at": "2026-10-23 10:00:00", "void_reason": "   "},  # blank reason
        {"status": "COMPLETED", "voided_at": "2026-10-23 10:00:00"},  # voided_at without VOIDED
    ):
        with pytest.raises(sqlite3.IntegrityError):
            _insert(test_db, **bad)


def test_an_order_replaces_at_most_one_other_and_never_itself(test_db):
    _insert(test_db, status="VOIDED", voided_at="2026-10-23 10:00:00", void_reason="x")
    _insert(test_db, replaces_order_id=1)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(test_db, replaces_order_id=1)  # a second replacement of order 1
    with pytest.raises(sqlite3.IntegrityError):
        _insert(test_db, id=10, replaces_order_id=10)  # itself
    with pytest.raises(sqlite3.IntegrityError):
        _insert(test_db, replaces_order_id=999)  # foreign key


def test_audit_triggers_log_the_new_columns(test_db):
    _insert(test_db)
    test_db.execute(
        "UPDATE orders SET status = 'VOIDED', voided_at = '2026-10-23 10:00:00', void_reason = 'x' WHERE id = 1"
    )
    row = test_db.execute(
        "SELECT after_json FROM audit_log WHERE entity_type = 'orders' AND action = 'UPDATE' ORDER BY id DESC"
    ).fetchone()
    assert '"void_reason":"x"' in row[0] and '"status":"VOIDED"' in row[0]


def _laptop_copy(folder: Path) -> tuple[str, dict, set]:
    """A copy of data/shop.db made through SQLite immutable mode (the file itself is never opened for writing):
    (path of the copy, its snapshot, the migrations it has applied)."""
    copy = folder / "shop.db"
    source = sqlite3.connect(f"file:{LAPTOP_DB.as_posix()}?mode=ro&immutable=1", uri=True)
    target = sqlite3.connect(copy)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    conn = get_connection(str(copy))
    conn.row_factory = sqlite3.Row
    try:
        before = _snapshot(conn)
        applied = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
    finally:
        conn.close()
    return str(copy), before, applied


def _generic_checks(db_path: str, before: dict) -> None:
    """What holds whatever schema the copy is at: init_db changed no order, movement or audit row, no foreign key
    is broken, and the integrity check passes."""
    conn = get_connection(db_path)
    try:
        after = _snapshot(conn)
        for key in ("orders", "order_items", "stock_movements", "audit_log", "user_version"):
            assert after[key] == before[key], key
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()
    assert integrity_main(["--db", db_path]) == 0


@pytest.mark.skipif(not LAPTOP_DB.is_file(), reason="this laptop's data/shop.db is not here")
def test_a_copy_of_the_laptop_database_survives_init_db():
    """Whatever schema data/shop.db is at (the app may have been run on another branch): a copy in its own folder
    under data/restore-test/, init_db, foreign_key_check and the integrity check; nothing in it changes. The folder is removed."""
    folder = RESTORE_TEST / f"m014-copy-pytest-{os.getpid()}"
    folder.mkdir(parents=True, exist_ok=False)
    try:
        path, before, _ = _laptop_copy(folder)
        init_db(path)
        _generic_checks(path, before)
    finally:
        shutil.rmtree(folder)


@pytest.mark.skipif(not LAPTOP_DB.is_file(), reason="this laptop's data/shop.db is not here")
def test_upgrade_of_a_copy_of_the_laptop_database():
    """Only while data/shop.db is still before migration 014: the copy is migrated by init_db and the upgrade
    assertions run. Once the owner's database is at 014 or later there is nothing to upgrade: skipped, with the reason."""
    folder = RESTORE_TEST / f"m014-pytest-{os.getpid()}"
    folder.mkdir(parents=True, exist_ok=False)
    try:
        path, before, applied = _laptop_copy(folder)
        if "014_order_void.sql" in applied:
            pytest.skip("this laptop's data/shop.db is already at migration 014 or later: no upgrade to test")
        init_db(path)
        _check_upgraded(path, before)
    finally:
        shutil.rmtree(folder)
