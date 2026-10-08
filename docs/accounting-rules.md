# Accounting rules — Rebel Store Manager

Currency: Rial, stored as INTEGER; Toman is display only (Toman = Rial ÷ 10, shown with one decimal digit only when the Rial amount is not a multiple of 10). All rounding of money is half-even to the Rial. Store timezone: Asia/Tehran.

Money was stored in integer Toman before migration 009, which multiplied every money column and the two money settings by 10 (nothing else changed).

## 1. Dates
- Moments in time (order_date, expense_date, purchase_date, production_date, movement_date, paid_date, distribution_date, created_at) are stored as UTC text "YYYY-MM-DD HH:MM:SS".
- Dates supplied by users are store-local (Asia/Tehran). A bare "YYYY-MM-DD" given as a record date means local midnight of that day, converted to UTC.
- A date-range filter (start_date, end_date) covers whole local days, inclusive: stored_value >= (start_date 00:00 local, as UTC) AND stored_value < (end_date + 1 day, 00:00 local, as UTC). Either bound may be omitted.
- Exception: profit_distributions.period_start and period_end are calendar days, not moments. They are stored as local "YYYY-MM-DD" and mean whole local days, exactly like a date-range filter.
- Also calendar days (local "YYYY-MM-DD"): orders.paid_date, orders.expected_settlement_date and settlements.settled_date (section 14). The paid_date in the moments list above is the postage batch's (section 6). "Today" for any business rule is today_local() in the store timezone.
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
- batch_total_cost is stored on the batch too (production_batches.total_cost); NULL for batches recorded before it was stored.
- The product's unit_cost is updated by weighted average (section 2) with value_in = batch_total_cost.
- STOCK materials are deducted by `needed`. SERVICE materials cost money but have no stock.
- If any STOCK material is short: InsufficientStockError, nothing written.
- Recipe cost estimate for display: calculate_recipe_cost(product_id, batch_qty=1) returns the per-unit cost for a batch of that size.

## 4. Settings
settings (key/value):
- default_shipping_charge = 1800000 (Rial; seeded as 180000 Toman by 003, × 10 by 009)
- postage_estimate_window = 3
- default_postage_estimate = 0
- timezone = Asia/Tehran
- display_currency = TOMAN (TOMAN or RIAL). Display only: how amounts are shown in the UI and on the customer invoice. Every stored, computed, sent and reported amount stays integer Rial; RIAL shows the stored integer, TOMAN shows Rial ÷ 10 (exact, integer arithmetic; one decimal digit only when needed, e.g. 1,800,005 Rial = 180,000.5 Toman).

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
- When an order commits stock, postage_cost = the explicit override if one was given; otherwise the current estimate if its channel applies_postage; otherwise 0. The value is frozen on the order.

## 7. Orders
Per line: list_price = quantity × unit_price; items_net = list_price − discount_amount.
Per order:
- shipping_charge: REVENUE. Default = default_shipping_charge if the channel applies_shipping_charge, else 0. Overridable (>= 0). Set at creation.
- packaging_cost, postage_cost: COSTS, frozen at commit (sections 5, 6).
- transaction_fee: COST, frozen per order: computed from the order's payment method, or entered by hand (section 14).
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
  - CANCELLED: allowed from DRAFT, PENDING, PAID (not shipped). If stock_committed, restore products and packaging materials (reason RETURN). Excluded from all revenue and cost reporting. If transaction_fee > 0 it is a loss (payment gateways rarely refund fees); packaging and postage are not losses, since nothing was shipped.
  - REFUNDED: allowed from PAID, COMPLETED (shipped). Restore products only (RETURN); packaging was used up. packaging_cost + postage_cost + transaction_fee count as refund losses.
  - made-to-order lines follow section 13.

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
- refund_losses = sum(packaging_cost + postage_cost + transaction_fee) over REFUNDED orders in range + sum(transaction_fee) over CANCELLED orders in range whose stock_committed = 1
- waste_cost = section 8, WASTE movements in range
- operating_expenses = sum(expenses) in range
- net_profit = gross_profit − postage_variance − refund_losses − waste_cost − operating_expenses
- order_count = number of eligible orders

Product performance: revenue = sum(items_net), cost = sum(quantity × unit_cost_at_time). Must reconcile exactly with items_revenue and cogs in the P&L for the same range.

Shipping summary for a date range: shipping_revenue, packaging_cost, postage_estimated, postage_actual, and net_shipping_result = shipping_revenue − packaging_cost − postage_actual, plus per-order averages.
- Shipped orders = revenue-eligible orders in range whose channel applies_postage = 1. shipping_revenue, packaging_cost and postage_estimated are sums over shipped orders only, so every figure derived from them (net results, averages, postage_gap) describes shipping alone: an IN_PERSON order that used a packaging kit is a cost of that sale, not of shipping. These totals equal the shipping-by-channel totals for the same range. (They can therefore differ from the P&L's shipping_revenue / packaging_cost / postage_estimated, which cover all eligible orders.)
- order_count = all revenue-eligible orders in range; shipped_order_count = shipped orders.
- postage_actual = sum(total_paid) of postage batches with paid_date in range. Batches pay for parcels, which only shipped orders produce, so it has no channel filter.
- net_shipping_result_estimated = shipping_revenue − packaging_cost − postage_estimated. This is the headline shipping result: it charges every shipped order the postage frozen on it, so a period whose postage batches are not yet paid does not look profitable.
- postage_gap = postage_estimated − postage_actual. Positive means part of the period's estimated postage has not been paid or recorded yet. (Not the P&L postage_variance: that one also counts postage on REFUNDED orders.)
- Per-order averages (avg_shipping_revenue, avg_packaging_cost, avg_postage_actual, avg_net_shipping_result, avg_net_shipping_result_estimated) = round(total / shipped_order_count), 0 when there are no shipped orders.

Purchases summary for a date range: material_purchases_total / material_purchases_count and product_purchases_total / product_purchases_count = sum(total_paid) and count of material_purchases / product_purchases with purchase_date in range (section 1 date rules). Purchases are inventory, not expenses: they raise stock and its weighted-average cost (section 2) and reach the P&L only as COGS (or production / packaging cost) when the stock is sold or consumed. No section 9 P&L figure includes them, and the two totals are reported separately, never added to operating_expenses.

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

## 13. Made-to-order products
- A product may be marked made_to_order. Such a product is manufactured when it sells; the shop does not hold finished units of it.
- A made-to-order product must have a recipe. Selling one with no recipe raises ValidationError (field "made_to_order").
- At commit (section 7), for each made-to-order line: take from finished stock first, then manufacture the shortfall from the recipe.
    from_stock = min(current_stock, quantity)
    to_make    = quantity − from_stock
- from_stock units are deducted from product stock as a SALE movement, exactly as for a normal product.
- For to_make units, the recipe is consumed at the quantities section 3 gives for a batch of to_make, using each material's unit_cost at that moment. STOCK materials are deducted with reason PRODUCTION_CONSUMPTION and reference_order_id set; SERVICE materials cost money but have no stock. If any STOCK material is short, InsufficientStockError names the material, and nothing is written. No production_batches row is created: the order itself is the record.
- The line's unit_cost_at_time is the weighted average of the two parts, rounded once:
    unit_cost_at_time = round((from_stock × product.unit_cost + make_cost) / quantity)
  where make_cost is the recipe cost for to_make units per section 3. When from_stock is 0, this is simply the per-unit manufacturing cost.
- A made-to-order product whose unit_cost is NULL is still sellable when to_make covers the whole line, since its cost comes from the recipe. The section 7 NULL-cost refusal applies only to units taken from finished stock.
- Manufacturing at sale time does not change the product's own unit_cost: no finished units are added to stock.
- On CANCELLED (section 7), materials consumed for this order are restored by reversing its own PRODUCTION_CONSUMPTION movements (reference_order_id = the order), exactly as packaging is. On REFUNDED, returned units are added back to product stock as finished goods at the line's unit_cost_at_time, blended in by weighted average (section 2), since a returned made item is now finished stock.

## 14. Payment methods, fees and settlements
Payment methods are owner-entered data (none are seeded). Each has a fee and a settlement rule. Examples: card to card (no fee, IMMEDIATE), Zarinpal (small percentage, DAYS_AFTER 1), Digipay (larger percentage, DAY_OF_NEXT_MONTH 7).

### Fee
- customer_total = sum(items_net) + shipping_charge (= section 7 revenue).
- Real example (Zarinpal: 0.5% up to 16,000 Toman, plus 500 Toman per transaction = fee_bps 50, fee_cap 160,000, fee_fixed 5,000 Rial): an order of 94,900,000 Rial pays 474,500 → capped 160,000 + 5,000 = 165,000 Rial; an order of 18,300,000 Rial pays 91,500 + 5,000 = 96,500 Rial. Both match the fees Zarinpal actually charged.
- The fee, in integer Rial, computed with integer arithmetic only:

      percentage_part = half_even(customer_total × fee_bps / 10000)
      if fee_cap is set: percentage_part = min(percentage_part, fee_cap)
      fee = percentage_part + fee_fixed

- fee_bps is basis points (150 = 1.5%), 0..10000; fee_fixed >= 0. Half-even means an exact .5 goes to the even neighbour: 1000 at 5 bps (0.5) → 0, 3000 at 5 bps (1.5) → 2. The cap applies after rounding.
- fee_cap is optional, per method, owner-entered (nothing is seeded): empty (NULL) = no cap; otherwise an integer >= 1 Rial. It caps the percentage part only; fee_fixed is never capped. A cap needs a percentage fee: a method with fee_bps 0 cannot have one, and setting fee_bps to 0 while a cap is set is refused unless the same change clears the cap.
- The fee is computed once, when the order is recorded, and frozen in orders.transaction_fee; later fee edits on the method (fee_bps, fee_fixed or fee_cap) never change an existing order. A caller may override it with any integer >= 0 (0 is a real zero). With no override and no method, the fee is 0.
- An order's method: an explicit method, no method, or the channel's default method (channel_settings.default_payment_method_id; none if unset). A new order, and a channel default, require an active method.

### paid_date
- The local calendar day the customer's money was paid. Set when the order first becomes PAID or COMPLETED (at creation, or by a status change from DRAFT/PENDING). Default: the local day of order_date (or today, with no order_date). Never in the future. Giving it for an order that does not become paid (DRAFT/PENDING creation, PAID → COMPLETED) is a ValidationError.
- Becoming paid freezes, from paid_date: paid_jalali_year / paid_jalali_month (the Jalali month of paid_date), and, with a method, expected_settlement_date per the method's rule. An order with no method still gets paid_date and its Jalali month, but no expected date and is never pending settlement.
- set_paid_date moves a paid, unsettled order's paid_date and recomputes these fields; the fee stays. It is refused (ConflictError) on an unpaid or settled order.

### Settlement rules and expected dates
- IMMEDIATE: expected on paid_date.
- DAYS_AFTER N (1..365): paid_date + N days.
- DAY_OF_NEXT_MONTH N (1..31): day N of the Jalali month after paid_date's month, clamped to that month's length (N = 31 in Mehr gives 30 Mehr; in Esfand, 29 or 30). Esfand rolls into Farvardin of the next Jalali year. The Jalali calendar is db/jalali.py, the same arithmetic as the frontend's date-fns-jalali.
- A method's rule (settlement_rule or settlement_days) cannot change while any of its orders is pending settlement (ConflictError naming the count): deactivate it and create a new method instead. Fee changes are always allowed.

### Pending and settling
- Pending item: an order with a payment method, status PAID or COMPLETED, and no settlement. Every method creates pending items, IMMEDIATE included; nothing is settled automatically. The owner checks the money and records each settlement.
- An order's expected amount = customer_total − transaction_fee (may be negative).
- IMMEDIATE / DAYS_AFTER: pending orders are grouped by expected date (due when expected date <= today, overdue when < today). A settlement takes any chosen set of this method's pending orders; settled_date must be >= the latest paid_date among them and not in the future. Settling before the expected date is allowed.
- DAY_OF_NEXT_MONTH: the method pays one amount per Jalali month (all orders paid from day 1 to the last day of the month, paid on day N of the next month, fees already deducted). Pending orders are grouped by paid Jalali month. A settlement covers a whole month and only once it has ended (its last day < today); it takes every pending order of that month, never a chosen subset; settled_date must be after the month's last day. One settlement per method and month. Once a month is settled it is closed: an order of that method can no longer become paid, or have its paid_date moved, into that month (ConflictError).
- A settlement stores expected_amount = sum(customer_total − transaction_fee) of its orders, frozen when recorded, and amount_received (>= 0) as entered. difference = amount_received − expected_amount is computed on read, never stored. amount_received, settled_date and note can be corrected later; the settlement's orders and expected_amount never change.
- A deactivated method still lists its pending orders, still settles and does not block marking an existing order paid.

### Cancel and refund
- Before settlement: a CANCELLED or REFUNDED order is no longer PAID/COMPLETED, so it drops out of pending, its group and the next settlement's expected_amount.
- After settlement: nothing is reversed. The order keeps its settlement_id; the settlement's expected_amount and amount_received stay as they were.
- Either way, the fee remains a loss as section 7 says (REFUNDED and committed CANCELLED orders), which is how it reaches refund_losses.

### Payment-method report
For a date range, one row per payment method (active, or inactive with any non-zero figure) plus a "no method" row:
- order_count, customer_total, transaction_fees: revenue-eligible orders (PENDING, PAID, COMPLETED) by order_date. Summed over all rows these equal the section 9 order_count, total_revenue and transaction_fees for the same range.
- fees_lost_on_returns: transaction_fee of REFUNDED orders plus CANCELLED orders with stock_committed = 1, by order_date. Summed, this is the fee part of section 9 refund_losses (refund_losses also holds the REFUNDED orders' packaging_cost and postage_cost).
- pending_expected: sum(customer_total − transaction_fee) of orders pending settlement now, by order_date.
- settled_expected, settled_received, settlement_difference (= received − expected): settlements by settled_date (local calendar day, inclusive range). 0 on the no-method row.
- The customer invoice never shows the fee, the method's name or the settlement (section 12).
