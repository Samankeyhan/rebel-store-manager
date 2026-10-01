# 13 — شرکا و تقسیم سود (Partners & profit distribution)

Route: `/partners` · sidebar key `partners` · page title in top bar: **شرکا و تقسیم سود**

Three things live on one page: the partner list with an editable share percentage per partner, a form that records one profit distribution for a Jalali period, and the history of past distributions. The screen is the only place where money leaves the business as partner payouts, so it carries two hard blocks (shares must total exactly ۱۰۰٪, and a period may not overlap an already-distributed period) and one soft block (distributing more than the undistributed profit, which needs an explicit acknowledgement before the button turns into a destructive-styled one). Everything is derived from the net profit of the chosen period plus whatever was carried over undistributed — see `../logic/formulas.md` §9.

Artboards:

| file | props | canvas | what it shows |
|---|---|---|---|
| `Partners.dc.html` | `preset: default`, `state: ready` | 1440 × 1180 | the normal screen: shares 60/25/15, amount ۴۰٬۰۰۰٬۰۰۰, nothing blocked |
| `Partners-Shares.dc.html` | `preset: shares`, `h: 1400` | 1440 × 1400 | shares 60/25/10 → sum ۹۵٪, the shares warning, save blocked |
| `Partners-Overlap.dc.html` | `preset: overlap`, `h: 1400` | 1440 × 1400 | overlapping period, blocking alert, period profit `—`, save blocked |
| `Partners-Exceed.dc.html` | `preset: exceed`, `h: 1480` | 1440 × 1480 | amount ۶۰٬۰۰۰٬۰۰۰ > undistributed, warning + acknowledgement checkbox |
| `Partners-States.dc.html` | three children, `state: empty / loading / error` | 3 × 1440 × 760 | the three non-ready states side by side |
| `PartnersMobile.dc.html` | `state: ready` | 390 × 1020 | mobile, with the over-distribution case baked in |
| `PartnersMobile-States.dc.html` | three children | 3 × 390 × 844 | mobile empty / loading / error |

The desktop artboard is interactive: `preset` (`default | overlap | exceed | shares`) plus `state`, `theme`, `h`. Typing in the amount input recomputes the whole preview and the block reason live (`onAmt` also resets the acknowledgement). The mobile artboard is static — its numbers and its ticked checkbox are hardcoded.

---

## 1. Layout

### Desktop (1440 × 1180 default; fluid 1024–1600)

```
┌ sidebar 264 (right) ┬──────────────────── content 1176 ─────────────────────┐
│                     │ top bar 64: «شرکا و تقسیم سود»                        │
│                     ├───────────────────────────────────────────────────────┤
│                     │ main  padding 24 / 32 / 40   →  inner width 1112      │
│                     │ ┌ row: flex, gap 24, align-items: flex-start ───────┐ │
│                     │ │ ┌ right col 440 ──────┐ ┌ left card grow 648 ───┐ │ │
│                     │ │ │ card «شرکا»         │ │ card «ثبت تقسیم سود»  │ │ │
│                     │ │ │  card-h + btn 32h   │ │  card-h 56            │ │ │
│                     │ │ │  table: 3 rows 52h  │ │  card-b padding 20    │ │ │
│                     │ │ │  tfoot «جمع سهم‌ها» │ │   1 دوره  (select 420) │ │ │
│                     │ │ │  ok line / warn     │ │   2 overlap alert      │ │ │
│                     │ │ ├─ gap 20 ────────────┤ │   3 two stat tiles     │ │ │
│                     │ │ │ card: 3 summary     │ │     grid 2×, gap 12    │ │ │
│                     │ │ │  lines + sep +      │ │   4 مبلغ قابل تقسیم    │ │ │
│                     │ │ │  «کل سود تقسیم‌نشده»│ │     (input 300)        │ │ │
│                     │ │ └─────────────────────┘ │   5 exceed alert + ✓   │ │ │
│                     │ │                         │   6 preview table      │ │ │
│                     │ │                         │   7 submit + reason    │ │ │
│                     │ │                         └────────────────────────┘ │ │
│                     │ └───────────────────────────────────────────────────┘ │
│                     │ ┌ card «سوابق تقسیم سود» — full 1112 ───────────────┐ │
│                     │ │ card-h 56 + table: 7 cols, 4 rows 52h, tfoot      │ │
│                     │ └───────────────────────────────────────────────────┘ │
└─────────────────────┴───────────────────────────────────────────────────────┘
```

- `main`: `padding: 24px 32px 40px; display:flex; flex-direction:column; gap:20px`.
- The two-column row: `display:flex; gap:24px; align-items:flex-start`. Right (first in DOM, so visually right in RTL) column `width:440px; flex-shrink:0; flex-direction:column; gap:20px`. The distribution card is `.card.grow` (`flex-grow:1; min-width:0`) → 648px at 1440.
- The history card is a sibling of the row inside the same `sc-if`, so it spans the full 1112px below it.
- Cards: `.card` = `--surface`, 1px `--border`, radius 12, `--shadow`. `.card-h` = `padding:16px 20px` with a bottom border (56px tall). `.card-b` = `padding:20px`.
- Tables: `.tbl th` 40px on `--surface-2`, `.tbl td` 52px, `.tbl tfoot td` on `--surface-2` and bold. All numeric cells carry `.n .num` (`text-align:right` + `tnum`).
- Both alerts are `.alert` (`padding:12px 16px`, radius 10, 1px border) — the shares one is inset with `margin:12px 16px 16px`, the two in the form are flow children of `.card-b`.

#### Partner table columns (exact order, right→left)

1. **شریک** — `.avatar` 32×32 circle with the one-letter initial (`--navy-soft`, 13px/700) + the name in `.b`; `display:flex; gap:10px; align-items:center`.
2. **سهم** — `.n`; an `.ig` of `width:92px; margin-right:auto` containing `input.input.input-num` at `height:34px; padding-left:28px` and a `.sfx` `٪` at `left:10px`. `aria-label="درصد سهم"`. The value in the input is digits only (`۶۰`), the `٪` is the suffix.
3. **جمع دریافتی (تومان)** — `.n .num`, read-only text.
4. *(no header, `width:44px`)* — `button.btn.btn-ghost.btn-icon.btn-sm` (32×32) with the pencil icon, `aria-label="ویرایش"`.

`tfoot`: `جمع سهم‌ها` · the sum with `٪` (`.num` + `pos`/`neg`) · the paid-to-date total · empty cell.

#### Undistributed-profit card (right column, second)

`padding:16px 20px; display:flex; flex-direction:column; gap:8px` — three `.sl` rows, the third preceded by `.sep`:

1. `سود خالص تقسیم‌نشده دوره‌های قبل` → `۱۲٬۴۰۰٬۰۰۰`
2. `سود خالص شهریور ۱۴۰۵` → `۴۲٬۰۴۶٬۰۰۰` (`.v.pos`)
3. `.sep`, then `.sl.total`: `کل سود تقسیم‌نشده` → `۵۴٬۴۴۶٬۰۰۰` + `تومان` in `.t-cap.muted` (weight 500)

#### Distribution form — field order (exact)

1. **دوره** — `label.label` + `button.select` (`max-width:420px`, 40px) showing the calendar icon and the period in `<b class="num">`, chevron-down at the end; `.help` beneath.
2. *(conditional)* overlap `.alert.alert-err` with the ban icon, a `.grow` body and an outline `btn-sm` quick-fix at the end.
3. Two stat tiles: `grid-template-columns: repeat(2, minmax(0,1fr)); gap:12px`; each `background:--surface-2; border-radius:10px; padding:12px`, caption `.t-cap.muted.b`, value `.num.b` at 20px. Right tile = period net profit, left tile = total undistributed.
4. **مبلغ قابل تقسیم** — `label` for `#am` + `.ig` (`max-width:300px`) with `input#am.input.input-num` (40px) and `.sfx` `تومان`; `.help` beneath carrying the remaining figure in `<b class="num">`.
5. *(conditional)* exceed `.alert.alert-warn` — `flex-direction:column; gap:10px`: first a triangle icon + title + body, then the acknowledgement row: `button.check` (18×18, `role="checkbox"`, `aria-checked`) inside a `label.t-sm.b` with `padding-right:30px`.
6. Preview table in a wrapper `border:1px solid var(--border); border-radius:10px; overflow:hidden` — 3 columns: `شریک` · `سهم` (`.n`) · `مبلغ این تقسیم (تومان)` (`.n`, bold values); `tfoot` = `جمع` · sum of shares · the amount.
7. Submit row: `display:flex; gap:10px; align-items:center` — the primary (or danger) 40px button, then a `.t-cap` block-reason label.

#### History table columns (exact order, right→left)

1. `دوره` (`.num`, e.g. `مرداد ۱۴۰۵ · ۰۵/۰۱ تا ۰۵/۳۱`)
2. `تاریخ ثبت` (`.num.muted2`)
3. `سود خالص دوره (تومان)` (`.n.num`)
4. `مبلغ تقسیم‌شده (تومان)` (`.n.num.b`)
5. `مالک فروشگاه` (`.n.num`)
6. `شریک سرمایه‌گذار` (`.n.num`)
7. `شریک هنری` (`.n.num`)

`tfoot`: `جمع` with `colspan="2"`, then the five column totals.

### Mobile (390 × 1020)

```
┌ 390 ─────────────────────────────────────┐
│ MobileBar 56: menu 44 · logo 26 · title  │
├──────────────────────────────────────────┤
│ main padding 14/16/100, gap 12 → 358 wide│
│ ┌ card «شرکا» padding 14, gap 8 ───────┐ │
│ │ t-h3 + 3 .sl rows + ok line          │ │
│ └──────────────────────────────────────┘ │
│ ┌ card «ثبت تقسیم سود» padding 14 ─────┐ │
│ │ t-h3                                 │ │
│ │ period select  48h  (full width)     │ │
│ │ .sl سود خالص دوره                    │ │
│ │ .sl کل سود تقسیم‌نشده                │ │
│ │ field مبلغ قابل تقسیم  input 48h     │ │
│ │ alert-warn + ✓ row (min-height 44)   │ │
│ │ 3 × .sl per-partner preview          │ │
│ └──────────────────────────────────────┘ │
├──────────────────────────────────────────┤
│ sticky bottom bar, padding 12/16/20      │
│ [ تقسیم با وجود کسری ]  btn-danger btn-lg│
│  full width, 48h                         │
└──────────────────────────────────────────┘
```

- `main`: `padding:14px 16px 100px; display:flex; flex-direction:column; gap:12px` (the 100px bottom padding clears the sticky bar).
- Bottom bar: `position:absolute; left:0; right:0; bottom:0; padding:12px 16px 20px; background:--surface; border-top:1px solid --border`; the button is `btn btn-danger btn-lg` at `width:100%` (48px tall).
- Mobile field order inside the distribution card: 1 period button (48px) → 2 period-profit line → 3 total-undistributed line → 4 amount input (48px, `is-warn`) → 5 warning + acknowledgement → 6 three preview lines. Touch targets: the period button and the amount input are 48px, the acknowledgement label `min-height:44px`.
- **Not present on mobile:** the add-partner button, the per-partner edit button, the editable share inputs (shares are plain text), the period help line, the overlap alert, the remaining-amount help, the preview table footer and the whole history table.

---

## 2. Copy (verbatim)

### Page chrome

| place | string |
|---|---|
| sidebar item + `title` attribute | `شرکا و تقسیم سود` |
| top bar `h1` | `شرکا و تقسیم سود` |
| desktop artboard `<title>` | `شرکا و تقسیم سود` |
| mobile artboard `<title>` | `شرکا و تقسیم سود — موبایل` |
| `Partners-Shares` wrapper title | `شرکا و تقسیم سود — جمع سهم‌ها ≠ ۱۰۰٪` |
| `Partners-Overlap` wrapper title | `شرکا و تقسیم سود — دوره هم‌پوشان (مسدود)` |
| `Partners-Exceed` wrapper title | `شرکا و تقسیم سود — بیش از سود تقسیم‌نشده` |
| `Partners-States` wrapper title | `شرکا و تقسیم سود — خالی · بارگذاری · خطا` |
| `PartnersMobile-States` wrapper title | `شرکا و تقسیم سود موبایل — خالی · بارگذاری · خطا` |

### Partners card

| element | string |
|---|---|
| card heading | `شرکا` |
| header button | `افزودن شریک` (plus icon 14) |
| th 1 | `شریک` |
| th 2 | `سهم` |
| th 3 | `جمع دریافتی (تومان)` |
| share input `aria-label` | `درصد سهم` |
| share input suffix | `٪` |
| row action `aria-label` | `ویرایش` |
| tfoot label | `جمع سهم‌ها` |
| partner 1 | `مالک فروشگاه` · initial `م` |
| partner 2 | `شریک سرمایه‌گذار` · initial `س` |
| partner 3 | `شریک هنری` · initial `ه` |

Shares-OK line (`.t-cap.pos.b`, check-circle icon 14, shown when the sum is exactly 100):

```
جمع سهم‌ها ۱۰۰٪ است.
```

Shares-bad alert (`.alert.alert-warn`, `role="alert"`, triangle icon 18) — title, then body, then the difference sentence appended to the body:

```
title: جمع سهم‌ها ۹۵٪ است، نه ۱۰۰٪
body:  تا جمع سهم‌ها دقیقاً ۱۰۰٪ نشود، تقسیم سود ثبت نمی‌شود. ۵٪ سهم بدون صاحب مانده است.
```

The last sentence has two forms (`diffT`):

| case | string |
|---|---|
| sum < 100 | `۵٪ سهم بدون صاحب مانده است.` (the number is `۱۰۰ − sum`) |
| sum > 100 | `۵٪ بیشتر از کل است.` (the number is `sum − ۱۰۰`) |

### Undistributed-profit card

| row | label | value |
|---|---|---|
| 1 | `سود خالص تقسیم‌نشده دوره‌های قبل` | `۱۲٬۴۰۰٬۰۰۰` |
| 2 | `سود خالص شهریور ۱۴۰۵` | `۴۲٬۰۴۶٬۰۰۰` |
| 3 | `کل سود تقسیم‌نشده` | `۵۴٬۴۴۶٬۰۰۰` + `تومان` |

### Distribution form

| element | string |
|---|---|
| card heading | `ثبت تقسیم سود` |
| period label | `دوره` |
| period value (normal) | `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` |
| period value (overlap preset) | `۱۴۰۵/۰۵/۱۵ تا ۱۴۰۵/۰۶/۱۵` |
| period help | `دوره نباید با دوره‌های تقسیم‌شده قبلی هم‌پوشانی داشته باشد.` |
| tile 1 caption | `سود خالص این دوره` |
| tile 1 value | `۴۲٬۰۴۶٬۰۰۰` — or `—` when the period overlaps |
| tile 2 caption | `کل سود تقسیم‌نشده (با دوره‌های قبل)` |
| tile 2 value | `۵۴٬۴۴۶٬۰۰۰` |
| amount label | `مبلغ قابل تقسیم` |
| amount suffix | `تومان` |
| amount help | `پس از ثبت، ۱۴٬۴۴۶٬۰۰۰ تومان تقسیم‌نشده باقی می‌ماند.` (the bold number is `leftT`) |
| preview th | `شریک` · `سهم` · `مبلغ این تقسیم (تومان)` |
| preview tfoot | `جمع` |
| submit (normal) | `ثبت تقسیم سود` |
| submit (acknowledged over-distribution) | `تقسیم با وجود کسری` |

Block-reason label next to the button (`blockT`, `.t-cap.neg.b` when non-empty, `.t-cap.muted` when empty) — exactly one of:

| condition | string |
|---|---|
| period overlaps | `دوره هم‌پوشانی دارد` |
| shares ≠ 100٪ | `جمع سهم‌ها باید ۱۰۰٪ باشد` |
| over-distribution not yet acknowledged | `برای ادامه، تأیید بالا را بزنید` |
| nothing blocking | *(empty string)* |

### Overlap alert (verbatim, `Partners-Overlap`)

```
title:  این دوره با تقسیم قبلی هم‌پوشانی دارد
body:   بازه ۱۴۰۵/۰۵/۱۵ تا ۱۴۰۵/۰۵/۳۱ قبلاً در تقسیم «مرداد ۱۴۰۵» (ثبت‌شده در ۱۴۰۵/۰۶/۰۲) حساب شده است. سود هر روز فقط یک بار تقسیم می‌شود. تاریخ شروع را ۱۴۰۵/۰۶/۰۱ یا بعد از آن انتخاب کنید.
button: شروع از ۱۴۰۵/۰۶/۰۱
```

`۱۴۰۵/۰۵/۱۵ تا ۱۴۰۵/۰۵/۳۱` and `۱۴۰۵/۰۶/۰۱` inside the body are `<b class="num">`; the icon is `ban`.

### Over-distribution warning (verbatim, `Partners-Exceed`)

```
title: مبلغ ۵٬۵۵۴٬۰۰۰ تومان بیشتر از سود تقسیم‌نشده است
body:  با این تقسیم، بیش از سود واقعی برداشت می‌شود و مانده سود تقسیم‌نشده منفی (−۵٬۵۵۴٬۰۰۰) می‌شود؛ یعنی بخشی از پول از سرمایه فروشگاه پرداخت شده است.
checkbox label: می‌دانم؛ با وجود این تقسیم شود
```

The title number is `overT` = amount − undistributed; the parenthesised number is `leftT` and carries the Persian minus `−` produced by `fa()`. On mobile the same warning is shortened to one line:

```
۵٬۵۵۴٬۰۰۰ تومان بیشتر از سود تقسیم‌نشده است.
```

(the amount in `<b>`, the sentence ending in a full stop, no title/body split, same checkbox label).

### History card

| element | string |
|---|---|
| card heading | `سوابق تقسیم سود` |
| th | `دوره` · `تاریخ ثبت` · `سود خالص دوره (تومان)` · `مبلغ تقسیم‌شده (تومان)` · `مالک فروشگاه` · `شریک سرمایه‌گذار` · `شریک هنری` |
| tfoot | `جمع` |

Rows verbatim:

| دوره | تاریخ ثبت | سود خالص دوره | مبلغ تقسیم‌شده | مالک فروشگاه | شریک سرمایه‌گذار | شریک هنری |
|---|---|---|---|---|---|---|
| `مرداد ۱۴۰۵ · ۰۵/۰۱ تا ۰۵/۳۱` | `۱۴۰۵/۰۶/۰۲` | `۳۸٬۹۰۰٬۰۰۰` | `۳۵٬۰۰۰٬۰۰۰` | `۲۱٬۰۰۰٬۰۰۰` | `۸٬۷۵۰٬۰۰۰` | `۵٬۲۵۰٬۰۰۰` |
| `تیر ۱۴۰۵ · ۰۴/۰۱ تا ۰۴/۳۱` | `۱۴۰۵/۰۵/۰۳` | `۳۳٬۲۰۰٬۰۰۰` | `۳۰٬۰۰۰٬۰۰۰` | `۱۸٬۰۰۰٬۰۰۰` | `۷٬۵۰۰٬۰۰۰` | `۴٬۵۰۰٬۰۰۰` |
| `خرداد ۱۴۰۵ · ۰۳/۰۱ تا ۰۳/۳۱` | `۱۴۰۵/۰۴/۰۴` | `۳۰٬۵۰۰٬۰۰۰` | `۲۸٬۰۰۰٬۰۰۰` | `۱۶٬۸۰۰٬۰۰۰` | `۷٬۰۰۰٬۰۰۰` | `۴٬۲۰۰٬۰۰۰` |
| `اردیبهشت ۱۴۰۵ · ۰۲/۰۱ تا ۰۲/۳۱` | `۱۴۰۵/۰۳/۰۲` | `۲۷٬۸۰۰٬۰۰۰` | `۲۵٬۰۰۰٬۰۰۰` | `۱۵٬۰۰۰٬۰۰۰` | `۶٬۲۵۰٬۰۰۰` | `۳٬۷۵۰٬۰۰۰` |
| **`جمع`** | | `۱۳۰٬۴۰۰٬۰۰۰` | `۱۱۸٬۰۰۰٬۰۰۰` | `۷۰٬۸۰۰٬۰۰۰` | `۲۹٬۵۰۰٬۰۰۰` | `۱۷٬۷۰۰٬۰۰۰` |

### Mobile-only copy

| element | string |
|---|---|
| card 1 heading | `شرکا` |
| row 1 | `مالک فروشگاه` → `۶۰٪` + `· ۷۰٬۸۰۰٬۰۰۰` |
| row 2 | `شریک سرمایه‌گذار` → `۲۵٪` + `· ۲۹٬۵۰۰٬۰۰۰` |
| row 3 | `شریک هنری` → `۱۵٪` + `· ۱۷٬۷۰۰٬۰۰۰` |
| shares-OK line | `جمع سهم‌ها ۱۰۰٪` *(no «است.» — differs from desktop)* |
| card 2 heading | `ثبت تقسیم سود` |
| period button | `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` |
| line | `سود خالص دوره` → `۴۲٬۰۴۶٬۰۰۰` |
| line | `کل سود تقسیم‌نشده` → `۵۴٬۴۴۶٬۰۰۰` |
| amount label / value | `مبلغ قابل تقسیم` / `۶۰٬۰۰۰٬۰۰۰` |
| preview | `مالک فروشگاه (۶۰٪)` → `۳۶٬۰۰۰٬۰۰۰` |
| preview | `شریک سرمایه‌گذار (۲۵٪)` → `۱۵٬۰۰۰٬۰۰۰` |
| preview | `شریک هنری (۱۵٪)` → `۹٬۰۰۰٬۰۰۰` |
| sticky button | `تقسیم با وجود کسری` |

### Empty state (`state: empty`, users icon 28 in a 56px `.e-art`, padding 96px 24px desktop / 48px 20px mobile)

Desktop:

```
title: هنوز شریکی تعریف نشده
body:  شرکا و درصد سهم هر کدام را وارد کنید؛ جمع سهم‌ها باید ۱۰۰٪ باشد. سپس می‌توانید سود خالص هر دوره را تقسیم کنید.
cta:   افزودن شریک
```

Mobile (same title and CTA, shorter body, CTA is `btn-primary btn-lg`):

```
body:  شرکا و درصد سهم را وارد کنید.
```

### Loading state (`state: loading`)

Skeletons only, no text: `<section aria-busy="true" aria-label="در حال بارگذاری">` containing a 20 × 180px `.sk` title bar and then **8** blocks of `height:40px; border-radius:10px` on desktop, **5** blocks of `height:84px` on mobile, `gap:12px`.

### Error state (`state: error`, cloud-off icon 28 on `--loss-soft`)

```
title:  اطلاعات شرکا بارگذاری نشد
body:   اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.
button: تلاش دوباره   (btn-outline, refresh icon 16)
```

The mobile error title is identical (`اطلاعات شرکا بارگذاری نشد`) because both boards pass the same `[[STATES:…]]`/`[[MSTATES:…]]` fifth argument `اطلاعات شرکا`, and the macro appends ` بارگذاری نشد`.

---

## 3. Interactive states designed

| element | states |
|---|---|
| Partner share input (`.input.input-num`, 34px) | default, focus (`border --navy-2` + `0 0 0 3px var(--ring)`); always editable, no read-only state |
| Share sum in `tfoot` | `pos` (green, sum = 100) / `neg` (red, sum ≠ 100) |
| Shares feedback block | OK line (`.t-cap.pos.b` + check icon) **xor** `.alert.alert-warn` (triangle icon, `role="alert"`) — mutually exclusive via `sharesOk` / `sharesBad` |
| `افزودن شریک` button | `btn-outline btn-sm` default + hover (`--surface-2`); no pressed/opened state, no form attached |
| Row `ویرایش` button | `btn-ghost btn-icon btn-sm` default + hover; no target designed |
| Table row | default, hover (`tbody tr:hover td → --surface-2`) |
| Period `button.select` | default, `is-error` (red border + `0 0 0 3px var(--loss-soft)`) when the period overlaps; no open/popover state |
| Overlap alert | hidden ↔ visible (`.alert-err`); its quick-fix `شروع از ۱۴۰۵/۰۶/۰۱` is a static `btn-outline btn-sm` |
| Period-profit tile | number, or `—` while the period overlaps |
| Amount input | default, `is-warn` (orange border) as soon as `amt > UNDIST`, focus ring |
| Amount help | always visible; its number goes negative (`−۵٬۵۵۴٬۰۰۰`) in the exceed case |
| Over-distribution block | hidden ↔ visible; inside it the acknowledgement `button.check[role=checkbox]` has **off** (`aria-checked="false"`, empty box) and **on** (`.check.on`, `--navy` fill, white check, `aria-checked="true"`) |
| Preview table | recomputed live from amount × share; no empty/zero state designed |
| Submit button | `btn-primary` enabled · `btn-primary` + `disabled` (opacity .45, `not-allowed`) when blocked · `btn-danger` labelled `تقسیم با وجود کسری` once the over-distribution is acknowledged |
| Block-reason label | empty (`.muted`) or one of four sentences (`.neg.b`) |
| Screen | ready, empty, loading, error (`state` prop); `theme` light/dark exists as a prop but **no dark artboard was rendered for this screen** |
| Mobile | one static composition only (over-distribution, checkbox already on, danger button) |

No modal, drawer or overlay exists on this screen in either breakpoint: `Partners.dc.html` contains no `.dialog` and no `.overlay`.

---

## 4. Validation

Three rules, all evaluated in `renderVals()` on every render; there is no separate submit-time pass and no field-level error text.

```js
var sum = S.shares.reduce(function (a, b) { return a + b; }, 0), sharesOk = sum === 100;
var exceed = S.amt > UNDIST, left = UNDIST - S.amt;
var blocked = S.overlap || !sharesOk || S.amt <= 0 || (exceed && !S.ack);
```

| # | rule | severity | blocks save | message |
|---|---|---|---|---|
| V1 | `sum(shares) !== 100` | blocking | yes | the shares alert + `جمع سهم‌ها باید ۱۰۰٪ باشد` |
| V2 | chosen period overlaps a distributed period | blocking, **not overridable** | yes | the overlap alert + `دوره هم‌پوشانی دارد` |
| V3 | `amt > undistributed` | warning, overridable by an explicit acknowledgement | yes **until acknowledged** | the over-distribution warning + `برای ادامه، تأیید بالا را بزنید` |
| V4 | `amt <= 0` | blocking | yes | **no message designed** — the button is simply disabled and the reason label stays empty |

### V1 — shares must total ۱۰۰٪

The sum is shown in the table footer (green when 100, red otherwise) and one of these two blocks is rendered:

```
جمع سهم‌ها ۱۰۰٪ است.
```

```
جمع سهم‌ها ۹۵٪ است، نه ۱۰۰٪
تا جمع سهم‌ها دقیقاً ۱۰۰٪ نشود، تقسیم سود ثبت نمی‌شود. ۵٪ سهم بدون صاحب مانده است.
```

over-100 variant of the last sentence:

```
۵٪ بیشتر از کل است.
```

and the reason label next to the disabled button:

```
جمع سهم‌ها باید ۱۰۰٪ باشد
```

### V2 — an overlapping period is BLOCKED

`role="alert"`, red, ban icon; there is no override anywhere for this rule (`blocked` is `true` whenever `S.overlap`, regardless of the acknowledgement):

```
این دوره با تقسیم قبلی هم‌پوشانی دارد
بازه ۱۴۰۵/۰۵/۱۵ تا ۱۴۰۵/۰۵/۳۱ قبلاً در تقسیم «مرداد ۱۴۰۵» (ثبت‌شده در ۱۴۰۵/۰۶/۰۲) حساب شده است. سود هر روز فقط یک بار تقسیم می‌شود. تاریخ شروع را ۱۴۰۵/۰۶/۰۱ یا بعد از آن انتخاب کنید.
```

quick-fix button:

```
شروع از ۱۴۰۵/۰۶/۰۱
```

reason label:

```
دوره هم‌پوشانی دارد
```

The period control also takes `is-error`, and the period-profit tile shows `—` instead of a number.

### V3 — distributing more than the available profit needs an explicit confirmation

**The confirmation is an inline acknowledgement, not a modal dialog.** It is rendered inside the orange `.alert.alert-warn`, above the submit row, and consists of the warning text, one checkbox and the relabelled destructive submit button. Verbatim, desktop:

```
مبلغ ۵٬۵۵۴٬۰۰۰ تومان بیشتر از سود تقسیم‌نشده است
با این تقسیم، بیش از سود واقعی برداشت می‌شود و مانده سود تقسیم‌نشده منفی (−۵٬۵۵۴٬۰۰۰) می‌شود؛ یعنی بخشی از پول از سرمایه فروشگاه پرداخت شده است.
☐ می‌دانم؛ با وجود این تقسیم شود
```

While the box is unticked:

```
برای ادامه، تأیید بالا را بزنید
```

Once ticked, the submit button becomes `btn btn-danger` and reads:

```
تقسیم با وجود کسری
```

There is **no second button**: the designed flow has no `انصراف` / `بازگشت` pair, because there is no dialog to dismiss — the user unticks the box (which restores `ثبت تقسیم سود` + `btn-primary`) or lowers the amount (which removes the whole block, `onAmt` also resetting `ack` to `false`). See Open questions #1: the two-button confirmation dialog expected by the spec does not exist in these artboards, and inventing one is out of scope for this document.

Mobile wording of the same warning:

```
۵٬۵۵۴٬۰۰۰ تومان بیشتر از سود تقسیم‌نشده است.
☑ می‌دانم؛ با وجود این تقسیم شود
```

---

## 5. Logic

The domain formulas are in `../logic/formulas.md` §9 (profit distribution); the period net profit itself comes from §7 (P&L). Only screen behaviour is described here.

### State

```js
var UNDIST = 54446000;                     // carried-over 12,400,000 + شهریور net 42,046,000
this.state = {
  amt:     pr === 'exceed' ? 60000000 : 40000000,
  ack:     false,
  overlap: pr === 'overlap',
  shares:  pr === 'shares' ? [60, 25, 10] : [60, 25, 15]
};
```

`names` holds the three partners with their paid-to-date totals, positionally aligned with `shares`:

```js
var names = [['م', 'مالک فروشگاه', 70800000], ['س', 'شریک سرمایه‌گذار', 29500000], ['ه', 'شریک هنری', 17700000]];
```

### Available-to-distribute figure

`UNDIST` is a single number in the artboard, but it is the sum the sidebar card spells out:

```
undistributedTotal = carried-over undistributed (۱۲٬۴۰۰٬۰۰۰) + period net profit (۴۲٬۰۴۶٬۰۰۰) = ۵۴٬۴۴۶٬۰۰۰
```

- The carried-over figure is everything earned in past periods that was never distributed (the history shows each period's net profit exceeding what was actually paid out).
- The period net profit is the bottom line of the P&L for the chosen Jalali period — `../logic/formulas.md` §7, sample `۴۲٬۰۴۶٬۰۰۰` for شهریور ۱۴۰۵.
- Remaining after this distribution: `left = UNDIST - S.amt`, rendered through `fa()` so a negative remainder prints with the Persian minus sign `−`.

### Per-partner amount

```js
preview: names.map(function (n, i) {
  return { name: n[1], shT: faD(S.shares[i]) + '٪', amtT: fa(S.amt * S.shares[i] / 100) };
})
```

i.e. `amount × percent ÷ 100`, formatted by `fa()` — which applies `Math.round` at display time only. The stored share is an integer percent; the preview footer prints the raw `amtT`/`sumT`, so the column is not re-summed from the rounded rows.

### Overlap check

The artboard does not compute the overlap — `S.overlap` is set by the `preset` prop and the previous period is hardcoded in the message. What the message states the real check must compare:

- the **day range** of the candidate period (`۱۴۰۵/۰۵/۱۵ تا ۱۴۰۵/۰۶/۱۵`) against the day range of every previously recorded distribution (`مرداد ۱۴۰۵` = `۰۵/۰۱ تا ۰۵/۳۱`, recorded `۱۴۰۵/۰۶/۰۲`);
- the intersection is named back to the user (`بازه ۱۴۰۵/۰۵/۱۵ تا ۱۴۰۵/۰۵/۳۱`), so the check must return the overlapping sub-range, the colliding distribution's label and its record date;
- the rule stated in the copy is "each day's profit is distributed exactly once" (`سود هر روز فقط یک بار تقسیم می‌شود`), and the remedy offered is the first free day after the collision (`۱۴۰۵/۰۶/۰۱`).

While `overlap` is true the period profit tile shows `—`, the period control is `is-error`, and the amount/preview keep computing from `UNDIST` (they are not blanked).

### Confirm / cancel of the over-distribution

```js
exceed  = S.amt > UNDIST
blocked = S.overlap || !sharesOk || S.amt <= 0 || (exceed && !S.ack)
btnT    = exceed && S.ack ? 'تقسیم با وجود کسری' : 'ثبت تقسیم سود'
btnCls  = exceed && S.ack ? 'btn btn-danger'     : 'btn btn-primary'
toggleAck: function () { self.setState({ ack: !S.ack }); }
onAmt:     function (e) { self.setState({ amt: num(e.target.value), ack: false }); }
```

- **Confirm** = ticking the checkbox. That alone changes nothing but the gate: `blocked` drops to `false` (if nothing else blocks), the button turns destructive-red and is relabelled. The actual submit is still a separate press of that button. No POST, no success state and no toast is designed for this screen.
- **Cancel** = unticking the box (immediately re-blocks and restores the primary label) or editing the amount: `onAmt` resets `ack: false` on every keystroke, so lowering the amount below `UNDIST` removes the alert entirely, and re-raising it requires a fresh acknowledgement.
- `num()` (helpers.js) parses Persian, Arabic and Latin digits and strips everything else, so typing `۶۰٬۰۰۰٬۰۰۰` yields `60000000` and a text-only entry yields `0` (which makes `amt <= 0` block the save with no message).

### Formatting

`fa()` for money (Persian digits, `٬` thousands separator, `−` for negatives, no decimals, no unit — the unit is either a column header `(تومان)` or a `.sfx`), `faD()` for bare digit strings (percentages, dates), and `٪` is always a separate literal after the number. Every numeric cell and input carries `.num` / `.input-num` (`font-feature-settings:"tnum" 1`) so columns align.

---

## 6. Sample data used

Full list in `../data/sample-data.md` (§ Partners); `../logic/formulas.md` §9 has the same worked numbers.

### Partners and shares

| partner | initial | share | جمع دریافتی |
|---|---|---|---|
| مالک فروشگاه | م | ۶۰٪ | 70,800,000 |
| شریک سرمایه‌گذار | س | ۲۵٪ | 29,500,000 |
| شریک هنری | ه | ۱۵٪ | 17,700,000 |
| **جمع** | | **۶۰ + ۲۵ + ۱۵ = ۱۰۰٪** ✓ | **70,800,000 + 29,500,000 + 17,700,000 = 118,000,000** ✓ |

The footer total `۱۱۸٬۰۰۰٬۰۰۰` is hardcoded (`paidTotT: fa(118000000)`) and matches both the column sum above and the history table's `مبلغ تقسیم‌شده` total.

### Available to distribute

```
carried over (دوره‌های قبل)   12,400,000
+ شهریور ۱۴۰۵ net profit       42,046,000
= کل سود تقسیم‌نشده            54,446,000     ← UNDIST
```

### Preset `default` — amount 40,000,000 (nothing blocked)

```
مالک فروشگاه        40,000,000 × 60 ÷ 100 = 24,000,000
شریک سرمایه‌گذار     40,000,000 × 25 ÷ 100 = 10,000,000
شریک هنری           40,000,000 × 15 ÷ 100 =  6,000,000
                    ───────────────────────────────────
جمع                 24,000,000 + 10,000,000 + 6,000,000 = 40,000,000 ✓  (= مبلغ قابل تقسیم)
سهم‌ها               ۶۰ + ۲۵ + ۱۵ = ۱۰۰٪ ✓
باقی‌مانده            54,446,000 − 40,000,000 = 14,446,000  → «پس از ثبت، ۱۴٬۴۴۶٬۰۰۰ تومان تقسیم‌نشده باقی می‌ماند.»
```

### Preset `shares` (`Partners-Shares`) — shares 60/25/10, amount 40,000,000

```
سهم‌ها   ۶۰ + ۲۵ + ۱۰ = ۹۵٪   ≠ ۱۰۰٪  → red footer, warning alert, save disabled
diff    ۱۰۰ − ۹۵ = ۵٪         → «۵٪ سهم بدون صاحب مانده است.»
preview 24,000,000 / 10,000,000 / 4,000,000 = 38,000,000 — i.e. 2,000,000 of the 40,000,000 is unassigned,
        while the footer still prints جمع = ۴۰٬۰۰۰٬۰۰۰ (it echoes amtT, it does not re-sum the rows).
```

### Preset `overlap` (`Partners-Overlap`) — amount 40,000,000

Same numbers as `default`; the period becomes `۱۴۰۵/۰۵/۱۵ تا ۱۴۰۵/۰۶/۱۵`, the period-profit tile shows `—`, the total-undistributed tile still shows `۵۴٬۴۴۶٬۰۰۰`, and the save is blocked with no override.

### Preset `exceed` (`Partners-Exceed`) — amount 60,000,000

```
مالک فروشگاه        60,000,000 × 60 ÷ 100 = 36,000,000
شریک سرمایه‌گذار     60,000,000 × 25 ÷ 100 = 15,000,000
شریک هنری           60,000,000 × 15 ÷ 100 =  9,000,000
                    ───────────────────────────────────
جمع                 36,000,000 + 15,000,000 + 9,000,000 = 60,000,000 ✓
over by             60,000,000 − 54,446,000 =  5,554,000   → alert title «مبلغ ۵٬۵۵۴٬۰۰۰ تومان …»
باقی‌مانده            54,446,000 − 60,000,000 = −5,554,000   → «(−۵٬۵۵۴٬۰۰۰)» in the body and in the amount help
```

The mobile artboard shows exactly this case, with the acknowledgement already ticked and the danger button in the sticky bar.

### Distribution history (arithmetic check)

| period | net profit | distributed | ۶۰٪ | ۲۵٪ | ۱۵٪ | row check |
|---|---|---|---|---|---|---|
| مرداد ۱۴۰۵ | 38,900,000 | 35,000,000 | 21,000,000 | 8,750,000 | 5,250,000 | 21,000,000 + 8,750,000 + 5,250,000 = 35,000,000 ✓ |
| تیر ۱۴۰۵ | 33,200,000 | 30,000,000 | 18,000,000 | 7,500,000 | 4,500,000 | = 30,000,000 ✓ |
| خرداد ۱۴۰۵ | 30,500,000 | 28,000,000 | 16,800,000 | 7,000,000 | 4,200,000 | = 28,000,000 ✓ |
| اردیبهشت ۱۴۰۵ | 27,800,000 | 25,000,000 | 15,000,000 | 6,250,000 | 3,750,000 | = 25,000,000 ✓ |
| **جمع** | **130,400,000** | **118,000,000** | **70,800,000** | **29,500,000** | **17,700,000** | 70,800,000 + 29,500,000 + 17,700,000 = 118,000,000 ✓ |

Column checks: 38,900,000 + 33,200,000 + 30,500,000 + 27,800,000 = 130,400,000 ✓ · 35 + 30 + 28 + 25 = 118,000,000 ✓. Each partner's history total equals that partner's `جمع دریافتی` in the partners table ✓. Undistributed remainder of those four periods: 130,400,000 − 118,000,000 = 12,400,000 — exactly the `سود خالص تقسیم‌نشده دوره‌های قبل` figure ✓.

No real person's name or phone number appears: the partners are role labels (`مالک فروشگاه`, `شریک سرمایه‌گذار`, `شریک هنری`) and the avatars are their first letters.

---

## 7. Open questions for this screen

1. **The over-distribution confirmation is not a dialog.** The design confirms it inline (warning + `می‌دانم؛ با وجود این تقسیم شود` checkbox + the `تقسیم با وجود کسری` danger button). There is no modal, no overlay, and therefore no confirm/cancel button pair; `Partners.dc.html` contains neither `.dialog` nor `.overlay`. If a modal with two buttons is wanted (as on the order-detail cancel/refund dialogs), its copy and its buttons still have to be written — they do not exist here and are not invented in this document.
2. **No success path at all.** Pressing `ثبت تقسیم سود` has no designed result: no success state, no toast, no redirect, no new history row, no undo window. Compare record-sale, which has a full success screen.
3. **The period picker is undesigned.** The period is a `button.select` with a hardcoded label; no Jalali range popover was drawn for this screen (`monthGrid()` exists in `helpers.js` and is used elsewhere, e.g. the orders date-range board). Unresolved: month-only vs free day range, whether the default is the last complete Jalali month, and whether a period may cross a Jalali year boundary.
4. **The overlap quick-fix is not wired**, and only the "move the start later" remedy is designed. Undesigned: a candidate period that *contains* an older one, that is fully contained, that touches several old periods at once, or that extends past today.
5. **Editing partners has no form.** `افزودن شریک` and the per-row `ویرایش` button lead nowhere; there is no partner dialog, no fields (name, role, contact, join date), no deactivate/remove behaviour, and no rule for what happens to history when a partner is removed or a share is changed after distributions exist.
6. **Share editing has no commit affordance and no rounding rule.** The inputs mutate state directly; there is no save/apply/reset, no validation message for a single share of `۰٪` or `>۱۰۰٪`, and nothing defines whether fractional shares (`۳۳٫۳۳`) are allowed. `sum === 100` is an exact integer comparison, which would reject any set of thirds.
7. **Rounding of the split is undefined.** `amt × share ÷ 100` can be fractional; `fa()` rounds only for display, so the shown rows can differ from the shown total by a toman or two, and no remainder-allocation rule (largest remainder, assign to the majority partner, …) is specified. The preview footer echoes the entered amount rather than the sum of the rows, which hides the discrepancy — and, in the `shares` preset, hides a 2,000,000 gap.
8. **`amt <= 0` blocks silently.** The button is disabled with an empty reason label; no message was written for an empty or zero amount.
9. **Where `کل سود تقسیم‌نشده` comes from is not editable or auditable.** It is the constant `UNDIST` in the artboard. There is no drill-down to the periods that produced the 12,400,000, no settings field for an opening balance, and no handling of a **loss** period (negative period profit): the screen has no negative/zero state for the two tiles, and nothing says whether distribution is then blocked.
10. **Payout tracking does not exist.** A distribution records amounts only — no payment date, method, per-partner paid/unpaid flag, partial payments or receipt. `جمع دریافتی` reads as "received" but nothing in the app records an actual transfer, and the distribution has no relationship to the expenses screen.
11. **History rows have no actions.** No row detail, no edit, no delete/reverse, no print or export, and no pagination or period filter for when the list grows beyond four rows.
12. **Mobile is a read-mostly stub.** It omits the history table, the add/edit affordances, the editable shares, the period help, the overlap alert and the remaining-amount help; its checkbox is pre-ticked and its only button is the destructive one. Undesigned: what mobile shows when shares ≠ ۱۰۰٪ or the period overlaps, and whether a distribution may be submitted from mobile at all.
13. **No dark artboard** was rendered for this screen, although `theme` is a prop on both boards.
14. **Empty state leads nowhere.** `افزودن شریک` in the empty state is the same unattached button as in the card header; there is also no empty/first-run design for the distribution form or the history card (only the whole-screen empty state exists).
15. **Access control is not addressed.** Partner payouts are the most sensitive numbers in the app, but no permission, hiding or `🔒` treatment is applied here — unlike the internal-cost blocks on the record-sale screen.
