# Accounting rules — Rebel Store Manager

Currency: Rial, stored as INTEGER; Toman is display only (Toman = Rial ÷ 10, shown with one decimal digit only when the Rial amount is not a multiple of 10). All rounding of money is half-even to the Rial. Store timezone: Asia/Tehran.

Money was stored in integer Toman before migration 009, which multiplied every money column and the two money settings by 10 (nothing else changed).

## 1. Dates
- Moments in time (order_date, expense_date, purchase_date, production_date, movement_date, paid_date, distribution_date, created_at) are stored as UTC text "YYYY-MM-DD HH:MM:SS".
- Dates supplied by users are store-local (Asia/Tehran). A bare "YYYY-MM-DD" given as a record date means local midnight of that day, converted to UTC.
- A date-range filter (start_date, end_date) covers whole local days, inclusive: stored_value >= (start_date 00:00 local, as UTC) AND stored_value < (end_date + 1 day, 00:00 local, as UTC). Either bound may be omitted.
- Exception: profit_distributions.period_start and period_end are calendar days, not moments. They are stored as local "YYYY-MM-DD" and mean whole local days, exactly like a date-range filter.
- Also calendar days (local "YYYY-MM-DD"): orders.paid_date, orders.expected_settlement_date and settlements.settled_date (section 14). The paid_date in the moments list above is the postage batch's (section 6). "Today" for any business rule is today_local() in the store timezone.
- An expense_date or postage paid_date after today_local() is refused when recording and when editing (422 DATE_IN_FUTURE, field = that date; only the day is compared). An edit that leaves the local day unchanged keeps the stored time of day and is not re-checked.
- A backdated sale (order_date before today) moves only order_date and what follows from it; the cost, stock and packaging figures are still today's (section 7, Backdated orders).
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
For a MATERIAL, a cost of 0 means "not entered" (go-live sets every stock material to 0) and counts as NULL: a material purchase, or a positive ADJUSTMENT / stocktake gain with a unit_cost, sets new_cost = round(value_in / qty_in) instead of averaging with the old stock at 0. The existing cost-0 stock is therefore re-priced at the new cost from then on, so the stock value rises; this is intended. A purchase at price 0 into a cost-0 material leaves the cost 0. Past rows (movements, purchases, frozen order costs) are never touched. A product's cost of 0 is a real cost and averages as usual.
A positive ADJUSTMENT without unit_cost leaves unit_cost unchanged (NULL stays NULL).
Setting a missing cost («ثبت بها», `set_material_cost` / `set_product_cost`): prices stock that is already there, without a purchase or a count.
- A material may be given a cost only while its unit_cost is 0 ("not entered"; STOCK or SERVICE, active or archived); a product only while its unit_cost is NULL. Any other cost is refused, 409 `COST_ALREADY_SET` (details item_type, item_id, item_name, unit_cost). The stock does not matter to the rule; the screens offer it for items that hold stock, and for a SERVICE material or a material in an incomplete recipe.
- The cost is an integer Rial amount, at least 1 and at most MAX_MONEY (section 17); 0 and negative amounts are refused (422, field unit_cost).
- It sets unit_cost and nothing else: no stock movement, quantity unchanged. Past movements, purchases, batches, frozen order costs and earlier sales keep what they hold. The stock value rises by stock × cost; recipes that were INCOMPLETE because of this material become COMPLETE (section 13); a product with stock can then be sold (section 7).
- One audit operation (`set_material_cost` / `set_product_cost`, one op_id) with the old and new unit_cost. There is no note: the audit log has no field for one.
- A cost that is already set cannot be changed by this action. Until a separate «اصلاح بها» action exists, a wrong cost can be replaced only through the stocktake: count the item down to 0 (a loss), then count it back up with a unit cost (stock ≤ 0, so the supplied cost becomes the cost); this leaves two ADJUSTMENT movements.
Stock going out (sales, production consumption, packaging, waste, negative adjustments) never changes unit_cost.
Rounding: exact half-even to the Rial (a REAL quantity counts as the decimal it was entered as, section 8), applied once at the end of a calculation — never per line, never on floats. Where later sections write round(...), this is what it means.

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
- A postage batch can be corrected: `update_postage_batch` (total_paid, order_count, paid_date, notes) and `delete_postage_batch` (hard delete; the audit log keeps the whole old row). A paid_date after today_local() is refused (422, field paid_date, code DATE_IN_FUTURE), also when recording. Editing or deleting a batch changes the current estimate for FUTURE orders only; postage_cost frozen on existing orders never changes. Closed days: section 11.
- When an order commits stock, postage_cost = the explicit override if one was given; otherwise the current estimate if its channel applies_postage; otherwise 0. The value is frozen on the order.

## 7. Orders
Per line: list_price = quantity × unit_price; items_net = list_price − discount_amount.
The stored order_items.unit_price is a legacy display value, floor((list_price − discount_amount) / quantity); it is not the unit_price in the line above, and no figure reads it. The list unit price (list_price ÷ quantity, always exact) is what screens and the invoice show (`list_unit_price` in the API).
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
- Only process_return sets CANCELLED or REFUNDED (customer returns); only void_order sets VOIDED (a sale entered by mistake, section 20). A VOIDED order changes status no more and cannot be returned.
  - CANCELLED: allowed from DRAFT, PENDING, PAID (not shipped). If stock_committed, restore products and packaging materials (reason RETURN). Excluded from all revenue and cost reporting. If transaction_fee > 0 it is a loss (payment gateways rarely refund fees); packaging and postage are not losses, since nothing was shipped.
  - REFUNDED: allowed from PAID, COMPLETED (shipped). Restore products only (RETURN); packaging was used up. packaging_cost + postage_cost + transaction_fee count as refund losses.
  - made-to-order lines follow section 13.

### Backdated orders
`record_order(order_date=...)` accepts a past day ("YYYY-MM-DD" = local midnight, or "YYYY-MM-DD HH:MM"). A day after today_local() is refused for every status (422, field order_date, code DATE_IN_FUTURE, details {"today"}); only the day is compared, so a time later today is accepted.
- Follows the chosen day: orders.order_date, the default paid_date (the local day of order_date) and so its Jalali month and expected_settlement_date (section 14).
- Stays as of today (the moment of saving): the commit freezes unit_cost_at_time from the product's current unit_cost (or the made-to-order recipe at today's material costs), packaging_cost from today's kit cost, and postage_cost from today's estimate; stock is deducted now, and stock_movements.movement_date is the moment of saving, not the order date.
- Reports, the dashboard and the orders list filter on order_date, so a backdated order changes the figures of the past period it lands in. Partner profit distributions already recorded are not recomputed; the undistributed profit after that date rises.
- A backdated paid day inside a Jalali month that is already settled for a DAY_OF_NEXT_MONTH method is refused (ConflictError, MONTH_ALREADY_SETTLED).

## 8. Stock adjustments
- Product quantities must be whole numbers. Material quantities may be fractional. Size limits: section 17. A physical count is applied as a set of these adjustments: section 19.
- WASTE quantity_change must be negative.
- No movement may take stock below zero: InsufficientStockError, nothing written.
- Every WASTE and ADJUSTMENT movement stores unit_cost_at_time = the item's unit_cost at that moment (NULL if unknown).
- WASTE reaches the P&L as waste_cost. ADJUSTMENT movements are corrections and do not reach the P&L.
- Waste cost per item (the waste report's cost): sum(|quantity_change| × unit_cost_at_time) over that item's WASTE movements in the range, computed exactly (a REAL quantity counts as the decimal it was entered as) and rounded once, half-even, to the Rial. Movements with unknown unit_cost_at_time are left out; an item whose every movement is unknown has no cost (NULL).
- Waste report row fields: item_type, item_id, item_name, unit, total_wasted, waste_event_count, cost, unknown_cost_count. unit is the material's unit, or "piece" for a product (products have no unit column and count whole units).
- waste_cost (P&L) = the sum of those per-item rounded costs, so the waste report's total and the P&L always agree exactly, fractional quantities included. Example: 2.5 × 333 = 832.5 → 832 and 0.5 × 1 = 0.5 → 0 give waste_cost 832, not round(833).
- **Waste of a service** (`record_service_waste`, «ضایع‌شدن خدمت»): a SERVICE material has a cost but no stock, so its waste is a WASTE movement with `quantity_change` = −(units wasted; fractional allowed, within section 17) and `unit_cost_at_time` = the price per unit, and NO stock change (`current_stock` stays NULL, the stock replay never reads a service). It counts in the waste report and in `waste_cost` exactly like any other waste (the same sum, the same rounding). The price per unit defaults to the material's current `unit_cost` and can be overridden (integer Rial, at least 1) so that the stored price times the units is exactly the amount the owner saw; the amount is never stored on its own. A material whose `unit_cost` is 0 (not entered) is refused with 422 `MATERIAL_NO_UNIT_COST` (material_id, material_name): give it a price with «ثبت بها» first (section 2). The date is today or in the past (`DATE_IN_FUTURE`); a closed day (section 11) does not refuse a NEW record. One audit operation (`record_service_waste`, one op_id). A SERVICE has no ADJUSTMENT, no purchase and no count (stocktake): WASTE is the only movement it can have. A material's `type` cannot be changed after it is created. There is no edit or delete of a waste entry (a mistaken one cannot be undone yet).

## 9. Reports
Revenue-eligible statuses: PENDING, PAID, COMPLETED. Orders are dated by order_date. A VOIDED order (section 20) is in no figure of this section, not even refund_losses or postage_committed.

Profit & loss for a date range:
- items_revenue = sum(items_net), eligible orders
- shipping_revenue = sum(shipping_charge), eligible orders
- total_revenue = items_revenue + shipping_revenue
- cogs, packaging_cost, postage_estimated, transaction_fees = sums over eligible orders
- gross_profit = total_revenue − cogs − packaging_cost − postage_estimated − transaction_fees
- postage_actual = sum(total_paid) of postage batches with paid_date in range
- postage_committed = sum(postage_cost) over eligible AND REFUNDED orders in range: the postage frozen on every order that shipped
- postage_variance = postage_actual − postage_committed
- refund_fee_losses = sum(transaction_fee) over REFUNDED orders in range + sum(transaction_fee) over CANCELLED orders in range whose stock_committed = 1 (section 7). Equals the sum of the payment-method report's fees_lost_on_returns (section 14).
- refund_losses = refund_fee_losses + sum(packaging_cost + postage_cost) over REFUNDED orders in range
- waste_cost = section 8: the sum of the per-item rounded waste costs, WASTE movements in range
- operating_expenses = sum(expenses) in range
  (An expense can be corrected with `update_expense` (category, amount, expense_date, description) or removed with `delete_expense`, a hard delete whose old row stays in the audit log; there is no payment method on an expense. The P&L is computed live, so it follows. Dates and closed days: sections 1 and 11.)
- net_profit = gross_profit − postage_variance − refund_losses − waste_cost − operating_expenses
- order_count = number of eligible orders

postage_committed and refund_fee_losses are shown for explanation only: they are parts of postage_variance and refund_losses, not further deductions, so net_profit does not subtract them again.

Channel breakdown for a date range: one row per channel with at least one revenue-eligible order (PENDING, PAID, COMPLETED) by order_date; channels with no orders are left out. Each row's order_count, total_revenue and total_profit are summed over that channel's orders, where an order's revenue and profit are the per-order figures of section 7 (profit = revenue − cogs − packaging_cost − postage_cost − transaction_fee). Over all rows, order_count, total_revenue and total_profit sum exactly to the P&L's order_count, total_revenue and gross_profit for the same range — gross, not net: postage_variance, refund_losses, waste_cost and operating_expenses are not order-level and are never attributed to a channel. CANCELLED and REFUNDED orders are on neither side; their losses appear only in refund_losses. Each row also has avg_order_value = total_revenue ÷ order_count, rounded half-even to the Rial (every row has at least one order).

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
- Closed days. A day on or before the period_end of the LATEST recorded distribution (the greatest period_end; one lookup, no range search, so a gap before it counts as closed) is closed. On a closed day these are refused with 409 `PERIOD_ALREADY_DISTRIBUTED` (details distribution_id, period_end, date = the day that hit it): editing an expense's amount or date, editing a postage batch's total_paid or paid_date (the old day AND the new day are both checked), and deleting any expense or postage batch. Not refused: an expense's category or description, a postage batch's order_count or notes (they do not change net_profit), and any change on a day after period_end. There is no way to reopen a payout yet, so the refusal promises none. Reason: net_profit of a paid-out period must not change under a recorded distribution (total_profit_available is a snapshot, and undistributed profit is cumulative).
- Voiding or correcting an order (section 20) is refused the same way when the voided order's local day is closed, and for a correction also when the new order's day is.
- Known difference, to revisit with a reopen-payout feature: RECORDING a new expense or postage batch on a closed day is not refused (existing behaviour); it raises that period's net cost after the payout was made. The same holds for a new service waste (section 8), which reaches `waste_cost` on its own date.
- Editing or deleting an expense or postage batch never touches `profit_distributions` or `distribution_shares`.
- Shares: amount = round(total × percentage / 100) per active partner; the rounding leftover goes to the partner with the highest percentage (ties: lowest id), so shares sum exactly to the total. Percentages are snapshotted per share.

## 12. Customer invoices
- A customer invoice shows only what the customer is charged: item lines (quantity, unit price, per-line discount; the unit price is the list unit price, never a discounted one, and the line total is list_price − discount_amount), the shipping charge, and the total the customer pays = sum(items_net) + shipping_charge (= section 7 revenue).
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
- Recipe cost (display only): the cost of one unit from the recipe today is section 3 for a batch of 1. A recipe line whose material has unit_cost 0 or NULL ("not entered", section 2) makes the recipe INCOMPLETE and it has no recipe cost: the screens name the missing materials and never show a partial sum as a cost. It is never written to products.unit_cost; a stored weighted average is never replaced by it. A sale of a made-to-order product is not blocked by an incomplete recipe: it commits with the material costs as they are, so its frozen cost is too low until the missing costs are entered.
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
- fee_bps and fee_fixed always have an integer value: an update that sends null (or a non-integer) for either is refused (422, field = that field) and nothing is written; omitted = unchanged. Only fee_cap can be cleared with null.
- fee_cap is optional, per method, owner-entered (nothing is seeded): empty (NULL) = no cap; otherwise an integer >= 1 Rial. It caps the percentage part only; fee_fixed is never capped. A cap needs a percentage fee: a method with fee_bps 0 cannot have one, and setting fee_bps to 0 while a cap is set is refused unless the same change clears the cap.
- The fee is computed once, when the order is recorded, and frozen in orders.transaction_fee; later fee edits on the method (fee_bps, fee_fixed or fee_cap) never change an existing order. A caller may override it with any integer >= 0 (0 is a real zero). With no override and no method, the fee is 0.
- An order's method: an explicit method, no method, or the channel's default method (channel_settings.default_payment_method_id; none if unset). A new order, and a channel default, require an active method.

### paid_date
- The local calendar day the customer's money was paid. Set when the order first becomes PAID or COMPLETED (at creation, or by a status change from DRAFT/PENDING). Default: the local day of order_date (or today, with no order_date). Never in the future. For a backdated order the default is the past order day, while cost, stock and packaging were frozen today (section 7, Backdated orders). Giving it for an order that does not become paid (DRAFT/PENDING creation, PAID → COMPLETED) is a ValidationError.
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
- A VOIDED order (section 20) is never a loss: a pending one drops out of pending like a cancelled one, and a settled order cannot be voided.

### Payment-method report
For a date range, one row per payment method (active, or inactive with any non-zero figure) plus a "no method" row:
- order_count, customer_total, transaction_fees: revenue-eligible orders (PENDING, PAID, COMPLETED) by order_date. Summed over all rows these equal the section 9 order_count, total_revenue and transaction_fees for the same range.
- fees_lost_on_returns: transaction_fee of REFUNDED orders plus CANCELLED orders with stock_committed = 1, by order_date. Summed, this is the fee part of section 9 refund_losses (refund_losses also holds the REFUNDED orders' packaging_cost and postage_cost).
- pending_expected: sum(customer_total − transaction_fee) of orders pending settlement now, by order_date.
- settled_expected, settled_received, settlement_difference (= received − expected): settlements by settled_date (local calendar day, inclusive range). 0 on the no-method row.
- The customer invoice never shows the fee, the method's name or the settlement (section 12).

## 15. Audit log
- Every INSERT, UPDATE and DELETE on an accounting table is recorded in `audit_log`, in the same transaction as the change: a failed change leaves no row, and a failed log insert undoes the change. Accounting tables are all tables except `counters` (invoice numbering), `schema_migrations` and the audit tables; a new table is audited unless listed as an exception in `db/audit.py`.
- A row holds the moment (UTC, section 1), the table (`entity_type`), the row key (`entity_id`), the action, the business operation (the `db/` function name, or `UNLABELLED` for a write outside one), the shared `op_id` of one business operation, an optional actor (none until there are users), and the data: INSERT = the whole new row, DELETE = the whole old row, UPDATE = only the changed columns, before and after. `updated_at` is never logged. Money is integer Rial exactly as stored.
- The log is append-only: UPDATE and DELETE on `audit_log` are refused. The one deliberate way to clear it is `reset_audit_log` (the go-live reset): it first writes every row to a verified JSON-lines archive (by default `data/backups/audit-archive-<moment>.jsonl`, never overwritten), then clears the log in one transaction and leaves a single `reset_audit_log` row recording the count, archive name and checksum. The go-live reset (`python -m tools.go_live_reset`, `db/go_live.py`, docs/RUNNING.md section 10) is its only caller: it names the archive `audit-archive-golive-<moment>.jsonl` and, in the same transaction, sets `PRAGMA user_version` = 1 as a marker that survives a later plain audit reset; a database with a marker and data is never reset again.
- Rows that existed before migration 012 are not logged; the log starts at the migration. `name_key` (section 16) is never logged, like `updated_at`.
- Read-only access: `GET /audit-log`, filtered by table, row key, `op_id`, operation and local-day range, newest first, with `limit`/`offset` and a total.

## 16. Names
- A name typed by the user is saved in its **stored form** (`db/names.py` `stored_form`): NFC; Arabic Yeh/Kaf become Persian Yeh/Kaf; Arabic-Indic digits become Persian digits; every whitespace run (NBSP, tab, newline) becomes one space, stripped; invisible and bidi control characters (zero-width space, LRM/RLM, U+202A–202E, U+2066–2069, BOM, soft hyphen, word joiner) are removed; ZWNJ is kept only between two Arabic-script letters. A name with nothing left is empty and refused.
- Two names are the **same name** when their comparison key is equal: the stored form, then NFKC, ZWNJ removed, Persian/Arabic-Indic digits to ASCII digits, casefold (`name_key`). The key lives in `name_key` on each table; searching, sorting and displaying names are unchanged.
- Names are unique, active or not (a deactivated name stays reserved), in: products, materials, suppliers, partners, payment methods, packaging kits, expense categories, and categories (among siblings: same kind and parent). A create or rename that repeats a name, even in another spelling, is refused with 409: `NAME_DUPLICATE` (details `entity`, `existing_id`), or `CATEGORY_DUPLICATE_NAME` / `PAYMENT_METHOD_DUPLICATE_NAME` for those two. The unique index on `name_key` is the final guard; rows without a key still count in the check.
- Existing names are never rewritten, merged or deleted (invoices, the audit log and reports show what was typed). Migration 013 adds `name_key` (NULL); `init_db` fills it afterwards. Rows whose key collides with another row keep `name_key` NULL, are logged and returned by `init_db` / `name_keys.find_name_collisions` for the later integrity check; the backfill touches neither `name` nor `updated_at`, and writes no audit row.
- `name_key` is never logged in the audit log (section 15) and never sent by the API.

## 17. Limits
- Money is an integer count of Rial with a size of at most `MAX_MONEY` = 9,007,199,254,740,991 (2^53 − 1: the largest integer a JSON/JavaScript client round-trips exactly, and far below SQLite's 2^63 − 1 so sums of many rows cannot overflow). It applies to every amount a client sends (request bodies and the `fee-preview` amount) and to every amount `db/` computes before it is written (line total, order total, fee, unit cost, batch cost, kit cost, settlement expected amount): a larger size, above or below zero, is refused with 422 `AMOUNT_TOO_LARGE` (details `max`, field = the amount to change), nothing is written. Whether an amount may be negative is each field's own rule (every amount field is ≥ 0). The largest amount in the real data was 300,000,000 Rial.
- Quantities: whole-number fields (order line, production batch, product purchase) are integers in 1..1,000,000; material quantities (purchase, recipe line, kit item) are numbers in (0, 1,000,000,000]; stock fields (`initial_stock`, `min_stock`) are 0..1,000,000,000; a stock adjustment is ±1,000,000,000 and never 0 (WASTE negative and whole numbers for products stay as in section 8). A non-integer where a whole number is required is 422 `QUANTITY_NOT_WHOLE`; out of range is 422 `QUANTITY_OUT_OF_RANGE` (details `min`, `max`: the bound that was crossed, the other side null).
- Report totals add up stored rows without a per-query guard: an overflow would need more than a thousand rows of the maximum amount.
- Request-shape errors (wrong type, missing field, bad query) answer in the same error envelope as every other refusal, type `RequestValidationError`, `details.errors` = the list of {loc, msg, type}; the input itself is never echoed.

## 18. Integrity check
`python -m tools.integrity_check [--db PATH]` reads the database (SQLite `mode=ro` and `query_only`; it never runs migrations or any write) and compares stored numbers with what `db/` computes. Exit 0 OK, 1 problems, 2 could not run (or a check could not run).
- a. SQLite `integrity_check` and `foreign_key_check`. b. Each settlement's stored `expected_amount` = sum of its orders' customer_total − transaction_fee (section 14); its orders belong to its method, were paid on or before `settled_date`, and (monthly rule) in its Jalali month. c. Each order: `get_order` and `list_orders` agree on customer_total; per line `list_price` is a multiple of `quantity` and `0 <= discount_amount <= list_price`; a paid order has `paid_date` and the matching Jalali month; an unsettled order's `expected_settlement_date` follows its method's rule; a negative fee is a failure.
- An order that is PAID/COMPLETED has a `paid_date`, except a legacy order: PAID/COMPLETED with no payment method and `paid_date` NULL is reported as INFO (its ids, every run, exit code unchanged). Such orders were created before migration 008 added `paid_date` (008 does not backfill it, and an order with no method has no settlement to move). The same gap on an order WITH a payment method is a failure.
- A fee that differs from the method's *current* rule, or is larger than the order total, is only a WARN: the fee is frozen per order and may be typed by hand or the rule edited later (section 14).
- d. Stock: a product's stock equals the sum of its movements exactly (a product can only get stock through a movement). A material created with `initial_stock` has no opening row in the ledger, so its opening is `current_stock − sum(movements)`: taken from the audit log's INSERT row when there is one (then it must match, within the tolerance), otherwise reported as INFO; a negative opening or a running balance below zero is a failure. Tolerance for REAL stock: `max(1e-6, 1e-9 × max(|stock|, sum |movements|))`. PURCHASE, PRODUCTION_OUTPUT and PRODUCTION_CONSUMPTION movements must equal the purchase and batch rows. SALE / RETURN / PACKAGING per order is not checked.
- e. Purchase `unit_cost` = total_paid ÷ quantity_bought; batch `unit_cost` = total_cost ÷ quantity_produced; batch `total_cost` = sum(quantity_used × unit_cost_at_time) (sections 2, 3), each rounded once, half-even.
- f. Invoice numbers have the `INV-` / `PUR-` format, no duplicates, and the counters are not behind the highest number. g. A distribution's `total_amount_distributed` = sum of its shares, periods do not overlap, and, when the stored percentages sum to exactly 100, each share is the section 11 calculation; when they do not, that is an INFO line (the leftover rule is not specified). h. Name collisions (section 16) are WARN lines, listed every run, and never change the exit code.
- i. Voided orders and corrections (needs migration 014): a VOIDED order has void_reason and voided_at, stock_committed 1, no settlement, and its movements net to zero per item; a replaces_order_id points at a VOIDED order; the all-time P&L order_count and total_revenue equal those of the PENDING / PAID / COMPLETED orders. Check d1 replays a void's RETURN movements like any other movement.
- d4. Service waste: a SERVICE material has `current_stock` NULL or 0, and every movement on it is a WASTE with a negative quantity and a `unit_cost_at_time` of at least 1 (section 8). Reads stored rows only.
- A check that needs a newer schema than the database has is SKIPPED with the reason; money checks need migration 009 (Rial storage).

## 19. Stocktake
A physical count turns into stock corrections (`db/stocktake.py`, `POST /stocktake`, screen «شمارش موجودی»). It adds no new accounting rule: each correction is a section 8 stock adjustment.
- **Pause sales and adjustments while a count is running.** The count is compared with the system stock the screen showed (`system_quantity`); if an item's live stock is no longer that quantity, nothing is written and the refusal is 409 `STOCKTAKE_STALE` listing those items. The screen keeps every typed count, marks the changed rows, and a marked row must be rechecked before applying.
- All or nothing: every differing item is corrected in ONE transaction, or none. An item left blank is not counted; an item counted equal to the system stock is unchanged. Products are counted in whole numbers, materials may be fractional (within section 17); services have no stock and are refused. Inactive items can be counted (an archived item can still hold stock): the stocktake is the only caller that may adjust an inactive item.
- The difference is `counted − system`, computed as exact decimals (a REAL reads as the decimal it was entered as) rounded half-even to 1e-9; 0 after that rounding is "no change". Counting an item down to 0 removes exactly what the system holds.
- Every correction is an `ADJUSTMENT` movement (a loss too: section 8, not WASTE, so a count does not reach the P&L; record known breakage as WASTE separately), dated with the stocktake day (default today, never in the future), with the note «شمارش موجودی <Jalali date>» (+ « — » + the caller's note). The audit log shows one `op_id` and the operation `apply_stocktake` for the whole count.
- Valuation (section 2, nothing new): a gain without `unit_cost` adds stock at the item's current cost (unchanged); a gain with `unit_cost` blends it by weighted average (stock ≤ 0 or no cost: the supplied cost becomes the cost). A gain on an item with no unit cost (a product that was never bought, made or costed) REQUIRES a unit cost (422 `PRODUCT_NO_UNIT_COST`, field `items.N.unit_cost`): opening stock needs it, because an unpriced product cannot be sold. A loss takes stock at the current cost and gives no cost. The review shows each line's value = difference × cost used, rounded once half-even; an item with unknown cost has no value.
- Applying the same count twice is stale the second time (the first changed the stock), so a double click cannot count twice.

## 20. Voided orders and corrections
A sale entered by mistake (wrong product, quantity, price, payment method, customer or date) is voided, never edited in place (`db/order_voids.py`). A void is not a customer return: a customer who cancels or sends goods back is still CANCELLED or REFUNDED (section 7).
- **Void** (`void_order`, «باطل‌کردن سفارش»): a PENDING, PAID or COMPLETED order becomes VOIDED with a required reason (`void_reason`, stored form as names are, at most 500 characters) and the moment (`voided_at`, UTC). The row, its lines, its invoice number and every frozen figure stay.
- **What comes back.** The order's own SALE, PACKAGING and PRODUCTION_CONSUMPTION movements are reversed, each as a RETURN movement with `reference_order_id` = the order and the note «ابطال سفارش <invoice> — <reason>». A made-to-order line returns only the units it took from finished stock, plus the materials it consumed; SERVICE materials have no stock. Nothing is written for payment, fee, settlement, postage or partners: VOIDED is in no status list, so the order leaves every figure of sections 9, 11 and 14, and its fee is no loss (the sale never happened).
- **Cost of the returned stock.** Returned stock is stock coming in at its frozen cost, by weighted average (section 2): `new_cost = round((stock × cost + Σ qty × frozen_cost) / (stock + Σ qty))`, materials treating a cost of 0 as "not entered". The COGS or packaging value the void takes out of the P&L thus goes back into stock; when no cost changed since the sale the cost stays exactly as it is. The frozen cost is the movement's own `unit_cost_at_time`, which the order commit stores on SALE, PACKAGING and PRODUCTION_CONSUMPTION movements from this section on. For an order committed before that: a product's frozen cost is its line's `unit_cost_at_time` when that is the product's cost at commit (a product not made to order, or a made-to-order line taken wholly from stock); any other movement (a mixed made-to-order line, every material) comes back at the current cost, which then stays.
- **Refused** (409, typed details), checked in this order, all listed by `plan_void` (read-only, `GET /orders/{id}/void-preview`):
  - `ORDER_ALREADY_VOIDED` (order_id, voided_at, replaced_by_order_id)
  - `ORDER_HAS_RETURN` (order_id, status): a CANCELLED or REFUNDED order; cancelling a return is not possible
  - `ORDER_NOT_COMMITTED` (order_id, status): a DRAFT committed nothing; cancel it instead
  - `ORDER_ALREADY_SETTLED` (order_id, settlement_id): the money was received in a settlement
  - `PERIOD_ALREADY_DISTRIBUTED` (distribution_id, period_end, date): the order's local day is closed (section 11)
  - `STOCKTAKE_AFTER_SALE` (order_id, item_type, item_id, item_name, stocktake_date): a stocktake recorded after the sale (an ADJUSTMENT the audit log labels `apply_stocktake`, or with the stocktake note) counted a product or material the sale moved; returning its stock would count it twice. A manual adjustment or a production run does not block.
  - A blank reason is 422 `VOID_REASON_REQUIRED` (field reason).
- **Correction** (`correct_order`, «اصلاح سفارش»): voids the order and records the right sale with `record_order` in ONE transaction and ONE audit operation (`correct_order`, one op_id); the new order's `replaces_order_id` is the voided order (at most one replacement each, unique index), and both sides show the link. The new order is a new sale in every respect: the day the user picks (today or past, `DATE_IN_FUTURE`, section 7 Backdated orders), today's costs, kit cost, postage estimate and fee, a new invoice number, the settlement rules of section 14 (`MONTH_ALREADY_SETTLED`). It may be PENDING, PAID or COMPLETED, not DRAFT, and its local day must not be closed either. Any refusal of either part leaves both orders as they were. A replacement can itself be corrected later; a voided order cannot.
- **Reading.** The orders list leaves VOIDED orders out unless asked (`include_voided`, or status VOIDED); their profit is not shown. The customer invoice of a VOIDED order is still printable and carries «این فاکتور باطل شده است» and the replacement's number (section 12 otherwise unchanged).
- **Schema** (migration 014): `orders.status` gains VOIDED; `void_reason`, `voided_at`, `replaces_order_id` (CHECK: VOIDED exactly when `voided_at` is set, VOIDED needs a reason, an order never replaces itself). The table was rebuilt with every row, id and the AUTOINCREMENT mark kept and no audit row written.
