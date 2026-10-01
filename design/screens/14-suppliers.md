# 14 — تأمین‌کنندگان (Suppliers)

Route: `/suppliers` · sidebar key `suppliers` · page title in top bar: **تأمین‌کنندگان**

A flat directory: one table of suppliers with what each one supplies, a contact role, the year-to-date purchase value, the last purchase date and an active/inactive badge, plus a right-side drawer that adds or edits one. The screen holds no arithmetic of its own — `خرید امسال` and `آخرین خرید` are read out of the purchase records, and the only reason the screen exists is so that the purchase form has something to pick from and so that spend per supplier is visible. Suppliers are never deleted, only deactivated, which the drawer says out loud. Nothing here is validated in the artboards: there is not a single error message, `is-error` class or alert in either source file.

Artboards:

| file | props | canvas | what it shows |
|---|---|---|---|
| `Suppliers.dc.html` | `form: false`, `state: ready` | 1440 × 760 | the table with six suppliers, one of them inactive |
| `Suppliers-Form.dc.html` | `form: true` | 1440 × 760 | the same page with the edit drawer open over it |
| `Suppliers-States.dc.html` | three children, `state: empty / loading / error` | 3 × 1440 × 760 | the three non-ready states side by side |
| `SuppliersMobile.dc.html` | `state: ready` | 390 × 844 | mobile list of five cards + sticky add button |
| `SuppliersMobile-States.dc.html` | three children | 3 × 390 × 844 | mobile empty / loading / error |

The desktop board is interactive only in one respect: `open` / `close` toggle `state.form`, so both the `تأمین‌کننده جدید` button and the first row's pencil button open the same drawer, and `بستن` / `انصراف` close it. `state` (`ready | empty | loading | error`), `theme` (`light | dark`) and `h` are props. The mobile board is static; its rows come from a literal array in `renderVals()`.

---

## 1. Layout

### Desktop (1440 × 760; fluid 1024–1600)

```
┌ sidebar 264 (right) ┬──────────────────── content 1176 ─────────────────────┐
│                     │ top bar 64: «تأمین‌کنندگان»                           │
│                     ├───────────────────────────────────────────────────────┤
│                     │ main  padding 24 / 32 / 40  →  inner width 1112       │
│                     │ ┌ toolbar row: space-between, gap 12 ───────────────┐ │
│                     │ │ [🔍 جستجوی نام یا کالا] 280×40                     │ │
│                     │ │ [switch 36×20] نمایش غیرفعال‌ها   … [تأمین‌کننده   │ │
│                     │ │                                      جدید] 40h    │ │
│                     │ └───────────────────────────────────────────────────┘ │
│                     │ ┌ card (overflow hidden) — full 1112 ───────────────┐ │
│                     │ │ thead 40h  │نام│اقلام تأمین│مسئول تماس│خرید امسال │ │
│                     │ │            │آخرین خرید│وضعیت│ 56px       │        │ │
│                     │ │ 6 rows × 52h   (last row opacity .55)            │ │
│                     │ └───────────────────────────────────────────────────┘ │
└─────────────────────┴───────────────────────────────────────────────────────┘

drawer open (Suppliers-Form):
  .overlay covers the whole 1176 × h content area
  ┌ aside.dialog 460 wide, top 0 → bottom 0, radius 0 14px 14px 0 ───┐
  │ header 20/24, border-bottom: «ویرایش تأمین‌کننده»   [✕ 32×32]     │
  │ body   20/24, gap 14, flex-grow 1  (8 blocks, see field order)    │
  │ footer .d-f 16/24, --surface-2, border-top: [ذخیره] [انصراف]      │
  └───────────────────────────────────────────────────────────────────┘
```

- `main`: `padding: 24px 32px 40px; display:flex; flex-direction:column; gap:20px`.
- The toolbar is **outside** the `sc-if` that swaps in the states, so search, toggle and the add button stay visible in the empty, loading and error states.
- Toolbar: `display:flex; align-items:center; justify-content:space-between; gap:12px`. The right group is `display:flex; gap:10px; align-items:center` and holds the `.ig` search (`width:280px`, prefix search icon 16, `.input` 40px, `padding-right:38px` because of the prefix) and a `label.t-sm` with `.switch` (36×20) + text. The primary button sits at the far end (visually left in RTL).
- Card: `.card` with `overflow:hidden` so the table's corners are clipped; the table is `width:100%`, `th` 40px on `--surface-2`, `td` 52px, no `tfoot`.
- Drawer: `position:absolute; top:0; left:0; bottom:0; width:460px; border-radius:0 14px 14px 0` — anchored to the **left** edge of the content area (the trailing edge in RTL), full height, with `.overlay` (`position:absolute; inset:0; background:var(--overlay)`) behind it. `.dialog` is a flex column: header, `flex-grow:1` body, `.d-f` footer on `--surface-2` with `border-radius:0 0 14px 0`.

#### Table columns (exact order, right→left)

1. **نام** — `.b` (bold text, no link, no avatar).
2. **اقلام تأمین** — a `div` of `.chip`s, `display:flex; gap:4px`; one to three chips per row, each 24px tall on `--surface-2`, no wrapping.
3. **مسئول تماس** — `.muted2`, a role string (or `—`).
4. **خرید امسال (تومان)** — `.n .num .b`, right-aligned tabular digits.
5. **آخرین خرید** — `.num .muted2`, a Jalali date.
6. **وضعیت** — one `.badge`: `st-done` for `فعال`, `st-draft` (dashed outline) for `غیرفعال`.
7. *(no header, `width:56px`)* — `button.btn.btn-ghost.btn-icon.btn-sm` (32×32) with the pencil icon, `aria-label="ویرایش"`. Only the **first** row's button is wired to `open`; the rest are static.

The inactive row is dimmed as a whole (`<tr style="opacity: 0.55;">`) in addition to its badge.

#### Drawer field order (exact)

1. **نام** — `label[for=s1]` + `input#s1.input` (40px), pre-filled `کارخانه پرس صفحه آوا`. No `(اختیاری)` marker, i.e. the only implicitly required field.
2. **مسئول تماس** `(اختیاری)` — `input#s2.input`, pre-filled `واحد فروش`.
3. **شماره تماس** `(اختیاری)` — `input#s3.input.input-num` with `direction:ltr; text-align:right`, empty, placeholder `۰۲۱-۰۰۰۰۰۰۰۰`.
4. **نشانی یا شناسه آنلاین** `(اختیاری)` — `input#s4.input`, empty, placeholder `مثلاً نشانی کارگاه یا صفحه اینستاگرام`.
5. **اقلام تأمین** — a `span.label` (not a `<label for>`) above a `display:flex; gap:6px; flex-wrap:wrap` row of removable `.chip`s, each ending in an ✕ icon 12, followed by a `btn btn-ghost btn-sm` at `height:24px` reading `افزودن` with a plus icon 12.
6. **یادداشت** — `label[for=s5]` + `textarea#s5.input` at `height:80px; padding:10px 12px; resize:none`, pre-filled.
7. **فعال** — `label.t-sm` with `span.switch.on` (36×20) + the word; `gap:10px`.
8. Help paragraph `.t-cap.muted` closing the body.

Footer buttons in order: `ذخیره` (`btn btn-primary`, 40px) then `انصراف` (`btn btn-outline`, wired to `close`); the footer is `justify-content:flex-start`, so they sit at the right edge in RTL.

### Mobile (390 × 844)

```
┌ 390 ─────────────────────────────────────┐
│ MobileBar 56: menu 44 · logo 26 · title  │
├──────────────────────────────────────────┤
│ main padding 14/16/100, gap 12 → 358 wide│
│ ┌ .ig search, input 44h ───────────────┐ │
│ └──────────────────────────────────────┘ │
│ ┌ card padding 12/14, gap 6 ───────────┐ │
│ │ نام (b, t-sm)        مبلغ (num b)    │ │ ← space-between
│ │ اقلام … (t-cap muted2)               │ │
│ │ آخرین خرید ۱۴۰۵/۰۶/۲۰ (t-cap muted)  │ │
│ └──────────────────────────────────────┘ │
│  × 5 cards                               │
├──────────────────────────────────────────┤
│ sticky bottom bar, padding 12/16/20      │
│ [ + تأمین‌کننده جدید ] btn-primary btn-lg │
│  full width, 48h                         │
└──────────────────────────────────────────┘
```

- `main`: `padding:14px 16px 100px; display:flex; flex-direction:column; gap:12px`; the search input is 44px tall (touch target) and sits above the `sc-if`, so it also stays visible in the three states.
- Each list card: `padding:12px 14px; display:flex; flex-direction:column; gap:6px`; row 1 is `justify-content:space-between` with the name (`.b.t-sm`) and the amount (`.num.b.t-sm`); row 2 is the supplied items joined with ` · `; row 3 is the last-purchase line.
- Sticky bar: `position:absolute; left:0; right:0; bottom:0; padding:12px 16px 20px; background:--surface; border-top:1px solid --border`; the button is `btn btn-primary btn-lg` at `width:100%` (48px) with a plus icon 18.
- **Not present on mobile:** the `نمایش غیرفعال‌ها` toggle, the contact-role column, the status badge, the row edit button, the inactive supplier itself, and the whole drawer/form — there is no mobile form design at all.

---

## 2. Copy (verbatim)

### Page chrome

| place | string |
|---|---|
| sidebar item + `title` attribute | `تأمین‌کنندگان` |
| top bar `h1` | `تأمین‌کنندگان` |
| desktop artboard `<title>` | `تأمین‌کنندگان` |
| mobile artboard `<title>` | `تأمین‌کنندگان — موبایل` |
| `Suppliers-Form` wrapper title | `تأمین‌کنندگان — افزودن / ویرایش` |
| `Suppliers-States` wrapper title | `تأمین‌کنندگان — خالی · بارگذاری · خطا` |
| `SuppliersMobile-States` wrapper title | `تأمین‌کنندگان موبایل — خالی · بارگذاری · خطا` |

### Toolbar

| element | string |
|---|---|
| search placeholder | `جستجوی نام یا کالا` |
| search `aria-label` | `جستجو` |
| toggle label | `نمایش غیرفعال‌ها` |
| primary button | `تأمین‌کننده جدید` (plus icon 16) |

### Table headers

| # | string |
|---|---|
| 1 | `نام` |
| 2 | `اقلام تأمین` |
| 3 | `مسئول تماس` |
| 4 | `خرید امسال (تومان)` |
| 5 | `آخرین خرید` |
| 6 | `وضعیت` |
| 7 | *(empty, 56px)* — buttons carry `aria-label="ویرایش"` |

### Table rows (verbatim, in artboard order)

| نام | اقلام تأمین (chips) | مسئول تماس | خرید امسال | آخرین خرید | وضعیت |
|---|---|---|---|---|---|
| `کارخانه پرس صفحه آوا` | `صفحه خام وینیل` · `وینیل آماده` | `واحد فروش` | `۸۶٬۴۵۰٬۰۰۰` | `۱۴۰۵/۰۶/۲۰` | `فعال` |
| `چاپخانه نقش` | `کاور چاپی` · `پوستر` · `نوار چسب` | `مدیر تولید` | `۲۴٬۳۰۰٬۰۰۰` | `۱۴۰۵/۰۶/۱۰` | `فعال` |
| `تولیدی پوشاک سپید` | `تی‌شرت خام` | `واحد فروش` | `۱۵٬۶۰۰٬۰۰۰` | `۱۴۰۵/۰۶/۲۵` | `فعال` |
| `بسته‌بندی کارتن‌سازان` | `کارتن` · `جعبه وینیل` · `پرکننده` | `فروش عمده` | `۱۲٬۸۵۰٬۰۰۰` | `۱۴۰۵/۰۶/۲۹` | `فعال` |
| `استودیو صدای روشن` | `مسترینگ` | `هماهنگی پروژه` | `۲۴٬۰۰۰٬۰۰۰` | `۱۴۰۵/۰۳/۱۸` | `فعال` |
| `چاپ دیجیتال پرتو` *(row at opacity .55)* | `استیکر` | `—` | `۰` | `۱۴۰۴/۱۱/۰۴` | `غیرفعال` |

Badge text is exactly `فعال` (`.badge.st-done`) or `غیرفعال` (`.badge.st-draft`); both render a 6px dot before the text via `.badge::before`.

### Drawer (verbatim, `Suppliers-Form`)

| element | string |
|---|---|
| dialog heading | `ویرایش تأمین‌کننده` |
| close button `aria-label` | `بستن` |
| field 1 label | `نام` |
| field 1 value | `کارخانه پرس صفحه آوا` |
| field 2 label | `مسئول تماس` + `(اختیاری)` |
| field 2 value | `واحد فروش` |
| field 3 label | `شماره تماس` + `(اختیاری)` |
| field 3 placeholder | `۰۲۱-۰۰۰۰۰۰۰۰` |
| field 4 label | `نشانی یا شناسه آنلاین` + `(اختیاری)` |
| field 4 placeholder | `مثلاً نشانی کارگاه یا صفحه اینستاگرام` |
| field 5 label | `اقلام تأمین` |
| field 5 chips | `صفحه خام وینیل` ✕ · `وینیل نسخه رنگی` ✕ |
| field 5 add button | `افزودن` |
| field 6 label | `یادداشت` |
| field 6 value | `حداقل سفارش پرس: ۳۰ عدد · زمان تحویل حدود ۶ هفته` |
| field 7 switch label | `فعال` |
| footer note | `تأمین‌کننده حذف نمی‌شود تا سوابق خرید حفظ شود؛ غیرفعال‌ها در انتخاب «خرید» نمایش داده نمی‌شوند.` |
| save | `ذخیره` |
| cancel | `انصراف` |

`(اختیاری)` is a `span.opt` inside the `label` (rendered by `.label .opt` as regular weight, `--text-3`).

### Mobile list (verbatim)

| نام | اقلام | آخرین خرید | مبلغ |
|---|---|---|---|
| `کارخانه پرس صفحه آوا` | `صفحه خام وینیل · وینیل آماده` | `آخرین خرید ۱۴۰۵/۰۶/۲۰` | `۸۶٬۴۵۰٬۰۰۰` |
| `چاپخانه نقش` | `کاور چاپی · پوستر · نوار چسب` | `آخرین خرید ۱۴۰۵/۰۶/۱۰` | `۲۴٬۳۰۰٬۰۰۰` |
| `استودیو صدای روشن` | `مسترینگ` | `آخرین خرید ۱۴۰۵/۰۳/۱۸` | `۲۴٬۰۰۰٬۰۰۰` |
| `تولیدی پوشاک سپید` | `تی‌شرت خام` | `آخرین خرید ۱۴۰۵/۰۶/۲۵` | `۱۵٬۶۰۰٬۰۰۰` |
| `بسته‌بندی کارتن‌سازان` | `کارتن · جعبه وینیل · پرکننده` | `آخرین خرید ۱۴۰۵/۰۶/۲۹` | `۱۲٬۸۵۰٬۰۰۰` |

The literal prefix in row 3 of each card is `آخرین خرید ` followed by the Jalali date; the items line is the chips of the desktop row joined by ` · `. Mobile search placeholder and `aria-label` are the same strings as desktop (`جستجوی نام یا کالا`, `جستجو`); the sticky button repeats `تأمین‌کننده جدید`.

### Empty state (`state: empty`, building icon 28 in a 56px `.e-art`, padding 96px 24px desktop / 48px 20px mobile)

Desktop:

```
title: هنوز تأمین‌کننده‌ای ثبت نشده
body:  تأمین‌کنندگان را ثبت کنید تا در «خرید» انتخاب شوند و مجموع خرید از هر کدام را ببینید.
cta:   افزودن تأمین‌کننده
```

Mobile (same title and CTA, shorter body, CTA is `btn-primary btn-lg`):

```
body:  تأمین‌کنندگان در فرم خرید انتخاب می‌شوند.
```

Note the CTA wording differs from the toolbar button: the empty state says `افزودن تأمین‌کننده`, the toolbar says `تأمین‌کننده جدید`.

### Loading state (`state: loading`)

Skeletons only, no text: `<section aria-busy="true" aria-label="در حال بارگذاری">` with a 20 × 180px `.sk` title bar then **8** blocks of `height:40px; border-radius:10px` (desktop) or **5** blocks of `height:84px` (mobile), `gap:12px`. The toolbar/search above stays live.

### Error state (`state: error`, cloud-off icon 28 on `--loss-soft`)

Desktop:

```
title:  فهرست تأمین‌کنندگان بارگذاری نشد
body:   اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.
button: تلاش دوباره   (btn-outline, refresh icon 16)
```

Mobile — same body and button, shorter title (the `[[MSTATES:…]]` fifth argument is `تأمین‌کنندگان`, and the macro appends ` بارگذاری نشد`):

```
title:  تأمین‌کنندگان بارگذاری نشد
```

---

## 3. Interactive states designed

| element | states |
|---|---|
| Search input | default, focus (`border --navy-2` + `box-shadow: 0 0 0 3px var(--ring)`); **no** typing/filtered/no-result state designed |
| `نمایش غیرفعال‌ها` switch | off (`.switch`, `--surface-3`) — the **on** state (`.switch.on`, `--navy-2`) exists in the design system and is used by the drawer's `فعال` switch, but no artboard shows this toggle on |
| `تأمین‌کننده جدید` button | `btn-primary` default + hover (`--red-hover`); opens the drawer (`onClick={{open}}`) |
| Table row | default, hover (`tbody tr:hover td → --surface-2`), inactive (whole `<tr>` at `opacity:.55`) |
| Status badge | `فعال` = `st-done` (green on `--profit-soft`) · `غیرفعال` = `st-draft` (dashed `--border-strong` outline on `--surface`) |
| Row `ویرایش` button | `btn-ghost btn-icon btn-sm` default + hover; row 1 opens the drawer, rows 2–6 are inert in the artboard |
| Chips (table) | one static appearance only (`--surface-2`, 24px) |
| Drawer | closed ↔ open (`state.form`), with `.overlay` behind it; closed by `بستن` (header ✕) or `انصراف` (footer) — both call `close` |
| Drawer inputs | default + focus ring; the phone field additionally forces `direction:ltr; text-align:right` and shows a Persian-digit placeholder |
| Drawer chips | removable appearance (trailing ✕ icon 12) + an `افزودن` ghost button; the picker that `افزودن` would open is **not** designed |
| `فعال` switch (drawer) | `on` (`--navy-2`) is what the artboard shows; `off` is the plain `.switch` |
| `ذخیره` / `انصراف` | `btn-primary` / `btn-outline`, both always enabled — no disabled, pending, saving or saved state |
| Screen | ready, empty, loading, error (`state` prop); `theme` light/dark is a prop but **no dark artboard was rendered for this screen** |
| Mobile | one composition only: list + sticky add button; no form, no row tap target, no swipe actions |

Focus rings are the shared `box-shadow: 0 0 0 3px var(--ring)`; the inactive row conveys its state twice (dimming **and** the `غیرفعال` badge), so it is not colour-only.

---

## 4. Validation

**No validation is designed for this screen.** Neither `Suppliers.dc.html` nor `SuppliersMobile.dc.html` contains an `.alert`, an `is-error`/`is-warn` class, a `role="alert"`, a required marker or any error string; `ذخیره` is never disabled and the component's only logic is `open` / `close`. The three `(اختیاری)` markers imply that `نام` is the one required field, but no message accompanies it.

For completeness, the rules the screen *implies* but does not specify — each of these needs copy written before implementation, and none may be invented from this document:

| implied rule | what exists in the design | what is missing |
|---|---|---|
| `نام` is required | it is the only field without `(اختیاری)` | the empty-name error message; whether `ذخیره` disables |
| duplicate supplier names | nothing | whether duplicates are rejected or merely warned, and the message |
| `شماره تماس` format | `input-num`, LTR, placeholder `۰۲۱-۰۰۰۰۰۰۰۰` | whether non-digits are stripped, min/max length, mobile vs landline, and any error message |
| `اقلام تأمین` | chips, freely removable, `افزودن` unwired | whether at least one item is required; whether items are free text or references to products/materials |
| deactivating a supplier | the note `تأمین‌کننده حذف نمی‌شود تا سوابق خرید حفظ شود؛ غیرفعال‌ها در انتخاب «خرید» نمایش داده نمی‌شوند.` | any confirmation when switching `فعال` off; what happens to draft purchases already referencing it |
| deleting a supplier | explicitly out of scope per the note | nothing designed, no delete affordance anywhere |

The only *rule* actually stated in product copy on this screen is the note above: suppliers are never deleted so purchase history survives, and inactive suppliers disappear from the purchase form's picker.

---

## 5. Logic

The component carries no calculation at all:

```js
class Component extends DCLogic {
  constructor(p) { super(p); this.state = { form: p.form === true || p.form === 'true' }; }
  renderVals() {
    var self = this;
    return Object.assign(stateVals(this.props, 760), {
      showForm: this.state.form,
      open:  function () { self.setState({ form: true }); },
      close: function () { self.setState({ form: false }); }
    });
  }
}
```

`stateVals()` (helpers.js) resolves `theme`, `h` and the four booleans `isReady / isEmpty / isLoading / isError` from the `state` prop. All table content is literal markup; on mobile the rows are a literal array mapped through the shared formatters:

```js
var R = [['کارخانه پرس صفحه آوا', 'صفحه خام وینیل · وینیل آماده', 86450000, '1405/06/20'], …];
rows: R.map(function (r) { return { n: r[0], i: r[1], t: fa(r[2]), d: faD(r[3]) }; })
```

So the two derived columns must be produced by the real implementation:

- **خرید امسال (تومان)** — the sum of purchase amounts for that supplier within the current Jalali year, displayed with `fa()` (Persian digits, `٬` separator, no decimals, unit in the header). The sample values are year-to-date and therefore larger than the شهریور-only purchase rows in `../data/sample-data.md` § Purchases; `۰` is a real value, shown for a supplier with no purchases this year (`چاپ دیجیتال پرتو`).
- **آخرین خرید** — the newest purchase date for that supplier, `faD()`-formatted Jalali (`YYYY/MM/DD`). For `چاپ دیجیتال پرتو` it is `۱۴۰۴/۱۱/۰۴`, i.e. last year, which is consistent with `خرید امسال = ۰`.
- **اقلام تأمین** — a stored list on the supplier, not derived from purchases: the chips are shortened labels (`صفحه خام وینیل`, `کارتن`, `پرکننده`) rather than the full material names in `../data/sample-data.md` § Materials, and `وینیل آماده` matches no catalog or material row at all.

Cross-references instead of restating: purchase-side arithmetic (weighted-average cost when a purchase lands) is `../logic/formulas.md` §3; the supplier fixture list and the purchase rows that back these two columns are `../data/sample-data.md` §§ Suppliers and Purchases. There is no formula on this screen.

Ordering and filtering, as built:

- Desktop row order is **neither** by name, nor by `خرید امسال` (`استودیو صدای روشن` at ۲۴٬۰۰۰٬۰۰۰ sits after ۱۲٬۸۵۰٬۰۰۰), nor by `آخرین خرید` — it is a hand-written order with the inactive supplier last. No sort rule is declared and no column is sortable.
- Mobile order **is** descending by `خرید امسال` (86,450,000 → 24,300,000 → 24,000,000 → 15,600,000 → 12,850,000) and excludes the inactive supplier.
- The desktop `نمایش غیرفعال‌ها` switch renders **off** while the inactive row is nonetheless in the table — so the toggle's effect is not demonstrated anywhere.
- Search (`جستجوی نام یا کالا`) is expected to match both the supplier name and the supplied items, per its placeholder; no filtered or no-result rendering is designed.

Drawer behaviour: `تأمین‌کننده جدید` and the first row's pencil both call the same `open`, and the drawer always renders the heading `ویرایش تأمین‌کننده` with `کارخانه پرس صفحه آوا` pre-filled — there is no "new supplier" variant with a blank form and an add-oriented title. `ذخیره` is not wired to anything; only `انصراف` and ✕ change state.

---

## 6. Sample data used

Full list in `../data/sample-data.md` § Suppliers; the purchase rows behind the two derived columns are in § Purchases. All names are invented workshops and no phone number appears anywhere (the only phone field is empty, showing the placeholder `۰۲۱-۰۰۰۰۰۰۰۰`), and `مسئول تماس` holds department roles rather than people (`واحد فروش`, `مدیر تولید`, `فروش عمده`, `هماهنگی پروژه`).

| supplier | items | contact | خرید امسال | آخرین خرید | status |
|---|---|---|---|---|---|
| کارخانه پرس صفحه آوا | صفحه خام وینیل، وینیل آماده | واحد فروش | 86,450,000 | ۱۴۰۵/۰۶/۲۰ | فعال |
| چاپخانه نقش | کاور چاپی، پوستر، نوار چسب | مدیر تولید | 24,300,000 | ۱۴۰۵/۰۶/۱۰ | فعال |
| تولیدی پوشاک سپید | تی‌شرت خام | واحد فروش | 15,600,000 | ۱۴۰۵/۰۶/۲۵ | فعال |
| بسته‌بندی کارتن‌سازان | کارتن، جعبه وینیل، پرکننده | فروش عمده | 12,850,000 | ۱۴۰۵/۰۶/۲۹ | فعال |
| استودیو صدای روشن | مسترینگ | هماهنگی پروژه | 24,000,000 | ۱۴۰۵/۰۳/۱۸ | فعال |
| چاپ دیجیتال پرتو | استیکر | — | 0 | ۱۴۰۴/۱۱/۰۴ | غیرفعال |

Sum of the column (no `tfoot` is rendered, but the figures are checkable):
`86,450,000 + 24,300,000 + 15,600,000 + 12,850,000 + 24,000,000 + 0 = 163,200,000`.

### Reconciliation against the sample purchases (شهریور ۱۴۰۵)

The شهریور purchases in `../data/sample-data.md` total 31,800,000 and break down per supplier as:

| supplier | شهریور purchases | sum | `خرید امسال` | earlier in ۱۴۰۵ (implied) |
|---|---|---|---|---|
| بسته‌بندی کارتن‌سازان | کارتن ۱۰۰ عدد 6,000,000 + کاغذ پرکننده ۵ کیلوگرم 450,000 | 6,450,000 | 12,850,000 | 6,400,000 |
| چاپخانه نقش | نوار چسب ۶ رول 900,000 + کاور چاپی ۵۰ عدد 9,000,000 | 9,900,000 | 24,300,000 | 14,400,000 |
| تولیدی پوشاک سپید | تی‌شرت خام ۲۰ عدد 5,200,000 | 5,200,000 | 15,600,000 | 10,400,000 |
| کارخانه پرس صفحه آوا | وینیل نسخه رنگی ۵ عدد 10,250,000 | 10,250,000 | 86,450,000 | 76,200,000 |
| استودیو صدای روشن | — | 0 | 24,000,000 | 24,000,000 |
| چاپ دیجیتال پرتو | — | 0 | 0 | 0 |
| **جمع** | | **31,800,000** ✓ | **163,200,000** | **131,400,000** |

`31,800,000 + 131,400,000 = 163,200,000` ✓ — i.e. the `خرید امسال` figures are consistent with the شهریور rows plus earlier purchases that the sample set does not enumerate. Date checks: each active supplier's `آخرین خرید` equals its newest شهریور row (`۰۶/۲۰`, `۰۶/۱۰`, `۰۶/۲۵`, `۰۶/۲۹`) ✓; `استودیو صدای روشن` (`۱۴۰۵/۰۳/۱۸`) and `چاپ دیجیتال پرتو` (`۱۴۰۴/۱۱/۰۴`) have no row in the sample purchases, which is why their last purchase predates شهریور. Today is `۱۴۰۵/۰۶/۳۱`, so every `آخرین خرید` is in the past ✓.

Where the chips do **not** line up with the item master (worth resolving before seeding): `صفحه خام وینیل` vs the material `صفحه خام وینیل ۱۲ اینچ`; `کارتن` vs `کارتن جعبه استاندارد`; `پرکننده` vs `کاغذ پرکننده`; `کاور چاپی` vs `کاور چاپی وینیل`; `نوار چسب` vs `نوار چسب لوگودار`; `مسترینگ` vs `مسترینگ و کات لاکر`; `تی‌شرت خام` vs `تی‌شرت خام مشکی L`; and `وینیل آماده`, which matches nothing. The drawer for the same supplier lists `صفحه خام وینیل` + `وینیل نسخه رنگی`, while its table row lists `صفحه خام وینیل` + `وینیل آماده` — the two are inconsistent in the artboards.

---

## 7. Open questions for this screen

1. **The drawer has no "new" variant.** `تأمین‌کننده جدید` opens the same panel titled `ویرایش تأمین‌کننده`, pre-filled with `کارخانه پرس صفحه آوا`. A blank add form, its heading, and the save-button wording for the add case are all undesigned.
2. **No validation whatsoever is designed** (see §4): no required-field message for `نام`, no duplicate-name rule, no phone format rule, no minimum for `اقلام تأمین`, and `ذخیره` never disables. Every message here still has to be written.
3. **`افزودن` (items) leads nowhere.** The chip picker is undesigned, and it is unresolved whether `اقلام تأمین` is free text or a reference to products/materials. The sample chips use shortened labels that match no master record (`وینیل آماده` matches nothing at all), and the drawer's chips disagree with the same supplier's table row.
4. **`نمایش غیرفعال‌ها` is shown off while an inactive row is visible**, so the toggle's actual effect is not demonstrated and its default (off, presumably hiding inactive suppliers) contradicts the rendered table.
5. **Sort and filter behaviour is undefined.** Desktop order follows no rule (it is neither alphabetical, nor by spend, nor by date), mobile silently sorts by spend descending and drops the inactive supplier, no column is sortable, and no filtered / no-result / searching state is designed for either breakpoint.
6. **No save feedback path.** `ذخیره` is inert: no pending, success, toast, error or optimistic row update is designed, nor is any behaviour for closing the drawer with unsaved edits (no "discard changes?" confirmation).
7. **Deactivation has no confirmation or consequence design.** The note promises inactive suppliers vanish from the purchase picker, but nothing covers purchases already referencing one, whether reactivation is symmetric, or whether switching `فعال` off needs a confirm.
8. **No supplier detail view.** There is no per-supplier page, purchase history, spend trend, outstanding balance or payment terms — `یادداشت` is the only place for terms such as the sample `حداقل سفارش پرس: ۳۰ عدد · زمان تحویل حدود ۶ هفته`, and it is free text.
9. **`خرید امسال` is undefined in detail.** Which purchase statuses count, whether the year is the Jalali year to date, and whether the figure is cached or computed on read — none is stated; there is also no `tfoot` total and no period selector.
10. **Mobile is read-only and partial.** No form, no inactive suppliers, no status badge, no contact column, no row tap target or edit affordance; the sticky `تأمین‌کننده جدید` button has nowhere to go.
11. **Copy inconsistency between the two add affordances:** the toolbar says `تأمین‌کننده جدید`, the empty state's CTA says `افزودن تأمین‌کننده`. One should win.
12. **Pagination and scale.** Six rows fit; nothing is designed for dozens of suppliers (no pagination, no virtualised list, no sticky header) and the table cells are all `white-space:nowrap`, so long names and long chip sets will overflow horizontally.
13. **No dark artboard** was rendered for this screen, although `theme` is a prop on both boards.
14. **Deletion, export and merge are absent by design but unconfirmed:** the note rules out deletion, yet nothing covers merging duplicates created by accident, or exporting the supplier list.
