# Stage 1 plan: supplier payables (A) + purchase edit / cancel / correct (B)

## Context
- **Why.** Item D of the master plan (`docs/plans/2026-10-supplier-units-cost-update.md`, edits E3, renumbered to migration 015 and check "j"). The shop also needs a way to fix a purchase entered by mistake. Today a purchase can only be created: `db/purchases.py:47,157` has no update, cancel or delete.
- **Baseline.** `main` = `origin/main` = `c87981f65720a04feac3ac4ee7deaf63df3018a3`, tree clean. Migrations 001–014.
- **Test database fingerprint (start).** `data\shop.db`: 622,592 bytes, mtime 2026-10-24T11:49:33.808Z, sha256 `210351AF6645438B2E8E05B54444D2997A9C6697F5ABFBEF7FFD9A086371861F`. The end values are in the reply.
- **How purchases are recorded today**
  - `record_material_purchase` / `record_product_purchase` work in one transaction:
    1. Allocate a `PUR-` number.
    2. INSERT the purchase row.
    3. Blend the item cost: `blend_unit_cost`, with `zero_is_unknown` for materials.
    4. Write one `PURCHASE` stock movement. Its note is `Material purchase #<id> (invoice PUR-…)` and it has no FK back to the purchase.
  - `total_paid` is the invoice total. Nothing records cash.
  - `supplier_id` is optional.
  - Purchases reach only `get_purchases_summary` (not P&L) and integrity checks d2 (Σ PURCHASE movements = Σ `quantity_bought` per item), e and f.
  - The test database has 2 material purchases (both with a supplier, one at total 0, both covered by audit rows) and no distributions.
- **Cost history facts that shape B**
  - A costed ADJUSTMENT stores the *blended result* as `unit_cost_at_time`, not the cost it was given (`adjustments.py:128-177`). A made-to-order REFUND does the same (`returns.py:78-104`).
  - `set_material_cost` / `set_product_cost` and the go-live reset change a cost with no movement at all.
  - So the incoming value of past events cannot be rebuilt from movements. A general replay cannot be exact.

## Build order and the one migration
- **Slice A first** (`feat/supplier-payables`). Then **slice B** (`feat/purchase-correction`, branched from `main` after A is merged).
- **Why A first:**
  - The master plan orders D first.
  - B's cancel rules depend on allocations: payments block, move or go with a cancel.
  - Migration 015 then ships once, in A, and B ships code only.
- **One migration, `015_supplier_payables_purchase_status.sql`, built in slice A.** It holds A's two new tables and B's columns. So the purchase tables are rebuilt exactly once, and B needs no migration. B2 (unit conversion) moves to **017**: 016 is purchase invoices (see "Amendment: purchase invoices and services" before slice B).

## Migration 015 (exact)
Runs with foreign keys OFF (`db/connection.py:115`), in one transaction. Steps, in this order:

1. **Save the AUTOINCREMENT marks.** `CREATE TEMP TABLE m015_sequence` holds the `sqlite_sequence` rows of `material_purchases` and `product_purchases`.
2. **Create `material_purchases_new`.** It keeps every 001 column and constraint, and adds:
   - `status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','CANCELLED'))`
   - `cancel_reason TEXT`, `cancelled_at TEXT` (UTC moment)
   - `replaces_purchase_id INTEGER REFERENCES material_purchases(id)`
   - `stock_movement_id INTEGER REFERENCES stock_movements(id)`: the purchase's own PURCHASE movement
   - `cancel_movement_id INTEGER REFERENCES stock_movements(id)`
   - `item_cost_before INTEGER CHECK (item_cost_before IS NULL OR item_cost_before >= 0)` and `item_cost_after INTEGER CHECK (... >= 0)`. These are the item's unit cost just before and just after this purchase. `item_cost_after` NULL means "not known" (a legacy row). `item_cost_before` NULL with `item_cost_after` set means the product had no cost.
   - Table CHECKs:
     - `(status='CANCELLED') = (cancelled_at IS NOT NULL)`
     - `status<>'CANCELLED' OR length(trim(coalesce(cancel_reason,'')))>0`
     - `(status='CANCELLED') = (cancel_movement_id IS NOT NULL)`
     - `replaces_purchase_id IS NULL OR replaces_purchase_id<>id`
     - `item_cost_after IS NOT NULL OR item_cost_before IS NULL`
3. **Copy every row** with its id. The new columns are filled as follows:
   - **`stock_movement_id`:** the single movement with reason PURCHASE, `item_type`/`item_id` matching, and notes LIKE `'Material purchase #'||id||' (%'`. NULL when there is not exactly one match.
   - **`item_cost_before` / `item_cost_after`, from the audit log:**
     - Find the purchase's audit INSERT row and take its `op_id`.
     - Find the item's UPDATE row in that `op_id`.
     - If `json_type(after_json,'$.unit_cost')` is set, take the before and after values.
     - Otherwise the cost did not change. Both values are the item's last earlier logged `unit_cost` (an earlier UPDATE, or its INSERT).
     - When nothing is found, both stay NULL (legacy).
4. **`DROP` the old table, `RENAME` the new one, and restore `sqlite_sequence`** as `MAX(saved seq, MAX(id))`, the same as 014.
5. **Same steps 2–4 for `product_purchases`** (`quantity_bought INTEGER`, `REFERENCES product_purchases(id)`).
6. **Recreate the indexes exactly:**
   - `idx_material_purchases_material_id`, `_supplier_id`, `idx_material_purchases_invoice_number_unique`, and the product equivalents
   - new: `ux_*_purchases_replaces` (UNIQUE partial on `replaces_purchase_id`)
   - new: `ux_*_purchases_stock_movement` (UNIQUE partial)
   - new: `idx_*_purchases_status`
7. **New table `supplier_payments`:**
   - `id` AUTOINCREMENT
   - `supplier_id` REFERENCES suppliers (NULL only for a payment on a purchase with no supplier)
   - `payment_date TEXT NOT NULL` (UTC moment)
   - `amount INTEGER NOT NULL CHECK (amount > 0)`
   - `method TEXT NOT NULL CHECK (method IN ('CASH','CARD','BANK_TRANSFER','CHEQUE','OTHER'))`
   - `reference`, `note`, `created_at` default now, `updated_at`
   - index on `(supplier_id, payment_date)`
8. **New table `supplier_payment_allocations`:**
   - `id`
   - `payment_id` REFERENCES supplier_payments ON DELETE CASCADE
   - `material_purchase_id` / `product_purchase_id` (nullable FKs) with `CHECK ((material_purchase_id IS NULL) <> (product_purchase_id IS NULL))`
   - `amount INTEGER NOT NULL CHECK (amount > 0)`
   - UNIQUE `(payment_id, material_purchase_id)` and UNIQUE `(payment_id, product_purchase_id)`
   - indexes on both purchase columns
9. **Backfill payments.** Every existing purchase with `total_paid > 0` gets:
   - one payment: amount = `total_paid`, `payment_date` = `purchase_date`, supplier = the purchase's, method OTHER, note «پیش از ثبت بدهی‌ها»
   - one allocation, matched by a temp mapping table
   - Purchases with total 0 get none: they are "paid" with 0 outstanding.
10. **Only now create the triggers:**
    - the `updated_at` trigger on `supplier_payments` (`AFTER UPDATE OF` its business columns)
    - `trg_audit_*` for both purchase tables (regenerated from `audit_trigger_sql` for the new columns) and for both new tables
    - So the copy and the backfill write no audit rows. Purchases have no `updated_at`.
- **Go-live (`db/go_live.py`):**
  - Both new tables are CLEAR.
  - `CLEAR_ORDER` gets `supplier_payment_allocations`, then `supplier_payments`, inserted before `material_purchases`.
  - `unclassified_tables` and the test cover them.
- **Docs:**
  - `accounting-rules.md`: new §21 «Supplier payables» (slice A) and §22 «Cancelled and corrected purchases» (slice B)
  - §9 purchases summary; §18 checks j (A) and k (B), plus a d2 note (B)
  - the migration header comment lists every object that references the purchase tables, checked against a 001–014 database and the test database, as 014 does

## Update tool and rehearsal (shop laptop)
- **`update-rebel.cmd` on the real database runs the usual steps:**
  - preflight
  - integrity before (blocks on FAIL/ERROR only)
  - stop, verified pre-update backup
  - pull, deps, build
  - `init_db` in a fresh process applies 015
  - integrity after, now including j
  - automatic rollback on any failure
  - start
- **What 015 does to the real data:**
  - rebuilds the purchase tables (0 or a few rows)
  - creates one payment per purchase with total > 0
  - sets the movement links and the cost snapshots from the audit log
  - Nothing else changes: no item stock or cost, no order, no P&L figure.
- **New invariants in `tools/update_app/invariants.py` (slice A):**
  - `purchases`: every material and product purchase row, compared on the columns both sides have, through `list_*_purchases` (cancelled included). The new columns are INFO.
  - `purchases_summary` all time: the totals and counts must be equal.
  - **After-only checks** (when the tables did not exist before): every supplier's outstanding is 0, and payment count = number of purchases with total > 0.
  - **INFO lines:** payments backfilled; purchases without a movement link; purchases without a cost snapshot (these cannot be cancelled in B).
- **Rehearsal:** `--rehearse data\restore-test\<copy>\shop.db` on a copy the owner supplies. I never read or touch `data\restore-test\real\`. The slice is approved only after a clean rehearsal.

---

## Slice A: supplier payables (`feat/supplier-payables`)

### Rules
- **Status is derived, never stored** (`db/supplier_payments.py`):
  - `paid` = Σ allocations of the purchase; `outstanding` = `total_paid` − `paid`
  - `payment_status`:
    - UNPAID «پرداخت‌نشده» when paid = 0 and the total is above 0
    - PARTIAL «پرداخت بخشی»
    - PAID «پرداخت‌شده», which includes a total of 0
- **New purchase.** `payment` = FULL (the default; today's behaviour), NONE, or PARTIAL with an amount, plus `method` and `reference`. Any payment is created in the same transaction and `op_id`.
  - NONE or PARTIAL without a supplier → `SUPPLIER_REQUIRED_FOR_CREDIT`.
  - PARTIAL needs `0 < amount < total`.
- **`record_supplier_payment(supplier_id, payment_date, amount, method, reference, note, allocations=None)`:**
  - **Date:** a local day, today or in the past; a future day is `DATE_IN_FUTURE`.
  - **Before a purchase:** a payment day before the day of any purchase it pays is `SUPPLIER_PAYMENT_BEFORE_PURCHASE` (E3).
  - **Amount:** 1..`MAX_MONEY`. Each allocation is 1..outstanding, checked inside the transaction (race guard: the outstanding is re-read inside it).
  - **Allocations given:** Σ must equal the amount exactly, otherwise `SUPPLIER_PAYMENT_ALLOCATION_MISMATCH`.
  - **Allocations omitted:** the db assigns them oldest first (purchase_date, then id), using `allocate_oldest_first`. That is the one formula, in `db/`.
  - **No advances, no overpayment:** an amount above the supplier's total outstanding is `SUPPLIER_PAYMENT_EXCEEDS_BALANCE`. An allocation above its purchase's outstanding is `SUPPLIER_PAYMENT_EXCEEDS_DUE`.
  - Every purchase must belong to that supplier (`SUPPLIER_PAYMENT_SUPPLIER_MISMATCH`). A payment on a purchase with no supplier has `supplier_id` NULL and pays only purchases with no supplier.
- **`update_supplier_payment`:** only date, method, reference and note. The date is re-checked: not in the future, not before its purchases.
- **`delete_supplier_payment`:** hard delete; its allocations cascade; the audit log keeps the rows.
- All three are `@audited`.
- **Reads:**
  - `list_*_purchases` and `get_*_purchase` gain `paid`, `outstanding` and `payment_status`. `get_*` also gains `payments` (date, amount, method, reference, payment id).
  - `get_payables()`: one row per supplier with an open balance, with `purchases_total`, `paid_total`, `outstanding`, `oldest_unpaid_date` and its open purchases. A "no supplier" row would only ever hold FULL purchases, so it is never open.
  - `list_supplier_payments(supplier_id, start_date, end_date)`.
- **Reports, P&L, cash vs accrual:**
  - §9 already treats purchases as stock, not expense: they reach P&L only as COGS or consumption. Paying a supplier moves cash and debt only.
  - So P&L, channel, product, payment-method and partner figures are unchanged (E3: partner payouts unaffected; a test proves it).
  - `get_purchases_summary` adds `supplier_payments_total` and `supplier_payments_count` (by `payment_date` in range) and `payables_outstanding` (now, ignoring the range).
- **Closed days (§11):**
  - Payments never change `net_profit` or a distribution snapshot. So recording, editing or deleting a payment on a closed day is **not** refused.
  - A purchase's paid/unpaid state is derived, so there is no status change to guard. See Q3.
- **Dashboard:** the master plan does not add payables there. The purchases KPI card is unchanged.

### Error codes (typed details, Persian text in `components/purchases/copy.ts` and `settlements/copy.ts`)
| Code | HTTP | Details | Persian |
|---|---|---|---|
| `SUPPLIER_REQUIRED_FOR_CREDIT` | 422 | empty model (E3) | «برای خرید نسیه یا پرداخت بخشی، تأمین‌کننده را انتخاب کنید» |
| `SUPPLIER_PAYMENT_EXCEEDS_DUE` | 409 | purchase_kind, purchase_id, outstanding | «مبلغ پرداخت از ماندهٔ این خرید بیشتر است» |
| `SUPPLIER_PAYMENT_EXCEEDS_BALANCE` | 409 | supplier_id, outstanding | «مبلغ پرداخت از کل بدهی به این تأمین‌کننده بیشتر است» |
| `SUPPLIER_PAYMENT_SUPPLIER_MISMATCH` | 422 | purchase_kind, purchase_id, supplier_id | «این خرید از تأمین‌کنندهٔ دیگری است» |
| `SUPPLIER_PAYMENT_ALLOCATION_MISMATCH` | 422 | amount, allocated | «جمع تقسیم پرداخت با مبلغ پرداخت برابر نیست» |
| `SUPPLIER_PAYMENT_BEFORE_PURCHASE` | 422 | purchase_kind, purchase_id, purchase_date | «تاریخ پرداخت پیش از تاریخ خرید است» |
| `PURCHASE_NOT_FOUND` | 404 | purchase_kind, purchase_id | «این خرید پیدا نشد» |
| `SUPPLIER_PAYMENT_NOT_FOUND` | 404 | payment_id | «این پرداخت پیدا نشد» |

Reused: `SUPPLIER_NOT_FOUND`, `DATE_IN_FUTURE`, `AMOUNT_TOO_LARGE`. There is no supplier delete in `db/suppliers.py`, so "a supplier with payments cannot be deleted" holds by the FK. A future delete must check it (noted in the docstring).

### API (`npm.cmd run gen:api`)
- `MaterialPurchaseCreate` / `ProductPurchaseCreate` gain `payment: PurchasePaymentIn | None` (`mode` FULL|NONE|PARTIAL, `amount: Money | None`, `method`, `reference`).
- `*PurchaseOut` gains `paid`, `outstanding`, `payment_status`, and the B columns: `status`, `cancel_reason`, `cancelled_at`, `replaces_purchase_id`, `replaced_by_purchase_id`. These are exposed from A because 015 adds them; until B they are always ACTIVE/NULL.
- `*PurchaseDetailOut` adds `payments[]`.
- New router `api/routers/supplier_payments.py`, registered in `api/main.py`:
  - `GET /supplier-payments`
  - `GET /supplier-payments/{id}` (with allocations)
  - `POST /supplier-payments` (201)
  - `PATCH /supplier-payments/{id}`
  - `DELETE /supplier-payments/{id}`
  - `GET /payables`
  - `GET /payables/allocation-preview?supplier_id&amount` (read-only `allocate_oldest_first`)
- `PurchasesSummaryOut` gets 3 new fields.
- `api/schemas/errors.py`: a details model per new code.

### Commits (A)
1. `feat(db): migration 015, supplier payments and purchase status columns`. Includes `db/go_live.py`, the audit-trigger, migration and go-live tests, and `test_migration_015`.
2. `feat(db): supplier_payments module, purchase payment terms, payables reads`. Includes `db/errors.py`, `db/purchases.py` and `tests/test_audit_wiring.py`.
3. `feat(db): purchases summary payments and payables`.
4. `feat(tools): integrity check j, rehearsal purchase invariants`.
5. `feat(api): supplier payments, payables, purchase payment fields; error details`.
6. `docs: accounting rules §21, §9, §18 j`.
7. `feat(frontend): purchase form payment segment, list status and remainder, sheet payments`. Includes `gen:api`.
8. `feat(frontend): settlements tab «بدهی به تأمین‌کنندگان», payment dialog and history`.

### Integrity check j «Supplier payables» (min_schema 15)
- every payment: `amount` = Σ its allocations, and > 0
- every allocation: its purchase exists and is ACTIVE; its supplier matches the payment's supplier (NULL with NULL); payment local day ≥ purchase local day
- every purchase: Σ allocations ≤ `total_paid`
- per supplier: `get_payables()` outstanding = Σ (`total_paid` − `paid`) over its ACTIVE purchases, read through `list_*_purchases`
- the all-time `get_purchases_summary` payment total = Σ `supplier_payments.amount`

### Files (A)
- Backend:
  - `migrations/015_…sql`
  - `db/supplier_payments.py` (new), `db/purchases.py`, `db/reports.py`, `db/errors.py`, `db/go_live.py`
  - `tools/integrity_check/checks.py`, `tools/update_app/invariants.py`
  - `api/schemas/{purchases,supplier_payments,reports,errors}.py`, `api/routers/{purchases,supplier_payments}.py`, `api/main.py`
  - `docs/accounting-rules.md`
- Frontend:
  - `components/purchases/{purchase-form,purchases-page,purchase-sheet,copy,use-purchases-data}.tsx/ts`
  - `components/settlements/{settlements-page,copy}.ts(x)`, plus new `payables-tab.tsx`, `supplier-payment-dialog.tsx` and `supplier-payments-history.tsx`
  - `lib/payables.ts` (+ test), `lib/error-codes.ts`, `lib/api.ts`, `lib/api-types.ts` (generated)

### UI (Persian)
- **Purchase form** (`purchase-form.tsx`):
  - a segment «پرداخت کامل / نسیه / پرداخت بخشی»
  - for partial, «مبلغ پرداخت‌شده» (`MoneyInput`)
  - «روش پرداخت» (نقدی، کارت به کارت، حواله بانکی، چک، سایر) and «شماره پیگیری»
  - the total field is relabelled «مبلغ فاکتور»
- **Purchases list:** a column «وضعیت پرداخت» (tag) and «مانده», plus a filter «وضعیت پرداخت» (`?pay=`).
- **Purchase sheet:** «پرداخت‌ها» (each one's date, amount and method), plus «مانده».
- **Settlements, new tab `?tab=payables` «بدهی به تأمین‌کنندگان»:**
  - one card per supplier: «مانده بدهی», «قدیمی‌ترین خرید پرداخت‌نشده», its open purchases
  - «ثبت پرداخت» opens a dialog: amount → oldest-first split from `/payables/allocation-preview`, editable per purchase, with a live «جمع تقسیم» check
  - «سابقهٔ پرداخت‌ها» below, with edit and delete
  - each card links to `/purchases?supplier=<id>`; that parameter is read at `components/purchases/purchases-page.tsx:55`

### Tests (A)
- **Backend +68 → 2583 passed + 2 skipped:**
  - db module, 30: FULL, NONE and PARTIAL purchases; credit without supplier; explicit and oldest-first allocation; exceeds due and balance; mismatch; supplier mismatch; before purchase; future date; MAX_MONEY on both sides; race (outstanding re-read); edit and re-check; delete cascade and audit; total 0; one `op_id` per purchase plus payment; partner payout and P&L unchanged
  - API: 12
  - integrity j: 7
  - `test_migration_015`: 10. Rebuild keeps rows, ids and `sqlite_sequence`; indexes; triggers equal `audit_trigger_sql`; backfill with no audit rows; total-0 purchase; movement link; cost snapshot (changed, unchanged, product NULL, no audit = NULL); FKs ok.
  - reports: 4
  - rehearsal invariants: 5
- **Existing tests to update:**
  - schema strings in `test_integrity_check.py` and `test_logging.py`
  - `test_error_codes.py` count
  - go-live classification and `CLEAR_ORDER`
  - money_bounds `CASES`
  - `test_audit_wiring.py` module list
  - `test_api_read.py` purchase shapes
  - latest-migration assertions in `test_connection.py`
- **Frontend +6 → 249:** `lib/payables.ts`, covering the allocation sum and remainder checks, status labels and parsing of the `?pay` filter.

### Owner checks by eye (A)
- the purchase form, all three segments, at desktop and 360px
- the purchases list status column and filter
- the purchase sheet's payments
- the payables tab cards, the payment dialog's oldest-first split and an edited split, the history edit and delete
- Toman/Rial switch on all of these

### Risks (A)
- **Rebuilding two tables.** Mitigated by the 014 pattern, the trigger-equality test and a rehearsal row comparison.
- **The snapshot backfill reads audit JSON** (`json_type` tells absent from null). It is tested on crafted logs.
- **A ships B's columns unused.** If B's design changes, a 016 would be needed. That is why B's columns are fixed in this plan.
- **Payment method list:** "card" (کارت به کارت) here is unrelated to sales `payment_methods`. The copy says so.

---

## Amendment: purchase invoices and services (`feat/purchase-lines`, migration 016, approved 2026-10-24)
Built between A and B, from `main` e52fa13. Slice B below is already written for it; this is the summary.
- **Purchase invoices.** One supplier invoice = one `purchase_invoices` row: PUR number, supplier, date, notes, and B's status, cancel reason and moment, and `replaces_invoice_id`. Its lines are the old tables:
  - `material_purchases` and `product_purchases` keep their names and ids, and gain `purchase_invoice_id`
  - each line keeps its item, quantity, line total, unit cost, its PURCHASE movement, its cancel movement and its cost snapshot
- **What moved out of the lines.** Supplier, PUR, date, notes, `status`, `cancel_reason`, `cancelled_at` and `replaces_purchase_id`. 015's line CHECKs on cancel fields therefore became check k rules.
- **Mixing and limits.**
  - one invoice may mix STOCK materials, services and products
  - the same item twice on one invoice is refused (`PURCHASE_DUPLICATE_ITEM`)
  - the invoice total is Σ line totals, computed, never stored
- **Payments are per invoice.** `supplier_payment_allocations.purchase_invoice_id` replaces the two kind columns. paid, outstanding and payment status belong to the invoice.
- **016 on existing data.** Every existing purchase became a one-line invoice with the same PUR, and every allocation points at its row's invoice. No figure changed.
- **Services are purchased.**
  - A service line writes **no** stock movement (`stock_movement_id` NULL forever) and leaves `current_stock` NULL.
  - It sets the service's `unit_cost` to line total ÷ quantity (`blend_unit_cost` with no stock).
  - A service line with total 0 is refused (`SERVICE_PURCHASE_NEEDS_TOTAL`).
  - Its snapshot is `item_cost_before` (0 = not entered) and `item_cost_after`.
- **Routes.** `/purchases/materials|products` are gone; `/purchases` and `/purchases/{id}` are per invoice.
- **Rules section.** Accounting rules §22 is «Purchase invoices», so B's section becomes **§23**.

---

## Slice B: purchase edit / cancel / correct (`feat/purchase-correction`)

### Cost restore: no general replay (recommended alternative)
- **Why not replay.** The movements cannot rebuild the incoming value of past events:
  - a costed ADJUSTMENT stores the blended result, not its supplied cost
  - a made-to-order refund stores the blended result
  - set-cost and go-live change a cost with no movement
  - legacy void returns come back "at the current cost"
- A replay would also need a value source per event kind, and every future cost feature (B2 conversion) would have to stay in sync. One mismatch silently mis-prices stock.
- **The rule instead.** An invoice can be cancelled only while each of its lines is its item's **latest cost event**:
  - **stock material and product lines:**
    - no movement on that item with id > the line's `stock_movement_id` has a positive `quantity_change` (PURCHASE, PRODUCTION_OUTPUT, RETURN, positive ADJUSTMENT or stocktake gain)
    - and the item's `unit_cost` still equals the line's `item_cost_after` (this catches set-cost and any other change without a movement)
  - **service lines** (no movement):
    - no later line of the same service (higher line id) on an ACTIVE invoice
    - and the service's `unit_cost` still equals the line's `item_cost_after`
    - service waste and consumption after the purchase do not block: their prices are frozen on their own rows
- **Then each line's item cost goes back to its `item_cost_before`.** This is exactly what a replay would give:
  - after the purchase only stock went out, and §2 says outgoing stock never changes `unit_cost`
  - so replaying without the purchase ends at the pre-purchase cost
  - no formula is copied and no rounding happens: the stored integer is restored
- **Frozen costs stay untouched.** `unit_cost_at_time` on orders and movements, batch costs and `production_batch_materials` are never written. Sales made between the purchase and the cancel keep the COGS they froze. That is the same principle as §20.
- **When a later cost event exists:** refused with `PURCHASE_COST_CHANGED_SINCE`, listing the later events. The preview names the later purchases, so the owner can cancel them newest first and re-enter them.
- **B2 note (017):** a unit conversion after the purchase must also block. Its `material_unit_changes.last_movement_id` ≥ the purchase movement counts as a later cost event.

### Rules
- **Easy edits** (`update_purchase(invoice_id, **fields)`, on the invoice header, `@audited`, refused on a CANCELLED invoice with `PURCHASE_ALREADY_CANCELLED`). Only these fields:
  - **`supplier_id`:**
    - refused with `PURCHASE_HAS_PAYMENTS` if it has allocations, because they belong to the old supplier
    - NULL while outstanding > 0 → `SUPPLIER_REQUIRED_FOR_CREDIT`
  - **`purchase_date`:**
    - a local day, not in the future (`DATE_IN_FUTURE`)
    - not after the day of an allocated payment (`SUPPLIER_PAYMENT_BEFORE_PURCHASE`)
    - an unchanged local day keeps the stored time; every line's PURCHASE movement `movement_date` follows, in the same op
  - **`notes`.**
  - None of these changes stock, cost, P&L or a distribution, so a closed day does not refuse them.
- **Cancel** (`cancel_purchase(invoice_id, reason, with_payments=False)`, «ابطال خرید»), always the **whole invoice**; there is no single-line cancel:
  - **What it writes:**
    - on the invoice: status CANCELLED, `cancel_reason` (stored form, at most 500 characters), `cancelled_at`
    - per stock material or product line: one movement with reason PURCHASE and quantity −qty, note «ابطال خرید PUR-… — <reason>», saved in the line's `cancel_movement_id`, and stock −qty
    - per service line: no movement (it has no stock)
    - per line: `unit_cost := item_cost_before` (only when it differs)
  - The invoice, its lines, its number and every figure stay.
- **Refusals**, all listed by `plan_cancel_purchase` (`GET …/cancel-preview`), in this order:
  `purchase_id` is the invoice id everywhere below; per-line refusals add `line_index` (0-based, in line id order) and the item.
  1. `PURCHASE_ALREADY_CANCELLED` (purchase_id, cancelled_at, replaced_by_purchase_id)
  2. `PURCHASE_HAS_PAYMENTS` (purchase_id, paid, payment_ids, shared): allocations exist and `with_payments` is false, **or** a payment also pays another invoice (shared = 1). With `with_payments=true`, every payment allocated *only* to this invoice is deleted in the same op (Q2).
  3. `PERIOD_ALREADY_DISTRIBUTED` (reused): the invoice's local day is closed (`refuse_closed_day`), as requested.
  4. `PURCHASE_STOCK_USED` (purchase_id, line_index, item_type, item_id, item_name, current_stock, quantity_bought): stock < qty for a stock or product line, compared as exact decimals.
  5. `STOCKTAKE_AFTER_PURCHASE` (purchase_id, line_index, item_type, item_id, item_name, stocktake_date): the same detection as `order_voids._refuse_stocktake_after`, extracted into a shared read-only helper in `db/stocktake.py` that order_voids also uses. Not for service lines.
  6. `PURCHASE_COST_CHANGED_SINCE` (purchase_id, line_index, item_type, item_id, item_name, later: [{reason, movement_id, date, purchase_id, invoice_number}], cost_changed_without_movement).
  7. `PURCHASE_COST_HISTORY_UNKNOWN` (purchase_id, line_index): a legacy line with no snapshot, or a stock/product line with no movement link.
  - A blank reason → `VOID_REASON_REQUIRED` (reused, field reason).
- **Correct** (`correct_purchase(invoice_id, reason, lines, supplier_id, purchase_date, notes, payment)`, «اصلاح خرید»), ONE op and ONE transaction, always the whole invoice:
  - cancel the invoice, then `record_purchase` with the full new list of lines (any kinds and items), then set the new invoice's `replaces_invoice_id`
  - **allocations of the old invoice move to the new one:** each payment row is unchanged and only the allocation's `purchase_invoice_id` moves
  - moving allocations needs the same supplier: otherwise `PURCHASE_HAS_PAYMENTS`
  - the new total must be ≥ what was paid: otherwise `PURCHASE_CORRECTION_BELOW_PAID` (paid, new_total)
  - `payment` (A's FULL/NONE/PARTIAL) applies only to the unpaid remainder
  - the new day must not be closed
  - any refusal leaves both as they were
  - a replacement can be corrected again; a cancelled purchase cannot
- **Reads:**
  - `list_purchases` (invoices) leaves CANCELLED out unless `include_cancelled=True` (or `status='CANCELLED'`)
  - `get_purchase` gives both links
  - `get_purchases_summary` counts lines of ACTIVE invoices only
  - payables only ever see ACTIVE invoices; a cancelled one has no allocations
  - stock replay: check d1 replays both movements, so they net to 0 and the result is the same as leaving the line out
  - d2 compares Σ PURCHASE movements (+qty and −qty) with Σ `quantity_bought` of the non-service lines of **ACTIVE** invoices
- **Integrity check k «Cancelled and corrected purchases»** (min_schema 16):
  - a CANCELLED invoice has a reason and `cancelled_at`
  - each of its stock and product lines has `cancel_movement_id`, and its two movements net to 0 and point at its item
  - its service lines have neither movement link
  - it has no allocations
  - lines of an ACTIVE invoice have no `cancel_movement_id`
  - `replaces_invoice_id` points at a CANCELLED invoice
  - every line recorded after 016 has `item_cost_after`, and its stock and product lines have `stock_movement_id`
  - the all-time purchases summary = Σ over the lines of ACTIVE invoices
- d2 is changed as above. Check e is unchanged: cancelled lines keep their unit_cost.

### Error codes (B, Persian in `components/purchases/copy.ts`)
| Code | HTTP | Persian |
|---|---|---|
| `PURCHASE_ALREADY_CANCELLED` | 409 | «این خرید قبلاً باطل شده است» |
| `PURCHASE_HAS_PAYMENTS` | 409 | «برای این خرید پرداخت ثبت شده است؛ پرداخت‌هایی که فقط برای همین خرید است همراه آن حذف می‌شود، پرداخت مشترک را اول اصلاح کنید» |
| `PURCHASE_STOCK_USED` | 409 | «بخشی از این خرید مصرف یا فروخته شده؛ موجودی ‹نام› کمتر از مقدار خرید است» |
| `STOCKTAKE_AFTER_PURCHASE` | 409 | «پس از این خرید، ‹نام› در شمارش موجودی شمرده شده است» |
| `PURCHASE_COST_CHANGED_SINCE` | 409 | «پس از این خرید، بهای ‹نام› با رویداد دیگری تغییر کرده؛ اول خریدهای بعدی را باطل کنید» |
| `PURCHASE_COST_HISTORY_UNKNOWN` | 409 | «این خرید پیش از ثبت سابقهٔ بها ثبت شده و باطل‌کردنش ممکن نیست» |
| `PURCHASE_CORRECTION_BELOW_PAID` | 422 | «مبلغ فاکتور جدید از مبلغ پرداخت‌شده کمتر است» |

`PERIOD_ALREADY_DISTRIBUTED` reuses the existing orders copy, worded for purchases.

### API (`npm.cmd run gen:api`)
- `PATCH /purchases/{id}` (`PurchaseUpdate`: supplier_id, purchase_date, notes), per invoice
- `GET /purchases/{id}/cancel-preview` (`PurchaseCancelPreviewOut`: blockers[], and per line: quantity, stock and cost before/after; the payments that would go)
- `POST /purchases/{id}/cancel` (`{reason, with_payments}`) → the invoice
- `POST /purchases/{id}/correct` (201, `PurchaseCreate` body plus `reason`) → the new invoice
- the `GET /purchases` `include_cancelled` query parameter

### Commits (B)
1. `refactor(db): shared stocktake-after helper (order_voids uses it)`.
2. `feat(db): update_purchase (supplier, date, note)`.
3. `feat(db): plan_cancel_purchase, cancel_purchase, correct_purchase; list include_cancelled; summary ACTIVE only`.
4. `feat(tools): integrity d2 ACTIVE invoices, check k`.
5. `feat(api): purchase edit, cancel preview, cancel, correct; error details`.
6. `docs: accounting rules §23, §9, §18 d2/k`.
7. `feat(frontend): purchase sheet edit / ابطال / اصلاح, cancelled tag and toggle, links`. Includes `gen:api` and `lib/purchase-correction.ts` (+ test), mirroring `lib/order-correction.ts`.

### Files (B)
- Backend:
  - `db/purchases.py` and new `db/purchase_cancel.py` (mirrors `order_voids.py`)
  - `db/stocktake.py`, `db/order_voids.py` (helper only), `db/reports.py`, `db/errors.py`
  - `tools/integrity_check/checks.py`
  - `api/schemas/{purchases,errors}.py`, `api/routers/purchases.py`
  - `docs/accounting-rules.md`
- Frontend:
  - `components/purchases/{purchase-sheet,purchases-page,copy,use-purchases-data}`, plus new `purchase-edit-dialog.tsx`, `purchase-cancel-dialog.tsx` and `purchase-correct-dialog.tsx` (the correct dialog reuses the invoice form, prefilled with every line)
  - `lib/purchase-correction.ts`, `lib/error-codes.ts`, `lib/api.ts`

### UI (B)
- **Purchase sheet buttons:** «ویرایش» (supplier, date, note), «ابطال خرید», «اصلاح خرید».
- **Both dialogs show the preview first:**
  - one row per line: «موجودی ‹نام متریال› از X به Y و بهای واحد از A به B برمی‌گردد»; for a service line only «بهای ‹نام خدمت› از A به B برمی‌گردد»
  - the payments that go with it
  - every blocker in Persian, with the later purchases linked
  - a required «دلیل»
- **Deleting payments needs an explicit tick (owner edit E3).** When a cancel would delete payments (`with_payments`), the cancel dialog lists each of them (date, amount, method, reference). The cancel button stays disabled until the checkbox «پرداخت‌های این خرید هم حذف شوند» is ticked; only then is `with_payments=true` sent.
- **Cancelled rows** are hidden by default. A toggle «نمایش خریدهای باطل‌شده» shows them greyed with the tag «باطل‌شده».
- **The sheet** shows «این خرید باطل شده است — دلیل: …», «جایگزین: PUR-…» and, on the new row, «اصلاحِ PUR-…».
- Copy uses «متریال» throughout, never «ماده».

### Tests (B)
- **Backend +52 → about 2635 passed + 2 skipped:**
  - edit, 8: each field, payments block supplier and date, credit needs supplier, cancelled refused, movement date follows
  - cancel, 24:
    - material and product
    - a service line: price restored, no movement; blocked by a later line of the same service
    - a multi-line invoice: all lines reversed in one op; one blocked line refuses the whole invoice
    - cost restored exactly: product NULL, material 0, and an unchanged cost
    - frozen sale COGS untouched after a sale in between
    - each blocker in order: stock used, stocktake loss after, later purchase, later production output, later costed adjustment, set-cost after, legacy no snapshot, closed day
    - `with_payments` single vs shared
    - one `op_id`
  - correct, 11: same and different item; a multi-line invoice corrected with lines added and removed; allocations move; below paid; supplier change with payments; closed new day; chain of corrections; any refusal leaves both
  - integrity d2 and k: 7
  - API: 7
- **Frontend +6 → 255:** the preview text and choosing which blocker to show (`lib/purchase-correction.ts`).

### Owner checks by eye (B)
- edit dialog
- cancel preview: allowed, and each blocker
- correct with a paid purchase
- the cancelled toggle and tags
- links between the old and new purchase, on desktop and 360px

### Risks (B)
- **The latest-cost-event rule can feel strict.** Cancelling an older purchase means cancelling newer ones of the same item first. It is exact, though, and the preview lists them.
- **Allocation move on correction:** the payment rows keep their date, which can now be before the new purchase's day. A correction to a later day than a payment is refused with `SUPPLIER_PAYMENT_BEFORE_PURCHASE`.
- **Negative PURCHASE movements:** any reader that assumes a PURCHASE is positive must be checked. Today only d2 reads them (verified by grep), and no screen lists movement reasons.

---

## Questions (recommended answer first)
1. **B, cost restore:** cancel only while the purchase is the item's latest cost event and restore the stored pre-purchase cost exactly *(recommended)*; or build a full replay engine over every cost event?
2. **B, payments on cancel and correct:** a correction moves the allocations to the new purchase; a plain cancel deletes, after confirmation, the payments allocated only to that purchase, and refuses a shared payment *(recommended)*; or always refuse until the owner deletes the payments by hand?
3. **Closed days:** supplier payments and the supplier/date/note edits are never refused (no P&L effect); cancel and correct are refused on a closed purchase day, as asked *(recommended)*?
4. **Cancelled purchases in the list:** hidden by default with a toggle, like voided orders *(recommended)*; or always shown greyed?
5. **Legacy purchases:** backfill the cost snapshot and movement link from the audit log and notes in 015; a row that cannot be backfilled cannot be cancelled *(recommended)*?
6. **Migration:** one 015 built in slice A, including B's columns, so purchases are rebuilt once *(recommended)*?

## Owner decisions and edits (approved 2026-10-24)
- **Scope now:** slice A only, on `feat/supplier-payables` from `main` c87981f. Slice B is built later, from `main` after A is merged, on `feat/purchase-correction`, from this file alone.
- **Answers:**
  - Q1: the latest-cost-event rule with an exact restore of `item_cost_before`.
  - Q2: a correction moves the allocations. A cancel deletes the payments allocated only to that purchase, after confirmation, and refuses a shared payment.
  - Q3: yes.
  - Q4: hidden by default with a toggle.
  - Q5: yes.
  - Q6: yes, one 015 in slice A, including B's columns.
- **E1:** this file is the first commit of slice A.
- **E2: rehearsal gate.** The owner places a fresh copy of the shop database at `data\restore-test\real\shop.db`.
  - It is used ONLY read-only (`mode=ro&immutable=1`) and through `.\.venv\Scripts\python.exe -m tools.update_app --rehearse data\restore-test\real\shop.db`, which works on its own copy.
  - It is never written, moved or copied elsewhere under `data\`.
  - The last step of a migration slice: if the file is missing or its modified date is before the slice's day, stop and say so. Otherwise run the rehearsal and report the full result, including the purchase invariants and the INFO lines.
- **E3 (slice B):** the cancel dialog lists every payment it would delete and needs the checkbox «پرداخت‌های این خرید هم حذف شوند» (see Slice B, UI).
- **Working rules:**
  - small commits; push the branch; never push to `main`, never merge
  - stop any server before the full pytest run
  - `npm.cmd run lint` last
- **Final report:** commit hashes, exact test counts, migration test results on a fresh database and on a copy of the test database, the rehearsal result, the `data\shop.db` fingerprint at start and end, and what was not checked by eye.

## Owner decisions for the amendment (approved 2026-10-24)
- Option (a): `purchase_invoices` with the old tables as lines, migration 016; B2 → 017.
- One invoice may mix materials, services and products. The same item twice on one invoice is refused (`PURCHASE_DUPLICATE_ITEM`). A service line with total 0 is refused.
- Slice B cancels and corrects per whole invoice only.
- The old `/purchases/materials|products` routes are removed; the db wrappers `record_material_purchase` / `record_product_purchase` stay (one-line invoices).
- The purchases list shows one row per invoice, with an item summary.
- `material_purchases_*` in the summary counts STOCK lines only; services have their own total.

## Slice B build check: deviations (approved 2026-10-25)
Checked against the code at `main` 3dd7c53 (migrations 001–016). **No migration is needed:** every column and CHECK slice B writes exists after 015 and 016, PURCHASE movements may be negative, `products.unit_cost` may go back to NULL. Where these differ from the slice B text above, these win; accounting rules §23 is the result.
- **D1. A cancelled later purchase does not block.** The +qty PURCHASE movement of a line whose invoice is CANCELLED is ignored by the latest-cost-event rule (its cancel movement takes it out again; the cost condition still holds).
- **D2. Exact stock on a cancel:** the new stock is `exact(stock) − exact(qty)` rounded to 1e-9 (the stocktake's `difference`), so equal amounts give exactly 0.
- **D3 (Q1 yes). Supplier edit or correction with payments:** the payments wholly on this invoice follow the new supplier (`supplier_payments.supplier_id`); a payment that also pays another purchase refuses (`PURCHASE_HAS_PAYMENTS`, shared 1).
- **D4 (Q2 yes). Day edit or correction:** the payment made with the purchase (recorded in the purchase's own audit operation, or 015's backfill payment, and still dated with it) moves with the day; any other payment is re-checked (`SUPPLIER_PAYMENT_BEFORE_PURCHASE`).
- **D5. Edit details:** an unknown supplier is `SUPPLIER_NOT_FOUND`; every line's PURCHASE movement follows the day; the same local day keeps the stored moment. A correction that keeps the old invoice's local day keeps its moment too (found in the scratch smoke: the new invoice and the payment made with it had moved to local midnight).
- **D6. Correction order:** inside one transaction: cancel (keeping the allocations), write the new invoice, move the allocations, then the form's payment on the remainder (`purchases._record`'s `corrects` hook). Recording the new invoice first would make its line a later cost event.
- **D7. Reason text** for purchases ("cancel or correct a purchase"), same code `VOID_REASON_REQUIRED`, field reason.
- **D8. Reads:** line reads carry the invoice `status`; `list_purchases(include_cancelled=False)`; the summary and `purchase_invoices_count` count ACTIVE only; the suppliers screen counts ACTIVE only.
- **D9. Check k** (`min_schema` 16): a line recorded with its cost history (its audit INSERT holds an `item_cost_after`) must keep it and, for a stock or product line, its movement link; older lines without one are INFO, never a failure.
- **D10.** The rules are accounting rules **§23** (§22 is «Purchase invoices»); §2, §9, §11, §18 and §21 point to it.
- **Q3 yes:** a voided sale's RETURN after the purchase blocks like any later stock-in; the preview names it. **Q4 yes:** cancelled purchases are hidden by default, toggle «نمایش خریدهای باطل‌شده».

## Verification (each slice)
- `data\shop.db` fingerprint at the start and end.
- `.\.venv\Scripts\python.exe -m pytest -q`, `npm.cmd test`, `npm.cmd run check:money`, `npx tsc --noEmit`, then `npm.cmd run lint` last.
- **A:**
  - `python -m tools.integrity_check --db <scratch copy>` after `init_db` on a scratch copy of the test database (`REBEL_DB` set, non-default port)
  - `--rehearse` on a `data\restore-test\<name>\` copy
  - manual API smoke with the scratch copy only
- **B:** the same on a scratch copy: record → cancel → correct, then integrity, with d2 and k clean.
- Small commits on `feat/supplier-payables` and `feat/purchase-correction`, pushed; never pushed to `main`, never merged.
