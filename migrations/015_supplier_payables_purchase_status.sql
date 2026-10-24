-- ============================================================
-- Supplier payables and purchase status (docs/accounting-rules.md sections 21 and 22;
-- docs/plans/2026-10-payables-purchase-correction.md)
--
-- 1. What the shop owes its suppliers: a purchase's total_paid is its invoice total;
--    supplier_payments records money paid to a supplier and supplier_payment_allocations
--    splits each payment over that supplier's purchases. paid, outstanding and the
--    payment status are computed on read (db/supplier_payments.py), never stored.
-- 2. The columns a later slice needs to cancel or correct a purchase entered by mistake
--    (status ACTIVE/CANCELLED, the reason and moment, replaces_purchase_id, the purchase's
--    own stock movement and its cancel movement, and the item's unit cost just before and
--    just after the purchase). Until that slice ships every row stays ACTIVE.
--
-- The status CHECK must be part of the table, so material_purchases and product_purchases
-- are rebuilt with SQLite's documented procedure (create new, copy, drop old, rename,
-- recreate indexes and triggers). The migration runner turns foreign keys off around this
-- script (db/connection.py _apply_migration), so DROP TABLE cascades into nothing.
--
-- Objects that reference the purchase tables (checked against a database built from
-- 001-014 and the test shop database before writing this file):
--   - indexes idx_<kind>_purchases_<item>_id, idx_<kind>_purchases_supplier_id and
--     idx_<kind>_purchases_invoice_number_unique: dropped with the old tables, recreated
--     below exactly as before.
--   - triggers trg_audit_<kind>_purchases_ins/upd/del: dropped with the old tables,
--     recreated below from db/audit.py audit_trigger_sql for the new columns.
--   - no foreign key, view or other trigger names a purchase table (the new allocation
--     table below is the first foreign key into them).
--
-- Every row and value is copied unchanged, ids included, and the AUTOINCREMENT high-water
-- mark is carried over. The copy and the payment backfill run before any audit trigger
-- exists, so they write no audit rows (the purchase tables have no updated_at).
--
-- Filled on the copied rows (NULL where the history does not tell):
--   stock_movement_id   the single PURCHASE movement of that item whose note the purchase
--                       code wrote ('Material purchase #<id> (...' / 'Product purchase #<id> (...').
--   item_cost_before /  from the audit log: the item's UPDATE in the purchase's own audit
--   item_cost_after     operation (its op_id); when that UPDATE did not change unit_cost,
--                       both are the item's last earlier logged unit_cost. item_cost_after
--                       NULL means "not known"; item_cost_before NULL with an after value
--                       means the product had no cost.
-- Backfill: every existing purchase with total_paid > 0 gets one payment of its full total,
-- dated purchase_date, method OTHER, note «پیش از ثبت بدهی‌ها», allocated to it, so no
-- existing purchase shows as owed. A purchase with total 0 owes nothing and gets none.
-- ============================================================

CREATE TEMP TABLE m015_sequence AS
    SELECT name, seq FROM sqlite_sequence WHERE name IN ('material_purchases', 'product_purchases');

-- the audit UPDATE of the purchased item inside each purchase's own operation
CREATE TEMP TABLE m015_item_update AS
    SELECT 'material_purchases' AS tbl, p.id AS purchase_id,
           (SELECT u.id FROM audit_log AS u
            WHERE u.entity_type = 'materials' AND u.entity_id = CAST(p.material_id AS TEXT)
              AND u.action = 'UPDATE'
              AND u.op_id = (SELECT i.op_id FROM audit_log AS i
                             WHERE i.entity_type = 'material_purchases' AND i.entity_id = CAST(p.id AS TEXT)
                               AND i.action = 'INSERT' AND i.op_id IS NOT NULL
                             ORDER BY i.id LIMIT 1)
            ORDER BY u.id LIMIT 1) AS update_id
    FROM material_purchases AS p
    UNION ALL
    SELECT 'product_purchases', p.id,
           (SELECT u.id FROM audit_log AS u
            WHERE u.entity_type = 'products' AND u.entity_id = CAST(p.product_id AS TEXT)
              AND u.action = 'UPDATE'
              AND u.op_id = (SELECT i.op_id FROM audit_log AS i
                             WHERE i.entity_type = 'product_purchases' AND i.entity_id = CAST(p.id AS TEXT)
                               AND i.action = 'INSERT' AND i.op_id IS NOT NULL
                             ORDER BY i.id LIMIT 1)
            ORDER BY u.id LIMIT 1)
    FROM product_purchases AS p;

-- the item's unit cost just before and just after each purchase (NULL after = not known)
CREATE TEMP TABLE m015_cost AS
    SELECT tbl, purchase_id, after_cost,
           CASE WHEN after_cost IS NULL THEN NULL ELSE before_cost END AS before_cost
    FROM (
        SELECT s.tbl, s.purchase_id,
               CASE
                   WHEN u.id IS NULL THEN NULL
                   WHEN json_type(u.after_json, '$.unit_cost') IS NOT NULL THEN json_extract(u.before_json, '$.unit_cost')
                   ELSE (SELECT json_extract(e.after_json, '$.unit_cost') FROM audit_log AS e
                         WHERE e.entity_type = u.entity_type AND e.entity_id = u.entity_id AND e.id < u.id
                           AND e.action IN ('INSERT', 'UPDATE') AND json_type(e.after_json, '$.unit_cost') IS NOT NULL
                         ORDER BY e.id DESC LIMIT 1)
               END AS before_cost,
               CASE
                   WHEN u.id IS NULL THEN NULL
                   WHEN json_type(u.after_json, '$.unit_cost') IS NOT NULL THEN json_extract(u.after_json, '$.unit_cost')
                   ELSE (SELECT json_extract(e.after_json, '$.unit_cost') FROM audit_log AS e
                         WHERE e.entity_type = u.entity_type AND e.entity_id = u.entity_id AND e.id < u.id
                           AND e.action IN ('INSERT', 'UPDATE') AND json_type(e.after_json, '$.unit_cost') IS NOT NULL
                         ORDER BY e.id DESC LIMIT 1)
               END AS after_cost
        FROM m015_item_update AS s
        LEFT JOIN audit_log AS u ON u.id = s.update_id
    );

-- ------------------------------------------------------------ material_purchases

CREATE TABLE material_purchases_new (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id          INTEGER NOT NULL REFERENCES materials(id),
    supplier_id          INTEGER REFERENCES suppliers(id),
    invoice_number       TEXT,
    purchase_date        TEXT NOT NULL DEFAULT (datetime('now')),
    quantity_bought      REAL NOT NULL CHECK (quantity_bought > 0),
    total_paid           INTEGER NOT NULL CHECK (total_paid >= 0),
    unit_cost            INTEGER NOT NULL CHECK (unit_cost >= 0),
    notes                TEXT,
    status               TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CANCELLED')),
    cancel_reason        TEXT,
    cancelled_at         TEXT,
    replaces_purchase_id INTEGER REFERENCES material_purchases(id),
    stock_movement_id    INTEGER REFERENCES stock_movements(id),
    cancel_movement_id   INTEGER REFERENCES stock_movements(id),
    item_cost_before     INTEGER CHECK (item_cost_before IS NULL OR item_cost_before >= 0),
    item_cost_after      INTEGER CHECK (item_cost_after IS NULL OR item_cost_after >= 0),
    CHECK ((status = 'CANCELLED') = (cancelled_at IS NOT NULL)),
    CHECK (status <> 'CANCELLED' OR length(trim(coalesce(cancel_reason, ''))) > 0),
    CHECK ((status = 'CANCELLED') = (cancel_movement_id IS NOT NULL)),
    CHECK (replaces_purchase_id IS NULL OR replaces_purchase_id <> id),
    CHECK (item_cost_after IS NOT NULL OR item_cost_before IS NULL)
);

INSERT INTO material_purchases_new (
    id, material_id, supplier_id, invoice_number, purchase_date,
    quantity_bought, total_paid, unit_cost, notes,
    stock_movement_id, item_cost_before, item_cost_after
)
SELECT
    p.id, p.material_id, p.supplier_id, p.invoice_number, p.purchase_date,
    p.quantity_bought, p.total_paid, p.unit_cost, p.notes,
    CASE WHEN (SELECT COUNT(*) FROM stock_movements AS m
               WHERE m.reason = 'PURCHASE' AND m.item_type = 'MATERIAL' AND m.item_id = p.material_id
                 AND m.notes LIKE 'Material purchase #' || p.id || ' (%') = 1
         THEN (SELECT m.id FROM stock_movements AS m
               WHERE m.reason = 'PURCHASE' AND m.item_type = 'MATERIAL' AND m.item_id = p.material_id
                 AND m.notes LIKE 'Material purchase #' || p.id || ' (%')
    END,
    c.before_cost, c.after_cost
FROM material_purchases AS p
LEFT JOIN m015_cost AS c ON c.tbl = 'material_purchases' AND c.purchase_id = p.id;

DROP TABLE material_purchases;

ALTER TABLE material_purchases_new RENAME TO material_purchases;

-- ------------------------------------------------------------ product_purchases

CREATE TABLE product_purchases_new (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id           INTEGER NOT NULL REFERENCES products(id),
    supplier_id          INTEGER REFERENCES suppliers(id),
    invoice_number       TEXT,
    purchase_date        TEXT NOT NULL DEFAULT (datetime('now')),
    quantity_bought      INTEGER NOT NULL CHECK (quantity_bought > 0),
    total_paid           INTEGER NOT NULL CHECK (total_paid >= 0),
    unit_cost            INTEGER NOT NULL CHECK (unit_cost >= 0),
    notes                TEXT,
    status               TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CANCELLED')),
    cancel_reason        TEXT,
    cancelled_at         TEXT,
    replaces_purchase_id INTEGER REFERENCES product_purchases(id),
    stock_movement_id    INTEGER REFERENCES stock_movements(id),
    cancel_movement_id   INTEGER REFERENCES stock_movements(id),
    item_cost_before     INTEGER CHECK (item_cost_before IS NULL OR item_cost_before >= 0),
    item_cost_after      INTEGER CHECK (item_cost_after IS NULL OR item_cost_after >= 0),
    CHECK ((status = 'CANCELLED') = (cancelled_at IS NOT NULL)),
    CHECK (status <> 'CANCELLED' OR length(trim(coalesce(cancel_reason, ''))) > 0),
    CHECK ((status = 'CANCELLED') = (cancel_movement_id IS NOT NULL)),
    CHECK (replaces_purchase_id IS NULL OR replaces_purchase_id <> id),
    CHECK (item_cost_after IS NOT NULL OR item_cost_before IS NULL)
);

INSERT INTO product_purchases_new (
    id, product_id, supplier_id, invoice_number, purchase_date,
    quantity_bought, total_paid, unit_cost, notes,
    stock_movement_id, item_cost_before, item_cost_after
)
SELECT
    p.id, p.product_id, p.supplier_id, p.invoice_number, p.purchase_date,
    p.quantity_bought, p.total_paid, p.unit_cost, p.notes,
    CASE WHEN (SELECT COUNT(*) FROM stock_movements AS m
               WHERE m.reason = 'PURCHASE' AND m.item_type = 'PRODUCT' AND m.item_id = p.product_id
                 AND m.notes LIKE 'Product purchase #' || p.id || ' (%') = 1
         THEN (SELECT m.id FROM stock_movements AS m
               WHERE m.reason = 'PURCHASE' AND m.item_type = 'PRODUCT' AND m.item_id = p.product_id
                 AND m.notes LIKE 'Product purchase #' || p.id || ' (%')
    END,
    c.before_cost, c.after_cost
FROM product_purchases AS p
LEFT JOIN m015_cost AS c ON c.tbl = 'product_purchases' AND c.purchase_id = p.id;

DROP TABLE product_purchases;

ALTER TABLE product_purchases_new RENAME TO product_purchases;

-- ------------------------------------------------------------ AUTOINCREMENT marks

DELETE FROM sqlite_sequence WHERE name IN ('material_purchases', 'product_purchases');
INSERT INTO sqlite_sequence (name, seq)
    SELECT 'material_purchases', MAX(seq) FROM (
        SELECT seq FROM temp.m015_sequence WHERE name = 'material_purchases'
        UNION ALL SELECT MAX(id) FROM material_purchases
    )
    HAVING MAX(seq) IS NOT NULL;
INSERT INTO sqlite_sequence (name, seq)
    SELECT 'product_purchases', MAX(seq) FROM (
        SELECT seq FROM temp.m015_sequence WHERE name = 'product_purchases'
        UNION ALL SELECT MAX(id) FROM product_purchases
    )
    HAVING MAX(seq) IS NOT NULL;
DROP TABLE temp.m015_sequence;
DROP TABLE temp.m015_cost;
DROP TABLE temp.m015_item_update;

-- ------------------------------------------------------------ purchase indexes

CREATE INDEX idx_material_purchases_material_id ON material_purchases(material_id);
CREATE INDEX idx_material_purchases_supplier_id ON material_purchases(supplier_id);
CREATE UNIQUE INDEX idx_material_purchases_invoice_number_unique
    ON material_purchases(invoice_number) WHERE invoice_number IS NOT NULL;
CREATE INDEX idx_material_purchases_status ON material_purchases(status);
CREATE UNIQUE INDEX ux_material_purchases_replaces_purchase_id
    ON material_purchases(replaces_purchase_id) WHERE replaces_purchase_id IS NOT NULL;
CREATE UNIQUE INDEX ux_material_purchases_stock_movement_id
    ON material_purchases(stock_movement_id) WHERE stock_movement_id IS NOT NULL;

CREATE INDEX idx_product_purchases_product_id ON product_purchases(product_id);
CREATE INDEX idx_product_purchases_supplier_id ON product_purchases(supplier_id);
CREATE UNIQUE INDEX idx_product_purchases_invoice_number_unique
    ON product_purchases(invoice_number) WHERE invoice_number IS NOT NULL;
CREATE INDEX idx_product_purchases_status ON product_purchases(status);
CREATE UNIQUE INDEX ux_product_purchases_replaces_purchase_id
    ON product_purchases(replaces_purchase_id) WHERE replaces_purchase_id IS NOT NULL;
CREATE UNIQUE INDEX ux_product_purchases_stock_movement_id
    ON product_purchases(stock_movement_id) WHERE stock_movement_id IS NOT NULL;

-- ------------------------------------------------------------ supplier payments

-- One payment to a supplier. supplier_id is NULL only for a payment on purchases that have no
-- supplier. payment_date is a UTC moment, like purchase_date. method is a fixed list
-- (cash, card to card, bank transfer, cheque, other), unrelated to the sales payment_methods.
CREATE TABLE supplier_payments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id  INTEGER REFERENCES suppliers(id),
    payment_date TEXT NOT NULL,
    amount       INTEGER NOT NULL CHECK (amount > 0),
    method       TEXT NOT NULL CHECK (method IN ('CASH', 'CARD', 'BANK_TRANSFER', 'CHEQUE', 'OTHER')),
    reference    TEXT,
    note         TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT
);

-- How a payment is split over purchases: exactly one of the two purchase columns is set.
CREATE TABLE supplier_payment_allocations (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id           INTEGER NOT NULL REFERENCES supplier_payments(id) ON DELETE CASCADE,
    material_purchase_id INTEGER REFERENCES material_purchases(id),
    product_purchase_id  INTEGER REFERENCES product_purchases(id),
    amount               INTEGER NOT NULL CHECK (amount > 0),
    CHECK ((material_purchase_id IS NULL) <> (product_purchase_id IS NULL)),
    UNIQUE (payment_id, material_purchase_id),
    UNIQUE (payment_id, product_purchase_id)
);

CREATE INDEX idx_supplier_payments_supplier_date ON supplier_payments(supplier_id, payment_date);
CREATE INDEX idx_supplier_payment_allocations_payment ON supplier_payment_allocations(payment_id);
CREATE INDEX idx_supplier_payment_allocations_material_purchase
    ON supplier_payment_allocations(material_purchase_id);
CREATE INDEX idx_supplier_payment_allocations_product_purchase
    ON supplier_payment_allocations(product_purchase_id);

-- ------------------------------------------------------------ backfill (no audit rows: no triggers yet)

CREATE TEMP TABLE m015_backfill AS
    SELECT 'MATERIAL' AS kind, id AS purchase_id, supplier_id, purchase_date, total_paid
    FROM material_purchases WHERE total_paid > 0
    UNION ALL
    SELECT 'PRODUCT', id, supplier_id, purchase_date, total_paid
    FROM product_purchases WHERE total_paid > 0
    ORDER BY 1, 2;

INSERT INTO supplier_payments (id, supplier_id, payment_date, amount, method, note)
    SELECT rowid, supplier_id, purchase_date, total_paid, 'OTHER', 'پیش از ثبت بدهی‌ها'
    FROM temp.m015_backfill ORDER BY rowid;

INSERT INTO supplier_payment_allocations (payment_id, material_purchase_id, product_purchase_id, amount)
    SELECT rowid,
           CASE WHEN kind = 'MATERIAL' THEN purchase_id END,
           CASE WHEN kind = 'PRODUCT' THEN purchase_id END,
           total_paid
    FROM temp.m015_backfill ORDER BY rowid;

DROP TABLE temp.m015_backfill;

-- an INSERT ... SELECT that found no rows still leaves a sqlite_sequence row at 0: drop it, as on a fresh table
DELETE FROM sqlite_sequence
    WHERE (name = 'supplier_payments' AND NOT EXISTS (SELECT 1 FROM supplier_payments))
       OR (name = 'supplier_payment_allocations' AND NOT EXISTS (SELECT 1 FROM supplier_payment_allocations));

-- ------------------------------------------------------------ triggers

CREATE TRIGGER trg_supplier_payments_updated_at
AFTER UPDATE OF id, supplier_id, payment_date, amount, method, reference, note, created_at ON supplier_payments
BEGIN
    UPDATE supplier_payments SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Audit triggers (db/audit.py audit_trigger_sql, generated for the columns above).
-- material_purchases
CREATE TRIGGER trg_audit_material_purchases_ins AFTER INSERT ON material_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, after_json, actor, op_id)
    SELECT 'material_purchases', CAST(NEW.id AS TEXT), 'INSERT', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', NEW.id, 'material_id', NEW.material_id, 'supplier_id', NEW.supplier_id, 'invoice_number', NEW.invoice_number, 'purchase_date', NEW.purchase_date, 'quantity_bought', NEW.quantity_bought, 'total_paid', NEW.total_paid, 'unit_cost', NEW.unit_cost, 'notes', NEW.notes, 'status', NEW.status, 'cancel_reason', NEW.cancel_reason, 'cancelled_at', NEW.cancelled_at, 'replaces_purchase_id', NEW.replaces_purchase_id, 'stock_movement_id', NEW.stock_movement_id, 'cancel_movement_id', NEW.cancel_movement_id, 'item_cost_before', NEW.item_cost_before, 'item_cost_after', NEW.item_cost_after), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

CREATE TRIGGER trg_audit_material_purchases_upd AFTER UPDATE ON material_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, after_json, actor, op_id)
    SELECT 'material_purchases', CAST(NEW.id AS TEXT), 'UPDATE', COALESCE(c.operation, 'UNLABELLED'),
           json_group_object(d.k, d.o), json_group_object(d.k, d.n), c.actor, c.op_id
    FROM (
        SELECT 'id' AS k, OLD.id AS o, NEW.id AS n
        UNION ALL SELECT 'material_id' AS k, OLD.material_id AS o, NEW.material_id AS n
        UNION ALL SELECT 'supplier_id' AS k, OLD.supplier_id AS o, NEW.supplier_id AS n
        UNION ALL SELECT 'invoice_number' AS k, OLD.invoice_number AS o, NEW.invoice_number AS n
        UNION ALL SELECT 'purchase_date' AS k, OLD.purchase_date AS o, NEW.purchase_date AS n
        UNION ALL SELECT 'quantity_bought' AS k, OLD.quantity_bought AS o, NEW.quantity_bought AS n
        UNION ALL SELECT 'total_paid' AS k, OLD.total_paid AS o, NEW.total_paid AS n
        UNION ALL SELECT 'unit_cost' AS k, OLD.unit_cost AS o, NEW.unit_cost AS n
        UNION ALL SELECT 'notes' AS k, OLD.notes AS o, NEW.notes AS n
        UNION ALL SELECT 'status' AS k, OLD.status AS o, NEW.status AS n
        UNION ALL SELECT 'cancel_reason' AS k, OLD.cancel_reason AS o, NEW.cancel_reason AS n
        UNION ALL SELECT 'cancelled_at' AS k, OLD.cancelled_at AS o, NEW.cancelled_at AS n
        UNION ALL SELECT 'replaces_purchase_id' AS k, OLD.replaces_purchase_id AS o, NEW.replaces_purchase_id AS n
        UNION ALL SELECT 'stock_movement_id' AS k, OLD.stock_movement_id AS o, NEW.stock_movement_id AS n
        UNION ALL SELECT 'cancel_movement_id' AS k, OLD.cancel_movement_id AS o, NEW.cancel_movement_id AS n
        UNION ALL SELECT 'item_cost_before' AS k, OLD.item_cost_before AS o, NEW.item_cost_before AS n
        UNION ALL SELECT 'item_cost_after' AS k, OLD.item_cost_after AS o, NEW.item_cost_after AS n
    ) AS d
    LEFT JOIN audit_context AS c ON c.id = 1
    WHERE d.o IS NOT d.n
    HAVING count(*) > 0;
END;

CREATE TRIGGER trg_audit_material_purchases_del AFTER DELETE ON material_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, actor, op_id)
    SELECT 'material_purchases', CAST(OLD.id AS TEXT), 'DELETE', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', OLD.id, 'material_id', OLD.material_id, 'supplier_id', OLD.supplier_id, 'invoice_number', OLD.invoice_number, 'purchase_date', OLD.purchase_date, 'quantity_bought', OLD.quantity_bought, 'total_paid', OLD.total_paid, 'unit_cost', OLD.unit_cost, 'notes', OLD.notes, 'status', OLD.status, 'cancel_reason', OLD.cancel_reason, 'cancelled_at', OLD.cancelled_at, 'replaces_purchase_id', OLD.replaces_purchase_id, 'stock_movement_id', OLD.stock_movement_id, 'cancel_movement_id', OLD.cancel_movement_id, 'item_cost_before', OLD.item_cost_before, 'item_cost_after', OLD.item_cost_after), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

-- product_purchases
CREATE TRIGGER trg_audit_product_purchases_ins AFTER INSERT ON product_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, after_json, actor, op_id)
    SELECT 'product_purchases', CAST(NEW.id AS TEXT), 'INSERT', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', NEW.id, 'product_id', NEW.product_id, 'supplier_id', NEW.supplier_id, 'invoice_number', NEW.invoice_number, 'purchase_date', NEW.purchase_date, 'quantity_bought', NEW.quantity_bought, 'total_paid', NEW.total_paid, 'unit_cost', NEW.unit_cost, 'notes', NEW.notes, 'status', NEW.status, 'cancel_reason', NEW.cancel_reason, 'cancelled_at', NEW.cancelled_at, 'replaces_purchase_id', NEW.replaces_purchase_id, 'stock_movement_id', NEW.stock_movement_id, 'cancel_movement_id', NEW.cancel_movement_id, 'item_cost_before', NEW.item_cost_before, 'item_cost_after', NEW.item_cost_after), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

CREATE TRIGGER trg_audit_product_purchases_upd AFTER UPDATE ON product_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, after_json, actor, op_id)
    SELECT 'product_purchases', CAST(NEW.id AS TEXT), 'UPDATE', COALESCE(c.operation, 'UNLABELLED'),
           json_group_object(d.k, d.o), json_group_object(d.k, d.n), c.actor, c.op_id
    FROM (
        SELECT 'id' AS k, OLD.id AS o, NEW.id AS n
        UNION ALL SELECT 'product_id' AS k, OLD.product_id AS o, NEW.product_id AS n
        UNION ALL SELECT 'supplier_id' AS k, OLD.supplier_id AS o, NEW.supplier_id AS n
        UNION ALL SELECT 'invoice_number' AS k, OLD.invoice_number AS o, NEW.invoice_number AS n
        UNION ALL SELECT 'purchase_date' AS k, OLD.purchase_date AS o, NEW.purchase_date AS n
        UNION ALL SELECT 'quantity_bought' AS k, OLD.quantity_bought AS o, NEW.quantity_bought AS n
        UNION ALL SELECT 'total_paid' AS k, OLD.total_paid AS o, NEW.total_paid AS n
        UNION ALL SELECT 'unit_cost' AS k, OLD.unit_cost AS o, NEW.unit_cost AS n
        UNION ALL SELECT 'notes' AS k, OLD.notes AS o, NEW.notes AS n
        UNION ALL SELECT 'status' AS k, OLD.status AS o, NEW.status AS n
        UNION ALL SELECT 'cancel_reason' AS k, OLD.cancel_reason AS o, NEW.cancel_reason AS n
        UNION ALL SELECT 'cancelled_at' AS k, OLD.cancelled_at AS o, NEW.cancelled_at AS n
        UNION ALL SELECT 'replaces_purchase_id' AS k, OLD.replaces_purchase_id AS o, NEW.replaces_purchase_id AS n
        UNION ALL SELECT 'stock_movement_id' AS k, OLD.stock_movement_id AS o, NEW.stock_movement_id AS n
        UNION ALL SELECT 'cancel_movement_id' AS k, OLD.cancel_movement_id AS o, NEW.cancel_movement_id AS n
        UNION ALL SELECT 'item_cost_before' AS k, OLD.item_cost_before AS o, NEW.item_cost_before AS n
        UNION ALL SELECT 'item_cost_after' AS k, OLD.item_cost_after AS o, NEW.item_cost_after AS n
    ) AS d
    LEFT JOIN audit_context AS c ON c.id = 1
    WHERE d.o IS NOT d.n
    HAVING count(*) > 0;
END;

CREATE TRIGGER trg_audit_product_purchases_del AFTER DELETE ON product_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, actor, op_id)
    SELECT 'product_purchases', CAST(OLD.id AS TEXT), 'DELETE', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', OLD.id, 'product_id', OLD.product_id, 'supplier_id', OLD.supplier_id, 'invoice_number', OLD.invoice_number, 'purchase_date', OLD.purchase_date, 'quantity_bought', OLD.quantity_bought, 'total_paid', OLD.total_paid, 'unit_cost', OLD.unit_cost, 'notes', OLD.notes, 'status', OLD.status, 'cancel_reason', OLD.cancel_reason, 'cancelled_at', OLD.cancelled_at, 'replaces_purchase_id', OLD.replaces_purchase_id, 'stock_movement_id', OLD.stock_movement_id, 'cancel_movement_id', OLD.cancel_movement_id, 'item_cost_before', OLD.item_cost_before, 'item_cost_after', OLD.item_cost_after), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

-- supplier_payments
CREATE TRIGGER trg_audit_supplier_payments_ins AFTER INSERT ON supplier_payments
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, after_json, actor, op_id)
    SELECT 'supplier_payments', CAST(NEW.id AS TEXT), 'INSERT', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', NEW.id, 'supplier_id', NEW.supplier_id, 'payment_date', NEW.payment_date, 'amount', NEW.amount, 'method', NEW.method, 'reference', NEW.reference, 'note', NEW.note, 'created_at', NEW.created_at), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

CREATE TRIGGER trg_audit_supplier_payments_upd AFTER UPDATE ON supplier_payments
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, after_json, actor, op_id)
    SELECT 'supplier_payments', CAST(NEW.id AS TEXT), 'UPDATE', COALESCE(c.operation, 'UNLABELLED'),
           json_group_object(d.k, d.o), json_group_object(d.k, d.n), c.actor, c.op_id
    FROM (
        SELECT 'id' AS k, OLD.id AS o, NEW.id AS n
        UNION ALL SELECT 'supplier_id' AS k, OLD.supplier_id AS o, NEW.supplier_id AS n
        UNION ALL SELECT 'payment_date' AS k, OLD.payment_date AS o, NEW.payment_date AS n
        UNION ALL SELECT 'amount' AS k, OLD.amount AS o, NEW.amount AS n
        UNION ALL SELECT 'method' AS k, OLD.method AS o, NEW.method AS n
        UNION ALL SELECT 'reference' AS k, OLD.reference AS o, NEW.reference AS n
        UNION ALL SELECT 'note' AS k, OLD.note AS o, NEW.note AS n
        UNION ALL SELECT 'created_at' AS k, OLD.created_at AS o, NEW.created_at AS n
    ) AS d
    LEFT JOIN audit_context AS c ON c.id = 1
    WHERE d.o IS NOT d.n
    HAVING count(*) > 0;
END;

CREATE TRIGGER trg_audit_supplier_payments_del AFTER DELETE ON supplier_payments
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, actor, op_id)
    SELECT 'supplier_payments', CAST(OLD.id AS TEXT), 'DELETE', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', OLD.id, 'supplier_id', OLD.supplier_id, 'payment_date', OLD.payment_date, 'amount', OLD.amount, 'method', OLD.method, 'reference', OLD.reference, 'note', OLD.note, 'created_at', OLD.created_at), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

-- supplier_payment_allocations
CREATE TRIGGER trg_audit_supplier_payment_allocations_ins AFTER INSERT ON supplier_payment_allocations
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, after_json, actor, op_id)
    SELECT 'supplier_payment_allocations', CAST(NEW.id AS TEXT), 'INSERT', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', NEW.id, 'payment_id', NEW.payment_id, 'material_purchase_id', NEW.material_purchase_id, 'product_purchase_id', NEW.product_purchase_id, 'amount', NEW.amount), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

CREATE TRIGGER trg_audit_supplier_payment_allocations_upd AFTER UPDATE ON supplier_payment_allocations
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, after_json, actor, op_id)
    SELECT 'supplier_payment_allocations', CAST(NEW.id AS TEXT), 'UPDATE', COALESCE(c.operation, 'UNLABELLED'),
           json_group_object(d.k, d.o), json_group_object(d.k, d.n), c.actor, c.op_id
    FROM (
        SELECT 'id' AS k, OLD.id AS o, NEW.id AS n
        UNION ALL SELECT 'payment_id' AS k, OLD.payment_id AS o, NEW.payment_id AS n
        UNION ALL SELECT 'material_purchase_id' AS k, OLD.material_purchase_id AS o, NEW.material_purchase_id AS n
        UNION ALL SELECT 'product_purchase_id' AS k, OLD.product_purchase_id AS o, NEW.product_purchase_id AS n
        UNION ALL SELECT 'amount' AS k, OLD.amount AS o, NEW.amount AS n
    ) AS d
    LEFT JOIN audit_context AS c ON c.id = 1
    WHERE d.o IS NOT d.n
    HAVING count(*) > 0;
END;

CREATE TRIGGER trg_audit_supplier_payment_allocations_del AFTER DELETE ON supplier_payment_allocations
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, actor, op_id)
    SELECT 'supplier_payment_allocations', CAST(OLD.id AS TEXT), 'DELETE', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', OLD.id, 'payment_id', OLD.payment_id, 'material_purchase_id', OLD.material_purchase_id, 'product_purchase_id', OLD.product_purchase_id, 'amount', OLD.amount), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;
