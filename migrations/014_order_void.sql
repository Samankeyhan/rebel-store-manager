-- ============================================================
-- Voided orders and corrections (docs/accounting-rules.md section 20)
--
-- A sale entered by mistake is VOIDED (orders.void_order): its stock comes back, it
-- leaves every figure, and the row and its lines stay. A correction voids it and records
-- the right sale in the same operation; the new order points back with replaces_order_id.
--
-- orders gets a seventh status, VOIDED. The status CHECK is part of the original table,
-- so orders is rebuilt with SQLite's documented procedure (create new, copy, drop old,
-- rename, recreate indexes and triggers). The migration runner turns foreign keys off
-- around this script (db/connection.py _apply_migration), so DROP TABLE does not cascade
-- into order_items or stock_movements.
--
-- Objects that reference orders (checked against a database built from 001-013 and the
-- test shop database before writing this file):
--   - foreign keys order_items.order_id (ON DELETE CASCADE) and
--     stock_movements.reference_order_id (ON DELETE SET NULL): they name the table, so
--     they point at the rebuilt table after the rename; nothing to change.
--   - indexes idx_orders_date, idx_orders_status, idx_orders_channel,
--     idx_orders_invoice_number_unique, idx_orders_settlement_pending: dropped with the
--     old table, recreated below exactly as before.
--   - triggers trg_audit_orders_ins/upd/del: dropped with the old table, recreated below
--     from db/audit.py audit_trigger_sql for the new columns.
--   - no views, and no trigger on another table mentions orders.
--
-- Every row and value is copied unchanged, ids included. The copy runs before the audit
-- triggers exist, so it writes no audit rows (orders has no updated_at). The
-- AUTOINCREMENT high-water mark is carried over, so an id is never reused.
--
-- New columns (NULL on every existing row):
--   void_reason        why the order was voided (required when VOIDED)
--   voided_at          UTC moment of the void (set exactly when VOIDED)
--   replaces_order_id  on a correction: the voided order it replaces (one at most)
-- ============================================================

CREATE TEMP TABLE m014_sequence AS
    SELECT seq FROM sqlite_sequence WHERE name = 'orders';

CREATE TABLE orders_new (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number           TEXT,
    order_date               TEXT NOT NULL DEFAULT (datetime('now')),
    status                   TEXT NOT NULL CHECK (status IN (
                                 'DRAFT', 'PENDING', 'PAID', 'COMPLETED', 'CANCELLED', 'REFUNDED', 'VOIDED'
                             )),
    channel                  TEXT NOT NULL CHECK (channel IN (
                                 'INSTAGRAM', 'WEBSITE', 'WHOLESALE', 'IN_PERSON', 'OTHER'
                             )),
    customer_name            TEXT,
    shipping_charge          INTEGER NOT NULL DEFAULT 0 CHECK (shipping_charge >= 0),
    postage_cost             INTEGER NOT NULL DEFAULT 0 CHECK (postage_cost >= 0),
    transaction_fee          INTEGER NOT NULL DEFAULT 0 CHECK (transaction_fee >= 0),
    notes                    TEXT,
    packaging_kit_id         INTEGER REFERENCES packaging_kits(id),
    packaging_cost           INTEGER NOT NULL DEFAULT 0 CHECK (packaging_cost >= 0),
    stock_committed          INTEGER NOT NULL DEFAULT 1 CHECK (stock_committed IN (0, 1)),
    payment_method_id        INTEGER REFERENCES payment_methods(id),
    payment_reference        TEXT,
    paid_date                TEXT,
    expected_settlement_date TEXT,
    paid_jalali_year         INTEGER,
    paid_jalali_month        INTEGER,
    settlement_id            INTEGER REFERENCES settlements(id),
    void_reason              TEXT,
    voided_at                TEXT,
    replaces_order_id        INTEGER REFERENCES orders(id),
    CHECK ((status = 'VOIDED') = (voided_at IS NOT NULL)),
    CHECK (status <> 'VOIDED' OR length(trim(coalesce(void_reason, ''))) > 0),
    CHECK (replaces_order_id IS NULL OR replaces_order_id <> id)
);

INSERT INTO orders_new (
    id, invoice_number, order_date, status, channel, customer_name,
    shipping_charge, postage_cost, transaction_fee, notes,
    packaging_kit_id, packaging_cost, stock_committed,
    payment_method_id, payment_reference, paid_date, expected_settlement_date,
    paid_jalali_year, paid_jalali_month, settlement_id
)
SELECT
    id, invoice_number, order_date, status, channel, customer_name,
    shipping_charge, postage_cost, transaction_fee, notes,
    packaging_kit_id, packaging_cost, stock_committed,
    payment_method_id, payment_reference, paid_date, expected_settlement_date,
    paid_jalali_year, paid_jalali_month, settlement_id
FROM orders;

DROP TABLE orders;

ALTER TABLE orders_new RENAME TO orders;

DELETE FROM sqlite_sequence WHERE name = 'orders';
INSERT INTO sqlite_sequence (name, seq)
    SELECT 'orders', MAX(seq) FROM (
        SELECT seq FROM temp.m014_sequence
        UNION ALL SELECT MAX(id) FROM orders
    )
    HAVING MAX(seq) IS NOT NULL;
DROP TABLE temp.m014_sequence;

CREATE INDEX idx_orders_date                       ON orders(order_date);
CREATE INDEX idx_orders_status                     ON orders(status);
CREATE INDEX idx_orders_channel                     ON orders(channel);
CREATE UNIQUE INDEX idx_orders_invoice_number_unique
    ON orders(invoice_number) WHERE invoice_number IS NOT NULL;
CREATE INDEX idx_orders_settlement_pending ON orders(payment_method_id, settlement_id);
CREATE UNIQUE INDEX ux_orders_replaces_order_id
    ON orders(replaces_order_id) WHERE replaces_order_id IS NOT NULL;

CREATE TRIGGER trg_audit_orders_ins AFTER INSERT ON orders
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, after_json, actor, op_id)
    SELECT 'orders', CAST(NEW.id AS TEXT), 'INSERT', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', NEW.id, 'invoice_number', NEW.invoice_number, 'order_date', NEW.order_date, 'status', NEW.status, 'channel', NEW.channel, 'customer_name', NEW.customer_name, 'shipping_charge', NEW.shipping_charge, 'postage_cost', NEW.postage_cost, 'transaction_fee', NEW.transaction_fee, 'notes', NEW.notes, 'packaging_kit_id', NEW.packaging_kit_id, 'packaging_cost', NEW.packaging_cost, 'stock_committed', NEW.stock_committed, 'payment_method_id', NEW.payment_method_id, 'payment_reference', NEW.payment_reference, 'paid_date', NEW.paid_date, 'expected_settlement_date', NEW.expected_settlement_date, 'paid_jalali_year', NEW.paid_jalali_year, 'paid_jalali_month', NEW.paid_jalali_month, 'settlement_id', NEW.settlement_id, 'void_reason', NEW.void_reason, 'voided_at', NEW.voided_at, 'replaces_order_id', NEW.replaces_order_id), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;

CREATE TRIGGER trg_audit_orders_upd AFTER UPDATE ON orders
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, after_json, actor, op_id)
    SELECT 'orders', CAST(NEW.id AS TEXT), 'UPDATE', COALESCE(c.operation, 'UNLABELLED'),
           json_group_object(d.k, d.o), json_group_object(d.k, d.n), c.actor, c.op_id
    FROM (
        SELECT 'id' AS k, OLD.id AS o, NEW.id AS n
        UNION ALL SELECT 'invoice_number' AS k, OLD.invoice_number AS o, NEW.invoice_number AS n
        UNION ALL SELECT 'order_date' AS k, OLD.order_date AS o, NEW.order_date AS n
        UNION ALL SELECT 'status' AS k, OLD.status AS o, NEW.status AS n
        UNION ALL SELECT 'channel' AS k, OLD.channel AS o, NEW.channel AS n
        UNION ALL SELECT 'customer_name' AS k, OLD.customer_name AS o, NEW.customer_name AS n
        UNION ALL SELECT 'shipping_charge' AS k, OLD.shipping_charge AS o, NEW.shipping_charge AS n
        UNION ALL SELECT 'postage_cost' AS k, OLD.postage_cost AS o, NEW.postage_cost AS n
        UNION ALL SELECT 'transaction_fee' AS k, OLD.transaction_fee AS o, NEW.transaction_fee AS n
        UNION ALL SELECT 'notes' AS k, OLD.notes AS o, NEW.notes AS n
        UNION ALL SELECT 'packaging_kit_id' AS k, OLD.packaging_kit_id AS o, NEW.packaging_kit_id AS n
        UNION ALL SELECT 'packaging_cost' AS k, OLD.packaging_cost AS o, NEW.packaging_cost AS n
        UNION ALL SELECT 'stock_committed' AS k, OLD.stock_committed AS o, NEW.stock_committed AS n
        UNION ALL SELECT 'payment_method_id' AS k, OLD.payment_method_id AS o, NEW.payment_method_id AS n
        UNION ALL SELECT 'payment_reference' AS k, OLD.payment_reference AS o, NEW.payment_reference AS n
        UNION ALL SELECT 'paid_date' AS k, OLD.paid_date AS o, NEW.paid_date AS n
        UNION ALL SELECT 'expected_settlement_date' AS k, OLD.expected_settlement_date AS o, NEW.expected_settlement_date AS n
        UNION ALL SELECT 'paid_jalali_year' AS k, OLD.paid_jalali_year AS o, NEW.paid_jalali_year AS n
        UNION ALL SELECT 'paid_jalali_month' AS k, OLD.paid_jalali_month AS o, NEW.paid_jalali_month AS n
        UNION ALL SELECT 'settlement_id' AS k, OLD.settlement_id AS o, NEW.settlement_id AS n
        UNION ALL SELECT 'void_reason' AS k, OLD.void_reason AS o, NEW.void_reason AS n
        UNION ALL SELECT 'voided_at' AS k, OLD.voided_at AS o, NEW.voided_at AS n
        UNION ALL SELECT 'replaces_order_id' AS k, OLD.replaces_order_id AS o, NEW.replaces_order_id AS n
    ) AS d
    LEFT JOIN audit_context AS c ON c.id = 1
    WHERE d.o IS NOT d.n
    HAVING count(*) > 0;
END;

CREATE TRIGGER trg_audit_orders_del AFTER DELETE ON orders
BEGIN
    INSERT INTO audit_log (entity_type, entity_id, action, operation, before_json, actor, op_id)
    SELECT 'orders', CAST(OLD.id AS TEXT), 'DELETE', COALESCE(c.operation, 'UNLABELLED'),
           json_object('id', OLD.id, 'invoice_number', OLD.invoice_number, 'order_date', OLD.order_date, 'status', OLD.status, 'channel', OLD.channel, 'customer_name', OLD.customer_name, 'shipping_charge', OLD.shipping_charge, 'postage_cost', OLD.postage_cost, 'transaction_fee', OLD.transaction_fee, 'notes', OLD.notes, 'packaging_kit_id', OLD.packaging_kit_id, 'packaging_cost', OLD.packaging_cost, 'stock_committed', OLD.stock_committed, 'payment_method_id', OLD.payment_method_id, 'payment_reference', OLD.payment_reference, 'paid_date', OLD.paid_date, 'expected_settlement_date', OLD.expected_settlement_date, 'paid_jalali_year', OLD.paid_jalali_year, 'paid_jalali_month', OLD.paid_jalali_month, 'settlement_id', OLD.settlement_id, 'void_reason', OLD.void_reason, 'voided_at', OLD.voided_at, 'replaces_order_id', OLD.replaces_order_id), c.actor, c.op_id
    FROM (SELECT 1) AS one LEFT JOIN audit_context AS c ON c.id = 1;
END;
