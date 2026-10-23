# Stage 1 plan: items A–E (read-only investigation)

## Context
- The owner has used the shop laptop for real since 15 Oct. Five items came out of that use:
  - A: a dropdown display bug
  - B: material units
  - C: product cost from recipes
  - D: debts to suppliers
  - E: safe updates
- Every slice must later reach the shop laptop and migrate its real data without damage.
- Baseline:
  - `main` = `origin/main` = `0ea128223bf97b0d85c738bc3908a8319d442b07`, as expected; tree clean.
  - Migrations 001–013.
  - This laptop's `data/shop.db` is a test database: 622,592 bytes, mtime 2026-10-19T19:12:28+03:30, sha256 `7971822301A4635E6322ADD18E581B5464B9CD262ABD8FCD667CC84085486808`.
  - The values at the end of the job are in the reply.

---

## A. Payment-method dropdown loses the name

**Findings**
- **Picker.** `frontend/components/settings/method-picker.tsx:29-78` is a Radix DropdownMenu.
  - Each row is `flex min-w-0 grow justify-between gap-3`: the name is `truncate` (:68) and the fee line is `shrink-0` (:69).
  - The menu is `w-[260px]` on desktop and 200px on mobile (:63).
  - `DropdownMenuRadioItem` reserves `pe-8` on every row for the check mark (`ui/dropdown-menu.tsx:128-157`).
- **Cause.** About 202px is left for name plus fee. The capped fee line "۰٫۵٪ تا سقف ۱۶٬۰۰۰ تومان + ۵۰۰ تومان" is about 200px or more and cannot shrink, so the name truncates to 0px.
  - It has nothing to do with the selection: ZarinPal is the only method with a cap, so it is the only method with a long fee line.
  - On mobile the fee line itself can also be clipped (`overflow-x-hidden`, dropdown-menu.tsx:45).
- **Same bug elsewhere:** the record-sale payment picker, `frontend/components/record-sale/payment-fields.tsx:124-139`. It has the identical row layout, and its menu is as wide as the button.
- **No bug** in pickers that show only the name: the orders filter (`orders/list/orders-list.tsx:395`), settlements history (`settlements/history-tab.tsx:168`), and every other `DropdownMenuRadioItem` (purchases, adjustments, and so on).
- **Fee formatter:** `feeText` (`components/payment-methods/copy.ts:23-31`) and `formatPercent` (`lib/payment-methods.ts:54`).
- **DigiPay `fee_bps`:**
  - On this laptop it is **1300 (13%)**. ZarinPal is 50 bps + 5,000 Rial with **no cap**, and no channel has a default method. So the screenshot comes from the shop laptop.
  - The shop laptop's «۱۳٫۲٪» means `fee_bps` = **1320** there. I will confirm that from the real copy at the first rehearsal. Left unchanged, as the owner asked.

**Design**
- Show each option on two lines: the name (bold, `truncate`) on the first, the fee (`text-xs`) on the second.
- This works at any width.
- It applies to both pickers: `method-picker.tsx` and `payment-fields.tsx`.
- The desktop menu width stays as it is.

**Files:** the two components above. **Migration:** no.

**Tests:** none possible (only `lib/` is unit-testable). Counts stay at backend 2159+1 and frontend 182. The visual check is left to the owner, at desktop width and at 360px.

**Risk:** very low.

---

## B. Units, recipe quantity display, unit conversion

### Findings
1. **Units are free text.**
   - `materials.unit TEXT NOT NULL DEFAULT 'piece'` with no CHECK (`migrations/001:66`); `db/materials.py:123` does not validate it.
   - The only list is in the frontend: `components/products/figures.ts:9`, `UNITS = ["عدد","متر","کیلوگرم","رول","لیتر","نوبت"]`. `"piece"` is shown as «عدد» (:12).
   - This test database also stores «برگ».
   - The unit cannot be edited: `UPDATABLE_FIELDS = ("min_stock",)` (`db/materials.py:27`), and the UI says so (`products/copy.ts:147`).
2. **Why the recipe box can show «۰ لیتر».**
   - The value is stored exactly: `quantity_needed` is REAL, the API allows decimals, and `parseDecimal` (`lib/persian-numbers.ts:98`) is fine.
   - The display is the problem: `formatQuantity` (`lib/persian-numbers.ts:66-80`) rounds to 3 decimals. I checked in node:
     - 0.005 → ۰٫۰۰۵ (correct)
     - 0.0005 → ۰٫۰۰۱
     - 0.0004 → **۰**
   - The recipe box shows `formatQuantity(quantity_needed)` when it is not being edited (`production/recipe-tab.tsx:261`). Any quantity under 0.0005 L therefore reads «۰ لیتر», with the unit suffix at :275.
   - Some inputs reformat the typed value on blur, so the rounding becomes the **saved** value:
     - `purchase-form.tsx:177`
     - `adjustment-form.tsx:332`
     - `material-drawer.tsx:384`
     - The kit editor (`packaging/kit-editor.tsx:124,166`) uses the same display pattern as the recipe box.
   - A related problem: the recipe line cost uses `Math.round` (`recipe-tab.tsx:294`) and `inventoryValue` also uses `Math.round` (`figures.ts:38`). Neither is half-even.
   - This is a bug for any quantity below 0.0005, as the owner says. 0.005 itself should display; if the owner typed something smaller, that is the case shown.
3. **Unit cost and its precision.**
   - `materials.unit_cost` is `INTEGER NOT NULL >= 0`: whole Rial per one unit (`001:68`).
   - Stock is `current_stock REAL`, plus `stock_movements.quantity_change REAL` with `unit_cost_at_time` (only WASTE, ADJUSTMENT and made-to-order RETURN store it).
   - Costs are computed exactly with `Fraction` and rounded once, half-even (`db/costing.py`).
   - **What this means for millilitres:** a per-mL cost is stored to the nearest Rial, so each mL can be off by up to 0.5 Rial. Example: 1,234,567 Rial per L → 1,234.567 per mL → 1,235 stored. On 2 L (2,000 mL) the stock value moves by +866 Rial (about 87 Toman).
     - The owner's ink is 120,000,000 Rial per L = 120,000 Rial per mL, which is exact.
     - The relative error is 0.5 ÷ the per-unit cost. It matters only for very cheap fine units, such as 3 Rial per gram.
   - Recipe consumption itself stays exact: quantity × cost is rounded once.
   - **Recommended rule:**
     - Keep integer Rial per unit. Do not add a precision column.
     - A conversion makes the new cost half-even of old cost ÷ factor. When the old cost divides exactly, the conversion is exact.
     - The confirmation screen shows the stock value before and after and the difference.
     - If the new per-unit cost would be under 1,000 Rial, the screen shows a warning (not a refusal): fine units lose precision.
4. **Integrity and audit facts that affect a conversion.**
   - Check d1 replays `quantity_change` against `current_stock`, and reads a material's opening stock from the audit log's INSERT `after_json.current_stock` (`tools/integrity_check/checks.py:199-259`).
   - Check d2 compares movements with `material_purchases.quantity_bought` and `production_batch_materials.quantity_used`.
   - Check e recomputes `per_unit_cost(total_paid, qty)` for purchases and Σ qty × cost for batches.
   - The audit log is written by triggers and is append-only (`db/audit.py`).

### Design
**B1: display fix and unit list (frontend only)**
- `formatQuantity` shows up to 6 decimals.
- No quantity input reformats on blur unless the reformatted text parses back to exactly the same number.
- Recipe line cost and `inventoryValue` use the exact half-even helpers in `lib/costing.ts`.
- New unit list, stored as Persian text:
  - میلی‌لیتر، لیتر، گرم، کیلوگرم، سانتی‌متر، متر
  - عدد، برگ، رول، بسته
  - نوبت (kept: it is offered today, mainly for services)
  - Existing values are untouched; "piece" is still shown as «عدد».

**B2: safe unit conversion (backend + migration)**
- **Where the units live:** a new `db/units.py` holds the unit list and the compatible pairs:
  - لیتر ↔ میلی‌لیتر ×1000
  - کیلوگرم ↔ گرم ×1000
  - متر ↔ سانتی‌متر ×100
- **Matching:** units are compared by their `names.stored_form`, so the same unit with or without ZWNJ counts as the same.
- **New function** `materials.convert_material_unit(material_id, to_unit, expected_unit, expected_stock)` is `@audited` and runs in one transaction.
  - It is a compare-and-set, like stocktake: a stale unit or stock gives 409.
- **What it changes:**
  - `materials`: `unit`; `current_stock` × f (exact decimal, rounded to 1e-9); `unit_cost` = half-even(cost ÷ f), or cost × f in the other direction; `min_stock` × f.
  - Every `product_recipe.quantity_needed` and every `packaging_kit_items.quantity` that uses this material, × f.
  - One new row in a new table, `material_unit_changes`. Columns:
    - id, material_id
    - from_unit, to_unit, factor (as integer numerator and denominator)
    - last_movement_id (the highest `stock_movements.id` at the moment of conversion)
    - before and after values of stock, cost and min_stock
    - changed_at, note
- **History is NOT rescaled.** Purchases, batches and movements keep the unit they were recorded in. Reasons:
  - Rescaling `unit_cost_at_time` on WASTE movements would change past P&L `waste_cost` through rounding.
  - Rescaling batch lines would break check e.
  - Every Rial figure in the history stays correct as it is (qty × cost in the same old unit).
  - Checks d2 and e therefore stay valid without any change.
- **Check d1 becomes conversion-aware.**
  - When the replay passes a conversion's `last_movement_id`, the running balance is multiplied by the factor, exactly.
  - The audit-log opening is scaled the same way when it comes before the conversion.
  - The existing tolerance stays.
- **Reads that show quantities across a conversion** (the waste report's `total_wasted`, movement lists) use a new helper, `units.movement_unit(conn, material_id, movement_id)`.
  - Their quantities are converted to the current unit for display.
  - Costs are untouched.
- **Audit:** one `op_id` and the operation `convert_material_unit`. The triggers log:
  - the materials UPDATE (unit, stock, cost, min_stock, before and after)
  - every recipe and kit UPDATE
  - the INSERT into `material_unit_changes`
- **Go-live:** `material_unit_changes` is classified CLEAR in `db/go_live.py`.
- **Unit change outside a compatible pair** (relabel only): allowed only when the material has no movements, no purchases, no recipe or kit lines and no stock. Otherwise refused: 409 `MATERIAL_UNIT_IN_USE` (details `material_id`, `recipe_count`, `kit_count`, `movement_count`).
- **New error codes:**
  - `MATERIAL_UNIT_INCOMPATIBLE` (details `from_unit`, `to_unit`)
  - `MATERIAL_UNIT_IN_USE`
  - `MATERIAL_UNIT_STALE` (details `current_unit`, `current_stock`)
- **UI** in the material drawer:
  - A button «تبدیل واحد».
  - A dialog showing stock, cost, min_stock, the number of recipe and kit lines, and the stock value before and after with the difference.
  - Then confirm.
  - Copy: «واحد این متریال از لیتر به میلی‌لیتر تبدیل می‌شود؛ موجودی، بهای واحد، حداقل موجودی و مقدار در همهٔ دستورهای تولید و بسته‌بندی‌ها به همان نسبت تغییر می‌کند. سوابق گذشته با واحد خودشان می‌مانند.»
- **Stocktake drafts:** a draft counted in the old unit is caught by the existing `STOCKTAKE_STALE` check.
- **Slice 6 (rename and unit edit):** merge the *unit* part into B2. Keep the *rename* part (names rules, section 16) as its own small slice.

**Files**
- B1 (frontend): `lib/persian-numbers.ts`, `products/figures.ts`, `production/recipe-tab.tsx`, `packaging/kit-editor.tsx`, `purchases/purchase-form.tsx`, `adjustments/adjustment-form.tsx`, `products/material-drawer.tsx`.
- B2 (backend):
  - `db/units.py`, `db/materials.py`
  - `tools/integrity_check/checks.py` (d1), `db/reports.py` (waste quantity), `db/go_live.py`, `db/errors.py`
  - `api/schemas/errors.py`, `api/schemas/materials.py`, `api/routers/materials.py`
- B2 (frontend): material drawer and dialog; `npm run gen:api`.
- B2 (docs): `docs/accounting-rules.md`, a new section «20. Unit conversion» plus a note in section 18 d1.

**Migration:** B1 no. B2 **yes**: `material_unit_changes` plus its audit triggers. It is 015 if D lands first.

**Tests**
- B1: frontend +6 (formatQuantity at 4–6 decimals, the round-trip guard, half-even line cost) → 188.
- B2: backend about +30:
  - the conversion itself: both directions, recipes and kits, cost rounding, min_stock NULL, SERVICE, stale, incompatible, in use
  - the audit `op_id`
  - d1 across a conversion, including the audit opening
  - the waste report across a conversion
  - `test_migration_015`
  - the error-schema and go-live classification tests
- B2: frontend about +4 (conversion preview helper).
- Existing tests to update: the schema strings in `test_integrity_check.py:145,581` and `test_logging.py:34`, and the code count in `test_error_codes.py:92-97`.

**Risks**
- REAL × 1000 on the stock: handled by computing with exact decimals.
- Any report that sums material quantities across a conversion: only the waste report does today.
- The rehearsal on the real copy must show the ink converted and integrity OK.

---

## C. Product cost from recipes

**Findings**
- `products.unit_cost` is nullable. It is set only by:
  - a product purchase, production or refund (weighted average, `db/costing.py`)
  - a positive adjustment or stocktake gain that comes with a cost
- **Made-to-order sale:** COGS already comes from the recipe at commit (`db/orders.py:298-347`, `recipe_batch_total`). A NULL product cost is fine when the whole line is made.
- **Sale from stock** (`orders.py:348-366`): uses the stored weighted average. NULL is refused with `PRODUCT_NO_UNIT_COST`.
- **Reports** (P&L, product performance, channels) use the frozen `unit_cost_at_time`. That is correct and stays as it is.
- **Stocktake gain:**
  - On a NULL-cost product it requires a cost (`db/stocktake.py:141`).
  - A **material** with cost 0 is not treated as "no cost", so it can take stock at cost 0.
- A recipe estimate already exists: `recipes.calculate_recipe_cost` → `unit_cost_at_qty_1` (`api/routers/recipes.py:18`).
  - The frontend fetches it product by product, only for made-to-order products with stock 0 (`products/products-page.tsx:287-297`, `products/figures.ts:29` `costState`).
- **Bug: record-sale preview.** It uses `toMake × unit_cost_at_qty_1` (`record-sale/derive.ts:197`), but the backend counts PER_BATCH lines once per sale. The preview overstates cost whenever a recipe has PER_BATCH lines.
- **Bug: cost 0 means "unknown" for materials but is blended as a real 0.**
  - Go-live set every STOCK material cost to 0 = unknown (`db/go_live.py:4`).
  - `blend_unit_cost` treats 0 as a real cost (`costing.py:68`). So a purchase into a material that has stock at cost 0 averages with 0 and understates the cost.
  - This test database has «استیکر برندینگ»: 20,000 units at cost 0.
  - A made-to-order sale using such a material also freezes a COGS that is too low.

**Design**
- **Display only. No accounting change.**
  - New `recipes.recipe_costs(conn, product_ids=None)`: one query over recipes and materials, using `recipe_batch_total` for a batch of 1.
  - It returns, per product:
    - `recipe_cost` (int, or NULL)
    - `recipe_cost_status`: NONE (no recipe), INCOMPLETE (any line's material cost is 0), or COMPLETE
    - `recipe_cost_missing` (the ids of materials with cost 0)
  - INCOMPLETE gives `recipe_cost` = NULL. It is never shown as a cheap number.
  - These fields are added to the product rows from `list_products` and `get_product`.
- **Which cost the screens show:**
  - The stored weighted average when it exists, labelled «میانگین موجودی».
  - Otherwise the recipe cost, labelled «برآورد از دستور تولید».
  - A made-to-order product that has stock shows both.
  - INCOMPLETE shows «ناقص: بهای ‹متریال› ثبت نشده».
  - No recipe and no cost shows «نامشخص».
- **Screens:**
  - Product list and drawer: the estimates come from the list endpoint, which removes the N per-product calls.
  - Record-sale form: the preview uses the exact recipe lines, so PER_BATCH is counted once per sale (fixes the bug above). An incomplete recipe shows a warning.
  - Product-performance report: a column «بهای فعلی هر واحد (برآورد)» next to the frozen cost. The frozen COGS figures do not change.
  - Stocktake and adjustment: a gain on a NULL-cost product **prefills** the required unit cost with a COMPLETE recipe cost. It is editable and still has to be confirmed.
- **The recipe cost is never written to `products.unit_cost`.** A stored weighted average is never overwritten.
- **Accounting change, only if the owner approves (Q4):**
  - For materials, cost 0 counts as "no cost" in `blend_unit_cost`, the same as NULL in section 2.
  - So the first real purchase or costed gain sets the cost instead of averaging it with 0.
  - Docs: section 2 edited and section 13 noted.
- Packaging kits are an order cost (`packaging_cost`), not part of the product cost, so they are not included.

**Files**
- Backend: `db/recipes.py`, `db/products.py`, `api/schemas/products.py`, optionally `db/costing.py` and `db/purchases.py`/`adjustments.py`/`stocktake.py` (Q4), `docs/accounting-rules.md`.
- Frontend: `products/figures.ts`, products tab and drawer, `record-sale/derive.ts` and `use-recipes.ts`, `reports/products-tab.tsx`, stocktake and adjustment forms, `npm run gen:api`.

**Migration:** no.

**Tests**
- Backend about +18:
  - each status, PER_BATCH, SERVICE, inactive material
  - `recipe_cost` = `calculate_recipe_cost(…,1)` = the commit `make_cost` for 1
  - API fields
  - with Q4: about +6 for blending at cost 0 (purchase, adjustment, stocktake)
- Frontend about +8: derive PER_BATCH, `costState`, the label choice.

**Risks**
- Q4 changes future costs for cost-0 materials only. Past rows are untouched.
- Rehearsal: list the cost-0 materials in the real copy before and after.

---

## D. Supplier debts (payables)

**Findings**
- `material_purchases` and `product_purchases` are create-only (`db/purchases.py:47,156`).
- `supplier_id` is an optional FK to `suppliers` (no `is_active` column).
- `total_paid` is really the **invoice total**, and it is the value used for the weighted average.
- There is no concept of cash, payable or allocation anywhere.
- Patterns to reuse from settlements (`db/settlements.py`):
  - the race guard (:431)
  - a difference computed on read, never stored
  - correcting only some fields (:539)
  - the pending and history tabs (`components/settlements/`)
- Error codes: `db/errors.py` plus `ERROR_DETAILS` (`api/schemas/errors.py:157`).
- Integrity checks are registered in `checks.py:472`.
- Go-live classification is in `db/go_live.py:24`.
- The audit-wiring module list is at `tests/test_audit_wiring.py:33`.
- There are no purchases in the real database.

**Design (migration 014)**
- **`supplier_payments`** (one payment):
  - id
  - supplier_id (FK; NULL only for a payment on a purchase that has no supplier)
  - payment_date: a UTC moment, like `purchase_date`; the user gives a local day
  - amount INTEGER > 0
  - method TEXT CHECK IN (CASH, CARD, BANK_TRANSFER, CHEQUE, OTHER)
  - reference, note, created_at, updated_at (with an `updated_at` trigger)
- **`supplier_payment_allocations`** (how a payment is split):
  - id
  - payment_id (FK, ON DELETE CASCADE)
  - material_purchase_id and product_purchase_id: both nullable FKs, CHECK exactly one is set
  - amount INTEGER > 0
  - UNIQUE (payment, purchase)
- Both new tables get audit triggers. Go-live classifies them CLEAR, allocations first. Purchase tables do not change.
- **Status is derived, never stored:** `paid = Σ allocations` and `outstanding = total_paid − paid`. The status is:
  - پرداخت‌نشده when nothing is paid
  - پرداخت بخشی when part is paid
  - پرداخت‌شده when fully paid
- **Backfill in 014:**
  - Every existing purchase gets one payment of its full total, dated `purchase_date`, method OTHER, note «پیش از ثبت بدهی‌ها», with an allocation.
  - It is inserted **before** the audit triggers are created, so it writes no audit rows.
  - In the real database this does nothing (no purchases); the rehearsal confirms it.
- **New purchase:**
  - `record_*_purchase` gains `payment` = FULL (the default; today's behaviour), NONE, or PARTIAL with an amount, plus method and reference.
  - Any payment is created in the same transaction and `op_id`.
  - NONE and PARTIAL need a supplier: `SUPPLIER_REQUIRED_FOR_CREDIT`.
- **Payments:**
  - `supplier_payments.record_supplier_payment(supplier_id, payment_date, amount, method, reference, note, allocations[])`
    - The amount must equal Σ allocations exactly. There are no advances.
    - Every purchase must belong to that supplier.
    - Inside the transaction, each allocation must be ≤ outstanding.
  - `update_supplier_payment`: only date, method, reference and note.
  - `delete_supplier_payment`: removes a mistaken payment and its allocations; the audit log keeps them.
  - All three are `@audited`. The new module is added to `tests/test_audit_wiring.py`.
- **Reads:**
  - `list_purchases` gains `paid` and `outstanding`.
  - `get_payables()` gives one row per supplier with purchases_total, paid_total, outstanding and oldest_unpaid_date, plus that supplier's open purchases.
  - `list_supplier_payments(filters)`.
- **Reports:**
  - P&L and stock cost are unchanged; the stock cost stays as it was at purchase time.
  - The purchases summary adds `supplier_payments_total` (by payment_date in range) and `payables_outstanding` (now). These are cash and debt only, never in P&L.
- **Integrity check «i» (min_schema 14):**
  - For each purchase, Σ allocations ≤ `total_paid`.
  - For each payment, amount = Σ its allocations.
  - The supplier on each allocation matches its purchase.
  - Per supplier, `get_payables` outstanding = Σ (total − paid) over its purchases, recomputed through `db/` functions.
- **New error codes:**
  - `SUPPLIER_PAYMENT_EXCEEDS_DUE` (details `purchase_kind`, `purchase_id`, `outstanding`)
  - `SUPPLIER_PAYMENT_SUPPLIER_MISMATCH` (details `purchase_kind`, `purchase_id`, `supplier_id`)
  - `SUPPLIER_PAYMENT_ALLOCATION_MISMATCH` (details `amount`, `allocated`)
  - `SUPPLIER_REQUIRED_FOR_CREDIT` (no details)
  - `PURCHASE_NOT_FOUND` (details `purchase_kind`, `purchase_id`)
  - Reused: `SUPPLIER_NOT_FOUND`, `DATE_IN_FUTURE`.
- **UI:**
  - Purchases screen: a column and filter «وضعیت پرداخت», and the remaining amount «مانده».
  - Purchase form: a segment «پرداخت کامل / نسیه / پرداخت بخشی», with the paid amount, «روش پرداخت» and «شماره پیگیری».
  - Purchase sheet: the list of its payments.
  - Settlements page: a new tab «بدهی به تأمین‌کنندگان» with one card per supplier (outstanding, oldest date, open purchases).
    - «ثبت پرداخت» opens a dialog that pre-allocates oldest first; the allocation can be edited.
    - A payments history list.
  - Method labels: «نقدی»، «کارت به کارت»، «حواله بانکی»، «چک»، «سایر».
  - Error text: «مبلغ پرداخت از ماندهٔ این خرید بیشتر است» and «برای خرید نسیه، تأمین‌کننده را انتخاب کنید».
- **Docs:** a new section «21. Supplier payables», plus section 9 (purchases summary) and section 18 (check i).

**Files**
- Backend:
  - `migrations/014_supplier_payables.sql`, `db/supplier_payments.py` (new), `db/purchases.py`, `db/reports.py`, `db/go_live.py`, `db/errors.py`
  - `api/schemas/` (purchases, supplier payments, errors), `api/routers/supplier_payments.py` (new) and its registration
  - `tools/integrity_check/checks.py`
- Frontend: purchases and settlements components, `lib/payables.ts` (allocation helper), `npm run gen:api`.

**Migration:** yes (014).

**Tests**
- Backend about +55:
  - the db module (about 28): full, none and partial purchase; multi-purchase payment; exceed; mismatch; race; edit; delete; backfill
  - the API (about 12)
  - integrity check i (about 6), `test_migration_014` (about 5), report figures (about 4)
- Existing tests to update: the schema strings, the code count, go-live classification, money_bounds `CASES`, audit wiring.
- Frontend about +8: the `lib/payables.ts` oldest-first allocation and status.

**Risks**
- `total_paid` is still named "paid" in the database. The UI will label it «مبلغ فاکتور».
- Deleting payments: audited, never silent.

---

## E. Safe updates on the shop laptop

**Findings**
- **The procedure today** (`docs/RUNNING.md` §6): stop-rebel → git pull → `start-rebel.cmd --rebuild` → integrity check.
- **Gaps:**
  1. `--rebuild` runs `npm ci` only when `node_modules` is missing (`tools/run_app/frontend.py:52`). New dependencies from a pull are not installed. `requirements.txt` is not reinstalled either.
  2. The pre-migration copy in `init_db` (`db/connection.py:85-99`) is an unverified `shutil.copy2`. It keeps the old file time and is never rotated.
  3. A failed migration only shows "did not start". Nothing guides the owner back.
  4. Nothing rehearses on a copy of the real database.
- **What exists to build on:**
  - `db/backup.make_backup`: SQLite backup API, `integrity_check` verified.
  - stop-rebel calls `POST /api/backups` first.
  - The integrity tool's exit codes: 0 OK, 1 problems, 2 could not run.
  - The go-live tool's pattern: a verified backup into its own subfolder, and refusing while the app runs (`tools/go_live_reset`).

**Design: `update-rebel.cmd` → `python -m tools.update_app`**
- The `.cmd` file stays a single line, so a `git pull` that rewrites it cannot break a running batch file.
- Steps; it aborts at the first failure:
  1. **Preflight.** The repo is on `main` with a clean tree, `.venv` exists, `git fetch` works. Show the incoming commits and the new `migrations/*.sql`. If there is nothing new, say "up to date" and exit 0.
  2. **Integrity check before** (read-only). Exit ≠ 0 → stop: do not update a database that already has problems.
  3. **Stop the app** with `run_app.stop`, which also makes the daily backup. Refuse if the database is still locked.
  4. **Verified backup:** `make_backup` into `data/backups/pre-update/`, so rotation never deletes it. Record the sha256, the old HEAD and the file names in `data/logs/update-<moment>.log`.
  5. **`git pull --ff-only origin main`.**
  6. **Dependencies:** `pip install -r requirements.txt` if it changed, `npm ci` if `package-lock.json` changed, then `npm run build`.
  7. **Migrate** in a **fresh** Python subprocess, so the new code runs `init_db`. Print the migrations applied.
  8. **Integrity check after.** Exit ≠ 0 → roll back automatically.
  9. **Start the app** (`run_app`) and wait for `/api/health`.
- **Automatic rollback** for a failure in steps 5–8, before any new data exists:
  - `git reset --hard <old HEAD>`
  - restore the pre-update backup over `shop.db` and verify its sha256
  - rebuild the screens and start the old version
  - print what failed and the log path
- **Manual rollback** after the app has been used: RUNNING.md gets a new section. Stop, restore `data\backups\pre-update\<file>`, `git reset --hard <old HEAD>` (from the update log), then `start-rebel.cmd --rebuild`.
  - Anything entered since the update is lost; the docs say so in red.
- **`--rehearse PATH`** (for this laptop):
  - Copies the given file (for example `data\restore-test\real\shop.db`) into `data\restore-test\rehearsal-<moment>\shop.db`.
  - Runs integrity before, `init_db`, integrity after.
  - Compares invariant figures before and after: row counts per table, all-time P&L, stock and cost per item, settlement totals. Any difference is a failure.
  - It never touches git, the app or `data\`.
  - Every migration slice is approved only after a clean rehearsal on the real copy.
- `init_db`'s pre-migration copy becomes `make_backup`-verified (into `backups/pre-migration/`). That is a db change and needs tests.
- Exit codes: 0 done, 1 refused or rolled back, 2 could not run.

**Files:** `update-rebel.cmd`, `tools/update_app/` (new), `tools/run_app/frontend.py` (`npm ci` when the lockfile changed), `db/connection.py` (verified backup), `docs/RUNNING.md` §6 rewritten plus a rollback section, `tests/test_running_doc.py`.

**Migration:** no.

**Tests**
- Backend about +25:
  - preflight refusals
  - the step order with git, npm and run_app faked
  - automatic rollback restores the file and the HEAD
  - the rehearsal compares figures and refuses paths inside `data\`
  - `init_db` verified backup
- Everything runs in temp folders.

**Risks**
- Windows file locks while the app runs: we stop it first and test that the database opens exclusively.
- Network: the repo is public HTTPS, so no credentials are needed.
- A first real run will be needed on the shop laptop.

---

## Recommended slice order (one branch each, from `main`)
1. **`fix/method-picker-and-quantities`**: A + B1. Frontend only, no migration, can ship with today's procedure.
2. **`feat/update-rebel`**: E. It must exist before any migration reaches the shop laptop.
3. **`feat/recipe-cost`**: C. No migration; includes Q4 if approved.
4. **`feat/supplier-payables`**: D. Migration 014; rehearsal on the real copy.
5. **`feat/material-unit-conversion`**: B2. Migration 015; rehearsal on the real copy, then the owner converts the ink in the UI.
6. Later: material and product rename (the rest of slice 6).
- After slice 1 the ink recipe in litres displays correctly (0.005 L), so the conversion is not urgent. If the owner wants millilitres first, swap 4 and 5 (the migration numbers swap too).

## Safety and verification for every slice
- `data/shop.db` fingerprint at the start and end of each slice.
- Rehearsals and servers only on `data\restore-test\<name>\` copies, with `REBEL_DB` echoed and the file size checked, on a non-default port.
- `python -m pytest -v` in `.venv`, `npm test`, `npm run check:money`, then `npm run lint` last.
- Small commits, push the branch, never merge.

## Questions for the owner (recommended answer first)
1. **B, cost rounding when converting units:** half-even with the value difference shown, and a warning under 1,000 Rial per unit *(recommended)*; or refuse unless the cost divides exactly?
2. **B, slice 6:** merge only the unit part into B2 and keep rename as its own slice *(recommended)*; or merge rename too?
3. **C, a material cost of 0:** does it always mean "not entered" *(recommended: yes)*? If yes, recipes show «ناقص» and Q4 applies.
4. **C, blending:** treat a material cost of 0 like "no cost" in the weighted average, so the next purchase or costed gain sets it *(recommended: yes)*?
5. **C, made-to-order sale with an incomplete recipe:** warn in the form only *(recommended)*; or refuse in the backend?
6. **D:** no advance or unallocated payments, a fixed method list, and new purchases default to «پرداخت کامل» *(recommended)*?
7. **E:** automatic rollback of code and database when the update fails before the app restarts *(recommended: yes)*?
8. **Order:** payables (D) before unit conversion (B2) *(recommended)*?

---

## Owner decisions and edits (approved)

**Answers:** Q1 yes (half-even, preview, warning under 1,000 Rial per unit). Q2 yes (unit part of slice 6 merged into B2; rename separate). Q3 yes (material cost 0 = "not entered"). Q4 yes (cost 0 treated like no cost when blending). Q5 warn in the form only. Q6 yes. Q7 yes. Q8 order: 1 A+B1, 2 E, 3 C, 4 D, 5 B2, 6 rename.

**E1 (B2):** list every read path that shows a past material quantity or per-unit cost (purchases list and sheet, production batches, movement lists, waste report, material history) and convert or label each across a conversion, with one test each.

**E2 (C):** a stocktake/adjustment gain on a material with cost 0 shows a non-blocking warning; the materials tab shows a count and list of materials with stock > 0 and cost 0 («متریال‌های بدون بها»).

**E3 (D):**
- A payment date may not be before the date of a purchase it pays: `SUPPLIER_PAYMENT_BEFORE_PURCHASE`.
- Payment and allocation amounts are bounded on both sides (`MAX_MONEY`).
- `SUPPLIER_REQUIRED_FOR_CREDIT` gets an explicit empty details model.
- A supplier with payments cannot be deleted.
- Confirm partner payout figures are unaffected.

**E4 (E):**
- The integrity check before an update blocks only on FAIL/ERROR, never on WARN.
- `data\backups\pre-update` keeps the newest 10.
- The `init_db` verified-backup change stays minimal, and the migration aborts if that backup fails.

**Slice 1 (A + B1) scope:** frontend only; two-line options in both pickers; `formatQuantity` up to 6 decimals; no quantity input reformats on blur unless the text parses back to exactly the same number; half-even line cost and `inventoryValue`; new unit list (میلی‌لیتر، لیتر، گرم، کیلوگرم، سانتی‌متر، متر، عدد، برگ، رول، بسته، نوبت).

---

## Renumbering after the sale-correction slice (2026-10-23)
- Migration 014 is now `014_order_void.sql` (voided orders and corrections) and integrity check "i" is "Voided orders and corrections".
- So D (supplier payables) takes migration **015** and its integrity check becomes **"j"**; B2 (unit conversion) moves to **016**.
