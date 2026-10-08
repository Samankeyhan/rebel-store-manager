-- Optional cap on the percentage part of a payment method's fee.
--
-- fee = min(half_even(customer_total x fee_bps / 10000), fee_cap) + fee_fixed,
-- in integer Rial (stored in Rial from the start: 009 never scaled it).
-- NULL = no cap, exactly the fee before this migration. fee_fixed is never capped.
--
-- Every existing method gets NULL; no row is backfilled and updated_at is not
-- touched. Orders keep the transaction_fee frozen on them.
-- SQLite accepts a CHECK on ADD COLUMN; every existing row (NULL) satisfies it.

ALTER TABLE payment_methods ADD COLUMN fee_cap INTEGER CHECK (fee_cap IS NULL OR fee_cap >= 1);
