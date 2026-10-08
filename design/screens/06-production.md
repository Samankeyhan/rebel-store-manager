# 06 — تولید (Production)

Route: `/production` · sidebar key `production` (group «انبار و عملیات») · page title in top bar: **تولید**

Where raw materials become sellable products, and where a product's cost is actually born. Three tabs on one route: **اجرای تولید** (run a batch — pick a product, type a quantity, see exactly which materials will be consumed, what the batch costs, and what it does to the product's weighted-average cost), **دستور تولید** (the recipe editor, whose one real idea is the per-unit / once-per-batch toggle), and **سوابق تولید** (an immutable log of past runs). The run tab is a live preview: every keystroke in the quantity stepper re-derives the whole material table, the batch cost, the per-unit cost and the new average, and a material shortage hard-blocks the run.

Artboards: `Production.dc.html` (default, tab اجرای تولید, qty ۳۰, 1440 × 1000), `Production-Shortage` (same tab with `qty: 50` → blocked, h 1060), `Production-Recipe` (tab دستور تولید, 1440 × 1000), `Production-History` (tab سوابق تولید, 1440 × 760), `Production-States` (empty · loading · error side by side, 3 × 1440 × 760), `ProductionMobile.dc.html` (390 × 1060, shortage state), `ProductionMobile-States` (3 × 390 × 844).
The desktop artboard is interactive: props `view` (`run | recipe | history`), `qty` (int, default 30), `state`, `theme`, `h`. The recipe array, the material table, the shortage list, the batch cost and the new average are all computed in that file's `<script>` from `MATERIALS` in `helpers.js`.

---

## 1. Layout

### Desktop — tab «اجرای تولید» (1440 × 1000; 1060 in the shortage variant)

```
┌──────────────── 1440 ─────────────────────────────────────────────────────┐
│ ┌ content 1176 ─────────────────────────────────┐ ┌ sidebar 264 (right) ┐ │
│ │ top bar 64  «تولید»                           │ │ production = on     │ │
│ ├───────────────────────────────────────────────┤ │                     │ │
│ │ main 24/32/40 · gap 20 · inner 1112           │ │                     │ │
│ │ ┌ tabs 40 ──────────────────────────────────┐ │ │                     │ │
│ │ │ اجرای تولید · دستور تولید · سوابق تولید ۱۴│ │ │                     │ │
│ │ ├ flex gap 24, align-items: flex-start ─────┤ │ │                     │ │
│ │ │ ┌ preview card (grow) 728 ─┬ form 360 ──┐ │ │ │                     │ │
│ │ │ │ header: title + «ویرایش  │ «تولید جدید»│ │ │ │                     │ │
│ │ │ │   دستور» link            │ 1 محصول     │ │ │ │                     │ │
│ │ │ │ [shortage alert]         │ 2 تعداد 160 │ │ │ │                     │ │
│ │ │ │ material table (6 cols)  │ 3 تاریخ     │ │ │ │                     │ │
│ │ │ │ tfoot: هزینه کل           │ 4 یادداشت   │ │ │ │                     │ │
│ │ │ │ 3-col tiles: 1 | span 2  │             │ │ │ │                     │ │
│ │ │ │ [ثبت تولید ۳۰ عدد] + note│             │ │ │ │                     │ │
│ │ └─┴──────────────────────────┴─────────────┘ │ │                     │ │
│ └───────────────────────────────────────────────┘ └─────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

- `main`: `padding: 24px 32px 40px; gap:20` → inner width **1112**. Everything except the empty/loading/error blocks sits inside the `isReady` guard, **tabs included** (unlike screen 05, where the toolbar survives all states).
- Row: `display:flex; gap:24px; align-items:flex-start`. Form card `width:360px; flex-shrink:0` (first in DOM → physically **right** in RTL); preview card `.grow` → **728**.
- Form card: `.card-h` `padding:16px 20px` with `h2.t-h2`; `.card-b` `padding:20px; gap:16`.
- Preview card: `overflow:hidden`; `.card-h` holds a two-line title block and a `.t-sm.b` link; the shortage alert is inset `margin:16px 20px 0`; the table gets `margin-top:8px`; the tile grid is `padding:16px 20px; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12` with a 1px top border; the submit row is `padding:0 20px 20px; display:flex; gap:8; align-items:center`.

**Tab order (exact, `role="tablist"`)**

1. `اجرای تولید` — 16px factory icon
2. `دستور تولید` — 16px edit icon
3. `سوابق تولید` — 16px clock icon + count pill `۱۴`

**Form field order (exact)**

1. **محصول** — `.select` (40 high) showing a bold product name on one side and a `.stock` pill on the other; `.help` under it.
2. **تعداد تولید** — `.stepper` `width:160px` (`+` button 32 wide, centred number input `#q`, `−` button 32 wide); `.help` under it ending in a bold tabular number.
3. **تاریخ تولید** — `.select` with a 16px calendar icon + bold Jalali date on one side, `.t-cap.muted` on the other.
4. **یادداشت** `(اختیاری)` — text input (`#nt`) with placeholder.

**Material preview table — column order**

| # | header | align | content |
|---|---|---|---|
| 1 | `ماده` | start, `.b` | material name |
| 2 | `نحوه محاسبه` | start | `.chip` per-unit / `badge st-refund` per-batch |
| 3 | `مقدار لازم` | `.n.num` | quantity + unit |
| 4 | `موجودی` | `.n.num.muted2` | stock, or `خدماتی` |
| 5 | `پس از تولید` | `.n.num` (+`.neg.b` when short) | remaining stock, `کمبود N`, or `—` |
| 6 | `هزینه (تومان)` | `.n.num.b` | row cost |

`tfoot`: one cell spanning columns 1–5 with the label, then the batch total (`.n.num`), on `--surface-2`, bold, 1px top border. Short rows are tinted `var(--loss-soft)`.

**Result tiles** (3-column grid; both tiles on `--surface-2`, `border-radius:10px; padding:12px`)

1. col 1 — caption, then the per-unit cost at `font-size:20px` bold tabular, then a `.t-cap.muted` derivation line.
2. cols 2–3 (`grid-column: span 2`) — caption, then a row of: old average at 18px in `--text-2`, an 18px chevron (pointing in the reading direction), new average at 22px bold, and a delta badge; then a `.t-cap.muted.num` line showing the literal formula with its numbers substituted.

### Desktop — tab «دستور تولید» (`Production-Recipe`, 1440 × 1000)

```
┌ editor card (grow) 808 ──────────────┬ product list 280 ┐
│ header: «دستور تولید: …» + «ذخیره     │ «محصولات» label  │
│   دستور»                              │ 6 × 44px rows    │
│ card-b (padding 20, gap 14):          │ each: name +     │
│  · alert-info (per-unit vs per-batch) │   badge/caption  │
│  · column header row                  │                  │
│  · 4 recipe rows                      │                  │
│  · [+ افزودن ماده یا خدمت]             │                  │
│  · .sep                               │                  │
│  · 3 summary tiles                    │                  │
└───────────────────────────────────────┴──────────────────┘
```

- Same `flex; gap:24; align-items:flex-start`. List card `width:280px; flex-shrink:0; padding:8px` (physically right); editor `.grow` → **808**.
- List rows: `height:44px; padding:0 10px; border-radius:8px`, name at one end, a `badge`/caption at the other. The selected row has `background: var(--red-soft)` and `font-weight:700`.
- Recipe row grid (used for the header row and every material row): `grid-template-columns: minmax(0,1fr) 110px 290px 130px 36px; gap:12px; align-items:center`. Inside the 808-wide card's 20px padding the free column resolves to **154px** (768 − 566 fixed − 48 gaps).
- Field order within one recipe row: **1** material `.select` (two stacked lines: bold name + `.t-cap.muted` sub-line) · **2** quantity `.ig` (number input with `padding-left:44px` + unit `.sfx`) · **3** mode `.seg` at `width:100%` with two `flex-grow:1` buttons at `font-size:12.5px` · **4** cost text (`.num.b`) · **5** 32 × 32 ghost trash button (`aria-label="حذف"`).
- Summary tiles: `repeat(3, minmax(0,1fr)); gap:12`, each `--surface-2`, radius 10, padding 12, caption + bold tabular value.

### Desktop — tab «سوابق تولید» (`Production-History`, 1440 × 760)

- Filter row: `display:flex; gap:10` — two `.select`s with `width:auto; gap:10` (product filter, then a calendar-icon date-range button).
- One `.card` (`overflow:hidden`) with a 7-column `.tbl`, 5 static rows: `تاریخ` · `محصول` · `تعداد` (`.n`) · `هزینه کل (تومان)` (`.n`) · `بهای هر عدد (تومان)` (`.n.b`) · `میانگین بها پس از تولید` (`.n`) · `یادداشت` (`.muted2`). No action column.

### Mobile (390 × 1060; states 390 × 844)

`MobileBar` 56 high. `main`: `padding: 14px 16px 100px; gap:12` → content width **358**.

1. `.seg` as `grid-template-columns: repeat(3, minmax(0,1fr))`, each button 40 high: `اجرا` (on) · `دستور` · `سوابق`.
2. `.card` `padding:14px; gap:12` with two fields: **محصول** (`.select` 48 high, bold name + stock pill) and **تعداد تولید** (`.stepper.is-error` 48 high, 48-wide `+`/`−` buttons, `aria-label="تعداد"`).
3. `.alert.alert-err[role=alert]` with an 18px alert icon: bold title line + body.
4. `.card` — a 14px `.t-h3` section title, then one 4-row list (each `padding:10px 14px`, 1px top border, `justify-content:space-between`): left a bold 13px name + a `.t-cap.muted` derivation line, right either a `.t-cap.neg.b` shortage or a `.num.t-sm` cost. Short rows are tinted `--loss-soft`. Then a footer block (`padding:12px 14px`, 1px top border, `gap:4`) of three `.sl` rows.
5. Fixed bottom bar: `position:absolute; left:0; right:0; bottom:0; padding:12px 16px 20px`, `--surface`, 1px top border, one full-width `btn-primary btn-lg` (48 high), **always `disabled`** in this artboard.

The recipe and history tabs have no mobile board; the three segment buttons are static markup.

---

## 2. Copy (verbatim)

### Tabs

| tab | label | pill |
|---|---|---|
| 1 | `اجرای تولید` | — |
| 2 | `دستور تولید` | — |
| 3 | `سوابق تولید` | `۱۴` |

### Run form

| slot | string |
|---|---|
| card title | `تولید جدید` |
| field 1 label | `محصول` |
| field 1 value | `وینیل آلبوم اول` + stock pill `موجودی ۱۴` |
| field 1 help | `فقط محصولاتی که دستور تولید دارند.` |
| field 2 label | `تعداد تولید` |
| stepper `aria-label`s | `افزایش` · `کاهش` |
| field 2 help | `عدد صحیح؛ حداکثر با موجودی فعلی مواد: ۳۸` |
| field 3 label | `تاریخ تولید` |
| field 3 value | `۱۴۰۵/۰۶/۳۱` + `امروز` |
| field 4 label | `یادداشت` + `(اختیاری)` in `.opt` |
| field 4 placeholder | `مثلاً: پرس نوبت دوم` |

### Preview card

| slot | string |
|---|---|
| title | `پیش‌نمایش مصرف مواد` |
| caption | `۳۰ عدد «وینیل آلبوم اول» · دستور نسخه ۲` |
| link | `ویرایش دستور` (switches to the recipe tab) |
| table headers | `ماده` · `نحوه محاسبه` · `مقدار لازم` · `موجودی` · `پس از تولید` · `هزینه (تومان)` |
| mode labels | `به ازای هر عدد` (`.chip`) · `یک‌بار برای کل تولید` (`badge st-refund`) |
| service stock cell | `خدماتی` |
| service "after" cell | `—` |
| shortage "after" cell | `کمبود ۱۲` — `'کمبود ' + faQ(need - stock)` |
| tfoot label | `هزینه کل این تولید` |
| tile 1 caption | `بهای هر عدد در این تولید` |
| tile 1 derivation | `هزینه کل ÷ ۳۰` |
| tile 2 caption | `میانگین بهای تمام‌شده «وینیل آلبوم اول»` |
| tile 2 derivation | `(۱۴ عدد × ۱٬۳۸۰٬۰۰۰ + ۴۰٬۰۰۰٬۰۰۰) ÷ ۴۴ عدد` |
| submit button | `ثبت تولید ۳۰ عدد` (check icon; the number is the quantity) |
| submit note | `مواد کالایی از موجودی کم و ۳۰ عدد به موجودی محصول اضافه می‌شود.` |

Per-unit cost tile value is rendered with its unit: `۱٬۳۳۳٬۳۳۳ تومان`.

### Shortage alert (desktop, `role="alert"`)

Title line:

```
کمبود مواد — تولید ممکن نیست
```

Body — the per-material sentences joined by a single space, then a fixed tail:

```
۱۲ عدد «صفحه خام وینیل ۱۲ اینچ» کم است. ۵ عدد «کاور چاپی وینیل» کم است. حداکثر قابل تولید با موجودی فعلی: ۳۸ عدد.
```

Per-material sentence template (`fa(need - stock) + ' ' + unit + ' «' + name + '» کم است.'`):

```
۱۲ عدد «صفحه خام وینیل ۱۲ اینچ» کم است.
۵ عدد «کاور چاپی وینیل» کم است.
```

Two stacked actions on the end of the alert:

```
ثبت خرید مواد        (outline link → Purchases.dc.html)
تولید ۳۸ عدد          (ghost button; sets qty = maxBuildable)
```

### Recipe tab

| slot | string |
|---|---|
| list label | `محصولات` |
| list rows | `وینیل آلبوم اول` `۴ ماده` · `وینیل نسخه رنگی` `۴ ماده` · `کاست نسخه محدود` `۳ ماده` · `تی‌شرت لوگو مشکی (L)` `۳ ماده` · `تی‌شرت تور سفید (M)` `بدون دستور` · `سی‌دی آلبوم اول` `خریدنی` |
| editor title | `دستور تولید: وینیل آلبوم اول` |
| editor caption | `آخرین تغییر ۱۴۰۵/۰۴/۰۸` |
| save button | `ذخیره دستور` |
| column headers | `ماده یا خدمت` · `مقدار` · `نحوه محاسبه` · `هزینه` · (empty) |
| mode segment | `به ازای هر عدد` · `یک‌بار برای کل تولید` |
| row delete `aria-label` | `حذف` |
| add button | `افزودن ماده یا خدمت` |
| tile 1 caption | `هزینه به ازای هر عدد` |
| tile 2 caption | `هزینه یک‌بار برای هر تولید` |
| tile 3 caption | `بهای هر عدد در تولید ۳۰ / ۱۰۰ عددی` |

Row sub-labels (`(service ? 'خدماتی · ' : 'کالایی · ') + fa(cost) + ' تومان / ' + unit`):

```
کالایی · ۶۲۰٬۰۰۰ تومان / عدد
کالایی · ۱۸۰٬۰۰۰ تومان / عدد
خدماتی · ۱۲٬۰۰۰٬۰۰۰ تومان / نوبت
خدماتی · ۴٬۰۰۰٬۰۰۰ تومان / نوبت
```

Row cost strings — per-unit rows carry the multiplier as words, per-batch rows carry `یک‌بار`:

```
۶۲۰٬۰۰۰ × تعداد
۱۸۰٬۰۰۰ × تعداد
۱۲٬۰۰۰٬۰۰۰ یک‌بار
۴٬۰۰۰٬۰۰۰ یک‌بار
```

The explainer alert (`.alert.alert-info`, 18px info icon) — bold runs marked, `<br>` before the example:

```
title: «به ازای هر عدد» یا «یک‌بار برای کل تولید»؟
body:  **به ازای هر عدد**: مقدار در تعداد تولید ضرب می‌شود — هر وینیل یک «صفحه خام» لازم دارد. **یک‌بار برای کل تولید**: هزینه‌ای که هر نوبت تولید فقط یک بار پرداخت می‌شود، مثل مسترینگ یا طراحی جلد.
       مثال: در تولید ۳۰ عدد، «صفحه خام» ۳۰ بار مصرف می‌شود، اما «مسترینگ» فقط یک بار (۱۲٬۰۰۰٬۰۰۰ تومان) حساب و بین ۳۰ عدد تقسیم می‌شود — یعنی ۴۰۰٬۰۰۰ تومان برای هر عدد. هرچه تعداد تولید بیشتر باشد، سهم این هزینه در هر عدد کمتر است.
```

### History tab

Filters: `محصول:` + `همه` · `۱۴۰۵/۰۱/۰۱ تا ۱۴۰۵/۰۶/۳۱`.

Headers: `تاریخ` · `محصول` · `تعداد` · `هزینه کل (تومان)` · `بهای هر عدد (تومان)` · `میانگین بها پس از تولید` · `یادداشت`.

Rows verbatim:

| تاریخ | محصول | تعداد | هزینه کل | بهای هر عدد | میانگین بها پس از تولید | یادداشت |
|---|---|---|---|---|---|---|
| `۱۴۰۵/۰۶/۱۸` | `تی‌شرت لوگو مشکی (L)` | `۲۰` | `۸٬۲۰۰٬۰۰۰` | `۴۱۰٬۰۰۰` | `۴۱۰٬۰۰۰` | `چاپ سیلک نوبت سوم` |
| `۱۴۰۵/۰۵/۲۰` | `کاست نسخه محدود` | `۵۰` | `۱۴٬۰۰۰٬۰۰۰` | `۲۸۰٬۰۰۰` | `۲۹۰٬۰۰۰` | `—` |
| `۱۴۰۵/۰۴/۱۰` | `وینیل آلبوم اول` | `۴۰` | `۵۵٬۲۰۰٬۰۰۰` | `۱٬۳۸۰٬۰۰۰` | `۱٬۳۸۰٬۰۰۰` | `پرس اول` |
| `۱۴۰۵/۰۳/۲۲` | `وینیل نسخه رنگی` | `۲۰` | `۴۱٬۰۰۰٬۰۰۰` | `۲٬۰۵۰٬۰۰۰` | `۲٬۰۵۰٬۰۰۰` | `نسخه محدود رنگی` |
| `۱۴۰۵/۰۲/۱۴` | `آینه لوگو گرد` | `۱۵` | `۸٬۴۰۰٬۰۰۰` | `۵۶۰٬۰۰۰` | `۵۶۰٬۰۰۰` | `—` |

### Empty state (`[[STATES:factory|…]]`)

`.card` + `.empty` (`padding:96px 24px`), 56 × 56 `.e-art`, 28px factory icon:

```
title: هنوز تولیدی ثبت نشده
body:  ابتدا برای یک محصول «دستور تولید» بسازید: مواد، مقدار و این‌که هر ماده به ازای هر عدد مصرف می‌شود یا یک‌بار برای کل تولید.
cta:   ساخت دستور تولید
```

### Error state

```
title: اطلاعات تولید بارگذاری نشد
body:  اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.
cta:   تلاش دوباره   (outline, refresh icon)
```

### Loading state

`section[aria-busy="true"][aria-label="در حال بارگذاری"]`: one 20 × 180 skeleton, then 8 skeletons 40 high at `border-radius:10px`. No copy.

### Mobile copy

| slot | string |
|---|---|
| segment | `اجرا` · `دستور` · `سوابق` |
| محصول | `وینیل آلبوم اول` + `موجودی ۱۴` |
| تعداد تولید | value `۵۰`, `aria-label="تعداد"`, stepper `aria-label`s `افزایش` · `کاهش` |
| alert title | `کمبود مواد` |
| alert body | `۱۲ عدد «صفحه خام وینیل ۱۲ اینچ» کم است. حداکثر قابل تولید: ۳۸.` |
| section title | `مصرف مواد` |
| row 1 | `صفحه خام وینیل ۱۲ اینچ` / `به ازای هر عدد · لازم ۵۰ · موجودی ۳۸` / `کمبود ۱۲` |
| row 2 | `کاور چاپی وینیل` / `به ازای هر عدد · لازم ۵۰ · موجودی ۴۵` / `کمبود ۵` |
| row 3 | `مسترینگ و کات لاکر` / `یک‌بار برای کل تولید` / `۱۲٬۰۰۰٬۰۰۰` |
| row 4 | `طراحی جلد` / `یک‌بار برای کل تولید` / `۴٬۰۰۰٬۰۰۰` |
| footer line 1 | `هزینه کل` / `۵۶٬۰۰۰٬۰۰۰` |
| footer line 2 | `بهای هر عدد` / `۱٬۱۲۰٬۰۰۰` |
| footer line 3 | `میانگین بها` / `۱٬۳۸۰٬۰۰۰ ← ۱٬۱۷۶٬۸۷۵` |
| submit | `ثبت تولید ۵۰ عدد` (disabled) |

Mobile empty state (`[[MSTATES:factory|…]]`, `padding:48px 20px`, `btn-lg` CTA):

```
title: هنوز تولیدی ثبت نشده
body:  ابتدا دستور تولید یک محصول را بسازید.
cta:   ساخت دستور تولید
```

Mobile error title: `اطلاعات تولید بارگذاری نشد`. Mobile loading: 5 skeletons, 84 high.

---

## 3. Interactive states designed

| element | states |
|---|---|
| Tab strip | 3 tabs, one `on` (red underline); `سوابق تولید` carries a count pill that flips to `--red-soft` when active |
| محصول select (run tab) | closed, static — **no picker popover designed** |
| Quantity stepper | default; `is-error` (red border + red ring) whenever the shortage list is non-empty; `−` clamps at 1; `+` unbounded; typing goes through `Math.max(1, num(v))` |
| تاریخ تولید select | closed, static (no calendar popover on this screen) |
| یادداشت input | default, focus |
| «ویرایش دستور» link | switches `view` to `recipe` |
| Material preview row | normal; short row tinted `--loss-soft` with `.neg.b` «کمبود N»; service row shows `خدماتی` / `—` and never goes short |
| Mode indicator (preview) | `.chip` per-unit · `badge st-refund` per-batch |
| **Shortage alert** | hidden / shown (`role="alert"`); carries two actions — «ثبت خرید مواد» (navigates away) and «تولید ۳۸ عدد» (rewrites the quantity to the max buildable) |
| Submit button | enabled; `disabled` while `short` is true (opacity .45, `cursor:not-allowed`) |
| Average-cost delta badge | `badge st-done` when the new average is **lower** than the old one, `badge st-warn` when it is higher or equal; sign prefixed with `+` when ≥ 0 |
| **Recipe list** | one selected row (`--red-soft`, bold), others plain; a product with no recipe shows `badge st-draft` «بدون دستور»; a purchased-only product is dimmed (`--text-3`) with the caption `خریدنی` |
| **Recipe row mode toggle** | two-way `.seg`, one `on`; clicking either side mutates the recipe in state and instantly re-derives the three summary tiles (and the run tab's preview) |
| Recipe qty input | rendered only — no `onChange` is wired (see §7) |
| Recipe row delete / add buttons | rendered only, no behaviour designed |
| «ذخیره دستور» | single enabled state (no dirty/saving/saved states) |
| History filters | closed selects only |
| Screen | ready (per tab), empty, loading, error; light + dark via `theme` |
| Mobile | ready (shortage), empty, loading, error; segment buttons and the submit button are static |

Focus ring everywhere: `box-shadow: 0 0 0 3px var(--ring)`. Shortage is signalled three ways at once — red row tint, the words «کمبود ۱۲», and the alert — never colour alone.

---

## 4. Validation

`short = shorts.length > 0` is the only blocking condition, and it is the only thing that disables the submit button.

| # | field | condition | severity | effect |
|---|---|---|---|---|
| V1 | تعداد تولید | typed value parses below 1 (or is empty / non-numeric) | silent coercion | `Math.max(1, num(v))` → the field becomes `۱`; no message |
| V2 | تعداد تولید | a fraction is typed (`۲٫۵`, `2.5`, `2/5`) | silent coercion — **no error message designed** | `num()` strips the decimal mark before parsing, so `۲٫۵` becomes **۲۵**, not 2 or 2.5 |
| V3 | material availability | any **goods** material's requirement exceeds its stock | error — blocks the run | red alert, red stepper, red rows, submit `disabled` |

### V1/V2 — the integer rule

Products are integers; only materials may be fractional. On this screen the rule is enforced by the parser, not by a validator:

```js
onQty: function (e) { self.setState({ qty: Math.max(1, num(e.target.value)) }); }
dec:   function () { self.setState({ qty: Math.max(1, q - 1) }); }
```

`num()` (helpers.js) maps Persian/Arabic digits to ASCII and then strips **every** non-`[0-9]` character — including `٫`, `.` and `/`. The consequence is documented here because it is a real trap: typing `۲٫۵` yields `۲۵`. The recipe side is the opposite: material quantities are parsed with `numQ()` (which maps `٫` and `/` to a decimal point and returns a float) and rendered with `faQ()`, which prints up to three decimals with the Persian decimal mark — `۱٫۵`, `۴۲٫۵`.

The only user-facing statement of the rule is the help line under the stepper, which also carries the ceiling:

```
عدد صحیح؛ حداکثر با موجودی فعلی مواد: ۳۸
```

There is **no** Persian error message for a fractional or out-of-range production quantity, and no upper clamp — the stepper will happily go past `maxBuildable`, which is what triggers V3.

### V3 — the material shortage rule

```js
var short = !svc && need > m.stock;
if (short) shorts.push(fa(need - m.stock) + ' ' + m.unit + ' «' + m.name + '» کم است.');
```

- Evaluated **per material row**, for goods only (`type: 'goods'`). Services (`stock: null`) are never checked and never block.
- Comparison is `need > stock`, so consuming the last unit exactly (`need === stock`) is allowed.
- Every short material contributes one sentence; the sentences are joined with a space into one alert body, followed by the fixed tail.

Exact messages — title, then body (the shortage variant at `qty: 50`):

```
کمبود مواد — تولید ممکن نیست
```
```
۱۲ عدد «صفحه خام وینیل ۱۲ اینچ» کم است. ۵ عدد «کاور چاپی وینیل» کم است. حداکثر قابل تولید با موجودی فعلی: ۳۸ عدد.
```

Per-row cell in column 5, red and bold:

```
کمبود ۱۲
```

Recovery paths offered in the alert: `ثبت خرید مواد` (link to the purchases screen) and `تولید ۳۸ عدد` (sets `qty = maxBuildable`, which clears the error). Mobile shows a shortened version: title `کمبود مواد`, body `۱۲ عدد «صفحه خام وینیل ۱۲ اینچ» کم است. حداکثر قابل تولید: ۳۸.` — it names only the first short material and offers no recovery action.

Nothing else is validated: no rule requires a product to have a recipe before it can be selected, no rule forbids a recipe with zero rows or a duplicated material, no rule validates the production date (a future date is not checked), and the recipe editor has no error states at all.

---

## 5. Logic

Canonical formulas: `../logic/formulas.md` §4 (production batch) and §3 (weighted average). This section covers what the screen adds on top of them.

### The recipe model

A recipe is a flat list of lines against one product — no nesting, no sub-assemblies, no yield/scrap factor, no labour-hours concept:

```js
var RECIPE = [
  { mid: 'm1', qty: 1, per: true },   // صفحه خام وینیل ۱۲ اینچ
  { mid: 'm2', qty: 1, per: true },   // کاور چاپی وینیل
  { mid: 'm7', qty: 1, per: false },  // مسترینگ و کات لاکر
  { mid: 'm8', qty: 1, per: false }   // طراحی جلد
];
```

Each line is `{ material, qty, per }`. `qty` is expressed in the material's own unit (`عدد`, `رول`, `کیلوگرم`, `متر`, `نوبت`) and may be fractional. The unit cost is never stored on the line — it is read live from the material, which is why a purchase changes every recipe's cost at once (same property as kit costs, `../logic/formulas.md` §5).

Materials of `type: 'service'` are legal recipe lines: they have a cost but no stock, so they add to the batch cost and are exempt from the shortage check and from `maxBuildable`.

### The per-unit vs once-per-batch toggle

`per` is the one flag that makes this screen worth its own page. It decides whether the line's quantity is multiplied by the batch size:

```js
var need = r.per ? r.qty * q : r.qty;
var cost = need * m.cost;
```

- `per: true` → «به ازای هر عدد». Requirement and cost both scale with the batch. Consumed from stock `qty × batchQty` times.
- `per: false` → «یک‌بار برای کل تولید». Requirement and cost are paid **once per run**, whatever the batch size — mastering, cover design, a setup fee.

The direct consequence is that the per-unit cost of a product is **not** a constant: fixed batch costs are amortised over the run, so bigger runs are cheaper per unit. The recipe editor states this arithmetic in the info alert («… بین ۳۰ عدد تقسیم می‌شود — یعنی ۴۰۰٬۰۰۰ تومان برای هر عدد») and proves it in the third summary tile, which prices the same recipe at two batch sizes:

```js
perSum  = Σ over per:true  lines of (qty × unitCost)     // 800,000
onceSum = Σ over per:false lines of (qty × unitCost)     // 16,000,000
u30     = perSum + onceSum / 30                          // 1,333,333
u100    = perSum + onceSum / 100                         // 960,000
```

### Batch cost and per-unit cost

```js
batchCost = Σ (need × material.unitCost)        // need already includes the per/batch rule
unitCost  = batchCost / q                       // «بهای هر عدد در این تولید»
```

The tile spells the division out in words — `هزینه کل ÷ ۳۰` — and the number is rounded only at display time (`fa()` does `Math.round`), so `40,000,000 ÷ 30` shows as `۱٬۳۳۳٬۳۳۳` while the stored batch value stays exact. Keep the money integer in Rial and never persist the rounded per-unit figure as the product's cost; derive it from the batch.

### What a production run does

The submit note states the two stock effects in one sentence («مواد کالایی از موجودی کم و ۳۰ عدد به موجودی محصول اضافه می‌شود»), and the preview table's «پس از تولید» column shows the first of them per material before it happens:

1. **Materials** — every goods line is decremented by its `need` (`stock − need`, the value in column 5). Service lines move nothing; their column 5 shows `—`. Fractional decrements are legal here.
2. **Product** — stock increases by `q`, an integer: `productStock + q` (`۱۴ + ۳۰ = ۴۴`).
3. **Product cost** — the batch is folded into the weighted average (`../logic/formulas.md` §3), *not* assigned:

```js
var afterStock = 14 + q;
var afterAvg   = (14 * 1380000 + batch) / afterStock;
var delta      = afterAvg - 1380000;
```

The tile renders `old → new` with the derivation line `(۱۴ عدد × ۱٬۳۸۰٬۰۰۰ + ۴۰٬۰۰۰٬۰۰۰) ÷ ۴۴ عدد`, and a delta badge: green `badge st-done` when the average falls, amber `badge st-warn` when it rises (`deltaCls: delta < 0 ? 'badge st-done' : 'badge st-warn'`, the `+` sign added for non-negative deltas). Past runs and past orders are never re-costed — this is the same rule as purchases.

So a product with no cost at all (`cost == null`, p7) gets a real cost the first time it is produced, which is why the products screen's missing-cost message points at «تولید/خرید» as an alternative to typing a seed value. The artboard hardcodes the current stock and average of `وینیل آلبوم اول` rather than reading them from the selected product (see §7).

### Maximum buildable quantity

```js
if (!svc && r.per) maxQ = Math.min(maxQ, Math.floor(m.stock / r.qty));
```

- Only **per-unit goods** lines constrain it: a once-per-batch line is paid once regardless, and services have no stock.
- `Math.floor` keeps the result an integer even when the recipe quantity is fractional.
- `maxQ` starts at `Infinity`, so a recipe made entirely of services (or of per-batch lines) leaves it unbounded — see §7.
- It is surfaced three times: in the stepper help line, inside the shortage alert, and as the label of the «تولید ۳۸ عدد» recovery button.

---

## 6. Sample data used

Materials come from `MATERIALS` (`../data/sample-data.md` §Materials); the product figures for `وینیل آلبوم اول` (stock 14, average 1,380,000) come from `CATALOG`. The recipe matches `../logic/formulas.md` §4.

### Recipe «وینیل آلبوم اول» — 4 lines

| ماده یا خدمت | sub-label | مقدار | نحوه محاسبه | هزینه |
|---|---|---|---|---|
| صفحه خام وینیل ۱۲ اینچ | `کالایی · ۶۲۰٬۰۰۰ تومان / عدد` | `۱` عدد | به ازای هر عدد | `۶۲۰٬۰۰۰ × تعداد` |
| کاور چاپی وینیل | `کالایی · ۱۸۰٬۰۰۰ تومان / عدد` | `۱` عدد | به ازای هر عدد | `۱۸۰٬۰۰۰ × تعداد` |
| مسترینگ و کات لاکر | `خدماتی · ۱۲٬۰۰۰٬۰۰۰ تومان / نوبت` | `۱` نوبت | یک‌بار برای کل تولید | `۱۲٬۰۰۰٬۰۰۰ یک‌بار` |
| طراحی جلد | `خدماتی · ۴٬۰۰۰٬۰۰۰ تومان / نوبت` | `۱` نوبت | یک‌بار برای کل تولید | `۴٬۰۰۰٬۰۰۰ یک‌بار` |

Summary tiles:

```
هزینه به ازای هر عدد        = 620,000 + 180,000                   = ۸۰۰٬۰۰۰ تومان
هزینه یک‌بار برای هر تولید  = 12,000,000 + 4,000,000              = ۱۶٬۰۰۰٬۰۰۰ تومان
بهای هر عدد در تولید ۳۰      = 800,000 + 16,000,000 ÷ 30 = 1,333,333 → ۱٬۳۳۳٬۳۳۳
بهای هر عدد در تولید ۱۰۰     = 800,000 + 16,000,000 ÷ 100 = 960,000  → ۹۶۰٬۰۰۰
```

The info alert's «۴۰۰٬۰۰۰ تومان برای هر عدد» is that same amortisation for the mastering line alone: 12,000,000 ÷ 30 = 400,000.

### Default run — `qty: 30` (artboard `Production.dc.html`)

| ماده | نحوه محاسبه | مقدار لازم | موجودی | پس از تولید | هزینه |
|---|---|---|---|---|---|
| صفحه خام وینیل ۱۲ اینچ | به ازای هر عدد | `۳۰ عدد` (1 × 30) | `۳۸` | `۸` (38 − 30) | 30 × 620,000 = `۱۸٬۶۰۰٬۰۰۰` |
| کاور چاپی وینیل | به ازای هر عدد | `۳۰ عدد` | `۴۵` | `۱۵` | 30 × 180,000 = `۵٬۴۰۰٬۰۰۰` |
| مسترینگ و کات لاکر | یک‌بار برای کل تولید | `۱ نوبت` | `خدماتی` | `—` | 1 × 12,000,000 = `۱۲٬۰۰۰٬۰۰۰` |
| طراحی جلد | یک‌بار برای کل تولید | `۱ نوبت` | `خدماتی` | `—` | 1 × 4,000,000 = `۴٬۰۰۰٬۰۰۰` |

```
هزینه کل این تولید = 18,600,000 + 5,400,000 + 12,000,000 + 4,000,000 = ۴۰٬۰۰۰٬۰۰۰
بهای هر عدد        = 40,000,000 ÷ 30                                 = ۱٬۳۳۳٬۳۳۳
موجودی محصول       = 14 + 30                                         = ۴۴
میانگین جدید       = (14 × 1,380,000 + 40,000,000) ÷ 44
                   = (19,320,000 + 40,000,000) ÷ 44 = 59,320,000 ÷ 44 = ۱٬۳۴۸٬۱۸۲
دلتا               = 1,348,182 − 1,380,000                           = −۳۱٬۸۱۸  (badge st-done)
حداکثر قابل تولید  = min(⌊38 ÷ 1⌋, ⌊45 ÷ 1⌋)                         = ۳۸
```

No shortage (30 ≤ 38 and 30 ≤ 45), so the alert is hidden, the stepper is neutral and the submit button reads `ثبت تولید ۳۰ عدد`.

### Shortage run — `qty: 50` (`Production-Shortage`, and the mobile artboard)

| ماده | مقدار لازم | موجودی | پس از تولید | هزینه |
|---|---|---|---|---|
| صفحه خام وینیل ۱۲ اینچ | `۵۰ عدد` | `۳۸` | `کمبود ۱۲` | 50 × 620,000 = `۳۱٬۰۰۰٬۰۰۰` |
| کاور چاپی وینیل | `۵۰ عدد` | `۴۵` | `کمبود ۵` | 50 × 180,000 = `۹٬۰۰۰٬۰۰۰` |
| مسترینگ و کات لاکر | `۱ نوبت` | `خدماتی` | `—` | `۱۲٬۰۰۰٬۰۰۰` |
| طراحی جلد | `۱ نوبت` | `خدماتی` | `—` | `۴٬۰۰۰٬۰۰۰` |

```
هزینه کل      = 31,000,000 + 9,000,000 + 12,000,000 + 4,000,000 = ۵۶٬۰۰۰٬۰۰۰
بهای هر عدد   = 56,000,000 ÷ 50                                 = ۱٬۱۲۰٬۰۰۰
میانگین جدید  = (19,320,000 + 56,000,000) ÷ (14 + 50)
              = 75,320,000 ÷ 64                                 = ۱٬۱۷۶٬۸۷۵
دلتا          = 1,176,875 − 1,380,000                           = −۲۰۳٬۱۲۵  (badge st-done)
کمبودها       = 50 − 38 = ۱۲ عدد ;  50 − 45 = ۵ عدد
حداکثر        = min(38, 45)                                     = ۳۸
```

The two fixed service costs are unchanged between the 30 and 50 runs — the whole point of the `per` flag — while the per-unit portion grows 12,000,000 + 3,600,000. Note that the preview still computes and displays a complete cost breakdown for a batch that cannot be run; only the submit button is blocked.

### Recipe product list — badge sources

`۴ ماده` / `۴ ماده` / `۳ ماده` / `۳ ماده` / `بدون دستور` / `خریدنی` for وینیل آلبوم اول, وینیل نسخه رنگی, کاست نسخه محدود, تی‌شرت لوگو مشکی (L), تی‌شرت تور سفید (M), سی‌دی آلبوم اول. Only the first recipe exists as data in the artboard; the other counts are static markup.

### History rows

The five rows match `../data/sample-data.md` §Production history exactly, and each is internally consistent: `۸٬۲۰۰٬۰۰۰ ÷ ۲۰ = ۴۱۰٬۰۰۰`, `۱۴٬۰۰۰٬۰۰۰ ÷ ۵۰ = ۲۸۰٬۰۰۰`, `۵۵٬۲۰۰٬۰۰۰ ÷ ۴۰ = ۱٬۳۸۰٬۰۰۰`, `۴۱٬۰۰۰٬۰۰۰ ÷ ۲۰ = ۲٬۰۵۰٬۰۰۰`, `۸٬۴۰۰٬۰۰۰ ÷ ۱۵ = ۵۶۰٬۰۰۰`. The کاست نسخه محدود row is the one where the run was cheaper than the running average (`۲۸۰٬۰۰۰` per unit, average after the run `۲۹۰٬۰۰۰`) — the case that justifies showing both columns.

---

## 7. Open questions for this screen

- **Is the recipe versioned?** The run preview says «دستور نسخه ۲» but the editor shows only «آخرین تغییر ۱۴۰۵/۰۴/۰۸» — there is no version number, no version history, no "restore previous version" and no indication of who changed it. The two strings contradict each other and need one model.
- **What happens to past runs when a recipe changes?** Undesigned. History stores the batch cost and the resulting averages, not the recipe that produced them, so a past run cannot be explained after an edit. Decide whether a run snapshots its recipe (and shows it in a run detail view — which also does not exist) or whether recipes are append-only versions referenced by each run.
- **Is there a create-recipe flow?** No. The empty-state CTA «ساخت دستور تولید» has no target, the list row «بدون دستور» is not a button to anything designed, «افزودن ماده یا خدمت» has no picker, and «ذخیره دستور» has no dirty / saving / saved / error feedback. Whether a recipe can be deleted, duplicated to another product, or deactivated is also open.
- **Recipe quantities are not editable in the artboard.** The `مقدار` input has no `onChange`, so the fractional-quantity capability (`numQ` / `faQ`, e.g. `۰٫۵ کیلوگرم` per unit) is designed in the data layer but unreachable in the UI, and there is no validation or error copy for `۰`, negative, blank or absurd quantities.
- **No Persian error message exists for the integer rule.** A typed fraction is silently mangled by `num()` (`۲٫۵` → `۲۵`, §4 V2) and a typed `۰` silently becomes `۱`. Decide whether to reject with a message, round, or block the decimal key — and write the copy.
- **`maxBuildable` is unbounded for service-only recipes.** `maxQ` starts at `Infinity`; with no per-unit goods line, the help text and the alert would print the literal string produced by `fa(Infinity)`. Needs a designed fallback (hide the ceiling, or say «محدودیتی ندارد»).
- **The product selector on the run tab is static, and so is the target product.** `محصول` is a non-functional `.select`, and the average-cost tile hardcodes `وینیل آلبوم اول`, `۱۴ عدد` and `۱٬۳۸۰٬۰۰۰`. There is no picker popover, no "this product has no recipe" state on the run tab, and no designed behaviour when the selected product's cost is currently `null` (the case production is supposed to fix) — does the average tile then show only the batch's own unit cost?
- **No confirmation and no success state.** Pressing «ثبت تولید ۳۰ عدد» has no confirm dialog, no success screen, no toast and no link to the created run — unlike record-sale, which has all four. Nothing tells the user the run was written.
- **Runs are irreversible and unexplained.** History has no row actions: no view, no edit, no delete, no reversal. If a run is entered wrongly, the only designed remedy is a stock adjustment on screen 10, which would not undo the effect on the weighted average.
- **The history count pill says `۱۴` while five rows render**, with no pagination, no row count, no sorting, and non-functional product / date-range filters. The date range `۱۴۰۵/۰۱/۰۱ تا ۱۴۰۵/۰۶/۳۱` also does not match a count of 14 against the 5 visible rows.
- **Nothing models an imperfect run.** There is no field for scrap or yield loss during production (e.g. 30 pressed, 28 usable), no partial-completion concept, and no link to ضایعات — so a failed batch has to be recorded twice, in two screens, with no connection between them.
- **Service availability is never checked.** A recipe can require «مسترینگ و کات لاکر» with no notion of whether the service has been ordered or paid; no wording tells the user why service lines never show a shortage.
- **Date and note are captured but weakly defined.** `تاریخ تولید` is a static select with no calendar popover (other screens have one) and no rule against future dates; the note is free text with no length limit, shown only in the history table.
- **Mobile is one static screen.** `دستور` and `سوابق` have no mobile boards, the segment does not switch, the stepper and submit button are frozen in the shortage state, and the mobile shortage alert names only the first short material and offers neither «ثبت خرید مواد» nor «تولید ۳۸ عدد».
