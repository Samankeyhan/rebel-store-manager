-- ============================================================
-- User-editable categories for products and materials
--
-- Replaces the fixed product category list (the CHECK on
-- products.category from 004, mirrored by db/constants.py) with a
-- categories table: two separate trees (kind PRODUCT / MATERIAL),
-- two levels (top-level, optional subcategory).
--
-- 1. Create categories and seed the nine old fixed product
--    categories as top-level PRODUCT rows, named in Persian.
-- 2. Compute each product's category_id from its old code via a
--    fixed code -> name map. If any product fails to match, the guard
--    insert fails with a named CHECK and the whole migration rolls
--    back (db/connection.py runs this file in one transaction), so
--    no product is ever left without a category or silently dropped.
-- 3. Rebuild products (SQLite cannot add NOT NULL / drop a CHECK in
--    place) so category_id is NOT NULL and the old category column
--    becomes a nullable legacy column with no CHECK. Same procedure
--    as 004; products has exactly one dependent object,
--    trg_products_updated_at, recreated below.
-- 4. Add a nullable materials.category_id (materials had no
--    category; none are invented).
--
-- products.category is kept for readers not yet migrated; new
-- products store NULL there. Dropping it is a later migration.
-- ============================================================

CREATE TABLE categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL CHECK (kind IN ('PRODUCT', 'MATERIAL')),
    name        TEXT NOT NULL CHECK (length(trim(name)) > 0),
    parent_id   INTEGER REFERENCES categories(id),
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT
);

-- Names are unique among siblings. Two partial indexes because a
-- UNIQUE over a nullable parent_id treats every NULL as distinct.
CREATE UNIQUE INDEX idx_categories_top_level_name
    ON categories(kind, name) WHERE parent_id IS NULL;
CREATE UNIQUE INDEX idx_categories_child_name
    ON categories(parent_id, name) WHERE parent_id IS NOT NULL;
CREATE INDEX idx_categories_parent ON categories(parent_id);

CREATE TRIGGER trg_categories_updated_at
AFTER UPDATE ON categories
BEGIN
    UPDATE categories SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TEMP TABLE _legacy_category_map (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
INSERT INTO _legacy_category_map (code, name) VALUES
    ('ALBUM',    'آلبوم'),
    ('CASSETTE', 'کاست'),
    ('VINYL',    'وینیل'),
    ('MIRROR',   'آینه'),
    ('POSTER',   'پوستر'),
    ('STICKER',  'استیکر'),
    ('TSHIRT',   'تی‌شرت'),
    ('OTHER',    'سایر'),
    ('فندک',     'فندک');

INSERT INTO categories (kind, name, parent_id)
SELECT 'PRODUCT', name, NULL FROM _legacy_category_map ORDER BY rowid;

-- Each product's seeded category, looked up from its old code. A view
-- (not an UPDATE on products) so the backfill never fires
-- trg_products_updated_at and every row's updated_at is preserved.
CREATE TEMP VIEW _product_category_backfill AS
SELECT p.id AS product_id, c.id AS category_id
FROM products p
LEFT JOIN _legacy_category_map m ON m.code = p.category
LEFT JOIN categories c
  ON c.name = m.name AND c.kind = 'PRODUCT' AND c.parent_id IS NULL;

-- Abort (and roll back everything above) if any product's old
-- category string had no seeded match.
CREATE TEMP TABLE _backfill_guard (
    unmatched INTEGER
        CONSTRAINT every_product_category_must_match_a_seeded_category
        CHECK (unmatched = 0)
);
INSERT INTO _backfill_guard (unmatched)
SELECT COUNT(*) FROM _product_category_backfill WHERE category_id IS NULL;

CREATE TABLE products_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    category        TEXT,
    category_id     INTEGER NOT NULL REFERENCES categories(id),
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
    id, name, category, category_id, retail_price, wholesale_price,
    current_stock, unit_cost, is_active, made_to_order, created_at, updated_at
)
SELECT
    p.id, p.name, p.category, b.category_id, p.retail_price, p.wholesale_price,
    p.current_stock, p.unit_cost, p.is_active, p.made_to_order, p.created_at, p.updated_at
FROM products p
JOIN _product_category_backfill b ON b.product_id = p.id;

DROP VIEW _product_category_backfill;
DROP TABLE products;

ALTER TABLE products_new RENAME TO products;

CREATE TRIGGER trg_products_updated_at
AFTER UPDATE ON products
BEGIN
    UPDATE products SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE INDEX idx_products_category ON products(category_id);

ALTER TABLE materials ADD COLUMN category_id INTEGER REFERENCES categories(id);
CREATE INDEX idx_materials_category ON materials(category_id);

DROP TABLE _backfill_guard;
DROP TABLE _legacy_category_map;
