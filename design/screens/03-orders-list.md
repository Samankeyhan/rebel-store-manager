# 03 — سفارش‌ها (Orders list)

Route: undefined (the artboards link to `Orders.dc.html`; see §7 and `00-app-shell.md` §7) · sidebar key `orders` · page title in top bar: **سفارش‌ها**

The list is the app's hub: every sale recorded on screen 02 lands here, and every order-detail page is reached from here. It is a filter bar over a status tab strip over a single wide table, and it is the only screen that shows **profit per order** in a list — so it is also the only place where the "profit unknown" and "profit negative" display rules have to survive next to each other, row by row. Desktop and mobile diverge more than on any other screen: desktop puts status in a tab strip with month-wide counts and channel in a dropdown, while mobile puts both into a bottom filter sheet and turns each row into a card. Almost nothing in the filter bar is wired in the artboards — only the status tabs and the date popover toggle have handlers — so this file is mostly a specification of what was *drawn*, and §7 is unusually long.

Artboards: `Orders.dc.html` (default, 1440 × 1080), `Orders-Dark` (`theme: dark`), `Orders-DateRange` (`dateOpen: true` — the open Jalali range popover), `Orders-Empty` (`state: empty`, h 760), `Orders-Loading` (`state: loading`, h 860), `Orders-Error` (`state: error`, h 760), and `OrdersMobile.dc.html` (390 × 1400), `OrdersMobile-Filters` (`state: filters`, h 844), `OrdersMobile-Empty`, `OrdersMobile-Loading`, `OrdersMobile-Error` (all 390 × 844).
Source: `src/Orders.dc.html`, `src/OrdersMobile.dc.html`. Both are interactive: the desktop `state` prop is `ready | empty | loading | error`, `dateOpen` is a boolean, and the status tabs really re-filter and re-total in the board (`setState({tab})`). The mobile `state` prop is `ready | filters | empty | loading | error`.

Neither file uses the `[[STATES:…]]` / `[[MSTATES:…]]` macros from `build.py` — this screen hand-writes its own empty/loading/error boards, with copy that is **richer than the macro's** (an error code on desktop, a screen-specific empty explanation, a table-shaped skeleton). The macro copy is therefore not what ships here; §2 lists the real strings.

---

## 1. Layout

### Desktop (1440 × 1080)

```
+-- sidebar 264 (RIGHT) --+------------------------ content 1176 ------------------------+
|                         | top bar 64: «سفارش‌ها»                                        |
|  active item = orders   +--------------------------------------------------------------+
|  (+ count pill ۳)       | main  padding 24 32 32  ·  flex column  ·  gap 16            |
|                         |                                                              |
|                         | [A] header row   justify-between                             |
|                         |     «۸۷ سفارش در شهریور ۱۴۰۵»      [خروجی Excel][ثبت فروش]   |
|                         |                                                              |
|                         | [B] filter bar   role=search · gap 10 · wrap                 |
|                         |     [search 300][کانال ▾][تاریخ ▾][پاک کردن فیلترها]         |
|                         |                                                              |
|                         | [C] tabs  role=tablist · h 40 · 1px bottom border            |
|                         |     همه ۸۷ | پیش‌نویس ۲ | در انتظار ۴ | پرداخت‌شده ۶ |          |
|                         |     تکمیل‌شده ۶۹ | لغوشده ۳ | مرجوعی ۳                        |
|                         |                                                              |
|                         | [D] card (radius 12, overflow hidden)                        |
|                         |   +--- totals strip  h~45, --surface, gap 28, padding 12 16 -+|
|                         |   | این صفحه: ۱۲ سفارش   جمع فروش: …   جمع سود: …           ||
|                         |   +----------------------------------------------------------+|
|                         |   | thead h 40 --surface-2 · 8 columns                       ||
|                         |   | 12 × tbody tr h 52, 1px separators, hover --surface-2    ||
|                         |   +--- footer  padding 12 16, border-top --------------------+|
|                         |   | نمایش ۱ تا ۱۲ از ۸۷        [‹][۱][۲][۳]…[۸][›]          ||
|                         |   +----------------------------------------------------------+|
+-------------------------+--------------------------------------------------------------+

Orders-DateRange adds, absolutely positioned inside the content column:
  .menu  top 190 · right 400 · z-index 30 · padding 0 · flex-direction row · role=dialog
  +-- presets 150 (right, border-left 1) --+-- مرداد ۱۴۰۵ 266 --+-- شهریور ۱۴۰۵ 266 --+
  |                                        |  footer: از … تا … (۳۱ روز)  [انصراف][اعمال]|
```

- `main` is `padding: 24px 32px 32px; display: flex; flex-direction: column; gap: 16px` — **not** the `[[PAGE]]` macro's `24px 32px 40px` / gap 20. This file writes its own shell (it does not use the macro) and its own padding. See §7.
- [A] is `display: flex; align-items: center; justify-content: space-between`, buttons in a `gap: 8px` group: outline `خروجی Excel` (`download` icon 16) then primary `ثبت فروش` (`plus` 16), which is an `<a href="RecordSale.dc.html">`.
- [B] is `display: flex; gap: 10px; align-items: center; flex-wrap: wrap` with `role="search"` and `aria-label="فیلتر سفارش‌ها"`.
- [C] `.tabs` is inside `sc-if isReady`, so the tab strip does **not** exist in the empty/loading/error boards.
- [D] `.card` with `style="overflow: hidden"` so the totals strip and the table header clip to the 12px radius.

#### Filter bar — control order (exact, inline-start → inline-end, i.e. right → left)

1. **Search** — `.ig` group, `width: 300px`; `search` icon 16 as `.pfx` at `right: 12`; `<input class="input">`, placeholder `شماره فاکتور یا نام مشتری`, `aria-label="جستجو در سفارش‌ها"`. No value, no handler.
2. **Channel filter** — `<button class="select">` with `style="width: auto; gap: 10px"` and `aria-haspopup="listbox"`; contents: `.muted` label `کانال:`, then `.b` value `همه کانال‌ها`, then `chevD` 14. No handler, and **no option list is drawn on desktop** (see §2 and §7).
3. **Date range** — `<button class="select {{dateCls}}">` with `aria-haspopup="dialog"`, `onClick=toggleDate`; contents: `cal` 16, `.muted` label `تاریخ:`, then `.b.num` value `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱`, then `chevD` 14. `dateCls` is `is-focus` while the popover is open (a 3px `--ring` glow), `''` otherwise.
4. **Clear** — `<button class="btn btn-ghost btn-sm">` with `x` 14 and the label `پاک کردن فیلترها`. No handler.

There is no channel/status/date state in the component at all — `this.state` holds only `{ tab, date }`.

#### Table — every column

Only the last column carries an explicit width. Columns 1–7 are sized by the browser: `.tbl { width: 100% }`, `td/th { padding: 0 16px; white-space: nowrap }`, header 40px, rows 52px. The only stated widths in the source are the **loading skeleton's** grid, which is the closest thing to an intended column model: `grid-template-columns: 110px 130px 90px minmax(0, 1fr) 100px 130px 120px; gap: 24px` (7 tracks — the actions column has no skeleton).

| # | header (verbatim) | th class | td class | content | width |
|---|---|---|---|---|---|
| 1 | `شماره فاکتور` | — | — | `<a href="OrderDetail.dc.html" class="inv">` — monospace 12.5/600, `direction: ltr; unicode-bidi: isolate` | auto · skeleton **110px** |
| 2 | `تاریخ ↓` | — | `num muted2` | `{{o.dt}}` = `faD(date) + ' · ' + faD(time)` | auto · skeleton **130px** |
| 3 | `کانال` | — | — | `<span class="ch ch-*">` chip, 24px, coloured 8×8 square | auto · skeleton **90px** |
| 4 | `مشتری` | — | — | plain text, `{{o.cust}}` | auto · skeleton **minmax(0, 1fr)** (the only flexible track) |
| 5 | `وضعیت` | — | — | `<span class="badge st-*">` pill, 24px, leading 6px dot | auto · skeleton **100px** |
| 6 | `مبلغ کل (تومان)` | `n` | `n num b` | `fa(total)` — number only, unit lives in the header | auto · skeleton **130px** |
| 7 | `سود (تومان)` | `n` | `{{o.pCls}}` = `n num b pos` / `n num b neg` / `n num b nil` | `fa(profit)` or `—` | auto · skeleton **120px** |
| 8 | visually-hidden `عملیات` (`position:absolute; width:1px; height:1px; overflow:hidden`) | inline `width: 56px` | — | `<button class="btn btn-ghost btn-icon btn-sm" aria-label="عملیات سفارش">` with `more` 16 | **56px** |

`.tbl .n` resolves to `text-align: right`, which in RTL is the *inline start* — the same alignment as every other column. See §7.
`↓` in the second header is a bare `U+2193` character inside plain `<th>` text: there is no sort button, no `aria-sort`, and no handler anywhere.

### Mobile (390 × 1400 default; 390 × 844 for the state boards)

```
+---------------------------- 390 ----------------------------+
| MobileBar  h 56 : «سفارش‌ها»                                 |
+-------------------------------------------------------------+
| main  padding 12 16 96  ·  flex column  ·  gap 12           |
|                                                             |
| [search 44px full width] placeholder شماره فاکتور یا نام…    |
|                                                             |
| chip row  display:flex · gap 8 · overflow:hidden  (!)        |
|  [فیلترها ۱][شهریور ۱۴۰۵][همه وضعیت‌ها][همه کانال‌ها]  ← clipped |
|                                                             |
| ۸۷ سفارش                     جمع فروش: ۱۸۶٬۴۲۰٬۰۰۰          |
|                                                             |
| +--- card = <a href="OrderDetailMobile.dc.html"> ----------+ |
| |  INV-000041                            [تکمیل‌شده]       | |
| |  [اینستاگرام] علی ر.                        ۹۵۰٬۰۰۰      | |
| |  ۱۴۰۵/۰۶/۳۱ · ۱۳:۴۲                  سود ۳۲۷٬۷۲۷        | |
| +-----------------------------------------------------------+ |
|  … 10 cards total (orderRows(10)) …                         |
|                                                             |
| [ نمایش ۱۲ سفارش بعدی ]  outline, h 44, full width          |
+-------------------------------------------------------------+
| sticky bar: absolute bottom · padding 12 16 20 · --surface  |
|  [ + ثبت فروش ]  primary btn-lg, width 100%                 |
+-------------------------------------------------------------+
```

- `main` is `padding: 12px 16px 96px; gap: 12px` — again hand-written, not the `[[MPAGE]]` macro's `14px 16px 100px`.
- The search input is the standard `.ig` group with `style="height: 44px"` and `aria-label="جستجو"`.
- The chip row is `overflow: hidden` — **not** `overflow-x: auto`. Four chips at ~110–120px each plus gaps exceed the 358px content width, so `همه کانال‌ها` (and part of `همه وضعیت‌ها`) is clipped with no way to scroll to it. See §7.
- The `فیلترها` chip has `border-color: var(--navy-2)` (so it reads as "active") and carries a `.cnt` pill restyled inline to `background: var(--red); color: #fff; border-radius: 999px; font-size: 11px; padding: 0 6px` with the value `۱`.

#### Card-per-order layout (mobile)

The whole card is the link: `<a href="OrderDetailMobile.dc.html" class="card" style="display:flex; flex-direction:column; gap:6px; padding:12px 14px; color:var(--text)">`. Three rows, each `justify-content: space-between`:

1. `.inv` invoice number · `<span class="badge st-*">` status.
2. `.t-sm` group (`display:flex; gap:8px; align-items:center; min-width:0`) holding the `.ch ch-*` channel chip and the customer name with `white-space:nowrap; overflow:hidden; text-overflow:ellipsis` · then `<span class="num b">` total.
3. `.t-cap muted num` date · time · then `.t-cap {{o.pClsM}}` (`num b pos|neg|nil`) profit, prefixed in the text itself (`سود …`).

There is no per-row actions button on mobile (the desktop `more` button has no mobile equivalent), and the total has **no** `تومان` unit anywhere on the card — mobile has no column header to carry it.

#### Filter sheet (`OrdersMobile-Filters`)

`.overlay` (`position:absolute; inset:0`, `--overlay`) + `.m-sheet` pinned to the bottom, `border-radius: 18px 18px 0 0; padding: 0 16px 20px; display:flex; flex-direction:column; gap:14px`, `role="dialog"`, `aria-label="فیلتر سفارش‌ها"`. The list stays rendered behind it (`isReady = state === 'ready' || state === 'filters'`).

Order inside the sheet:

1. `.grab` handle (40×4, `--border-strong`, `margin: 8px auto 0`).
2. Header row: `<h2 class="t-h2">فیلترها</h2>` · ghost-sm button `پاک کردن همه`. **No close button.**
3. `.field` — label `وضعیت`, then a `flex-wrap` row of 6 status chips: `<button class="badge st-*" style="height:36px; padding:0 12px; cursor:pointer">`. Selected chips add `box-shadow: 0 0 0 2px var(--warn)` / `var(--info)` and a trailing `check` 12 icon.
4. `.field` — label `کانال`, then a `flex-wrap` row of 5 channel chips: `<button class="ch ch-*" style="height:36px; padding:0 12px">`. None is drawn selected.
5. `.field` — label `بازه تاریخ`, then a `.seg` with `grid-template-columns: repeat(3, minmax(0,1fr))`, three 40px buttons; then a `grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px` pair of `.select` buttons, 44px, each showing a `.t-cap muted` prefix plus a `.num` bold date and a `cal` 16 icon.
6. Primary `btn-lg`, `width: 100%`: `نمایش ۱۰ سفارش`.

---

## 2. Copy (verbatim)

### Page chrome

| Slot | String |
|---|---|
| `[[HEAD:]]` / `<title>`, desktop | `سفارش‌ها` |
| `[[HEAD:]]` / `<title>`, mobile | `سفارش‌ها — موبایل` |
| Top-bar `title` prop | `سفارش‌ها` |
| MobileBar `title` prop | `سفارش‌ها` |
| Subtitle, ready / loading / error | `۸۷ سفارش در شهریور ۱۴۰۵` |
| Subtitle, empty | `هنوز سفارشی ندارید` |
| Export button | `خروجی Excel` |
| Primary button (desktop header + mobile sticky bar) | `ثبت فروش` |

Artboard titles (from `wrappers.json`, shown in the design tool, not in the product): `سفارش‌ها — بازه تاریخ جلالی` · `سفارش‌ها — تم تیره` · `سفارش‌ها — خالی` · `سفارش‌ها — بارگذاری` · `سفارش‌ها — خطا` · `سفارش‌ها موبایل — فیلترها` · `سفارش‌ها موبایل — خالی` · `سفارش‌ها موبایل — بارگذاری` · `سفارش‌ها موبایل — خطا`.

### Filter bar (desktop)

| Slot | String |
|---|---|
| region `aria-label` | `فیلتر سفارش‌ها` |
| search placeholder | `شماره فاکتور یا نام مشتری` |
| search `aria-label` | `جستجو در سفارش‌ها` |
| channel label | `کانال:` |
| channel value | `همه کانال‌ها` |
| date label | `تاریخ:` |
| date value | `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` |
| clear button | `پاک کردن فیلترها` |

### Filter bar (mobile chip row)

| Slot | String |
|---|---|
| chip 1 | `فیلترها` + count pill `۱` |
| chip 2 | `شهریور ۱۴۰۵` |
| chip 3 | `همه وضعیت‌ها` |
| chip 4 | `همه کانال‌ها` |
| search placeholder | `شماره فاکتور یا نام مشتری` |
| search `aria-label` | `جستجو` |

### Channels — the five options

The channel names live in `helpers.js` as `CH` and are the same five everywhere in the app. They are rendered as options **only in the mobile filter sheet**; on desktop only the collapsed trigger value `همه کانال‌ها` exists.

| key | name (verbatim) | class | swatch token |
|---|---|---|---|
| `web` | `وب‌سایت` | `ch ch-web` | `--ch-web` `#0E7470` / dark `#4FC2BB` |
| `insta` | `اینستاگرام` | `ch ch-insta` | `--ch-insta` `#B8266A` / dark `#EE7FB2` |
| `wholesale` | `عمده‌فروشی` | `ch ch-wholesale` | `--ch-wholesale` `#33496A` / dark `#A9B8D6` |
| `inperson` | `حضوری` | `ch ch-inperson` | `--ch-inperson` `#8F520C` / dark `#E0A55B` |
| `other` | `سایر` | `ch ch-other` | `--ch-other` `#5D6471` / dark `#959DB0` |

### Statuses — the six options, and the seventh tab

`ST` in `helpers.js`. On desktop these are the tab strip (with `همه` prepended); on mobile they are the sheet's `وضعیت` chips.

| key | name (verbatim) | badge class | colour pair |
|---|---|---|---|
| — | `همه` (desktop tab only, not a status) | — | — |
| `draft` | `پیش‌نویس` | `badge st-draft` | `--surface` on a 1px **dashed** `--border-strong`, text `--text-2` |
| `pending` | `در انتظار` | `badge st-pending` | `--warn-soft` / `--warn` (amber) |
| `paid` | `پرداخت‌شده` | `badge st-paid` | `--info-soft` / `--info` (blue) |
| `done` | `تکمیل‌شده` | `badge st-done` | `--profit-soft` / `--profit` (green) |
| `cancel` | `لغوشده` | `badge st-cancel` | `--cancel-bg` `#474C57` fill / `--cancel-fg` `#FFFFFF` |
| `refund` | `مرجوعی` | `badge st-refund` | `--violet-soft` / `--violet` |

Every badge has a 6×6 `currentColor` dot via `.badge::before`. Tab counts (hardcoded in `renderVals`):

| tab | count |
|---|---|
| `همه` | `۸۷` |
| `پیش‌نویس` | `۲` |
| `در انتظار` | `۴` |
| `پرداخت‌شده` | `۶` |
| `تکمیل‌شده` | `۶۹` |
| `لغوشده` | `۳` |
| `مرجوعی` | `۳` |

Tab strip `aria-label`: `وضعیت`. The six status counts sum to exactly ۸۷, matching `../data/sample-data.md` "Month totals".

### Table headers

| # | String |
|---|---|
| 1 | `شماره فاکتور` |
| 2 | `تاریخ ↓` |
| 3 | `کانال` |
| 4 | `مشتری` |
| 5 | `وضعیت` |
| 6 | `مبلغ کل (تومان)` |
| 7 | `سود (تومان)` |
| 8 | `عملیات` (visually hidden) |

Row action button `aria-label`: `عملیات سفارش`.

### Totals strip and result count

Three spans in one `t-sm` row, `gap: 28px`:

| slot | template | rendered on the `همه` tab |
|---|---|---|
| result count, `همه` tab | `'این صفحه: ' + fa(rows.length) + ' سفارش'` | `این صفحه: ۱۲ سفارش` |
| result count, any status tab | `fa(rows.length) + ' سفارش «' + name + '» در این صفحه'` | e.g. `۶ سفارش «تکمیل‌شده» در این صفحه` |
| sales total | `جمع فروش: ` + `<b class="num">{{sumT}} تومان</b>` | `جمع فروش: ۲۸٬۲۴۰٬۰۰۰ تومان` |
| profit total | `جمع سود: ` + `<b class="num pos">{{profitSumT}} تومان</b>` | `جمع سود: ۹٬۵۴۸٬۸۱۶ تومان` |

All seven result-count variants, verbatim:

```
این صفحه: ۱۲ سفارش
۱ سفارش «پیش‌نویس» در این صفحه
۱ سفارش «در انتظار» در این صفحه
۲ سفارش «پرداخت‌شده» در این صفحه
۶ سفارش «تکمیل‌شده» در این صفحه
۱ سفارش «لغوشده» در این صفحه
۱ سفارش «مرجوعی» در این صفحه
```

### Pagination (desktop)

| Slot | String |
|---|---|
| range line | `نمایش ۱ تا ۱۲ از ۸۷` |
| prev button `aria-label` | `صفحه قبل` (icon `chevR`, `disabled`) |
| page 1 (`btn-secondary`, `aria-current="page"`) | `۱` |
| page 2 (`btn-ghost`) | `۲` |
| page 3 (`btn-ghost`) | `۳` |
| gap | `…` (`.muted`) |
| last page (`btn-ghost`) | `۸` |
| next button `aria-label` | `صفحه بعد` (icon `chevL`) |

`⌈۸۷ ÷ ۱۲⌉ = ۸`, so the page numbers are internally consistent. Mobile has no pagination — it has one button instead:

| Slot | String |
|---|---|
| mobile "more" button | `نمایش ۱۲ سفارش بعدی` |
| mobile count line | `۸۷ سفارش` |
| mobile sales total | `جمع فروش: ` + `<b class="num">۱۸۶٬۴۲۰٬۰۰۰</b>` |

### Jalali range picker (`Orders-DateRange`)

| Slot | String |
|---|---|
| dialog `aria-label` | `انتخاب بازه تاریخ` |
| preset 1 | `امروز` |
| preset 2 | `دیروز` |
| preset 3 | `۷ روز اخیر` |
| preset 4 | `۳۰ روز اخیر` |
| preset 5 (selected — `.mi.hl`, `font-weight: 700`, `color: var(--red)`, trailing `check` 14) | `این ماه` |
| preset 6 | `ماه گذشته` |
| preset 7 | `سال ۱۴۰۵` |
| preset 8 | `بازه دلخواه` |
| right calendar `.m` | `مرداد ۱۴۰۵` |
| left calendar `.m` | `شهریور ۱۴۰۵` |
| prev-month `aria-label` (right calendar, icon `chevR`) | `ماه قبل` |
| next-month `aria-label` (left calendar, icon `chevL`) | `ماه بعد` |
| weekday header cells, in DOM order | `ش` · `ی` · `د` · `س` · `چ` · `پ` · `ج` |
| footer summary | `از` `۱۴۰۵/۰۶/۰۱` `تا` `۱۴۰۵/۰۶/۳۱` `(۳۱ روز)` |
| footer cancel | `انصراف` |
| footer apply | `اعمال` |

The week starts on **شنبه** and the last column is **جمعه**, tinted `--loss` inline on the header cell (`style="color: var(--loss)"`) and by `.cal-d.fri` on the day cells. The header cells are single letters in the source — the full words شنبه … جمعه appear nowhere in this screen's markup; `ش` is the literal, verbatim first cell. The footer words `از` / `تا` / `(۳۱ روز)` are `.muted`, the two dates `<b class="num">`.

### Mobile filter sheet

| Slot | String |
|---|---|
| dialog `aria-label` | `فیلتر سفارش‌ها` |
| title | `فیلترها` |
| clear-all button | `پاک کردن همه` |
| field label 1 | `وضعیت` |
| status chips (in order) | `پیش‌نویس` · `در انتظار` · `پرداخت‌شده` · `تکمیل‌شده` · `لغوشده` · `مرجوعی` |
| selected status chips (ring + `check` 12) | `در انتظار` (ring `--warn`) and `پرداخت‌شده` (ring `--info`) |
| field label 2 | `کانال` |
| channel chips (in order) | `وب‌سایت` · `اینستاگرام` · `عمده‌فروشی` · `حضوری` · `سایر` |
| field label 3 | `بازه تاریخ` |
| segment 1 | `۷ روز` |
| segment 2 (`.on`) | `این ماه` |
| segment 3 | `دلخواه` |
| from select | `از ` + `۱۴۰۵/۰۶/۰۱` |
| to select | `تا ` + `۱۴۰۵/۰۶/۳۱` |
| apply button | `نمایش ۱۰ سفارش` |

Note the two clear-filters wordings differ by platform: desktop `پاک کردن فیلترها`, mobile `پاک کردن همه`. Also note the mobile segment reads `۷ روز` where the desktop preset reads `۷ روز اخیر`, and mobile `دلخواه` where desktop reads `بازه دلخواه`.

### Filtered-empty (inside the table card, `noRows`)

```
title:  هیچ سفارشی با این فیلترها پیدا نشد
body:   وضعیت یا بازه تاریخ را تغییر دهید.
button: نمایش همه        (btn-outline btn-sm, onClick → tab = 'all')
```
Icon: `filter` 26 in the standard `.e-art` tile. This state is **unreachable in every artboard** — see §7.

### Empty (no orders at all)

Desktop (`Orders-Empty`), `.empty` with `padding: 96px 24px`, icon `receipt` 28:

```
title:  هنوز سفارشی ثبت نشده
body:   هر فروشی که ثبت کنید با شماره فاکتور، کانال، وضعیت، مبلغ و سود این‌جا فهرست می‌شود.
CTA:    ثبت اولین فروش     (btn-primary, plus 16, <a href="RecordSale.dc.html">)
```

Mobile (`OrdersMobile-Empty`), `padding: 48px 20px`, icon `receipt` 26:

```
title:  هنوز سفارشی ثبت نشده
body:   هر فروشی که ثبت کنید این‌جا فهرست می‌شود.
CTA:    ثبت اولین فروش     (btn-primary btn-lg, plus 18, <a href="RecordSaleMobile.dc.html">)
```

### Error

Desktop (`Orders-Error`), `.empty` with `padding: 96px 24px`, `.e-art` overridden to `background: var(--loss-soft); color: var(--loss)`, icon `cloudoff` 28:

```
title:  فهرست سفارش‌ها بارگذاری نشد
body:   سرور پاسخ نداد. فیلترهای شما حفظ شده‌اند؛ دوباره تلاش کنید.
button: تلاش دوباره        (btn-outline, refresh 16)
code:   کد خطا: ORDERS_500   (.t-cap.muted, the code itself in <span class="ltr">)
```

Mobile (`OrdersMobile-Error`), `padding: 48px 20px`, icon `cloudoff` 26:

```
title:  سفارش‌ها بارگذاری نشد
body:   سرور پاسخ نداد. فیلترهای شما حفظ شده‌اند.
button: تلاش دوباره        (btn-outline btn-lg, refresh 18)
```

Mobile drops the error code entirely, and its title is `سفارش‌ها بارگذاری نشد` where desktop says `فهرست سفارش‌ها بارگذاری نشد`.

### Loading

Desktop (`Orders-Loading`): no copy at all. One `.sk` bar `height: 40px; width: 640px` standing in for the tab strip, then a `.card` with `aria-busy="true"` and `padding: 0 16px` holding 10 rows of the column grid described in §1, each row 52px with a 1px bottom border and seven `.sk` bars (`14px`, `14px`, `22px`, `14px` at 60% width, `22px` with `border-radius: 999px`, `14px`, `14px`).

Mobile (`OrdersMobile-Loading`): five bare `.sk` blocks, `height: 92px; border-radius: 12px`. **No `aria-busy`, no `aria-label`** — unlike desktop and unlike the `[[MSTATES]]` macro, which wraps its skeletons in `aria-busy="true"` with `aria-label="در حال بارگذاری"`.

Both loading boards still render the header row and filter bar above them, so `۸۷ سفارش در شهریور ۱۴۰۵` and the full date range are visible while the list is still loading.

---

## 3. Interactive states designed

| element | states |
|---|---|
| Screen (desktop) | `ready` (`Orders`) · `empty` · `loading` · `error` · dark (`Orders-Dark`, ready only) · range popover open (`Orders-DateRange`) |
| Screen (mobile) | `ready` · `filters` (sheet over the list) · `empty` · `loading` · `error`. **No dark mobile board.** |
| Search input | resting only (`.input`; `:focus` = `--navy-2` border + 3px `--ring` from the design system). No typed-value, no clear-affordance, no results state |
| Channel select | resting only. `aria-haspopup="listbox"` but no open state and no list |
| Date select | resting · open (`.select.is-focus`, 3px `--ring`) — the only select on this screen with a second state |
| Clear-filters button | ghost default · hover `--surface-2` (from `.btn-ghost:hover`) |
| Status tab | default (`--text-3`, transparent 2px underline) · `.on` (`--heading`, `--red` underline, `aria-selected="true"`) · hover (no separate rule — `.tab` has no `:hover`) |
| Tab count pill | `.cnt` on `--surface-3`/`--text-2` · on the active tab `.tab.on .cnt` flips to `--red-soft`/`--red` |
| Table row | default · hover (`.tbl tbody tr:hover td` → `--surface-2`). No selected, no focus-within, no expanded state |
| Invoice link | `.inv` default (`--heading`, monospace, LTR isolate). No hover/visited rule is defined |
| Status badge | six variants, one per status (see §2). One state each — they are not interactive here |
| Channel chip | five variants. One state each |
| Profit cell | three variants: `.pos` (`--profit` green) · `.neg` (`--loss` red, with a leading `−`) · `.nil` (`--text-3`, renders `—`) |
| Row actions button | ghost icon default · hover. The menu it opens is **not designed** |
| Pagination | prev `disabled` · current page `.btn-secondary` + `aria-current="page"` · other pages `.btn-ghost` · next enabled. No hover/focus variants drawn, no last-page state |
| Filtered-empty block | one state, `noRows` — not instantiated by any artboard |
| Mobile card | default only. `<a>`, so it inherits the browser focus ring; no pressed/hover rule |
| Mobile chip row | `فیلترها` chip drawn "active" (`border-color: var(--navy-2)` + red count pill `۱`); the other three chips drawn plain |
| Mobile sheet | closed · open (overlay + sheet). No drag/snap states, no close button |
| Mobile status chip (sheet) | unselected (plain `.badge st-*`) · selected (`box-shadow: 0 0 0 2px <status colour>` + trailing `check` 12). Drawn selected: `در انتظار`, `پرداخت‌شده` |
| Mobile channel chip (sheet) | unselected only — **no selected state is drawn for any channel** |
| Mobile date segment | `این ماه` `.on` · `۷ روز` and `دلخواه` default |
| Mobile from/to selects | resting only; they open nothing |

### The open Jalali range picker, in detail (`Orders-DateRange`)

The popover is `.menu` positioned `top: 190px; right: 400px; z-index: 30`, `flex-direction: row`, `padding: 0`, `role="dialog"`, `aria-label="انتخاب بازه تاریخ"`. In RTL the preset column (first in DOM) renders on the **right**, separated by its own `border-left: 1px solid var(--border)`, and the two calendars sit to its left in a `gap: 24px` row with `padding: 12px 16px` — earlier month (`مرداد ۱۴۰۵`) on the right, later month (`شهریور ۱۴۰۵`) on the left, which is the correct RTL reading order.

Presets are `.mi` rows in a 150px column, `gap: 2px`, `padding: 8px`; `این ماه` is `.mi.hl` (background `--surface-2`) with inline `font-weight: 700; color: var(--red)` and a trailing `check` 14. `.mi:hover` shares the `.hl` background, so the selected row and a hovered row look identical.

Each calendar is `.cal` (266px wide), header `.cal-h` 36px with the month name `.m` (14/700) centred between a nav button and a 32px spacer — `مرداد` gets the **prev** button (`chevR`, `ماه قبل`) on its right and a spacer on its left; `شهریور` gets a spacer on its right and the **next** button (`chevL`, `ماه بعد`) on its left. So there is exactly one prev and one next control for the pair, each on the outside edge.

Grid is `.cal-g`, `grid-template-columns: repeat(7, 38px); row-gap: 2px`. Weekday row `.cal-w` (28px, 11.5/600, `--text-3`), cells `ش ی د س چ پ ج` left-to-right in DOM = right-to-left on screen, so **شنبه is the inline-start (right-most) column and جمعه the inline-end (left-most)**, tinted `--loss`.

Day cells are `.cal-d`, 36px tall, `border-radius: 8px`, 13px, `font-feature-settings: "tnum"`, real `<button>`s, labels via `faD(d)` so `۱ … ۳۱`. Both grids come from `monthGrid(startIdx, days, opt)`:

```js
calA: monthGrid(5, 31, {}),                               // مرداد ۱۴۰۵ — day 1 on پ (پنجشنبه)
calB: monthGrid(1, 31, { today: 31, from: 1, to: 31 })    // شهریور ۱۴۰۵ — day 1 on ی (یکشنبه)
```

| cell kind | class | appearance | where it occurs in the two artboard grids |
|---|---|---|---|
| leading/trailing filler | `cal-d x` | `visibility: hidden` | مرداد: 5 leading + 6 trailing (36 → 42 cells, 6 rows). شهریور: 1 leading + 3 trailing (32 → 35 cells, 5 rows) |
| ordinary day | `cal-d` | transparent, `--text`; `:hover` → `--surface-2` | all of مرداد except Fridays |
| Friday | `cal-d fri` | text `--loss` | مرداد ۲، ۹، ۱۶، ۲۳، ۳۰ |
| range start | `cal-d s` | `--red` fill, `#fff`, 700, `border-radius: 0 8px 8px 0` (rounded on the inline-start/right edge) | شهریور ۱ |
| in range | `cal-d in` | `--red-soft` background, square (`border-radius: 0`), text `--text` | شهریور ۲…۳۰ |
| in range **and** Friday | `cal-d fri in` | `.in` is declared after `.fri`, so the red Friday text is overridden back to `--text` | شهریور ۶، ۱۳، ۲۰، ۲۷ |
| range end | `cal-d e` | `--red` fill, `#fff`, 700, `border-radius: 8px 0 0 8px` | — (see next row) |
| today **and** range end | `cal-d today e` | `.e` fill wins visually; `.today`'s `inset 0 0 0 1.5px var(--red)` ring is drawn *inside* the same red fill and is therefore invisible | شهریور ۳۱ |
| single-day range | `cal-d s e` | `border-radius: 8px` | not instantiated |
| explicit single selection | `cal-d sel` | `--red` fill, `#fff`, 700, radius 8 | not instantiated on this screen (`opt.sel` is never passed) |
| **disabled** | — | — | **not designed.** `monthGrid` emits no disabled class, `.cal-d` has no `:disabled` rule, and no artboard passes a min/max. Future dates in شهریور past today (there are none — today is the 31st) and future months are all clickable |

The weekday index of day 1 in each grid is internally consistent with the project's fixed today: مرداد starts on پنجشنبه, so 1 شهریور falls on یکشنبه (`(5+31) mod 7 = 1`), and ۳۱ شهریور lands on `(1+30) mod 7 = 3` = **سه‌شنبه**, matching `../design-system.md` §6 ("All sample screens are dated ۳۱ شهریور ۱۴۰۵ (Tuesday)").

Footer: `padding: 12px 16px`, `border-top: 1px solid var(--border)`, `justify-content: space-between` — the summary line on the inline start, then a `gap: 8px` pair `انصراف` (ghost sm) + `اعمال` (primary sm). **Both buttons call the same handler, `toggleDate`** — i.e. both merely close the popover; neither commits or discards anything, because the popover holds no draft range state.

Focus: per `../design-system.md` §7, every interactive element takes `box-shadow: 0 0 0 3px var(--ring)`. No state on this screen is conveyed by colour alone except the profit sign, which is also carried by the `−` character and by the `—` placeholder.

---

## 4. Validation

None on this screen. It has one text input (the search field) with no value, no pattern, no minimum length and no error state; the filter controls cannot produce an invalid combination because no combination is committed. The only near-validation behaviour is the `noRows` filtered-empty block (§2), which is a result state, not a validation message.

The date range is likewise unvalidated: nothing designed prevents a `تا` earlier than `از` (on mobile the two dates are separate selects), and there is no min/max or disabled-day design in the calendar (§3).

---

## 5. Logic

Per-order profit and margin are defined once in `../logic/formulas.md` §1; the stock/transition rules behind the six statuses are in §6 of the same file. This screen only *displays* those numbers — it recomputes nothing per order. What is screen-specific:

### How filtering combines

Four filters are drawn. Exactly one is implemented.

```js
constructor(p) { super(p); this.state = { tab: 'all', date: p.dateOpen === true || p.dateOpen === 'true' }; }
```

`this.state` has no `q`, no `channel` and no `from`/`to`. So:

- **Status** (desktop tabs) is live: `tab` is `'all'` or one of the six `ST` keys, set by `self.setState({ tab: k })` on click.
- **Search**, **channel** and **date range** are display-only in the artboards. Their intended combination is therefore undocumented; the only thing the design commits to is that they are four independent controls plus one `پاک کردن فیلترها` that resets all of them, and that the clear button is always enabled (there is no "no filters active" state).
- The mobile sheet implies multi-select within a group (two statuses are drawn selected simultaneously) and therefore OR-within-group, AND-across-groups — but that is read off one static frame, not from code. Desktop's single-select tab strip contradicts it (see §7).

Filtering itself is a plain status equality test, applied twice — once for the display rows and once for the raw tuples used by the totals:

```js
var rows = orderRows().filter(function (o) { return tab === 'all' || o.stKey === tab; });
var raw  = ORDERS.filter(function (o) { return tab === 'all' || o[5]   === tab; });
```

`noRows = rows.length === 0`, and the `نمایش همه` button in the filtered-empty block is `allTab`, which does `setState({ tab: 'all' })` — it resets the status tab only, not the other three controls, despite the body copy naming `وضعیت یا بازه تاریخ`.

### How the Jalali range is applied

It is not. The picker's only wiring is:

```js
dateOpen: this.state.date,
dateCls:  this.state.date ? 'is-focus' : '',
toggleDate: function () { self.setState({ date: !self.state.date }); },
```

`toggleDate` is bound to the trigger button, to `انصراف` and to `اعمال` alike. No day cell has an `onClick`; no preset has an `onClick`; the two month-nav buttons have no `onClick`. The range `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` is a hardcoded string in three places (the trigger, the footer summary, and — as `from: 1, to: 31` — the `calB` grid), and the day count `(۳۱ روز)` is likewise literal. The month pair shown is fixed at مرداد/شهریور ۱۴۰۵ by the two `monthGrid` calls; nothing derives it from the selected range.

What the design *does* fix, and what an implementation must honour: Jalali only (no Gregorian anywhere, converted at the data layer per `../design-system.md` §5), week starting شنبه, Friday tinted as the holiday column, two months side by side with the earlier one on the inline start, eight presets in a fixed order, and a footer that states the resolved range plus its inclusive length in days (۱ → ۳۱ شهریور = ۳۱ روز, i.e. `to − from + 1`).

### Per-row profit: computation and colouring

The rows carry no arithmetic. Profit is a stored field on the order (`ORDERS[i][7]`), which per `../logic/formulas.md` §1 was computed and frozen at save time. `orderRows()` only classifies and formats it:

```js
var pc = o[7] === null ? 'nil' : (o[7] < 0 ? 'neg' : 'pos');
return {
  …,
  total:  fa(o[6]),
  profit: o[7] === null ? '—' : fa(o[7]),
  pCls:   'n num b ' + pc,     // desktop cell classes
  pClsM:  'num b '   + pc,     // mobile card classes
  profitT: o[7] === null ? 'سود: —' : 'سود ' + fa(o[7])
};
```

| case | test | class | rendered |
|---|---|---|---|
| profit | `profit > 0` | `.pos` → `--profit` (`#137A38` / dark `#4CC476`) | `۳۲۷٬۷۲۷` — no `+` sign |
| loss | `profit < 0` | `.neg` → `--loss` (`#B42318` / dark `#F4776C`) | `−۲۹۴٬۲۷۳` — `fa()` prepends `U+2212 MINUS SIGN`, not a hyphen |
| unknown / not applicable | `profit === null` | `.nil` → `--text-3` | `—` (`U+2014`) |
| exactly zero | `profit === 0` | falls into `.pos` (green) — `0 < 0` is false | `۰` in green. Not instantiated in the sample data |

Note the mobile string builders are not symmetric: `'سود ' + fa(...)` (space) versus `'سود: —'` (colon + space). Both are verbatim in the source.

`fa()` is the single money formatter for this screen — `Math.round(abs)`, `٬` (U+066C) every three digits, Persian digits, `−` prefix when negative, and `'—'` for `null`/`undefined`/`NaN`. Dates use `faD()`, which only transliterates digits, so `۱۴۰۵/۰۶/۳۱` keeps its ASCII slashes; `{{o.dt}}` is `faD(date) + ' · ' + faD(time)` with a `·` (U+00B7) separator. `faT()` (which appends ` تومان`) is **not** used on this screen — the desktop table puts the unit in the column headers and the totals strip writes ` تومان` inline as markup.

### Ordering

`ORDERS` in `helpers.js` is authored newest-first (INV-000041 → INV-000030, ۳۱ شهریور → ۲۶ شهریور) and `orderRows()` preserves array order via `.map`. The `تاریخ ↓` header advertises that ordering but is inert text — there is no comparator, no secondary key, and no way to reverse it. Within one day, the sample rows also run newest-first by time (۱۳:۴۲ → ۱۱:۰۵ → ۰۹:۲۰ on the 31st), so `date desc, time desc` is the ordering to implement; whether invoice number is the tiebreaker is not stated (it happens to be monotonic with the timestamp in the sample).

### Totals line

The strip is recomputed from `raw` (the status-filtered raw tuples) on every tab change:

```js
var sum = 0, ps = 0;
raw.forEach(function (o) {
  if (o[5] !== 'cancel' && o[5] !== 'draft') sum += o[6];   // sales total
  if (o[7] != null) ps += o[7];                              // profit total
});
```

Two different exclusion rules, deliberately:

- **جمع فروش** excludes `لغوشده` and `پیش‌نویس` — consistent with `../logic/formulas.md` §7 ("Drafts are excluded from every report. Cancelled and refunded orders leave revenue…"): a refunded order's revenue stays in, a cancelled one's does not.
- **جمع سود** includes every order whose stored profit is non-null, which means the refunded order's **negative** profit reduces the total. Drafts and cancellations contribute nothing simply because their profit is `null`.

The strip is scoped to the current page and the current tab, and its label says so (`این صفحه`). It is **not** a `tfoot` totals row (`../design-system.md` §5 defines one; this screen uses a header strip above `thead` instead).

Two display faults in the strip, both in the markup rather than the logic: the profit total is hardcoded `<b class="num pos">`, so it renders **green even when negative** (the `مرجوعی` tab shows `جمع سود: −۲۹۴٬۲۷۳ تومان` in profit-green), and the sales total has no class, so it is always neutral. Mobile has no equivalent computation at all — its `جمع فروش: ۱۸۶٬۴۲۰٬۰۰۰` is a literal string, the whole-month revenue from `../data/sample-data.md`, sitting above ten cards that sum to something else entirely.

### Row and card navigation

Desktop: only the invoice number is a link (`<a href="OrderDetail.dc.html" class="inv">`) — the row itself has no handler. Mobile: the **entire card** is the link (`<a href="OrderDetailMobile.dc.html" class="card">`). The two platforms therefore have different click targets for the same action, and desktop's `عملیات سفارش` button opens nothing.

---

## 6. Sample data used

All twelve rows come from `ORDERS` in `helpers.js`, reproduced in `../data/sample-data.md` §Orders. `orderRows()` is called with no limit on desktop (all 12) and as `orderRows(10)` on mobile (the first 10, INV-000041 → INV-000032). Exactly as the source defines them:

| # | invoice | Jalali date · time | channel (key) | status (key) | total | profit |
|---|---|---|---|---|---|---|
| 1 | `INV-000041` | `۱۴۰۵/۰۶/۳۱ · ۱۳:۴۲` | `اینستاگرام` (`insta`) | `تکمیل‌شده` (`done`) | `۹۵۰٬۰۰۰` | `۳۲۷٬۷۲۷` `.pos` |
| 2 | `INV-000040` | `۱۴۰۵/۰۶/۳۱ · ۱۱:۰۵` | `حضوری` (`inperson`) | `تکمیل‌شده` (`done`) | `۱٬۰۴۰٬۰۰۰` | `۵۹۲٬۰۰۰` `.pos` |
| 3 | `INV-000039` | `۱۴۰۵/۰۶/۳۱ · ۰۹:۲۰` | `اینستاگرام` (`insta`) | `در انتظار` (`pending`) | `۸۰۰٬۰۰۰` | `۲۱۵٬۷۲۷` `.pos` |
| 4 | `INV-000038` | `۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴` | `وب‌سایت` (`web`) | `پرداخت‌شده` (`paid`) | `۳٬۱۳۰٬۰۰۰` | `۱٬۱۸۹٬۷۲۷` `.pos` |
| 5 | `INV-000037` | `۱۴۰۵/۰۶/۳۰ · ۱۲:۱۰` | `عمده‌فروشی` (`wholesale`) | `تکمیل‌شده` (`done`) | `۴٬۳۰۰٬۰۰۰` | `۲٬۲۹۵٬۷۲۷` `.pos` |
| 6 | `INV-000036` | `۱۴۰۵/۰۶/۲۹ · ۱۸:۳۷` | `وب‌سایت` (`web`) | `لغوشده` (`cancel`) | `۱٬۴۳۰٬۰۰۰` | `—` `.nil` (`null`) |
| 7 | `INV-000035` | `۱۴۰۵/۰۶/۲۹ · ۱۰:۰۲` | `اینستاگرام` (`insta`) | `مرجوعی` (`refund`) | `۱٬۰۷۰٬۰۰۰` | `−۲۹۴٬۲۷۳` `.neg` |
| 8 | `INV-000034` | `۱۴۰۵/۰۶/۲۸ · ۱۹:۱۵` | `سایر` (`other`) | `پیش‌نویس` (`draft`) | `۴۸۰٬۰۰۰` | `—` `.nil` (`null`) |
| 9 | `INV-000033` | `۱۴۰۵/۰۶/۲۸ · ۱۴:۴۸` | `حضوری` (`inperson`) | `تکمیل‌شده` (`done`) | `۲٬۴۵۰٬۰۰۰` | `۱٬۰۷۰٬۰۰۰` `.pos` |
| 10 | `INV-000032` | `۱۴۰۵/۰۶/۲۷ · ۲۰:۳۱` | `وب‌سایت` (`web`) | `تکمیل‌شده` (`done`) | `۱٬۰۷۰٬۰۰۰` | `۳۵۰٬۷۲۷` `.pos` |
| 11 | `INV-000031` | `۱۴۰۵/۰۶/۲۷ · ۱۱:۲۶` | `اینستاگرام` (`insta`) | `پرداخت‌شده` (`paid`) | `۳٬۶۸۰٬۰۰۰` | `۱٬۲۹۰٬۷۲۷` `.pos` |
| 12 | `INV-000030` | `۱۴۰۵/۰۶/۲۶ · ۱۵:۰۲` | `عمده‌فروشی` (`wholesale`) | `تکمیل‌شده` (`done`) | `۹٬۷۵۰٬۰۰۰` | `۲٬۵۱۰٬۷۲۷` `.pos` |

Customer names, as authored (column 4): `علی ر.` · `مشتری حضوری` · `رها س.` · `نگار ک.` · `فروشگاه نوای شهر` · `مهدی ت.` · `پریا ن.` · `—` · `مشتری حضوری` · `کیان ب.` · `پرستو ج.` · `فروشگاه صفحه‌گردان`. Row 8's customer is the literal string `—` in the data (an `other`-channel draft with no name), not a formatter output.

Only INV-000038 has a full breakdown elsewhere (`../data/sample-data.md` §INV-000038, and it is the default record-sale form in `02-record-sale.md` §6) — its `۱٬۱۸۹٬۷۲۷` reconciles as `3,130,000 − 1,570,000 − 140,000 − 199,273 − 31,000`. The other eleven profits are authored figures with no line-item derivation anywhere in the handoff.

### Totals arithmetic, per tab

`جمع فروش` = Σ total over rows whose status is neither `cancel` nor `draft`. `جمع سود` = Σ profit over rows whose profit is not `null`.

| tab | rows | جمع فروش | جمع سود |
|---|---|---|---|
| `همه` | 12 | `950,000 + 1,040,000 + 800,000 + 3,130,000 + 4,300,000 + 1,070,000 + 2,450,000 + 1,070,000 + 3,680,000 + 9,750,000` (INV-000036 `لغوشده` and INV-000034 `پیش‌نویس` excluded) = **28,240,000** → `۲۸٬۲۴۰٬۰۰۰` | `327,727 + 592,000 + 215,727 + 1,189,727 + 2,295,727 − 294,273 + 1,070,000 + 350,727 + 1,290,727 + 2,510,727` = **9,548,816** → `۹٬۵۴۸٬۸۱۶` |
| `پیش‌نویس` | 1 | excluded → **0** → `۰` | `null` → **0** → `۰` |
| `در انتظار` | 1 | **800,000** → `۸۰۰٬۰۰۰` | **215,727** → `۲۱۵٬۷۲۷` |
| `پرداخت‌شده` | 2 | `3,130,000 + 3,680,000` = **6,810,000** → `۶٬۸۱۰٬۰۰۰` | `1,189,727 + 1,290,727` = **2,480,454** → `۲٬۴۸۰٬۴۵۴` |
| `تکمیل‌شده` | 6 | `950,000 + 1,040,000 + 4,300,000 + 2,450,000 + 1,070,000 + 9,750,000` = **19,560,000** → `۱۹٬۵۶۰٬۰۰۰` | `327,727 + 592,000 + 2,295,727 + 1,070,000 + 350,727 + 2,510,727` = **7,146,908** → `۷٬۱۴۶٬۹۰۸` |
| `لغوشده` | 1 | excluded → **0** → `۰` | `null` → **0** → `۰` |
| `مرجوعی` | 1 | **1,070,000** → `۱٬۰۷۰٬۰۰۰` | **−294,273** → `−۲۹۴٬۲۷۳`, rendered **in `.pos` green** |

Cross-check: the six status tabs' sales totals sum to `0 + 800,000 + 6,810,000 + 19,560,000 + 0 + 1,070,000 = 28,240,000` and their profit totals to `0 + 215,727 + 2,480,454 + 7,146,908 + 0 − 294,273 = 9,548,816`, both matching the `همه` tab exactly.

### Figures that are not derived from the twelve rows

| slot | value | provenance |
|---|---|---|
| Subtitle | `۸۷ سفارش در شهریور ۱۴۰۵` | month totals, `../data/sample-data.md` |
| Tab counts | `۸۷ / ۲ / ۴ / ۶ / ۶۹ / ۳ / ۳` | month totals (they sum to 87 ✓), not the page |
| Pagination range | `نمایش ۱ تا ۱۲ از ۸۷` | 12 per page × 8 pages ⊇ 87 ✓ |
| Date range | `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` `(۳۱ روز)` | the whole of شهریور ۱۴۰۵, consistent with the subtitle and the `این ماه` preset |
| Mobile `جمع فروش` | `۱۸۶٬۴۲۰٬۰۰۰` | month revenue (`../logic/formulas.md` §7), **not** the sum of the ten cards shown |
| Mobile "more" button | `نمایش ۱۲ سفارش بعدی` | inconsistent with the 10 cards actually rendered (`orderRows(10)`) and with the sheet CTA `نمایش ۱۰ سفارش` |
| Sidebar count pill | `۳` | unexplained — see `00-app-shell.md` §7 |
| Mobile filter count pill | `۱` | inconsistent with the two statuses drawn selected in the sheet |

---

## 7. Open questions for this screen

- **Is pagination real or decorative?** Nothing is wired: no page state, no handler on any page button, `disabled` hardcoded on prev, and `۱ / ۲ / ۳ / … / ۸` hardcoded. Undecided: whether 12 rows/page is the real page size (it is the length of the whole sample array, so it may be a coincidence), whether the count is server- or client-side, what the middle-page and last-page renderings look like, whether there is a page-size control, and whether the `…` is one gap or two. Mobile uses a different model entirely — a single `نمایش ۱۲ سفارش بعدی` button — and nothing says whether that is "load more" (append) or "next page" (replace), nor what it becomes on the last page. Its label also disagrees with the 10 cards it sits under.
- **Is there bulk selection?** No checkbox column, no header checkbox, no selection count, no bulk action bar, and no selected row state anywhere. If bulk status changes, bulk printing or bulk export are wanted, none of it is designed — and adding a leading checkbox column would change every column position in §1.
- **Can the list be exported, and to what?** `خروجی Excel` is drawn as an outline button with a `download` icon and has no handler, no format choice, no "exporting…" state, no success/failure feedback, and no statement of scope: the current page, the current filters, or all 87 orders. It also appears on the **empty** board, where there is nothing to export. Whether `خروجی Excel` means `.xlsx` or CSV, and whether the file uses Persian digits (which would break as numbers in a spreadsheet), is unspecified. Mobile has no export affordance at all.
- **What happens on row click?** The two platforms disagree: desktop makes only the invoice number a link, mobile makes the whole card one. Undecided: whether the desktop row should be clickable, whether it should be keyboard-focusable if so, and what `عملیات سفارش` (the `more` button, present on every desktop row) opens — no menu artboard exists, and the actions it would contain (مشاهده / چاپ فاکتور / لغو / مرجوعی / حذف پیش‌نویس) are neither listed nor gated by status, even though `../logic/formulas.md` §6 makes those transitions status-dependent.
- **Status filtering has two incompatible designs.** Desktop is a single-select tab strip; the mobile sheet draws two statuses selected at once. Pick one model. If multi-select wins, the desktop tab strip has no design for it (no "۲ وضعیت" summary, no clear-per-group), and the result-count template `۶ سفارش «تکمیل‌شده» در این صفحه` interpolates exactly one status name.
- **The channel filter has no options on desktop.** The trigger declares `aria-haspopup="listbox"` and reads `همه کانال‌ها`, but no listbox was drawn — the five channel options exist only as chips in the mobile sheet. Undecided: single- or multi-select, whether `همه کانال‌ها` is a selectable option or just the empty-state label, how the trigger reads with 1/2/5 channels chosen, and whether the list carries counts like the status tabs do.
- **Search is undefined beyond its placeholder.** `شماره فاکتور یا نام مشتری` promises two fields; no typed state, no results, no clear button, no debounce, no minimum length, no no-results copy distinct from `هیچ سفارشی با این فیلترها پیدا نشد`, and no statement of whether it matches a partial invoice number (`41` → `INV-000041`?) or ignores the `INV-` prefix. It is also separate from the global top-bar search, which returns orders too (`00-app-shell.md` §2) — nothing says how the two relate.
- **The Jalali picker commits nothing.** `انصراف` and `اعمال` are bound to the same `toggleDate`, so the popover has no draft-vs-applied range distinction; the month-nav buttons and all eight presets are inert; no day cell has a handler. Undecided: which preset is default (`این ماه` is drawn selected and matches the trigger, but `بازه دلخواه` implies a mode switch that has no second state), how clicking a start then an end builds the range, whether the range is inclusive (the `(۳۱ روز)` footer implies yes), whether single-day ranges are allowed (`.cal-d.s.e` exists in CSS but is never instantiated), and what the popover looks like when the two visible months do not contain the selection.
- **Disabled days are not designed.** `monthGrid` emits no disabled class and `.cal-d` has no `:disabled` rule, so future months and future days are clickable. If orders cannot exist in the future, decide whether those cells are disabled, hidden, or simply allowed to return an empty list. Likewise there is no min bound (the store's first order) and no design for a range spanning a year boundary.
- **`today` is invisible when it is also the range end.** ۳۱ شهریور carries `cal-d today e`: `.e`'s solid `--red` fill covers `.today`'s `inset 0 0 0 1.5px var(--red)` ring, so "today" reads as nothing extra. Decide on a today marker that survives selection (a dot, a different ring colour, or a bolder weight).
- **The profit total is always green.** `<b class="num pos">` is hardcoded, so the `مرجوعی` tab renders `جمع سود: −۲۹۴٬۲۷۳ تومان` in profit-green, and any filter producing a net loss will too. The sales total carries no class at all. The same class needs to be derived from the sign the way `pCls` is per row.
- **«نامشخص» never appears on this screen, although the profit rule calls for it.** `../logic/formulas.md` §1 says an order whose product cost is unknown must display «نامشخص», never 0, and `02-record-sale.md` §4 shows that wording on the form. Here `orderRows()` maps *every* `null` profit to `—` with `.nil` — and the only two null-profit sample orders are a `لغوشده` and a `پیش‌نویس`, i.e. the "not applicable" case, not the "cost unknown" case. So the list has **no row that exercises an unknown cost**, and nothing distinguishes "no profit because this order was cancelled" from "profit cannot be computed because a product has no cost". `../design-system.md` §6 asks for `—` in tables and «نامشخص» inline, which may be the intent, but the two meanings collapsing into one glyph should be a deliberate decision, not an accident — and if they stay distinct, the list needs a second visual and a sample row for it.
- **Drafts and cancellations are shown but silently excluded from the sales total** with no footnote. The result line says `این صفحه: ۱۲ سفارش` while `جمع فروش` covers 10 of them, and a reader who adds the visible `مبلغ کل` column will not reach `۲۸٬۲۴۰٬۰۰۰`. Decide whether to annotate the total, strike those rows, or move them out of the default view.
- **Tab counts and page rows measure different things.** The `تکمیل‌شده` tab says `۶۹` and then shows 6 rows with a `این صفحه` caveat; the pagination says `از ۸۷` regardless of which tab is active, so switching to a tab with 2 orders still offers 8 pages. The count scope (month, filtered range, or all time) is also unstated — they happen to equal the month totals, which matches the date filter's current value but would not survive changing it.
- **The filtered-empty state is unreachable and partially designed.** Every one of the seven tabs matches at least one sample row, so no artboard shows `هیچ سفارشی با این فیلترها پیدا نشد`. Worse, that block sits *inside* the card between the table and the pagination footer, so when it does appear the reader gets an empty `thead`, the empty block, and a pagination footer still claiming `نمایش ۱ تا ۱۲ از ۸۷`. Its CTA `نمایش همه` resets only the status tab although the body copy says `وضعیت یا بازه تاریخ`, and `../design-system.md` §5 says the filtered-empty variant should offer «پاک کردن فیلترها» — which this one does not.
- **The mobile chip row is clipped with no way to reach it.** `overflow: hidden` on a flex row whose four chips exceed 358px means `همه کانال‌ها` is cut off permanently: no horizontal scroll, no wrap, no overflow affordance. Either make it scrollable (and design the scroll hint), wrap it, or collapse the three value chips into the `فیلترها` button.
- **The mobile sheet cannot be dismissed.** No close button, no cancel, and the overlay has no handler. Also missing: `aria-modal`, a focus trap, focus restore to the `فیلترها` chip, and any drag/snap behaviour for the `.grab` handle, which is drawn but purely decorative. (`02-record-sale.md`'s mobile sheet does have a close button — the two sheets should agree.)
- **The mobile sheet's filter count and its selections disagree**, and applying is ambiguous: the chip says `۱` while two statuses are ringed; the CTA `نمایش ۱۰ سفارش` implies a live preview count that nothing computes; no channel is drawn selected so the selected-chip treatment for `.ch` is undesigned; and the two `از` / `تا` selects open nothing — there is no mobile calendar artboard anywhere, so `دلخواه` has no second screen.
- **Two theme/board gaps.** `Orders-Dark` is built with `dateOpen: false` and `state: ready`, so the range popover, the empty, loading, error and filtered-empty boards have **no dark artboard**; and there is no dark mobile board at all. The `.cal-d.in` / `.cal-d.fri` override interaction and the `st-cancel` white-on-dark-fill badge are exactly the cases worth checking in dark mode.
- **Loading and error boards still advertise stale content.** Both keep the header row and the whole filter bar, so `۸۷ سفارش در شهریور ۱۴۰۵`, `همه کانال‌ها` and the full date range are asserted while the data is absent or failed. The desktop loading skeleton also omits the tab strip (replaced by one 640px bar) and the actions column, and the mobile loading board has no `aria-busy`/`aria-label` at all, unlike desktop and unlike the `[[MSTATES]]` macro. Decide what survives a failed load, given that the error copy promises `فیلترهای شما حفظ شده‌اند`.
- **`.n` does nothing in RTL.** `.tbl .n { text-align: right }` is the same as the default `th`/`td` alignment, so `مبلغ کل` and `سود` are inline-start aligned like the text columns and their digits do not line up against a common edge. `../design-system.md` §5 describes `.n` as "text-align inline-start = right in RTL", so this may be intentional — but a money column that is not end-aligned is unusual, and if `text-align: left` (inline end) is wanted the token needs to change here and on every other table screen at once.
- **Column widths are unspecified.** Only the 56px actions column is fixed; the other seven are browser-sized from `nowrap` content, so the table reflows as soon as a long customer name or a nine-digit total appears. The loading skeleton's `110 / 130 / 90 / 1fr / 100 / 130 / 120` grid is the only stated intent and it does not match the real table (gap 24 vs `padding: 0 16px`, and no eighth track). Fix real widths, decide which column absorbs slack (`مشتری` in the skeleton), and specify truncation for long customer names — desktop has none, mobile ellipsises.
- **Sorting is advertised but absent.** `تاریخ ↓` is plain text in a `<th>`: no button, no `aria-sort`, no second click to reverse, and no other column is sortable even though `مبلغ کل` and `سود` are the obvious candidates. Either remove the arrow or design the full sort affordance.
- **The route and the detail-page link are placeholders.** Rows link to `OrderDetail.dc.html` / `OrderDetailMobile.dc.html` with no order identifier in the URL, and the screen's own route is undefined (see `00-app-shell.md` §7). Filter state is nowhere encoded in a URL, so a filtered list cannot be linked, bookmarked or restored after following a row and coming back — and the error copy's promise that filters are preserved has nothing to preserve them in.
- **Two paddings diverge from the shell contract.** This screen hand-writes its shell instead of using `[[PAGE]]` / `[[MPAGE]]`, and uses `24px 32px 32px` / gap 16 on desktop and `12px 16px 96px` / gap 12 on mobile, where the macros emit `24px 32px 40px` / gap 20 and `14px 16px 100px` / gap 12. `00-app-shell.md` §7 already flags conflicting `main` paddings; this screen is a third variant and should be folded into that decision.
- **Copy inconsistencies to resolve before translation freeze:** `پاک کردن فیلترها` (desktop) vs `پاک کردن همه` (mobile); `۷ روز اخیر` / `بازه دلخواه` (desktop presets) vs `۷ روز` / `دلخواه` (mobile segments); `فهرست سفارش‌ها بارگذاری نشد` (desktop error) vs `سفارش‌ها بارگذاری نشد` (mobile); `سود ۳۲۷٬۷۲۷` vs `سود: —` (space vs colon in the same mobile builder); and `نمایش ۱۲ سفارش بعدی` vs `نمایش ۱۰ سفارش` vs the 10 cards actually rendered.
