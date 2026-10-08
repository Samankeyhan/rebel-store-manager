-- Optional minimum stock per material (a quantity in the material's own unit).
--
-- An active STOCK material is low when current_stock <= 0, or when min_stock
-- is set and current_stock <= min_stock (the rule lives in db/materials.py).
-- NULL = no minimum (only the out-of-stock warning). SERVICE materials never
-- have one; db/ enforces that, since a cross-column CHECK needs a table rebuild.
--
-- Every existing material gets NULL; no row is backfilled and updated_at is not
-- touched. SQLite accepts a CHECK on ADD COLUMN; every existing row (NULL) satisfies it.

ALTER TABLE materials ADD COLUMN min_stock REAL CHECK (min_stock IS NULL OR min_stock >= 0);
