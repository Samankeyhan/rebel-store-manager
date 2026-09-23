-- ============================================================
-- Made-to-order products + فندک (lighter) category
--
-- SQLite CHECK constraints cannot be altered in place, so the
-- products table is rebuilt per SQLite's documented procedure:
-- create the new table with the extended CHECK, copy every row
-- and column, drop the old table, rename, then recreate every
-- index and trigger that existed on it. products has exactly one
-- such object — trg_products_updated_at (verified against
-- migrations/001_initial_schema.sql; no CREATE INDEX targets
-- products directly, only FK columns on other tables reference
-- it, and those tables are untouched by this rebuild).
--
-- db/connection.py wraps this file in BEGIN...COMMIT and toggles
-- PRAGMA foreign_keys off/on around it, per that same procedure.
-- ============================================================

CREATE TABLE products_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL CHECK (category IN (
                        'ALBUM', 'CASSETTE', 'VINYL', 'MIRROR',
                        'POSTER', 'STICKER', 'TSHIRT', 'OTHER', 'فندک'
                    )),
    retail_price    INTEGER NOT NULL CHECK (retail_price >= 0),
    wholesale_price INTEGER NOT NULL CHECK (wholesale_price >= 0),
    current_stock   INTEGER NOT NULL DEFAULT 0 CHECK (current_stock >= 0),
    unit_cost       INTEGER CHECK (unit_cost IS NULL OR unit_cost >= 0),
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    made_to_order   INTEGER NOT NULL DEFAULT 0 CHECK (made_to_order IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT
);

INSERT INTO products_new (
    id, name, category, retail_price, wholesale_price,
    current_stock, unit_cost, is_active, created_at, updated_at
)
SELECT
    id, name, category, retail_price, wholesale_price,
    current_stock, unit_cost, is_active, created_at, updated_at
FROM products;

DROP TABLE products;

ALTER TABLE products_new RENAME TO products;

CREATE TRIGGER trg_products_updated_at
AFTER UPDATE ON products
BEGIN
    UPDATE products SET updated_at = datetime('now') WHERE id = NEW.id;
END;
