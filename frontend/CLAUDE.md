# frontend/ rules

- Display numbers from the API. Any preview calculation mirrors the backend exactly (like `frontend/lib/costing.ts`) and is labelled as a preview.
- Money is an integer count of Rial end to end: in state, on the wire, in every computation. Toman is a display unit only; the display currency (Settings → «واحد پول») never reaches the API. `frontend/lib/money.ts` is the frontend's only place that converts: Rial = the stored integer, or Toman = Rial ÷ 10 with one decimal digit only when the Rial amount isn't a multiple of 10 (`۱۸۰٬۰۰۰٫۵ تومان` = 1,800,005 Rial).
  - Display every money value with `formatMoney(rial)` or `<Money value={rial} />` (`components/common/money.tsx`), never `formatNumber`, and never rely on a column header for the unit. Operands inside a shown formula use `formatMoneyNumber`; the result carries the unit.
  - Every money input is `MoneyInput` (`components/record-sale/primitives.tsx`): it reports integer Rial, or `null` (reason as `onValue`'s second argument) when the text gives no exact amount: Toman takes at most one decimal, Rial none, no minus sign, nothing beyond 9,007,199,254,740,991 Rial; never rounded. Treat `null` as a blocking error.
  - Unit label via `currencyLabel()`; never hard-code «تومان»/«ریال» (copy objects use getters, e.g. `get unit() { return currencyLabel() }`).
  - Previews (`lib/costing.ts`, record-sale `derive.ts`, postage `figures.ts`) compute in Rial exactly as `db/` does and convert only to display. A preview that multiplies money by a rate must stay exact (BigInt) when the product can pass 9,007,199,254,740,991.
  - Never multiply or divide money by 10 outside `lib/money.ts`. `npm run check:money` must pass.
  - Each page root calls `useCurrency()` (`lib/use-currency.ts`) so a currency switch re-renders the screen without a reload.
- Persian digits via `frontend/lib/persian-numbers`, dates via `frontend/lib/jalali`. Terminology rules are in the root CLAUDE.md.
- RTL with logical CSS properties; works on desktop and mobile; every screen has loading, error and empty states.
- Copy lives in `frontend/components/common/copy.ts` plus a `copy.ts` per feature folder (`frontend/components/<feature>/copy.ts`); mark new strings `// NEW`.
- Product/material rows already include `category_name`/`parent_category_name`; don't fetch categories per row.
- Backend gaps go in the report, not fixed here.
