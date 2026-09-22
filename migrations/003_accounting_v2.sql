-- ============================================================
-- Accounting v2: packaging kits, postage batches, settings,
-- invoice counters, PER_BATCH recipe costing, stock_committed,
-- PACKAGING stock movements, unit_cost_at_time on stock_movements,
-- UTC date normalization.
--
-- This file contains no PRAGMA foreign_keys / BEGIN / COMMIT of its
-- own — db/connection.py wraps every migration file's content in a
-- single BEGIN...COMMIT (with schema_migrations recorded inside the
-- same script) and toggles PRAGMA foreign_keys off/on around it, so
-- that the stock_movements table rebuild below (step 9) runs with
-- foreign key enforcement off, per SQLite's documented rebuild
-- procedure.
-- ============================================================

-- ------------------------------------------------------------
-- 1. packaging_kits
-- ------------------------------------------------------------

CREATE TABLE packaging_kits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT
);

CREATE TRIGGER trg_packaging_kits_updated_at
AFTER UPDATE ON packaging_kits
BEGIN
    UPDATE packaging_kits SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- ------------------------------------------------------------
-- 2. packaging_kit_items
-- ------------------------------------------------------------

CREATE TABLE packaging_kit_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kit_id      INTEGER NOT NULL REFERENCES packaging_kits(id) ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE RESTRICT,
    quantity    REAL NOT NULL CHECK (quantity > 0),
    UNIQUE (kit_id, material_id)
);

-- ------------------------------------------------------------
-- 3. settings
-- ------------------------------------------------------------

CREATE TABLE settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

-- ------------------------------------------------------------
-- 4. channel_settings (references packaging_kits, so must come
--    after step 1)
-- ------------------------------------------------------------

CREATE TABLE channel_settings (
    channel                     TEXT PRIMARY KEY CHECK (channel IN (
                                    'INSTAGRAM', 'WEBSITE', 'WHOLESALE', 'IN_PERSON', 'OTHER'
                                )),
    applies_shipping_charge     INTEGER NOT NULL DEFAULT 0 CHECK (applies_shipping_charge IN (0, 1)),
    applies_postage             INTEGER NOT NULL DEFAULT 0 CHECK (applies_postage IN (0, 1)),
    default_packaging_kit_id    INTEGER REFERENCES packaging_kits(id) ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- 5. postage_batches
-- ------------------------------------------------------------

CREATE TABLE postage_batches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paid_date       TEXT NOT NULL DEFAULT (datetime('now')),
    total_paid      INTEGER NOT NULL CHECK (total_paid >= 0),
    order_count     INTEGER NOT NULL CHECK (order_count > 0),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- 6. counters (invoice number sequences)
-- ------------------------------------------------------------

CREATE TABLE counters (
    name    TEXT PRIMARY KEY,
    value   INTEGER NOT NULL DEFAULT 0 CHECK (value >= 0)
);

-- ------------------------------------------------------------
-- 7. product_recipe.cost_basis
-- ------------------------------------------------------------

ALTER TABLE product_recipe
    ADD COLUMN cost_basis TEXT NOT NULL DEFAULT 'PER_UNIT'
    CHECK (cost_basis IN ('PER_UNIT', 'PER_BATCH'));

-- ------------------------------------------------------------
-- 8. orders: packaging_kit_id, packaging_cost, stock_committed
-- ------------------------------------------------------------

ALTER TABLE orders ADD COLUMN packaging_kit_id INTEGER REFERENCES packaging_kits(id);

ALTER TABLE orders
    ADD COLUMN packaging_cost INTEGER NOT NULL DEFAULT 0 CHECK (packaging_cost >= 0);

-- Default 1 is correct for existing rows: the old code deducted stock for
-- every order it created, including drafts, so every pre-existing order was
-- already stock-committed.
ALTER TABLE orders
    ADD COLUMN stock_committed INTEGER NOT NULL DEFAULT 1 CHECK (stock_committed IN (0, 1));

-- ------------------------------------------------------------
-- 9. stock_movements rebuild: add 'PACKAGING' reason and
--    unit_cost_at_time. SQLite's documented table-rebuild
--    procedure (create new, copy, drop old, rename, reindex) —
--    every existing row and column survives unchanged.
-- ------------------------------------------------------------

CREATE TABLE stock_movements_new (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type                       TEXT NOT NULL CHECK (item_type IN ('MATERIAL', 'PRODUCT')),
    item_id                         INTEGER NOT NULL,
    quantity_change                 REAL NOT NULL,
    reason                          TEXT NOT NULL CHECK (reason IN (
                                        'PURCHASE', 'PRODUCTION_CONSUMPTION', 'PRODUCTION_OUTPUT',
                                        'SALE', 'RETURN', 'WASTE', 'ADJUSTMENT', 'PACKAGING'
                                    )),
    reference_order_id              INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    reference_production_batch_id   INTEGER REFERENCES production_batches(id) ON DELETE SET NULL,
    movement_date                   TEXT NOT NULL DEFAULT (datetime('now')),
    notes                           TEXT,
    unit_cost_at_time               INTEGER CHECK (unit_cost_at_time IS NULL OR unit_cost_at_time >= 0)
);

INSERT INTO stock_movements_new (
    id, item_type, item_id, quantity_change, reason,
    reference_order_id, reference_production_batch_id, movement_date, notes,
    unit_cost_at_time
)
SELECT
    sm.id, sm.item_type, sm.item_id, sm.quantity_change, sm.reason,
    sm.reference_order_id, sm.reference_production_batch_id, sm.movement_date, sm.notes,
    -- Backfill for existing WASTE/ADJUSTMENT rows: the item's current
    -- unit_cost is the best available figure, since no historical cost was
    -- tracked for these movements before this migration.
    CASE WHEN sm.reason IN ('WASTE', 'ADJUSTMENT') THEN
        CASE sm.item_type
            WHEN 'MATERIAL' THEN (SELECT m.unit_cost FROM materials m WHERE m.id = sm.item_id)
            WHEN 'PRODUCT' THEN (SELECT p.unit_cost FROM products p WHERE p.id = sm.item_id)
        END
    END
FROM stock_movements sm;

DROP TABLE stock_movements;

ALTER TABLE stock_movements_new RENAME TO stock_movements;

CREATE INDEX idx_stock_movements_item              ON stock_movements(item_type, item_id);
CREATE INDEX idx_stock_movements_order             ON stock_movements(reference_order_id);
CREATE INDEX idx_stock_movements_production_batch  ON stock_movements(reference_production_batch_id);

-- ------------------------------------------------------------
-- 10. Seed counters from existing invoice numbers
-- ------------------------------------------------------------

INSERT INTO counters (name, value)
VALUES (
    'INV',
    COALESCE(
        (SELECT MAX(CAST(SUBSTR(invoice_number, 5) AS INTEGER))
         FROM orders
         WHERE invoice_number IS NOT NULL),
        0
    )
);

INSERT INTO counters (name, value)
VALUES (
    'PUR',
    COALESCE(
        (SELECT MAX(v) FROM (
            SELECT MAX(CAST(SUBSTR(invoice_number, 5) AS INTEGER)) AS v
            FROM material_purchases
            WHERE invoice_number IS NOT NULL
            UNION ALL
            SELECT MAX(CAST(SUBSTR(invoice_number, 5) AS INTEGER))
            FROM product_purchases
            WHERE invoice_number IS NOT NULL
        )),
        0
    )
);

-- ------------------------------------------------------------
-- 11. UNIQUE indexes on invoice numbers. NULLs never collide
--     under SQLite UNIQUE-index semantics. If real duplicates
--     exist, this statement itself fails, which rolls back the
--     whole migration (see db/connection.py) — nothing is ever
--     deleted or renumbered to work around it.
-- ------------------------------------------------------------

CREATE UNIQUE INDEX idx_orders_invoice_number_unique
    ON orders(invoice_number) WHERE invoice_number IS NOT NULL;
CREATE UNIQUE INDEX idx_material_purchases_invoice_number_unique
    ON material_purchases(invoice_number) WHERE invoice_number IS NOT NULL;
CREATE UNIQUE INDEX idx_product_purchases_invoice_number_unique
    ON product_purchases(invoice_number) WHERE invoice_number IS NOT NULL;

-- ------------------------------------------------------------
-- 12. Normalize bare "YYYY-MM-DD" dates (entered as local Tehran
--     days) to UTC. Tehran has had a fixed UTC+3:30 offset since
--     2022, so local midnight of day D is UTC (D-1) 20:30:00.
--     Values with a time part already came from datetime('now')
--     and are already UTC — left untouched (length(col) <> 10).
--     profit_distributions.period_start/period_end/distribution_date
--     are NOT touched here: period_start/period_end are calendar
--     days by rule (section 1), and distribution_date is already UTC.
-- ------------------------------------------------------------

UPDATE orders
    SET order_date = datetime(order_date, '-210 minutes')
    WHERE length(order_date) = 10;

UPDATE expenses
    SET expense_date = datetime(expense_date, '-210 minutes')
    WHERE length(expense_date) = 10;

UPDATE material_purchases
    SET purchase_date = datetime(purchase_date, '-210 minutes')
    WHERE length(purchase_date) = 10;

UPDATE product_purchases
    SET purchase_date = datetime(purchase_date, '-210 minutes')
    WHERE length(purchase_date) = 10;

UPDATE production_batches
    SET production_date = datetime(production_date, '-210 minutes')
    WHERE length(production_date) = 10;

UPDATE stock_movements
    SET movement_date = datetime(movement_date, '-210 minutes')
    WHERE length(movement_date) = 10;

-- ------------------------------------------------------------
-- 13. Seed settings and channel_settings
-- ------------------------------------------------------------

INSERT INTO settings (key, value) VALUES ('default_shipping_charge', '180000');
INSERT INTO settings (key, value) VALUES ('postage_estimate_window', '3');
INSERT INTO settings (key, value) VALUES ('default_postage_estimate', '0');
INSERT INTO settings (key, value) VALUES ('timezone', 'Asia/Tehran');

INSERT INTO channel_settings (channel, applies_shipping_charge, applies_postage, default_packaging_kit_id)
VALUES
    ('WEBSITE', 1, 1, NULL),
    ('INSTAGRAM', 1, 1, NULL),
    ('WHOLESALE', 0, 1, NULL),
    ('IN_PERSON', 0, 0, NULL),
    ('OTHER', 0, 0, NULL);
