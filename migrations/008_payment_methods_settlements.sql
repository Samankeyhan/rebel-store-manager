-- Payment methods, fees and settlements.
--
-- A payment method is owner-entered data (nothing is seeded): a fee
-- (fee_bps basis points of customer_total, half-even, plus fee_fixed Toman)
-- and a settlement rule saying when the gateway pays the money out:
--   IMMEDIATE          expected on the paid day (settlement_days NULL)
--   DAYS_AFTER         expected paid_date + settlement_days (1..365)
--   DAY_OF_NEXT_MONTH  one payout per Jalali month, on day settlement_days
--                      (1..31, clamped to the month's length) of the next month
--
-- orders.paid_date, expected_settlement_date and settled_date are LOCAL
-- calendar days ("YYYY-MM-DD" in the store timezone), not UTC moments.
-- Every new orders column is NULL for orders recorded before this migration;
-- no existing row is backfilled.
--
-- A CHECK that evaluates to NULL passes in SQLite, so the rule/days CHECK
-- tests settlement_days IS NOT NULL explicitly in the branches that need it.

CREATE TABLE payment_methods (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,
    fee_bps          INTEGER NOT NULL DEFAULT 0 CHECK (fee_bps BETWEEN 0 AND 10000),
    fee_fixed        INTEGER NOT NULL DEFAULT 0 CHECK (fee_fixed >= 0),
    settlement_rule  TEXT NOT NULL CHECK (settlement_rule IN ('IMMEDIATE', 'DAYS_AFTER', 'DAY_OF_NEXT_MONTH')),
    settlement_days  INTEGER,
    is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (
        (settlement_rule = 'IMMEDIATE'
            AND settlement_days IS NULL) OR
        (settlement_rule = 'DAYS_AFTER'
            AND settlement_days IS NOT NULL AND settlement_days BETWEEN 1 AND 365) OR
        (settlement_rule = 'DAY_OF_NEXT_MONTH'
            AND settlement_days IS NOT NULL AND settlement_days BETWEEN 1 AND 31)
    )
);

CREATE TABLE settlements (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_method_id  INTEGER NOT NULL REFERENCES payment_methods(id) ON DELETE RESTRICT,
    settled_date       TEXT NOT NULL,
    jalali_year        INTEGER,                    -- set only for DAY_OF_NEXT_MONTH
    jalali_month       INTEGER CHECK (jalali_month BETWEEN 1 AND 12),  -- NULL on purpose for other rules
    expected_amount    INTEGER NOT NULL,           -- sum(customer_total - transaction_fee); may be negative
    amount_received    INTEGER NOT NULL CHECK (amount_received >= 0),
    note               TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((jalali_year IS NULL) = (jalali_month IS NULL))
);

-- One settlement per method and Jalali month (DAY_OF_NEXT_MONTH only).
CREATE UNIQUE INDEX ux_settlements_method_month
    ON settlements(payment_method_id, jalali_year, jalali_month)
    WHERE jalali_month IS NOT NULL;

ALTER TABLE orders ADD COLUMN payment_method_id        INTEGER REFERENCES payment_methods(id);
ALTER TABLE orders ADD COLUMN payment_reference        TEXT;
ALTER TABLE orders ADD COLUMN paid_date                TEXT;
ALTER TABLE orders ADD COLUMN expected_settlement_date TEXT;
ALTER TABLE orders ADD COLUMN paid_jalali_year         INTEGER;
ALTER TABLE orders ADD COLUMN paid_jalali_month        INTEGER;
ALTER TABLE orders ADD COLUMN settlement_id            INTEGER REFERENCES settlements(id);

CREATE INDEX idx_orders_settlement_pending ON orders(payment_method_id, settlement_id);

ALTER TABLE channel_settings ADD COLUMN default_payment_method_id INTEGER REFERENCES payment_methods(id);
