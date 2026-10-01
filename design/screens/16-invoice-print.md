# 16 — فاکتور فروش (Printed invoice, A4)

Not a route and **not a sidebar entry** — it has no `active` key, no top bar, no sidebar and no page chrome of any kind. It is a standalone document, opened from three places:

- `02-record-sale.md` — the success state's button `چاپ فاکتور (PDF)` (mobile: the same label)
- `04-order-detail` — the desktop action button `چاپ فاکتور`; on mobile the same label as an icon button
- `15-settings.md` — the link `پیش‌نمایش فاکتور` in the `فروشگاه و فاکتور` section, which is the only artboard that actually links to `Invoice.dc.html`

A single A4 page at **794 × 1123 px**, which is 210 × 297 mm at 96 dpi. It is the only customer-facing surface in the whole product, and that is the one thing about it that must not be negotiated in implementation:

> **INVARIANT.** The printed invoice must **NEVER** show postage paid, packaging cost, transaction fees, product cost or profit. Everything the app marks `🔒 هزینه داخلی` / «به مشتری نمایش داده نمی‌شود» on the record-sale and order-detail screens is absent here by design, not by omission. §5 lists exactly which fields print; §2 lists exactly which internal fields are deliberately missing, with the values they would have had for the sample order, so a reviewer can confirm none of them leaks.

The document is a plain fixed-size flex column with hardcoded hex colours (no theme tokens), one table, one totals block and a footer pushed down by a `flex-grow: 1` spacer. It contains no JavaScript logic at all: `renderVals()` returns `{}`, every value is literal markup, and `data-theme="light"` is hardcoded on the root.

Artboards:

| file | props | canvas | what it shows |
|---|---|---|---|
| `Invoice.dc.html` | none — `$preview` 794 × 1123, theme hardcoded `light` | 794 × 1123 | the only board: order `INV-000038`, two lines, one of them discounted, status `پرداخت‌شده` |

Source: `src/Invoice.dc.html`. There is **no** dark board, no empty/loading/error board, no mobile board, no multi-page board and no variant for any other order status — this one page is the entire design.

---

## 1. Layout

### The A4 page, top to bottom

```
+================================ 794 px wide =================================+
|                                                                              |
|  page padding: 56 top · 56 inline · 48 bottom                                |
|  root: .rs data-theme="light" · background #ffffff · color #171A21           |
|  display flex · flex-direction column · gap 28                               |
|                                                                              |
|  +------------------------ content box 682 x 1019 -----------------------+   |
|  |                                                                       |   |
|  | [A] HEADER                                            h ~= 90         |   |
|  |     flex · space-between · align-items flex-start                     |   |
|  |     padding-bottom 20 · border-bottom 2px #26364C                     |   |
|  |   inline-start: [logo 64x64 circle] [ربل شاپ 22/800 #26364C]          |   |
|  |                                     [tagline 12 #454C59]              |   |
|  |                                     [website placeholder 12 #454C59]  |   |
|  |   inline-end:   [فاکتور فروش 24/800 #26364C]                          |   |
|  |                 [شماره: + .inv INV-000038 (LTR, mono 14)]             |   |
|  |                 [تاریخ: + ۱۴۰۵/۰۶/۳۰ (.num, bold)]                     |   |
|  |                                                                       |   |
|  | ---- gap 28 ----                                                      |   |
|  |                                                                       |   |
|  | [B] PARTY BOXES                                       h ~= 66         |   |
|  |     grid repeat(2, minmax(0,1fr)) · gap 16 · font 13.5               |   |
|  |   +--- خریدار -----------------+ +--- وضعیت پرداخت --------------+     |   |
|  |   | label 12/700 #454C59       | | label 12/700 #454C59         |     |   |
|  |   | value 15/700               | | value 15/700                 |     |   |
|  |   | 1px #C6C6BE · radius 8     | | 1px #C6C6BE · radius 8       |     |   |
|  |   | padding 12 14 · gap 4      | | padding 12 14 · gap 4        |     |   |
|  |   +----------------------------+ +------------------------------+     |   |
|  |                                                                       |   |
|  | ---- gap 28 ----                                                      |   |
|  |                                                                       |   |
|  | [C] LINE-ITEM TABLE                                   h ~= 139        |   |
|  |     width 100% · border-collapse collapse · font 13.5                |   |
|  |     every cell: 1px #C6C6BE · padding 10                             |   |
|  |     thead: background #ECEFF5 · color #26364C                        |   |
|  |   | ردیف 44 | شرح کالا (grow) | تعداد 64 | واحد 118 | تخفیف 104 |      |   |
|  |   | مبلغ 122 |                                                        |   |
|  |     2 body rows; row 2 carries a 11.5px #454C59 sub-line              |   |
|  |     "مبلغ" cell is font-weight 700                                    |   |
|  |     NO tfoot - the totals are a separate block                        |   |
|  |                                                                       |   |
|  | ---- gap 28 ----                                                      |   |
|  |                                                                       |   |
|  | [D] TOTALS BLOCK                                      h ~= 190        |   |
|  |     section flex · justify-content flex-end (= LEFT edge in RTL)      |   |
|  |     inner width 320 · flex column · font 14                          |   |
|  |   +--------------------------------------------+ 320 wide            |   |
|  |   | جمع اقلام ................ amount          | pad 8 12, 1px #E1E1DA|   |
|  |   | تخفیف .................... −amount         | pad 8 12, 1px #E1E1DA|   |
|  |   | هزینه ارسال .............. amount          | pad 8 12, 1px #E1E1DA|   |
|  |   |############################################| navy #26364C, white  |   |
|  |   | مبلغ قابل پرداخت ......... amount 20/800   | pad 12, radius 0 0 8 8|  |
|  |   | به حروف: ... (12 #454C59)                  | pad 8 12             |   |
|  |   +--------------------------------------------+                      |   |
|  |                                                                       |   |
|  | ---- gap 28 ----                                                      |   |
|  |                                                                       |   |
|  | [E] SPACER  <div style="flex-grow: 1">           h ~= 318 (remainder) |   |
|  |     the only thing pinning the footer to the bottom of the page       |   |
|  |                                                                       |   |
|  | ---- gap 28 ----                                                      |   |
|  |                                                                       |   |
|  | [F] FOOTER                                            h ~= 76         |   |
|  |     flex · space-between · align-items flex-end                       |   |
|  |     padding-top 18 · border-top 1px #C6C6BE                           |   |
|  |   inline-start: thank-you line + website placeholder                  |   |
|  |                 12.5px #454C59 · max-width 420 · gap 4                |   |
|  |   inline-end:   wordmark image, height 56, width auto                 |   |
|  +-----------------------------------------------------------------------+   |
|                                                                              |
+================================ 1123 px tall ================================+
```

**Which numbers are authoritative.** Every padding, border, width, font size and gap above is a literal value in the source and must be implemented as given. The per-region heights marked `~=` are **content-driven, not declared**: the source sets no height on any region. They are derived as `1123 − 56 − 48 = 1019` px of content box, minus `5 × 28 = 140` px of gaps, leaving 879 px for the six children; regions A–D and F measure ≈561 px at the given type sizes, and the `flex-grow: 1` spacer absorbs the ≈318 px remainder. Change any type size or add a line and the spacer shrinks — the page height never does.

### Column order and widths (table [C])

| # | header | width | align | content |
|---|---|---|---|---|
| 1 | `ردیف` | **44px** | center | line number, `.num` |
| 2 | `شرح کالا` | auto (grows) | start (default RTL) | product name; optional 11.5px sub-line for the discount reason |
| 3 | `تعداد` | **64px** | `text-align: right` | quantity, `.num` |
| 4 | `قیمت واحد (تومان)` | **118px** | `text-align: right` | unit price as recorded, `.num` |
| 5 | `تخفیف (تومان)` | **104px** | `text-align: right` | line discount, `.num` |
| 6 | `مبلغ (تومان)` | **122px** | `text-align: right` | line net, `.num`, `font-weight: 700` |

Total of the five fixed columns is 452px, leaving ≈230px for `شرح کالا` inside the 682px content width. Note the RTL oddity in the source: column 1 is `text-align: center` while columns 2–6 are `text-align: right`, which in an RTL document is the *start* edge — so the numeric columns are start-aligned, not end-aligned. That is what the source does; it is listed in §7 because it is more likely a slip than a decision.

### Print-CSS implications

The source contains **no print CSS at all** — no `@page`, no `@media print`, no `print-color-adjust`. It is a fixed-size `<div>`. Everything below is therefore an implementation requirement that the design implies, not something already written:

1. **Fixed page size.** `@page { size: A4; margin: 0 }` with the document keeping its own 56/56/48 padding as the visual margin, *or* `@page { size: A4; margin: <n>mm }` with the padding reduced by the same amount. Pick one — do not apply both (see §7). Express the page in `mm` or `A4`, not in the 794 × 1123 px of the artboard: those pixels are only A4 at exactly 96 dpi, and a printer at any other resolution will scale a px-sized page.
2. **One page, by construction.** The layout is a single fixed-height flex column whose footer is held down by a `flex-grow: 1` spacer. That works for exactly one page and for exactly the two sample lines. A longer order needs real pagination rules that do not exist yet: `thead { display: table-header-group }` so the header repeats, `tr { break-inside: avoid }`, `break-inside: avoid` on the totals block and the footer, and a decision about whether the footer is a running footer on every page or printed once at the end.
3. **Background colours must be forced.** Two fills carry meaning: the navy total bar (`#26364C` with white text) and the table head (`#ECEFF5`). Browsers drop backgrounds in default print settings, which would render the grand total as **white text on white paper**. `-webkit-print-color-adjust: exact; print-color-adjust: exact` is mandatory on at least those two elements; a monochrome-safe fallback (border + dark text instead of a fill) is not designed.
4. **No dark theme, ever.** `data-theme="light"` is hardcoded on the root and every colour is a literal hex rather than a token, so the document cannot follow the app theme or `prefers-color-scheme`. Keep it that way: paper is white.
5. **No interactive chrome.** See §3 for the full list of what must not be added.
6. **Assets must be print-ready.** Two raster images (the 64px circular logo and the 56px-tall wordmark) are referenced by blob URL. They must be embedded or resolvable at print time, and the self-hosted Vazirmatn variable `woff2` must be loaded *before* the print dialog opens, or the whole document reflows in a fallback font and the fixed-height assumption in [E] breaks.
7. **RTL.** `<html lang="fa" dir="rtl">`; every «inline-start» in the diagram above is the right-hand side on paper.

---

## 2. Copy (verbatim)

Every string is copied character-for-character from `src/Invoice.dc.html`, including ZWNJ (نیم‌فاصله) and the Persian thousands separator `٬`.

### Document

| slot | string |
|---|---|
| `<title>` | `فاکتور فروش INV-000038` |

### [A] Header

| slot | string |
|---|---|
| logo `alt` | `لوگوی ربل شاپ` |
| store name (22px / 800, `#26364C`) | `ربل شاپ` |
| store tagline (12px, `#454C59`) | `محصولات موسیقی: وینیل، کاست، سی‌دی، پوستر و تی‌شرت` |
| website line (12px, `#454C59`) | `[نشانی وب‌سایت یا اینستاگرام فروشگاه]` |
| document title (24px / 800, `#26364C`) | `فاکتور فروش` |
| invoice-number label | `شماره:` |
| invoice number (`.inv`, 14px, LTR, monospace) | `INV-000038` |
| date label | `تاریخ:` |
| date (`.num`, bold) | `۱۴۰۵/۰۶/۳۰` |

The website line is a **literal placeholder in square brackets**, not a value — the settings field that fills it is empty by default (`15-settings.md` §6) and its own placeholder text is a *different* string. See §7.

### [B] Party boxes

| slot | string |
|---|---|
| box 1 label | `خریدار` |
| box 1 value | `نگار ک.` |
| box 2 label | `وضعیت پرداخت` |
| box 2 value | `پرداخت‌شده` |

`پرداخت‌شده` is the `ST.paid.name` string from `helpers.js`, i.e. the same status vocabulary as the rest of the app (`پیش‌نویس` · `در انتظار` · `پرداخت‌شده` · `تکمیل‌شده` · `لغوشده` · `مرجوعی`). Only `پرداخت‌شده` is drawn.

### [C] Line-item table

Column headers, in order:

| # | header |
|---|---|
| 1 | `ردیف` |
| 2 | `شرح کالا` |
| 3 | `تعداد` |
| 4 | `قیمت واحد (تومان)` |
| 5 | `تخفیف (تومان)` |
| 6 | `مبلغ (تومان)` |

Body rows, verbatim:

| `ردیف` | `شرح کالا` | `تعداد` | `قیمت واحد (تومان)` | `تخفیف (تومان)` | `مبلغ (تومان)` |
|---|---|---|---|---|---|
| `۱` | `وینیل آلبوم اول` | `۱` | `۲٬۴۵۰٬۰۰۰` | `۰` | `۲٬۴۵۰٬۰۰۰` |
| `۲` | `پوستر تور ۱۴۰۴` + sub-line `تخفیف: مشتری ثابت` | `۲` | `۲۹۰٬۰۰۰` | `۸۰٬۰۰۰` | `۵۰۰٬۰۰۰` |

The discount reason is printed as an 11.5px `#454C59` sub-line inside the description cell with the literal prefix `تخفیف: ` followed by the reason the seller typed on the sale form (`02-record-sale.md` §2, `دلیل تخفیف (اختیاری)`). A line with no discount prints `۰` in column 5, not a dash.

### [D] Totals block

| row | label | value | styling |
|---|---|---|---|
| 1 | `جمع اقلام` | `۳٬۰۳۰٬۰۰۰ تومان` | label `#454C59`, 1px `#E1E1DA` bottom border |
| 2 | `تخفیف` | `−۸۰٬۰۰۰ تومان` | same |
| 3 | `هزینه ارسال` | `۱۸۰٬۰۰۰ تومان` | same |
| 4 | `مبلغ قابل پرداخت` | `۳٬۱۳۰٬۰۰۰ تومان` | navy `#26364C` bar, white text, label 700, value 20px / 800, `border-radius: 0 0 8px 8px` |
| 5 | — | `به حروف: سه میلیون و صد و سی هزار تومان` | 12px `#454C59`, `padding: 8px 12px`, below the navy bar |

Row 5 is one string, verbatim, prefix included: `به حروف: سه میلیون و صد و سی هزار تومان`.

### [F] Footer

| slot | string |
|---|---|
| thank-you line (12.5px, `#454C59`, `max-width: 420px`) | `از خرید شما سپاسگزاریم. برای پیگیری سفارش، شماره فاکتور را همراه داشته باشید.` |
| website line (same style) | `[نشانی وب‌سایت یا اینستاگرام فروشگاه]` |
| wordmark `alt` | `ربل شاپ` |

The thank-you line is the settings value `متن پای فاکتور` (`15-settings.md` §6 quotes the identical string), and the website line is the *same* placeholder as the header's third line — it appears twice in the document.

### Internal fields deliberately ABSENT

None of the following appears anywhere on the page. The values are the real ones for `INV-000038` (`../data/sample-data.md` § INV-000038 in full), listed so a reviewer can grep the rendered output and confirm each one is missing:

| internal field | value for this order | why it must not print |
|---|---|---|
| product cost (`بهای تمام‌شده کالا`) | `۱٬۵۷۰٬۰۰۰` | reveals the store's buying/production cost |
| packaging kit and its cost | `جعبه وینیل` · `۱۴۰٬۰۰۰` | internal cost; the customer never chose a kit |
| postage estimate stamped on the order | `۱۹۹٬۲۷۳` | internal cost, and it is an estimate, not a charge |
| actual postage paid to the post office | part of the month's `۱۴٬۷۶۰٬۰۰۰` | internal, period-level |
| transaction fee (`کارمزد تراکنش`) | `۳۱٬۰۰۰` | internal cost |
| order profit (`سود این سفارش`) | `۱٬۱۸۹٬۷۲۷` | never |
| profit margin (`حاشیه سود`) | `۳۸٪` | never |
| shipping result for the order | `−۱۵۹٬۲۷۳` | derived from postage + packaging |
| sales channel | `وب‌سایت` | internal classification |
| order status history / timeline | the two entries for `۱۴۰۵/۰۶/۳۰` | internal |
| stock movements caused by the order | 3 units + 1 kit | internal |
| the store-wide postage-estimate caption | «جمع پرداختی ÷ جمع سفارش‌ها» | internal method note; it belongs on the app screens only |

Note that `هزینه ارسال ۱۸۰٬۰۰۰` **does** print — that is what the customer was *charged* for shipping, not what shipping cost. The distinction is the whole point of the invariant.

---

## 3. Interactive states designed

**None. The document is non-interactive by design.** It has exactly one state — printed — and no props, no `state` enum, no theme switch and no JS (`renderVals()` returns `{}`).

Not present, and not to be added:

| absent | note |
|---|---|
| Sidebar | no `active` key, no `Sidebar` import, no nav |
| Top bar / mobile bar | no `Topbar`, no `MobileBar`, no page title, no breadcrumb |
| Buttons of any kind | no print button on the document itself, no close, no back, no download |
| Links | there is not one `<a>` in the file |
| Inputs, selects, steppers | nothing is editable; the invoice is a rendering of a saved order |
| Hover, focus, active, disabled states | no interactive element exists to carry them |
| Tooltips | none — the app's `.tipwrap`/`.tipbox` pattern is not used here |
| Empty / loading / error states | the `[[STATES]]`/`[[MSTATES]]` macro is **not** used; there is no skeleton and no failure board |
| Dark theme | `data-theme="light"` is hardcoded; all colours are literal hex, not tokens |
| Mobile / responsive layout | one fixed 794 × 1123 box; no `MPAGE`, no breakpoint, no mobile artboard |
| Toasts, dialogs, overlays, `aria-live` | none |
| Status badges (`.badge`, `.ch`) | the status is plain 15/700 text in a bordered box, not the app's badge component |

The only two behaviours the document depends on are the browser's own: the print dialog, and font/image loading before it opens.

---

## 4. Validation

**None.** There is nothing to validate: no input, no form, no submit, no action. Every value is already-saved order data, validated on the record-sale screen (`02-record-sale.md` §4) before it could ever reach an invoice.

Two content risks exist that validation elsewhere does *not* cover, and they are content-length rules rather than validation messages — both are recorded in §7:

- `نام مشتری` is free text with no length limit (`02-record-sale.md` §7) and prints at 15px / 700 in a half-width box with no truncation rule.
- `متن پای فاکتور` has no maximum length (`15-settings.md` §4) and prints into a `max-width: 420px` box at 12.5px; a longer string wraps to a third or fourth line and eats into the spacer.

---

## 5. Logic

There is no arithmetic in the file — every number is literal markup. What follows is the contract: which saved field feeds which slot, and how each total is derived. All derivations are `../logic/formulas.md` §1 (order profit / customer total); nothing new is defined here.

### Exactly which fields print

| slot | source field | notes |
|---|---|---|
| store name | settings `نام فروشگاه` | `15-settings.md` §6 |
| store tagline | **hardcoded in the document** | no settings field exists for it — see §7 |
| website line (header + footer, twice) | settings `وب‌سایت یا اینستاگرام (روی فاکتور)` | `15-settings.md` §6; currently empty, so the placeholder prints |
| invoice number | `prefix + sequence`, assigned by the backend at save | settings `پیشوند شماره فاکتور` (`INV-`) + the order's number; `02-record-sale.md` §5, `15-settings.md` §6 |
| date | the **order's** date, Jalali | `۱۴۰۵/۰۶/۳۰` — the order date, *not* today (`۱۴۰۵/۰۶/۳۱`). Not a print date |
| `خریدار` | the order's `نام مشتری` | free text typed on the sale form; the app stores no customer record (`02-record-sale.md` §7) |
| `وضعیت پرداخت` | the order's status | `ST[status].name` from `helpers.js` |
| line `ردیف` | 1-based position in the order | display only |
| line `شرح کالا` | `product.name` at the time of printing | the product name, not a SKU — there is no product code anywhere in the design |
| line discount sub-line | the line's `دلیل تخفیف` | printed as `تخفیف: <reason>`; omitted when there is no reason |
| line `تعداد` | `qty` | integer; fractional quantities exist only for materials, never on an order |
| line `قیمت واحد (تومان)` | `unitPrice` **as recorded on the order** | retail or wholesale, including any manual override — historical, never re-priced |
| line `تخفیف (تومان)` | `lineDiscount` | `۰` when absent |
| line `مبلغ (تومان)` | `qty × unitPrice − lineDiscount` | the line **net**; bold |
| footer thank-you line | settings `متن پای فاکتور` | `15-settings.md` §6 |
| logo, wordmark | `assets/` | `alt="لوگوی ربل شاپ"` / `alt="ربل شاپ"` |

### How each total is derived

```
جمع اقلام         = itemsGross   = Σ (qty × unitPrice)          ← GROSS, before discounts
تخفیف             = −discountSum = −Σ lineDiscount              ← printed with a leading "−"
هزینه ارسال       = shippingCharge                              ← what the customer was charged
مبلغ قابل پرداخت  = itemsGross − discountSum + shippingCharge
                  = customerTotal                                ← formulas.md §1
به حروف           = customerTotal, spelled out in Persian words
```

`مبلغ قابل پرداخت` is exactly `customerTotal` from `../logic/formulas.md` §1 — the same figure the record-sale summary calls `مبلغ قابل پرداخت` and the orders list calls `مبلغ کل`. The invoice stops there: the four internal subtractions that turn `customerTotal` into `profit` in §1 of the formulas file are the fields the invariant excludes, and none of them is on the page.

Two derivation notes that matter for implementation:

- **The `مبلغ` column and `جمع اقلام` use different bases.** Column 6 is the line **net** (`qty × unitPrice − lineDiscount`), so the column sums to `itemsNet`, while the totals block starts from `itemsGross` and subtracts the discount again on its own row. Both paths land on the same `مبلغ قابل پرداخت`, but a customer adding up the last column gets a number that appears nowhere on the page. See §7.
- **`به حروف` has no producer.** Every other value on the invoice is a field the backend already has or a sum of such fields. The amount-in-words string is the single exception: nothing in `helpers.js` produces it (`fa()`, `faD()`, `faT()`, `faQ()` all emit digits) and no other screen in the design contains a Persian number-to-words rendering. Implementing it means writing a Persian cardinal speller for Toman amounts. Its fate is an open decision — see §7.

---

## 6. Sample data used

The board renders `INV-000038` — `../data/sample-data.md` § «INV-000038 in full», which is also the order used by the order-detail screen. Channel `وب‌سایت`, customer `نگار ک.`, kit `جعبه وینیل`, status `پرداخت‌شده`, dated `۱۴۰۵/۰۶/۳۰`.

### Lines

| # | product | qty | unit price | line gross | discount | line net (`مبلغ`) |
|---|---|---|---|---|---|---|
| 1 | وینیل آلبوم اول (`p1`) | 1 | 2,450,000 | 1 × 2,450,000 = **2,450,000** | 0 | **2,450,000** |
| 2 | پوستر تور ۱۴۰۴ (`p5`) | 2 | 290,000 | 2 × 290,000 = **580,000** | 80,000 («مشتری ثابت») | 580,000 − 80,000 = **500,000** |

Unit prices are the retail prices from `CATALOG` (`وب‌سایت` is a retail channel — `../data/sample-data.md` § Channel defaults), so nothing was manually overridden on this order.

### The totals, with arithmetic

```
جمع اقلام            2,450,000 + 580,000            = 3,030,000
تخفیف                                       −            80,000
هزینه ارسال          وب‌سایت default              +           180,000
-------------------------------------------------------------------
مبلغ قابل پرداخت     3,030,000 − 80,000 + 180,000   = 3,130,000
```

`3,130,000` matches `ORDERS[3]` (`INV-000038`, total 3,130,000) in `helpers.js` and the orders-list row in `../data/sample-data.md` ✓, and it matches `formulas.md` §1's `customerTotal` for this order ✓.

Cross-check on the printed column: `2,450,000 + 500,000 = 2,950,000` — the sum of the `مبلغ` column, i.e. `itemsNet`. `2,950,000 + 180,000 = 3,130,000` ✓, so both routes agree on the bottom line even though `2,950,000` is never printed.

Amount in words: `3,130,000` → `سه میلیون و صد و سی هزار تومان` ✓ (three million, one hundred thirty thousand).

### The internal figures for the same order, which must NOT appear

Given here only so the exclusion can be verified against the rendered page:

```
product cost      1,380,000 + 2 × 95,000          = 1,570,000
packaging kit     جعبه وینیل                       =   140,000
postage estimate  store-wide, stamped at save      =   199,273
transaction fee   entered on the order             =    31,000
-------------------------------------------------------------------
profit            3,130,000 − 1,570,000 − 140,000 − 199,273 − 31,000
                                                   = 1,189,727   (margin ۳۸٪)
shipping result   180,000 − (140,000 + 199,273)    =  −159,273
```

Every one of those six numbers is absent from the document, and `۳٬۱۳۰٬۰۰۰` / `۱۸۰٬۰۰۰` / `۸۰٬۰۰۰` / `۲٬۴۵۰٬۰۰۰` / `۵۰۰٬۰۰۰` / `۳٬۰۳۰٬۰۰۰` / `۲۹۰٬۰۰۰` are the only money figures that are present.

### Formatting

Persian tabular digits throughout (`.num` → `font-feature-settings: "tnum" 1`), `٬` as the thousands separator, Toman with **no** decimals, the minus rendered as `−` (U+2212) not a hyphen, the invoice number LTR-isolated in `.inv` (`direction: ltr; unicode-bidi: isolate`, monospace), and the date as a Jalali `YYYY/MM/DD` in Persian digits. `../design-system.md` § numerals is the rule; the invoice follows it without exception.

---

## 7. Open questions for this screen

- **«به حروف» is the one element the backend does not already produce, and the client has not answered.** The line `به حروف: سه میلیون و صد و سی هزار تومان` is in the design, but every other value on the page is a stored field or a sum of stored fields, whereas this one needs a Persian cardinal number-to-words function that exists nowhere in the design or in `helpers.js`. **The client was asked whether to keep the line and that decision is still open.** Until it is answered, do not silently drop it and do not silently implement it: if it stays, the speller needs a spec (does it say `تومان` or `ریال`? how are zero, one and round millions phrased? what happens above a billion? is it ever needed on the app screens or only here?); if it goes, region [D] loses ≈32px and the spacer [E] grows by the same amount.
- **No multi-page design exists.** The page is a fixed 1123px with a `flex-grow: 1` spacer; the sample order has two lines. Nothing is designed for an order that overflows: no repeating table header, no «ادامه در صفحه بعد», no page numbering («صفحه ۱ از ۲»), no rule for whether the totals block may be split from the table, and no maximum line count. Decide the overflow model before implementing, because it determines whether the footer is a running footer or a once-at-the-end block.
- **There is no print stylesheet in the source at all.** No `@page`, no `@media print`, no `print-color-adjust`. Three consequences need decisions: (a) page margin via `@page` versus the document's own 56/56/48 padding — currently both would apply and the content box would shrink; (b) whether the navy `مبلغ قابل پرداخت` bar and the `#ECEFF5` table head are forced to print (without `print-color-adjust: exact` the grand total prints white-on-white); (c) whether a monochrome/black-and-white fallback is required for the two raster images and the navy fills.
- **The website line is a bracketed placeholder printed twice, and the settings placeholder is a different string.** The document prints `[نشانی وب‌سایت یا اینستاگرام فروشگاه]` in the header and again in the footer, while the settings field that feeds it (`وب‌سایت یا اینستاگرام (روی فاکتور)`) is empty with the placeholder `[نشانی وب‌سایت فروشگاه]` (`15-settings.md` §6). Decide: the empty-value behaviour (hide the line, or print brackets on a customer's invoice), whether the same value really belongs in both places, and which of the two placeholder strings is correct.
- **The store tagline has no settings field.** `محصولات موسیقی: وینیل، کاست، سی‌دی، پوستر و تی‌شرت` is hardcoded in the document, but `15-settings.md`'s `فروشگاه و فاکتور` section has only name, website, prefix, next number and footer text. Either add a tagline field or accept the string as fixed product copy.
- **The `مبلغ` column and `جمع اقلام` do not reconcile on the page.** Column 6 sums to `2,950,000` (net of discount) while the totals block shows `جمع اقلام ۳٬۰۳۰٬۰۰۰` and then subtracts `تخفیف ۸۰٬۰۰۰` again. A customer who adds the column up gets a figure printed nowhere. Pick one convention: make column 6 gross and keep the `تخفیف` total row, or keep column 6 net and make the total row read `جمع اقلام پس از تخفیف` (which is the phrasing the record-sale footer already uses).
- **No legal/tax fields.** No VAT or tax line, no seller `کد اقتصادی` or registration number, no buyer tax ID, no «فاکتور رسمی» versus «پیش‌فاکتور» distinction. `15-settings.md` §7 records the same gap from the settings side. Whether this document must satisfy any Iranian invoicing requirement is undecided, and it changes both the totals block and the header.
- **No customer contact or delivery details, because the app has none.** The document charges `هزینه ارسال ۱۸۰٬۰۰۰` but cannot say where the parcel goes: there is no customer record anywhere in the product (`02-record-sale.md` §7), so no address, no phone, no postcode. There is also no tracking number field (`کد رهگیری`), even though the footer tells the customer to quote the invoice number to follow up. For a mail-order store this is the largest functional gap on the page.
- **Only one order status is drawn.** The `وضعیت پرداخت` box shows `پرداخت‌شده`. Undefined: what it shows for `پیش‌نویس`, `در انتظار`, `تکمیل‌شده`, `لغوشده` and `مرجوعی`; whether a draft may be printed at all (it has no invoice number yet — the number is assigned at save, `02-record-sale.md` §5); and whether a cancelled or refunded invoice needs a watermark, a «باطل شد» stamp or a credit-note layout. No duplicate/«کپی» marking exists either.
- **Column alignment is suspect.** Columns 2–6 are `text-align: right`, which in this RTL document is the **start** edge, so the numeric columns are start-aligned rather than end-aligned; column 1 is `center`. Everywhere else in the app numeric cells use `.n`/`.num` and align to the end (`.tbl .n { text-align: right }` works there because those tables are laid out in the app's RTL flow with the same declaration reading as "end"). Confirm whether the invoice's numeric columns are meant to look different from every other table in the product.
- **`تخفیف (تومان)` prints `۰` on undiscounted lines.** No rule says whether a zero should be a dash, blank or `۰`, and no rule covers a discount with no reason typed (the sub-line simply disappears) or a reason long enough to wrap the description cell.
- **No on-screen or small-screen presentation.** The document is a fixed 794px box with no responsive behaviour, so the `پیش‌نمایش فاکتور` link from settings and the `چاپ فاکتور` action from order detail open something that will overflow a 390px phone. Whether there is an in-app preview (scaled, scrollable, in a dialog?) or the action goes straight to the browser print dialog is not designed.
- **Export mechanics are unspecified.** `چاپ فاکتور (PDF)` promises a PDF, but nothing says whether that is `window.print()` to a browser PDF, a server-rendered file, or a download; there is no filename convention, no PDF metadata (title, author), no busy state and no failure state. This is the same open decision as the export buttons in `12-reports.md` §7 — see `../open-questions.md`.
- **Document semantics are thin.** There is no `<h1>` (the largest text, `فاکتور فروش`, is a `<span>`), the table has no `<caption>` and no `scope` attributes, the two party boxes are `<div>`s rather than a definition list, and the two `[نشانی …]` placeholders would be read aloud verbatim by a screen reader. If the invoice is ever emailed as HTML rather than printed, these matter.
- **Content-length rules are missing on the two free-text fields.** `نام مشتری` prints at 15px / 700 into a half-width box with no truncation, and `متن پای فاکتور` prints into `max-width: 420px` at 12.5px with no maximum length (`15-settings.md` §4 and §7). Both can overflow their region and eat the spacer that holds the footer at the bottom of the page.
