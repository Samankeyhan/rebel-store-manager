-- ============================================================
-- Purchase invoices with lines (docs/accounting-rules.md sections 21 and 22;
-- docs/plans/2026-10-payables-purchase-correction.md, "Amendment: purchase invoices and services")
--
-- One supplier invoice is one purchase_invoices row: its PUR number, supplier, day, note, and the
-- status / cancel / replacement columns a later cancel or correction needs. Its lines are the
-- existing tables material_purchases and product_purchases (same names, same ids): each line keeps
-- its item, quantity, line total (total_paid), unit cost, its own PURCHASE movement, its cancel
-- movement and the item's cost just before and after it. The invoice total is the sum of its line
-- totals, computed on read, never stored. A supplier payment is now allocated to an invoice, not to
-- a line: supplier_payment_allocations.purchase_invoice_id replaces material_purchase_id /
-- product_purchase_id.
--
-- The columns that move to the invoice must leave the line tables, so material_purchases,
-- product_purchases and supplier_payment_allocations are rebuilt with SQLite's documented procedure
-- (create new, copy, drop old, rename, recreate indexes and triggers). The migration runner turns
-- foreign keys off around this script (db/connection.py _apply_migration), so DROP TABLE cascades
-- into nothing.
--
-- Objects that reference the rebuilt tables (checked against a database built from 001-015 and the
-- test shop database before writing this file):
--   - indexes idx_<kind>_purchases_<item>_id, _supplier_id, _invoice_number_unique, _status,
--     ux_<kind>_purchases_replaces_purchase_id, ux_<kind>_purchases_stock_movement_id, and
--     idx_supplier_payment_allocations_payment / _material_purchase / _product_purchase plus the two
--     UNIQUE autoindexes: dropped with the old tables. Recreated below: the item and movement indexes
--     on the lines, the supplier / number / status / replaces indexes on the invoice, and the payment
--     and invoice indexes on the allocations.
--   - triggers trg_audit_<kind>_purchases_* and trg_audit_supplier_payment_allocations_*: dropped
--     with the old tables, recreated below from db/audit.py audit_trigger_sql for the new columns.
--   - the only foreign keys into the purchase tables were the allocation table's, rebuilt here; no
--     view or other trigger names a rebuilt table. supplier_payments is not touched.
--
-- Every existing purchase row becomes a one-line invoice: invoices are numbered in the order
-- purchase_date, materials before products, line id (the payables order), and each takes its row's
-- PUR number, supplier, day, note, status and cancel columns. Every line and allocation keeps its id,
-- and each allocation points at the invoice of the row it paid, so paid, outstanding and the payment
-- status of every purchase stay exactly as they were. The AUTOINCREMENT marks are carried over. The
-- copy runs before any audit trigger exists, so it writes no audit rows (none of these tables has
-- updated_at). No stock, cost, movement, order, payment or counter changes.
-- ============================================================

CREATE TEMP TABLE m016_sequence AS
    SELECT name, seq FROM sqlite_sequence
    WHERE name IN ('material_purchases', 'product_purchases', 'supplier_payment_allocations');

-- one invoice per existing purchase row, numbered oldest first
CREATE TEMP TABLE m016_map (
    invoice_id INTEGER PRIMARY KEY,
    kind       TEXT NOT NULL,
    line_id    INTEGER NOT NULL,
    UNIQUE (kind, line_id)
);
INSERT INTO temp.m016_map (kind, line_id)
    SELECT kind, id FROM (
        SELECT 'MATERIAL' AS kind, 0 AS kind_order, id, purchase_date FROM material_purchases
        UNION ALL
        SELECT 'PRODUCT', 1, id, purchase_date FROM product_purchases
    )
    ORDER BY purchase_date, kind_order, id;

-- ------------------------------------------------------------ purchase_invoices

CREATE TABLE purchase_invoices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number      TEXT,
    supplier_id         INTEGER REFERENCES suppliers(id),
    purchase_date       TEXT NOT NULL DEFAULT (datetime('now')),
    notes               TEXT,
    status              TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CANCELLED')),
    cancel_reason       TEXT,
    cancelled_at        TEXT,
    replaces_invoice_id INTEGER REFERENCES purchase_invoices(id),
    CHECK ((status = 'CANCELLED') = (cancelled_at IS NOT NULL)),
    CHECK (status <> 'CANCELLED' OR length(trim(coalesce(cancel_reason, ''))) > 0),
    CHECK (replaces_invoice_id IS NULL OR replaces_invoice_id <> id)
);

INSERT INTO purchase_invoices (
    id, invoice_number, supplier_id, purchase_date, notes, status, cancel_reason, cancelled_at, replaces_invoice_id
)
SELECT m.invoice_id, p.invoice_number, p.supplier_id, p.purchase_date, p.notes, p.status, p.cancel_reason, p.cancelled_at,
       (SELECT r.invoice_id FROM temp.m016_map AS r WHERE r.kind = 'MATERIAL' AND r.line_id = p.replaces_purchase_id)
FROM temp.m016_map AS m JOIN material_purchases AS p ON m.kind = 'MATERIAL' AND p.id = m.line_id
UNION ALL
SELECT m.invoice_id, p.invoice_number, p.supplier_id, p.purchase_date, p.notes, p.status, p.cancel_reason, p.cancelled_at,
       (SELECT r.invoice_id FROM temp.m016_map AS r WHERE r.kind = 'PRODUCT' AND r.line_id = p.replaces_purchase_id)
FROM temp.m016_map AS m JOIN product_purchases AS p ON m.kind = 'PRODUCT' AND p.id = m.line_id
ORDER BY 1;

-- ------------------------------------------------------------ supplier_payment_allocations (to the invoice)

CREATE TABLE supplier_payment_allocations_new (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id          INTEGER NOT NULL REFERENCES supplier_payments(id) ON DELETE CASCADE,
    purchase_invoice_id INTEGER NOT NULL REFERENCES purchase_invoices(id),
    amount              INTEGER NOT NULL CHECK (amount > 0),
    UNIQUE (payment_id, purchase_invoice_id)
);

INSERT INTO supplier_payment_allocations_new (id, payment_id, purchase_invoice_id, amount)
SELECT a.id, a.payment_id, m.invoice_id, a.amount
FROM supplier_payment_allocations AS a
JOIN temp.m016_map AS m
  ON (m.kind = 'MATERIAL' AND m.line_id = a.material_purchase_id)
  OR (m.kind = 'PRODUCT' AND m.line_id = a.product_purchase_id)
ORDER BY a.id;

DROP TABLE supplier_payment_allocations;

ALTER TABLE supplier_payment_allocations_new RENAME TO supplier_payment_allocations;

-- ------------------------------------------------------------ material_purchases (lines)

CREATE TABLE material_purchases_new (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_invoice_id INTEGER NOT NULL REFERENCES purchase_invoices(id),
    material_id         INTEGER NOT NULL REFERENCES materials(id),
    quantity_bought     REAL NOT NULL CHECK (quantity_bought > 0),
    total_paid          INTEGER NOT NULL CHECK (total_paid >= 0),
    unit_cost           INTEGER NOT NULL CHECK (unit_cost >= 0),
    stock_movement_id   INTEGER REFERENCES stock_movements(id),
    cancel_movement_id  INTEGER REFERENCES stock_movements(id),
    item_cost_before    INTEGER CHECK (item_cost_before IS NULL OR item_cost_before >= 0),
    item_cost_after     INTEGER CHECK (item_cost_after IS NULL OR item_cost_after >= 0),
    CHECK (item_cost_after IS NOT NULL OR item_cost_before IS NULL),
    CHECK (cancel_movement_id IS NULL OR stock_movement_id IS NOT NULL)
);

INSERT INTO material_purchases_new (
    id, purchase_invoice_id, material_id, quantity_bought, total_paid, unit_cost,
    stock_movement_id, cancel_movement_id, item_cost_before, item_cost_after
)
SELECT p.id, m.invoice_id, p.material_id, p.quantity_bought, p.total_paid, p.unit_cost,
       p.stock_movement_id, p.cancel_movement_id, p.item_cost_before, p.item_cost_after
FROM material_purchases AS p
JOIN temp.m016_map AS m ON m.kind = 'MATERIAL' AND m.line_id = p.id
ORDER BY p.id;

DROP TABLE material_purchases;

ALTER TABLE material_purchases_new RENAME TO material_purchases;

-- ------------------------------------------------------------ product_purchases (lines)

CREATE TABLE product_purchases_new (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_invoice_id INTEGER NOT NULL REFERENCES purchase_invoices(id),
    product_id          INTEGER NOT NULL REFERENCES products(id),
    quantity_bought     INTEGER NOT NULL CHECK (quantity_bought > 0),
    total_paid          INTEGER NOT NULL CHECK (total_paid >= 0),
    unit_cost           INTEGER NOT NULL CHECK (unit_cost >= 0),
    stock_movement_id   INTEGER REFERENCES stock_movements(id),
    cancel_movement_id  INTEGER REFERENCES stock_movements(id),
    item_cost_before    INTEGER CHECK (item_cost_before IS NULL OR item_cost_before >= 0),
    item_cost_after     INTEGER CHECK (item_cost_after IS NULL OR item_cost_after >= 0),
    CHECK (item_cost_after IS NOT NULL OR item_cost_before IS NULL),
    CHECK (cancel_movement_id IS NULL OR stock_movement_id IS NOT NULL)
);

INSERT INTO product_purchases_new (
    id, purchase_invoice_id, product_id, quantity_bought, total_paid, unit_cost,
    stock_movement_id, cancel_movement_id, item_cost_before, item_cost_after
)
SELECT p.id, m.invoice_id, p.product_id, p.quantity_bought, p.total_paid, p.unit_cost,
       p.stock_movement_id, p.cancel_movement_id, p.item_cost_before, p.item_cost_after
FROM product_purchases AS p
JOIN temp.m016_map AS m ON m.kind = 'PRODUCT' AND m.line_id = p.id
ORDER BY p.id;

DROP TABLE product_purchases;

ALTER TABLE product_purchases_new RENAME TO product_purchases;

-- ------------------------------------------------------------ AUTOINCREMENT marks

DELETE FROM sqlite_sequence
    WHERE name IN ('material_purchases', 'product_purchases', 'supplier_payment_allocations', 'purchase_invoices');
INSERT INTO sqlite_sequence (name, seq)
    SELECT 'material_purchases', MAX(seq) FROM (
        SELECT seq FROM temp.m016_sequence WHERE name = 'material_purchases'
        UNION ALL SELECT MAX(id) FROM material_purchases
    )
    HAVING MAX(seq) IS NOT NULL;
INSERT INTO sqlite_sequence (name, seq)
    SELECT 'product_purchases', MAX(seq) FROM (
        SELECT seq FROM temp.m016_sequence WHERE name = 'product_purchases'
        UNION ALL SELECT MAX(id) FROM product_purchases
    )
    HAVING MAX(seq) IS NOT NULL;
INSERT INTO sqlite_sequence (name, seq)
    SELECT 'supplier_payment_allocations', MAX(seq) FROM (
        SELECT seq FROM temp.m016_sequence WHERE name = 'supplier_payment_allocations'
        UNION ALL SELECT MAX(id) FROM supplier_payment_allocations
    )
    HAVING MAX(seq) IS NOT NULL;
-- a new table: its mark is its highest id, and no row at all when it is empty (as on a fresh table)
INSERT INTO sqlite_sequence (name, seq)
    SELECT 'purchase_invoices', MAX(id) FROM purchase_invoices HAVING MAX(id) IS NOT NULL;
DROP TABLE temp.m016_sequence;
DROP TABLE temp.m016_map;

-- ------------------------------------------------------------ indexes

CREATE UNIQUE INDEX ux_purchase_invoices_invoice_number
    ON purchase_invoices(invoice_number) WHERE invoice_number IS NOT NULL;
CREATE INDEX idx_purchase_invoices_supplier_date ON purchase_invoices(supplier_id, purchase_date);
CREATE INDEX idx_purchase_invoices_purchase_date ON purchase_invoices(purchase_date);
CREATE INDEX idx_purchase_invoices_status ON purchase_invoices(status);
CREATE UNIQUE INDEX ux_purchase_invoices_replaces_invoice_id
    ON purchase_invoices(replaces_invoice_id) WHERE replaces_invoice_id IS NOT NULL;

-- one line per item on an invoice (the same item twice is refused: PURCHASE_DUPLICATE_ITEM)
CREATE UNIQUE INDEX ux_material_purchases_invoice_material ON material_purchases(purchase_invoice_id, material_id);
CREATE INDEX idx_material_purchases_material_id ON material_purchases(material_id);
CREATE UNIQUE INDEX ux_material_purchases_stock_movement_id
    ON material_purchases(stock_movement_id) WHERE stock_movement_id IS NOT NULL;

CREATE UNIQUE INDEX ux_product_purchases_invoice_product ON product_purchases(purchase_invoice_id, product_id);
CREATE INDEX idx_product_purchases_product_id ON product_purchases(product_id);
CREATE UNIQUE INDEX ux_product_purchases_stock_movement_id
    ON product_purchases(stock_movement_id) WHERE stock_movement_id IS NOT NULL;

CREATE INDEX idx_supplier_payment_allocations_payment ON supplier_payment_allocations(payment_id);
CREATE INDEX idx_supplier_payment_allocations_invoice ON supplier_payment_allocations(purchase_invoice_id);

-- ------------------------------------------------------------ triggers

-- Audit triggers (db/audit.py audit_trigger_sql, generated for the columns above).
-- purchase_invoices
CREATE TRIGGER trg_audit_purchase_invoices_ins AFTER INSERT ON purchase_invoices
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, after_json, actor, op_id)
    SELECT 'purchase_invoices', CAST(NEW.id AS TEXT), 'INSERT', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', NEW.id, 'invoice_number', NEW.invoice_number, 'supplier_id', NEW.supplier_id, 'purchase_date', NEW.purchase_date, 'notes', NEW.notes, 'status', NEW.status, 'cancel_reason', NEW.cancel_reason, 'cancelled_at', NEW.cancelled_at, 'replaces_invoice_id', NEW.replaces_invoice_id), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

CREATE TRIGGER trg_audit_purchase_invoices_upd AFTER UPDATE ON purchase_invoices
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, after_json, actor, op_id)
    SELECT 'purchase_invoices', CAST(NEW.id AS TEXT), 'UPDATE', COALESCE(c.operation, 'UNLABELLED'),
           json_group_object(d.k, d.o), json_group_object(d.k, d.n), c.actor, c.op_id
    FROM (
        SELECT 'id' AS k, OLD.id AS o, NEW.id AS n
        UNION ALL SELECT 'invoice_number' AS k, OLD.invoice_number AS o, NEW.invoice_number AS n
        UNION ALL SELECT 'supplier_id' AS k, OLD.supplier_id AS o, NEW.supplier_id AS n
        UNION ALL SELECT 'purchase_date' AS k, OLD.purchase_date AS o, NEW.purchase_date AS n
        UNION ALL SELECT 'notes' AS k, OLD.notes AS o, NEW.notes AS n
        UNION ALL SELECT 'status' AS k, OLD.status AS o, NEW.status AS n
        UNION ALL SELECT 'cancel_reason' AS k, OLD.cancel_reason AS o, NEW.cancel_reason AS n
        UNION ALL SELECT 'cancelled_at' AS k, OLD.cancelled_at AS o, NEW.cancelled_at AS n
        UNION ALL SELECT 'replaces_invoice_id' AS k, OLD.replaces_invoice_id AS o, NEW.replaces_invoice_id AS n
    ) AS d
    LEFT JOIN audit_context AS c ON c.id = 1
    WHERE d.o IS NOT d.n
    HAVING count(*) > 0;
END;

CREATE TRIGGER trg_audit_purchase_invoices_del AFTER DELETE ON purchase_invoices
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, actor, op_id)
    SELECT 'purchase_invoices', CAST(OLD.id AS TEXT), 'DELETE', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', OLD.id, 'invoice_number', OLD.invoice_number, 'supplier_id', OLD.supplier_id, 'purchase_date', OLD.purchase_date, 'notes', OLD.notes, 'status', OLD.status, 'cancel_reason', OLD.cancel_reason, 'cancelled_at', OLD.cancelled_at, 'replaces_invoice_id', OLD.replaces_invoice_id), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

-- material_purchases
CREATE TRIGGER trg_audit_material_purchases_ins AFTER INSERT ON material_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, after_json, actor, op_id)
    SELECT 'material_purchases', CAST(NEW.id AS TEXT), 'INSERT', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', NEW.id, 'purchase_invoice_id', NEW.purchase_invoice_id, 'material_id', NEW.material_id, 'quantity_bought', NEW.quantity_bought, 'total_paid', NEW.total_paid, 'unit_cost', NEW.unit_cost, 'stock_movement_id', NEW.stock_movement_id, 'cancel_movement_id', NEW.cancel_movement_id, 'item_cost_before', NEW.item_cost_before, 'item_cost_after', NEW.item_cost_after), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

CREATE TRIGGER trg_audit_material_purchases_upd AFTER UPDATE ON material_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, after_json, actor, op_id)
    SELECT 'material_purchases', CAST(NEW.id AS TEXT), 'UPDATE', COALESCE(c.operation, 'UNLABELLED'),
           json_group_object(d.k, d.o), json_group_object(d.k, d.n), c.actor, c.op_id
    FROM (
        SELECT 'id' AS k, OLD.id AS o, NEW.id AS n
        UNION ALL SELECT 'purchase_invoice_id' AS k, OLD.purchase_invoice_id AS o, NEW.purchase_invoice_id AS n
        UNION ALL SELECT 'material_id' AS k, OLD.material_id AS o, NEW.material_id AS n
        UNION ALL SELECT 'quantity_bought' AS k, OLD.quantity_bought AS o, NEW.quantity_bought AS n
        UNION ALL SELECT 'total_paid' AS k, OLD.total_paid AS o, NEW.total_paid AS n
        UNION ALL SELECT 'unit_cost' AS k, OLD.unit_cost AS o, NEW.unit_cost AS n
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
           json_object('id', OLD.id, 'purchase_invoice_id', OLD.purchase_invoice_id, 'material_id', OLD.material_id, 'quantity_bought', OLD.quantity_bought, 'total_paid', OLD.total_paid, 'unit_cost', OLD.unit_cost, 'stock_movement_id', OLD.stock_movement_id, 'cancel_movement_id', OLD.cancel_movement_id, 'item_cost_before', OLD.item_cost_before, 'item_cost_after', OLD.item_cost_after), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

-- product_purchases
CREATE TRIGGER trg_audit_product_purchases_ins AFTER INSERT ON product_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, after_json, actor, op_id)
    SELECT 'product_purchases', CAST(NEW.id AS TEXT), 'INSERT', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', NEW.id, 'purchase_invoice_id', NEW.purchase_invoice_id, 'product_id', NEW.product_id, 'quantity_bought', NEW.quantity_bought, 'total_paid', NEW.total_paid, 'unit_cost', NEW.unit_cost, 'stock_movement_id', NEW.stock_movement_id, 'cancel_movement_id', NEW.cancel_movement_id, 'item_cost_before', NEW.item_cost_before, 'item_cost_after', NEW.item_cost_after), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

CREATE TRIGGER trg_audit_product_purchases_upd AFTER UPDATE ON product_purchases
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, after_json, actor, op_id)
    SELECT 'product_purchases', CAST(NEW.id AS TEXT), 'UPDATE', COALESCE(c.operation, 'UNLABELLED'),
           json_group_object(d.k, d.o), json_group_object(d.k, d.n), c.actor, c.op_id
    FROM (
        SELECT 'id' AS k, OLD.id AS o, NEW.id AS n
        UNION ALL SELECT 'purchase_invoice_id' AS k, OLD.purchase_invoice_id AS o, NEW.purchase_invoice_id AS n
        UNION ALL SELECT 'product_id' AS k, OLD.product_id AS o, NEW.product_id AS n
        UNION ALL SELECT 'quantity_bought' AS k, OLD.quantity_bought AS o, NEW.quantity_bought AS n
        UNION ALL SELECT 'total_paid' AS k, OLD.total_paid AS o, NEW.total_paid AS n
        UNION ALL SELECT 'unit_cost' AS k, OLD.unit_cost AS o, NEW.unit_cost AS n
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
           json_object('id', OLD.id, 'purchase_invoice_id', OLD.purchase_invoice_id, 'product_id', OLD.product_id, 'quantity_bought', OLD.quantity_bought, 'total_paid', OLD.total_paid, 'unit_cost', OLD.unit_cost, 'stock_movement_id', OLD.stock_movement_id, 'cancel_movement_id', OLD.cancel_movement_id, 'item_cost_before', OLD.item_cost_before, 'item_cost_after', OLD.item_cost_after), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

-- supplier_payment_allocations
CREATE TRIGGER trg_audit_supplier_payment_allocations_ins AFTER INSERT ON supplier_payment_allocations
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, after_json, actor, op_id)
    SELECT 'supplier_payment_allocations', CAST(NEW.id AS TEXT), 'INSERT', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', NEW.id, 'payment_id', NEW.payment_id, 'purchase_invoice_id', NEW.purchase_invoice_id, 'amount', NEW.amount), c.actor, c.op_id
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
        UNION ALL SELECT 'purchase_invoice_id' AS k, OLD.purchase_invoice_id AS o, NEW.purchase_invoice_id AS n
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
           json_object('id', OLD.id, 'payment_id', OLD.payment_id, 'purchase_invoice_id', OLD.purchase_invoice_id, 'amount', OLD.amount), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;
