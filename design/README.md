# Rebel Store Manager — design handoff

Everything needed to build the UI in Next.js + Tailwind + shadcn/ui, file by file. No screenshots required: every screen has its layout, verbatim Persian copy, states, validation messages, formulas and sample data in Markdown, and the original artboard source is included for reference.

**Language note:** explanations are in English (for the implementing developer); every string that appears in the product is quoted verbatim in Persian and must be copied exactly, including ZWNJ (نیم‌فاصله) characters, the Persian thousands separator `٬` (U+066C) and the decimal mark `٫` (U+066B).

## Folder map

| Path | What it is |
|---|---|
| `design-system.md` | Tokens (colour light/dark, type, spacing, radius, shadow), component patterns, money/date formatting, RTL conventions. **Read first.** |
| `tokens.css` | The actual stylesheet every artboard uses — all tokens and component classes, ready to port into a Tailwind theme + globals. |
| `logic/formulas.md` | All calculations in one place, with worked numbers. |
| `data/sample-data.md` | The single source of sample data (catalog, materials, kits, orders, postage payments, expenses, P&L) so numbers can be checked across screens, and so it can be used as seed/fixtures. |
| `screens/00-…` … `screens/16-…` | One file per screen: layout, field order, verbatim copy, states, validation, logic, sample data, open questions. |
| `open-questions.md` | Every unresolved decision, gathered in one place. Part A is the list only the owner can answer. |
| `artboards/*.dc.html` | Original artboard source (markup + the JS that computes each screen). Authoritative if a doc and the source ever disagree — see `artboards/README.md`. |
| `assets/` | Logo, both wordmarks, and the Vazirmatn variable font to self-host. |

## The 17 screen files

| File | Screen | Sidebar key |
|---|---|---|
| `00-app-shell.md` | پوسته برنامه — sidebar, top bar, search, user menu, mobile drawer | — |
| `01-dashboard.md` | خانه | `home` |
| `02-record-sale.md` | ثبت فروش | `sale` |
| `03-orders-list.md` | سفارش‌ها | `orders` |
| `04-order-detail.md` | جزئیات سفارش | `orders` |
| `05-products-materials.md` | محصولات و مواد | `products` |
| `06-production.md` | تولید | `production` |
| `07-purchases.md` | خرید | `purchases` |
| `08-packaging.md` | بسته‌بندی | `packaging` |
| `09-postage.md` | هزینه‌های ارسال | `postage` |
| `10-stock-adjustments.md` | تعدیل موجودی | `adjust` |
| `11-expenses.md` | هزینه‌ها | `expenses` |
| `12-reports.md` | گزارش‌ها (5 tabs) | `reports` |
| `13-partners.md` | شرکا و تقسیم سود | `partners` |
| `14-suppliers.md` | تأمین‌کنندگان | `suppliers` |
| `15-settings.md` | تنظیمات | `settings` |
| `16-invoice-print.md` | فاکتور فروش (A4 print) | — |

(The brief said 12 screens; the shell, the order detail, the printed invoice and the split of products/materials make 17 documents.)

## Reading order for the developer

1. `design-system.md` → set up tokens, font, RTL, formatting helpers.
2. `logic/formulas.md` + `data/sample-data.md` → build the domain layer; the sample data doubles as seed/fixtures.
3. `screens/00-app-shell.md` → the layout every route sits in.
4. `screens/02-record-sale.md` → the hardest screen; everything else is simpler than it.
5. The rest of `screens/`, then `open-questions.md` before making any judgement call.

## Status of corrections agreed during design

All six are in the artboards and in these docs; the files in `artboards/` are the same versions the docs describe.

| Correction | Where it lives now |
|---|---|
| One store-wide postage estimate, **total paid ÷ total orders** over the last 3 payments (۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵ = **۱۹۹٬۲۷۳**), not the average of per-payment rates | `logic/formulas.md` §2, `screens/09-postage.md` §5, `screens/02-record-sale.md` §5, `screens/15-settings.md` §5, and the dashboard, reports and order-detail files |
| Channels only switch postage **on/off** (وب‌سایت، اینستاگرام، عمده‌فروشی = on; حضوری، سایر = off); no per-channel postage amount anywhere | `screens/02-record-sale.md` §5, `screens/15-settings.md` §5 |
| The estimate is always shown with the hint «جمع پرداختی ÷ جمع سفارش‌ها» | every screen that displays it — record sale, order detail, postage, settings, reports |
| Out-of-stock products are **selectable**; insufficient stock blocks only در انتظار/پرداخت‌شده/تکمیل‌شده and shows a soft orange warning in پیش‌نویس | `screens/02-record-sale.md` §4 (V2) |
| A product with **no known cost** follows the same pattern: blocking banner + «ثبت بهای تمام‌شده» + «ذخیره به‌عنوان پیش‌نویس» for non-draft, soft warning in draft, profit shown as «نامشخص» | `screens/02-record-sale.md` §4 (V3) |
| Cancelling a paid order: products **and** packaging return to stock, no postage cost is recorded, only the transaction fee becomes a loss | `screens/04-order-detail.md` §5 |
| Recording a refund captures **status + optional reason only** — no editable refund amount; packaging, postage and fee become the order's loss, and the money movement happens outside the app | `screens/04-order-detail.md` §5 |
| Stock **corrections never appear in the P&L**; only ضایعات does, valued at the item's cost **on the day it was recorded** | `screens/10-stock-adjustments.md` §5, `screens/12-reports.md` §5 |
| Tabular (equal-width) Persian digits everywhere, self-hosted Vazirmatn | `design-system.md` § numerals, `tokens.css` |
| The money KPI example on the design-system page reads ۴۲٬۰۴۶٬۰۰۰, matching every other screen | `design-system.md`, `artboards/Main.dc.html` |

## Conventions used in the screen files

- **Layout** is given as boxes and pixel sizes at 1440 (desktop) and 390 (mobile). Use them as ratios, not as a fixed canvas: the desktop layout is fluid between 1024 and 1600. No tablet-specific layout was designed — see `open-questions.md` §B.
- **Copy** blocks are verbatim. Where a string contains a number it is written with the sample value; the number is produced by the formula named next to it.
- **States** lists what was designed. If a state is not listed for a screen, it was not designed — check `open-questions.md` before inventing one.
- **Sample numbers** are artboard literals. Where a literal disagrees with `data/sample-data.md`, the data file wins and the literal should be recomputed; the known disagreements are listed in `open-questions.md` §B.
