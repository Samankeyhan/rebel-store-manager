# Rebel Store Manager: project plan (saved from the planning chat)

## Status
Merged to main:
- Backend accounting engine, API (FastAPI) and frontend shell (Next.js static export).
- Payment methods and fees, backend and frontend (steps A and B): migration 008, Jalali helper, fee computed in db/ and frozen on the order, explicit paid_date, channel default method, Settings card for methods, Record Sale picker with fee preview, order detail and list filter, payment-method report reconciled with the P&L.
- Fee cap: migration 010 adds an optional payment_methods.fee_cap on the percentage part of the fee (also in the method drawer and fee text).
- Settlements BACKEND: db/settlements.py, settlement endpoints (pending list with overdue flag, record payouts, history). No settlements screen yet.
- Rial storage: migration 009 stores every money column as integer Rial; Toman is a display unit only (Settings switch, never reaches the API).
- Minimum stock: migration 011 adds an optional materials.min_stock; low-stock badge in the materials list and a dashboard card.
- Per-folder CLAUDE.md files (root, db/, api/, frontend/) and module docstrings; the old CLI (cli/) is removed.
- Label cleanup: the word متریال, never ماده or مواد.

Screens (frontend/app, lib/nav.ts):
- Built: Dashboard (periods today, last 7 days, this month, last month, custom; low-stock materials card), Record Sale, Orders (list and detail, with payment method and settlement state), Products and Materials (tabs محصولات، متریال، دسته‌ها), Production, Purchases, Packaging, Postage, Stock Adjustments, Expenses, Suppliers, Settings (including payment methods and channel default method).
- Stubs (PageStub only): Reports, Partners.
- Missing (no route or nav item): Settlements, Stocktake.

## Next, in this order (branch names in brackets)
Done: A. Payment methods and fees, BACKEND [backend-payment-methods] and B. Payment methods FRONTEND [frontend-payment-methods], both merged (see Status). Owner rules kept for reference: rates and rules are owner-entered data, never seeded; every payment method (card to card included) creates pending items; nothing settles automatically, the owner approves each settlement; DAY_OF_NEXT_MONTH (Digipay) settles whole Jalali months only, after the month has ended; IMMEDIATE and DAYS_AFTER settle any chosen set of pending orders; a deactivated method still lists and settles its pending orders; the invoice never shows fees.

1. Settlements screen [frontend-settlements]: tabs Pending and History, record a settlement (expected vs received, difference shown), plus a dashboard card for money still owed by gateways.
2. Partners [frontend-partners]: owner sets partners and percentages (live total must be 100); for each payout the owner enters the FULL amount, the app splits it across ALL active partners by percentage (rounding exactly as the backend does) and records who received what and the date. Undistributed-profit guard, overlap and over-limit confirmations. Paying only some partners is NOT needed.
3. Reports screens [frontend-reports]: tabs P&L (all 15 keys with explanations), Products, Channels, Shipping (headline uses ESTIMATED figures, actual postage as a reference, amber note for the gap), Payment methods, Waste, Expenses; also show purchases totals from /reports/purchases. Default period: current Jalali month, presets, no previous-period comparison. Must include reconciliation checks against seeded data. PDF and print come after the real-use week.
4. Hardening, then corrections.
   a. Backend hardening [backend-hardening]: audit_log table and helper; structured error details for refusals (machine-readable codes for 409s); PATCH product name and material name and unit; cost-seeding endpoint for products that have stock but no cost; name normalization (Persian and Arabic letters, ZWNJ) through a stored name_key with unique indexes; server-side validation (no future dates, expense amount above zero, postage total above zero and order count at least 1, reject inactive expense category); server-side guard when deactivating a kit that a channel uses as default; orders pagination (limit and offset); review payment-method and settlement validation.
   b. Corrections [backend-corrections]: edit and delete for expenses and postage payments (audit logged); rename, deactivate and reactivate expense categories. Purchases, production batches and stock adjustments are NOT editable; mistakes there are fixed with an opposite entry (usually a stock adjustment). Document the correction recipes.
5. Integrity check [tools-integrity-check]: read-only tool (python -m tools.integrity_check) plus docs/real-use-test.md with daily and weekly routines and a bug log. Include invariants for settlements and fees.
6. Stocktake screen [frontend-stocktake]: enter real opening stock for products and materials (counted quantity per item; how it is recorded is decided in its plan). This answers the go-live question of how to enter real opening stock.
7. Daily use [release-daily-use]: one-click start (start.bat, setup.bat, update.bat, desktop shortcut with the logo icon); one process serving the built frontend and the API (API under /api, bound to 127.0.0.1); daily backup at startup using SQLite's backup API (keep the newest 30, optional second folder, warn but never crash) and a Settings card for backups; rotating log file; decide on scripts/partner_walkthrough.py (import_catalog_v2.py and setup_shipping.py are already gone); docs/RUNNING.md. Reserved ports: on the owner's laptop Windows reserves ports 7966-8065, so the start script must choose a free port outside the reserved ranges (the dev setup uses 8100 with NEXT_PUBLIC_API_URL in frontend/.env.local).
8. Go-live reset [release-go-live-reset] (prompt not written yet): takes a full backup first, reusing the backup mechanism from step 7. Owner answer still needed: clear test data before the real-use week? Recommended: yes; keep catalogue, recipes, kits, categories, suppliers, partners, payment methods and settings; clear orders, purchases, production, adjustments, expenses, postage payments, settlements, distributions, invoice counter. Real opening stock is then entered with the stocktake screen (step 6).
9. One-week real-use test on a single laptop with the bug log, then decide about the later online and multi-user phase.

## Parked decisions
- Minimum-stock levels and low-stock warnings on the dashboard: DONE and merged, migration 011 added an optional materials.min_stock (materials only; products get none). A material is low at stock 0, or at or below its minimum; the dashboard card and the materials list show it.
- Exact odd-Rial storage (store money in Rial, Toman as display): DONE, migration 009 multiplied every money column by 10. Money is stored as integer Rial; Toman is display only (Rial ÷ 10, at most one decimal).
- PDF and print for reports: after the one-week real-use test (step 9).
- Invoice "amount in words": removed from scope.
- Online, multi-user, logins: decide after the real-use week.

## Rules for every task (also in the CLAUDE.md Working agreement)
Plan first and wait for approval; one feature per branch off the latest origin/main; never write to data/shop.db (use a scratchpad copy with REBEL_DB); commit and push and report the full hash; money formulas live in db/ only; money display through formatMoney or the Money component and inputs through MoneyInput; list backend gaps instead of silently fixing them; the report must say what could not be verified (no browser tools means the owner checks the screens).

## Owner routine after each task
Back up (copy data\shop.db data\shop.db.backup), fetch, check out the branch, run pytest and the app, test against real data, merge to main, push, then run git log --oneline -3 to confirm.

## Open items to remember
- Cost check (products with stock but no recorded cost): DONE, run read-only on a copy of the real database on 2026-10-08; none found (13 of 145 products have stock, all with a cost).
- The real database still contains test entries (a test sale, test adjustments, changed packaging stock); the go-live reset (step 8) handles this.
- Known small gaps: no status history for orders, backend error messages are English, kit and expense category renaming not yet possible.
- Record Sale sends transaction_fee null when the fee is automatic, and an integer for a manual override or when there is no payment method.
- On the owner's laptop Windows reserves ports 7966-8065, so the API must run on another port such as 8100 (set NEXT_PUBLIC_API_URL in frontend/.env.local); the one-click start script in step 7 must choose a free port outside the reserved ranges.
- Run "npx next typegen" before "npx tsc --noEmit".
- Backend 409 errors have no machine-readable code; the UI matches English message text (a hardening item for step 4a).
