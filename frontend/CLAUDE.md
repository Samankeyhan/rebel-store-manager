# frontend/ rules

- Display numbers from the API. Any preview calculation mirrors the backend exactly (like `frontend/lib/costing.ts`) and is labelled as a preview.
- Money is an integer count of Rial end to end: in state, on the wire, in every computation. Toman is a display unit only; the display currency (Settings → «واحد پول») never reaches the API. `frontend/lib/money.ts` is the frontend's only place that converts: Rial = the stored integer, or Toman = Rial ÷ 10 with one decimal digit only when the Rial amount isn't a multiple of 10 (`۱۸۰٬۰۰۰٫۵ تومان` = 1,800,005 Rial).
  - Display every money value with `formatMoney(rial)` or `<Money value={rial} />` (`components/common/money.tsx`), never `formatNumber`, and never rely on a column header for the unit. Operands inside a shown formula use `formatMoneyNumber`; the result carries the unit.
  - Every money input is `MoneyInput` (`components/record-sale/primitives.tsx`): it reports integer Rial, or `null` (reason as `onValue`'s second argument) when the text gives no exact amount: Toman takes at most one decimal, Rial none, no minus sign, nothing beyond 9,007,199,254,740,991 Rial; never rounded. Treat `null` as a blocking error.
  - Unit label via `currencyLabel()`; never hard-code «تومان»/«ریال» (copy objects use getters, e.g. `get unit() { return currencyLabel() }`).
  - Previews (`lib/costing.ts`, record-sale `derive.ts`, postage `figures.ts`) compute in Rial exactly as `db/` does and convert only to display. A preview that multiplies money by a rate must stay exact (BigInt) when the product can pass 9,007,199,254,740,991.
  - Never multiply or divide money by 10 outside `lib/money.ts`. `npm run check:money` must pass.
  - Each page root calls `useCurrency()` (`lib/use-currency.ts`) so a currency switch re-renders the screen without a reload.
- Every displayed non-money number goes through `lib/persian-numbers.ts` (`formatNumber`, `formatQuantity`, `toPersianDigits`); never render a raw number or call `toLocaleString`. If it `console.warn`s about a non-integer, fix the source.
- Every displayed date goes through `formatJalali` (`lib/jalali.ts`); every date input is `JalaliDatePicker` / `JalaliDateRangePicker` (`components/jalali-date-picker.tsx`). State and wire values are Gregorian `"YYYY-MM-DD"`; no timezone math in the frontend.
- Terminology rules are in the root CLAUDE.md.
- Tabular digits are global (`body` enables Vazirmatn's `tnum`); never reset `font-feature-settings` without re-including `"tnum"`.
- RTL: logical properties only (`ms-/me-/ps-/pe-/start-/end-/text-start/text-end/border-s/border-e/rounded-s/rounded-e`), never `ml-/mr-/pl-/pr-/left-/right-/text-left/text-right`; physical sides only for a screen-edge choice (e.g. `<Sidebar side="right">`). Directional icons need `rtl:rotate-180`.
- Works on desktop and mobile; every screen has loading, error and empty states.
- API access only through `lib/api.ts` (`apiFetch`, `ApiError`, typed helpers). Tell API errors apart by `ApiError.code` / `details` (`lib/error-codes.ts`; codes documented on `db/errors.py` `ErrorCode`), or `field`; never by matching `message` text. Persian error text lives in the feature `copy.ts`. Never hand-edit `lib/api-types.ts`; after any `api/schemas` change run `npm run gen:api` (imports `api.main` with the repo `.venv`; no server, no DB).
- Static export (`output: "export"`): no data-fetching server components, route handlers, middleware or `next/image` optimization, no dynamic routes without `generateStaticParams`. Fetch client-side (`"use client"`); read anything time-dependent (e.g. today) on the client, not at build time.
- Navigation lives in `lib/nav.ts` (sidebar, top bar and `PageStub` read it). Add a screen = its nav item + `app/<slug>/page.tsx`.
- Colours: theme tokens from `app/globals.css` (`bg-primary`, `bg-sidebar`, `bg-brand-red`, `text-navy`…), never raw hex. Brand: logo red `#F03045`, button red `#D21F37`, navy `#26364C`.
- Copy lives in `frontend/components/common/copy.ts` plus a `copy.ts` per feature folder (`frontend/components/<feature>/copy.ts`); mark new strings `// NEW`.
- Product/material rows already include `category_name`/`parent_category_name`; don't fetch categories per row.
- Backend gaps go in the report, not fixed here.

## Commands
- Backend (repo root, scratch DB only): `$env:REBEL_DB = "<scratch copy>"; .venv\Scripts\uvicorn api.main:app --port 8000`
- Frontend: `npm run dev` → http://localhost:3000 (API URL via `NEXT_PUBLIC_API_URL`, see `.env.example`); same `REBEL_DB` rule for the API it talks to.
- `npm run build` (writes `out/`), `npm run lint`, `npx tsc --noEmit`, `npm run gen:api`.
- `npm run check:money`: fails on a hard-coded currency unit, `formatNumber` on money, a money `IntInput`, or ×10 / ÷10 / `RIAL_PER_TOMAN` outside `lib/money.ts`. Run it before finishing any screen.
- `npm test`: Node's built-in runner over `lib/**/*.test.mjs`, for dependency-free `lib/` helpers only (no test framework is installed).
