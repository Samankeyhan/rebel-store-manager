# Local Changes Report

Generated while preparing uncommitted local work (partner profit distribution + Persian invoice PDFs) for a public repository. No application logic was changed as part of this task — the only changes made here are `.gitignore` and this report.

## 1. File inventory and classification

| Path | Size | Classification | Reason |
|---|---|---|---|
| `cli/main.py` | modified, +295/-3 | **commit** | New CLI menus wiring in partners/distributions and invoice-PDF generation into the existing app. |
| `requirements.txt` | modified, +4 | **commit** | Adds `reportlab`, `arabic-reshaper`, `python-bidi`, `pdfplumber`. |
| `db/partners.py` | 2.8 KB | **commit** | Source: partner CRUD. |
| `db/distributions.py` | 7.9 KB | **commit** | Source: profit distribution logic. |
| `migrations/002_partner_distributions.sql` | 2.2 KB | **commit** | Migration: adds `partners`, `profit_distributions`, `distribution_shares`. |
| `pdf/invoice.py` | 10.5 KB | **commit** | Source: PDF invoice rendering. |
| `config/store_info.py` | 277 B | **commit** | Store display constants (name/address/phone, logo/footer paths). No secrets — see note below. |
| `scripts/partner_walkthrough.py` | 4.7 KB | **commit** | Manual/dev walkthrough script; uses a throwaway temp-file DB, no real data, useful as living documentation. |
| `tests/test_distributions.py` | 9.7 KB | **commit** | Tests. |
| `tests/test_partners.py` | 2.8 KB | **commit** | Tests. |
| `tests/test_invoice_pdf.py` | 4.8 KB | **commit** | Tests. |
| `fonts/Vazirmatn-Regular.ttf` | 123 KB | **commit** | Redistributable open-source font (see licensing note below). |
| `fonts/Vazirmatn-Bold.ttf` | 123 KB | **commit** | Same as above. |
| `assets/Logo.png` | 752 KB | **commit** | Store's own brand logo. No personal data (visually inspected — it's a red/navy circular mark, no people, no address/contact text baked into the image). |
| `assets/footer.png` | 826 KB | **commit** | Store's own wordmark + logo lockup ("ربل شاپ" / RebelShop). Same inspection result as Logo.png. |
| `invoices/invoice_INV-000001.pdf` | 2.1 MB | **do not commit — generated output** | A PDF produced by actually running `generate_invoice_pdf` against order #3 in the local dev DB. Added `invoices/*.pdf` to `.gitignore`. |
| `config/__pycache__/`, `pdf/__pycache__/`, `scripts/__pycache__/*.pyc` | — | **not committed — already ignored** | Covered by the existing `__pycache__/` / `*.pyc` rules in `.gitignore`, so `git status` doesn't even surface them individually. Note: `scripts/__pycache__/walkthrough_adjustments.cpython-313.pyc` and `walkthrough_purchases.cpython-313.pyc` are orphaned bytecode with no matching `.py` source anywhere in the tree (leftover from scripts that were since renamed/removed) — harmless since they're gitignored, but worth a manual `rm -rf` of `__pycache__` folders if you want a clean working tree. |

**Font licensing note:** Vazirmatn is distributed under the SIL Open Font License 1.1, which permits redistribution (including bundling) without payment. No `OFL.txt`/`LICENSE` file was present alongside the `.ttf` files in this working tree, so none was added — flagging this as a finding in §9 rather than adding a file, since the task scope excludes changes beyond `.gitignore` and config examples.

**Config note:** `config/store_info.py` contains `STORE_PHONE = "09390143353"` and the store name in Persian. This is not an API key/password/token, and it's the business's *own* contact info that the app is designed to print on every customer-facing invoice — not a customer's or partner's personal data. I committed it as-is rather than gitignoring it, but flagging it explicitly: publishing your own business phone number in a public git history is effectively permanent (even if later removed, it stays in history) — confirm this is acceptable before pushing.

No API keys, passwords, tokens, bank/card numbers, or SMTP/DB credentials were found anywhere in the tracked diff or the untracked files. No real customer or partner personal data was found in tests, fixtures, or scripts — all test data uses fictional names ("Alice", "Bob", "Carol", "Alex", "Blake", "Casey") and the one real generated invoice (`invoices/invoice_INV-000001.pdf`) has a `NULL` customer name in the source order, so it contains only product/price/store data, no customer identity — and it isn't being committed anyway.

## 2. Business purpose of partners, distributions, and invoice PDFs

**Partners** (`db/partners.py`, `migrations/002_partner_distributions.sql`): models the shop's owners/investors, each with a name and an ownership `current_percentage` (must be `> 0` and `<= 100`), plus optional phone/email/notes. Partners can be deactivated (soft-delete via `is_active`) rather than removed, so historical distribution records still resolve to a name.

**Profit distributions** (`db/distributions.py`): lets the owner periodically pay out real profit to partners according to their ownership percentage. The flow is: pick a period (`period_start`/`period_end`), the system shows `get_profit_and_loss` for that period as a reference figure, the owner decides a `total_amount_distributed` (which can be less than net profit, e.g. to hold back a reserve), and the system splits that amount across all currently-active partners by their current percentage, snapshotting each partner's percentage-at-time and amount into `distribution_shares` so later percentage changes never retroactively alter historical payouts.

**Invoice PDF generation** (`pdf/invoice.py`): renders a right-to-left Persian A4 invoice PDF for a completed order — store header/logo, invoice number, date, channel, line items (with any per-line discount and reason), totals (items subtotal, shipping, postage, transaction fee deduction, final total), and a thank-you footer with store branding. It's a read-only presentation layer over an existing order; it doesn't create or modify any order/financial data.

## 3. Migration 002 schema — full detail

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE partners (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    current_percentage  REAL NOT NULL CHECK (current_percentage > 0 AND current_percentage <= 100),
    phone               TEXT,
    email               TEXT,
    notes               TEXT,
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT
);

CREATE TABLE profit_distributions (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    distribution_date           TEXT NOT NULL DEFAULT (datetime('now')),
    period_start                TEXT NOT NULL,
    period_end                  TEXT NOT NULL,
    total_profit_available      INTEGER NOT NULL,
    total_amount_distributed    INTEGER NOT NULL CHECK (total_amount_distributed >= 0),
    notes                       TEXT
);

CREATE TABLE distribution_shares (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    distribution_id     INTEGER NOT NULL REFERENCES profit_distributions(id) ON DELETE CASCADE,
    partner_id          INTEGER NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
    percentage_at_time  REAL NOT NULL,
    amount              INTEGER NOT NULL CHECK (amount >= 0)
);

CREATE INDEX idx_distribution_shares_distribution_id ON distribution_shares(distribution_id);
CREATE INDEX idx_distribution_shares_partner_id ON distribution_shares(partner_id);
CREATE INDEX idx_profit_distributions_distribution_date ON profit_distributions(distribution_date);
CREATE INDEX idx_profit_distributions_period_start ON profit_distributions(period_start);
CREATE INDEX idx_profit_distributions_period_end ON profit_distributions(period_end);

CREATE TRIGGER trg_partners_updated_at
AFTER UPDATE ON partners
BEGIN
    UPDATE partners SET updated_at = datetime('now') WHERE id = NEW.id;
END;
```

**Relationship to existing schema:** none of the three new tables have a foreign key into `orders`, `products`, `materials`, or `stock_movements` (or `expenses`). The only cross-reference to existing data is *logical*, not a DB constraint: `record_profit_distribution` calls `get_profit_and_loss(conn, period_start, period_end)` (which itself reads `orders`/`order_items` via `get_revenue_summary` and reads `expenses`) purely to compute a reference `total_profit_available` figure that gets stored — read-only, no writes back to orders/expenses. `distribution_shares.partner_id` → `partners.id` is `ON DELETE RESTRICT` (can't delete a partner with recorded shares); `distribution_shares.distribution_id` → `profit_distributions.id` is `ON DELETE CASCADE`.

**Trigger:** `trg_partners_updated_at` stamps `partners.updated_at` on every UPDATE. Note `add_partner` in `db/partners.py` never sets `updated_at` on insert, so it starts `NULL` and only gets a value after the first update (see §9).

## 4. Every money/stock calculation in the new code

All of these are in **`db/distributions.py`** unless noted. None of the new code touches `products.current_stock`, `materials.current_stock`, or writes to `stock_movements` — see §5.

1. **`_validate_non_negative(amount, field_name)`** — guard only, no computation: rejects `amount < 0`.

2. **`_validate_percentage_sum(partners)`** — `total = sum(partner["current_percentage"] for partner in partners)`, then rejects unless `abs(total - 100) <= 0.01` (module constant `PERCENTAGE_SUM_TOLERANCE = 0.01`). Float sum, no rounding applied before the tolerance check. Does not write to the DB — raises `ValueError` before any INSERT if the check fails, inside a `BEGIN`/`rollback` transaction so nothing is written.

3. **`_compute_share_amounts(partners, total_amount_distributed)`** — the core money math:
   - For each partner: `raw_amount = total_amount_distributed * (partner["current_percentage"] / 100)`, then `amount = round(raw_amount)`. `total_amount_distributed` is an `int` (smallest currency unit, e.g. Toman), `current_percentage` is a `float`, so `raw_amount` is a `float`, and Python's built-in `round()` (round-half-to-even / "banker's rounding", not round-half-up) converts it to an `int`.
   - **Rounding reconciliation:** `leftover = total_amount_distributed - sum(rounded amounts)`. If `leftover != 0` (i.e., the per-partner roundings didn't sum exactly back to the total — always possible with 3+ way splits, e.g. 33.33/33.33/33.34%), the *entire* leftover (which can be positive or negative, but in practice ±1 or ±2 units for typical splits) is added to **one single partner**: the one with the highest `current_percentage` (ties broken by lowest `partner_id`), via `min(rounded_amounts, key=lambda share: (-share["percentage_at_time"], share["partner_id"]))`. This guarantees `sum(share amounts) == total_amount_distributed` exactly, at the cost of that one partner's amount not being a perfectly proportional rounding of their percentage.
   - Writes to DB: **yes**, indirectly — `record_profit_distribution` calls this function in-memory, then inserts each result row into `distribution_shares.amount`.
   - Integer vs float: `amount` is always coerced to `int` via `round()` before being stored (column is `INTEGER NOT NULL CHECK (amount >= 0)`); `percentage_at_time` is stored as the raw `float`.

4. **`record_profit_distribution(conn, period_start, period_end, total_amount_distributed, ...)`** (`db/distributions.py`):
   - Fetches `total_profit_available = get_profit_and_loss(conn, period_start, period_end)["net_profit"]` — this is a **read** of existing profit/loss data, not a recalculation, and is stored verbatim into `profit_distributions.total_profit_available`. It is purely informational/historical context alongside the distribution — it is never compared against `total_amount_distributed` (you can distribute more than net profit and the code will not stop you; see §9).
   - Writes: `profit_distributions` row (`total_profit_available`, `total_amount_distributed` as given, both `INTEGER`), then one `distribution_shares` row per active partner from `_compute_share_amounts`. All inside a manual `BEGIN` ... `commit()`/`rollback()` transaction (not using a context manager — see §9).

5. **`get_partner_totals`** (`db/distributions.py`) — pure read: `SUM(distribution_shares.amount)` grouped by partner, via SQL, no Python-side rounding.

6. **`pdf/invoice.py` — `_line_total(item)`**: `item["list_price"] - item["discount_amount"]`. Both are `int` (smallest currency unit) as read from `order_items`. **Display only** — recomputes a value that already exists identically computed elsewhere in the codebase (order detail display in `cli/main.py::_display_order_detail`); does not write to the DB.

7. **`pdf/invoice.py` — `_draw_totals_section`**: `subtotal = sum(_line_total(item) for item in items)` (Python `sum()` over ints, no rounding needed), then conditionally adds `shipping_charge`, `postage_cost`, subtracts `transaction_fee` — all display strings drawn onto the PDF canvas via `to_persian_digits`. `final_total` itself is not recomputed here — it's passed in as `order_data["total"]`, which was already computed by `db/orders.py` (pre-existing code, out of scope for this report) when the order was created. **No DB writes** — `pdf/invoice.py` never calls `conn.execute` for anything other than the read in `get_order`.

8. **`to_persian_digits(number)`**: pure formatting (`f"{number:,}"` then digit substitution to Persian numerals), not a financial calculation, no rounding, no DB interaction.

## 5. Interaction with existing accounting — explicit answers

- **Do distributions change stock?** No. `db/distributions.py` never references `products`, `materials`, or `stock_movements` in any query.
- **Do distributions create orders or stock_movements?** No. No `INSERT INTO orders` / `order_items` / `stock_movements` anywhere in the new code.
- **Do distributions affect revenue, profit, COGS, or expenses?** No, not the underlying figures. `record_profit_distribution` *reads* `get_profit_and_loss` (which itself reads `orders`/`order_items`/`expenses`) to snapshot a reference number, but never writes back to `orders`, `order_items`, or `expenses`. Recording a distribution has zero effect on subsequent `get_revenue_summary`, `get_profit_and_loss`, or any report — running the same P&L query before and after a distribution returns identical numbers.
- **Does invoice PDF generation change stock, orders, revenue, or anything else?** No. `generate_invoice_pdf` only calls `get_order` (a read) and draws to a PDF file on disk. It does not update `orders.invoice_number` or any other column — the invoice number is assigned elsewhere (pre-existing order-creation code), and the PDF filename simply reads whatever `invoice_number` the order already has.
- **Do distributions/invoices appear in any existing report?** No. `db/reports.py` (`get_product_performance`, `get_channel_breakdown`, `get_low_stock_products`, `get_waste_report`, `get_expense_breakdown`, `get_profit_and_loss`) has zero references to `partners`, `profit_distributions`, `distribution_shares`, or invoice PDFs — confirmed by grep. Distribution/payout history is only queryable through the new `db/distributions.py` functions themselves (`list_profit_distributions`, `get_partner_payout_history`, `get_partner_totals`), which are not wired into `manage_reports()` in `cli/main.py` — they're under the separate "Manage Partners & Profit Distribution" menu.
- **Net effect:** profit distribution is purely a downstream bookkeeping record of "we paid out X" layered on top of the existing accounting; it doesn't feed back into it. This means net profit shown by reports is *before* any partner payouts — the system doesn't currently model "profit already distributed" as a liability or deduct it from future P&L (see §9 for the implication).

## 6. `cli/main.py` and `requirements.txt` changes

**`requirements.txt`**: added 4 lines — `reportlab`, `arabic-reshaper`, `python-bidi`, `pdfplumber` (the last is a test-only dependency, used solely by `tests/test_invoice_pdf.py` to extract text back out of generated PDFs for assertions).

**`cli/main.py`** (+295/-3 lines), two independent feature additions bundled in the same file:

- *Invoice PDF* (spans into the existing "View Orders" menu): new imports `from pdf.invoice import generate_invoice_pdf`; new `_handle_generate_invoice_pdf(conn)` handler; `_handle_view_orders` menu gained a new option "3. Generate PDF Invoice" (renumbering the old "3. Back" to "4. Back", and the invalid-option message from "1-3" to "1-4").
- *Partners & distributions* (new top-level feature): new imports from `db.partners` and `db.distributions`; seven new handler functions (`_prompt_percentage`, `_handle_add_partner`, `_handle_update_partner_percentage`, `_handle_deactivate_partner`, `_handle_list_partners`, `_handle_record_profit_distribution`, `_handle_view_distribution_history`, `_handle_view_partner_payout_history`) plus the `manage_partners_and_distributions(conn)` submenu; wired into `main()` as new top-level option "16. Manage Partners & Profit Distribution" (main menu's invalid-option message updated from "1-15" to "1-16").

Both changes are additive and localized — no existing handler's logic was altered, only the "View Orders" submenu's option numbering shifted (3→4 for Back) to make room for the new option.

## 7. Migration state (`data/shop.db`)

`data/shop.db` **exists**, so per instructions `init_db` was **not** run — the database was only opened read-only for inspection.

`schema_migrations` contains exactly one row:

| id | filename | content_hash | applied_at |
|---|---|---|---|
| 1 | `001_initial_schema.sql` | `24dd9a4b3321163871e225f8794e568516c8af4efda50efb6967ba4c64182cf9` | 2026-07-05 09:51:26 |

**`002_partner_distributions.sql` is NOT applied.** There is no row for it in `schema_migrations`, and confirmed independently: `sqlite_master` has no `partners`, `profit_distributions`, or `distribution_shares` tables in the live DB yet.

Current file hash of `migrations/002_partner_distributions.sql` (SHA-256 of its UTF-8 content, computed exactly as `db/connection.py::_hash_migration_content` does): `119391f776c6e58949a6e08ea24dc97001719a93984da61d4ab4b283b3ed19b5`. Since it isn't applied yet, there is nothing to compare this against — the "modified after being applied" guard in `init_db` doesn't apply here. Because it hasn't been applied, the file may still be safely edited if needed; once it is applied (e.g., next time someone chooses "1. Initialize/update database" in the CLI or runs `init_db`), it must never be edited again per the existing guard.

Note: `data/shop.db` currently has 3 pre-existing orders (from manual testing), none with real customer data — order #2 has `customer_name = "CLI Walkthrough"` (clearly test data), the other two have `NULL` customer names.

## 8. Full pytest output

```
============================= test session starts =============================
platform win32 -- Python 3.13.1, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Saman\rebel-store-manager\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Saman\rebel-store-manager
collecting ... collected 152 items

tests/test_adjustments.py::test_waste_decreases_material_stock PASSED    [  0%]
tests/test_adjustments.py::test_waste_decreases_product_stock PASSED     [  1%]
tests/test_adjustments.py::test_adjustment_increases_material_stock PASSED [  1%]
tests/test_adjustments.py::test_zero_quantity_change_raises PASSED       [  2%]
tests/test_adjustments.py::test_invalid_reason_raises PASSED             [  3%]
tests/test_adjustments.py::test_invalid_item_type_raises PASSED          [  3%]
tests/test_adjustments.py::test_service_material_raises_and_rolls_back PASSED [  4%]
tests/test_adjustments.py::test_nonexistent_item_raises PASSED           [  5%]
tests/test_adjustments.py::test_inactive_item_raises PASSED              [  5%]
tests/test_adjustments.py::test_list_stock_adjustments_excludes_other_reasons PASSED [  6%]
tests/test_adjustments.py::test_get_stock_movement_returns_none_for_missing PASSED [  7%]
tests/test_conftest.py::test_test_db_fixture PASSED                      [  7%]
tests/test_connection.py::test_init_db_raises_on_modified_migration_hash PASSED [  8%]
tests/test_distributions.py::test_record_profit_distribution_happy_path PASSED [  9%]
tests/test_distributions.py::test_rounding_reconciliation PASSED         [  9%]
tests/test_distributions.py::test_percentage_sum_not_100_raises_and_rolls_back PASSED [ 10%]
tests/test_distributions.py::test_total_profit_available_from_pnl PASSED [ 11%]
tests/test_distributions.py::test_distribute_less_than_profit_available PASSED [ 11%]
tests/test_distributions.py::test_get_partner_payout_history PASSED      [ 12%]
tests/test_distributions.py::test_get_partner_totals PASSED              [ 13%]
tests/test_distributions.py::test_list_profit_distributions_date_filtering PASSED [ 13%]
tests/test_distributions.py::test_deactivated_partner_excluded_from_later_distribution PASSED [ 14%]
tests/test_expenses.py::test_add_expense_category_happy_path PASSED      [ 15%]
tests/test_expenses.py::test_duplicate_expense_category_raises_value_error PASSED [ 15%]
tests/test_expenses.py::test_deactivate_expense_category PASSED          [ 16%]
tests/test_expenses.py::test_add_expense_happy_path PASSED               [ 17%]
tests/test_expenses.py::test_add_expense_nonexistent_category_raises PASSED [ 17%]
tests/test_expenses.py::test_add_expense_negative_amount_raises PASSED   [ 18%]
tests/test_expenses.py::test_list_expenses_filters PASSED                [ 19%]
tests/test_expenses.py::test_get_total_expenses PASSED                   [ 19%]
tests/test_invoice_pdf.py::test_generate_invoice_pdf_creates_nonempty_file PASSED [ 20%]
tests/test_invoice_pdf.py::test_generate_invoice_pdf_raises_for_missing_order PASSED [ 21%]
tests/test_invoice_pdf.py::test_invoice_number_present_in_pdf_text PASSED [ 21%]
tests/test_invoice_pdf.py::test_filename_uses_invoice_number PASSED      [ 22%]
tests/test_invoice_pdf.py::test_filename_fallback_when_invoice_number_null PASSED [ 23%]
tests/test_invoice_pdf.py::test_missing_logo_does_not_crash PASSED       [ 23%]
tests/test_invoice_pdf.py::test_missing_footer_does_not_crash PASSED     [ 24%]
tests/test_invoice_pdf.py::test_footer_image_does_not_crash PASSED       [ 25%]
tests/test_materials.py::test_add_and_get_stock_material PASSED          [ 25%]
tests/test_materials.py::test_add_stock_material_default_stock PASSED    [ 26%]
tests/test_materials.py::test_add_service_material PASSED                [ 26%]
tests/test_materials.py::test_invalid_type_raises_value_error PASSED     [ 27%]
tests/test_materials.py::test_negative_unit_cost_raises_value_error PASSED [ 28%]
tests/test_materials.py::test_service_with_initial_stock_raises_value_error PASSED [ 28%]
tests/test_materials.py::test_list_materials_ordered_by_name PASSED      [ 29%]
tests/test_materials.py::test_deactivate_material PASSED                 [ 30%]
tests/test_materials.py::test_get_low_stock_materials PASSED             [ 30%]
tests/test_materials.py::test_get_low_stock_excludes_inactive PASSED     [ 31%]
tests/test_orders.py::test_record_order_single_item_happy_path PASSED    [ 32%]
tests/test_orders.py::test_record_order_multiple_items_happy_path PASSED [ 32%]
tests/test_orders.py::test_insufficient_stock_rolls_back_entire_order PASSED [ 33%]
tests/test_orders.py::test_invalid_channel_raises_value_error PASSED     [ 34%]
tests/test_orders.py::test_invalid_status_raises_value_error PASSED      [ 34%]
tests/test_orders.py::test_empty_items_raises_value_error PASSED         [ 35%]
tests/test_orders.py::test_discount_exceeds_line_total_raises_value_error PASSED [ 36%]
tests/test_orders.py::test_nonexistent_product_raises_value_error PASSED [ 36%]
tests/test_orders.py::test_cost_snapshot_frozen_after_product_cost_change PASSED [ 37%]
tests/test_orders.py::test_get_order_computed_total_and_profit PASSED    [ 38%]
tests/test_orders.py::test_list_orders_filters_by_channel_and_status PASSED [ 38%]
tests/test_orders.py::test_update_order_status PASSED                    [ 39%]
tests/test_orders.py::test_record_order_accepts_lifecycle_statuses[DRAFT] PASSED [ 40%]
tests/test_orders.py::test_record_order_accepts_lifecycle_statuses[PENDING] PASSED [ 40%]
tests/test_orders.py::test_record_order_accepts_lifecycle_statuses[PAID] PASSED [ 41%]
tests/test_orders.py::test_record_order_accepts_lifecycle_statuses[COMPLETED] PASSED [ 42%]
tests/test_orders.py::test_record_order_rejects_cancelled_at_creation PASSED [ 42%]
tests/test_orders.py::test_record_order_rejects_refunded_at_creation PASSED [ 43%]
tests/test_orders.py::test_record_order_defaults_to_completed PASSED     [ 44%]
tests/test_orders.py::test_forward_status_transitions_draft_to_completed PASSED [ 44%]
tests/test_orders.py::test_record_order_assigns_invoice_number PASSED    [ 45%]
tests/test_orders.py::test_order_invoice_numbers_increment_sequentially PASSED [ 46%]
tests/test_orders.py::test_null_invoice_orders_do_not_break_numbering PASSED [ 46%]
tests/test_orders.py::test_invoice_number_shared_sequence_across_statuses PASSED [ 47%]
tests/test_partners.py::test_add_partner_happy_path PASSED               [ 48%]
tests/test_partners.py::test_add_partner_percentage_zero_raises PASSED   [ 48%]
tests/test_partners.py::test_add_partner_percentage_over_100_raises PASSED [ 49%]
tests/test_partners.py::test_update_partner_percentage_happy_path PASSED [ 50%]
tests/test_partners.py::test_update_partner_percentage_validation PASSED [ 50%]
tests/test_partners.py::test_update_partner_percentage_inactive_raises PASSED [ 51%]
tests/test_partners.py::test_deactivate_partner_excludes_from_active_list PASSED [ 51%]
tests/test_partners.py::test_get_active_percentage_total PASSED          [ 52%]
tests/test_production.py::test_run_production_batch_happy_path PASSED    [ 53%]
tests/test_production.py::test_insufficient_stock_rolls_back_entire_batch PASSED [ 53%]
tests/test_production.py::test_no_recipe_raises_value_error PASSED       [ 54%]
tests/test_production.py::test_invalid_quantity_raises_value_error PASSED [ 55%]
tests/test_production.py::test_nonexistent_product_raises_value_error PASSED [ 55%]
tests/test_production.py::test_service_materials_no_stock_movements PASSED [ 56%]
tests/test_production.py::test_two_batches_freeze_costs_independently PASSED [ 57%]
tests/test_production.py::test_list_production_batches PASSED            [ 57%]
tests/test_products.py::test_add_and_get_product PASSED                  [ 58%]
tests/test_products.py::test_list_products_ordered_by_name PASSED        [ 59%]
tests/test_products.py::test_invalid_category_raises_value_error PASSED  [ 59%]
tests/test_products.py::test_negative_retail_price_raises_value_error PASSED [ 60%]
tests/test_products.py::test_negative_wholesale_price_raises_value_error PASSED [ 61%]
tests/test_products.py::test_update_product_prices PASSED                [ 61%]
tests/test_products.py::test_update_product_prices_nonexistent_raises PASSED [ 62%]
tests/test_products.py::test_update_product_prices_negative_raises PASSED [ 63%]
tests/test_products.py::test_deactivate_product PASSED                   [ 63%]
tests/test_products.py::test_all_valid_categories PASSED                 [ 64%]
tests/test_purchases.py::test_compute_unit_cost_rounding PASSED          [ 65%]
tests/test_purchases.py::test_record_material_purchase_happy_path PASSED [ 65%]
tests/test_purchases.py::test_record_product_purchase_happy_path PASSED  [ 66%]
tests/test_purchases.py::test_invoice_numbers_shared_across_material_and_product PASSED [ 67%]
tests/test_purchases.py::test_service_material_purchase_raises_and_rolls_back PASSED [ 67%]
tests/test_purchases.py::test_nonexistent_material_raises PASSED         [ 68%]
tests/test_purchases.py::test_nonexistent_product_raises PASSED          [ 69%]
tests/test_purchases.py::test_nonexistent_supplier_raises PASSED         [ 69%]
tests/test_purchases.py::test_invalid_quantity_raises[record_material_purchase-material_id] PASSED [ 70%]
tests/test_purchases.py::test_invalid_quantity_raises[record_product_purchase-product_id] PASSED [ 71%]
tests/test_purchases.py::test_negative_total_paid_raises[record_material_purchase-material_id-1] PASSED [ 71%]
tests/test_purchases.py::test_negative_total_paid_raises[record_product_purchase-product_id-1] PASSED [ 72%]
tests/test_purchases.py::test_material_purchase_without_supplier PASSED  [ 73%]
tests/test_purchases.py::test_list_material_purchases_filters PASSED     [ 73%]
tests/test_purchases.py::test_list_product_purchases_filters PASSED      [ 74%]
tests/test_purchases.py::test_get_purchase_returns_none_for_missing PASSED [ 75%]
tests/test_recipes.py::test_add_and_get_recipe PASSED                    [ 75%]
tests/test_recipes.py::test_calculate_recipe_cost PASSED                 [ 76%]
tests/test_recipes.py::test_calculate_recipe_cost_empty_recipe PASSED    [ 76%]
tests/test_recipes.py::test_calculate_recipe_cost_nonexistent_product PASSED [ 77%]
tests/test_recipes.py::test_duplicate_recipe_item_raises_value_error PASSED [ 78%]
tests/test_recipes.py::test_update_recipe_item PASSED                    [ 78%]
tests/test_recipes.py::test_update_recipe_item_nonexistent_raises PASSED [ 79%]
tests/test_recipes.py::test_remove_recipe_item PASSED                    [ 80%]
tests/test_recipes.py::test_remove_recipe_item_nonexistent_raises PASSED [ 80%]
tests/test_recipes.py::test_add_recipe_item_invalid_quantity PASSED      [ 81%]
tests/test_recipes.py::test_update_recipe_item_invalid_quantity PASSED   [ 82%]
tests/test_recipes.py::test_add_recipe_item_nonexistent_product PASSED   [ 82%]
tests/test_recipes.py::test_add_recipe_item_nonexistent_material PASSED  [ 83%]
tests/test_reports.py::test_get_product_performance PASSED               [ 84%]
tests/test_reports.py::test_get_product_performance_excludes_cancelled_and_date_filter PASSED [ 84%]
tests/test_reports.py::test_get_channel_breakdown PASSED                 [ 85%]
tests/test_reports.py::test_get_channel_breakdown_excludes_cancelled_and_empty_range PASSED [ 86%]
tests/test_reports.py::test_get_low_stock_products PASSED                [ 86%]
tests/test_reports.py::test_get_waste_report PASSED                      [ 87%]
tests/test_reports.py::test_get_waste_report_date_filter_and_empty PASSED [ 88%]
tests/test_reports.py::test_get_expense_breakdown PASSED                 [ 88%]
tests/test_reports.py::test_get_expense_breakdown_date_filter_and_empty PASSED [ 89%]
tests/test_reports.py::test_get_profit_and_loss_hand_calculated PASSED   [ 90%]
tests/test_reports.py::test_get_profit_and_loss_date_filter PASSED       [ 90%]
tests/test_returns.py::test_process_return_restores_stock_and_records_movements PASSED [ 91%]
tests/test_returns.py::test_process_return_cancelled_status PASSED       [ 92%]
tests/test_returns.py::test_process_return_already_refunded_raises PASSED [ 92%]
tests/test_returns.py::test_process_return_already_cancelled_raises PASSED [ 93%]
tests/test_returns.py::test_process_return_invalid_status_raises PASSED  [ 94%]
tests/test_returns.py::test_process_return_nonexistent_order_raises PASSED [ 94%]
tests/test_returns.py::test_process_return_already_returned_leaves_state_unchanged PASSED [ 95%]
tests/test_returns.py::test_update_order_status_rejects_cancelled_and_refunded PASSED [ 96%]
tests/test_returns.py::test_get_revenue_summary_excludes_cancelled_and_refunded PASSED [ 96%]
tests/test_suppliers.py::test_add_and_list_suppliers PASSED              [ 97%]
tests/test_suppliers.py::test_get_supplier_returns_none_for_missing PASSED [ 98%]
tests/test_suppliers.py::test_update_supplier PASSED                     [ 99%]
tests/test_suppliers.py::test_update_nonexistent_supplier_raises PASSED  [100%]

============================ 152 passed in 32.25s =============================
```

(The venv was missing `reportlab`, `arabic-reshaper`, `python-bidi`, and `pdfplumber` before this run; they were installed from `requirements.txt` — `pytest` was already present.)

## 9. Bugs, risks, and inconsistencies found (no fixes applied)

1. **Logo path case mismatch.** `config/store_info.py` sets `LOGO_PATH = "assets/logo.png"` (lowercase `l`), but the actual file on disk is `assets/Logo.png` (capital `L`). This works today only because Windows/NTFS is case-insensitive. Deployed on Linux/macOS or any case-sensitive filesystem, `_draw_store_header` in `pdf/invoice.py` would silently skip the logo (the `logo_path.is_file()` check would return `False` — no crash, but the invoice would render without the logo, since the code treats a missing logo as a soft no-op, not an error). `FOOTER_PATH` matches the actual `footer.png` casing correctly.

2. **Distribution amount is never validated against available profit.** `record_profit_distribution` fetches `total_profit_available` for the period and stores it, but never checks `total_amount_distributed <= total_profit_available`. An owner can distribute more than the period's net profit (or distribute profit from a period with negative net profit) with no warning beyond what the CLI prints before confirming. This may be intentional (e.g., distributing from accumulated reserves across periods isn't modeled at all, so any single-period check would be wrong anyway) — flagging as a design question, not asserting it's a bug.

3. **No tracking of cumulative "already distributed" profit.** Because distributions don't feed back into `get_profit_and_loss` or any other report, there's no way for the system to tell you "of the $X net profit ever earned, $Y has already been paid out, $Z remains." The owner has to manually reconcile `get_partner_totals`/distribution history against P&L reports themselves. `get_partner_totals` exists in `db/distributions.py` but is **not wired into `cli/main.py`** at all (no menu option calls it) — only `list_profit_distributions` and `get_partner_payout_history` are exposed via the CLI.

4. **Non-atomic-looking transaction management.** `record_profit_distribution` manually calls `conn.execute("BEGIN")` / `conn.commit()` / `conn.rollback()` in a try/except, rather than using `with conn:` or a context manager helper. Functionally it works (confirmed by `test_percentage_sum_not_100_raises_and_rolls_back`, which asserts zero rows after a rejected distribution), but it's inconsistent with whatever pattern the rest of the codebase uses elsewhere (not verified in this task's scope) and is easy to get wrong if someone adds an early `return` inside the `try` block in the future without going through `commit()`.

5. **`round()` is banker's rounding, not round-half-up.** `_compute_share_amounts` uses Python's built-in `round()`, which rounds `0.5` to the nearest *even* integer (e.g., `round(2.5) == 2`, `round(3.5) == 4`). For a two-way 50/50 split of an odd total amount, this could occasionally round differently than a naive "round half up" implementation would. The leftover-reconciliation step (§4.3) always makes the final per-partner sum correct regardless, so this only affects *which* partner gets the extra/fewer unit in an edge case, not the total.

6. **`partners.updated_at` starts `NULL` and the trigger only fires on UPDATE.** `add_partner` doesn't set `updated_at` at insert time, and `trg_partners_updated_at` only fires `AFTER UPDATE`, so a partner that's never had its percentage changed will show `updated_at = NULL` forever, while `created_at` is always set. Not a functional bug, just a slightly inconsistent column semantic (`updated_at` means "last updated, or never" rather than "same as created_at until first update").

7. **`invoices/` output directory is not `.gitkeep`'d.** Unlike `data/` (which has a tracked `.gitkeep`), the `invoices/` directory has no placeholder — but `generate_invoice_pdf`'s `_resolve_output_dir` creates it on demand via `mkdir(parents=True, exist_ok=True)`, so this has no functional impact; noting only because `data/` and `invoices/` are inconsistent in this regard.

8. **Business phone number embedded in a public-repo-bound file.** `config/store_info.py` has the real store phone number hardcoded as a Python constant (not an env var or gitignored config file). Once pushed, it's in git history permanently. Flagged for the owner's awareness rather than treated as a "secret" per se — see §1.

9. **Font license file absent.** Vazirmatn (SIL OFL 1.1, redistributable) ships without its license text in this tree. Not a blocker for committing the font files themselves, but best practice for a public repo bundling a third-party font is to include the `OFL.txt`. No file was added, per this task's no-app-changes scope.

## 10. What was not committed, and why

- **`invoices/invoice_INV-000001.pdf`** — generated output from a local test run of `generate_invoice_pdf`, not source. Added `invoices/*.pdf` to `.gitignore` instead.
- **`__pycache__/` directories and `.pyc` files** under `config/`, `pdf/`, `scripts/` — already excluded by the pre-existing `.gitignore` rules (`__pycache__/`, `*.pyc`); nothing needed to change here, they were simply never staged.
- **`data/shop.db`** — pre-existing `.gitignore` rule (`data/*.db`) already excludes it; it was only opened read-only for the migration-state inspection in §7, never modified.
- Nothing else was withheld — no secrets or real personal data were found in anything that *was* committed (see §1 for the full reasoning on `config/store_info.py`, the one file that got the closest scrutiny).

---

*No `OFL.txt`/font-license file, no code changes beyond `.gitignore`, and no example-config file were added, because §1 and §3 (secrets scan) found nothing in `config/store_info.py` that needed to move to a gitignored real/example-file split — it contains no secrets, only business display constants.*
