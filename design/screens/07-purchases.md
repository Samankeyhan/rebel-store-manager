# 07 — خرید (Purchases)

Route: `/purchases` · sidebar key `purchases` · page title in top bar: **خرید**
(Mobile top bar carries a different title — **ثبت خرید** — because the mobile screen leads with the entry form, not the list. See §1.)

The screen where stock arrives and cost is set. A purchase is one line: one item, one quantity, one total amount paid. From those two numbers the screen derives the unit cost of *this* purchase and, more importantly, the **new weighted-average cost** of the item, previewed live before the purchase is saved (see `../logic/formulas.md` §3). Desktop is a list of past purchases with the entry form in a right-side drawer; mobile is the form itself with a short "recent purchases" tail. There is no per-line freight or extra-cost field anywhere — the single «مبلغ کل پرداختی» is the whole cost basis (§5, §7).

Artboards: `Purchases.dc.html` (default, list only), `Purchases-Form` (`form="true"` — the drawer open, this is the artboard for the weighted-average preview), `Purchases-States` (empty · loading · error, three 1440×760 frames side by side), `PurchasesMobile`, `PurchasesMobile-States` (three 390×844 frames).
Props on `Purchases`: `form` (boolean, default `false`), `state` (`ready | empty | loading | error`), `theme` (`light | dark`), `h` (int, default 900). **No `-Dark` artboard was generated for this screen** (`extra_dark=False` in `layout.py`), although the `theme` prop exists.
The quantity and total inputs in the drawer are live: `onQty` / `onTotal` re-derive the unit cost, the new average and the delta on every change.

---

## 1. Layout

### Desktop (1440 × 900 default; the states frames are 1440 × 760)

```
┌ sidebar 264 (right) ┬──────────────────── content 1176 ─────────────────────┐
│                     │ top bar 64: «خرید»                                    │
│                     ├───────────────────────────────────────────────────────┤
│                     │ main: padding 24 32 40, flex-column, gap 20           │
│                     │                                                       │
│                     │ [0] toolbar row (space-between, h 40)                 │
│                     │     right group (gap 10, wrap):                       │
│                     │       search 240 · seg 3 · تأمین‌کننده · date range     │
│                     │     left: [＋ ثبت خرید] primary 40                     │
│                     │                                                       │
│                     │ [1] ┌ card, overflow hidden ───────────────────────┐  │
│                     │     │ thead 40  تاریخ کالا نوع تأمین‌کننده …          │  │
│                     │     │ 6 rows × 52                                   │  │
│                     │     │ tfoot 52  جمع خریدهای شهریور …                 │  │
│                     │     └───────────────────────────────────────────────┘  │
└─────────────────────┴───────────────────────────────────────────────────────┘

when form = true, over the WHOLE 1440 frame (.rs is position:relative; overflow:hidden):
  .overlay  inset 0
  aside.dialog  position:absolute; top:0; left:0; bottom:0; width:500;
                border-radius: 0 14px 14px 0      ← flush to the physical left edge,
                                                     rounded on the side facing the page
```

- `main`: `padding: 24px 32px 40px; display:flex; flex-direction:column; gap:20px` (from the `[[PAGE:]]` macro).
- Card total height at 6 rows: `40 (thead) + 6×52 (tbody) + 52 (tfoot) = 404` + 1px borders.
- The drawer is a sibling of the page column, not a child of `main`, so it covers the sidebar too.

### Desktop table — column order, exact

| # | header | align | cell classes | sample cell |
|---|---|---|---|---|
| 1 | `تاریخ` | start | `num muted2` | `۱۴۰۵/۰۶/۲۹` |
| 2 | `کالا` | start | `b` | `کارتن جعبه استاندارد` |
| 3 | `نوع` | start | `badge st-paid` / `badge st-done` | `ماده` / `محصول` |
| 4 | `تأمین‌کننده` | start | — | `بسته‌بندی کارتن‌سازان` |
| 5 | `مقدار` | `n` | `n num` | `۱۰۰ عدد` |
| 6 | `مبلغ پرداختی (تومان)` | `n` | `n num b` | `۶٬۰۰۰٬۰۰۰` |
| 7 | `بهای واحد (تومان)` | `n` | `n num` | `۶۰٬۰۰۰` |

`tfoot`: one row — `colspan="5"` carrying `جمع خریدهای شهریور (۶ مورد)`, then the amount total in column 6, then an **empty cell** in column 7 (no total unit cost, correctly).
`.tbl th` is 40px on `--surface-2`; `.tbl td` is 52px; `tbody tr:hover td` fills with `--surface-2`.

### Desktop toolbar — element order, exact

1. Search: `.ig` `width:240px`, `.pfx` search icon 16 on the start side, `input.input` placeholder `جستجوی کالا`, `aria-label="جستجو"`.
2. `.seg` (3 buttons, h 40 incl. its 3px padding): `همه` (`.on`) · `مواد` · `محصولات`.
3. `.select` `width:auto; gap:10px`: `<span class="muted">تأمین‌کننده:</span>` + `<span class="b">همه</span>` + chevron-down 14.
4. `.select` `width:auto; gap:10px`: calendar icon 16 + `<span class="b num">۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱</span>` + chevron-down 14.
5. (left end) `button.btn.btn-primary` with plus 16: `ثبت خرید` → `onClick = open` → `showForm = true`.

### Drawer — field order, exact

`aside.dialog`, `role="dialog"`, `aria-labelledby="pf"`; header 20/24 padding with a bottom border, body `padding:18px 24px; gap:14px`, footer `.d-f` with `border-radius: 0 0 14px 0`.

1. Header: `h2#pf.t-h2` → `ثبت خرید`; close `button.btn.btn-ghost.btn-icon.btn-sm`, `aria-label="بستن"`, x-icon 16 → `close`.
2. **نوع کالا** — `.field` with a `.seg` at `width:100%`, two buttons each `flex-grow:1`: `ماده یا بسته‌بندی` (`.on`) · `محصول آماده`.
3. **کالا** — `.field` + `button.select`: `<span class="b">صفحه خام وینیل ۱۲ اینچ</span>` and a `.stock` pill `موجودی ۳۸ عدد`. (No chevron on this one; no picker popover was designed.)
4. **تأمین‌کننده** — `.field` + `button.select`: `کارخانه پرس صفحه آوا` + chevron-down 14.
5. Two-column grid `repeat(2, minmax(0,1fr)); gap:12px`:
   1. **مقدار** — `label for="pq"`, `.ig` → `input#pq.input.input-num value="{{qtyT}}" onChange="{{onQty}}"`, `.sfx` `عدد`.
   2. **مبلغ کل پرداختی** — `label for="pt"`, `.ig` → `input#pt.input.input-num value="{{totalT}}" onChange="{{onTotal}}"`, `.sfx` `تومان`.
6. **تاریخ خرید** — `.field` + `button.select`: calendar icon 16 + `<b class="num">۱۴۰۵/۰۶/۳۱</b>` on the start side, `<span class="t-cap muted">امروز</span>` on the end side.
7. **پیش‌نمایش بهای تمام‌شده** — `section` on `--surface-2`, radius 12, padding 14, gap 10, `aria-label="پیش‌نمایش بهای تمام‌شده"`:
   1. `.t-h3` heading (colour `--heading`).
   2. `.sl` row: `بهای واحد این خرید` → `{{unitT}} تومان`.
   3. The before/after box — `grid-template-columns: 1fr auto 1fr; gap:8px` on `--surface`, 1px border, radius 10, padding `10px 12px`:
      · right cell: caption `میانگین فعلی`, value `۶۲۰٬۰۰۰` at 17px, caption `۳۸ عدد در انبار`
      · middle: chevron-left 20 in `--text-3` (points from "current" toward "after" in RTL)
      · left cell: caption `میانگین پس از خرید`, value `{{afterT}}` bold 19px, caption `{{afterStockT}} عدد در انبار`
   4. The formula line (`t-cap muted num`, `line-height:1.8`) + the delta badge.
   5. The "future productions" note (`t-cap muted2`).
8. **یادداشت** — `label for="pn"` with `<span class="opt">(اختیاری)</span>`, `input#pn.input` placeholder `مثلاً: شماره فاکتور تأمین‌کننده`.
9. Footer `.d-f`: `button.btn.btn-primary` → `ثبت خرید`; `button.btn.btn-outline` → `انصراف` (`onClick = close`).

### Mobile (390 × 1140 default; the states frames are 390 × 844)

Top bar 56 (`MobileBar title="ثبت خرید"`), `main { padding: 14px 16px 100px; display:flex; flex-direction:column; gap:12px }`, plus a **fixed bottom action bar** — `position:absolute; left:0; right:0; bottom:0; padding:12px 16px 20px;` on `--surface` with a top border, holding one full-width `btn btn-primary btn-lg` (48px) `ثبت خرید` with a check icon 18.

```
┌──────────── 390 ─────────────┐
│ mobile bar 56 «ثبت خرید»      │
├──────────────────────────────┤
│ card 1 — the form (pad 14)   │
│  seg 2×40 grid               │
│  کالا select 48              │
│  تأمین‌کننده select 48         │
│  [مقدار 48] [تاریخ 48]  ←grid │
│  مبلغ کل پرداختی 48           │
├──────────────────────────────┤
│ card 2 — preview, surface-2  │
│  4 summary lines + caption   │
├──────────────────────────────┤
│ «خریدهای اخیر» (t-h3)         │
│ card 12/14  purchase 1       │
│ card 12/14  purchase 2       │
├──────────────────────────────┤
│ bottom bar 12/16/20 [ثبت خرید]│
└──────────────────────────────┘
```

Order on mobile, exact:

1. `.seg` as a `grid-template-columns: repeat(2, minmax(0,1fr))`, buttons 40px: `ماده یا بسته‌بندی` (`.on`) · `محصول آماده`.
2. **کالا** — `.select` 48px: `<span class="b">صفحه خام وینیل ۱۲ اینچ</span>` + `.stock` pill `۳۸ عدد` (shorter than desktop's `موجودی ۳۸ عدد`).
3. **تأمین‌کننده** — `.select` 48px: `کارخانه پرس صفحه آوا` + chevron-down 14.
4. Grid `repeat(2, minmax(0,1fr)); gap:8px`: **مقدار** (`input.input-num` 48px, `.sfx` `عدد`, value `۵۰`) and **تاریخ** (`.select` 48px, `<b class="num">۱۴۰۵/۰۶/۳۱</b>` + calendar icon 16).
5. **مبلغ کل پرداختی** — `input.input-num` 48px, `.sfx` `تومان`, value `۳۳٬۵۰۰٬۰۰۰`.
6. Preview card on `--surface-2`: `.t-h3` heading + three `.sl` rows (the third is `.sl.total`) + a `t-cap muted` formula caption.
7. `خریدهای اخیر` section heading (`t-h3`, `margin-top:4px`), then two compact cards (`padding:12px 14px`, space-between): bold name + `t-cap muted` meta on the start side, bold amount on the end side.

Mobile differences worth flagging for the build: there is **no list/table, no search, no type filter, no supplier filter, no date-range picker, no یادداشت field, no delta badge and no "future productions" note** on mobile. Mobile values are static in the artboard (not wired to `onQty`/`onTotal`).

---

## 2. Copy (verbatim)

### Desktop toolbar

| element | string |
|---|---|
| search placeholder | `جستجوی کالا` |
| search aria-label | `جستجو` |
| segment 1 (on) | `همه` |
| segment 2 | `مواد` |
| segment 3 | `محصولات` |
| supplier select, muted prefix | `تأمین‌کننده:` |
| supplier select, value | `همه` |
| date-range select | `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` |
| primary button | `ثبت خرید` |

### Desktop table headers

`تاریخ` · `کالا` · `نوع` · `تأمین‌کننده` · `مقدار` · `مبلغ پرداختی (تومان)` · `بهای واحد (تومان)`

Type badges: `ماده` (`badge st-paid`) · `محصول` (`badge st-done`).

### Desktop table rows (all six, verbatim — static markup in the artboard)

| تاریخ | کالا | نوع | تأمین‌کننده | مقدار | مبلغ پرداختی | بهای واحد |
|---|---|---|---|---|---|---|
| `۱۴۰۵/۰۶/۲۹` | `کارتن جعبه استاندارد` | `ماده` | `بسته‌بندی کارتن‌سازان` | `۱۰۰ عدد` | `۶٬۰۰۰٬۰۰۰` | `۶۰٬۰۰۰` |
| `۱۴۰۵/۰۶/۲۵` | `تی‌شرت خام مشکی L` | `ماده` | `تولیدی پوشاک سپید` | `۲۰ عدد` | `۵٬۲۰۰٬۰۰۰` | `۲۶۰٬۰۰۰` |
| `۱۴۰۵/۰۶/۲۰` | `وینیل نسخه رنگی` | `محصول` | `کارخانه پرس صفحه آوا` | `۵ عدد` | `۱۰٬۲۵۰٬۰۰۰` | `۲٬۰۵۰٬۰۰۰` |
| `۱۴۰۵/۰۶/۱۵` | `کاغذ پرکننده` | `ماده` | `بسته‌بندی کارتن‌سازان` | `۵ کیلوگرم` | `۴۵۰٬۰۰۰` | `۹۰٬۰۰۰` |
| `۱۴۰۵/۰۶/۱۰` | `نوار چسب لوگودار` | `ماده` | `چاپخانه نقش` | `۶ رول` | `۹۰۰٬۰۰۰` | `۱۵۰٬۰۰۰` |
| `۱۴۰۵/۰۶/۰۴` | `کاور چاپی وینیل` | `ماده` | `چاپخانه نقش` | `۵۰ عدد` | `۹٬۰۰۰٬۰۰۰` | `۱۸۰٬۰۰۰` |

Footer: `جمع خریدهای شهریور (۶ مورد)` · `۳۱٬۸۰۰٬۰۰۰`

### Drawer

| element | string |
|---|---|
| dialog title | `ثبت خرید` |
| close aria-label | `بستن` |
| field label | `نوع کالا` |
| segment 1 (on) | `ماده یا بسته‌بندی` |
| segment 2 | `محصول آماده` |
| field label | `کالا` |
| selected item | `صفحه خام وینیل ۱۲ اینچ` |
| stock pill | `موجودی ۳۸ عدد` |
| field label | `تأمین‌کننده` |
| selected supplier | `کارخانه پرس صفحه آوا` |
| field label | `مقدار` |
| quantity suffix | `عدد` |
| field label | `مبلغ کل پرداختی` |
| amount suffix | `تومان` |
| field label | `تاریخ خرید` |
| date value | `۱۴۰۵/۰۶/۳۱` |
| date caption | `امروز` |
| note label | `یادداشت` + `(اختیاری)` |
| note placeholder | `مثلاً: شماره فاکتور تأمین‌کننده` |
| primary button | `ثبت خرید` |
| secondary button | `انصراف` |

### Drawer — cost preview block

| element | string |
|---|---|
| section heading / aria-label | `پیش‌نمایش بهای تمام‌شده` |
| row label | `بهای واحد این خرید` |
| row value (sample) | `۶۷۰٬۰۰۰ تومان` |
| before caption | `میانگین فعلی` |
| before value | `۶۲۰٬۰۰۰` |
| before sub-caption | `۳۸ عدد در انبار` |
| after caption | `میانگین پس از خرید` |
| after value (sample) | `۶۴۸٬۴۰۹` |
| after sub-caption (sample) | `۸۸ عدد در انبار` |

Formula line (sample values interpolated; `{{totalT}}` and `{{afterStockT}}` are live):

```
میانگین موزون = (۳۸ × ۶۲۰٬۰۰۰ + ۳۳٬۵۰۰٬۰۰۰) ÷ ۸۸
```

Delta badge, immediately after the formula line, `margin-right: 6px` (sample): `+۲۸٬۴۰۹`

Note under the block:

```
تولیدهای بعدی «وینیل آلبوم اول» با بهای جدید محاسبه می‌شوند؛ تولیدهای گذشته تغییر نمی‌کنند.
```

### Desktop empty / loading / error (from `[[STATES:cart|…]]`)

The macro arguments **are** the copy. `[[STATES:cart|هنوز خریدی ثبت نشده|خرید مواد اولیه، بسته‌بندی یا محصولات آماده را ثبت کنید تا موجودی و بهای تمام‌شده خودکار به‌روز شود.|ثبت اولین خرید|فهرست خریدها]]` renders:

**Empty** — `section.card` → `.empty` with `padding: 96px 24px`, `.e-art` disc 56 with the cart icon 28:

- `.e-t` → `هنوز خریدی ثبت نشده`
- `.e-d` → `خرید مواد اولیه، بسته‌بندی یا محصولات آماده را ثبت کنید تا موجودی و بهای تمام‌شده خودکار به‌روز شود.`
- `button.btn.btn-primary` with plus 16 → `ثبت اولین خرید`

**Loading** — `section` with `aria-busy="true"`, `aria-label="در حال بارگذاری"`: one `.sk` 20×180 then **8** `.sk` rows 40px tall, radius 10, gap 12. No text.

**Error** — same `.empty` shell, `.e-art` on `--loss-soft`/`--loss` with the cloud-off icon 28:

- `.e-t` → `فهرست خریدها بارگذاری نشد`  *(the 5th macro argument + ` بارگذاری نشد`)*
- `.e-d` → `اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.`
- `button.btn.btn-outline` with the refresh icon 16 → `تلاش دوباره`

### Mobile copy

Top bar title: `ثبت خرید`. Bottom bar button: `ثبت خرید`.

Form: `ماده یا بسته‌بندی` · `محصول آماده` · `کالا` / `صفحه خام وینیل ۱۲ اینچ` / pill `۳۸ عدد` · `تأمین‌کننده` / `کارخانه پرس صفحه آوا` · `مقدار` (`۵۰`, suffix `عدد`) · `تاریخ` (`۱۴۰۵/۰۶/۳۱`) · `مبلغ کل پرداختی` (`۳۳٬۵۰۰٬۰۰۰`, suffix `تومان`).

Preview card:

| row | label | value |
|---|---|---|
| 1 | `پیش‌نمایش بهای تمام‌شده` (heading) | — |
| 2 | `بهای واحد این خرید` | `۶۷۰٬۰۰۰` |
| 3 | `میانگین فعلی (۳۸ عدد)` | `۶۲۰٬۰۰۰` |
| 4 (`.sl.total`) | `میانگین پس از خرید (۸۸ عدد)` | `۶۴۸٬۴۰۹` |

Caption under it: `(۳۸ × ۶۲۰٬۰۰۰ + ۳۳٬۵۰۰٬۰۰۰) ÷ ۸۸`

Recent purchases: heading `خریدهای اخیر`, then

| name | meta | amount |
|---|---|---|
| `کارتن جعبه استاندارد` | `۱۴۰۵/۰۶/۲۹ · ۱۰۰ عدد · کارتن‌سازان` | `۶٬۰۰۰٬۰۰۰` |
| `تی‌شرت خام مشکی L` | `۱۴۰۵/۰۶/۲۵ · ۲۰ عدد · پوشاک سپید` | `۵٬۲۰۰٬۰۰۰` |

Note the supplier names are **abbreviated on mobile** (`کارتن‌سازان`, `پوشاک سپید`) versus the desktop table (`بسته‌بندی کارتن‌سازان`, `تولیدی پوشاک سپید`).

Mobile states (from `[[MSTATES:cart|هنوز خریدی ثبت نشده|خریدها موجودی و بهای تمام‌شده را به‌روز می‌کنند.|ثبت خرید|خریدها]]`), `.empty` padding `48px 20px`, CTA is `btn btn-primary btn-lg`:

- empty title `هنوز خریدی ثبت نشده`, body `خریدها موجودی و بهای تمام‌شده را به‌روز می‌کنند.`, CTA `ثبت خرید`
- error title `خریدها بارگذاری نشد`, body `اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.`, button `تلاش دوباره`
- loading: **5** `.sk` blocks 84px tall (plus the 20×180 header skeleton), `aria-label="در حال بارگذاری"`

---

## 3. Interactive states designed

| element | states |
|---|---|
| Search input | default, focus-visible (`box-shadow: 0 0 0 3px var(--ring)`); no typed/filtered state designed |
| Type segment (`همه / مواد / محصولات`) | 3 options, `همه` is `.on`; the other two were not rendered as selected in any artboard |
| تأمین‌کننده select | closed only, value `همه`; **no popover / option list designed** |
| Date-range select | closed only; no calendar popover on this screen (unlike `Orders-DateRange`) |
| `ثبت خرید` (toolbar) | default, hover (`--red-hover`), focus; click → `open()` → drawer |
| Table row | default, hover (`tbody tr:hover td` → `--surface-2`) |
| نوع badge | two variants only: `ماده` = `badge st-paid`, `محصول` = `badge st-done` |
| Drawer | closed (`form=false`) / open (`form=true`, artboard `Purchases-Form`) with `.overlay` behind it |
| Close / انصراف | both call `close()`; identical effect |
| نوع کالا segment (drawer) | 2 options, `ماده یا بسته‌بندی` is `.on`; `محصول آماده` never shown selected |
| کالا select (drawer) | one selected item with a `.stock` pill; **no picker, no empty/placeholder state** |
| تأمین‌کننده select (drawer) | one selected supplier; no picker |
| مقدار input | live — `onQty` → `num(value)`; `Math.max(0, qty)` floors it at 0. No error/warn styling designed |
| مبلغ کل پرداختی input | live — `onTotal` → `num(value)`. No error/warn styling designed |
| Unit-cost preview | number, or `—` when quantity is 0 (`unitT: q ? fa(unit) : '—'`) |
| Delta badge | increase → `badge st-warn` (`+…`); zero or decrease → `badge st-done` (no `+` sign) |
| تاریخ خرید select | closed only, fixed at today with the caption `امروز`; no calendar popover designed |
| Save (`ثبت خرید`, drawer) | enabled only — **no disabled state, no validation, no success/toast state designed** |
| Screen | `ready`, `empty`, `loading`, `error` (desktop + mobile). `theme: dark` is a prop but no dark artboard was built |
| Mobile | one state: the form, always visible, with the sticky bottom bar. Touch targets 44–48px |

Focus ring everywhere: `.rs :focus-visible { box-shadow: 0 0 0 3px var(--ring) }`.

---

## 4. Validation

**No validation was designed on this screen.** There is no error message, no warning message, no disabled save state and no blocking condition anywhere in `Purchases.dc.html` or `PurchasesMobile.dc.html`. The only input guards are mechanical:

| # | guard | where | behaviour | message |
|---|---|---|---|---|
| G1 | non-digits are stripped from both numeric inputs | `num()` in `helpers.js` | `num('۵۰ عدد') → 50`; an empty/garbage entry becomes `0` | none |
| G2 | quantity cannot go negative | `var q = Math.max(0, S.qty)` | a negative value is clamped to 0 for every derived number | none |
| G3 | division by zero avoided | `unit = q ? S.total / q : 0` | with quantity 0 the unit cost renders as `—` | none |
| G4 | **fractional quantities are impossible to type** | `onQty` uses `num()` (integer-only), not `numQ()` | `۱٫۵` is read as `15` — the separator is stripped, not parsed | none |

G4 is a real defect against the project decision that materials may carry fractional quantities: the sample data itself has `کاغذ پرکننده` at `۱٫۵ کیلوگرم` and `کاغذ کرافت` at `۴۲٫۵ متر`, and the purchase list shows a `۵ کیلوگرم` purchase. The helper needed (`numQ`, which maps `٫` and `/` to a decimal point) exists in `helpers.js` and is used by the packaging and adjustment screens — it is simply not wired here. Logged in §7.

Note also that with quantity 0 the new average still renders — `after = (38×620,000 + total) ÷ 38` — i.e. the preview silently treats a 0-quantity purchase as a pure cost increase on existing stock. Nothing flags it. Logged in §7.

---

## 5. Logic

Canonical derivation: `../logic/formulas.md` §3 (weighted-average cost). Do not restate it in code; this section records what *this screen* does with it.

### The live preview (the whole of the screen's JS)

```js
constructor(p) { super(p); this.state = { form: p.form === true || p.form === 'true', qty: 50, total: 33500000 }; }

renderVals() {
  var self = this, S = this.state, q = Math.max(0, S.qty), unit = q ? S.total / q : 0;
  var after = (38 * 620000 + S.total) / (38 + q), d = after - 620000;
  return Object.assign(stateVals(this.props, 900), {
    showForm: S.form, open: …, close: …,
    qtyT: fa(q), totalT: fa(S.total), unitT: q ? fa(unit) : '—', afterT: fa(after), afterStockT: fa(38 + q),
    deltaT: (d >= 0 ? '+' : '') + fa(d), deltaCls: d > 0 ? 'badge st-warn' : 'badge st-done',
    onQty: function (e) { self.setState({ qty: num(e.target.value) }); },
    onTotal: function (e) { self.setState({ total: num(e.target.value) }); }
  });
}
```

So, in prose:

```
unitCostOfThisPurchase = totalPaid ÷ qty                        (— when qty = 0)
newAverage             = (oldStock × oldAverage + totalPaid) ÷ (oldStock + qty)
delta                  = newAverage − oldAverage
newStock               = oldStock + qty
```

`oldStock = 38` and `oldAverage = 620,000` are **hard-coded in the artboard** (they are `m1 صفحه خام وینیل ۱۲ اینچ` from `MATERIALS`). In the real screen they come from the item selected in the `کالا` field, and the `عدد` suffix and the two `… عدد در انبار` captions must follow that item's `unit` (`رول`, `کیلوگرم`, `متر`, `نوبت`) rather than being fixed to `عدد`.

Note the incoming value fed into the numerator is the **total paid**, not `qty × unit`: the two are algebraically identical here, but it means any rounding in the displayed unit cost never propagates into the average. `fa()` rounds only at display time (`Math.round`), so the stored average keeps its fractional part: the sample average is really `648,409.0909…`, displayed `۶۴۸٬۴۰۹`.

### What a saved purchase does

The design states the effects in copy rather than in code (there is no save handler in the artboard):

1. **Stock** — the purchased quantity is added to the item: `newStock = oldStock + qty`. The empty-state copy states the intent plainly: `خرید مواد اولیه، بسته‌بندی یا محصولات آماده را ثبت کنید تا موجودی و بهای تمام‌شده خودکار به‌روز شود.`
2. **Cost** — the item's cost becomes `newAverage` by the formula above. This is the item's `cost` field in `CATALOG` (for `محصول آماده`) or `MATERIALS` (for `ماده یا بسته‌بندی`), the same field that the sale screen reads for `productCost` and that the packaging screen reads for `kitCost`.
3. **Nothing is retro-costed.** The note in the preview block is the contract: `تولیدهای بعدی «وینیل آلبوم اول» با بهای جدید محاسبه می‌شوند؛ تولیدهای گذشته تغییر نمی‌کنند.` — consistent with `../logic/formulas.md` §3 ("Past orders/productions are never re-costed") and §5 (kit cost is computed from *current* material costs, so a purchase of a packaging material changes every kit's cost from that moment on, while the cost copied onto an already-saved order does not move).
4. **The two item kinds differ only in which table is updated.** `ماده یا بسته‌بندی` → a `MATERIALS` row, feeding production recipes (`formulas.md` §4) and packaging kits (§5). `محصول آماده` → a `CATALOG` row directly, which is how a resold/outsourced product gets a cost without a production batch (sample: `وینیل نسخه رنگی`, 5 units at 2,050,000 each).
5. **Freight and extra costs: not modelled.** There is no freight, tax, customs or "other costs" field, and no landed-cost breakdown. The single field is `مبلغ کل پرداختی` — the total amount paid — so anything the user wants inside the cost basis must be added into that one number by hand, and anything they leave out lands on the expenses screen instead (screen 11) where it does **not** raise the item's cost. The screen offers no guidance either way. Logged in §7.
6. **Payment is not modelled either** — no paid/unpaid flag, no due date, no partial payment; the field name asserts the money has already been paid.

### Type filter and totals

`همه / مواد / محصولات` filters the list by the `نوع` column. The `tfoot` total (`۳۱٬۸۰۰٬۰۰۰`) is the sum of the **مبلغ پرداختی** column for the rows in the current period; the `بهای واحد` column has no total (the footer's 7th cell is deliberately empty — averaging unit costs across different items would be meaningless).

---

## 6. Sample data used

Source of truth: `../data/sample-data.md` §Purchases and §Materials. Every number below is checkable.

### The list (شهریور ۱۴۰۵, 6 rows)

| تاریخ | کالا | نوع | مقدار | مبلغ پرداختی | بهای واحد = مبلغ ÷ مقدار |
|---|---|---|---|---|---|
| ۱۴۰۵/۰۶/۲۹ | کارتن جعبه استاندارد (m9) | ماده | 100 عدد | 6,000,000 | 6,000,000 ÷ 100 = **60,000** |
| ۱۴۰۵/۰۶/۲۵ | تی‌شرت خام مشکی L (m5) | ماده | 20 عدد | 5,200,000 | 5,200,000 ÷ 20 = **260,000** |
| ۱۴۰۵/۰۶/۲۰ | وینیل نسخه رنگی (p2) | محصول | 5 عدد | 10,250,000 | 10,250,000 ÷ 5 = **2,050,000** |
| ۱۴۰۵/۰۶/۱۵ | کاغذ پرکننده (m13) | ماده | 5 کیلوگرم | 450,000 | 450,000 ÷ 5 = **90,000** |
| ۱۴۰۵/۰۶/۱۰ | نوار چسب لوگودار (m12) | ماده | 6 رول | 900,000 | 900,000 ÷ 6 = **150,000** |
| ۱۴۰۵/۰۶/۰۴ | کاور چاپی وینیل (m2) | ماده | 50 عدد | 9,000,000 | 9,000,000 ÷ 50 = **180,000** |

Footer total:
`6,000,000 + 5,200,000 + 10,250,000 + 450,000 + 900,000 + 9,000,000 = 31,800,000` ✓ (`۳۱٬۸۰۰٬۰۰۰`, 6 items)

Each unit cost equals the item's current cost in `MATERIALS` / `CATALOG` — these six purchases are what *set* those costs in the sample fixture, which is why they reconcile exactly.

### The pending purchase in the drawer (`Purchases-Form`, and the mobile artboard)

Item `صفحه خام وینیل ۱۲ اینچ` (m1), supplier `کارخانه پرس صفحه آوا`, date ۱۴۰۵/۰۶/۳۱ (today), qty `50` عدد, total paid `33,500,000`. Current state: stock 38, average cost 620,000.

```
unit cost of this purchase = 33,500,000 ÷ 50            = 670,000          → ۶۷۰٬۰۰۰
old stock value            = 38 × 620,000               = 23,560,000
new stock value            = 23,560,000 + 33,500,000    = 57,060,000
new stock count            = 38 + 50                    = 88               → ۸۸ عدد در انبار
new average                = 57,060,000 ÷ 88            = 648,409.0909…    → ۶۴۸٬۴۰۹
delta                      = 648,409.09 − 620,000       = +28,409.09       → +۲۸٬۴۰۹  (badge st-warn)
```

The average rises because the incoming unit cost (670,000) is above the old average (620,000); it lands between the two, closer to the new price because 50 > 38. This matches `../logic/formulas.md` §3 exactly (`(38 × 620,000 + 33,500,000) ÷ 88 = 648,409`).

The delta badge turns `st-warn` (orange) only because cost went **up** — it is an information colour here, not an error: `deltaCls: d > 0 ? 'badge st-warn' : 'badge st-done'`.

### Downstream effect of this one purchase (for cross-checking)

Because the recipe for `وینیل آلبوم اول` consumes one `صفحه خام وینیل ۱۲ اینچ` per unit (`formulas.md` §4), saving this purchase would raise that recipe's per-unit material cost from `620,000 + 180,000 = 800,000` to `648,409 + 180,000 = 828,409` for **future** batches only — which is what the note in the preview promises. Past batches, and the 1,380,000 cost currently carried by `p1`, do not move.

---

## 7. Open questions for this screen

- **Fractional quantities cannot be entered.** `onQty` uses `num()` (integer-only) instead of `numQ()`, so `۱٫۵` becomes `15`. Materials are explicitly allowed fractional quantities, and the sample data contains them (`کاغذ پرکننده ۱٫۵ کیلوگرم`, `کاغذ کرافت ۴۲٫۵ متر`). Decide the rule — fractional for `ماده`, integer for `محصول آماده` — and swap the parser; also decide whether the entered quantity should be validated against the item's unit.
- **No freight / extra-cost handling at all.** There is only `مبلغ کل پرداختی`. Undecided: whether shipping-in, customs, tax or a supplier fee should be separate fields that roll into the cost basis (landed cost), and whether a purchase covering several items should be splittable with the freight apportioned. Today a multi-item invoice has to be entered as several purchases, and any cost left out silently becomes an operating expense instead of item cost.
- **No validation and no save feedback were designed.** No required-field errors, no "quantity must be > 0", no "amount must be > 0", no disabled save, no success state, no toast, and no confirmation despite the fact that saving permanently changes an item's cost. Decide the minimum set before build.
- **A zero quantity is not caught.** With `qty = 0` the unit cost shows `—` but the preview still computes `(38 × 620,000 + total) ÷ 38`, presenting a pure cost increase on existing stock as if it were a purchase. Decide whether that is a legitimate "add cost to existing stock" case (it would overlap with the stock-correction screen's optional unit cost, `formulas.md` §8) or simply an error.
- **The unit is hard-coded to `عدد`** in the drawer suffix and in both `… عدد در انبار` captions, and the baseline (`۳۸`, `۶۲۰٬۰۰۰`) is hard-coded too. The real screen must take unit, stock and average from the selected item; and it is undecided what the preview shows for an item with **no cost yet** (`cost: null`, e.g. `p7`) — there is no "first purchase / no previous average" variant of the preview block.
- **Item and supplier pickers were never designed** (both `.select` controls are static, with no popover, no search, no empty state, and no "add a new supplier inline" path), nor was the date picker on this screen. An item search exists on the sale screen and a calendar on the orders screen; neither was reused here.
- **No editing, deleting or reversing a purchase.** Rows are not clickable, there is no row menu, and nothing says what happens to the weighted average if a wrong purchase has to be undone (recomputing the average backwards is not generally possible).
- **Type filter is one-way only.** `همه / مواد / محصولات` is designed in the `همه` position only; and the mobile screen has no list at all, so filtering, searching and the period total are desktop-only features with no mobile equivalent.
- **Period scope is implicit.** The footer says `جمع خریدهای شهریور` while the range control says `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱`; it is undecided whether the footer label follows the chosen range (and what it reads for a range that is not a whole Jalali month).
- **`یادداشت` is desktop-only** and its placeholder implies it is where the supplier invoice number goes — decide whether that deserves a real field (and whether purchases should link to the supplier record on screen 14).
- **No dark artboard** was generated (`extra_dark=False`), although the `theme` prop exists; dark styling for the drawer and the preview block is untested.
