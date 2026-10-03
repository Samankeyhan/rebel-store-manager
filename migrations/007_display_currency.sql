-- Display currency: how money is SHOWN (UI and customer invoice), never how
-- it is stored. Every amount stays INTEGER Toman; Rial is Toman x 10, applied
-- only when displaying. Adds one settings row and touches nothing else.
INSERT OR IGNORE INTO settings (key, value) VALUES ('display_currency', 'TOMAN');
