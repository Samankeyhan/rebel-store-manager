# Rebel Store Manager

Single-user accounting + inventory app for a music merch shop: products, materials, production, multi-channel orders, payments/settlements, returns, purchases, expenses, partners, Persian invoice PDFs, reports.
Stack: `db/` (Python, SQLite) → `api/` (FastAPI) → `frontend/` (Next.js static export). Multi-user comes later: keep `db/` free of single-process assumptions, but don't add auth speculatively.

More rules load per folder: `db/CLAUDE.md`, `api/CLAUDE.md`, `frontend/CLAUDE.md`. Each `db/` module's docstring says what it does and its rules; read it before changing the module.
`docs/accounting-rules.md` overrides the code. Old tests that contradict it are wrong; update them.

## Workflow
1. Non-trivial change → written plan, then wait for approval.
2. Branch from latest `origin/main`, one feature per branch, name from the prompt.
3. Backend changes only when asked. Backend gaps found during frontend work go in the report, not fixed.
4. Commit and push before finishing.
5. Nothing outside the repo; no browser extensions.

## Final report
It gets pasted into the planning chat, so keep it to short bullets, no prose or recap of the plan:
- Branch, full commit hash, `git status` clean
- Changed: files/areas, one line each
- Verified / not verified (e.g. visual check left to the owner)
- Choices made on open questions
- Backend gaps

## Hard rules
- **Never write to `data/shop.db`** (read-only is fine). API startup runs migrations, so manual runs use a scratch copy via `REBEL_DB`; tests use the temp-DB fixtures in `tests/conftest.py`.
- **Never start uvicorn or the frontend dev server without `REBEL_DB` set to a scratchpad copy of the database.**
- **Money = integer Rial, never float** (since migration 009; it was Toman before). Every formula lives in `db/`; all money rounding is half-even to the Rial. Toman is a display unit only: Rial ÷ 10, at most one decimal digit (shown only when the Rial amount is not a multiple of 10); Toman input takes one decimal. Amounts are integer Rial on the wire and in frontend state; the display currency (Settings → «واحد پول») never reaches the database or the API. The only conversion points are `db/currency.py` (backend, used by the invoice) and `frontend/lib/money.ts` (frontend; `npm run check:money` must pass).
- **Schema changes:** new `migrations/NNN_*.sql` numbered after the highest. Never edit an existing one (hash-checked). Backfills must not touch `updated_at`.
- **Tests:** every `db/` or `pdf/` change has tests; `python -m pytest -v` in `.venv` passes before finishing.
- **Invoice** (`pdf/invoice.py`) shows only what the customer pays: item prices, line discounts, shipping charge, total. Never postage, packaging, fees, unit cost or COGS.
- **Persian terms, everywhere (UI, invoice, copy):** «متریال», never «ماده» or «مواد». Products area: «محصولات و متریال»; tabs «محصولات»، «متریال»، «دسته‌ها».
- **Public repo:** no secrets, no invoice PDFs (`invoices/*.pdf` is gitignored; keep it that way), no real personal data; fictional test data only.
