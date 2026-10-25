# Slice plan: services in purchases, purchase invoices with lines, picker wheel fix (`feat/purchase-lines`)

A fresh session can finish this slice from this file alone. Read it with `docs/plans/2026-10-payables-purchase-correction.md` (slice A done, slice B not built; its "Amendment" section and slice B text are already adjusted to this slice) and `docs/accounting-rules.md`.

## Status (updated 2026-10-25)
- Branch `feat/purchase-lines` from `main` e52fa130d696f3b5c9194d282f1f42f8847672e7. Never push to `main`, never merge.
- **Step-0 baseline on `main`:** pytest 2605 passed + 3 skipped; `npm.cmd test` 249 passed.
- **Test database `data\shop.db` (start and end of the first session):** 643,072 bytes, mtime 2026-10-24T18:37:09.761+03:30, sha256 `137025182862FB56DF7BE4D3AA2AD71A8850EFAF42CC9A80EDBBB5EF81CDD787`. Record it again at the start and end of the final report.
- **Done (pushed):**
  - `d6d0d6e` fix(frontend): item picker `Popover modal`. Checked in the purchase drawer, the supplier payment dialog and the mobile kit editor: wheel, typing, arrows, Esc, click outside. The `modal` fix shipped, not the fallback.
  - `ba4d169` docs(plans): slice B adjusted, B2 → 017, "Amendment" section.
  - `f6920a3` feat(db): migration 016 (`purchase_invoices`, lines, allocations per invoice), go-live, `test_migration_016`, `test_migration_015` pinned to 015, connection/startup/go-live tests.
  - `a19c8c5` feat(db) WIP: `record_purchase`, invoice reads, payments per invoice, d2/f/j, summary, error details (`db/errors.py`, `api/schemas/errors.py`).
- **Remaining, in order:** see "Remaining steps" at the end.

## Context
- The live shop database (separate laptop) is at migration 015, marked live, with real purchases. 015 can no longer be edited: any schema change is a new migration, so this is **016** and B2 (unit conversion) is **017**.
- The owner asked for three changes before slice B (purchase edit/cancel/correct):
  1. **Services in purchases.** A SERVICE material (printing…) can be bought from a supplier and recorded as a purchase: supplier, quantity, total, payment terms, supplier debt.
  2. **Several items in one purchase.** One supplier invoice = one purchase with several lines.
  3. **Mouse wheel in the item dropdown** (the picker list did not scroll inside a drawer).

## Owner answers (approved 2026-10-24)
- Option (a): a `purchase_invoices` header table; the existing per-item rows become its lines. Migration 016.
- Q1: one invoice may mix STOCK materials, services and products.
- Q2: the same item twice on one invoice is refused (`PURCHASE_DUPLICATE_ITEM`).
- Q3: a service line with total 0 is refused (`SERVICE_PURCHASE_NEEDS_TOTAL`).
- Q4: slice B cancels and corrects per whole invoice only.
- Q5: remove the old `/purchases/materials|products` routes; keep the db wrappers `record_material_purchase` / `record_product_purchase` (one-line invoices, return the line id).
- Q6: the purchases list shows one row per invoice with an item summary.
- Q7: `material_purchases_*` in the summary = STOCK lines only, plus a separate service total.
- **E1:** after the ItemPicker change, verify in the scratch smoke test (desktop and a narrow window), inside the purchase drawer, the supplier payment dialog and the mobile kit editor: the search box keeps focus and typing works, arrow keys, Enter and Esc work, the list scrolls with the wheel, clicking outside closes it. If `Popover modal` breaks any, use the fallback (stop wheel/touchmove propagation on the list) and say which shipped. (Done: `modal` shipped.)
- **E2: rehearsal gate.** `data\restore-test\real\shop.db` must exist, be read only with `mode=ro&immutable=1` for this check, have exactly 15 rows in `schema_migrations` (the last being 015), and be dated after the shop's 015 update (the shop update is the `main` commit e52fa13 / 015 release of 2026-10-24 ~18:11 +03:30; the file seen on 2026-10-24 was 16:55, so too old); otherwise stop and say so. Then run `.\.venv\Scripts\python.exe -m tools.update_app --rehearse data\restore-test\real\shop.db` and report the full result, every new invariant and INFO line; stop if it applies anything other than 016.
- Working rules: small commits, push the branch, never push to `main`, never merge. Stop any server you start before the full pytest run. `npm.cmd run lint` last. Safety: never touch `data\backups`, `data\logs`, `data\restore-test\real\` (except the read-only rehearsal), `data\shop-2026-10-13.db`, `data\integrity-2026-10-13.txt`; migrations 001–015 are never edited; run any server only with `REBEL_DB` on a scratch copy and a non-default port.
- Final report: commit hashes, exact test counts with the step-0 baseline, which wheel fix shipped, migration 016 results on a fresh DB and a test-DB copy, the rehearsal result, `data\shop.db` fingerprint start/end, what could not be verified by eye. End with exactly "Waiting for review".

## Services in purchases (rules)
- A service line writes **no stock movement** (`stock_movement_id` NULL forever) and leaves `current_stock` NULL. Check d4 is unchanged ("WASTE is the only movement a SERVICE can have").
- It sets the service's `unit_cost := per_unit_cost(line total, quantity)`, half-even: the same `blend_unit_cost` call with stock NULL. The last purchase sets the price (no averaging, nothing in stock). The line's own `unit_cost` holds the same value (check e unchanged).
- A service line with total 0 is refused (it would set the price to 0 = "not entered").
- Cost snapshot for slice B: `item_cost_before` (0 = not entered) and `item_cost_after`.
- **No double counting.** A purchase is cash and debt (payables) only, not inventory (no stock) and not an expense. A service cost reaches the P&L only through production consumption, made-to-order consumption, kits and `record_service_waste`, each at the price frozen then. The form says: «هزینهٔ خدمت از راه تولید و ضایعات به سود و زیان می‌رسد؛ همین فاکتور را در هزینه‌ها ثبت نکنید». Known gap: bought vs used units of a service are not reconciled (no stock).
- Checks: d2 compares only non-SERVICE lines and requires every SERVICE line to have no movement link; e unchanged; d4 unchanged; j counts service lines in their invoice total.
- Summary: `material_purchases_*` = STOCK lines, new `service_purchases_total` / `_count`, `purchase_invoices_count`.

## Purchase invoices (design, as built in 016)
- `purchase_invoices`: `id`, `invoice_number` (PUR, unique partial index), `supplier_id`, `purchase_date`, `notes`, `status` ACTIVE/CANCELLED, `cancel_reason`, `cancelled_at`, `replaces_invoice_id` (unique partial), same CHECKs as 015's row. Total = Σ line totals, computed (`db/supplier_payments.total_sql`), never stored.
- Lines = `material_purchases` / `product_purchases` (names and ids unchanged): `purchase_invoice_id`, item, `quantity_bought`, `total_paid` (line total), `unit_cost`, `stock_movement_id`, `cancel_movement_id`, `item_cost_before`, `item_cost_after`. Unique `(purchase_invoice_id, item)`.
- `supplier_payment_allocations`: `payment_id`, `purchase_invoice_id`, `amount`, UNIQUE `(payment_id, purchase_invoice_id)`. Payment status, paid and outstanding are per invoice.
- 016 on existing data: every row becomes a one-line invoice with the same PUR, supplier, day, note, status; invoices numbered oldest first (purchase_date, materials before products, line id); every allocation keeps id, payment and amount and points at its row's invoice; AUTOINCREMENT marks kept; no audit rows.
- Go-live: `purchase_invoices` is CLEAR (`CLEAR_ORDER`: allocations, payments, material_purchases, product_purchases, purchase_invoices, stock_movements, …).
- Slice B: see the Amendment and slice B text of `docs/plans/2026-10-payables-purchase-correction.md` (per whole invoice; service-line latest-cost rule; accounting rules §23).

## db API (built)
- `record_purchase(conn, lines, supplier_id, purchase_date, notes, payment) -> invoice id`, `@audited`, one transaction; lines `{kind MATERIAL|PRODUCT, item_id, quantity_bought, total_paid}`; field errors `lines.N.<field>`.
- `record_material_purchase` / `record_product_purchase`: one-line wrappers returning the **line id**.
- Reads: `get_purchase`, `require_purchase`, `list_purchases(supplier_id, start_date, end_date, item_type MATERIAL|SERVICE|PRODUCT, item_id)`, `purchase_lines`; line reads `list_material_purchases` / `list_product_purchases` / `get_*_purchase` stay (with invoice fields).
- `db/supplier_payments.py`: allocations `{purchase_id, amount}` (an invoice id); `total_sql`, `paid_sql`, `item_names`, `not_found`.
- Error codes: `PURCHASE_DUPLICATE_ITEM` (index, item_type, item_id), `SERVICE_PURCHASE_NEEDS_TOTAL` (index, material_id, material_name); `purchase_kind` is gone from every purchase/payment error detail.

## API (to build, then `npm.cmd run gen:api`)
- `POST /purchases` (201, `PurchaseCreate`: `supplier_id`, `purchase_date`, `notes`, `payment`, `lines[]` of `PurchaseLineIn {kind, item_id, quantity_bought: PositiveQuantity, total_paid: Money}`) → `PurchaseDetailOut`.
- `GET /purchases` (`supplier_id`, `start_date`, `end_date`, `item_type`, `item_id`) → `PurchaseOut[]` (invoice fields, `total`, `paid`, `outstanding`, `payment_status`, `lines` summary: `line_count`, `item_names`).
- `GET /purchases/{id}` → header, `lines[]`, `payments[]`.
- Remove `GET/POST /purchases/materials|products[/{id}]`.
- Supplier payments: allocation in/out = `{purchase_id, amount}` plus the invoice's number, date and item names; the allocation preview and payables return invoices (`open_purchases`: `purchase_id`, `invoice_number`, `purchase_date`, `total`, `paid`, `outstanding`, `payment_status`, `item_names`).
- `PurchasesSummaryOut`: `service_purchases_total`, `service_purchases_count`, `purchase_invoices_count`.

## Checks and invariants
- d2, f (PUR from `purchase_invoices` at schema ≥ 16), j (min_schema 16): built.
- **Rehearsal invariants (`tools/update_app/invariants.py`) for 016, to build.** When `purchase_invoices` is new:
  - every 015 purchase row is compared on its full 015 column set through the invoice join (supplier, PUR, day, note, status, cancel columns, `replaces_*` mapped); a missing 015 column is a FAIL, never silently ignored
  - invoices = purchase rows before, each with exactly 1 line
  - every allocation keeps id, payment, amount and its row (allocation → invoice → its one line = the old kind/id)
  - unchanged: payables per supplier, `payables_outstanding`, the all-time purchases summary, the PUR counter, the P&L, every item stock and cost
  - INFO: invoices created; lines without a movement link; lines without a cost snapshot
  - `_payables` and `collect` must read through the new schema when the database is at 016 and through the old tables when it is at 015 (the rehearsal collects from both the before and the after database).

## Remaining steps (commit order)
1. This file (commit "docs(plans): purchase lines slice plan") — done when pushed.
2. `test:` rewrite the tests broken by the db change (`test_supplier_payments`, `test_api_supplier_payments`, `test_api_read`, `test_reports`, `test_audit_wiring`, `test_error_codes` count, money_bounds `CASES`, `test_integrity_check*`, `test_logging` / `test_restore` schema strings) and add: `record_purchase` tests (one and several lines, mixed kinds, duplicate item, service sets price / no movement / stock NULL / total 0 refused, product whole qty, line field paths, Σ above MAX_MONEY, FULL/NONE/PARTIAL on the invoice total, one op_id), payments per invoice, P&L unchanged after a service purchase (consumption and waste use the new price), reports (service total, invoice count), integrity d2/f/j on invoices and services.
3. `feat(tools):` rehearsal invariants for 016 + their tests.
4. `feat(api):` the routes above, schemas, error details, `tests/test_api_*`; then `npm.cmd run gen:api`.
5. `docs:` accounting rules §2 (service price rule), §8 (a service can be purchased), §9 (summary fields), §10 (PUR per invoice), §18 (d2, f, j), §21 (payments per invoice), new §22 «Purchase invoices»; slice B's section becomes §23.
6. `feat(frontend):` invoice form with lines (متریال، خدمت، محصول): lines editor, per-line preview, service help text, payment segment on the invoice total; `lib/purchase-lines.ts` (+ test); `components/purchases/*`.
7. `feat(frontend):` purchases list and sheet per invoice (one row per invoice with an item summary, `?type=service`), payables tab and payment dialog per invoice, reports and dashboard links and the service total; `lib/payables.ts`, `lib/error-codes.ts`, copy.
8. Checks: stop any server; `.\.venv\Scripts\python.exe -m pytest -q`; `npm.cmd test`; `npm.cmd run check:money`; `npx tsc --noEmit`; `npm.cmd run lint` last. Scratch smoke on a copy of `data\shop.db` (`REBEL_DB`, port 8765, web 3000) for the form, list, sheet, payables.
9. Rehearsal gate (E2) and final report; push; "Waiting for review".

## Owner checks by eye
- the wheel scroll in every picker (purchase drawer, supplier payment dialog, mobile kit editor, adjustments, recipes, production run)
- invoice form: add and remove lines, mixed lines, the service line preview, the payment segment on the invoice total, at desktop and 360px
- purchases list per invoice, the type filter including «خدمت», the sheet with lines and payments
- payables cards and the payment dialog split per invoice
- the Toman/Rial switch on all of these

## Risks
- A four-table rebuild on live data: mitigated by the 015 pattern, the 1:1 remap test and the rehearsal invariants.
- `test_migration_015` must build exactly to 015 (done).
- API break for supplier payments (no `purchase_kind`): the frontend is the only client and changes in this branch.
- Service usage vs purchase is not reconciled (no stock); said in the form help and §22.
- `Popover modal` traps focus while open (checked; the fallback was not needed).
