-- ============================================================
-- Name keys: duplicate-name protection across spelling variants
--
-- name_key is the comparison key of `name` (db/names.py name_key: Arabic/Persian
-- letter and digit variants, ZWNJ, case and width folded). It is NULL for every
-- existing row here; init_db fills it from Python (db/name_keys.py) because SQL
-- cannot compute it. Rows whose key collides with another row stay NULL, so
-- nothing is merged, renamed or deleted. The partial unique indexes ignore NULLs.
--
-- 1. name_key on every table with a user-typed name.
-- 2. Unique indexes on it. The existing UNIQUE(name) / sibling indexes stay.
--    Categories: unique among siblings, as before (top level per kind).
-- 3. Each updated_at trigger is recreated, identical except that it fires only
--    AFTER UPDATE OF the business columns: the name_key backfill must not move
--    updated_at. A column added to one of these tables later must be added to
--    its trigger (tests/test_migration_013.py checks this).
-- Audit triggers need no change: name_key is in db/audit.py UNAUDITED_COLUMNS,
-- so their generated SQL is unchanged.
-- ============================================================

ALTER TABLE products ADD COLUMN name_key TEXT;
ALTER TABLE materials ADD COLUMN name_key TEXT;
ALTER TABLE suppliers ADD COLUMN name_key TEXT;
ALTER TABLE partners ADD COLUMN name_key TEXT;
ALTER TABLE categories ADD COLUMN name_key TEXT;
ALTER TABLE payment_methods ADD COLUMN name_key TEXT;
ALTER TABLE packaging_kits ADD COLUMN name_key TEXT;
ALTER TABLE expense_categories ADD COLUMN name_key TEXT;

CREATE UNIQUE INDEX ux_products_name_key ON products(name_key) WHERE name_key IS NOT NULL;
CREATE UNIQUE INDEX ux_materials_name_key ON materials(name_key) WHERE name_key IS NOT NULL;
CREATE UNIQUE INDEX ux_suppliers_name_key ON suppliers(name_key) WHERE name_key IS NOT NULL;
CREATE UNIQUE INDEX ux_partners_name_key ON partners(name_key) WHERE name_key IS NOT NULL;
CREATE UNIQUE INDEX ux_categories_top_level_name_key
    ON categories(kind, name_key) WHERE parent_id IS NULL AND name_key IS NOT NULL;
CREATE UNIQUE INDEX ux_categories_child_name_key
    ON categories(parent_id, name_key) WHERE parent_id IS NOT NULL AND name_key IS NOT NULL;
CREATE UNIQUE INDEX ux_payment_methods_name_key ON payment_methods(name_key) WHERE name_key IS NOT NULL;
CREATE UNIQUE INDEX ux_packaging_kits_name_key ON packaging_kits(name_key) WHERE name_key IS NOT NULL;
CREATE UNIQUE INDEX ux_expense_categories_name_key ON expense_categories(name_key) WHERE name_key IS NOT NULL;

DROP TRIGGER trg_suppliers_updated_at;
CREATE TRIGGER trg_suppliers_updated_at
AFTER UPDATE OF id, name, phone, email, website, notes, created_at ON suppliers
BEGIN
    UPDATE suppliers SET updated_at = datetime('now') WHERE id = NEW.id;
END;

DROP TRIGGER trg_expense_categories_updated_at;
CREATE TRIGGER trg_expense_categories_updated_at
AFTER UPDATE OF id, name, is_active, created_at ON expense_categories
BEGIN
    UPDATE expense_categories SET updated_at = datetime('now') WHERE id = NEW.id;
END;

DROP TRIGGER trg_products_updated_at;
CREATE TRIGGER trg_products_updated_at
AFTER UPDATE OF id, name, category, category_id, retail_price, wholesale_price, current_stock, unit_cost, is_active, made_to_order, created_at ON products
BEGIN
    UPDATE products SET updated_at = datetime('now') WHERE id = NEW.id;
END;

DROP TRIGGER trg_materials_updated_at;
CREATE TRIGGER trg_materials_updated_at
AFTER UPDATE OF id, name, type, unit, current_stock, unit_cost, is_active, created_at, category_id, min_stock ON materials
BEGIN
    UPDATE materials SET updated_at = datetime('now') WHERE id = NEW.id;
END;

DROP TRIGGER trg_categories_updated_at;
CREATE TRIGGER trg_categories_updated_at
AFTER UPDATE OF id, kind, name, parent_id, is_active, created_at ON categories
BEGIN
    UPDATE categories SET updated_at = datetime('now') WHERE id = NEW.id;
END;

DROP TRIGGER trg_packaging_kits_updated_at;
CREATE TRIGGER trg_packaging_kits_updated_at
AFTER UPDATE OF id, name, is_active, created_at ON packaging_kits
BEGIN
    UPDATE packaging_kits SET updated_at = datetime('now') WHERE id = NEW.id;
END;

DROP TRIGGER trg_partners_updated_at;
CREATE TRIGGER trg_partners_updated_at
AFTER UPDATE OF id, name, current_percentage, phone, email, notes, is_active, created_at ON partners
BEGIN
    UPDATE partners SET updated_at = datetime('now') WHERE id = NEW.id;
END;
