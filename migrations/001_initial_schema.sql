-- ============================================================
-- Rebel Music Store — Accounting & Inventory
-- Final SQLite schema
-- ============================================================
-- Fixes applied from review:
-- 1. stock_movements.item_type now uses its own MATERIAL/PRODUCT
--    check, not the unrelated STOCK/SERVICE material type.
-- 2. stock_movements can now reference the production_batches row
--    that caused a PRODUCTION_CONSUMPTION / PRODUCTION_OUTPUT move.
-- 3. Wholesale stays a channel value (channel = 'WHOLESALE'),
--    unchanged from the reviewed version.
-- 4. Refund/cancellation revenue handling is left as an app-level
--    concern for now (exclude CANCELLED/REFUNDED/DRAFT in report
--    queries; trigger a RETURN stock_movement when marking REFUNDED).
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- LOOKUP TABLES
-- ============================================================

CREATE TABLE suppliers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT,
    email       TEXT,
    website     TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT
);

CREATE TABLE expense_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT
);

-- ============================================================
-- PRODUCTS
-- ============================================================

CREATE TABLE products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL CHECK (category IN (
                        'ALBUM', 'CASSETTE', 'VINYL', 'MIRROR',
                        'POSTER', 'STICKER', 'TSHIRT', 'OTHER'
                    )),
    retail_price    INTEGER NOT NULL CHECK (retail_price >= 0),
    wholesale_price INTEGER NOT NULL CHECK (wholesale_price >= 0),
    current_stock   INTEGER NOT NULL DEFAULT 0 CHECK (current_stock >= 0),
    unit_cost       INTEGER CHECK (unit_cost IS NULL OR unit_cost >= 0),
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT
);

CREATE TABLE materials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('STOCK', 'SERVICE')),
    unit            TEXT NOT NULL DEFAULT 'piece',
    current_stock   REAL CHECK (current_stock IS NULL OR current_stock >= 0),
    unit_cost       INTEGER NOT NULL CHECK (unit_cost >= 0),
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT,
    CHECK (
        (type = 'SERVICE' AND current_stock IS NULL)
        OR (type = 'STOCK' AND current_stock IS NOT NULL)
    )
);

-- ============================================================
-- PURCHASING
-- ============================================================

CREATE TABLE material_purchases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id     INTEGER NOT NULL REFERENCES materials(id),
    supplier_id     INTEGER REFERENCES suppliers(id),
    invoice_number  TEXT,
    purchase_date   TEXT NOT NULL DEFAULT (datetime('now')),
    quantity_bought REAL NOT NULL CHECK (quantity_bought > 0),
    total_paid      INTEGER NOT NULL CHECK (total_paid >= 0),
    unit_cost       INTEGER NOT NULL CHECK (unit_cost >= 0),
    notes           TEXT
);

CREATE TABLE product_purchases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id),
    supplier_id     INTEGER REFERENCES suppliers(id),
    invoice_number  TEXT,
    purchase_date   TEXT NOT NULL DEFAULT (datetime('now')),
    quantity_bought INTEGER NOT NULL CHECK (quantity_bought > 0),
    total_paid      INTEGER NOT NULL CHECK (total_paid >= 0),
    unit_cost       INTEGER NOT NULL CHECK (unit_cost >= 0),
    notes           TEXT
);

-- ============================================================
-- MANUFACTURING
-- ============================================================

CREATE TABLE product_recipe (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    material_id     INTEGER NOT NULL REFERENCES materials(id) ON DELETE RESTRICT,
    quantity_needed REAL NOT NULL CHECK (quantity_needed > 0),
    UNIQUE (product_id, material_id)
);

CREATE TABLE production_batches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id          INTEGER NOT NULL REFERENCES products(id),
    quantity_produced   INTEGER NOT NULL CHECK (quantity_produced > 0),
    unit_cost           INTEGER NOT NULL CHECK (unit_cost >= 0),
    production_date     TEXT NOT NULL DEFAULT (datetime('now')),
    notes               TEXT
);

CREATE TABLE production_batch_materials (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    production_batch_id     INTEGER NOT NULL REFERENCES production_batches(id) ON DELETE CASCADE,
    material_id             INTEGER NOT NULL REFERENCES materials(id) ON DELETE RESTRICT,
    quantity_used           REAL NOT NULL CHECK (quantity_used > 0),
    unit_cost_at_time       INTEGER NOT NULL CHECK (unit_cost_at_time >= 0)
);

-- ============================================================
-- SALES
-- ============================================================

CREATE TABLE orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number      TEXT,
    order_date          TEXT NOT NULL DEFAULT (datetime('now')),
    status              TEXT NOT NULL CHECK (status IN (
                            'DRAFT', 'PENDING', 'PAID', 'COMPLETED', 'CANCELLED', 'REFUNDED'
                        )),
    channel             TEXT NOT NULL CHECK (channel IN (
                            'INSTAGRAM', 'WEBSITE', 'WHOLESALE', 'IN_PERSON', 'OTHER'
                        )),
    customer_name       TEXT,
    shipping_charge     INTEGER NOT NULL DEFAULT 0 CHECK (shipping_charge >= 0),
    postage_cost        INTEGER NOT NULL DEFAULT 0 CHECK (postage_cost >= 0),
    transaction_fee     INTEGER NOT NULL DEFAULT 0 CHECK (transaction_fee >= 0),
    notes               TEXT
);

CREATE TABLE order_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id            INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id          INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    list_price          INTEGER NOT NULL CHECK (list_price >= 0),
    discount_amount     INTEGER NOT NULL DEFAULT 0 CHECK (discount_amount >= 0 AND discount_amount <= list_price),
    discount_reason     TEXT,
    unit_price          INTEGER NOT NULL CHECK (unit_price >= 0),
    unit_cost_at_time   INTEGER NOT NULL CHECK (unit_cost_at_time >= 0)
);

-- ============================================================
-- INVENTORY
-- ============================================================

-- Fix 1: item_type describes what item_id points into
-- (materials vs products) — a different concept from
-- materials.type (STOCK/SERVICE), so it gets its own check.
CREATE TABLE stock_movements (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type                   TEXT NOT NULL CHECK (item_type IN ('MATERIAL', 'PRODUCT')),
    item_id                     INTEGER NOT NULL,
    quantity_change             REAL NOT NULL,
    reason                      TEXT NOT NULL CHECK (reason IN (
                                    'PURCHASE', 'PRODUCTION_CONSUMPTION', 'PRODUCTION_OUTPUT',
                                    'SALE', 'RETURN', 'WASTE', 'ADJUSTMENT'
                                )),
    reference_order_id          INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    -- Fix 2: traceability back to the production run that caused
    -- a PRODUCTION_CONSUMPTION / PRODUCTION_OUTPUT movement.
    reference_production_batch_id INTEGER REFERENCES production_batches(id) ON DELETE SET NULL,
    movement_date               TEXT NOT NULL DEFAULT (datetime('now')),
    notes                       TEXT
);

-- ============================================================
-- ACCOUNTING
-- ============================================================

CREATE TABLE expenses (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_category_id     INTEGER NOT NULL REFERENCES expense_categories(id),
    expense_date            TEXT NOT NULL DEFAULT (datetime('now')),
    amount                  INTEGER NOT NULL CHECK (amount >= 0),
    description             TEXT
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_material_purchases_material_id   ON material_purchases(material_id);
CREATE INDEX idx_material_purchases_supplier_id    ON material_purchases(supplier_id);
CREATE INDEX idx_product_purchases_product_id      ON product_purchases(product_id);
CREATE INDEX idx_product_purchases_supplier_id     ON product_purchases(supplier_id);
CREATE INDEX idx_product_recipe_product_id         ON product_recipe(product_id);
CREATE INDEX idx_production_batches_product_id     ON production_batches(product_id);
CREATE INDEX idx_production_batch_materials_batch  ON production_batch_materials(production_batch_id);
CREATE INDEX idx_order_items_order_id              ON order_items(order_id);
CREATE INDEX idx_order_items_product_id            ON order_items(product_id);
CREATE INDEX idx_orders_date                       ON orders(order_date);
CREATE INDEX idx_orders_status                     ON orders(status);
CREATE INDEX idx_orders_channel                     ON orders(channel);
CREATE INDEX idx_stock_movements_item              ON stock_movements(item_type, item_id);
CREATE INDEX idx_stock_movements_order             ON stock_movements(reference_order_id);
CREATE INDEX idx_stock_movements_production_batch  ON stock_movements(reference_production_batch_id);
CREATE INDEX idx_expenses_date                     ON expenses(expense_date);
CREATE INDEX idx_expenses_category                 ON expenses(expense_category_id);

-- ============================================================
-- updated_at TRIGGERS
-- SQLite does not auto-update this column, so it needs an
-- explicit trigger for every table that has one.
-- ============================================================

CREATE TRIGGER trg_suppliers_updated_at
AFTER UPDATE ON suppliers
BEGIN
    UPDATE suppliers SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_expense_categories_updated_at
AFTER UPDATE ON expense_categories
BEGIN
    UPDATE expense_categories SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_products_updated_at
AFTER UPDATE ON products
BEGIN
    UPDATE products SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_materials_updated_at
AFTER UPDATE ON materials
BEGIN
    UPDATE materials SET updated_at = datetime('now') WHERE id = NEW.id;
END;