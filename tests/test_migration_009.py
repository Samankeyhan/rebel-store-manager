"""Migration 009: money is stored in integer Rial (every money column x 10)."""

from pathlib import Path

from db.connection import MIGRATIONS_DIR, get_connection, init_db

BEFORE_009 = tuple(
    name for name in sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql")) if name < "009"
)

# This file is about 009 alone: later migrations change the schema it compares,
# so the 009 tests apply migrations only up to 009.
UP_TO_009 = tuple(
    name for name in sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql")) if name < "010"
)

# Every money column in the schema after 008, by table. Anything not listed
# here must come through the migration byte-identical.
MONEY = {
    "products": ("retail_price", "wholesale_price", "unit_cost"),
    "materials": ("unit_cost",),
    "material_purchases": ("total_paid", "unit_cost"),
    "product_purchases": ("total_paid", "unit_cost"),
    "production_batches": ("unit_cost", "total_cost"),
    "production_batch_materials": ("unit_cost_at_time",),
    "orders": ("shipping_charge", "postage_cost", "transaction_fee", "packaging_cost"),
    "order_items": ("list_price", "discount_amount", "unit_price", "unit_cost_at_time"),
    "stock_movements": ("unit_cost_at_time",),
    "expenses": ("amount",),
    "profit_distributions": ("total_profit_available", "total_amount_distributed"),
    "distribution_shares": ("amount",),
    "postage_batches": ("total_paid",),
    "payment_methods": ("fee_fixed",),
    "settlements": ("expected_amount", "amount_received"),
}
MONEY_SETTINGS = ("default_shipping_charge", "default_postage_estimate")

# Money columns added after 009, stored in Rial from the start (009 never scaled them).
MONEY_SINCE_RIAL = {
    "payment_methods": ("fee_cap",),  # 010
}

OLD_STAMP = "2025-01-02 03:04:05"


def _migrations_dir(tmp_path: Path, name: str, filenames) -> Path:
    dest = tmp_path / name
    dest.mkdir()
    for filename in filenames:
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        (dest / filename).write_text(content, encoding="utf-8")
    return dest


def _seed_every_money_column(conn) -> None:
    """At least one non-NULL, non-zero value in every money column, plus the NULL
    cases (product cost unknown, pre-006 batch total, a non-waste movement) and
    the two signed columns with a negative value."""
    x = conn.execute
    vinyl = x("SELECT id FROM categories WHERE kind = 'PRODUCT' AND name = 'وینیل'").fetchone()[0]
    supplier = x("INSERT INTO suppliers (name) VALUES ('Test Supplier')").lastrowid
    p1 = x(
        "INSERT INTO products (name, category_id, retail_price, wholesale_price, current_stock, unit_cost) "
        "VALUES ('LP', ?, 30001, 20003, 5, 1207)", (vinyl,)
    ).lastrowid
    p2 = x(  # unit_cost unknown: NULL must stay NULL
        "INSERT INTO products (name, category_id, retail_price, wholesale_price, current_stock, unit_cost) "
        "VALUES ('Poster', ?, 9999, 7777, 0, NULL)", (vinyl,)
    ).lastrowid
    m1 = x(
        "INSERT INTO materials (name, type, unit, current_stock, unit_cost) "
        "VALUES ('Box', 'STOCK', 'piece', 12.5, 333)"
    ).lastrowid
    x("INSERT INTO materials (name, type, unit, current_stock, unit_cost) VALUES ('Print', 'SERVICE', 'job', NULL, 4501)")
    x(
        "INSERT INTO material_purchases (material_id, supplier_id, invoice_number, quantity_bought, total_paid, unit_cost) "
        "VALUES (?, ?, 'PUR-000001', 2.5, 1001, 400)", (m1, supplier)
    )
    x(
        "INSERT INTO product_purchases (product_id, supplier_id, invoice_number, quantity_bought, total_paid, unit_cost) "
        "VALUES (?, ?, 'PUR-000002', 3, 3621, 1207)", (p1, supplier)
    )
    b1 = x(
        "INSERT INTO production_batches (product_id, quantity_produced, unit_cost, created_at, total_cost) "
        "VALUES (?, 4, 251, '2026-01-01 10:00:00', 1003)", (p1,)
    ).lastrowid
    x(  # pre-006 batch: total_cost NULL stays NULL
        "INSERT INTO production_batches (product_id, quantity_produced, unit_cost) VALUES (?, 1, 99)", (p1,)
    )
    x(
        "INSERT INTO production_batch_materials (production_batch_id, material_id, quantity_used, unit_cost_at_time) "
        "VALUES (?, ?, 1.25, 333)", (b1, m1)
    )
    kit = x("INSERT INTO packaging_kits (name) VALUES ('Box kit')").lastrowid
    x("INSERT INTO packaging_kit_items (kit_id, material_id, quantity) VALUES (?, ?, 1.5)", (kit, m1))
    method = x(
        "INSERT INTO payment_methods (name, fee_bps, fee_fixed, settlement_rule, settlement_days) "
        "VALUES ('Gateway', 150, 503, 'DAY_OF_NEXT_MONTH', 7)"
    ).lastrowid
    settlement = x(
        "INSERT INTO settlements (payment_method_id, settled_date, jalali_year, jalali_month, expected_amount, amount_received) "
        "VALUES (?, '2026-09-29', 1405, 6, -1234, 0)", (method,)
    ).lastrowid
    x(
        "INSERT INTO settlements (payment_method_id, settled_date, expected_amount, amount_received) "
        "VALUES (?, '2026-09-30', 5003, 4999)", (method,)
    )
    order = x(
        "INSERT INTO orders (invoice_number, order_date, status, channel, customer_name, shipping_charge, "
        "postage_cost, transaction_fee, packaging_kit_id, packaging_cost, stock_committed, payment_method_id, "
        "payment_reference, paid_date, expected_settlement_date, paid_jalali_year, paid_jalali_month, settlement_id) "
        "VALUES ('INV-000001', '2026-09-10 08:00:00', 'COMPLETED', 'WEBSITE', 'Test Buyer', 18001, 2503, 457, ?, "
        "333, 1, ?, 'REF-1', '2026-09-10', '2026-09-29', 1405, 6, ?)", (kit, method, settlement)
    ).lastrowid
    x(
        "INSERT INTO order_items (order_id, product_id, quantity, list_price, discount_amount, discount_reason, "
        "unit_price, unit_cost_at_time) VALUES (?, ?, 2, 60002, 7, 'promo', 29997, 1207)", (order, p1)
    )
    x(
        "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason, reference_order_id, unit_cost_at_time) "
        "VALUES ('PRODUCT', ?, -1, 'WASTE', NULL, 1207)", (p1,)
    )
    x(  # a non-waste movement has no cost: NULL stays NULL
        "INSERT INTO stock_movements (item_type, item_id, quantity_change, reason, reference_order_id) "
        "VALUES ('PRODUCT', ?, -2, 'SALE', ?)", (p1, order)
    )
    category = x("INSERT INTO expense_categories (name) VALUES ('Ads')").lastrowid
    x("INSERT INTO expenses (expense_category_id, amount, description) VALUES (?, 12345, 'ad')", (category,))
    partner = x("INSERT INTO partners (name, current_percentage) VALUES ('Partner A', 100)").lastrowid
    distribution = x(
        "INSERT INTO profit_distributions (period_start, period_end, total_profit_available, total_amount_distributed) "
        "VALUES ('2026-01-01', '2026-01-31', -777, 0)"
    ).lastrowid
    x(
        "INSERT INTO profit_distributions (period_start, period_end, total_profit_available, total_amount_distributed) "
        "VALUES ('2026-02-01', '2026-02-28', 90001, 50003)"
    )
    x(
        "INSERT INTO distribution_shares (distribution_id, partner_id, percentage_at_time, amount) "
        "VALUES (?, ?, 100.0, 50003)", (distribution, partner)
    )
    x("INSERT INTO postage_batches (total_paid, order_count) VALUES (60001, 3)")
    x("UPDATE settings SET value = '250003' WHERE key = 'default_shipping_charge'")
    x("UPDATE settings SET value = '45001' WHERE key = 'default_postage_estimate'")
    conn.commit()
    # A known old updated_at on every table that has one. The AFTER UPDATE
    # triggers would overwrite it with datetime('now'), so each trigger is
    # dropped for this one UPDATE and recreated from its exact saved SQL.
    triggers = _schema_objects(conn, "trigger")
    for table in ("products", "materials", "payment_methods", "suppliers", "expense_categories",
                  "partners", "packaging_kits", "categories"):
        trigger = f"trg_{table}_updated_at"
        if trigger in triggers:
            x(f"DROP TRIGGER {trigger}")
        x(f"UPDATE {table} SET updated_at = '{OLD_STAMP}'")
        if trigger in triggers:
            x(triggers[trigger])
    conn.commit()
    assert _schema_objects(conn, "trigger") == triggers


def _snapshot(conn) -> dict:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT IN ('sqlite_sequence', 'schema_migrations')"
    )]
    return {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in tables}


def _schema_objects(conn, kind: str) -> dict:
    return {r["name"]: r["sql"] for r in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = ? AND name NOT LIKE 'sqlite_%'", (kind,)
    )}


def _at_008_with_data(tmp_path):
    db_path = tmp_path / "shop.db"
    assert BEFORE_009[-1] == "008_payment_methods_settlements.sql"
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "at_008", BEFORE_009)))
    conn = get_connection(str(db_path))
    try:
        _seed_every_money_column(conn)
    finally:
        conn.close()
    return db_path


def test_009_multiplies_every_money_column_and_nothing_else(tmp_path):
    db_path = _at_008_with_data(tmp_path)

    conn = get_connection(str(db_path))
    try:
        before = _snapshot(conn)
        triggers_before = _schema_objects(conn, "trigger")
        indexes_before = _schema_objects(conn, "index")
        tables_before = _schema_objects(conn, "table")
    finally:
        conn.close()

    # Every money column holds at least one non-zero value, so x 10 is visible.
    for table, columns in MONEY.items():
        for column in columns:
            assert any(row[column] for row in before[table]), (table, column)

    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "up_to_009", UP_TO_009)))

    conn = get_connection(str(db_path))
    try:
        after = _snapshot(conn)
        applied = [r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")]
        triggers_after = _schema_objects(conn, "trigger")
        indexes_after = _schema_objects(conn, "index")
        tables_after = _schema_objects(conn, "table")
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()

    assert "009_rial_storage.sql" in applied
    assert [tuple(r) for r in integrity] == [("ok",)]
    assert fk == []
    # Schema unchanged: same tables, and every trigger and index definition byte-identical.
    assert tables_after == tables_before
    assert triggers_after == triggers_before
    assert indexes_after == indexes_before

    assert set(after) == set(before)
    for table, rows_before in before.items():
        rows_after = after[table]
        assert len(rows_after) == len(rows_before), table
        money = set(MONEY.get(table, ()))
        for row_before, row_after in zip(rows_before, rows_after, strict=True):
            assert set(row_after) == set(row_before), table
            for column, value in row_before.items():
                if table == "settings" and column == "value" and row_before["key"] in MONEY_SETTINGS:
                    assert row_after[column] == str(int(value) * 10), (table, row_before["key"])
                elif column in money:
                    expected = None if value is None else value * 10
                    assert row_after[column] == expected, (table, column, value)
                else:
                    assert row_after[column] == value, (table, column)

    # updated_at never changed (the triggers were dropped for the UPDATEs).
    for table in ("products", "materials", "payment_methods"):
        assert {row["updated_at"] for row in after[table]} == {OLD_STAMP}, table

    # The settings: money x 10 as integer strings, everything else identical.
    settings = {r["key"]: r["value"] for r in after["settings"]}
    assert settings["default_shipping_charge"] == "2500030"
    assert settings["default_postage_estimate"] == "450010"


def test_009_triggers_still_fire_after_the_migration(tmp_path):
    db_path = _at_008_with_data(tmp_path)
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "up_to_009", UP_TO_009)))

    conn = get_connection(str(db_path))
    try:
        conn.execute("UPDATE products SET name = 'LP renamed' WHERE name = 'LP'")
        conn.execute("UPDATE materials SET name = 'Box renamed' WHERE name = 'Box'")
        conn.commit()
        product = conn.execute("SELECT updated_at FROM products WHERE name = 'LP renamed'").fetchone()
        material = conn.execute("SELECT updated_at FROM materials WHERE name = 'Box renamed'").fetchone()
        untouched = conn.execute("SELECT updated_at FROM products WHERE name = 'Poster'").fetchone()
    finally:
        conn.close()
    assert product["updated_at"] != OLD_STAMP
    assert material["updated_at"] != OLD_STAMP
    assert untouched["updated_at"] == OLD_STAMP


def test_009_checks_still_hold_and_null_money_stays_null(tmp_path):
    db_path = _at_008_with_data(tmp_path)
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "up_to_009", UP_TO_009)))

    conn = get_connection(str(db_path))
    try:
        assert conn.execute("SELECT unit_cost FROM products WHERE name = 'Poster'").fetchone()[0] is None
        assert conn.execute(
            "SELECT COUNT(*) FROM production_batches WHERE total_cost IS NULL"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE unit_cost_at_time IS NULL"
        ).fetchone()[0] == 1
        # discount_amount <= list_price survives x 10.
        item = conn.execute("SELECT list_price, discount_amount FROM order_items").fetchone()
        assert (item["list_price"], item["discount_amount"]) == (600020, 70)
        # Signed columns keep their sign.
        assert conn.execute(
            "SELECT MIN(total_profit_available) FROM profit_distributions"
        ).fetchone()[0] == -7770
        assert conn.execute("SELECT MIN(expected_amount) FROM settlements").fetchone()[0] == -12340
    finally:
        conn.close()


def test_every_numeric_column_is_classified(tmp_path):
    """A new numeric column must be added to MONEY (and to a later migration),
    to MONEY_SINCE_RIAL (money added already in Rial), or to this list of
    non-money columns — never silently left out."""
    non_money = {
        "id", "name", "current_stock", "is_active", "made_to_order", "category_id", "parent_id",
        "quantity_bought", "quantity_needed", "quantity_produced", "quantity_used", "quantity",
        "quantity_change", "item_id", "material_id", "supplier_id", "product_id", "order_id",
        "production_batch_id", "reference_order_id", "reference_production_batch_id",
        "expense_category_id", "distribution_id", "partner_id", "kit_id", "packaging_kit_id",
        "payment_method_id", "settlement_id", "default_packaging_kit_id", "default_payment_method_id",
        "stock_committed", "applies_shipping_charge", "applies_postage", "paid_jalali_year",
        "paid_jalali_month", "jalali_year", "jalali_month", "current_percentage",
        "percentage_at_time", "order_count", "value", "fee_bps", "settlement_days", "seq",
    }
    db_path = tmp_path / "shop.db"
    init_db(str(db_path))
    conn = get_connection(str(db_path))
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT IN ('schema_migrations', 'sqlite_sequence')"
        )]
        unclassified = []
        for table in tables:
            for col in conn.execute(f"PRAGMA table_info({table})"):
                if col["type"] in ("INTEGER", "REAL") and col["name"] not in non_money:
                    if col["name"] not in MONEY.get(table, ()) + MONEY_SINCE_RIAL.get(table, ()):
                        unclassified.append(f"{table}.{col['name']}")
    finally:
        conn.close()
    assert unclassified == []
