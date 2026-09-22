# Rebel Store Manager

## What this is

A single-user accounting and inventory manager for Rebel Store, a music merch shop (vinyl, cassettes, posters, T-shirts, etc.). It tracks products, raw materials, production batches, sales orders (multi-channel: Instagram, website, wholesale, in-person), returns/refunds, purchases, stock adjustments/waste, expenses, suppliers, partner profit distributions, and generates Persian (RTL) invoice PDFs. Reports cover product performance, channel breakdown, low stock, waste, expenses, and profit & loss.

Currently a Python CLI (`cli/main.py`) over SQLite (`data/shop.db`). It is being turned into a **local web app** — FastAPI backend + Next.js static-export frontend — and later into a **multi-user online app**. Design decisions in `db/` should keep that trajectory in mind (e.g. business logic must not assume a single global CLI process), but no multi-user/auth work exists yet — don't add it speculatively.

All money is stored as **INTEGER** in the smallest currency unit (Toman). See Architecture rules below.

## Module map

- `db/connection.py` — opens the SQLite connection and runs migrations (`init_db`); tracks applied migrations in `schema_migrations` with a content hash, refuses to run if an applied migration file was edited.
- `db/errors.py` — exception hierarchy for db/: `AppError` (base, subclasses `ValueError`), `NotFoundError`, `ValidationError` (optional `field`), `InsufficientStockError` (`item_name`/`needed`/`available`), `ConflictError`.
- `db/products.py` — finished-goods CRUD: add/list/get product, update prices, deactivate.
- `db/materials.py` — raw material CRUD (STOCK or SERVICE type), low-stock query, deactivate.
- `db/recipes.py` — product → material BOM (bill of materials): add/update/remove recipe items, compute recipe cost.
- `db/production.py` — runs a production batch: consumes recipe materials (STOCK only), increases product stock, freezes a per-batch unit cost.
- `db/orders.py` — records sales orders and line items, decrements product stock, computes order total/profit, revenue summary; defines valid channels/statuses.
- `db/returns.py` — marks an order CANCELLED/REFUNDED, restores product stock, records RETURN stock movements.
- `db/purchases.py` — records material/product purchases from suppliers, increases stock, computes unit cost, logs PURCHASE stock movements.
- `db/adjustments.py` — manual stock corrections and waste write-offs (WASTE/ADJUSTMENT reasons) for materials or products.
- `db/expenses.py` — expense categories and expense entries (business overhead, not COGS).
- `db/suppliers.py` — supplier CRUD.
- `db/reports.py` — read-only aggregate queries: product performance, channel breakdown, low-stock, waste report, expense breakdown, profit & loss (revenue − COGS/fees − expenses).
- `db/partners.py` — business owners/investors: name, ownership percentage (must sum to ~100% across active partners), soft-deactivate.
- `db/distributions.py` — records profit payouts to partners, split by ownership percentage at time of distribution, snapshotted per share so later percentage changes don't rewrite history.
- `pdf/invoice.py` — renders a Persian RTL A4 invoice PDF for a completed order (customer-facing; see rules below).
- `config/store_info.py` — store display constants (name, address, phone, logo/footer paths) used on invoices.
- `scripts/partner_walkthrough.py` — manual/dev walkthrough exercising the partners + distributions flow end-to-end against a throwaway temp-file DB; not part of the app, not tested by pytest, useful as living documentation of the intended flow.

## Architecture rules (do not break)

- **`db/` owns all business logic and SQL.** No module under `db/` may call `print()` or `input()` — those are interface concerns.
- **Interface layers never write SQL directly.** `cli/main.py` and `pdf/` (and the future API) only call functions exported from `db/`. If a screen/endpoint needs a new query, add a function to the relevant `db/` module — don't inline `conn.execute(...)` outside `db/`.
- **All money is `INTEGER` in the smallest currency unit (Toman).** Never use `float` for money — not for prices, costs, totals, discounts, or distribution amounts. (Quantities of STOCK materials/products *can* be `REAL` where the schema already allows fractional units — that's a separate concern from money.) Python's `round()` is banker's rounding (round-half-to-even); when a formula must round money to an integer, be deliberate about that and reconcile any leftover so totals still sum exactly (see `db/distributions.py::_compute_share_amounts` for the existing pattern).
- **Schema changes go in a new migration file** in `migrations/`, numbered one past the highest existing number (currently `002_partner_distributions.sql`; next would be `003_...`). **Never edit a migration file that already exists in the repo** — `init_db` hashes each applied migration's content and refuses to run if an applied file's hash no longer matches, and the file may already be applied on someone else's `data/shop.db`.
- **Every multi-step write happens inside a transaction that rolls back on failure.** Every write goes through `with transaction(conn):` from db/connection.py. Never call conn.commit(), conn.rollback() or execute('BEGIN') directly. transaction() nests safely: an inner call uses a savepoint, so if it fails only its own work is undone.
- **Partner profit distributions are owner payouts, not business expenses.** They must never reduce revenue, profit, or expenses in any report — `db/reports.py` and `db/distributions.py` must stay decoupled (distributions may *read* `get_profit_and_loss` as a reference figure, but must never write back to `orders`, `order_items`, or `expenses`, and no report function may query `partners`/`profit_distributions`/`distribution_shares`).
- **Customer-facing documents show only what the customer pays.** It shows only what the customer is charged: item prices, per-line discounts, the shipping charge, and the final amount the customer pays (items after discount + shipping charge). It never shows postage paid, packaging cost, transaction or gateway fees, product unit_cost, or COGS — not as costs, not as deductions, not in any form.
- **The repository is public.** Never commit secrets (API keys, credentials, tokens), generated invoice PDFs (`invoices/*.pdf` is gitignored — keep it that way), or real customer/partner personal data (real names paired with phone/email/address, etc.). Use fictional data in tests and scripts, as the existing tests already do.

## Testing rules

- Every change to `db/` or `pdf/` must include or update tests in `tests/`.
- Run the full suite with `python -m pytest -v` inside `.venv` before finishing any task.
- **Never run `init_db` or any write against `data/shop.db`.** Tests use temporary databases only — see `tests/conftest.py`'s `test_db` fixture, which creates a fresh temp-file DB via `init_db(temp_path)` per test and deletes it afterward. Follow that pattern for any new test; don't point a test or script at the real `data/shop.db` path.

## Do not touch `cli/main.py` casually

`cli/main.py` will be **deleted** once the web UI (FastAPI + Next.js) exists — it's a stopgap, not a long-term interface. Do not refactor it, restyle it, or add tests for it. Only change it when a `db/` change breaks it (e.g. a function signature changes), and keep that change minimal.
