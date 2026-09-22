# Accounting rules — Rebel Store Manager

Currency: Toman, stored as INTEGER. Store timezone: Asia/Tehran.

## 1. Dates
- Moments in time (order_date, expense_date, purchase_date, production_date, movement_date, paid_date, distribution_date, created_at) are stored as UTC text "YYYY-MM-DD HH:MM:SS".
- Dates supplied by users are store-local (Asia/Tehran). A bare "YYYY-MM-DD" given as a record date means local midnight of that day, converted to UTC.
- A date-range filter (start_date, end_date) covers whole local days, inclusive: stored_value >= (start_date 00:00 local, as UTC) AND stored_value < (end_date + 1 day, 00:00 local, as UTC). Either bound may be omitted.
- Exception: profit_distributions.period_start and period_end are calendar days, not moments. They are stored as local "YYYY-MM-DD" and mean whole local days, exactly like a date-range filter.
- All conversions go through db/timeutil.py. No other module does timezone arithmetic.

## 2. Inventory costing — weighted average
When stock comes in:
    new_cost = round((stock_before × cost_before + value_in) / (stock_before + qty_in))
If stock_before <= 0 or cost_before is NULL:
    new_cost = round(value_in / qty_in)
Applies to:
- material purchase: value_in = total_paid
- product purchase: value_in = total_paid
- production output: value_in = batch_total_cost
- positive ADJUSTMENT with a unit_cost supplied: value_in = unit_cost × qty_in
A positive ADJUSTMENT without unit_cost leaves unit_cost unchanged (NULL stays NULL).
Stock going out (sales, production consumption, packaging, waste, negative adjustments) never changes unit_cost.
Rounding: Python round(), applied once at the end of a calculation — never per line.

## 3. Production
- Each recipe line has cost_basis PER_UNIT (default) or PER_BATCH.
- PER_UNIT: needed = quantity_needed × batch_qty. PER_BATCH: needed = quantity_needed (once per batch, whatever the batch size).
- batch_total_cost = round(sum(needed × material.unit_cost)) over all lines.
- batch unit cost = round(batch_total_cost / batch_qty); stored on the batch.
- The product's unit_cost is updated by weighted average (section 2) with value_in = batch_total_cost.
- STOCK materials are deducted by `needed`. SERVICE materials cost money but have no stock.
- If any STOCK material is short: InsufficientStockError, nothing written.
- Recipe cost estimate for display: calculate_recipe_cost(product_id, batch_qty=1) returns the per-unit cost for a batch of that size.

## 4. Settings
settings (key/value):
- default_shipping_charge = 180000
- postage_estimate_window = 3
- default_postage_estimate = 0
- timezone = Asia/Tehran

channel_settings:
| channel   | applies_shipping_charge | applies_postage | default_packaging_kit_id |
|-----------|-------------------------|-----------------|--------------------------|
| WEBSITE   | 1                       | 1               | NULL                     |
| INSTAGRAM | 1                       | 1               | NULL                     |
| WHOLESALE | 0                       | 1               | NULL                     |
| IN_PERSON | 0                       | 0               | NULL                     |
| OTHER     | 0                       | 0               | NULL                     |

## 5. Packaging
- A packaging kit is a named recipe of STOCK materials (box, tape, filler...) with quantities.
- kit_cost = round(sum(quantity × material.unit_cost)).
- An order uses: the kit passed explicitly; else the channel's default kit; else none. Passing "no kit" explicitly is allowed.
- When an order commits stock (section 7), the kit's materials are deducted with reason PACKAGING and kit_cost is frozen on the order as packaging_cost.

## 6. Postage
- A postage batch records a bulk payment to the post office: paid_date, total_paid, order_count (> 0), notes.
- Current postage estimate = round(sum(total_paid) / sum(order_count)) over the most recent N batches by paid_date (N = postage_estimate_window). With no batches: default_postage_estimate.
- When an order commits stock, if its channel applies_postage, postage_cost = current estimate (unless overridden); otherwise 0. The value is frozen on the order.

## 7. Orders
Per line: list_price = quantity × unit_price; items_net = list_price − discount_amount.
Per order:
- shipping_charge: REVENUE. Default = default_shipping_charge if the channel applies_shipping_charge, else 0. Overridable (>= 0). Set at creation.
- packaging_cost, postage_cost: COSTS, frozen at commit (sections 5, 6).
- transaction_fee: COST, entered per order.
- cogs = sum(quantity × unit_cost_at_time), frozen at commit.

    revenue = sum(items_net) + shipping_charge
    profit  = revenue − cogs − packaging_cost − postage_cost − transaction_fee

Selling a product whose unit_cost is NULL is refused with ValidationError (field "unit_cost").

### Status and stock commitment
- DRAFT orders commit nothing: no stock deducted, no costs frozen, no stock check.
- An order commits when it is created with status PENDING/PAID/COMPLETED, or when it leaves DRAFT. Commit = stock check; deduct products (SALE) and packaging materials (PACKAGING); freeze unit_cost_at_time, packaging_cost, postage_cost. All in one transaction.
- orders.stock_committed (0/1) records whether this has happened.
- Allowed transitions via update_order_status: DRAFT → PENDING, PAID, COMPLETED; PENDING → PAID, COMPLETED; PAID → COMPLETED. Anything else raises ConflictError.
- Only process_return sets CANCELLED or REFUNDED:
  - CANCELLED: allowed from DRAFT, PENDING, PAID (not shipped). If stock_committed, restore products and packaging materials (reason RETURN). Excluded from all revenue and cost reporting.
  - REFUNDED: allowed from PAID, COMPLETED (shipped). Restore products only (RETURN); packaging was used up. packaging_cost + postage_cost + transaction_fee count as refund losses.

## 8. Stock adjustments
- Product quantities must be whole numbers. Material quantities may be fractional.
- WASTE quantity_change must be negative.
- No movement may take stock below zero: InsufficientStockError, nothing written.
- Every WASTE and ADJUSTMENT movement stores unit_cost_at_time = the item's unit_cost at that moment (NULL if unknown).
- WASTE reaches the P&L as waste_cost = |quantity_change| × unit_cost_at_time. ADJUSTMENT movements are corrections and do not reach the P&L.

## 9. Reports
Revenue-eligible statuses: PENDING, PAID, COMPLETED. Orders are dated by order_date.

Profit & loss for a date range:
- items_revenue = sum(items_net), eligible orders
- shipping_revenue = sum(shipping_charge), eligible orders
- total_revenue = items_revenue + shipping_revenue
- cogs, packaging_cost, postage_estimated, transaction_fees = sums over eligible orders
- gross_profit = total_revenue − cogs − packaging_cost − postage_estimated − transaction_fees
- postage_actual = sum(total_paid) of postage batches with paid_date in range
- postage_variance = postage_actual − (sum of postage_cost over eligible AND refunded orders in range)
- refund_losses = sum(packaging_cost + postage_cost + transaction_fee) over REFUNDED orders in range
- waste_cost = section 8, WASTE movements in range
- operating_expenses = sum(expenses) in range
- net_profit = gross_profit − postage_variance − refund_losses − waste_cost − operating_expenses
- order_count = number of eligible orders

Product performance: revenue = sum(items_net), cost = sum(quantity × unit_cost_at_time). Must reconcile exactly with items_revenue and cogs in the P&L for the same range.

Shipping summary for a date range: shipping_revenue, packaging_cost, postage_estimated, postage_actual, and net_shipping_result = shipping_revenue − packaging_cost − postage_actual, plus per-order averages.

## 10. Invoice numbers
Order invoices INV-000001..., purchase invoices PUR-000001... (one sequence shared by material and product purchases). Numbers come from a counters table incremented inside the same transaction as the insert. invoice_number columns are UNIQUE.

## 11. Partners and profit distributions
- Partner payouts are owners taking profit out of the business. They are NOT expenses and never change revenue, costs, profit, or any section 9 figure.
- Active partners' current_percentage values must sum to 100 (tolerance 0.01) to record a distribution.
- A distribution covers a period (period_start..period_end, local calendar days, section 1). Its total_profit_available is the section 9 net_profit for that period, snapshotted at recording time.
- Periods of distributions must not overlap: recording a distribution whose period overlaps an existing one raises ConflictError.
- Undistributed profit as of a date = sum of net_profit over every distributed or undistributed period up to that date (i.e. net_profit from the first recorded activity through that date) − sum of total_amount_distributed of distributions with period_end on or before that date.
- total_amount_distributed may not exceed the undistributed profit as of period_end unless the caller passes allow_exceeding=True; otherwise ValidationError (field "total_amount_distributed").
- Shares: amount = round(total × percentage / 100) per active partner; the rounding leftover goes to the partner with the highest percentage (ties: lowest id), so shares sum exactly to the total. Percentages are snapshotted per share.

## 12. Customer invoices
- A customer invoice shows only what the customer is charged: item lines (quantity, unit price, per-line discount), the shipping charge, and the total the customer pays = sum(items_net) + shipping_charge (= section 7 revenue).
- It never shows postage_cost, packaging_cost, transaction_fee, unit_cost, COGS, or profit — in any form.
