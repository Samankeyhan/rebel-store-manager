-- ============================================================
-- production_batches: when the row was recorded, and the batch's
-- true total cost.
--
-- created_at: the moment the batch was recorded (UTC text, like every
-- other created_at). Distinct from production_date, which may be
-- backdated. NULL for batches recorded before this migration: their
-- creation time was never stored, and inventing one would be false.
--
-- total_cost: batch_total_cost as run_production_batch computed it
-- (round(sum(needed x material unit_cost)), docs/accounting-rules.md
-- section 3) before dividing it into unit_cost. NULL for earlier
-- batches; their per-line costs remain in production_batch_materials.
--
-- Both are plain nullable columns (SQLite's ALTER TABLE cannot add a
-- non-constant default); db/production.py sets them on every new batch.
-- ============================================================

ALTER TABLE production_batches ADD COLUMN created_at TEXT;
ALTER TABLE production_batches ADD COLUMN total_cost INTEGER
    CHECK (total_cost IS NULL OR total_cost >= 0);
