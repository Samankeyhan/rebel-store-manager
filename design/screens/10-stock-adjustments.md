# 10 — تعدیل موجودی (Stock adjustments)

Route: undefined (the artboards link to `Adjustments.dc.html`; see §7 and `00-app-shell.md` §7) · sidebar key `adjust` (icon `sliders`) · page title in top bar: **تعدیل موجودی**

This is where stock moves for reasons that are not a sale, a purchase or a production run. It carries one of the agreed corrections, and the whole screen is built around it: there are exactly **two** kinds of adjustment — **ضایعات** (waste: goods actually destroyed or thrown away) and **اصلاح موجودی** (correction: the warehouse count simply disagrees with the system) — and only ضایعات is a real loss. A correction never reaches the profit-and-loss statement, in any row; it only fixes the count and the inventory valuation. The screen states that three separate times (on the type tile, in the live preview note, and in the table footnote) because in the old spreadsheet both kinds were mixed into one "shrinkage" figure. The second half of the correction is valuation: a waste record is priced at the item's cost **on the day it was recorded** and that value is frozen with the record, so a later purchase that moves the weighted average never rewrites last month's waste. Layout is a form on the right, a live before/after preview beside it, and the month's adjustment history underneath. Materials may carry fractional quantities (`٫`), products may not — this screen is where that rule is enforced.

Artboards: `Adjustments.dc.html` (light, `preset: default`, `state: ready`, 1440 × 1080), `Adjustments-Add.dc.html` (`preset: add` — a correction **+** with a unit cost, 1440 × 1120), `Adjustments-Over.dc.html` (`preset: over` — more than current stock, blocked, 1440 × 1120), `Adjustments-Fraction.dc.html` (`preset: fraction` — a fractional quantity on a product, error, 1440 × 1120), `Adjustments-States.dc.html` (three 1440 × 760 boards: `state: empty` · `loading` · `error`), `AdjustmentsMobile.dc.html` (390 × 900), `AdjustmentsMobile-States.dc.html` (three 390 × 844 boards: `empty` · `loading` · `error`).
Source: `src/Adjustments.dc.html`, `src/AdjustmentsMobile.dc.html`. The desktop artboard is fully live: the `preset` prop (`default | over | fraction | add`) seeds the form state, and every value in the preview — before/after, the valuation row, the weighted-average row, the note, the badge and the disabled state of the save button — is computed by the JS in that file. The mobile artboard is a static frame (`renderVals()` returns `stateVals()` only) and shows the over-stock error case.

---

## 1. Layout

### Desktop (1440 × 1080; 1120 for the three preset boards; fluid 1024–1600)

```
┌ sidebar 264 (RIGHT / inline-start) ┬──────────────── content 1176 ────────────────┐
│                                    │ top bar 64: «تعدیل موجودی»                     │
│                                    ├───────────────────────────────────────────────┤
│                                    │ main  padding 24 32 40 · column · gap 20      │
│  ┌── row: flex, gap 24, align-items flex-start ────────────────────────────────┐   │
│  │ form card 440 (flex-shrink 0)         │ preview card grow (648)             │   │
│  │  «ثبت تعدیل»                            │  «پیش‌نمایش»          [kind badge]  │   │
│  │  [ ضایعات ] [ اصلاح موجودی ]  ← 2-col grid │  ┌ before → after (surface-2) ──┐ │   │
│  │  کالا  .seg, 4 buttons, wrap            │  │ ۴۲   [chevL 24]   ۳۹        │ │   │
│  │  جهت   .seg (correction only)           │  └──────────────────────────────┘ │   │
│  │  مقدار  ig 220 + sfx                    │  .sl  valuation label / value     │   │
│  │  بهای واحد … (correction + only)        │  .sl  weighted average (add only) │   │
│  │  دلیل  input                            │  note paragraph (t-cap muted)     │   │
│  │                                        │  [ثبت تعدیل]                        │   │
│  └────────────────────────────────────────┴────────────────────────────────────┘   │
│  ┌── history card 1112, overflow hidden ───────────────────────────────────────┐   │
│  │ «تاریخچه تعدیل‌ها»   [همه|ضایعات|اصلاح] [کالا: همه ▾] [شهریور ۱۴۰۵]            │   │
│  │ table: 8 columns × 5 rows                                                    │   │
│  │ footnote paragraph (padding 12 20)                                           │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────┘
```

- Content width `1440 − 264 = 1176`; `main` padding `24px 32px 40px`, `gap: 20px` from the `[[PAGE:adjust|تعدیل موجودی]]` macro (`00-app-shell.md` §5) → inner width `1112`.
- Top row: `display: flex; gap: 24px; align-items: flex-start`. **The form card is the first DOM child, so in RTL it is at the inline start — the right-hand side**; the preview is `.card.grow` and fills `1112 − 440 − 24 = 648`.
- Form body: `.card-b` with `display: flex; flex-direction: column; gap: 14px`.
- Preview body: `.card-b` with `gap: 16px`. The before/after panel is `display: grid; grid-template-columns: 1fr auto 1fr; gap: 16px; align-items: center; background: var(--surface-2); border-radius: 12px; padding: 18px 20px` — first cell (right, in RTL) is "current", the middle is a `chevL` 24 in `--text-3`, the last cell (left) is "after".
- The save button is `align-self: flex-start`, i.e. pinned to the inline start (right) of the preview card.
- History card is full width with `overflow: hidden`; the footnote is a `p.t-cap.muted` with `padding: 12px 20px` **inside** the card, below the table.
- The three preset boards are 40px taller (1120) than the default (1080) because they render the extra error row and, for `add`, two extra rows.

### Field order, desktop form (exact)

1. **نوع تعدیل** — `.field` with a `span.label` (not a `<label>`, because the control is a radio group) and `div[role="radiogroup"]` at `grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px`. Two `.opt` buttons, each `role="radio"` with `aria-checked` and `.on` when selected:
   - `ضایعات` — `.o-t` with a `trash` 16 icon, then two `.o-s` sub-lines (the second is `.neg.b`).
   - `اصلاح موجودی` — `.o-t` with a `sliders` 16 icon, then two `.o-s` sub-lines (the second is `.b`).
2. **کالا** — a `.seg` at `width: 100%; flex-wrap: wrap` containing one button per item (4 in the sample), each `flex-grow: 1; font-size: 12.5px; padding: 0 8px`, showing the item's **short** name. Below it a `.help` line with the selected item's metadata.
3. **جهت** — **rendered only when نوع = اصلاح موجودی** (`{{isC}}`). A `.seg` at `width: 100%` with two buttons: `plus` 14 + `افزایش`, `minus` 14 + `کاهش`.
4. **مقدار** — `#aq`, `.input.input-num` inside `.ig` at `max-width: 220px`, with the `.sfx` suffix set to the selected item's unit. Below it: the conditional `.err` row (`role="alert"`, `alert` icon 14), then a `.help` line stating whether decimals are allowed.
5. **بهای واحد موجودی اضافه‌شده** `(اختیاری)` — `#uc`, same 220px `.ig` with the `تومان` suffix. **Rendered only when نوع = اصلاح موجودی AND جهت = افزایش** (`{{showCost}}` = `plus`).
6. **دلیل** — `#ar`, plain `.input`, full width.

There is **no date field** (see §7).

### Preview card contents (exact order)

1. Header: `h2#ap.t-h2` `پیش‌نمایش` + a kind badge (`{{kindBadge}}` / `{{kindT}}`).
2. Before/after panel — each side is `t-cap muted b` caption, a 28px/40 `.num.b` figure, and a `t-cap muted` unit line.
3. `.sl` — valuation label / valuation value (`.v.b` + `{{valueCls}}`).
4. `.sl` — `میانگین بهای واحد` / `old ← new` — **only when `showAvg`** (correction + with a positive quantity).
5. `p.t-cap.muted` — the per-kind note.
6. `.btn.btn-primary` `ثبت تعدیل`, `disabled="{{hasErr}}"`.

### History table columns (exact order, first = rightmost in RTL)

1. `تاریخ` — `.num.muted2`
2. `کالا` — `.b`
3. `نوع` — a `.badge`
4. `مقدار` — `.n.num`
5. `قبل ← بعد` — `.n.num.muted2`
6. `ارزش (تومان)` — `.n.num`, `.neg` when negative
7. `اثر در سود و زیان` — `.t-cap`, `.neg.b` for waste / `.muted` for corrections
8. `دلیل` — `.muted2`

Header controls, inline end of the card header (`display: flex; gap: 8px`): a `.seg` (`همه` `.on` / `ضایعات` / `اصلاح`), then a `.select` 36px tall showing `کالا:` + `همه` + `chevD` 14, then a `.select` 36px tall with `cal` 14 + `شهریور ۱۴۰۵`.

### Mobile (390 × 900)

```
┌────────────────────── 390 ──────────────────────┐
│ mobile bar 56: «تعدیل موجودی»                      │
├─────────────────────────────────────────────────┤
│ main  padding 14 16 100 · column · gap 12       │
│ ┌ form card (padding 14, gap 12) ─────────────┐ │
│ │ .seg 2-col grid, each 44 tall               │ │
│ │   [ ضایعات ·on ] [ اصلاح موجودی ]              │ │
│ │ p.help (bold ضایعات / اصلاح موجودی)           │ │
│ │ کالا  .select 48 (2-line: name + meta) ▾     │ │
│ │ مقدار  ig input 48 .is-error + sfx           │ │
│ │   .err row                                   │ │
│ │ دلیل  input 48                                │ │
│ └─────────────────────────────────────────────┘ │
│ ┌ before/after card (surface-2, padding 14) ──┐ │
│ │ ۸    [chevL 20]    —                        │ │
│ └─────────────────────────────────────────────┘ │
│ t-h3 «اخیر»                                      │
│ ┌ recent card پوستر تور ۱۴۰۴ ──────────────────┐ │
│ ┌ recent card کاغذ پرکننده ────────────────────┐ │
├─────────────────────────────────────────────────┤
│ sticky footer: [ ثبت تعدیل ] full width, disabled│
└─────────────────────────────────────────────────┘
```

- `main` padding `14px 16px 100px`, `gap: 12px` (from `[[MPAGE:تعدیل موجودی]]`); inner width `390 − 32 = 358`.
- Sticky footer: `position: absolute; left: 0; right: 0; bottom: 0; padding: 12px 16px 20px; background: var(--surface); border-top: 1px solid var(--border)`, one `.btn.btn-primary.btn-lg` at `width: 100%`, `disabled`.
- The kind control is a 2-column `.seg` grid with 44px buttons (not `.opt` tiles); the two tiles' three sub-lines collapse into one `p.help` sentence with two bold runs.
- کالا becomes a single `.select` 48px tall, two stacked lines (`.b` name over `.t-cap.muted` metadata) plus a `chevD` 14. All controls are 48px; every target ≥ 44px.
- The before/after panel keeps the same `1fr auto 1fr` grid at `padding: 14px` with 24px figures and a `chevL` 20.
- **Absent on mobile:** the جهت control (even though the اصلاح موجودی tab exists), the بهای واحد field, the valuation `.sl` row, the weighted-average `.sl` row, the per-kind note paragraph, the whole history table with its three filters, and the table footnote. The history is reduced to two "recent" cards, each `padding: 12px 14px; display: flex; justify-content: space-between`.

---

## 2. Copy (verbatim)

### Type tiles (desktop)

| Slot | String |
|---|---|
| field label | `نوع تعدیل` |
| tile 1 title (`.o-t`, `trash` 16) | `ضایعات` |
| tile 1 sub-line 1 (`.o-s`) | `همیشه موجودی را کم می‌کند` |
| tile 1 sub-line 2 (`.o-s.neg.b`) | `زیان واقعی است و در سود و زیان می‌آید` |
| tile 2 title (`.o-t`, `sliders` 16) | `اصلاح موجودی` |
| tile 2 sub-line 1 (`.o-s`) | `شمارش انبار با سیستم نمی‌خواند (+ یا −)` |
| tile 2 sub-line 2 (`.o-s.b`) | `فقط شمارش را درست می‌کند و در سود و زیان نمی‌آید` |

The `−` in tile 2's sub-line is U+2212 MINUS SIGN, matching `fa()`'s negative sign.

### Form (desktop)

| Slot | String |
|---|---|
| card title (`#af`, `.t-h2`) | `ثبت تعدیل` |
| label | `کالا` |
| item buttons (short names) | `پوستر تور ۱۴۰۴` · `جعبه وینیل` · `نوار چسب` · `کاغذ پرکننده` |
| item metadata (`.help`, template) | `{kind} · موجودی {stock} {unit} · بهای واحد {cost} تومان` |
| — sample, `default` preset | `محصول · موجودی ۴۲ عدد · بهای واحد ۹۵٬۰۰۰ تومان` |
| — sample, `over` preset | `ماده · موجودی ۸ عدد · بهای واحد ۹۵٬۰۰۰ تومان` |
| — sample, `add` preset | `ماده · موجودی ۱٫۵ کیلوگرم · بهای واحد ۹۰٬۰۰۰ تومان` |
| label (correction only) | `جهت` |
| direction option 1 (`plus` 14) | `افزایش` |
| direction option 2 (`minus` 14) | `کاهش` |
| label (`for="aq"`) | `مقدار` |
| suffix | the item's unit — `عدد` · `رول` · `کیلوگرم` |
| quantity help, product | `محصول: فقط عدد صحیح` |
| quantity help, material | `ماده: اعشار مجاز است (مثلاً ۰٫۵)` |
| label (`for="uc"`) | `بهای واحد موجودی اضافه‌شده` + `(اختیاری)` in `.opt` |
| suffix | `تومان` |
| unit-cost help (template) | `خالی بماند = بهای فعلی ({cost} تومان). اگر وارد شود، میانگین موزون به‌روز می‌شود.` |
| — sample, `add` preset | `خالی بماند = بهای فعلی (۹۰٬۰۰۰ تومان). اگر وارد شود، میانگین موزون به‌روز می‌شود.` |
| label (`for="ar"`) | `دلیل` |

Reason values seeded by the presets (they are input **values**, not placeholders): `پارگی هنگام بسته‌بندی` (default) · `له‌شدگی` (over) · `شمارش انبار` (fraction) · `بسته پیدا شد در شمارش` (add).

### Preview (desktop)

| Slot | String |
|---|---|
| card title (`#ap`, `.t-h2`) | `پیش‌نمایش` |
| kind badge, waste (`.badge.st-loss`) | `ضایعات` |
| kind badge, correction + (`.badge.st-paid`) | `اصلاح +` |
| kind badge, correction − (`.badge.st-pending`) | `اصلاح −` |
| before caption | `موجودی فعلی` |
| after caption | `پس از ثبت` |
| unit caption (both sides) | the item's unit |
| valuation label, waste | `زیان ضایعات (در سود و زیان)` |
| valuation label, correction + | `افزایش ارزش موجودی (بدون اثر در سود و زیان)` |
| valuation label, correction − | `کاهش ارزش موجودی (بدون اثر در سود و زیان)` |
| valuation value, none/blocked | `—` |
| weighted-average label | `میانگین بهای واحد` |
| note, waste | `ضایعات زیان واقعی است و در سود و زیان می‌آید — در ردیف «ضایعات». ارزش آن با بهای تمام‌شده همین امروز ثبت و ذخیره می‌شود و با تغییر بعدی بهای تمام‌شده عوض نمی‌شود.` |
| note, correction | `اصلاح موجودی فقط شمارش را درست می‌کند و در سود و زیان نمی‌آید؛ فقط موجودی و ارزش انبار تغییر می‌کند.` |
| primary button | `ثبت تعدیل` |

### History (desktop)

| Slot | String |
|---|---|
| card title (`#ah`, `.t-h2`) | `تاریخچه تعدیل‌ها` |
| filter segment | `همه` (`.on`) · `ضایعات` · `اصلاح` |
| item filter select | `کالا:` + `همه` |
| period select (`cal` 14) | `شهریور ۱۴۰۵` |
| column headers | `تاریخ` · `کالا` · `نوع` · `مقدار` · `قبل ← بعد` · `ارزش (تومان)` · `اثر در سود و زیان` · `دلیل` |
| type badges | `ضایعات` (`.st-loss`) · `اصلاح +` (`.st-paid`) · `اصلاح −` (`.st-pending`) |
| P&L-effect cell, waste | `ردیف ضایعات` (`.t-cap.neg.b`) |
| P&L-effect cell, correction | `بدون اثر` (`.t-cap.muted`) |

Rows, verbatim:

| تاریخ | کالا | نوع | مقدار | قبل ← بعد | ارزش (تومان) | اثر در سود و زیان | دلیل |
|---|---|---|---|---|---|---|---|
| `۱۴۰۵/۰۶/۲۷` | `پوستر تور ۱۴۰۴` | `ضایعات` | `−۳ عدد` | `۴۵ ← ۴۲` | `−۲۸۵٬۰۰۰` | `ردیف ضایعات` | `آب‌دیدگی در انبار` |
| `۱۴۰۵/۰۶/۲۲` | `تی‌شرت خام مشکی L` | `ضایعات` | `−۲ عدد` | `۸ ← ۶` | `−۵۲۰٬۰۰۰` | `ردیف ضایعات` | `خطای چاپ سیلک` |
| `۱۴۰۵/۰۶/۱۶` | `کاغذ پرکننده` | `اصلاح +` | `+۰٫۵ کیلوگرم` | `۱ ← ۱٫۵` | `+۴۵٬۰۰۰` | `بدون اثر` | `شمارش ماهانه` |
| `۱۴۰۵/۰۶/۱۱` | `جعبه وینیل` | `ضایعات` | `−۲ عدد` | `۱۰ ← ۸` | `−۱۹۰٬۰۰۰` | `ردیف ضایعات` | `له‌شدگی در حمل` |
| `۱۴۰۵/۰۶/۰۹` | `استیکر پک` | `اصلاح −` | `−۷ عدد` | `۱۲۷ ← ۱۲۰` | `−۲۶۶٬۰۰۰` | `بدون اثر` | `شمارش ماهانه` |

Footnote below the table (the rule, in the product's own words):

```
فقط ردیف‌های «ضایعات» به گزارش سود و زیان می‌روند و با بهای تمام‌شده همان روز ارزش‌گذاری می‌شوند. «اصلاح موجودی» هیچ‌وقت در سود و زیان نمی‌آید.
```

### Mobile copy

| Slot | String |
|---|---|
| kind segment | `ضایعات` (`.on`) · `اصلاح موجودی` |
| help paragraph (`<b class="neg">ضایعات</b>` … `<b>اصلاح موجودی</b>`) | `ضایعات زیان واقعی است و در سود و زیان می‌آید (به بهای تمام‌شده همان روز). اصلاح موجودی فقط شمارش را درست می‌کند و در سود و زیان نمی‌آید.` |
| label | `کالا` |
| select line 1 | `جعبه وینیل` |
| select line 2 | `ماده · موجودی ۸ عدد` |
| label | `مقدار` |
| value | `۱۰` |
| suffix | `عدد` |
| error (`.err`, `role="alert"`, `alert` 14) | `بیشتر از موجودی فعلی است — فقط ۸ عدد موجود است.` |
| label | `دلیل` |
| value | `له‌شدگی` |
| before caption | `موجودی فعلی` |
| before value | `۸` |
| after caption | `پس از ثبت` |
| after value | `—` (`.neg`) |
| section heading (`.t-h3`) | `اخیر` |
| recent card 1 | `پوستر تور ۱۴۰۴` / `۱۴۰۵/۰۶/۲۷ · ضایعات −۳ · ۴۵ ← ۴۲` / `−۲۸۵٬۰۰۰` |
| recent card 2 | `کاغذ پرکننده` / `۱۴۰۵/۰۶/۱۶ · اصلاح +۰٫۵ کیلوگرم · بدون اثر در سود و زیان` / `+۴۵٬۰۰۰` |
| sticky footer button | `ثبت تعدیل` |

Note that the mobile over-stock error **drops the item name** that the desktop message includes (`— فقط ۸ عدد موجود است.` vs `— فقط ۸ عدد «جعبه وینیل» موجود است.`); see §4 and §7.

### Empty · loading · error (the `[[STATES:…]]` / `[[MSTATES:…]]` macro)

Desktop: `[[STATES:sliders|هنوز تعدیلی ثبت نشده|وقتی کالا خراب می‌شود یا شمارش انبار با سیستم نمی‌خواند، این‌جا ثبت کنید تا موجودی و گزارش‌ها درست بمانند.|ثبت تعدیل|تاریخچه تعدیل موجودی]]`. Mobile: `[[MSTATES:sliders|هنوز تعدیلی ثبت نشده|ضایعات و اصلاح شمارش انبار را این‌جا ثبت کنید.|ثبت تعدیل|تعدیل‌ها]]`.

| Board | Slot | String |
|---|---|---|
| empty (both) | art icon | `sliders` at 28 (in `.e-art`) |
| empty (both) | title (`.e-t`) | `هنوز تعدیلی ثبت نشده` |
| desktop empty | body (`.e-d`) | `وقتی کالا خراب می‌شود یا شمارش انبار با سیستم نمی‌خواند، این‌جا ثبت کنید تا موجودی و گزارش‌ها درست بمانند.` |
| mobile empty | body | `ضایعات و اصلاح شمارش انبار را این‌جا ثبت کنید.` |
| empty (both) | CTA (`plus` 16) | `ثبت تعدیل` |
| loading (both) | `aria-label` | `در حال بارگذاری` |
| desktop error | title | `تاریخچه تعدیل موجودی بارگذاری نشد` |
| mobile error | title | `تعدیل‌ها بارگذاری نشد` |
| error (both) | body | `اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.` |
| error (both) | button (`.btn.btn-outline`, `refresh` 16) | `تلاش دوباره` |

Empty/error padding `96px 24px` desktop, `48px 20px` mobile; the error art disc is `background: var(--loss-soft); color: var(--loss)` with `cloudoff` 28. Loading is `.sk` skeletons inside `<section aria-busy="true">`: a 20 × 180px bar then 8 × 40px rows (desktop) / 5 × 84px blocks (mobile).

---

## 3. Interactive states designed

| element | states |
|---|---|
| **نوع تعدیل** tiles | `ضایعات` selected (`.opt.on`, `aria-checked="true"`) · `اصلاح موجودی` selected. Picking ضایعات also **forces جهت back to کاهش** (`setW: set({ kind: 'w', dir: 'm' })`); picking اصلاح keeps the current direction (`setC: set({ kind: 'c' })`) |
| **جهت** segment | hidden when نوع = ضایعات; when shown, `افزایش` on · `کاهش` on |
| **کالا** segment | one of four buttons `.on`; switching item re-derives the unit, the suffix, the metadata help, the decimal rule, the before/after figures and the valuation — and can therefore create or clear an error without the quantity changing |
| **مقدار** input | default · `.is-error` (all three error causes share one class) |
| Error row | hidden · visible `.err` with `role="alert"` — three distinct messages (§4) |
| **بهای واحد …** field | hidden (waste, or correction −) · shown (correction +); empty (help promises the current cost) · filled (weighted average recomputes live) |
| **دلیل** input | default only; it is pre-filled by every preset and has no placeholder, no error and no required rule |
| Preview badge | `ضایعات` `.st-loss` · `اصلاح +` `.st-paid` · `اصلاح −` `.st-pending` |
| After figure | value · `—` (blocked decrease) · `.neg` red tint whenever any error is active |
| Valuation row | `+value` (correction +) · `−value` (waste and correction −, `.neg`) · `—` |
| Weighted-average row | hidden · shown (`old ← new`) only for a correction + with a positive quantity |
| Note paragraph | waste text · correction text |
| **ثبت تعدیل** | enabled · `disabled` whenever `hasErr` |
| History filters | `همه` `.on` / `ضایعات` / `اصلاح`; the two selects have a resting state only (no open menu designed) |
| History row | one state — no hover, no row menu, no undo |
| Screen | ready (`default`) · blocked over-stock (`over`) · fractional-product error (`fraction`) · correction + with unit cost (`add`) · empty · loading · error |
| Mobile screen | one frozen frame (the over-stock error) + empty · loading · error; nothing is wired |

Focus ring is `box-shadow: 0 0 0 3px var(--ring)` (`../design-system.md` §7). Every error is text + an `alert` icon + `role="alert"`, so nothing depends on colour alone. **There is no dark artboard for this screen.**

---

## 4. Validation

All three rules live in one `if / else if / else if` chain, so **only one message can ever show** and the precedence is fixed:

```js
var q = numQ(S.q), plus = S.kind === 'c' && S.dir === 'p', sign = plus ? 1 : -1, err = '';
if (!(q > 0)) err = 'مقدار را وارد کنید.';
else if (it.int && Math.floor(q) !== q) err = 'تعداد محصول باید عدد صحیح باشد؛ فقط مواد می‌توانند اعشاری باشند.';
else if (!plus && q > it.stock) err = 'بیشتر از موجودی فعلی است — فقط ' + faQ(it.stock) + ' ' + it.unit + ' «' + it.name + '» موجود است.';
```

| # | precedence | condition | applies to | message (verbatim) |
|---|---|---|---|---|
| V1 | 1st | `!(numQ(value) > 0)` — empty, zero, or unparseable | every kind | `مقدار را وارد کنید.` |
| V2 | 2nd | `item.int && Math.floor(q) !== q` — a fractional quantity on a **product** | every kind | `تعداد محصول باید عدد صحیح باشد؛ فقط مواد می‌توانند اعشاری باشند.` |
| V3 | 3rd | `!plus && q > item.stock` — a decrease larger than current stock | ضایعات **and** اصلاح − | `بیشتر از موجودی فعلی است — فقط {faQ(stock)} {unit} «{name}» موجود است.` |

`hasErr` drives three things at once: `qCls: 'is-error'` on the input, the `.err` row, and `disabled="{{hasErr}}"` on `ثبت تعدیل`. There are no soft warnings on this screen — unlike record sale, every rule here is blocking and there is no "save as draft" escape.

### V2 — the fractional-quantity rule (artboard `Adjustments-Fraction`)

> `تعداد محصول باید عدد صحیح باشد؛ فقط مواد می‌توانند اعشاری باشند.`

Board state: item `پوستر تور ۱۴۰۴` (a **محصول**, `int: true`, stock 42), نوع = `اصلاح موجودی`, جهت = `کاهش`, مقدار = `۱٫۵`, دلیل = `شمارش انبار`. The quantity help under the field reads `محصول: فقط عدد صحیح`; the preview badge is `اصلاح −`, the after figure is `—` in red, the valuation row is `—` with the label `کاهش ارزش موجودی (بدون اثر در سود و زیان)`, and the save button is disabled.

This is the project-wide rule ("materials may have fractional quantities, products may not") enforced per item by the `int` flag, **not** per adjustment kind: a product cannot take `۰٫۵` as waste either. The decimal mark accepted and displayed is `٫` (U+066B); `numQ()` also accepts `/` as a decimal separator, so typing `۱/۵` parses to 1.5 and triggers the same error on a product.

### V3 — the over-stock rule (artboard `Adjustments-Over`)

> `بیشتر از موجودی فعلی است — فقط ۸ عدد «جعبه وینیل» موجود است.`

Board state: item `جعبه وینیل` (a **ماده**, `int: false`, stock 8, cost 95,000), نوع = `ضایعات`, مقدار = `۱۰`, دلیل = `له‌شدگی`. The input is `.is-error`, the after figure is `—` in red (the raw arithmetic would be `−۲`), the valuation row shows `—`, and `ثبت تعدیل` is disabled. Mobile shows the same case with the shortened message `بیشتر از موجودی فعلی است — فقط ۸ عدد موجود است.`

Three things to note:

- The name is quoted with Persian guillemets `«…»` and the stock figure is rendered with `faQ()`, so a fractional stock appears as e.g. `۱٫۵`.
- The rule keys off `!plus`, so it guards **corrections downward as well as waste** — stock can never be driven negative by this screen.
- Equality is allowed: `q === stock` passes and the after figure is `۰`. No warning is designed for zeroing an item out.

### Not validated (see §7)

- `دلیل` is never required, even for waste. It is a free-text input with no preset reason list.
- `بهای واحد موجودی اضافه‌شده` has no rule; `num()` strips everything non-numeric so it is always a non-negative integer, and `0` silently falls back to the item's current cost (`var uc = S.uc || it.cost`).
- There is no date to validate — the record is implicitly today's.
- Negative input is impossible: `numQ()` deletes the sign along with every other non-digit character, so "direction" is only ever expressed by the جهت control.

---

## 5. Logic

### 5.1 The two kinds, and the P&L rule

This is the correction this screen exists to enforce:

| | ضایعات (waste) | اصلاح موجودی (correction) |
|---|---|---|
| Direction | always a decrease (`dir` is forced to `m`) | `+` or `−`, chosen in جهت |
| Meaning | goods really destroyed or discarded | the count was wrong |
| Stock | decreases | increases or decreases |
| Inventory value | decreases | changes with the count |
| **Profit & loss** | **appears — in the `ضایعات` line, and only there** | **never appears, in any line** |
| Waste report | included | excluded |
| Valuation | `qty × item.cost on the day it was recorded`, frozen with the record | `qty × current average` (or the entered unit cost, for `+`) |

The rule is stated in the product in four places. Verbatim, the two that state it as a rule:

**a. The preview note for a correction** (`{{note}}` when `kind !== 'w'`):
```
اصلاح موجودی فقط شمارش را درست می‌کند و در سود و زیان نمی‌آید؛ فقط موجودی و ارزش انبار تغییر می‌کند.
```

**b. The history footnote** (below the table, `p.t-cap.muted`):
```
فقط ردیف‌های «ضایعات» به گزارش سود و زیان می‌روند و با بهای تمام‌شده همان روز ارزش‌گذاری می‌شوند. «اصلاح موجودی» هیچ‌وقت در سود و زیان نمی‌آید.
```

And the two supporting statements — the type tile's sub-line:
```
فقط شمارش را درست می‌کند و در سود و زیان نمی‌آید
```
and the mobile help paragraph, which states both halves in one sentence:
```
ضایعات زیان واقعی است و در سود و زیان می‌آید (به بهای تمام‌شده همان روز). اصلاح موجودی فقط شمارش را درست می‌کند و در سود و زیان نمی‌آید.
```

The corresponding waste note, which carries the day-of-record valuation rule:
```
ضایعات زیان واقعی است و در سود و زیان می‌آید — در ردیف «ضایعات». ارزش آن با بهای تمام‌شده همین امروز ثبت و ذخیره می‌شود و با تغییر بعدی بهای تمام‌شده عوض نمی‌شود.
```

### 5.2 The «اثر در سود و زیان» column

The history table makes the rule auditable row by row. The column has exactly **two** values:

| value | class | rows |
|---|---|---|
| `ردیف ضایعات` | `.t-cap.neg.b` | every `ضایعات` row — it names the P&L line the value lands in |
| `بدون اثر` | `.t-cap.muted` | every `اصلاح +` and `اصلاح −` row |

Note that a correction still shows a number in the `ارزش (تومان)` column (`+۴۵٬۰۰۰`, `−۲۶۶٬۰۰۰`) — that is the change in **inventory value**, which is a balance-sheet movement, not an expense. The `بدون اثر` cell is what tells the reader it stops there. The same split is repeated in the reports screen's waste table footnote: `«اصلاح موجودی» (تصحیح شمارش انبار) در این گزارش و در سود و زیان نمی‌آید — آن را در «تعدیل موجودی» ببینید.` and in the P&L tooltip for the `ضایعات` line: `ارزش کالا و موادی که خراب یا دور ریخته شده، به بهای تمام‌شده همان روزِ ثبت ضایعات. «اصلاح موجودی» (تصحیح شمارش انبار) در این ردیف و در هیچ ردیف دیگری از سود و زیان نمی‌آید.`

P&L placement: `../logic/formulas.md` §7 puts `waste` between `refundAndCancelLosses` and `operatingExpenses`, below gross profit — `− waste (ONLY ضایعات; stock corrections never appear here)`. The full rule pair is §8 of the same file.

### 5.3 Valuation at the cost of the day it was recorded

```
wasteValue = qty × item.cost  // the cost in force on the day of the record, stored with the record
```

The value is **frozen at write time**. A purchase next week that raises the weighted average (`../logic/formulas.md` §3) must not change last week's waste figure; likewise a production run that lowers it. The screen says so twice — `ارزش آن با بهای تمام‌شده همین امروز ثبت و ذخیره می‌شود و با تغییر بعدی بهای تمام‌شده عوض نمی‌شود.` in the preview, and `با بهای تمام‌شده همان روز ارزش‌گذاری می‌شوند` in the footnote — and the reports screen repeats it for the month total: `ارزش هر ضایعات با بهای تمام‌شده همان روزِ ثبت محاسبه و ذخیره می‌شود؛ تغییر بعدی بهای تمام‌شده این عددها را عوض نمی‌کند.`

Implementation consequence: the adjustment row needs its own `unitCost` and `value` columns, denormalised at insert; the P&L waste line and the waste report must both read those stored values, never re-multiply by today's cost. This is the same "copied at write time" pattern as the postage estimate on an order (`09-postage.md` §5.3) and the kit cost on a sale (`../logic/formulas.md` §5).

### 5.4 The computation, verbatim

```js
var q = numQ(S.q), plus = S.kind === 'c' && S.dir === 'p', sign = plus ? 1 : -1, err = '';
// …validation chain (see §4)…
var after = it.stock + sign * (q || 0), value = q * it.cost;
var uc = S.uc || it.cost, newAvg = plus && q > 0 ? (it.stock * it.cost + q * uc) / (it.stock + q) : it.cost;
```
and the display mapping:
```js
beforeT: faQ(it.stock), afterT: err && !plus ? '—' : faQ(after), afterCls: err ? 'neg' : '',
valueLabel: S.kind === 'w' ? 'زیان ضایعات (در سود و زیان)'
          : (plus ? 'افزایش ارزش موجودی (بدون اثر در سود و زیان)' : 'کاهش ارزش موجودی (بدون اثر در سود و زیان)'),
valueT: q > 0 && !err ? (plus ? '+' : '−') + fa(plus ? q * uc : value) + ' تومان' : '—', valueCls: plus ? '' : 'neg',
showAvg: plus && q > 0, newAvgT: fa(newAvg) + ' تومان',
```

- `sign` is `+1` only for a correction **+**; waste and correction **−** both decrement.
- Quantities are formatted with `faQ()` (Persian digits, `٬` for thousands, `٫` for the decimal, up to 3 decimal places, trailing zeros stripped) and money with `fa()` (integer money, `٬`; money is integer Rial, Toman display has at most one decimal) — never mix the two helpers.
- The valuation uses **the entered unit cost** for an increase (`q * uc`) and **the current average** otherwise (`q * it.cost`). So a correction + is valued at what the found stock actually cost, which is also what feeds the new average.
- Weighted average, only for a correction +: the §3 formula, `newAverage = (stockOnHand × currentAverage + incomingQty × incomingUnitCost) ÷ (stockOnHand + incomingQty)`. When the unit-cost field is left empty, `uc` falls back to `it.cost`, which makes `newAvg === it.cost` — the average is unchanged, exactly as the help text promises.
- The average is **never** recomputed for a decrease (waste or correction −): removing units at the current average leaves the average untouched.

### 5.5 What committing a record must do

| kind | stock | inventory value | P&L | weighted average |
|---|---|---|---|---|
| ضایعات | `stock − q` | `− q × cost(today)` | `ضایعات` line, value frozen | unchanged |
| اصلاح − | `stock − q` | `− q × cost(today)` | nothing | unchanged |
| اصلاح + | `stock + q` | `+ q × (entered unit cost, else current cost)` | nothing | recomputed by §3 if a unit cost was entered |

Nothing else moves: adjustments touch no order, no invoice and no partner distribution. They do feed the reports screen's `ضایعات` card (waste only) and the month's `ضایعات` P&L line.

---

## 6. Sample data used

The item picker uses its own four-item `ITEMS` array, each row a subset of `../data/sample-data.md` (`CATALOG` p5 and `MATERIALS` m10, m12, m13):

| id | name (short) | kind | stock | unit | cost | `int` | source |
|---|---|---|---|---|---|---|---|
| a1 | پوستر تور ۱۴۰۴ (`پوستر تور ۱۴۰۴`) | `محصول` | 42 | عدد | 95,000 | **true** | `CATALOG` p5 |
| a2 | جعبه وینیل (`جعبه وینیل`) | `ماده` | 8 | عدد | 95,000 | false | `MATERIALS` m10 |
| a3 | نوار چسب لوگودار (`نوار چسب`) | `ماده` | 2 | رول | 150,000 | false | `MATERIALS` m12 |
| a4 | کاغذ پرکننده (`کاغذ پرکننده`) | `ماده` | 1.5 | کیلوگرم | 90,000 | false | `MATERIALS` m13 |

`int: true` on the one product and `false` on the three materials is what drives V2. Note a1 and a2 share a cost of 95,000, which is a coincidence in the sample data, not a relationship.

### Preset `default` (artboard `Adjustments`)

item a1 · نوع ضایعات · مقدار `۳` · دلیل `پارگی هنگام بسته‌بندی`

```
before  = 42
after   = 42 − 3            = 39          → ۳۹
value   = 3 × 95,000        = 285,000     → −۲۸۵٬۰۰۰ تومان   (label «زیان ضایعات (در سود و زیان)»)
average : unchanged (95,000) — row hidden
badge   : ضایعات (st-loss) ·  note: the waste note ·  save: enabled
```

### Preset `over` (artboard `Adjustments-Over`) — blocked

item a2 · نوع ضایعات · مقدار `۱۰` · دلیل `له‌شدگی`

```
q = 10 > stock 8  → V3
before  = 8 → ۸
after   = 8 − 10 = −2, suppressed → «—» (.neg)
value   → «—»
save    : disabled ·  error: بیشتر از موجودی فعلی است — فقط ۸ عدد «جعبه وینیل» موجود است.
```

### Preset `fraction` (artboard `Adjustments-Fraction`) — blocked

item a1 (a product) · نوع اصلاح موجودی · جهت کاهش · مقدار `۱٫۵` · دلیل `شمارش انبار`

```
numQ('۱٫۵') = 1.5 ; item.int = true ; floor(1.5) ≠ 1.5 → V2
before  = 42 → ۴۲
after   → «—» (.neg)              (the raw value would be 40.5)
value   → «—»                     label «کاهش ارزش موجودی (بدون اثر در سود و زیان)»
badge   : اصلاح − (st-pending) ·  note: the correction note ·  save: disabled
```

### Preset `add` (artboard `Adjustments-Add`) — correction + with a unit cost

item a4 · نوع اصلاح موجودی · جهت افزایش · مقدار `۰٫۵` · بهای واحد `۹۲٬۰۰۰` · دلیل `بسته پیدا شد در شمارش`

```
before  = 1.5                                    → ۱٫۵
after   = 1.5 + 0.5 = 2                          → ۲
value   = 0.5 × 92,000 = 46,000                  → +۴۶٬۰۰۰ تومان
          (label «افزایش ارزش موجودی (بدون اثر در سود و زیان)»)
newAvg  = (1.5 × 90,000 + 0.5 × 92,000) ÷ (1.5 + 0.5)
        = (135,000 + 46,000) ÷ 2 = 181,000 ÷ 2 = 90,500   → ۹۰٬۰۰۰ تومان ← ۹۰٬۵۰۰ تومان
badge   : اصلاح + (st-paid) ·  save: enabled
```
Left empty, the unit-cost field would give `uc = 90,000` → `value = 45,000` and `newAvg = 90,000` (unchanged) — which is exactly the `۱۴۰۵/۰۶/۱۶` history row.

### History rows, arithmetic checked against the sample costs

| کالا | qty | unit cost | value | check |
|---|---|---|---|---|
| پوستر تور ۱۴۰۴ | 3 | 95,000 (`CATALOG` p5) | −285,000 | 3 × 95,000 = 285,000 ✓ |
| تی‌شرت خام مشکی L | 2 | 260,000 (`MATERIALS` m5) | −520,000 | 2 × 260,000 = 520,000 ✓ |
| کاغذ پرکننده | 0.5 | 90,000 (m13) | +45,000 | 0.5 × 90,000 = 45,000 ✓ |
| جعبه وینیل | 2 | 95,000 (m10) | −190,000 | 2 × 95,000 = 190,000 ✓ |
| استیکر پک | 7 | 38,000 (`CATALOG` p8) | −266,000 | 7 × 38,000 = 266,000 ✓ |

Stock continuity also checks out against the current sample stocks: `۴۵ ← ۴۲` leaves p5 at 42 ✓, `۸ ← ۶` leaves m5 at 6 ✓, `۱ ← ۱٫۵` leaves m13 at 1.5 ✓, `۱۰ ← ۸` leaves m10 at 8 ✓, `۱۲۷ ← ۱۲۰` leaves p8 at 120 ✓.

### The month's waste total (what reaches the P&L)

From `../data/sample-data.md` and the reports screen's `ضایعات` card, only the **ضایعات** rows count:

```
285,000  پوستر تور ۱۴۰۴   (3 × 95,000)
520,000  تی‌شرت خام مشکی L (2 × 260,000)
290,000  کاست نسخه محدود   (1 × 290,000)   ← not in this screen's 5-row table
190,000  جعبه وینیل        (2 × 95,000)
  3,000  کاغذ کرافت        (0.25 × 12,000) ← not in this screen's 5-row table
─────────
1,288,000  → P&L «ضایعات» −۱٬۲۸۸٬۰۰۰
```
The two correction rows (`+45,000` and `−266,000`) are **excluded**, which is the whole point. Note the reports screen's waste table lists five waste rows while this screen's history shows only three of them plus the two corrections — see §7.

---

## 7. Open questions for this screen

- **There is no date field.** Every other entry form in the app (postage, purchases, expenses) has `تاریخ …`; this one does not, so a record is implicitly dated today (`۳۱ شهریور ۱۴۰۵`) and back-dating is impossible. That collides directly with the valuation rule: if waste is priced at "the cost on the day it was recorded", the design needs to say whether a stock count finished on the 31st but covering the 28th is dated (and priced) on the 28th or the 31st.
- **The history and the waste report disagree about their contents.** This screen's table shows five شهریور rows (3 waste + 2 corrections) totalling 995,000 of waste, while `Reports.dc.html` lists five waste rows totalling 1,288,000 — including `کاست نسخه محدود` (−290,000) and `کاغذ کرافت` (−3,000), which appear nowhere here, and omitting `تی‌شرت خام مشکی L`'s reason wording (`خطای چاپ` vs `خطای چاپ سیلک`). One of the two lists must become a view of the other, and the reason strings must be single-sourced.
- **The item picker is a 4-button segmented control.** The real catalogue is 11 products + 16 materials; nothing is designed for searching, grouping products vs materials, paging, or excluding deactivated products (`p11`) and service-type materials (`m6`–`m8`, which have no stock at all and cannot be adjusted). Mobile has a `.select` that opens **no menu** — there is no picker artboard for it.
- **The blocked-decrease preview is inconsistent.** `afterT: err && !plus ? '—' : faQ(after)` suppresses the after-figure only when the adjustment is a decrease. With a correction **+** that has a fractional quantity on a product, the error shows but the after-figure still renders (`۴۳٫۵`) in red — a number the user is being told is invalid. Decide one behaviour for all error cases.
- **`دلیل` is optional and unstructured.** Waste can be saved with an empty reason, there is no preset reason list (the sample data uses five different free-text strings), nothing is searchable, and there is no attachment/photo affordance — which is what an auditor would want for a write-off. Decide whether reason is required for ضایعات specifically.
- **No zero-stock and no zeroing-out design.** No sample item has stock 0, so the V3 message for that case (`… — فقط ۰ عدد «…» موجود است.`) is never shown and may want its own wording, as record sale has for `ناموجود`. Equally, a decrease exactly equal to stock is allowed silently; no confirmation is designed for taking an item to zero.
- **No success, no editing, no reversal.** There is no toast, no success board, no post-save state, no row hover, no row menu, no edit and no delete/undo for a committed adjustment — and a mistyped waste quantity is both a stock error and a P&L error. Whether a correction of a correction is a new row or an edit in place is undecided.
- **Mobile is a dead, partial frame.** It drops جهت, the unit-cost field, the valuation row, the weighted-average row, the per-kind note, the whole history table and its three filters; nothing is wired; and its over-stock message differs from desktop's (`— فقط ۸ عدد موجود است.` without the item name). Either single-source the message or record the shortened form as intentional.
- **The history filters do nothing and have no empty result.** `همه / ضایعات / اصلاح`, `کالا: همه` and `شهریور ۱۴۰۵` are all static; no open menu, no month picker, no "no rows match" state, no pagination and no export are designed, although the table is the only place either kind of adjustment can be reviewed.
- **`.badge.st-loss` is an undocumented token.** It exists in `rebel.css` (`background: var(--loss-soft); color: var(--loss)`) and is used for the `ضایعات` badges here, but `../design-system.md` lists only `st-draft / st-pending / st-paid / st-done / st-cancel / st-refund`. Also worth settling: `اصلاح +` reuses `st-paid` (blue) and `اصلاح −` reuses `st-pending` (amber), colours that mean "paid" and "awaiting" everywhere else in the app.
- **A correction − is valued at the current average with no override**, while a correction + can carry a unit cost. If a count shortfall is actually old, cheaper stock, there is no way to say so. Decide whether that asymmetry is intended.
- **No dark artboard, and no route.** `Postage` has a `-Dark` board; this screen has none, so the `st-loss` / `st-pending` badges, the `--surface-2` before/after panel and the red error states are undrawn in dark mode. Routes are undefined throughout (`00-app-shell.md` §7), and no screen links **into** this one — the low-stock warnings on the dashboard and products screens point elsewhere.
