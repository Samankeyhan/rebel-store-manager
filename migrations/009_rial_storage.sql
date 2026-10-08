-- Money is stored in integer RIAL from here on (it was integer Toman).
--
-- Every money column, and the two money settings, are multiplied by 10.
-- Nothing else changes: quantities, stock, percentages, basis points, counts,
-- ids, windows, Jalali years/months, dates and text are left exactly as they
-- are. NULL stays NULL (NULL * 10 is NULL). Every money CHECK is ">= 0" or
-- "discount_amount <= list_price", both preserved by multiplying by 10; the
-- two columns allowed to be negative (profit_distributions.total_profit_available,
-- settlements.expected_amount) keep their sign.
--
-- init_db runs this whole file in one transaction and backs the database up
-- before applying it.
--
-- updated_at must not change (the 005 lesson): products and materials have an
-- AFTER UPDATE trigger that rewrites updated_at, so both triggers are dropped
-- for the UPDATEs and recreated with exactly their previous definitions.
-- payment_methods has no trigger; no other updated table has one.

DROP TRIGGER trg_products_updated_at;
DROP TRIGGER trg_materials_updated_at;

UPDATE products
   SET retail_price    = retail_price * 10,
       wholesale_price = wholesale_price * 10,
       unit_cost       = unit_cost * 10;

UPDATE materials
   SET unit_cost = unit_cost * 10;

UPDATE material_purchases
   SET total_paid = total_paid * 10,
       unit_cost  = unit_cost * 10;

UPDATE product_purchases
   SET total_paid = total_paid * 10,
       unit_cost  = unit_cost * 10;

UPDATE production_batches
   SET unit_cost  = unit_cost * 10,
       total_cost = total_cost * 10;

UPDATE production_batch_materials
   SET unit_cost_at_time = unit_cost_at_time * 10;

UPDATE orders
   SET shipping_charge = shipping_charge * 10,
       postage_cost    = postage_cost * 10,
       transaction_fee = transaction_fee * 10,
       packaging_cost  = packaging_cost * 10;

UPDATE order_items
   SET list_price        = list_price * 10,
       discount_amount   = discount_amount * 10,
       unit_price        = unit_price * 10,
       unit_cost_at_time = unit_cost_at_time * 10;

UPDATE stock_movements
   SET unit_cost_at_time = unit_cost_at_time * 10;

UPDATE expenses
   SET amount = amount * 10;

UPDATE profit_distributions
   SET total_profit_available   = total_profit_available * 10,
       total_amount_distributed = total_amount_distributed * 10;

UPDATE distribution_shares
   SET amount = amount * 10;

UPDATE postage_batches
   SET total_paid = total_paid * 10;

UPDATE payment_methods
   SET fee_fixed = fee_fixed * 10;

UPDATE settlements
   SET expected_amount = expected_amount * 10,
       amount_received = amount_received * 10;

-- The two money settings are integer strings (db/settings.py validates them).
UPDATE settings
   SET value = CAST(CAST(value AS INTEGER) * 10 AS TEXT)
 WHERE key IN ('default_shipping_charge', 'default_postage_estimate');

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
