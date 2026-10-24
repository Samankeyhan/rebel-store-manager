"""Migration 015 (supplier payables; material_purchases and product_purchases rebuilt with status, cancel and cost-snapshot
columns): every purchase row, id and AUTOINCREMENT mark survives, nothing is logged, the indexes and audit triggers are
back, each purchase with a total gets one backfilled payment, the movement link and the cost snapshot are read from the
history, and the new CHECKs hold. Run on a database built from 001-014 with fictional rows, and on a copy of this
laptop's data/shop.db."""

import json
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from db.audit import audit_operation, stale_audit_tables
from db.connection import MIGRATIONS_DIR, get_connection, init_db
from tools.integrity_check.__main__ import main as integrity_main

REPO = Path(__file__).resolve().parent.parent
LAPTOP_DB = REPO / "data" / "shop.db"
RESTORE_TEST = REPO / "data" / "restore-test"
MIGRATION = "015_supplier_payables_purchase_status.sql"

OLD_COLUMNS = ("id", "{item}_id", "supplier_id", "invoice_number", "purchase_date", "quantity_bought", "total_paid", "unit_cost", "notes")
NEW_COLUMNS = (
    "status", "cancel_reason", "cancelled_at", "replaces_purchase_id", "stock_movement_id", "cancel_movement_id",
    "item_cost_before", "item_cost_after",
)
INDEXES = {
    "idx_{t}_{item}_id", "idx_{t}_supplier_id", "idx_{t}_invoice_number_unique", "idx_{t}_status",
    "ux_{t}_replaces_purchase_id", "ux_{t}_stock_movement_id",
}
BACKFILL_NOTE = "پیش از ثبت بدهی‌ها"
KINDS = (("material_purchases", "material"), ("product_purchases", "product"))


def _old_columns(item: str) -> tuple:
    return tuple(c.format(item=item) for c in OLD_COLUMNS)


def _snapshot(conn) -> dict:
    snap = {}
    for table, item in KINDS:
        snap[table] = [dict(r) for r in conn.execute(f"SELECT {', '.join(_old_columns(item))} FROM {table} ORDER BY id")]
        row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)).fetchone()
        snap[f"{table}.seq"] = row[0] if row else None
    snap["stock_movements"] = [dict(r) for r in conn.execute("SELECT * FROM stock_movements ORDER BY id")]
    for table in ("materials", "products"):  # name_key is filled by init_db for rows added after 013
        snap[table] = [{k: v for k, v in dict(r).items() if k != "name_key"} for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
    snap["audit_log"] = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    snap["user_version"] = conn.execute("PRAGMA user_version").fetchone()[0]
    return snap


def _check_upgraded(db_path: str, before: dict) -> None:
    conn = get_connection(db_path)
    try:
        after = _snapshot(conn)
        for key, value in before.items():
            assert after[key] == value, key  # rows, ids, marks, items and movements unchanged; no audit row written
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert stale_audit_tables(conn) == []
        for table, item in KINDS:
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ?", (table,))}
            assert {i.format(t=table, item=item) for i in INDEXES} <= names
            assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE status <> 'ACTIVE' OR cancelled_at IS NOT NULL").fetchone()[0] == 0
            # one backfilled payment per purchase with a total, none for a total of 0
            for purchase in conn.execute(f"SELECT id, supplier_id, purchase_date, total_paid FROM {table}").fetchall():
                rows = conn.execute(
                    f"SELECT p.supplier_id, p.payment_date, p.amount, p.method, p.note, a.amount AS allocated "
                    f"FROM supplier_payment_allocations a JOIN supplier_payments p ON p.id = a.payment_id "
                    f"WHERE a.{item}_purchase_id = ?",
                    (purchase["id"],),
                ).fetchall()
                if purchase["total_paid"] == 0:
                    assert rows == []
                else:
                    assert [tuple(r) for r in rows] == [(
                        purchase["supplier_id"], purchase["purchase_date"], purchase["total_paid"], "OTHER", BACKFILL_NOTE,
                        purchase["total_paid"],
                    )]
    finally:
        conn.close()
    assert integrity_main(["--db", db_path]) == 0


def _migrations_upto(folder: Path, last: str) -> Path:
    """A folder with the migration files up to and including `last` (a 3-digit prefix)."""
    folder.mkdir()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name[:3] <= last:
            shutil.copy(path, folder / path.name)
    return folder


@pytest.fixture
def to_015(tmp_path) -> Path:
    """Migration 016 rebuilt these tables again: these tests stop at 015, the schema they describe."""
    return _migrations_upto(tmp_path / "migrations_to_015", "015")


@pytest.fixture
def db_at_014(tmp_path):
    db_path = str(tmp_path / "old.db")
    init_db(db_path, migrations_dir=_migrations_upto(tmp_path / "migrations_to_014", "014"))
    return db_path


@pytest.fixture
def db_015(tmp_path, to_015):
    """A connection to a fresh database built from 001-015."""
    db_path = str(tmp_path / "at015.db")
    init_db(db_path, migrations_dir=to_015)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _purchase(conn, kind, item_id, qty, total, unit_cost, new_cost, supplier=None, number=None, operation=True):
    """A purchase written the way the 014 code writes it (purchase row, item UPDATE, PURCHASE movement with its note),
    inside one audit operation unless `operation` is False."""
    table, item_table, item_col = (
        ("material_purchases", "materials", "material_id") if kind == "MATERIAL" else ("product_purchases", "products", "product_id")
    )
    label = "Material" if kind == "MATERIAL" else "Product"

    def write():
        cursor = conn.execute(
            f"INSERT INTO {table} ({item_col}, supplier_id, invoice_number, purchase_date, quantity_bought, total_paid, unit_cost) "
            f"VALUES (?, ?, ?, '2026-10-20 08:00:00', ?, ?, ?)",
            (item_id, supplier, f"PUR-{number:06d}", qty, total, unit_cost),
        )
        purchase_id = cursor.lastrowid
        conn.execute(f"UPDATE {item_table} SET current_stock = current_stock + ?, unit_cost = ? WHERE id = ?", (qty, new_cost, item_id))
        conn.execute(
            "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason, movement_date, notes) "
            "VALUES (?, ?, ?, 'PURCHASE', '2026-10-20 08:00:00', ?)",
            (kind, item_id, qty, f"{label} purchase #{purchase_id} (invoice PUR-{number:06d})"),
        )
        return purchase_id

    if operation:
        with audit_operation(conn, f"record_{kind.lower()}_purchase"):
            return write()
    return write()


def _add_fictional_purchases(db_path: str) -> dict:
    conn = get_connection(db_path)
    try:
        category = conn.execute("SELECT id FROM categories WHERE kind = 'PRODUCT' ORDER BY id").fetchone()[0]
        conn.execute("INSERT INTO suppliers (name) VALUES ('Fictional Paper Co')")
        conn.execute("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('Fictional Box', 'STOCK', 'piece', 0, 0)")
        conn.execute("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('Fictional Tape', 'STOCK', 'piece', 4, 250)")
        conn.execute(
            "INSERT INTO products (name, category, category_id, retail_price, wholesale_price, current_stock, unit_cost) "
            "VALUES ('Fictional Tee', 'OTHER', ?, 100, 80, 0, NULL)",
            (category,),
        )
        ids = {
            # material cost 0 -> 500
            "changed": _purchase(conn, "MATERIAL", 1, 10, 5000, 500, 500, supplier=1, number=1),
            # tape bought at its own cost: unit_cost does not change, the snapshot is its last logged cost
            "unchanged": _purchase(conn, "MATERIAL", 2, 4, 1000, 250, 250, supplier=1, number=2),
            # written outside any operation: no op_id, nothing to read
            "unlabelled": _purchase(conn, "MATERIAL", 1, 1, 0, 0, 500, number=3, operation=False),
            # a product with no cost gets one
            "product": _purchase(conn, "PRODUCT", 1, 3, 900, 300, 300, number=4),
            # deleted afterwards: the AUTOINCREMENT mark stays above the highest id left
            "deleted": _purchase(conn, "PRODUCT", 1, 1, 300, 300, 300, number=5),
        }
        conn.execute("DELETE FROM stock_movements WHERE notes LIKE 'Product purchase #' || ? || ' (%'", (ids["deleted"],))
        conn.execute("DELETE FROM product_purchases WHERE id = ?", (ids["deleted"],))
        conn.execute("UPDATE products SET current_stock = current_stock - 1 WHERE id = 1")
        conn.execute("UPDATE counters SET value = 5 WHERE name = 'PUR'")
        conn.execute("PRAGMA user_version = 1")
        return ids
    finally:
        conn.close()


def test_upgrade_from_014_keeps_every_purchase_row_id_and_mark_and_backfills_payments(db_at_014, to_015):
    ids = _add_fictional_purchases(db_at_014)
    conn = get_connection(db_at_014)
    before = _snapshot(conn)
    conn.close()
    assert before["product_purchases.seq"] == 2 and [p["id"] for p in before["product_purchases"]] == [1]
    assert integrity_main(["--db", db_at_014]) == 0  # the rehearsal checks the database BEFORE 015 with this code

    init_db(db_at_014, migrations_dir=to_015)

    _check_upgraded(db_at_014, before)
    conn = get_connection(db_at_014)
    try:
        payments = conn.execute("SELECT COUNT(*) FROM supplier_payments").fetchone()[0]
        assert payments == 3  # material 1 and 2, product 1; the total-0 purchase owes nothing
        assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'supplier_payments'").fetchone()[0] == 3
        conn.execute("INSERT INTO product_purchases (product_id, quantity_bought, total_paid, unit_cost) VALUES (1, 1, 0, 0)")
        assert conn.execute("SELECT MAX(id) FROM product_purchases").fetchone()[0] == 3  # id 2 is never reused
        assert ids["changed"] == 1
    finally:
        conn.close()


def test_the_cost_snapshot_and_movement_link_come_from_the_history(db_at_014, to_015):
    ids = _add_fictional_purchases(db_at_014)
    init_db(db_at_014, migrations_dir=to_015)
    conn = get_connection(db_at_014)
    try:
        rows = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM material_purchases")}
        assert (rows[ids["changed"]]["item_cost_before"], rows[ids["changed"]]["item_cost_after"]) == (0, 500)
        assert (rows[ids["unchanged"]]["item_cost_before"], rows[ids["unchanged"]]["item_cost_after"]) == (250, 250)
        assert (rows[ids["unlabelled"]]["item_cost_before"], rows[ids["unlabelled"]]["item_cost_after"]) == (None, None)
        product = dict(conn.execute("SELECT * FROM product_purchases WHERE id = ?", (ids["product"],)).fetchone())
        assert (product["item_cost_before"], product["item_cost_after"]) == (None, 300)
        for table, kind in (("material_purchases", "MATERIAL"), ("product_purchases", "PRODUCT")):
            for row in conn.execute(f"SELECT id, stock_movement_id FROM {table}").fetchall():
                movement = conn.execute("SELECT item_type, reason, notes FROM stock_movements WHERE id = ?", (row["stock_movement_id"],)).fetchone()
                assert movement["item_type"] == kind and movement["reason"] == "PURCHASE"
                assert movement["notes"].startswith(f"{kind.capitalize()} purchase #{row['id']} (")
    finally:
        conn.close()


def test_a_purchase_whose_movement_note_is_ambiguous_or_missing_gets_no_link(db_at_014, to_015):
    _add_fictional_purchases(db_at_014)
    conn = get_connection(db_at_014)
    conn.execute(
        "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason, notes) "
        "VALUES ('MATERIAL', 1, 10, 'PURCHASE', 'Material purchase #1 (invoice PUR-000001) duplicate')"
    )
    conn.execute("UPDATE stock_movements SET notes = 'hand written' WHERE notes LIKE 'Material purchase #2 (%'")
    conn.execute("UPDATE materials SET current_stock = current_stock + 10 WHERE id = 1")
    conn.close()
    init_db(db_at_014, migrations_dir=to_015)
    conn = get_connection(db_at_014)
    try:
        links = dict(conn.execute("SELECT id, stock_movement_id FROM material_purchases").fetchall())
        assert links[1] is None and links[2] is None and links[3] is not None
    finally:
        conn.close()


def test_upgrade_of_an_empty_database_leaves_no_sequence_row_and_no_payment(db_at_014, to_015):
    init_db(db_at_014, migrations_dir=to_015)
    conn = get_connection(db_at_014)
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_sequence")]
        assert not {"material_purchases", "product_purchases", "supplier_payments"} & set(names)
        assert conn.execute("SELECT COUNT(*) FROM supplier_payments").fetchone()[0] == 0
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_new_columns_come_last_and_old_ones_keep_their_order(db_015):
    for table, item in KINDS:
        columns = tuple(r["name"] for r in db_015.execute(f"PRAGMA table_info({table})"))
        assert columns == _old_columns(item) + NEW_COLUMNS


def _insert_purchase(conn, **cols):
    cols = {"material_id": 1, "quantity_bought": 1, "total_paid": 0, "unit_cost": 0, **cols}
    conn.execute(
        f"INSERT INTO material_purchases ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", list(cols.values())
    )


def test_cancelled_needs_a_moment_a_reason_and_a_movement_and_the_snapshot_is_consistent(db_015):
    db_015.execute("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('M', 'STOCK', 'piece', 0, 0)")
    db_015.execute("INSERT INTO stock_movements (item_type, item_id, quantity_change, reason) VALUES ('MATERIAL', 1, -1, 'PURCHASE')")
    ok = {"status": "CANCELLED", "cancelled_at": "2026-10-24 10:00:00", "cancel_reason": "wrong amount", "cancel_movement_id": 1}
    _insert_purchase(db_015, **ok)
    for bad in (
        {**ok, "cancelled_at": None},
        {**ok, "cancel_reason": "  "},
        {**ok, "cancel_movement_id": None},
        {"cancelled_at": "2026-10-24 10:00:00"},  # ACTIVE with a cancel moment
        {"status": "VOIDED"},
        {"item_cost_before": 5},  # a before cost without an after cost
        {"item_cost_after": -1},
        {"id": 9, "replaces_purchase_id": 9},
    ):
        with pytest.raises(sqlite3.IntegrityError):
            _insert_purchase(db_015, **bad)
    _insert_purchase(db_015, replaces_purchase_id=1)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_purchase(db_015, replaces_purchase_id=1)  # a purchase is replaced at most once


def test_payment_and_allocation_constraints(db_015):
    db_015.execute("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('M', 'STOCK', 'piece', 0, 0)")
    _insert_purchase(db_015, total_paid=100)
    db_015.execute("INSERT INTO supplier_payments (payment_date, amount, method) VALUES ('2026-10-24 08:00:00', 100, 'CASH')")
    for sql in (
        "INSERT INTO supplier_payments (payment_date, amount, method) VALUES ('2026-10-24 08:00:00', 0, 'CASH')",
        "INSERT INTO supplier_payments (payment_date, amount, method) VALUES ('2026-10-24 08:00:00', 5, 'BITCOIN')",
        "INSERT INTO supplier_payment_allocations (payment_id, amount) VALUES (1, 5)",
        "INSERT INTO supplier_payment_allocations (payment_id, material_purchase_id, product_purchase_id, amount) VALUES (1, 1, 1, 5)",
        "INSERT INTO supplier_payment_allocations (payment_id, material_purchase_id, amount) VALUES (1, 1, 0)",
        "INSERT INTO supplier_payment_allocations (payment_id, material_purchase_id, amount) VALUES (1, 99, 5)",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            db_015.execute(sql)
    db_015.execute("INSERT INTO supplier_payment_allocations (payment_id, material_purchase_id, amount) VALUES (1, 1, 100)")
    with pytest.raises(sqlite3.IntegrityError):
        db_015.execute("INSERT INTO supplier_payment_allocations (payment_id, material_purchase_id, amount) VALUES (1, 1, 1)")
    db_015.execute("DELETE FROM supplier_payments WHERE id = 1")
    assert db_015.execute("SELECT COUNT(*) FROM supplier_payment_allocations").fetchone()[0] == 0  # cascade


def test_audit_triggers_log_payments_and_the_new_purchase_columns(db_015):
    db_015.execute("INSERT INTO supplier_payments (payment_date, amount, method, note) VALUES ('2026-10-24 08:00:00', 70, 'CARD', 'n')")
    db_015.execute("UPDATE supplier_payments SET note = 'm' WHERE id = 1")
    rows = db_015.execute(
        "SELECT action, before_json, after_json FROM audit_log WHERE entity_type = 'supplier_payments' ORDER BY id"
    ).fetchall()
    assert [r["action"] for r in rows] == ["INSERT", "UPDATE"]
    assert json.loads(rows[0]["after_json"])["amount"] == 70
    assert json.loads(rows[1]["before_json"]) == {"note": "n"}  # updated_at is never logged
    assert db_015.execute("SELECT updated_at FROM supplier_payments").fetchone()[0] is not None
    db_015.execute("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('M', 'STOCK', 'piece', 0, 0)")
    _insert_purchase(db_015, item_cost_before=0, item_cost_after=10)
    after = db_015.execute(
        "SELECT after_json FROM audit_log WHERE entity_type = 'material_purchases' AND action = 'INSERT'"
    ).fetchone()[0]
    assert '"status":"ACTIVE"' in after and '"item_cost_after":10' in after


def _laptop_copy(folder: Path) -> tuple[str, dict, set]:
    """A copy of data/shop.db made through SQLite immutable mode (the file itself is never opened for writing)."""
    copy = folder / "shop.db"
    source = sqlite3.connect(f"file:{LAPTOP_DB.as_posix()}?mode=ro&immutable=1", uri=True)
    target = sqlite3.connect(copy)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    conn = get_connection(str(copy))
    try:
        before = _snapshot(conn)
        applied = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
    finally:
        conn.close()
    return str(copy), before, applied


@pytest.mark.skipif(not LAPTOP_DB.is_file(), reason="this laptop's data/shop.db is not here")
def test_upgrade_of_a_copy_of_the_laptop_database():
    """Only while data/shop.db is still before migration 015: the copy (in its own folder under data/restore-test/,
    removed afterwards) is migrated by init_db and the upgrade assertions run, the integrity check included."""
    folder = RESTORE_TEST / f"m015-pytest-{os.getpid()}"
    folder.mkdir(parents=True, exist_ok=False)
    try:
        path, before, applied = _laptop_copy(folder)
        if MIGRATION in applied:
            pytest.skip("this laptop's data/shop.db is already at migration 015 or later: no upgrade to test")
        init_db(path, migrations_dir=_migrations_upto(folder / "migrations_to_015", "015"))
        _check_upgraded(path, before)
    finally:
        shutil.rmtree(folder)
