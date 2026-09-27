# Rebel Store Manager — frontend

Next.js (App Router) + Tailwind v4 + shadcn/ui, built as a **static export** (`output: "export"`, `trailingSlash: true`) that FastAPI will serve from `out/`. Persian UI, right-to-left. The backend rules in the root `CLAUDE.md` still apply (money is integer Toman, no business logic outside `db/`).

## Rules

- **RTL: logical properties only.** Use `ms-/me-/ps-/pe-/start-/end-/text-start/text-end/border-s/border-e/rounded-s/rounded-e`, never `ml-/mr-/pl-/pr-/left-/right-/text-left/text-right`. Physical `left`/`right` is only OK as a *screen-edge* choice (e.g. `<Sidebar side="right">`, a tooltip's `side`). Directional icons (chevrons, arrows) need `rtl:rotate-180`. `<html dir="rtl">` handles CSS; `components/providers.tsx` also sets Radix's `DirectionProvider` for keyboard/menu behaviour.
- **Every displayed number goes through `lib/persian-numbers.ts`**: `formatNumber`, `formatMoney` (→ `"۱۸۰٬۰۰۰ تومان"`), `toPersianDigits`. Never render a raw number or call `toLocaleString`. These never throw; a non-integer amount is rounded and `console.warn`ed — fix the source when you see that warning.
- **Money is an integer count of Toman** end to end. Never do money arithmetic in the frontend that the backend should own; display what the API returns.
- **Every displayed date goes through `formatJalali`** (`lib/jalali.ts`), and every date input uses `JalaliDatePicker` / `JalaliDateRangePicker` (`components/jalali-date-picker.tsx`). Values in state and on the wire are Gregorian `"YYYY-MM-DD"` strings; only the display is Jalali. No timezone math in the frontend.
- **Tabular digits are global.** Vazirmatn's Persian digits are proportional by default (۱ = 591, ۳ = 1349 units at 2048 upm); `body` enables the font's `tnum` feature (all digits 1349). Don't reset `font-feature-settings` on an element without re-including `"tnum"`.
- **API access only through `lib/api.ts`** (`apiFetch`, `ApiError`, typed helpers like `getCatalog`). Types come from `lib/api-types.ts`, generated from the backend — **never hand-edit it**; after any `api/schemas` change run `npm run gen:api` (imports `api.main` with the repo `.venv`; no server, no DB).
- **Static export constraints:** no server components that fetch data, no route handlers / API routes, no middleware, no `next/image` optimization, no dynamic routes without `generateStaticParams`. Data fetching happens client-side (`"use client"`), and anything time-dependent (e.g. today's date) must be read on the client, not at build time.
- Navigation lives in `lib/nav.ts` (sidebar, top-bar title and `PageStub` all read it). Add a screen by adding its nav item and `app/<slug>/page.tsx`.
- Colors: use theme tokens (`bg-primary`, `bg-sidebar`, `bg-brand-red`, `text-navy`…) from `app/globals.css`, not raw hex. Brand: logo red `#F03045`, button red `#D21F37`, navy `#26364C`.

## Commands

- Backend: `.venv\Scripts\uvicorn api.main:app --port 8000` (repo root)
- Frontend: `npm run dev` → http://localhost:3000 (API URL via `NEXT_PUBLIC_API_URL`, see `.env.example`)
- `npm run build` (writes `out/`), `npm run lint`, `npm run gen:api`
