-- ============================================================
-- Partner Profit Distribution
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE partners (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    current_percentage  REAL NOT NULL CHECK (
                            current_percentage > 0 AND current_percentage <= 100
                        ),
    phone               TEXT,
    email               TEXT,
    notes               TEXT,
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT
);

CREATE TABLE profit_distributions (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    distribution_date           TEXT NOT NULL DEFAULT (datetime('now')),
    period_start                TEXT NOT NULL,
    period_end                  TEXT NOT NULL,
    total_profit_available      INTEGER NOT NULL,
    total_amount_distributed    INTEGER NOT NULL CHECK (total_amount_distributed >= 0),
    notes                       TEXT
);

CREATE TABLE distribution_shares (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    distribution_id     INTEGER NOT NULL REFERENCES profit_distributions(id) ON DELETE CASCADE,
    partner_id          INTEGER NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
    percentage_at_time  REAL NOT NULL,
    amount              INTEGER NOT NULL CHECK (amount >= 0)
);

CREATE INDEX idx_distribution_shares_distribution_id
    ON distribution_shares(distribution_id);
CREATE INDEX idx_distribution_shares_partner_id
    ON distribution_shares(partner_id);
CREATE INDEX idx_profit_distributions_distribution_date
    ON profit_distributions(distribution_date);
CREATE INDEX idx_profit_distributions_period_start
    ON profit_distributions(period_start);
CREATE INDEX idx_profit_distributions_period_end
    ON profit_distributions(period_end);

CREATE TRIGGER trg_partners_updated_at
AFTER UPDATE ON partners
BEGIN
    UPDATE partners SET updated_at = datetime('now') WHERE id = NEW.id;
END;
