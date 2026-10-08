# 01 — خانه (Dashboard)

Route: `/` (undecided — see §7) · sidebar key `home` · page title in top bar: **خانه**

The landing screen. It answers four questions in one glance — how much sold today, how much came in this month, how much of that is profit, how many orders — and then spends most of its area on the one thing the shop owner cannot see anywhere else: **that every shipped order loses money**. The «اقتصاد ارسال این ماه» card is the reason this screen exists; it puts the ۱۸۰٬۰۰۰ charged to the customer next to the ۹۵٬۰۰۰ packaging plus the ۱۹۹٬۲۷۳ store-wide postage estimate and states the shortfall as a number, per order and per month. To its side sits the low-stock alert (products and packaging/materials in two tabs), and below both, the eight most recent orders with the profit of each. It is read-only: nothing on it is editable, the only real interaction is the tab switch in the low-stock card, and every other control is a link to another screen. The shell (sidebar, top bar, search, user menu) is documented in `00-app-shell.md` and is not repeated here.

Artboards: `Dashboard.dc.html` (1440 × 1440, light, ready), `Dashboard-Dark.dc.html` (1440 × 1440, `theme: dark`), `Dashboard-Empty.dc.html`, `Dashboard-Loading.dc.html`, `Dashboard-Error.dc.html` (each 1440 × 1100, via the `state` prop), `DashboardMobile.dc.html` (390 × 2000, ready), `DashboardMobile-Empty.dc.html`, `DashboardMobile-Loading.dc.html`, `DashboardMobile-Error.dc.html` (each 390 × 844).
Source: `src/Dashboard.dc.html`, `src/DashboardMobile.dc.html`. Props on both: `state` (`ready | empty | loading | error`), `theme` (`light | dark`), `h` (int). There is **no** `DashboardMobile-Dark` artboard.

Both source files **hand-write the shell instead of using the `[[PAGE:]]` / `[[MPAGE:]]` macros**, and both override the macro's `main` padding and gap — see §1 and §7. Neither uses the shared `[[STATES:]]` / `[[MSTATES:]]` macro either; the empty/loading/error boards on this screen are hand-authored per-block states, which is why §2 documents them in full rather than pointing at `build.py`.

---

## 1. Layout

### Desktop (1440 × 1440; empty/loading/error boards 1440 × 1100; fluid 1024–1600)

```
┌ sidebar 264 (RIGHT) ┬──────────────── content 1176 ─────────────────────────┐
│                     │ top bar 64: «خانه»                                    │
│                     ├───────────────────────────────────────────────────────┤
│                     │ main  padding 24 32 32 · flex column · gap 24         │
│                     │ ┌─ [0] header row 1112 ──────────────────────────────┐│
│                     │ │ سه‌شنبه، ۳۱ شهریور ۱۴۰۵  · آخرین به‌روزرسانی ۱۴:۰۵   ││
│                     │ │                     [شهریور ۱۴۰۵ ▾] [+ ثبت فروش]   ││
│                     │ └────────────────────────────────────────────────────┘│
│                     │ ┌─ [1] KPI grid: repeat(4, 1fr) gap 20 ──────────────┐│
│                     │ │ [263 ][263 ][263 ][263 ]   card .kpi, pad 18 20    ││
│                     │ └────────────────────────────────────────────────────┘│
│                     │ ┌─ [2] flex row, gap 20, align-items stretch ────────┐│
│                     │ │ ┌ economics card  grow → 692 ┐ ┌ low-stock 400 ──┐ ││
│                     │ │ │ card-h  16 20 + border      │ │ card-h (no rule)│ ││
│                     │ │ │ card-b  pad 20, gap 20      │ │ tabs 40 (pad 16)│ ││
│                     │ │ │  · 4-col figure grid gap 12 │ │ 4–5 rows, 11 0  │ ││
│                     │ │ │  · 2 bars, h 26, gap 10     │ │ each: name+qty  │ ││
│                     │ │ │  · alert-info pad 10 14     │ │  meter 6 + meta │ ││
│                     │ │ │                             │ │  + btn-sm 32    │ ││
│                     │ │ │                             │ │ footer link     │ ││
│                     │ │ └─────────────────────────────┘ └─────────────────┘ ││
│                     │ └────────────────────────────────────────────────────┘│
│                     │ ┌─ [3] recent-orders card 1112 ──────────────────────┐│
│                     │ │ card-h 16 20 · table: th 40, 8 × td 52 = 416       ││
│                     │ └────────────────────────────────────────────────────┘│
└─────────────────────┴───────────────────────────────────────────────────────┘
```

- Content width `1440 − 264 = 1176`; `main` inner width `1176 − 64 = 1112`.
- `main` is `padding: 24px 32px 32px; display: flex; flex-direction: column; gap: 24px`. **This is an override**: the `[[PAGE:]]` macro every other screen uses emits `padding: 24px 32px 40px; gap: 20px`. The content wrapper here also omits the macro's `position: relative`.
- KPI grid: `grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 20px` → `(1112 − 3×20) ÷ 4 = 263` per card. `.kpi` is `padding: 18px 20px; gap: 6px`; the number is `.t-kpi` (26/38, 700), the unit is `.kpi-u` (13, 500, `--text-3`).
- Row [2]: `display: flex; gap: 20px; align-items: stretch`. Economics card `flex-grow: 1; min-width: 0` → 692. Low-stock card `width: 400px; flex-shrink: 0`. Both are `display: flex; flex-direction: column` so they end at the same height.
- Economics figure grid: `repeat(4, minmax(0, 1fr)); gap: 12px`. The fourth cell (the result) is tinted `--loss-soft`, `border-radius: 10px; padding: 10px 12px; margin: -10px 0` — it bleeds 10px above and below the other three so the loss reads as a highlighted block.
- The two bars: each row is `label 64px` + a `flex-grow` track `height: 26px`. Row 1 has `gap: 0` (the shortfall is contiguous with the charged part); row 2 has `gap: 2px`. Segments are radiused only on their outer edge (`border-radius: 0 6px 6px 0` for the inline-start segment, `6px 0 0 6px` for the inline-end one) so the pair reads as one bar.
- Low-stock card: `card-h` has `border-bottom: 0; padding-bottom: 8px`; `.tabs` sits at `padding: 0 16px`; the list is `padding: 6px 20px 12px; flex-grow: 1`; each row is `padding: 11px 0` with a 1px `--border` bottom rule (**including the last row** — there is no `:last-child` reset, so the list ends on a rule); footer link block `padding: 0 20px 16px`.
- Recent-orders table is the standard `.tbl`: header 40px on `--surface-2`, rows 52px, money columns `.n.num`.
- The `h` prop only sets the artboard canvas height; nothing on the screen is anchored to the bottom.

### Block order, desktop (exact)

0. **Header row** — long date + last-updated caption on the inline start; month picker button + `ثبت فروش` primary link on the inline end. **Outside every `sc-if`**, so it is present in all four states.
1. **KPI row** — 4 cards (order below).
2. **اقتصاد ارسال این ماه** (grow) + **هشدار کمبود موجودی** (400) side by side.
3. **آخرین سفارش‌ها** — 8-row table.

### KPI card order (exact)

1. **فروش امروز** — icon `receipt` — value + `تومان` — caption: order count and pending count.
2. **درآمد این ماه** — icon `wallet` — value + `تومان` — caption: `.delta.pos` vs مرداد.
3. **سود خالص این ماه** — icon `chart` — value is `.num.pos` (green) + `تومان` — caption: `.delta.neg` vs مرداد + margin.
4. **سفارش‌های این ماه** — icon `package` — value + `سفارش` — caption: channel split.

Each card's label row is `.kpi-l` (13/600 `--text-2`) with the icon pushed to the inline end at 18px in `--text-3`. The grid itself is a `<section>` with `aria-label="شاخص‌های کلیدی"` (desktop only — the mobile KPI grid has no label).

### Economics card, inner order (exact)

1. Header: `h2.t-h2` title + caption line, and a `badge st-loss` on the inline end.
2. Four-figure grid: **دریافتی از مشتری → هزینه بسته‌بندی → هزینه پست (تخمینی) → نتیجه هر سفارش**. Each cell is: bold 12px label (`.muted2`), the per-order number at 20px (`.num.b`), a 12px qualifier line, then a 12px `جمع ماه: …` line.
3. Two-bar comparison (`role="img"` with an `aria-label`): row `دریافتی`, row `هزینه`.
4. `alert-info` with the break-even sentence and a `هزینه‌های ارسال` link.

### Low-stock card, inner order (exact)

1. Header: title + `badge st-warn` with the combined count.
2. Two tabs, `role="tablist"` / `role="tab"`: `محصولات` (count pill `۴`) and `بسته‌بندی و مواد` (count pill `۵`). Products is the default (`state.tab = 'p'`).
3. The list for the active tab: name (truncated with ellipsis) + quantity pill on one line, a 6px `.meter` below it, then a 12px meta line; an outline `btn-sm` action on the inline end of the row.
4. Footer link `مشاهده همه در محصولات و مواد` + `chevL`.

### Mobile (390 × 2000 ready; 390 × 844 for the three state boards)

```
┌──────────────────────── 390 ────────────────────────┐
│ MobileBar 56: [☰][logo] خانه            [search][av]│
├─────────────────────────────────────────────────────┤
│ main  padding 16 16 104 · flex column · gap 16       │
│  [0] سه‌شنبه، ۳۱ شهریور ۱۴۰۵        [شهریور ▾ 36]    │
│  [1] KPI 2×2 grid, gap 10 → 174 × ~74 each          │
│      ┌ فروش امروز ─┐ ┌ درآمد این ماه ┐              │
│      └─────────────┘ └───────────────┘              │
│      ┌ سود خالص… ──┐ ┌ سفارش‌های… ───┐              │
│      └─────────────┘ └───────────────┘              │
│  [2] اقتصاد ارسال card, pad 16, gap 14              │
│      · 5 .sl rows + .sep  (statement form)          │
│      · 2 bars h 14 + legend                         │
│  [3] هشدار کمبود موجودی card                        │
│      · tabs h 44 (pad 12) · 4 rows, pad 12 0        │
│  [4] آخرین سفارش‌ها card                            │
│      · 8 link blocks, pad 12 16, border-top each    │
├─────────────────────────────────────────────────────┤
│ bottom action bar (abs, bottom 0) pad 12 16 20      │
│  [+ ثبت فروش]  btn-primary btn-lg, width 100%       │
└─────────────────────────────────────────────────────┘
```

- `main` is `padding: 16px 16px 104px; display: flex; flex-direction: column; gap: 16px`. **Also an override**: the `[[MPAGE:]]` macro emits `padding: 14px 16px 100px; gap: 12px`. The 104px bottom padding clears the action bar.
- Content width `390 − 32 = 358`; KPI grid `repeat(2, minmax(0,1fr)); gap: 10px` → `(358 − 10) ÷ 2 = 174` per card. Mini-KPI cards are `padding: 12px 14px; gap: 2px`; the number is 18px `.num.b` (not `.t-kpi`).
- Economics card: `padding: 16px; gap: 14px`. The four-figure grid of the desktop becomes five `.sl` statement rows (13.5/22, label on the inline start, value on the inline end) plus a `.sep`; the result row is `.sl.total` (15/700, value 20px) on `--loss-soft` with `margin: 0 -8px; padding: 8px; border-radius: 8px`, so it bleeds to the card edge.
- Mobile bars are 14px tall and carry **no in-bar labels**; a legend row with four 8×8 swatch chips replaces them.
- Low-stock card: tabs are 44px tall (touch target), rows are `padding: 12px 0` with a bottom rule except the last, and each row is just name + `حداقل …` sub-line + quantity pill. **No meter, no category, no per-row action button, and no footer link.**
- Recent orders: each order is a full-width `<a>` block, `padding: 12px 16px`, `border-top: 1px solid var(--border)` on every block (including the first, so a rule sits directly under the card header), three stacked lines.
- Bottom action bar: `position: absolute; left: 0; right: 0; bottom: 0; padding: 12px 16px 20px; background: var(--surface); border-top: 1px solid var(--border)`. It anchors to `.rs` (which is `position: relative; overflow: hidden`), i.e. to the bottom of the `h` canvas — in the 2000px ready artboard it sits 2000px down. In the app this is a fixed bar; see §7.
- All mobile touch targets are ≥ 44px (tabs 44, action button `btn-lg` 48, month button is the exception at 36 — see §7).

### Block order, mobile (exact)

0. Header row (date + month button) — outside every `sc-if`.
1. KPI 2×2 grid, same four metrics in the same order.
2. اقتصاد ارسال این ماه.
3. هشدار کمبود موجودی (products tab only).
4. آخرین سفارش‌ها.
5. Bottom action bar (outside every `sc-if`).

---

## 2. Copy (verbatim)

### Header row

| Slot | Desktop | Mobile |
|---|---|---|
| long date | `سه‌شنبه، ۳۱ شهریور ۱۴۰۵` | `سه‌شنبه، ۳۱ شهریور ۱۴۰۵` |
| last-updated caption | `· آخرین به‌روزرسانی ۱۴:۰۵` | — |
| month picker button (`cal` + `chevD`) | `شهریور ۱۴۰۵` | `شهریور` |
| primary action | `ثبت فروش` (`plus` icon, → `RecordSale.dc.html`) | in the bottom bar: `ثبت فروش` (→ `RecordSaleMobile.dc.html`) |

The desktop caption's leading `·` is part of the string, inside the `.t-sm.muted` span.

### KPI cards — ready state

| # | Label (desktop) | Value | Unit | Caption |
|---|---|---|---|---|
| 1 | `فروش امروز` | `۲٬۷۹۰٬۰۰۰` | `تومان` | `۳ سفارش · ۱ در انتظار پرداخت` |
| 2 | `درآمد این ماه` | `۱۸۶٬۴۲۰٬۰۰۰` | `تومان` | `۱۲٪` (in `.delta.pos`, `up` icon) + ` نسبت به مرداد` |
| 3 | `سود خالص این ماه` | `۴۲٬۰۴۶٬۰۰۰` | `تومان` | `۳٪` (in `.delta.neg`, `down` icon) + ` نسبت به مرداد · حاشیه سود ۲۳٪` |
| 4 | `سفارش‌های این ماه` | `۸۷` | `سفارش` | `۶۴ ارسالی · ۸ عمده · ۱۵ حضوری` |

Mobile mini-cards — the labels for cards 1–4 are identical (`فروش امروز`, `درآمد این ماه`, `سود خالص این ماه`, `سفارش‌های این ماه`), the values are identical, and the captions are shortened:

| # | Mobile caption |
|---|---|
| 1 | `تومان · ۳ سفارش` |
| 2 | `۱۲٪` (in `.delta.pos`, `up` 12px) + ` تومان` |
| 3 | `۴٪` (in `.delta.neg`, `down` 12px) + ` تومان` |
| 4 | `۶۴ ارسالی` |

The mobile delta on card 3 reads **۴٪** where the desktop reads **۳٪** — see §7.

### اقتصاد ارسال این ماه — desktop

| Slot | String |
|---|---|
| card title | `اقتصاد ارسال این ماه` |
| card caption | `۶۴ سفارش ارسالی وب‌سایت و اینستاگرام · شهریور ۱۴۰۵` |
| header badge (`badge st-loss`) | `زیان‌ده` |

Figure grid, in order:

| # | Label | Per-order value | Qualifier line | Month line |
|---|---|---|---|---|
| 1 | `دریافتی از مشتری` | `۱۸۰٬۰۰۰` | `تومان برای هر سفارش` | `جمع ماه: ۱۱٬۵۲۰٬۰۰۰` |
| 2 | `هزینه بسته‌بندی` | `۹۵٬۰۰۰` | `تومان برای هر سفارش` | `جمع ماه: ۶٬۰۸۰٬۰۰۰` |
| 3 | `هزینه پست (تخمینی)` | `۱۹۹٬۲۷۳` | `جمع پرداختی ÷ جمع سفارش‌ها` | `جمع ماه: ۱۲٬۷۵۳٬۴۷۲` |
| 4 | `نتیجه هر سفارش` | `−۱۱۴٬۲۷۳` | `تومان زیان` | `جمع ماه: −۷٬۳۱۳٬۴۷۲` |

Cell 3's qualifier is the mandated postage caption «جمع پرداختی ÷ جمع سفارش‌ها» — it must appear wherever the estimate is shown. Cell 4's label, value, qualifier and month line are all `.neg`; the minus is `−` (U+2212), emitted by `fa()`.

Bars:

| Slot | String |
|---|---|
| `role="img"` label on the bar group | `مقایسه دریافتی ۱۸۰ هزار تومان با هزینه ۲۹۴ هزار تومان برای هر سفارش` |
| bar 1 row label | `دریافتی` |
| bar 1, filled segment (61%, `--bar-a`, white text) | `۱۸۰٬۰۰۰` |
| bar 1, hatched segment (39%, `.hatch`, `--loss` text) | `کسری ۱۱۴٬۲۷۳` |
| bar 2 row label | `هزینه` |
| bar 2, first segment (32%, `--bar-b`, `--text`) | `بسته‌بندی ۹۵٬۰۰۰` |
| bar 2, second segment (68%, `--bar-c`, white text) | `پست ۱۹۹٬۲۷۳` |

Break-even alert (`alert-info`, `info` icon), the two amounts in `<b class="num">`:

```
برای سربه‌سر شدن، هزینه ارسال دریافتی باید دست‌کم ۲۹۴٬۲۷۳ تومان باشد، یا هزینه بسته‌بندی و پست ۱۱۴٬۲۷۳ تومان کمتر شود.
```

Alert link (nowrap, on the inline end): `هزینه‌های ارسال`

### اقتصاد ارسال این ماه — mobile

| Slot | String |
|---|---|
| card title | `اقتصاد ارسال این ماه` |
| card caption | `۶۴ سفارش ارسالی` |
| header badge | `زیان‌ده` |
| `role="img"` label on the bar group | `دریافتی ۱۸۰ هزار در برابر هزینه ۲۹۴ هزار تومان` |

Statement rows, in order:

| # | Label | Value |
|---|---|---|
| 1 | `دریافتی از مشتری` | `۱۸۰٬۰۰۰ تومان` |
| 2 | `هزینه بسته‌بندی` | `−۹۵٬۰۰۰ تومان` |
| 3 | `هزینه پست (تخمینی)` | `−۱۹۹٬۲۷۳ تومان` |
| — | `.sep` | |
| 4 | `نتیجه هر سفارش` (`.neg`, `.sl.total`) | `−۱۱۴٬۲۷۳ تومان` (`.neg`) |
| 5 | `جمع زیان ماه` (`.muted`) | `−۷٬۳۱۳٬۴۷۲ تومان` (`.neg.b`) |

Legend row (four items, `t-cap muted`): `دریافتی` (`--bar-a` swatch) · `بسته‌بندی` (`--bar-b`) · `پست` (`--bar-c`) · `▨ کسری` (in `.neg`; the `▨` U+25A8 glyph stands in for the hatch pattern).

Mobile drops the «جمع پرداختی ÷ جمع سفارش‌ها» caption, the three `جمع ماه:` subtotals, the in-bar value labels and the break-even alert — see §7.

### هشدار کمبود موجودی

| Slot | Desktop | Mobile |
|---|---|---|
| card title | `هشدار کمبود موجودی` | `هشدار کمبود موجودی` |
| header badge (`badge st-warn`) | `۹ مورد` | `۹` |
| tab 1 label + `.cnt` | `محصولات` `۴` | `محصولات` `۴` |
| tab 2 label + `.cnt` | `بسته‌بندی و مواد` `۵` | `بسته‌بندی و مواد` `۵` |
| footer link | `مشاهده همه در محصولات و مواد` + `chevL` | — |

**Tab 1 — محصولات** (4 rows, in this order):

| # | Name | Quantity pill | class | meter | Meta line | Action |
|---|---|---|---|---|---|---|
| 1 | `کاست آلبوم اول` | `ناموجود` | `stock out` | 2% `--loss` | `کاست · حداقل ۵ عدد` | `تولید` |
| 2 | `وینیل نسخه رنگی` | `۲ عدد` | `stock out` | 40% `--loss` | `وینیل · حداقل ۳ عدد` | `خرید` |
| 3 | `کاست نسخه محدود` | `۳ عدد` | `stock low` | 60% `--warn` | `کاست · حداقل ۵ عدد` | `تولید` |
| 4 | `آینه لوگو گرد` | `۴ عدد` | `stock low` | 80% `--warn` | `آینه · حداقل ۵ عدد` | `خرید` |

**Tab 2 — بسته‌بندی و مواد** (5 rows, in this order):

| # | Name | Quantity pill | class | meter | Meta line | Action |
|---|---|---|---|---|---|---|
| 1 | `جعبه وینیل` | `۸ عدد` | `stock out` | 40% `--loss` | `بسته‌بندی · حداقل ۲۰ · حدود ۵ روز` | `خرید` |
| 2 | `نوار چسب لوگودار` | `۲ رول` | `stock out` | 40% `--loss` | `بسته‌بندی · حداقل ۵ رول` | `خرید` |
| 3 | `پاکت حباب‌دار کوچک` | `۱۵ عدد` | `stock low` | 38% `--warn` | `بسته‌بندی · حداقل ۴۰` | `خرید` |
| 4 | `تی‌شرت خام مشکی L` | `۶ عدد` | `stock low` | 60% `--warn` | `ماده اولیه · حداقل ۱۰` | `خرید` |
| 5 | `کاغذ پرکننده` | `۱ بسته` | `stock low` | 33% `--warn` | `بسته‌بندی · حداقل ۳ بسته` | `خرید` |

The meta lines are inconsistent by design-accident: rows carry the unit (`عدد`, `رول`, `بسته`) in some and not others, one row carries an unexplained `· حدود ۵ روز`, and `کاغذ پرکننده` is described in `بسته` although its unit in `MATERIALS` is `کیلوگرم` — see §7.

Mobile shows only the products tab, with the category dropped from the meta line:

| # | Name | Sub-line | Quantity pill |
|---|---|---|---|
| 1 | `کاست آلبوم اول` | `حداقل ۵ عدد` | `ناموجود` (`stock out`) |
| 2 | `وینیل نسخه رنگی` | `حداقل ۳ عدد` | `۲ عدد` (`stock out`) |
| 3 | `کاست نسخه محدود` | `حداقل ۵ عدد` | `۳ عدد` (`stock low`) |
| 4 | `آینه لوگو گرد` | `حداقل ۵ عدد` | `۴ عدد` (`stock low`) |

### آخرین سفارش‌ها

| Slot | Desktop | Mobile |
|---|---|---|
| card title | `آخرین سفارش‌ها` | `آخرین سفارش‌ها` |
| header link | `همه سفارش‌ها` + `chevL` (→ `Orders.dc.html`) | `همه` (→ `OrdersMobile.dc.html`) |

Desktop column headers, in order (the money columns carry the unit, per `design-system.md` §5):

| # | Header | Alignment |
|---|---|---|
| 1 | `شماره فاکتور` | start |
| 2 | `تاریخ` | start |
| 3 | `کانال` | start |
| 4 | `مشتری` | start |
| 5 | `وضعیت` | start |
| 6 | `مبلغ کل (تومان)` | `.n` |
| 7 | `سود (تومان)` | `.n` |

The 8 rows, verbatim as rendered by `orderRows(8)`:

| شماره فاکتور | تاریخ | کانال | مشتری | وضعیت | مبلغ کل (تومان) | سود (تومان) |
|---|---|---|---|---|---|---|
| `INV-000041` | `۱۴۰۵/۰۶/۳۱ · ۱۳:۴۲` | `اینستاگرام` | `علی ر.` | `تکمیل‌شده` | `۹۵۰٬۰۰۰` | `۳۲۷٬۷۲۷` |
| `INV-000040` | `۱۴۰۵/۰۶/۳۱ · ۱۱:۰۵` | `حضوری` | `مشتری حضوری` | `تکمیل‌شده` | `۱٬۰۴۰٬۰۰۰` | `۵۹۲٬۰۰۰` |
| `INV-000039` | `۱۴۰۵/۰۶/۳۱ · ۰۹:۲۰` | `اینستاگرام` | `رها س.` | `در انتظار` | `۸۰۰٬۰۰۰` | `۲۱۵٬۷۲۷` |
| `INV-000038` | `۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴` | `وب‌سایت` | `نگار ک.` | `پرداخت‌شده` | `۳٬۱۳۰٬۰۰۰` | `۱٬۱۸۹٬۷۲۷` |
| `INV-000037` | `۱۴۰۵/۰۶/۳۰ · ۱۲:۱۰` | `عمده‌فروشی` | `فروشگاه نوای شهر` | `تکمیل‌شده` | `۴٬۳۰۰٬۰۰۰` | `۲٬۲۹۵٬۷۲۷` |
| `INV-000036` | `۱۴۰۵/۰۶/۲۹ · ۱۸:۳۷` | `وب‌سایت` | `مهدی ت.` | `لغوشده` | `۱٬۴۳۰٬۰۰۰` | `—` |
| `INV-000035` | `۱۴۰۵/۰۶/۲۹ · ۱۰:۰۲` | `اینستاگرام` | `پریا ن.` | `مرجوعی` | `۱٬۰۷۰٬۰۰۰` | `−۲۹۴٬۲۷۳` |
| `INV-000034` | `۱۴۰۵/۰۶/۲۸ · ۱۹:۱۵` | `سایر` | `—` | `پیش‌نویس` | `۴۸۰٬۰۰۰` | `—` |

Channel names come from `CH` (`وب‌سایت`، `اینستاگرام`، `عمده‌فروشی`، `حضوری`، `سایر`) and status names from `ST` (`پیش‌نویس`، `در انتظار`، `پرداخت‌شده`، `تکمیل‌شده`، `لغوشده`، `مرجوعی`) — never re-typed per screen. `INV-000034`'s customer is the literal em-dash string `—` stored in `ORDERS`, not a missing value.

Mobile order block, three lines per order:

1. `{inv}` in `.inv` (monospace, LTR isolate) + the status badge.
2. Channel chip + `{cust}` on one side, the total on the other (number only, no unit).
3. `{dt}` (`۱۴۰۵/۰۶/۳۱ · ۱۳:۴۲`) on one side, the profit label on the other.

The profit label is `profitT` from `helpers.js`: `سود ۳۲۷٬۷۲۷` when a profit exists, and `سود: —` when it is null. The two forms punctuate differently (no colon vs colon) and the refunded row reads `سود −۲۹۴٬۲۷۳` — see §7. All eight blocks link to `OrderDetailMobile.dc.html`.

### Empty state — desktop (`Dashboard-Empty`)

Welcome banner (`alert-info`, `info` icon):

| Slot | String |
|---|---|
| `.a-t` | `به مدیریت ربل شاپ خوش آمدید` |
| body | `برای دیدن گزارش‌ها، ابتدا محصولات و کیت‌های بسته‌بندی را تعریف کنید و سپس اولین فروش را ثبت کنید.` |
| button (`btn-outline btn-sm`) | `تعریف محصولات` |

The four KPI cards keep their labels and icons; every value is `۰` in `.num.nil` with the same unit, and the captions become:

| # | Label | Value | Caption |
|---|---|---|---|
| 1 | `فروش امروز` | `۰ تومان` | `هنوز فروشی ثبت نشده` |
| 2 | `درآمد این ماه` | `۰ تومان` | `—` |
| 3 | `سود خالص این ماه` | `۰ تومان` | `—` |
| 4 | `سفارش‌های این ماه` | `۰ سفارش` | `—` |

Economics card — title `اقتصاد ارسال این ماه`, then an `.empty` block (icon `truck`, **mirrored**):

```
هنوز سفارش ارسالی ندارید
پس از ثبت اولین سفارش وب‌سایت یا اینستاگرام، این‌جا می‌بینید هزینه ارسال دریافتی چقدر از هزینه بسته‌بندی و پست را پوشش می‌دهد.
```

Low-stock card — title `هشدار کمبود موجودی`, then an `.empty` block (icon `ok`, tile tinted `--profit-soft` / `--profit`):

```
کمبودی وجود ندارد
وقتی موجودی کالا یا بسته‌بندی به حداقل تعیین‌شده برسد، این‌جا هشدار می‌گیرید.
```

Orders card — title `آخرین سفارش‌ها`, then an `.empty` block at `padding: 56px 24px` (icon `receipt`):

```
هنوز سفارشی ثبت نشده
اولین فروش را ثبت کنید تا فهرست سفارش‌ها و سود هر کدام این‌جا نمایش داده شود.
```

with a primary CTA `ثبت اولین فروش` (`plus` icon, → `RecordSale.dc.html`).

### Empty state — mobile (`DashboardMobile-Empty`)

No welcome banner. Four mini cards, all `۰` in `.num.b.nil`, with **shortened labels** (cards 3 and 4 differ from the ready state):

| # | Label | Value |
|---|---|---|
| 1 | `فروش امروز` | `۰` |
| 2 | `درآمد این ماه` | `۰` |
| 3 | `سود خالص` | `۰` |
| 4 | `سفارش‌ها` | `۰` |

Then one `.empty` card at `padding: 36px 20px` (icon `receipt`):

```
هنوز فروشی ثبت نشده
پس از ثبت اولین فروش، درآمد، سود و اقتصاد ارسال این‌جا نمایش داده می‌شود.
```

CTA `ثبت اولین فروش` (`btn-primary btn-lg`, `plus` 18, → `RecordSaleMobile.dc.html`).

### Error state — desktop (`Dashboard-Error`)

Banner, `alert-err` with `role="alert"` and the `cloudoff` icon:

| Slot | String |
|---|---|
| `.a-t` | `اطلاعات داشبورد بارگذاری نشد` |
| body | `اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید. اگر مشکل ادامه داشت، اتصال اینترنت را بررسی کنید.` |
| caption line | `کد خطا: ` + `NET_TIMEOUT` (in `.ltr`) + ` · آخرین بارگذاری موفق: امروز ۱۰:۴۲` |
| button (`btn-outline btn-sm`, `refresh` 14) | `تلاش دوباره` |

The four KPI cards keep their labels and icons; every value is the em-dash `—` in `.t-kpi.nil` and every caption is `در دسترس نیست`.

Everything below collapses into one card with an `.empty` block at `padding: 72px 24px` (icon `tri`, tile tinted `--loss-soft` / `--loss`):

```
نمودارها و فهرست سفارش‌ها نمایش داده نمی‌شوند
پس از برقراری اتصال، این بخش خودکار به‌روز می‌شود. ثبت فروش جدید همچنان در دسترس است.
```

Buttons: `تلاش دوباره` (`btn-outline`, `refresh` 16) and `رفتن به ثبت فروش` (`btn-ghost`, → `RecordSale.dc.html`).

### Error state — mobile (`DashboardMobile-Error`)

One `.empty` card at `padding: 44px 20px` (icon `cloudoff`, tile tinted `--loss-soft` / `--loss`):

```
اطلاعات بارگذاری نشد
اتصال به سرور برقرار نشد. داده‌های شما سالم است.
```

Button `تلاش دوباره` (`btn-outline btn-lg`, `refresh` 18), then a caption `آخرین بارگذاری موفق: امروز ۱۰:۴۲`. **No error code, no `role="alert"`, and no link to ثبت فروش** (the bottom action bar covers that).

### Loading state

Skeletons only, no copy. Desktop: `<section aria-busy="true" aria-label="در حال بارگذاری">` — that label is the shell-level string shared by every screen (`00-app-shell.md` §2). Mobile has `aria-busy="true"` with **no** `aria-label`.

---

## 3. Interactive states designed

| element | states |
|---|---|
| Low-stock tabs (desktop) | `محصولات` `on` (default) ⇄ `بسته‌بندی و مواد` `on` — the **only** live interaction on the screen; `role="tablist"` / `role="tab"`, red underline on `.tab.on`, `.cnt` pill flips to `--red-soft` / `--red` |
| Low-stock tabs (mobile) | `محصولات` drawn `on`, second tab drawn resting — **inert**, no handler, no second list |
| Low-stock row action (`تولید` / `خرید`) | default + hover; `btn-outline btn-sm`, an `<a href="#">` with no destination |
| Low-stock quantity pill | `stock` (neutral) · `stock.low` (`--warn-soft`) · `stock.out` (`--loss-soft`) — all three classes appear; see §7 for how they are assigned |
| Low-stock meter | one filled bar, colour `--loss` or `--warn` matching the pill |
| Month picker button | one state only — resting. No open popover artboard on this screen (the Jalali range picker is designed on `Orders-DateRange`) |
| `ثبت فروش` button | default + hover (`btn-primary`) |
| Recent-orders table row | default · hover (`--surface-2`, from `.tbl`) |
| Invoice link `.inv` | link to `OrderDetail.dc.html` (desktop) / whole block links to `OrderDetailMobile.dc.html` (mobile) |
| Status badge | all six `ST` variants render in the sample: `st-done`, `st-pending`, `st-paid`, `st-cancel`, `st-refund`, `st-draft` |
| Channel chip | all five `CH` variants render: `ch-web`, `ch-insta`, `ch-wholesale`, `ch-inperson`, `ch-other` |
| Profit cell | `.pos` (green) · `.neg` (red, with `−`) · `.nil` (`—`, for draft and cancelled) |
| Economics card | one state only — the loss case. No break-even and no profitable variant is drawn |
| Screen | ready · empty · loading · error · dark (desktop only) |
| Header row | identical in all four states (it is outside every `sc-if`) |

Focus rings come from the shared component classes (`box-shadow: 0 0 0 3px var(--ring)`); nothing on this screen conveys state by colour alone — every loss carries a `−` and a word, every stock pill carries its quantity or `ناموجود`.

---

## 4. Validation

None on this screen. The dashboard is entirely read-only: it has no inputs, no form controls, no submit, and therefore no validation rules or error messages of the `../logic/formulas.md`-driven kind. The only "error" here is the data-load failure documented in §2.

---

## 5. Logic

All arithmetic is cross-referenced, not restated: order profit is `../logic/formulas.md` §1, the postage estimate is §2, the P&L that produces the profit KPI is §7, and the stock-by-status rules that decide which orders count are §6. Every number below is hardcoded in the artboard — `Dashboard.dc.html`'s `renderVals()` computes nothing except which low-stock list to show — so what follows is the derivation the implementation must supply.

### Period

Every KPI except the first is scoped to the month in the header's month picker (`شهریور ۱۴۰۵`); the first is scoped to today (`۱۴۰۵/۰۶/۳۱`). Neither scope is stated in the UI beyond the labels «امروز» / «این ماه», and the month picker is not wired to anything — see §7.

### KPI 1 — فروش امروز

```
todaysSales = Σ customerTotal over orders where date == today AND status != 'draft'
```
`customerTotal` is `../logic/formulas.md` §1. Caption: `<count> سفارش · <pendingCount> در انتظار پرداخت`, where `pendingCount` counts status `در انتظار` only. Drafts are excluded from the amount; whether they are excluded from the count is not stated (in the sample there is no draft dated today, so the artboard cannot tell us) — see §7.

### KPI 2 — درآمد این ماه

```
monthRevenue = itemsRevenue + shippingRevenue      // = totalRevenue, ../logic/formulas.md §7
```
i.e. the customer-facing total of every non-draft order in the month, shipping charges included. The `۱۲٪` delta is a month-over-month comparison against مرداد that has no formula and no source figure — see §7.

### KPI 3 — سود خالص این ماه

This is **net** profit — the bottom line of the P&L in `../logic/formulas.md` §7, not the sum of per-order profits. It is `grossProfit` minus postage variance, refund/cancel losses, waste and operating expenses, so it is strictly smaller than `Σ order.profit`. The caption's `حاشیه سود ۲۳٪` is `netProfit ÷ totalRevenue`, and the `۳٪` delta is again an undocumented comparison to مرداد.

### KPI 4 — سفارش‌های این ماه

```
monthOrders = count of orders in the month
caption     = `<shipped> ارسالی · <wholesale> عمده · <inPerson> حضوری`
```
`ارسالی` here means **وب‌سایت + اینستاگرام only** (`۳۴ + ۳۰ = ۶۴`), even though عمده‌فروشی also ships and also carries postage. The count `۸۷` includes drafts, cancellations and refunds, which the money KPIs exclude — see §7.

### اقتصاد ارسال این ماه

The card is a single-rate model: one charged amount, one kit cost, one postage estimate, multiplied by the shipped-order count.

```
n         = shippedOrders                       // 64 = web + Instagram
charged   = channelDefaults.web.ship            // 180,000, same for insta
packaging = kit('جعبه استاندارد').cost          // 95,000, ../logic/formulas.md §5
postage   = POSTAGE_EST                         // 199,273, ../logic/formulas.md §2
perOrder  = charged - packaging - postage        // −114,273
month     = perOrder * n                        // −7,313,472
```

and each `جمع ماه:` line is the corresponding per-order figure × `n`. The header badge is `زیان‌ده` whenever `perOrder < 0`; no other badge value is designed.

- `postage` is the **one store-wide estimate**, `Σ paid ÷ Σ orders` over the last 3 postage payments (`../logic/formulas.md` §2) — never a per-channel amount, never the mean of the three per-payment rates. The caption «جمع پرداختی ÷ جمع سفارش‌ها» must be rendered with it, always.
- Channels only switch postage **on/off**; وب‌سایت، اینستاگرام، عمده‌فروشی = on، حضوری، سایر = off. That is why the card's population is "shipped" orders and why حضوری orders are absent from it.
- Bar widths are percentages of the cost side, not of a shared maximum:
  ```
  bar1 = [ charged / (packaging + postage), shortfall / (packaging + postage) ]   → 61% / 39%
  bar2 = [ packaging / (packaging + postage), postage / (packaging + postage) ]   → 32% / 68%
  ```
  Both bars therefore sum to 100% of `۲۹۴٬۲۷۳`, which is what makes the hatched shortfall legible.
- Break-even copy: `دست‌کم packaging + postage تومان` on the revenue side, or `perOrder` less cost — i.e. the same number said twice, once as a target and once as a gap.

### هشدار کمبود موجودی

The rule, from `helpers.js`:

```js
function stockCls(stock, min) { return stock === 0 ? 'stock out' : (min && stock <= min ? 'stock low' : 'stock'); }
```

So an item is "low" when **`stock <= min`** (inclusive — `۳ ≤ ۳` is low), "out" when `stock === 0`, and a `min` of `0`/`null` opts an item out of alerting entirely (which is how the deactivated `پوستر تور ۱۴۰۳` and every `type: 'service'` material stay off the list). Two lists:

- **محصولات** — over `CATALOG`, active items only.
- **بسته‌بندی و مواد** — over `MATERIALS`, `type: 'goods'` only (services have `stock: null`). It spans both `use` values: `بسته‌بندی` rows are labelled `بسته‌بندی` and `تولید` rows are labelled `ماده اولیه`.

Badge count = products + materials. The meter is `min(100, stock ÷ min × 100)`, coloured to match the pill. The artboard's actual pill classes and percentages do **not** follow from `stockCls()` — `وینیل نسخه رنگی` (stock 2, min 3) is drawn `stock out`, and one material is missing from the list altogether; see §6 and §7.

### آخرین سفارش‌ها

```js
function orderRows(limit) { return ORDERS.slice(0, limit || ORDERS.length).map(...); }
```
called as `orderRows(8)`. `ORDERS` is **stored newest-first** and the screen slices it — there is no sort in the code. The intended ordering is `date DESC, time DESC` (the sample satisfies it: `۰۶/۳۱ ۱۳:۴۲` → `۰۶/۲۸ ۱۹:۱۵`), and that must be implemented explicitly.

Per row, the same helper decides the profit presentation:

```js
var pc = o[7] === null ? 'nil' : (o[7] < 0 ? 'neg' : 'pos');
...
profit: o[7] === null ? '—' : fa(o[7]),
```

so `null` profit renders as `—` in `.nil` — which is what draft and cancelled orders get. **Drafts appear in this list** (`INV-000034`, `پیش‌نویس`) even though they are excluded from KPIs 1–3, and so do cancelled and refunded orders. The list is "recent activity", not "recent sales".

### Formatting helpers (all from `helpers.js`, no per-screen re-implementation)

```js
function fa(n)  { /* Persian digits, ٬ (U+066C) group separator, − (U+2212) for negatives, — for null/NaN */ }
function faT(n) { return fa(n) + ' تومان'; }
function faD(s) { /* Latin→Persian digits only, no grouping — used for dates and times */ }
```

- Money is integer Rial (shown in Rial or Toman; Toman has at most one decimal), Persian tabular digits, `٬` thousands separator; the unit sits in the table header, in the `.kpi-u` span or in the `.sl .v` value, never inside the number.
- Losses always carry `−` (U+2212) **and** a word (`زیان`, `کسری`, `زیان‌ده`); never colour alone.
- Dates are Jalali only — `faD('1405/06/31')` → `۱۴۰۵/۰۶/۳۱`, with time as `۱۴۰۵/۰۶/۳۱ · ۱۳:۴۲`, long form `سه‌شنبه، ۳۱ شهریور ۱۴۰۵`. No Gregorian date appears anywhere; convert at the data layer.
- Percentages use the Persian decimal `٫` and a trailing `٪` (`۲۲٫۶٪`); this screen rounds to a whole number (`۲۳٪`, `۱۲٪`, `۳٪`).

### What the artboard's JS actually does

```js
constructor(p) { super(p); this.state = { tab: 'p' }; }
...
tabP: tab === 'p' ? 'on' : '', tabM: tab === 'm' ? 'on' : '',
showP: function () { self.setState({ tab: 'p' }); }, showM: function () { self.setState({ tab: 'm' }); },
lowList: tab === 'p' ? P : M,
orders: orderRows(8)
```

`P` and `M` are literal arrays of display strings (name, pill text, pill class, meter percent, meter colour, meta, action label) — not derived from `CATALOG` / `MATERIALS`. `DashboardMobile.dc.html` has no state at all; its only computed value is `orderRows(8)`.

---

## 6. Sample data used

Sources: `../data/sample-data.md` (orders, catalog, materials, channel and month figures) and `../logic/formulas.md` (§1, §2, §5, §7). Every figure on the artboard, with its arithmetic:

### KPI 1 — فروش امروز = ۲٬۷۹۰٬۰۰۰ · ۳ سفارش · ۱ در انتظار پرداخت

Orders dated `۱۴۰۵/۰۶/۳۱`:

| فاکتور | وضعیت | مبلغ کل |
|---|---|---|
| INV-000041 | تکمیل‌شده | 950,000 |
| INV-000040 | تکمیل‌شده | 1,040,000 |
| INV-000039 | در انتظار | 800,000 |

`950,000 + 1,040,000 + 800,000 = 2,790,000` ✓ · count 3 ✓ · `در انتظار` count 1 (INV-000039) ✓. No draft is dated today, so the draft-exclusion rule is untested by this figure.

### KPI 2 — درآمد این ماه = ۱۸۶٬۴۲۰٬۰۰۰

`itemsRevenue 174,900,000 + shippingRevenue 11,520,000 = 186,420,000` ✓ (`../data/sample-data.md` → Month figures; `../logic/formulas.md` §7). Delta `↑۱۲٪ نسبت به مرداد` implies a مرداد revenue of `186,420,000 ÷ 1.12 ≈ 166,446,000`, **which is not in the sample data** — not verifiable.

### KPI 3 — سود خالص این ماه = ۴۲٬۰۴۶٬۰۰۰ · حاشیه سود ۲۳٪

Full P&L chain (`../logic/formulas.md` §7):

```
  174,900,000  itemsRevenue
+  11,520,000  shippingRevenue
= 186,420,000  totalRevenue
−  91,336,000  COGS
−   7,120,000  packaging
−  14,347,656  postage (estimate) = 72 shipped × 199,273
−   1,260,000  transaction fees
=  72,356,344  grossProfit
−     412,344  postage variance = 14,760,000 paid − 14,347,656 estimated
−   1,610,000  refund + cancel losses
−   1,288,000  waste (ضایعات only)
−  27,000,000  operating expenses
=  42,046,000  netProfit
```
✓ `42,046,000 ÷ 186,420,000 = 22.557٪`. The card rounds to **۲۳٪**; `../data/sample-data.md` and the reports screen carry the same ratio as **۲۲٫۶٪** — the same number at two precisions (§7). Delta `↓۳٪ نسبت به مرداد`: مرداد net profit in `../data/sample-data.md` is 38,900,000, so this month is `+8٪`, not `−3٪` — not verifiable and apparently contradicted (§7).

### KPI 4 — سفارش‌های این ماه = ۸۷ · ۶۴ ارسالی · ۸ عمده · ۱۵ حضوری

Channel counts from `../data/sample-data.md`: وب‌سایت 34 · اینستاگرام 30 · عمده‌فروشی 8 · حضوری 15 · سایر 0.

```
34 + 30            = 64   ارسالی
                     8    عمده
                     15   حضوری
64 + 8 + 15        = 87   ✓ total
```
Status mix behind the 87: پیش‌نویس ۲، در انتظار ۴، پرداخت‌شده ۶، تکمیل‌شده ۶۹، لغوشده ۳، مرجوعی ۳ — so the count includes 2 drafts, 3 cancellations and 3 refunds that KPIs 1–3 exclude. Note also that the P&L above bills postage for **72** shipped orders (64 + 8 wholesale) while this caption calls only 64 «ارسالی».

### اقتصاد ارسال این ماه

Inputs: `n = 64` (web 34 + insta 30), `charged = 180,000` (وب‌سایت / اینستاگرام channel default), `packaging = 95,000` (جعبه استاندارد, `../logic/formulas.md` §5: `60,000 + 0.1×150,000 + 0.2×90,000 + 2,000`), `postage = 199,273` (`../logic/formulas.md` §2: `(3,960,000 + 3,400,000 + 3,600,000) ÷ (18 + 17 + 20) = 10,960,000 ÷ 55`).

| figure | per order | × 64 | artboard |
|---|---|---|---|
| دریافتی از مشتری | 180,000 | 11,520,000 | `۱۱٬۵۲۰٬۰۰۰` ✓ |
| هزینه بسته‌بندی | 95,000 | 6,080,000 | `۶٬۰۸۰٬۰۰۰` ✓ |
| هزینه پست (تخمینی) | 199,273 | 12,753,472 | `۱۲٬۷۵۳٬۴۷۲` ✓ |
| نتیجه هر سفارش | −114,273 | −7,313,472 | `−۱۱۴٬۲۷۳` / `−۷٬۳۱۳٬۴۷۲` ✓ |

```
180,000 − 95,000 − 199,273 = −114,273          per order
−114,273 × 64              = −7,313,472        month
11,520,000 − 6,080,000 − 12,753,472 = −7,313,472   (same, from the month totals)
break-even charge = 95,000 + 199,273 = 294,273
gap               = 294,273 − 180,000 = 114,273
```

Cross-checks against the month figures:
- The card's `۱۱٬۵۲۰٬۰۰۰` equals the whole month's shipping revenue in `../data/sample-data.md` ✓ — consistent, because عمده‌فروشی، حضوری and سایر all charge 0.
- The card's `۶٬۰۸۰٬۰۰۰` is **less** than the month's packaging line in the P&L (7,120,000). The difference of 1,040,000 covers the 8 wholesale orders and the orders that used a costlier kit (INV-000038 used جعبه وینیل at 140,000) — the card models one kit for all 64, which the month data does not (§7).
- The card's `۱۲٬۷۵۳٬۴۷۲` is `64 × 199,273`; the P&L's postage line is `72 × 199,273 = 14,347,656` ✓ — the same rate over a different population.

Bar widths:

```
180,000 ÷ 294,273 = 61.2%  → 61%    (charged)
114,273 ÷ 294,273 = 38.8%  → 39%    (کسری)
 95,000 ÷ 294,273 = 32.3%  → 32%    (بسته‌بندی)
199,273 ÷ 294,273 = 67.7%  → 68%    (پست)
```
The `aria-label`s round to «۱۸۰ هزار» and «۲۹۴ هزار».

### هشدار کمبود موجودی — products tab

Applying `stock <= min` to active `CATALOG` rows:

| id | نام | موجودی | حداقل | rule says | artboard shows |
|---|---|---|---|---|---|
| p10 | کاست آلبوم اول | 0 | 5 | `out` (stock 0) | `ناموجود`, `stock out`, meter **2%** (0% would be invisible) |
| p2 | وینیل نسخه رنگی | 2 | 3 | `low` (2 ≤ 3) | `۲ عدد`, **`stock out`**, meter **40%** (2 ÷ 3 = 67%) |
| p3 | کاست نسخه محدود | 3 | 5 | `low` (3 ≤ 5) | `۳ عدد`, `stock low`, meter 60% = 3 ÷ 5 ✓ |
| p9 | آینه لوگو گرد | 4 | 5 | `low` (4 ≤ 5) | `۴ عدد`, `stock low`, meter 80% = 4 ÷ 5 ✓ |
| p6 | تی‌شرت لوگو مشکی (L) | 7 | 5 | not low (7 > 5) | correctly absent ✓ |
| p11 | پوستر تور ۱۴۰۳ | 6 | 0 | not low (`min` falsy) + inactive | correctly absent ✓ |

Count `۴` ✓ — the membership of the list is exactly right; two of the four severities/percentages are not (§7).

### هشدار کمبود موجودی — materials tab

Applying `stock <= min` to `type: 'goods'` rows of `MATERIALS`:

| id | نام | موجودی | حداقل | ratio | artboard |
|---|---|---|---|---|---|
| m10 | جعبه وینیل | 8 | 20 | 40% | `۸ عدد`, `stock out`, 40% ✓ |
| m12 | نوار چسب لوگودار | 2 | 5 | 40% | `۲ رول`, `stock out`, 40% ✓ |
| m11 | پاکت حباب‌دار کوچک | 15 | 40 | 37.5% | `۱۵ عدد`, `stock low`, 38% ✓ |
| m5 | تی‌شرت خام مشکی L | 6 | 10 | 60% | `۶ عدد`, `stock low`, 60% ✓ |
| m13 | کاغذ پرکننده | 1.5 | 3 | 50% | **`۱ بسته`**, `stock low`, **33%**, meta `حداقل ۳ بسته` — the data says **۱٫۵ کیلوگرم / حداقل ۳** |
| m3 | نوار کاست خام | 12 | 20 | 60% | **missing from the list entirely** |

So the rule yields **6** materials and **10** items overall, while the artboard shows `۵` on the tab and `۹ مورد` in the badge (§7). Non-qualifying goods, for completeness: m1 38/20, m2 45/20, m4 60/20, m9 64/30, m14 400/100, m15 90/30, m16 42.5/10 — all above minimum ✓. Services m6, m7, m8 have `stock: null` and never alert ✓.

### آخرین سفارش‌ها

`ORDERS[0..7]` verbatim (see the table in §2). Spot-checks:

- `INV-000038` — `۳٬۱۳۰٬۰۰۰` and `۱٬۱۸۹٬۷۲۷` match the fully worked order in `../data/sample-data.md`: `3,030,000 − 80,000 + 180,000 = 3,130,000`; `3,130,000 − 1,570,000 − 140,000 − 199,273 − 31,000 = 1,189,727` ✓ (جعبه وینیل, not the standard kit).
- `INV-000035` (مرجوعی) — `−۲۹۴٬۲۷۳` = `refundLoss = kitCost 95,000 + postageEstimate 199,273 + fee 0` (`../logic/formulas.md` §6) ✓. Revenue stays; the profit becomes the loss.
- `INV-000036` (لغوشده) and `INV-000034` (پیش‌نویس) — profit `null` → `—` in `.nil` ✓, matching §1's "unknown / not applicable" formatting rule.
- `INV-000040` (حضوری) — profit 592,000 on a 1,040,000 total, i.e. no packaging and no postage, consistent with حضوری having postage **off** and the `بدون بسته‌بندی` kit.
- Ordering `۰۶/۳۱ ۱۳:۴۲ → ۰۶/۳۱ ۱۱:۰۵ → ۰۶/۳۱ ۰۹:۲۰ → ۰۶/۳۰ ۱۶:۲۴ → ۰۶/۳۰ ۱۲:۱۰ → ۰۶/۲۹ ۱۸:۳۷ → ۰۶/۲۹ ۱۰:۰۲ → ۰۶/۲۸ ۱۹:۱۵` is strictly descending ✓.

### Header

`سه‌شنبه، ۳۱ شهریور ۱۴۰۵` is the sample "today" used by every screen (`../data/sample-data.md`). `آخرین به‌روزرسانی ۱۴:۰۵` and the error state's `آخرین بارگذاری موفق: امروز ۱۰:۴۲` are literals with no source field.

---

## 7. Open questions for this screen

**Postage and shipping economics**

- **Estimate or actual?** The card is titled «هزینه پست (تخمینی)» and uses the store-wide estimate ۱۹۹٬۲۷۳ for all 64 orders. But `../logic/formulas.md` §2 says the estimate is *copied onto each order at save time* and never rewritten, and §7 records a `postageVariance` of ۴۱۲٬۳۴۴ for the month against ۱۴٬۷۶۰٬۰۰۰ actually paid. So there are three candidate numbers for this card — the current estimate, the sum of the estimates stored on the month's orders, and the actual paid — and the design does not say which. The card's ۱۲٬۷۵۳٬۴۷۲ is the first. Whether the variance should appear here (as it does in the P&L and on the shipping report) is undecided; `../data/sample-data.md` gives an all-shipped figure of **−۱۰٬۳۶۰٬۰۰۰** including variance, which is a different and larger loss than this card's −۷٬۳۱۳٬۴۷۲.
- **Population is ambiguous.** The card counts 64 orders (وب‌سایت + اینستاگرام) and calls them «سفارش ارسالی», while KPI 4 uses the same word for the same 64 and the P&L bills postage for **72** (adding عمده‌فروشی, which also has postage on). Decide once what «ارسالی» means and make the card, the KPI caption and the P&L agree — or say in the card why wholesale is excluded.
- **One kit for everyone.** The month total ۶٬۰۸۰٬۰۰۰ assumes all 64 orders used جعبه استاندارد at ۹۵٬۰۰۰, yet the sample's own INV-000038 used جعبه وینیل at ۱۴۰٬۰۰۰ and the P&L packaging line is ۷٬۱۲۰٬۰۰۰. Decide whether the card shows a weighted average of the kits actually used (and what the "per order" line then means) or keeps the single-rate model and labels it as an assumption.
- **Only the loss case is drawn.** There is no break-even and no profitable artboard: no alternative to the `زیان‌ده` badge, no copy for «سربه‌سر» or a positive «نتیجه هر سفارش», no colour/hatch treatment when `perOrder >= 0`, and no design for the bars when the charged amount exceeds the cost (the hatch would have to move to the cost bar).
- **The alert's link goes nowhere.** `هزینه‌های ارسال` is `href="#"`. It presumably means `Postage.dc.html`, but no route is stated.

**KPI period, deltas and counting rules**

- **What period do the KPIs cover, and does the month picker drive them?** Three cards say «این ماه» and one says «امروز»; the picker reads `شهریور ۱۴۰۵` but has no handler, no popover artboard on this screen and no defined effect. Does changing the month re-scope «فروش امروز» too (to e.g. the last day of that month), or does that card always mean today? Is the period the Jalali calendar month, or the arbitrary range the picker can produce elsewhere (`Orders-DateRange`)?
- **Are the deltas real comparisons?** `↑۱۲٪` and `↓۳٪` «نسبت به مرداد» have no formula, no source figure and no tooltip. Worse, they look wrong: مرداد net profit in `../data/sample-data.md` is ۳۸٬۹۰۰٬۰۰۰, so شهریور's ۴۲٬۰۴۶٬۰۰۰ is about **+۸٪**, not −۳٪, and no مرداد revenue exists to check the +۱۲٪ against. Decide whether these are computed at all (what they compare — revenue to revenue, net to net; same-length period or full previous month), what happens when the previous month is missing or zero, whether an up-arrow is always good (a rising cost would be bad), and whether the month name in the caption is derived from the picker.
- **۳٪ or ۴٪?** The desktop profit card shows `↓۳٪` and the mobile one `↓۴٪`. One of them is wrong.
- **۲۳٪ or ۲۲٫۶٪?** The KPI caption rounds the margin to `۲۳٪` while `../data/sample-data.md` and the reports screen use `۲۲٫۶٪`. `design-system.md` §6 mandates the Persian decimal form for percentages, so the rounding rule for a KPI caption needs a decision.
- **Do drafts count anywhere?** `../logic/formulas.md` §7 is explicit that drafts are excluded from every report, and «فروش امروز» / «درآمد» / «سود خالص» follow that. But «سفارش‌های این ماه ۸۷» includes ۲ پیش‌نویس، ۳ لغوشده and ۳ مرجوعی, and «آخرین سفارش‌ها» lists a draft as its eighth row. Decide whether the order count excludes drafts (making it ۸۵), whether it excludes cancellations and refunds too (making it ۸۲), and whether the KPI should say so. Likewise for KPI 1's «۳ سفارش» — the sample has no draft today, so the artboard does not settle it.
- **«۱ در انتظار پرداخت» vs the status name.** The status is «در انتظار»; the caption says «در انتظار پرداخت». Decide whether that is a deliberate clarification or drift, and note that the sidebar's unexplained orders pill `۳` (`00-app-shell.md` §7) is a third count of roughly the same thing.

**Low-stock card**

- **One material is missing and the counts are therefore wrong.** `نوار کاست خام` is 12 against a minimum of 20, so `stock <= min` puts it on the list; the artboard shows 5 materials and `۵` / `۹ مورد` where the rule gives 6 and ۱۰. Either the rule is not what the list intends, or the sample list is incomplete.
- **What is «out» vs «low»?** `stockCls()` reserves `out` for `stock === 0`, but the artboard marks `وینیل نسخه رنگی` (2 of 3), `جعبه وینیل` (8 of 20) and `نوار چسب لوگودار` (2 of 5) as `stock out` while `پاکت حباب‌دار کوچک` (15 of 40, a *lower* ratio than جعبه وینیل) is `stock low`. There is evidently a second, undocumented severity threshold — define it, or make the card use `stockCls()`.
- **The meter's formula is unstated and inconsistent.** Rows 3–4 of the products tab and every material except one are `stock ÷ min`, but `کاست آلبوم اول` is drawn at 2% instead of 0% (deliberate, so an empty bar is still visible), `وینیل نسخه رنگی` at 40% instead of 67%, and `کاغذ پرکننده` at 33% instead of 50%. Decide the formula, the minimum visible width, and what happens above 100%.
- **`کاغذ پرکننده` is described with the wrong unit and quantity.** The card says `۱ بسته` / `حداقل ۳ بسته`; `MATERIALS` says `1.5` `کیلوگرم` with a minimum of 3. Fractional material quantities are supposed to render as `۱٫۵ کیلوگرم` (`design-system.md` §6), which is exactly the case this row should have exercised.
- **The meta line has no fixed shape.** Compare `بسته‌بندی · حداقل ۲۰ · حدود ۵ روز`, `بسته‌بندی · حداقل ۵ رول`, `بسته‌بندی · حداقل ۴۰` and `کاست · حداقل ۵ عدد`: sometimes the unit is present, sometimes not, and `حدود ۵ روز` appears on exactly one row with nothing to say what it is (supplier lead time?) or where it is stored. There is no lead-time field anywhere in `../data/sample-data.md`.
- **`تولید` vs `خرید` is not derivable.** `کاست نسخه محدود` and `کاست آلبوم اول` get `تولید`; `وینیل نسخه رنگی` and `آینه لوگو گرد` get `خرید` — but both of the latter appear in the production history, and وینیل نسخه رنگی also appears in the purchase history. What decides the action label (a per-product `replenishMethod` field? whichever history is more recent?) is unspecified, and both buttons are `href="#"` with no target screen or prefilled state.
- **Nothing is designed for the zero case or the overflow case.** There is no "no shortage" state inside the ready board (only the whole-screen empty board has one), no rule for how many rows the card shows before it scrolls or truncates, and no ordering rule — the sample happens to run worst-first by severity, but ties and the products/materials interleave are undefined. `مشاهده همه در محصولات و مواد` is also `href="#"`.

**Mobile**

- **The mandated postage caption is missing.** The project rule is that «۱۹۹٬۲۷۳» always carries «جمع پرداختی ÷ جمع سفارش‌ها»; the mobile card shows the number with no caption, no tooltip and no info affordance. The break-even alert and the three `جمع ماه:` subtotals are gone too, so the mobile card cannot answer "why is this number what it is" at all.
- **The second low-stock tab is dead.** `بسته‌بندی و مواد` is rendered with its count pill `۵` but has no handler and no list; the mobile board has no `role="tablist"`/`role="tab"` either. Decide whether mobile gets the tab behaviour, a combined list, or no tabs.
- **Mobile drops per-row context.** No meter, no category, and no `تولید`/`خرید` action, so a mobile user can see the shortage but cannot act on it, and there is no `مشاهده همه` link to the full screen.
- **Labels change between states.** The ready board says `سود خالص این ماه` / `سفارش‌های این ماه`; the empty board says `سود خالص` / `سفارش‌ها`. Pick one set.
- **The mobile error state is weaker than the desktop one.** No error code, no `role="alert"`, and the whole screen is replaced rather than keeping the KPI shells as `—` the way desktop does. There is also no welcome banner on the mobile empty board, so the "define products first" instruction never reaches a mobile-only user.
- **The month button is 36px tall**, below the 44px touch-target rule in `design-system.md` §7, and it opens nothing.
- **The bottom action bar is `position: absolute` inside the artboard canvas**, so at `h: 2000` it sits 2000px down rather than at the bottom of the viewport. The implementation needs `fixed` (or a sticky footer) plus a safe-area inset; the 20px bottom padding looks like an approximation of one, but no `env(safe-area-inset-bottom)` is specified.
- **No `DashboardMobile-Dark` artboard exists**, so the mobile dark theme of the loss tints, the hatch pattern, the bar colours and the legend swatches was never checked.

**Structural / cross-cutting**

- **The route is unknown.** No screen file states the dashboard's path; the artboards link by filename (`RecordSale.dc.html`, `Orders.dc.html`, `OrderDetail.dc.html`) — see `00-app-shell.md` §7.
- **Two `main` paddings, again.** Both dashboard boards override the shell macro: desktop `24px 32px 32px` with `gap: 24` against the macro's `24px 32px 40px` / `gap: 20`, and mobile `16px 16px 104px` / `gap: 16` against `14px 16px 100px` / `gap: 12`. The desktop wrapper also drops the macro's `position: relative`. Pick the canonical values (this is the same conflict recorded in `00-app-shell.md` §7).
- **The shared state macro is bypassed.** `[[STATES:]]` / `[[MSTATES:]]` exist precisely so every screen's empty/loading/error copy matches, but the dashboard hand-writes all three on both breakpoints. Its error title is `اطلاعات داشبورد بارگذاری نشد` where the macro would produce `<what> بارگذاری نشد`, and its error body adds a sentence the macro does not have. Decide whether the dashboard is a deliberate exception (it has to keep the KPI shells visible, which the macro cannot do) and, if so, record its copy as a sanctioned variant.
- **`آخرین به‌روزرسانی ۱۴:۰۵` has no mechanism.** No refresh button, no polling interval, no stale threshold, no relative form («۲ دقیقه پیش»), and no behaviour when the tab has been open for hours. The error board's `آخرین بارگذاری موفق: امروز ۱۰:۴۲` implies the value is remembered across a failure, but nothing says where from.
- **The recent-orders list mixes activities and sales.** It shows drafts, cancellations and refunds — sensible for "recent activity" but confusing next to KPIs that exclude them, and the mobile card labels a refund's negative figure `سود −۲۹۴٬۲۷۳` ("profit −294,273") rather than «زیان», which the record-sale summary does flip (`02-record-sale.md` §5). `helpers.js` also punctuates the two forms differently (`سود ۳۲۷٬۷۲۷` vs `سود: —`).
- **Eight rows is a magic number.** `orderRows(8)` is hardcoded on both breakpoints; nothing says why 8, whether it should fill the available height, or whether the count should match the sidebar pill or a setting. There is also no empty-but-filtered state, no pagination, no column sorting and no row-level action on this table.
- **No live-region or auto-refresh accessibility story.** `main` has no `aria-label`, the KPI values are not in a live region, and if the numbers do refresh in place a screen-reader user is not told. The loading board announces itself (`aria-busy` + `aria-label`) on desktop but the mobile one has `aria-busy` with no label.
