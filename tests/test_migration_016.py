"""Migration 016 (purchase invoices: material_purchases and product_purchases become the lines of purchase_invoices,
supplier payment allocations point at the invoice): every existing purchase becomes a one-line invoice with its own PUR
number, supplier, day, note and status; every line and allocation keeps its id; the AUTOINCREMENT marks survive; paid
and outstanding per purchase are unchanged; nothing is logged; the indexes, constraints and audit triggers are there.
Run on a database built from 001-015 with fictional rows, and on a copy of this laptop's data/shop.db."""

import shutil
import sqlite3
from pathlib import Path

import pytest

from db.audit import audit_trigger_sql, stale_audit_tables
from db.connection import MIGRATIONS_DIR, get_connection, init_db
from db.purchases import get_purchase
from tools.integrity_check.__main__ import main as integrity_main

REPO = Path(__file__).resolve().parent.parent
LAPTOP_DB = REPO / "data" / "shop.db"
MIGRATION = "016_purchase_invoices.sql"
KINDS = (("MATERIAL", "material_purchases", "material_id"), ("PRODUCT", "product_purchases", "product_id"))
HEADER_COLUMNS = ("invoice_number", "supplier_id", "purchase_date", "notes", "status", "cancel_reason", "cancelled_at")
LINE_COLUMNS = (
    "id", "{item}", "quantity_bought", "total_paid", "unit_cost", "stock_movement_id", "cancel_movement_id",
    "item_cost_before", "item_cost_after",
)


def _migrations_upto(folder: Path, last: str) -> Path:
    folder.mkdir()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name[:3] <= last:
            shutil.copy(path, folder / path.name)
    return folder


@pytest.fixture
def db_at_015(tmp_path):
    db_path = str(tmp_path / "old.db")
    init_db(db_path, migrations_dir=_migrations_upto(tmp_path / "migrations_to_015", "015"))
    return db_path


def _snapshot(conn) -> dict:
    """Everything 016 must keep, read with the 015 column names."""
    snap = {"lines": {}, "seq": {}}
    for kind, table, item in KINDS:
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY id"):
            snap["lines"][(kind, row["id"])] = dict(row)
    snap["allocations"] = [
        (r["id"], r["payment_id"], "MATERIAL" if r["material_purchase_id"] else "PRODUCT",
         r["material_purchase_id"] or r["product_purchase_id"], r["amount"])
        for r in conn.execute("SELECT * FROM supplier_payment_allocations ORDER BY id")
    ]
    for table in ("material_purchases", "product_purchases", "supplier_payment_allocations", "supplier_payments"):
        row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)).fetchone()
        snap["seq"][table] = row[0] if row else None
    snap["payments"] = [dict(r) for r in conn.execute("SELECT * FROM supplier_payments ORDER BY id")]
    snap["movements"] = [dict(r) for r in conn.execute("SELECT * FROM stock_movements ORDER BY id")]
    snap["counters"] = [tuple(r) for r in conn.execute("SELECT * FROM counters ORDER BY name")]
    snap["audit_log"] = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    snap["paid"] = {
        key: sum(a[4] for a in snap["allocations"] if (a[2], a[3]) == key) for key in snap["lines"]
    }
    return snap


def _check_upgraded(conn, before: dict) -> dict:
    """Every 015 purchase is a one-line invoice with the same fields; returns {(kind, line id): invoice id}."""
    invoice_of = {}
    for kind, table, item in KINDS:
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY id"):
            invoice_of[(kind, row["id"])] = row["purchase_invoice_id"]
            old = before["lines"][(kind, row["id"])]
            for column in LINE_COLUMNS:
                name = column.format(item=item)
                assert row[name] == old[name], (kind, row["id"], name)
            invoice = conn.execute("SELECT * FROM purchase_invoices WHERE id = ?", (row["purchase_invoice_id"],)).fetchone()
            for column in HEADER_COLUMNS:
                assert invoice[column] == old[column], (kind, row["id"], column)
            replaced = old["replaces_purchase_id"]
            assert invoice["replaces_invoice_id"] == (invoice_of.get((kind, replaced)) if replaced else None)
    assert set(invoice_of) == set(before["lines"])
    assert len(set(invoice_of.values())) == len(invoice_of)  # one invoice per purchase
    assert conn.execute("SELECT COUNT(*) FROM purchase_invoices").fetchone()[0] == len(invoice_of)
    # every allocation keeps its id, payment and amount, and now pays the invoice of the row it paid
    after = [tuple(r) for r in conn.execute("SELECT id, payment_id, purchase_invoice_id, amount FROM supplier_payment_allocations ORDER BY id")]
    assert after == [(a[0], a[1], invoice_of[(a[2], a[3])], a[4]) for a in before["allocations"]]
    assert [dict(r) for r in conn.execute("SELECT * FROM supplier_payments ORDER BY id")] == before["payments"]
    assert [dict(r) for r in conn.execute("SELECT * FROM stock_movements ORDER BY id")] == before["movements"]
    assert [tuple(r) for r in conn.execute("SELECT * FROM counters ORDER BY name")] == before["counters"]
    for table, seq in before["seq"].items():
        row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)).fetchone()
        assert (row[0] if row else None) == seq, table
    row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'purchase_invoices'").fetchone()
    assert (row[0] if row else None) == (len(invoice_of) or None)
    assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == before["audit_log"]  # nothing logged
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert stale_audit_tables(conn) == []
    # paid and outstanding of every purchase are what they were
    for (kind, line_id), invoice_id in invoice_of.items():
        purchase = get_purchase(conn, invoice_id)
        old = before["lines"][(kind, line_id)]
        assert (purchase["total"], purchase["paid"]) == (old["total_paid"], before["paid"][(kind, line_id)])
        assert purchase["outstanding"] == old["total_paid"] - before["paid"][(kind, line_id)]
    return invoice_of


def _add_fictional_rows(db_path: str, cancelled: bool = False) -> None:
    """Purchases, payments and allocations written the way the 015 code stores them (stock and movements agree, so the
    integrity check is clean). `cancelled` adds a cancelled purchase and its replacement, as slice B would write them."""
    conn = get_connection(db_path)
    try:
        category = conn.execute("SELECT id FROM categories WHERE kind = 'PRODUCT' ORDER BY id").fetchone()[0]
        conn.execute("INSERT INTO suppliers (name) VALUES ('Fictional Paper Co')")
        conn.execute("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('Fictional Box', 'STOCK', 'piece', 0, 0)")
        conn.execute("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('Fictional Tape', 'STOCK', 'piece', 0, 0)")
        conn.execute(
            "INSERT INTO products (name, category, category_id, retail_price, wholesale_price, current_stock, unit_cost) "
            "VALUES ('Fictional Tee', 'OTHER', ?, 100, 80, 0, NULL)",
            (category,),
        )

        def movement(kind, item, qty):
            table = "materials" if kind == "MATERIAL" else "products"
            conn.execute(f"UPDATE {table} SET current_stock = current_stock + ? WHERE id = ?", (qty, item))
            return conn.execute(
                "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason, movement_date) "
                "VALUES (?, ?, ?, 'PURCHASE', '2026-10-20 08:00:00')",
                (kind, item, qty),
            ).lastrowid

        def purchase(table, item_col, item, date, number, total, supplier=1, notes=None, **extra):
            cols = {
                item_col: item, "supplier_id": supplier, "invoice_number": number, "purchase_date": date,
                "quantity_bought": 10, "total_paid": total, "unit_cost": total // 10, "notes": notes, **extra,
            }
            return conn.execute(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", list(cols.values())
            ).lastrowid

        # material 1 shares its day with the product; material 2 is the oldest and has no supplier
        purchase("material_purchases", "material_id", 1, "2026-10-20 08:00:00", "PUR-000003", 5000, notes="first box",
                 stock_movement_id=movement("MATERIAL", 1, 10), item_cost_before=0, item_cost_after=500)
        purchase("material_purchases", "material_id", 2, "2026-10-18 08:00:00", "PUR-000001", 2500, supplier=None,
                 stock_movement_id=movement("MATERIAL", 2, 10))
        purchase("product_purchases", "product_id", 1, "2026-10-20 08:00:00", "PUR-000004", 3000,
                 stock_movement_id=movement("PRODUCT", 1, 10), item_cost_before=None, item_cost_after=300)
        # a legacy purchase: no number, its movement not linked
        movement("MATERIAL", 1, 10)
        purchase("material_purchases", "material_id", 1, "2026-10-19 08:00:00", None, 0)
        purchase("product_purchases", "product_id", 1, "2026-10-21 08:00:00", "PUR-000005", 300,
                 stock_movement_id=movement("PRODUCT", 1, 10))
        # a deleted purchase: the AUTOINCREMENT mark stays above the highest id left
        gone = purchase("product_purchases", "product_id", 1, "2026-10-21 09:00:00", "PUR-000006", 100)
        conn.execute("DELETE FROM product_purchases WHERE id = ?", (gone,))
        conn.execute("UPDATE materials SET unit_cost = 500 WHERE id = 1")
        conn.execute("UPDATE materials SET unit_cost = 250 WHERE id = 2")
        conn.execute("UPDATE products SET unit_cost = 300 WHERE id = 1")
        if cancelled:
            cancel = movement("PRODUCT", 1, -10)
            old = purchase("product_purchases", "product_id", 1, "2026-10-21 10:00:00", "PUR-000007", 3000,
                           status="CANCELLED", cancel_reason="wrong count", cancelled_at="2026-10-21 11:00:00",
                           stock_movement_id=movement("PRODUCT", 1, 10), cancel_movement_id=cancel)
            purchase("product_purchases", "product_id", 1, "2026-10-21 12:00:00", "PUR-000008", 300, replaces_purchase_id=old,
                     stock_movement_id=movement("PRODUCT", 1, 10))

        def payment(supplier, amount, allocations):
            pid = conn.execute(
                "INSERT INTO supplier_payments (supplier_id, payment_date, amount, method) VALUES (?, '2026-10-21 08:00:00', ?, 'CASH')",
                (supplier, amount),
            ).lastrowid
            for column, purchase_id, part in allocations:
                conn.execute(
                    f"INSERT INTO supplier_payment_allocations (payment_id, {column}, amount) VALUES (?, ?, ?)",
                    (pid, purchase_id, part),
                )
            return pid

        # one payment over a material and a product purchase, one partial, one for the purchase with no supplier
        payment(1, 7000, [("material_purchase_id", 1, 5000), ("product_purchase_id", 1, 2000)])
        payment(1, 100, [("product_purchase_id", 2, 100)])
        payment(None, 2500, [("material_purchase_id", 2, 2500)])
        # a deleted payment leaves a gap in the allocation ids
        extra = payment(1, 50, [("product_purchase_id", 2, 50)])
        conn.execute("DELETE FROM supplier_payments WHERE id = ?", (extra,))
        conn.execute("UPDATE counters SET value = ? WHERE name = 'PUR'", (8 if cancelled else 6,))
    finally:
        conn.close()


def test_upgrade_from_015_makes_one_invoice_per_purchase_and_keeps_every_id_mark_and_payment(db_at_015):
    _add_fictional_rows(db_at_015)
    conn = get_connection(db_at_015)
    before = _snapshot(conn)
    conn.close()
    assert before["seq"]["product_purchases"] == 3 and before["seq"]["supplier_payment_allocations"] == 5
    assert integrity_main(["--db", db_at_015]) == 0  # the rehearsal checks the database BEFORE 016 with this code

    init_db(db_at_015)

    conn = get_connection(db_at_015)
    try:
        invoice_of = _check_upgraded(conn, before)
        # numbered oldest first: purchase day, then materials before products, then line id
        order = (("MATERIAL", 2), ("MATERIAL", 3), ("MATERIAL", 1), ("PRODUCT", 1), ("PRODUCT", 2))
        assert [invoice_of[k] for k in order] == [1, 2, 3, 4, 5]
        conn.execute("INSERT INTO purchase_invoices (purchase_date) VALUES ('2026-10-24 08:00:00')")
        conn.execute(
            "INSERT INTO product_purchases (purchase_invoice_id, product_id, quantity_bought, total_paid, unit_cost) VALUES (6, 1, 1, 0, 0)"
        )
        assert conn.execute("SELECT MAX(id) FROM product_purchases").fetchone()[0] == 4  # id 3 is never reused
        assert conn.execute("SELECT MAX(id) FROM purchase_invoices").fetchone()[0] == 6
        conn.execute("DELETE FROM product_purchases WHERE id = 4")
        conn.execute("DELETE FROM purchase_invoices WHERE id = 6")
    finally:
        conn.close()
    assert integrity_main(["--db", db_at_015]) == 0


def test_a_cancelled_purchase_and_its_replacement_keep_their_status_and_link(db_at_015):
    _add_fictional_rows(db_at_015, cancelled=True)
    conn = get_connection(db_at_015)
    before = _snapshot(conn)
    conn.close()
    init_db(db_at_015)
    conn = get_connection(db_at_015)
    try:
        invoice_of = _check_upgraded(conn, before)
        old, new = invoice_of[("PRODUCT", 4)], invoice_of[("PRODUCT", 5)]
        cancelled = conn.execute("SELECT status, cancel_reason FROM purchase_invoices WHERE id = ?", (old,)).fetchone()
        assert tuple(cancelled) == ("CANCELLED", "wrong count")
        assert conn.execute("SELECT replaces_invoice_id FROM purchase_invoices WHERE id = ?", (new,)).fetchone()[0] == old
    finally:
        conn.close()


def test_upgrade_of_an_empty_database_leaves_no_sequence_row(db_at_015):
    init_db(db_at_015)
    conn = get_connection(db_at_015)
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_sequence")}
        assert not {"purchase_invoices", "material_purchases", "product_purchases", "supplier_payment_allocations"} & names
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_columns_of_the_invoice_the_lines_and_the_allocations(test_db):
    def columns(table):
        return tuple(r["name"] for r in test_db.execute(f"PRAGMA table_info({table})"))

    assert columns("purchase_invoices") == ("id",) + HEADER_COLUMNS + ("replaces_invoice_id",)
    assert columns("material_purchases") == ("id", "purchase_invoice_id") + tuple(c.format(item="material_id") for c in LINE_COLUMNS[1:])
    assert columns("product_purchases") == ("id", "purchase_invoice_id") + tuple(c.format(item="product_id") for c in LINE_COLUMNS[1:])
    assert columns("supplier_payment_allocations") == ("id", "payment_id", "purchase_invoice_id", "amount")
    indexes = {r[0] for r in test_db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {
        "ux_purchase_invoices_invoice_number", "idx_purchase_invoices_supplier_date", "idx_purchase_invoices_purchase_date",
        "idx_purchase_invoices_status", "ux_purchase_invoices_replaces_invoice_id",
        "ux_material_purchases_invoice_material", "idx_material_purchases_material_id", "ux_material_purchases_stock_movement_id",
        "ux_product_purchases_invoice_product", "idx_product_purchases_product_id", "ux_product_purchases_stock_movement_id",
        "idx_supplier_payment_allocations_payment", "idx_supplier_payment_allocations_invoice",
    } <= indexes


def _invoice(conn, **cols) -> int:
    cols = {"purchase_date": "2026-10-24 08:00:00", **cols}
    return conn.execute(
        f"INSERT INTO purchase_invoices ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", list(cols.values())
    ).lastrowid


def _line(conn, **cols) -> None:
    cols = {"purchase_invoice_id": 1, "material_id": 1, "quantity_bought": 1, "total_paid": 0, "unit_cost": 0, **cols}
    conn.execute(f"INSERT INTO material_purchases ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", list(cols.values()))


def test_invoice_and_line_constraints(test_db):
    test_db.execute("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('M', 'STOCK', 'piece', 0, 0)")
    test_db.execute("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('N', 'STOCK', 'piece', 0, 0)")
    test_db.execute("INSERT INTO stock_movements (item_type, item_id, quantity_change, reason) VALUES ('MATERIAL', 1, 1, 'PURCHASE')")
    _invoice(test_db, invoice_number="PUR-000001")
    for bad in (
        {"invoice_number": "PUR-000001"},  # numbers are unique
        {"status": "CANCELLED", "cancel_reason": "x"},  # cancelled needs its moment
        {"status": "CANCELLED", "cancelled_at": "2026-10-24 09:00:00", "cancel_reason": " "},  # and a reason
        {"cancelled_at": "2026-10-24 09:00:00"},
        {"status": "VOIDED"},
        {"id": 9, "replaces_invoice_id": 9},
    ):
        with pytest.raises(sqlite3.IntegrityError):
            _invoice(test_db, **bad)
    _invoice(test_db, replaces_invoice_id=1)
    with pytest.raises(sqlite3.IntegrityError):
        _invoice(test_db, replaces_invoice_id=1)  # an invoice is replaced at most once
    _line(test_db, stock_movement_id=1)
    _line(test_db, material_id=2)
    for bad in (
        {"material_id": 1, "purchase_invoice_id": 1},  # the same item twice on one invoice
        {"purchase_invoice_id": None},
        {"purchase_invoice_id": 2, "cancel_movement_id": 1},  # a cancel movement without its own movement
        {"purchase_invoice_id": 2, "item_cost_before": 5},
        {"purchase_invoice_id": 2, "stock_movement_id": 1},  # one line per movement
    ):
        with pytest.raises(sqlite3.IntegrityError):
            _line(test_db, **bad)


def test_allocation_constraints(test_db):
    _invoice(test_db)
    test_db.execute("INSERT INTO supplier_payments (payment_date, amount, method) VALUES ('2026-10-24 08:00:00', 100, 'CASH')")
    for sql in (
        "INSERT INTO supplier_payment_allocations (payment_id, amount) VALUES (1, 5)",
        "INSERT INTO supplier_payment_allocations (payment_id, purchase_invoice_id, amount) VALUES (1, 1, 0)",
        "INSERT INTO supplier_payment_allocations (payment_id, purchase_invoice_id, amount) VALUES (1, 99, 5)",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute(sql)
    test_db.execute("INSERT INTO supplier_payment_allocations (payment_id, purchase_invoice_id, amount) VALUES (1, 1, 100)")
    with pytest.raises(sqlite3.IntegrityError):
        test_db.execute("INSERT INTO supplier_payment_allocations (payment_id, purchase_invoice_id, amount) VALUES (1, 1, 1)")
    test_db.execute("DELETE FROM supplier_payments WHERE id = 1")
    assert test_db.execute("SELECT COUNT(*) FROM supplier_payment_allocations").fetchone()[0] == 0  # cascade


def test_audit_triggers_are_generated_for_the_new_columns(test_db):
    text = (MIGRATIONS_DIR / MIGRATION).read_text(encoding="utf-8")
    for table in ("purchase_invoices", "material_purchases", "product_purchases", "supplier_payment_allocations"):
        columns = [dict(r) for r in test_db.execute(f"PRAGMA table_info({table})")]
        assert audit_trigger_sql(table, columns).strip() in text, table
    _invoice(test_db, notes="n")
    test_db.execute("UPDATE purchase_invoices SET notes = 'm' WHERE id = 1")
    rows = test_db.execute("SELECT action, before_json FROM audit_log WHERE entity_type = 'purchase_invoices' ORDER BY id").fetchall()
    assert [r["action"] for r in rows] == ["INSERT", "UPDATE"]
    assert rows[1]["before_json"] == '{"notes":"n"}'


@pytest.mark.skipif(not LAPTOP_DB.is_file(), reason="this laptop's data/shop.db is not here")
def test_upgrade_of_a_copy_of_the_laptop_database(tmp_path):
    """A copy of data/shop.db (read through SQLite immutable mode, so the file itself is never opened for writing), in a
    temporary folder: when it is at 015, init_db applies 016 and the upgrade assertions and the integrity check run."""
    copy = tmp_path / "shop.db"
    source = sqlite3.connect(f"file:{LAPTOP_DB.as_posix()}?mode=ro&immutable=1", uri=True)
    target = sqlite3.connect(copy)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    conn = get_connection(str(copy))
    try:
        applied = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
        if MIGRATION in applied or "015_supplier_payables_purchase_status.sql" not in applied:
            pytest.skip("this laptop's data/shop.db is not at migration 015: no 016 upgrade to test")
        before = _snapshot(conn)
    finally:
        conn.close()
    init_db(str(copy))
    conn = get_connection(str(copy))
    try:
        _check_upgraded(conn, before)
    finally:
        conn.close()
    assert integrity_main(["--db", str(copy)]) == 0
