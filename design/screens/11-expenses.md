# 11 — هزینه‌ها (Expenses)

Route: `/expenses` · sidebar key `expenses` (group «مالی», wallet icon) · page title in top bar: **هزینه‌ها**

Operating expenses — the running costs of the shop that belong to no particular order (rent, advertising, internet, couriers, odds and ends). This screen is the only writer of the P&L line «هزینه‌های عملیاتی»: whatever is recorded here for a Jalali month is subtracted, in one lump, from that month's gross profit. It is a deliberately small screen — a filtered list on the left, a share-by-category breakdown and a category manager on the right, and a single modal form for adding one expense. There is no per-expense detail page, no attachment, no approval flow, and no link between an expense and an order.

Artboards: `Expenses.dc.html` (desktop, 1440×860), `Expenses-Form.dc.html` (the same board with `form: true`, 1440×860), `Expenses-States.dc.html` (three boards side by side — empty · loading · error, 1440×760 each on a 4416×760 canvas), `ExpensesMobile.dc.html` (390×1080), `ExpensesMobile-States.dc.html` (empty · loading · error, 390×844 each on 1266×844).

The desktop board's props are `form` (boolean, default `false`), `state` (`ready | empty | loading | error`, default `ready`), `theme` (`light | dark`, default `light`) and `h` (int, default `860`). Only `form` is interactive inside the board: «ثبت هزینه» calls `open()` and the dialog's close/«انصراف» call `close()`. Everything else is static. There is **no** `Expenses-Dark` artboard, although the `theme` prop exists and works.

---

## 1. Layout

### Desktop (1440 × 860)

```
┌ sidebar 264 (right) ┬──────────────────── content 1176 ─────────────────────┐
│                     │ top bar 64: «هزینه‌ها»                                 │
│                     ├───────────────────────────────────────────────────────┤
│                     │ main: padding 24 / 32 / 40 · column · gap 20          │
│                     │ ┌─ toolbar row (space-between) ─────────────────────┐ │
│                     │ │ [search 240] [دسته: همه] [۱۴۰۵/۰۶/۰۱ تا ۳۱]  │ [ثبت هزینه] │
│                     │ └───────────────────────────────────────────────────┘ │
│                     │ ┌─ body row: flex · gap 24 · align-items:flex-start ─┐ │
│                     │ │ ┌ list card (grow, 728) ┐ ┌ aside 360 ──────────┐ │ │
│                     │ │ │ thead 40               │ │ card «به تفکیک دسته» │ │ │
│                     │ │ │ 8 × td 52 = 416        │ │  5 × (label+meter 8) │ │ │
│                     │ │ │ tfoot 52               │ ├──── gap 20 ─────────┤ │ │
│                     │ │ │ = 508 tall             │ │ card «دسته‌ها»        │ │ │
│                     │ │ └────────────────────────┘ │  5 × row 40 + note   │ │ │
│                     │ │                            └──────────────────────┘ │ │
│                     │ └───────────────────────────────────────────────────┘ │
└─────────────────────┴───────────────────────────────────────────────────────┘
```

- `main` padding `24px 32px 40px`, `display:flex; flex-direction:column; gap:20px` → inner width **1112**.
- Body row: `display:flex; gap:24px; align-items:flex-start`. List card `.card.grow` (`flex-grow:1; min-width:0`) → **728** at 1440. Aside: `width:360px; flex-shrink:0; display:flex; flex-direction:column; gap:20px`.
- Toolbar: outer `display:flex; align-items:center; justify-content:space-between; gap:12px`; left cluster `display:flex; gap:10px; align-items:center`.
  1. Search — `.ig` at `width:240px`, `.pfx` search icon 16 on the inline start, `.input` 40 tall (`padding-right:38px` because of the prefix).
  2. Category filter — `.select` with `width:auto; gap:10px`, 40 tall: muted «دسته:» + bold «همه» + chevron-down 14.
  3. Date range — `.select` with `width:auto; gap:10px`: calendar icon 16 + bold tabular range + chevron-down 14.
  4. Right: `.btn.btn-primary` (40 tall) with a plus-16 icon.
- List card is `overflow:hidden` with `aria-label="فهرست هزینه‌ها"`; `.tbl` header cells 40 tall on `--surface-2`, body cells 52, footer on `--surface-2` at `font-weight:700`.
- Category meters: `.meter` overridden to `height:8px`, one `<i>` at `width:{{c.p}}%` filled with `var(--bar-a)`; each block is wrapped in a native `title` tooltip.
- The category manager's rows are 40 tall with `padding:0 8px` and a `1px solid var(--border)` bottom rule; the card body is `padding:8px 12px` (not `.card-b`).

#### Column order (desktop table)

| # | header (verbatim) | align | width | content |
|---|---|---|---|---|
| 1 | `تاریخ` | start | auto | `.num.muted2` — Jalali date, Persian digits |
| 2 | `دسته` | start | auto | `.chip` (neutral category chip) |
| 3 | `شرح` | start | auto (absorbs slack) | plain text |
| 4 | `مبلغ (تومان)` | end (`.n`) | auto | `.num.b` — amount, no unit suffix (the unit is in the header) |
| 5 | *(empty)* | — | **56px** | `.btn.btn-ghost.btn-icon.btn-sm`, edit-16, `aria-label="ویرایش"` |

Footer row: `colspan=3` label, then the total in column 4, then an empty cell under the action column.

#### Field order (the «ثبت هزینه» dialog)

`.dialog` `role="dialog"` `aria-labelledby="ef"`, `position:absolute; top:140px; left:50%; margin-left:-250px; width:500px` → a 500-wide panel horizontally centred on the page (left edge 470 at 1440), 140 from the top, over a full-page `.overlay`. Header `.d-h` (`justify-content:space-between`), body `.d-b` (gap 14), footer `.d-f` (`--surface-2`, actions start-aligned).

1. **تاریخ** — `.select` showing `<b class="num">۱۴۰۵/۰۶/۳۱</b>` + calendar-16. Half width.
2. **دسته** — `.select` showing `تبلیغات` + chevron-down-14. Half width.
   (1 and 2 sit in `grid-template-columns: repeat(2, minmax(0,1fr)); gap:12px`.)
3. **شرح** — `.input`, `id="et"`, full width, prefilled.
4. **مبلغ** — `.ig` with `.input.input-num` + `.sfx` «تومان», full width, plus one `.help` line.

Footer: `.btn.btn-primary` «ثبت هزینه» first (inline start), `.btn.btn-outline` «انصراف» second. The header carries a ghost icon close button, `aria-label="بستن"`.

### Mobile (390 × 1080)

```
┌──────────────── 390 ────────────────┐
│ mobile bar 56: ☰ · logo · «هزینه‌ها» │
├─────────────────────────────────────┤
│ main: padding 14 / 16 / 100 · gap 12│
│ [شهریور ۱۴۰۵ 36] [همه دسته‌ها 36]    │  ← flex, gap 8
│ ┌ summary card (pad 14, gap 10) ───┐│
│ │ جمع شهریور            ۲۷٬۰۰۰٬۰۰۰ ││  ← .sl.total (value 20px)
│ │ ▓▓▓▓▓▓▓▓░░░░░░▒▒▒░░▒▒  12px bar  ││  ← 5 segments, gap 2, radius 6
│ │ اجاره ۴۴٪ تبلیغات ۳۱٪ … (wrap)   ││
│ └──────────────────────────────────┘│
│ ┌ expense card ── 8 of these ──────┐│
│ │ شرح (13/700)              مبلغ   ││  ← pad 12/14, space-between
│ │ تاریخ · دسته (12, muted)          ││
│ └──────────────────────────────────┘│
│                                     │
├─────────────────────────────────────┤
│ fixed bottom bar: [+ ثبت هزینه] 48  │  ← pad 12/16/20, surface, top border
└─────────────────────────────────────┘
```

- `main` padding `14px 16px 100px` (the bottom padding clears the fixed bar), `gap:12px` → content width **358**.
- Filters are two `.btn.btn-outline.btn-sm` forced to `height:36px` — **below the 44px touch minimum used elsewhere** (see Open questions).
- Summary card: `.sl.total` row, then the stacked bar, then the legend (`.t-cap.muted2`, `flex-wrap`, `gap:4px 12px`).
- Stacked bar: `height:12px; display:flex; gap:2px; border-radius:6px; overflow:hidden`, `role="img"` `aria-label="سهم دسته‌ها"`. Widths and fills, in order: `44% --bar-a`, `31% --bar-c`, `9% --bar-b`, `8% --border-strong`, `8% --surface-3`.
- Expense cards: `padding:12px 14px; display:flex; justify-content:space-between; align-items:center; gap:8px`; the text column is `min-width:0` (so long descriptions can shrink) with description `.t-sm.b` above `.t-cap.muted` «date · category»; amount is `.num.b.t-sm`.
- Bottom bar: `position:absolute; left:0; right:0; bottom:0; padding:12px 16px 20px; background:var(--surface); border-top:1px solid var(--border)`; the button is `.btn.btn-primary.btn-lg` at `width:100%` with a plus-18 icon.
- Mobile has **no** category-breakdown card beyond the stacked bar, **no** category manager, and **no** form: tapping «ثبت هزینه» has no designed destination.

---

## 2. Copy (verbatim)

### Toolbar and chrome

| element | string |
|---|---|
| top-bar title / mobile bar title | `هزینه‌ها` |
| search placeholder | `جستجوی شرح` |
| search `aria-label` | `جستجو` |
| category filter, muted part | `دسته:` |
| category filter, bold part | `همه` |
| date range button | `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` |
| primary action (desktop toolbar, dialog footer, mobile bottom bar) | `ثبت هزینه` |
| list card `aria-label` | `فهرست هزینه‌ها` |
| mobile month filter | `شهریور ۱۴۰۵` |
| mobile category filter | `همه دسته‌ها` |

### Desktop table

Headers, in order: `تاریخ` · `دسته` · `شرح` · `مبلغ (تومان)` · *(empty)*.
Row action `aria-label`: `ویرایش`.

All eight rows, in the exact order they are rendered (newest first — the `EXP` array order, no sorting is applied):

| # | تاریخ | دسته | شرح | مبلغ (تومان) |
|---|---|---|---|---|
| 1 | `۱۴۰۵/۰۶/۲۶` | `متفرقه` | `تعمیر پرینتر برچسب` | `۱٬۵۰۰٬۰۰۰` |
| 2 | `۱۴۰۵/۰۶/۲۲` | `متفرقه` | `لوازم‌التحریر و چاپ برچسب` | `۷۰۰٬۰۰۰` |
| 3 | `۱۴۰۵/۰۶/۱۸` | `تبلیغات` | `همکاری با صفحه موسیقی` | `۳٬۵۰۰٬۰۰۰` |
| 4 | `۱۴۰۵/۰۶/۱۲` | `حمل‌ونقل داخلی` | `پیک رساندن مرسوله‌ها به پست` | `۱٬۹۰۰٬۰۰۰` |
| 5 | `۱۴۰۵/۰۶/۰۵` | `تبلیغات` | `تبلیغ اینستاگرام — کمپین تور` | `۵٬۰۰۰٬۰۰۰` |
| 6 | `۱۴۰۵/۰۶/۰۳` | `اینترنت و نرم‌افزار` | `هاست و دامنه وب‌سایت` | `۱٬۴۰۰٬۰۰۰` |
| 7 | `۱۴۰۵/۰۶/۰۳` | `اینترنت و نرم‌افزار` | `اشتراک نرم‌افزار طراحی` | `۱٬۰۰۰٬۰۰۰` |
| 8 | `۱۴۰۵/۰۶/۰۱` | `اجاره انبار` | `اجاره شهریور` | `۱۲٬۰۰۰٬۰۰۰` |

Footer row (the label is a literal in the template, **not** interpolated):

```
جمع هزینه‌های شهریور (۸ مورد)            ۲۷٬۰۰۰٬۰۰۰
```

Note the em dash in row 5 (`تبلیغ اینستاگرام — کمپین تور`) and the ZWNJ in `لوازم‌التحریر`, `حمل‌ونقل`, `نرم‌افزار`, `وب‌سایت`, `مرسوله‌ها`, `هزینه‌های`, `تفکیک`-adjacent labels and `دسته‌ها`.

### Card «به تفکیک دسته»

Header: `به تفکیک دسته` · header value `۲۷٬۰۰۰٬۰۰۰`.
Each row's native tooltip is `{{c.name}}: {{c.aT}} تومان`, e.g. `اجاره انبار: ۱۲٬۰۰۰٬۰۰۰ تومان`.

| order | دسته | مبلغ | درصد | meter width |
|---|---|---|---|---|
| 1 | `اجاره انبار` | `۱۲٬۰۰۰٬۰۰۰` | `۴۴٪` | 44% |
| 2 | `تبلیغات` | `۸٬۵۰۰٬۰۰۰` | `۳۱٪` | 31% |
| 3 | `اینترنت و نرم‌افزار` | `۲٬۴۰۰٬۰۰۰` | `۹٪` | 9% |
| 4 | `متفرقه` | `۲٬۲۰۰٬۰۰۰` | `۸٪` | 8% |
| 5 | `حمل‌ونقل داخلی` | `۱٬۹۰۰٬۰۰۰` | `۷٪` | 7% |

### Card «دسته‌ها»

Header: `دسته‌ها` · action `دسته جدید` (outline, small, plus-14).
Rows: the same five category names in the same order, each with an icon button `aria-label="ویرایش دسته"`.
Footer note:

```
دسته‌ای که هزینه دارد حذف نمی‌شود؛ فقط غیرفعال می‌شود.
```

### Mobile summary card

| element | string |
|---|---|
| total label | `جمع شهریور` |
| total value | `۲۷٬۰۰۰٬۰۰۰` |
| bar `aria-label` | `سهم دسته‌ها` |
| legend | `اجاره انبار ۴۴٪` · `تبلیغات ۳۱٪` · `اینترنت ۹٪` · `متفرقه ۸٪` · `حمل ۷٪` |

The mobile legend abbreviates two names (`اینترنت` for `اینترنت و نرم‌افزار`, `حمل` for `حمل‌ونقل داخلی`); the desktop card spells both out.

### The «ثبت هزینه» dialog (`Expenses-Form`)

| element | string |
|---|---|
| dialog title | `ثبت هزینه` |
| close button `aria-label` | `بستن` |
| label 1 | `تاریخ` |
| value 1 | `۱۴۰۵/۰۶/۳۱` |
| label 2 | `دسته` |
| value 2 | `تبلیغات` |
| label 3 | `شرح` |
| value 3 | `تبلیغ پست معرفی وینیل نسخه رنگی` |
| label 4 | `مبلغ` |
| value 4 | `۲٬۵۰۰٬۰۰۰` |
| amount suffix | `تومان` |
| amount help | `در ردیف «هزینه‌های عملیاتی» سود و زیان همان ماه حساب می‌شود.` |
| submit | `ثبت هزینه` |
| cancel | `انصراف` |

Both `شرح` and `مبلغ` are rendered with `value="…"` (prefilled, not placeholders) — no placeholder copy exists for either field.

### Empty state (desktop, `[[STATES:…]]` arguments 1–4)

Icon `wallet` at 28 in a 56px `.e-art` tile; `.empty` padding `96px 24px`.

```
هنوز هزینه‌ای ثبت نشده
هزینه‌های عملیاتی مثل اجاره، تبلیغات و اینترنت را ثبت کنید تا سود خالص واقعی در گزارش‌ها دیده شود.
[+ ثبت اولین هزینه]      ← .btn.btn-primary, plus-16
```

### Empty state (mobile, `[[MSTATES:…]]`)

`.empty` padding `48px 20px`, CTA is `.btn.btn-primary.btn-lg`.

```
هنوز هزینه‌ای ثبت نشده
هزینه‌های عملیاتی را ثبت کنید تا سود خالص درست محاسبه شود.
[+ ثبت هزینه]
```

### Error state

The macro builds the title from its 5th argument plus the fixed words ` بارگذاری نشد`; the body and the retry label are fixed for the whole app. Icon `cloudoff` at 28 on `--loss-soft` / `--loss`.

Desktop (5th argument `فهرست هزینه‌ها`):

```
فهرست هزینه‌ها بارگذاری نشد
اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.
[↻ تلاش دوباره]      ← .btn.btn-outline, refresh-16
```

Mobile (5th argument `هزینه‌ها`):

```
هزینه‌ها بارگذاری نشد
اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.
[↻ تلاش دوباره]
```

Unlike the record-sale screen, **no error code** (`EXPENSES_5xx`) is shown here — the macro's error board has no code line.

### Loading state

Skeletons only, no text. `aria-busy="true"`, `aria-label="در حال بارگذاری"` on the wrapping section, `display:flex; flex-direction:column; gap:12px`.

- Desktop: one `.sk` 20 tall × 180 wide (the faux heading), then **8** `.sk` blocks 40 tall, `border-radius:10px`.
- Mobile: the same heading block, then **5** `.sk` blocks 84 tall, `border-radius:10px`.

The toolbar row stays visible and interactive in all three non-ready states — only the body is replaced (the `sc-if` wraps just the list + aside).

---

## 3. Interactive states designed

| element | states designed |
|---|---|
| Search input | default only (`.input` hover/focus/`is-error` exist in the system; no filtered result or "no match" board here) |
| Category filter `.select` | default only — the open menu is not drawn |
| Date-range `.select` | default only — the Jalali range picker is the shared component from `design-system.md` § Calendar; no Expenses-specific board |
| «ثبت هزینه» (toolbar / bottom bar) | default, hover, `:focus-visible` ring; opens the dialog (`form → true`) |
| Table row | default + `.tbl tbody tr:hover td` → `--surface-2` background |
| Row edit button | default, hover, focus — **no target designed** (no edit dialog, no delete) |
| Table footer | static total row, always visible |
| Category meter | static; each bar carries a native `title` tooltip and the value + percent are written in the label row (no hover-only data) |
| Category manager row | default + edit icon button; «دسته جدید» has no designed dialog |
| Dialog | closed / open; closes via the header ✕ or «انصراف»; overlay is `--overlay` over the full page |
| Dialog fields | default only — no focus, error, or disabled variants drawn |
| Dialog submit | default only — no loading («در حال ثبت…») or disabled variant drawn |
| Screen | ready · empty · loading · error (desktop and mobile), light theme only |
| Mobile filters | default only; both are 36px tall |

Focus rings follow the system: `box-shadow: 0 0 0 3px var(--ring)` on every interactive element. Nothing on this screen conveys meaning by colour alone — every meter and bar segment is paired with a written category name and percentage.

### Chart constraint (deliberate)

Both charts here are **single-hue with direct value labels**, per `design-system.md` § "Channels and chart bars": the five channel colours (`--ch-web`, `--ch-insta`, `--ch-wholesale`, `--ch-inperson`, `--ch-other`) are for small inline labels only and **are not used as a chart palette**, because that five-colour set fails the colour-blind / categorical-contrast check. Concretely:

- Desktop breakdown: every bar is `var(--bar-a)`; separation comes from one row per category, with the name, the amount in bold and the percent written on the row.
- Mobile stacked bar: the five segments step down a **neutral** ramp — `--bar-a`, `--bar-c`, `--bar-b`, `--border-strong`, `--surface-3` — and the legend repeats every category with its percentage, so the bar is decorative reinforcement rather than the only key. It carries `role="img"` with `aria-label="سهم دسته‌ها"`.

---

## 4. Validation

**None designed.** The dialog in `Expenses-Form` has no error, warning, or disabled state, and no error copy exists anywhere in either artboard. Specifically, none of the following is designed, and none should be invented without a decision:

| candidate rule | status |
|---|---|
| `شرح` required / non-empty | no rule, no message |
| `مبلغ` required, `> 0`, non-negative | no rule, no message (the field is a free `.input.input-num`; `num()` would coerce any junk to `0`) |
| `دسته` required | no rule — the select is prefilled with `تبلیغات`, and there is no empty/placeholder variant |
| `تاریخ` required / inside the selected period / not in the future | no rule; the field is prefilled with today (`۱۴۰۵/۰۶/۳۱`) |
| duplicate expense detection | not designed |
| submit disabled while invalid | not designed — the primary button has no `disabled` variant on this screen |
| deleting a category that has expenses | **prevented by design, stated as a note, not as an error**: `دسته‌ای که هزینه دارد حذف نمی‌شود؛ فقط غیرفعال می‌شود.` |

The only guidance copy in the form is the help line under `مبلغ`, which explains the *effect* of saving rather than constraining input: `در ردیف «هزینه‌های عملیاتی» سود و زیان همان ماه حساب می‌شود.`

---

## 5. Logic

The board's JS is small; all of it is derivation from one array.

### Source data

```js
var EXP = [
  ['1405/06/26', 'متفرقه', 'تعمیر پرینتر برچسب', 1500000],
  ['1405/06/22', 'متفرقه', 'لوازم‌التحریر و چاپ برچسب', 700000],
  ['1405/06/18', 'تبلیغات', 'همکاری با صفحه موسیقی', 3500000],
  ['1405/06/12', 'حمل‌ونقل داخلی', 'پیک رساندن مرسوله‌ها به پست', 1900000],
  ['1405/06/05', 'تبلیغات', 'تبلیغ اینستاگرام — کمپین تور', 5000000],
  ['1405/06/03', 'اینترنت و نرم‌افزار', 'هاست و دامنه وب‌سایت', 1400000],
  ['1405/06/03', 'اینترنت و نرم‌افزار', 'اشتراک نرم‌افزار طراحی', 1000000],
  ['1405/06/01', 'اجاره انبار', 'اجاره شهریور', 12000000]
];
```

One expense = `{ date, category, description, amount }`. There is no id, no attachment, no supplier link, no order link, no VAT/tax field, and no currency field (everything is integer Rial; Toman is display only).

### Row rendering

```js
rows: EXP.map(function (e) { return { d: faD(e[0]), c: e[1], t: e[2], aT: fa(e[3]) }; })
```

`faD()` only converts digits, so the date keeps its `/` separators (`۱۴۰۵/۰۶/۲۶`); `fa()` adds the `٬` thousands separator and Persian digits. **The array order is the render order** — the list is not sorted by the component, it just happens to be stored newest-first. Both boards (desktop and mobile) use the identical array and the identical mapping.

### Category breakdown

```js
var tot = {}, sum = 0;
EXP.forEach(function (e) { tot[e[1]] = (tot[e[1]] || 0) + e[3]; sum += e[3]; });
var cats = Object.keys(tot).sort(function (a, b) { return tot[b] - tot[a]; }).map(function (k) {
  var p = tot[k] / sum * 100;
  return { name: k, aT: fa(tot[k]), p: Math.round(p), pT: faD(Math.round(p)) + '٪' };
});
```

- Categories are **derived from the expenses present in the period**, sorted by amount descending. They are not a stored master list.
- `p` is used for both the meter width and the printed percent, so the bar and the number can never disagree — but the five rounded percents sum to **۹۹٪**, not ۱۰۰٪ (see Sample data). The design accepts that; no "other/rounding" row exists.
- The «دسته‌ها» manager card iterates **the same `cats` array**, so it can only ever show categories that already have an expense in the selected range. A category with no expenses this month is invisible here, and the note about deactivating rather than deleting implies a persisted category entity that this board does not model.

### Relationship to the rest of the app

- **P&L.** The period sum is the single «هزینه‌های عملیاتی» line of the profit & loss statement — `−۲۷٬۰۰۰٬۰۰۰`, subtracted after gross profit. See `../logic/formulas.md` §7 for the full statement; the reports screen (`12-reports.md`) shows the same five-category breakdown again in its «ضایعات و هزینه‌ها» tab, with identical amounts and percentages, so both screens must read one source.
- **Expenses are never allocated to orders.** They do not touch order profit, per-product profit, or the shipping report. In particular `حمل‌ونقل داخلی` (`۱٬۹۰۰٬۰۰۰`, the courier who takes parcels to the post office) is an operating expense and is deliberately **not** part of the postage figures: the store-wide postage estimate is `جمع پرداختی ÷ جمع سفارش‌ها` over the last 3 payments = **۱۹۹٬۲۷۳**, and estimate-versus-actual is reconciled by the P&L's own «مغایرت هزینه پست» line, not here. See `../logic/formulas.md` §2.
- **Nothing on this screen touches stock or the P&L's «ضایعات» line.** Waste and stock corrections are recorded on the adjustments screen; corrections never reach the P&L at all, and waste is valued at the item's cost on the day the waste was recorded. See `../logic/formulas.md` §8.
- **Period boundary.** Everything on the board is one Jalali month (`۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱`, today = ۳۱ شهریور ۱۴۰۵). The footer label and the mobile total label hardcode the month name «شهریور» and the footer hardcodes the count «(۸ مورد)» — both must become interpolations in the build.

---

## 6. Sample data used

Full set in `../data/sample-data.md` § "Expenses (شهریور) — total 27,000,000". Eight expenses, one Jalali month.

### Rows and total

| تاریخ | دسته | شرح | مبلغ |
|---|---|---|---|
| ۱۴۰۵/۰۶/۲۶ | متفرقه | تعمیر پرینتر برچسب | 1,500,000 |
| ۱۴۰۵/۰۶/۲۲ | متفرقه | لوازم‌التحریر و چاپ برچسب | 700,000 |
| ۱۴۰۵/۰۶/۱۸ | تبلیغات | همکاری با صفحه موسیقی | 3,500,000 |
| ۱۴۰۵/۰۶/۱۲ | حمل‌ونقل داخلی | پیک رساندن مرسوله‌ها به پست | 1,900,000 |
| ۱۴۰۵/۰۶/۰۵ | تبلیغات | تبلیغ اینستاگرام — کمپین تور | 5,000,000 |
| ۱۴۰۵/۰۶/۰۳ | اینترنت و نرم‌افزار | هاست و دامنه وب‌سایت | 1,400,000 |
| ۱۴۰۵/۰۶/۰۳ | اینترنت و نرم‌افزار | اشتراک نرم‌افزار طراحی | 1,000,000 |
| ۱۴۰۵/۰۶/۰۱ | اجاره انبار | اجاره شهریور | 12,000,000 |

```
1,500,000 + 700,000 + 3,500,000 + 1,900,000 + 5,000,000 + 1,400,000 + 1,000,000 + 12,000,000
= 27,000,000          → footer «جمع هزینه‌های شهریور (۸ مورد)» ۲۷٬۰۰۰٬۰۰۰
                      → mobile «جمع شهریور» ۲۷٬۰۰۰٬۰۰۰
                      → «به تفکیک دسته» card header ۲۷٬۰۰۰٬۰۰۰
                      → P&L «هزینه‌های عملیاتی» −۲۷٬۰۰۰٬۰۰۰
```

### Category totals, percentages and bar widths

| دسته | arithmetic | total | raw % | shown (`Math.round`) | meter |
|---|---|---|---|---|---|
| اجاره انبار | 12,000,000 | 12,000,000 | 44.444% | `۴۴٪` | 44% |
| تبلیغات | 3,500,000 + 5,000,000 | 8,500,000 | 31.481% | `۳۱٪` | 31% |
| اینترنت و نرم‌افزار | 1,400,000 + 1,000,000 | 2,400,000 | 8.889% | `۹٪` | 9% |
| متفرقه | 1,500,000 + 700,000 | 2,200,000 | 8.148% | `۸٪` | 8% |
| حمل‌ونقل داخلی | 1,900,000 | 1,900,000 | 7.037% | `۷٪` | 7% |
| **جمع** | | **27,000,000** | 100% | **۹۹٪** (rounding) | 99% |

Cross-check of the sort order: 12,000,000 > 8,500,000 > 2,400,000 > 2,200,000 > 1,900,000 — the rendered order matches `sort((a,b) => tot[b] - tot[a])`.

### Mobile stacked bar vs. the computed shares

| segment | width in the artboard | fill | computed share |
|---|---|---|---|
| 1 — اجاره انبار | 44% | `--bar-a` | 44% ✓ |
| 2 — تبلیغات | 31% | `--bar-c` | 31% ✓ |
| 3 — اینترنت و نرم‌افزار | 9% | `--bar-b` | 9% ✓ |
| 4 — متفرقه | 8% | `--border-strong` | 8% ✓ |
| 5 — حمل‌ونقل داخلی | **8%** | `--surface-3` | **7%** ✗ |

The fifth segment is hardcoded at `8%` so the widths sum to 100, while its legend reads `حمل ۷٪`. The desktop meter for the same category is 7%. This is a hardcoded-artboard artifact, not a rule — the implementation should drive all five widths from the computed shares and decide how to absorb the 1-point rounding gap (see Open questions).

### Dialog sample values

`تاریخ` ۱۴۰۵/۰۶/۳۱ (today) · `دسته` تبلیغات · `شرح` تبلیغ پست معرفی وینیل نسخه رنگی · `مبلغ` ۲٬۵۰۰٬۰۰۰ تومان.
Saving it would make تبلیغات 11,000,000 and the month 29,500,000 — **the artboard does not show that after-state**; the board behind the dialog still shows the pre-save numbers.

---

## 7. Open questions for this screen

- **No edit or delete flow.** Every row has an `aria-label="ویرایش"` button and every category an `aria-label="ویرایش دسته"` button, but no edit dialog, no pre-filled variant of the form, no delete action and no confirmation are designed. Decide whether the add dialog doubles as the edit dialog (title, submit label) and whether an expense can be deleted after it has been counted in a closed month's P&L.
- **Mobile cannot create an expense.** The mobile board has a full-width «ثبت هزینه» button with nothing designed behind it — no bottom sheet, no full-screen form, no route. Decide the mobile form pattern (the app's precedent is the record-sale bottom sheet).
- **Category model is undefined.** Categories are derived from the expenses present in the range, yet the UI has «دسته جدید» and «ویرایش دسته» and promises `دسته‌ای که هزینه دارد حذف نمی‌شود؛ فقط غیرفعال می‌شود.` That requires a stored category entity with an active/inactive flag, a create dialog and a rename dialog — none of which are drawn, and no place shows inactive categories. The five names in the sample (`اجاره انبار`، `تبلیغات`، `اینترنت و نرم‌افزار`، `متفرقه`، `حمل‌ونقل داخلی`) are sample data, not a decided seed list.
- **No validation at all**, as listed in §4 — in particular whether `مبلغ` may be zero or negative (a negative expense would silently reduce the P&L line), whether `شرح` is required, and whether an expense may be dated outside the selected period or in the future.
- **Filters are decorative.** Search, category and date-range controls are static: no open menu, no applied-filter chips, no "no results for «…»" board (contrast the product picker's `محصولی با «<query>» پیدا نشد.`), and no designed interaction between the filters and either the footer total or the breakdown card — it is unstated whether «به تفکیک دسته» follows the filtered set or the whole period.
- **Rounding of the percentages is unresolved**: the shown shares sum to ۹۹٪ on desktop, and the mobile bar hides that by hardcoding the last segment at 8% against a legend that says ۷٪. Decide one rule (largest-remainder, or one decimal place) and apply it to both, and to the identical breakdown in `12-reports.md`.
- **Hardcoded strings that must become interpolations**: the footer `جمع هزینه‌های شهریور (۸ مورد)` and the mobile `جمع شهریور` embed the month name and the row count; the desktop date-range button, the mobile month button and the dialog's date all embed ۱۴۰۵/۰۶ literals.
- **No dark artboard** (`Expenses-Dark` does not exist) even though the `theme` prop is wired, so the dark rendering of the meters, the category chips and the dialog is unverified.
- **Mobile filter buttons are 36px tall**, below the ≥44px touch target the rest of the mobile design holds itself to (mobile bar buttons, bottom CTA, record-sale steppers). Confirm whether that is intended or should be raised to 44.
- **Empty state ambiguity**: the empty board is written for "no expenses have ever been recorded" (`ثبت اولین هزینه`), but it is also what a period filter with no matches would land on. No separate empty-for-this-range copy exists.
- **No export.** The reports screen offers Excel/PDF; this screen offers neither, although it is the natural place to export a month's expense ledger. Not designed, not refused.
