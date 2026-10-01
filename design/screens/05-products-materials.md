# 05 — محصولات و مواد (Products & materials)

Route: `/products` · sidebar key `products` (group «انبار و عملیات») · page title in top bar: **محصولات و مواد**

The master data screen: one page with two tabs over two different tables — finished products (what you sell) and materials/services (what you consume). It is the only place where a product's **initial** cost can be typed in, which makes it the destination of the blocking "no cost" banner on the record-sale screen. Nothing is ever deleted here: products and materials are deactivated so that order history, reports and stock history stay intact. Both tables are read-only grids; every mutation happens in one of three overlays (edit product drawer, edit material drawer, deactivate confirm).

Artboards: `Products.dc.html` (default, tab محصولات), `Products-Materials` (tab مواد و خدمات, h 1240), `Products-EditProduct` (drawer over the products tab, h 1060), `Products-EditMaterial` (drawer over the materials tab, h 1240), `Products-Deactivate` (confirm dialog, h 1060), `Products-States` (empty · loading · error side by side, 3 × 1440 × 760), `ProductsMobile.dc.html` (390 × 1500), `ProductsMobile-States` (3 × 390 × 844).
The desktop artboard is interactive: props `tab` (`products | materials`), `panel` (`none | product | material | deactivate`), `state` (`ready | empty | loading | error`), `theme`, `h`. Both tables are generated from `CATALOG` and `MATERIALS` in `helpers.js`, so every cell below is derived, not typed.

---

## 1. Layout

### Desktop (1440 × 1000 default; 1240 for the materials tab, fluid 1024–1600)

```
┌──────────────── 1440 ─────────────────────────────────────────────────┐
│ ┌ content 1176 ──────────────────────────────┐ ┌ sidebar 264 (right) ┐│
│ │ top bar 64  «محصولات و مواد» + search 380  │ │ brand 72            ││
│ ├────────────────────────────────────────────┤ │ nav … products = on ││
│ │ main  padding 24 / 32 / 40 · gap 20        │ │                     ││
│ │ inner width 1112                           │ │                     ││
│ │ ┌ [0] toolbar 40 ─ flex space-between ───┐ │ │                     ││
│ │ │ search 280 · «دسته: همه» auto · switch │ │ │                     ││
│ │ │                     [+ماده] [+محصول]   │ │ │                     ││
│ │ ├ [1] tabs 40 (border-bottom 1) ─────────┤ │ │                     ││
│ │ ├ [2] 2-col grid gap 12 → 2 alerts 550 ──┤ │ │                     ││
│ │ ├ [3] card, table 1112 wide ─────────────┤ │ │                     ││
│ │ │   th 40 · td 52 · cell padding 0 16    │ │ │                     ││
│ │ │   11 product rows / 16 material rows   │ │ │                     ││
│ │ ├ [4] footnote .t-cap.muted ─────────────┤ │ │                     ││
│ └─┴────────────────────────────────────────┴─┘ └─────────────────────┘│
└───────────────────────────────────────────────────────────────────────┘
```

- `main`: `padding: 24px 32px 40px; display:flex; flex-direction:column; gap:20px` → content width **1112**.
- **Toolbar [0] is outside the `isReady` guard**: the search box, category button, «نمایش غیرفعال‌ها» switch and the two add buttons render in the empty, loading and error states too. The tabs, banners, table and footnote are all inside it.
- Toolbar left cluster (visually right, RTL): `gap:10` — `.ig` 280 wide with a 16px search prefix icon and a 40px input; `.select` with `width:auto; gap:10`; a `.t-sm` label with `.switch` (36 × 20) + text.
- Toolbar right cluster (visually left): `gap:8` — `.btn.btn-outline` «افزودن ماده», `.btn.btn-primary` «افزودن محصول», both 40 high with a 16px plus icon.
- Banners [2]: `grid-template-columns: repeat(2, minmax(0,1fr)); gap:12` → each **550** wide, `padding:10px 14px`, icon 18, grow text, trailing `btn-sm` (32 high). Only rendered on the **products** tab.
- Table: `.tbl` `width:100%`, `th` 40 high on `--surface-2`, `td` 52 high, `border-bottom:1px solid var(--border)` (removed on the last row), row hover paints `--surface-2`.

**Tab order (exact, `role="tablist"`)**

1. `محصولات` + count pill `۱۱`
2. `مواد و خدمات` + count pill `۱۶`

Active tab: `.tab.on` → heading colour + 2px `--red` bottom border; its `.cnt` pill flips to `--red-soft` / `--red`.

**Products table — column order and widths**

| # | header | width | content |
|---|---|---|---|
| 1 | `نام محصول` | auto | two lines: bold name + `.t-cap.muted` sub-line |
| 2 | `دسته` | auto | `.chip` |
| 3 | `موجودی` | auto | `.stock` / `.stock.low` / `.stock.out` pill |
| 4 | `بهای تمام‌شده (تومان)` | auto, `.n.num` | number, or the `badge st-loss` when null |
| 5 | `قیمت خرده (تومان)` | auto, `.n.num.b` | bold number |
| 6 | `قیمت عمده (تومان)` | auto, `.n.num` | number |
| 7 | `وضعیت` | auto | `badge st-done` فعال / `badge st-draft` غیرفعال |
| 8 | (empty) | **88px** | two 32 × 32 ghost icon buttons: edit, ban |

**Materials table — column order and widths**

| # | header | width | content |
|---|---|---|---|
| 1 | `نام` | auto, `.b` | bold name |
| 2 | `نوع` | auto | `badge st-paid` کالایی / `badge st-refund` خدماتی |
| 3 | `کاربرد` | auto, `.muted2` | تولید / بسته‌بندی |
| 4 | `واحد` | auto | عدد / رول / کیلوگرم / متر / نوبت |
| 5 | `موجودی` | auto | `.stock*` pill, or `.chip` «بدون موجودی» for services |
| 6 | `بهای واحد (تومان)` | auto, `.n.num` | number |
| 7 | `ارزش موجودی (تومان)` | auto, `.n.num.muted2` | stock × cost, `—` for services |
| 8 | (empty) | **56px** | one 32 × 32 ghost edit button |

**Row tinting** (both tables, applied as an inline `background`)

- product with `cost == null` → `var(--loss-soft)`
- product at/below minimum (and active) → `color-mix(in srgb, var(--warn-soft) 55%, transparent)`
- inactive product → whole row `opacity: 0.55`
- material at/below minimum (goods only) → same warm mix

### Edit-product drawer (`Products-EditProduct`, 1440 × 1060)

`.overlay` + `aside.dialog[role=dialog][aria-labelledby=pf-t]`, `position:absolute; top:0; left:0; bottom:0; width:460px; border-radius:0 14px 14px 0` — i.e. a full-height panel pinned to the **physical left** edge of the 1440 page (over the content column; the sidebar stays visible under the overlay), with its rounded corners facing inward.

Header `padding:20px 24px`, `border-bottom:1px solid var(--border)`: `h2.t-h2` + 32 × 32 close button (`aria-label="بستن"`).
Body `padding:20px 24px; gap:16`. Footer `.d-f` (`padding:16px 24px`, `--surface-2`, `border-radius:0 0 14px 0`).

**Field order (exact)**

1. `نام محصول` — text input (`#pn`), full width.
2. `دسته` — `.select` button, 40 high.
3. 2-col grid gap 12: `قیمت خرده` (`.ig` number input + `تومان` suffix) · `قیمت عمده` (same).
4. `بهای تمام‌شده اولیه` — its own block on `background: var(--loss-soft); border-radius:10px; padding:12px`; label carries a 14px lock icon; number input `.is-error` + `تومان` suffix; then an `.err` line (14px alert icon) and a `.help` line.
5. 2-col grid gap 12: `موجودی فعلی` — **read-only** `.input.is-disabled.num` box + help line · `حداقل موجودی (هشدار)` — number input (`#pm`).
6. `.switch.on` + label text (active toggle).

Footer buttons, in DOM order: `ذخیره` (primary) · `انصراف` (outline) · flexible spacer · `غیرفعال کردن` (`btn-danger-o btn-sm`, 14px ban icon) pushed to the far end.

### Edit-material drawer (`Products-EditMaterial`, 1440 × 1240)

Same geometry (460 wide, full height, left edge), `aria-labelledby="mf-t"`.

**Field order (exact)**

1. `نام` — text input (`#mn`).
2. `نوع` — `.seg` at `width:100%`, two equal buttons (`flex-grow:1`), first one `on`; then a `.help` line.
3. 2-col grid gap 12: `واحد` (`.select` + help listing the units) · `کاربرد` (`.select`).
4. 2-col grid gap 12: `بهای واحد` (`.ig` + `تومان` + help) · `حداقل موجودی (هشدار)` (`.ig` + unit suffix).
5. `.alert.alert-warn` (`padding:10px 12px`, 16px triangle icon) — the below-minimum note.
6. `.switch.on` + `فعال`.

Footer: `ذخیره` (primary) · `انصراف` (outline).

### Deactivate dialog (`Products-Deactivate`, 1440 × 1060)

`.overlay` + `div.dialog[role=alertdialog][aria-labelledby=dd-t]`, `position:absolute; top:200px; left:50%; margin-left:-260px; width:520px` → horizontally centred on the 1440 page (left edge at 460), 200 from the top.

1. `.d-h` — 40 × 40 `.d-ico.danger` with a 20px ban icon, then `h2.t-h2` + `.t-sm.muted` sub-line.
2. `.d-b` — three `.effect` rows (24 × 24 `.e-ico.e-flat` + text; icons cart, chart, package at 14px), then a `.t-cap.muted` paragraph.
3. `.d-f` — `غیرفعال کردن` (`btn-danger`) · `انصراف` (outline).

### Mobile (390 × 1500; states 390 × 844)

`MobileBar` 56 high (hamburger 44, 26px logo, title, search 44, avatar 44). `main`: `padding: 14px 16px 100px; gap:12` → content width **358**; the bottom padding clears the fixed action bar.

1. Search `.ig` — 44 high input, placeholder + search prefix icon. **Outside** the `isReady` guard.
2. `.tabs` — two `.tab`s, each `height:44px; flex-grow:1; justify-content:center`, with the same count pills.
3. `.alert.alert-err` (`padding:10px 12px`, 18px lock icon) — the missing-cost notice, one line.
4. One `.card` per product (`padding:12px 14px; gap:8`), three rows each:
   1. bold name (left/start) ↔ stock pill
   2. `.chip` category ↔ `خرده <retail> · عمده <wholesale>`
   3. cost line ↔ فعال/غیرفعال
   Card border turns `--loss-border` and the cost line `.neg.b` when the cost is null; inactive cards render at `opacity:0.55`.
5. Fixed bottom bar: `position:absolute; left:0; right:0; bottom:0; padding:12px 16px 20px`, `--surface`, 1px top border, `grid-template-columns: repeat(2, minmax(0,1fr)); gap:8` → `ماده` (outline, `btn-lg` 48) · `محصول` (primary, `btn-lg` 48).

All mobile touch targets are ≥ 44px. The materials tab, the three overlays and any row-level edit affordance are **not** designed for mobile (see §7).

---

## 2. Copy (verbatim)

### Toolbar

| element | string |
|---|---|
| search placeholder | `جستجوی نام` |
| search `aria-label` | `جستجو` |
| category button | `دسته:` + `همه` |
| inactive toggle label | `نمایش غیرفعال‌ها` |
| outline button | `افزودن ماده` |
| primary button | `افزودن محصول` |

### Tabs

| tab | label | count |
|---|---|---|
| 1 | `محصولات` | `۱۱` |
| 2 | `مواد و خدمات` | `۱۶` |

### Banners (products tab only, both hardcoded)

`.alert.alert-err`, lock icon:

```
۱ محصول بدون بهای تمام‌شده — «تی‌شرت تور سفید (M)» تا تعیین بها قابل فروش نیست.
```
trailing button: `ثبت بها` (opens the edit-product drawer).

`.alert.alert-warn`, triangle icon:

```
۴ محصول به حداقل موجودی رسیده‌اند یا ناموجودند.
```
trailing link button: `برنامه تولید` → `Production.dc.html`.

(`۱ محصول بدون بهای تمام‌شده` and `۴ محصول` are the bold `<b>` parts of those sentences.)

### Products table

Headers, in order: `نام محصول` · `دسته` · `موجودی` · `بهای تمام‌شده (تومان)` · `قیمت خرده (تومان)` · `قیمت عمده (تومان)` · `وضعیت` · (empty).

Derived cell strings:

| slot | rule | strings |
|---|---|---|
| name sub-line | `stock === 0` | `ناموجود` |
| | `stock <= min && active` | `کمتر از حداقل (۵)` — the number is `fa(p.min)` |
| | otherwise | `حداقل ۵` — the number is `fa(p.min)` |
| stock pill | `stock === 0` | `ناموجود` |
| | otherwise | `۱۴ عدد` — `fa(p.stock) + ' عدد'` |
| cost cell | `cost == null` | `بدون بهای تمام‌شده` (`badge st-loss`) |
| status | `active` | `فعال` (`badge st-done`) |
| | else | `غیرفعال` (`badge st-draft`) |
| row action `aria-label`s | | `ویرایش` · `غیرفعال کردن` |

Footnote under the table:

```
بهای تمام‌شده میانگین موزون است و از «تولید» و «خرید» به‌روز می‌شود. محصولات حذف نمی‌شوند؛ غیرفعال‌سازی سوابق فروش را حفظ می‌کند.
```

### Materials table

Headers, in order: `نام` · `نوع` · `کاربرد` · `واحد` · `موجودی` · `بهای واحد (تومان)` · `ارزش موجودی (تومان)` · (empty).

| slot | strings |
|---|---|
| type badge | `کالایی` (`badge st-paid`) · `خدماتی` (`badge st-refund`) |
| use | `تولید` · `بسته‌بندی` |
| units | `عدد` · `رول` · `کیلوگرم` · `متر` · `نوبت` |
| stock, services | `بدون موجودی` (`.chip`) |
| stock, goods | `۳۸ عدد`, `۲ رول`, `۱٫۵ کیلوگرم`, `۴۲٫۵ متر` — `faQ(stock) + ' ' + unit` |
| inventory value, services | `—` |
| row action `aria-label` | `ویرایش` |

Footnote under the table:

```
«خدماتی» (مثل مسترینگ یا چاپ سیلک) موجودی ندارد و فقط هزینه‌اش در تولید حساب می‌شود. مقدار مواد می‌تواند اعشاری باشد (۱٫۵ کیلوگرم).
```

### Edit-product drawer

| slot | string |
|---|---|
| title | `ویرایش محصول` |
| close `aria-label` | `بستن` |
| field 1 label / value | `نام محصول` / `تی‌شرت تور سفید (M)` |
| field 2 label / value | `دسته` / `تی‌شرت` |
| field 3 labels | `قیمت خرده` · `قیمت عمده`; suffix `تومان` twice; values `۹۵۰٬۰۰۰` · `۷۴۰٬۰۰۰` |
| cost label | `بهای تمام‌شده اولیه` (with lock icon) |
| cost placeholder | `مثلاً ۴۳۰٬۰۰۰` |
| cost suffix | `تومان` |
| stock label / value | `موجودی فعلی` / `۱۲ عدد` |
| min label / value | `حداقل موجودی (هشدار)` / `۵` |
| footer | `ذخیره` · `انصراف` · `غیرفعال کردن` |

Error line under the cost input (`.err`, red, alert icon):

```
این محصول بهای تمام‌شده ندارد و تا ثبت آن قابل فروش نیست.
```

Help line under it:

```
برای کالایی که قبلاً ساخته یا خریده‌اید، بهای هر عدد را وارد کنید. از این پس «تولید» و «خرید» آن را به‌صورت میانگین موزون به‌روز می‌کنند.
```

Help under `موجودی فعلی`:

```
فقط از تولید، خرید، فروش و تعدیل تغییر می‌کند.
```

Active toggle label:

```
فعال — در انتخاب محصول ثبت فروش نمایش داده می‌شود
```

### Edit-material drawer

| slot | string |
|---|---|
| title | `ویرایش ماده` |
| field 1 label / value | `نام` / `نوار چسب لوگودار` |
| type label | `نوع` |
| type segment | `کالایی — موجودی دارد` (on) · `خدماتی — بدون موجودی` |
| unit label / value | `واحد` / `رول` |
| use label / value | `کاربرد` / `بسته‌بندی` |
| cost label / value | `بهای واحد` / `۱۵۰٬۰۰۰` + `تومان` |
| min label / value | `حداقل موجودی (هشدار)` / `۵` + suffix `رول` |
| active toggle | `فعال` |
| footer | `ذخیره` · `انصراف` |

Help under the type segment:

```
خدماتی مثل مسترینگ، طراحی یا چاپ سیلک: فقط هزینه دارد و موجودی نگه داشته نمی‌شود.
```

Help under `واحد`:

```
عدد، متر، کیلوگرم، رول، لیتر، نوبت
```

Help under `بهای واحد`:

```
میانگین موزون خریدها
```

Warning alert:

```
موجودی فعلی ۲ رول — کمتر از حداقل. هر «جعبه استاندارد» ۰٫۱ رول مصرف می‌کند.
```

### Deactivate dialog

```
title:    غیرفعال کردن «پوستر تور ۱۴۰۳»؟
subtitle: محصولات حذف نمی‌شوند تا سوابق حفظ شود.
```

Three effect rows, in order:

```
از فهرست انتخاب محصول در «ثبت فروش» و «تولید» پنهان می‌شود.
سفارش‌ها، گزارش‌ها و تاریخچه موجودی آن دست‌نخورده می‌مانند.
موجودی فعلی (۶ عدد) باقی می‌ماند و در ارزش انبار حساب می‌شود.
```

Closing paragraph:

```
هر زمان با روشن کردن «نمایش غیرفعال‌ها» می‌توانید دوباره فعالش کنید.
```

Buttons: `غیرفعال کردن` (danger) · `انصراف`.

### Empty state (`[[STATES:package|…]]`)

`.card` + `.empty` (`padding:96px 24px`), 56 × 56 `.e-art` with a 28px package icon:

```
title: هنوز محصولی تعریف نشده
body:  اولین محصول را با دسته، قیمت خرده و قیمت عمده تعریف کنید. بهای تمام‌شده از تولید یا خرید محاسبه می‌شود.
cta:   افزودن اولین محصول
```

### Error state

Same shell, `.e-art` on `--loss-soft` / `--loss` with a 28px cloud-off icon:

```
title: فهرست محصولات و مواد بارگذاری نشد
body:  اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.
cta:   تلاش دوباره   (outline, refresh icon)
```

### Loading state

`section[aria-busy="true"][aria-label="در حال بارگذاری"]`, `gap:12`: one 20 × 180 skeleton bar, then **8** skeletons 40 high, `border-radius:10px`. No copy.

### Mobile-only copy

| slot | string |
|---|---|
| search placeholder / `aria-label` | `جستجوی نام` / `جستجو` |
| tabs | `محصولات` `۱۱` · `مواد و خدمات` `۱۶` |
| banner | `تی‌شرت تور سفید (M)` (bold) + ` بهای تمام‌شده ندارد و قابل فروش نیست.` |
| stock pill | `موجودی ۱۴` / `ناموجود` |
| price line | `خرده ۲٬۴۵۰٬۰۰۰ · عمده ۱٬۹۵۰٬۰۰۰` |
| cost line, known | `بهای تمام‌شده ۱٬۳۸۰٬۰۰۰ تومان` |
| cost line, null | `بدون بهای تمام‌شده — قابل فروش نیست` |
| status | `فعال` / `غیرفعال` |
| bottom bar | `ماده` · `محصول` |

Mobile empty state (`[[MSTATES:package|…]]`, `padding:48px 20px`, `btn-lg` CTA):

```
title: هنوز محصولی تعریف نشده
body:  اولین محصول را تعریف کنید.
cta:   افزودن محصول
```

Mobile error title: `محصولات بارگذاری نشد` (same body and `تلاش دوباره` button). Mobile loading: 5 skeletons, 84 high.

---

## 3. Interactive states designed

| element | states |
|---|---|
| Tab «محصولات» / «مواد و خدمات» | default, `on` (red underline + red count pill); switching re-renders the whole table region |
| Search input | default, focus (`box-shadow: 0 0 0 3px var(--ring)`); **no typed/filtered/no-result state** |
| «دسته: همه» select | closed only (no menu designed) |
| «نمایش غیرفعال‌ها» switch | rendered **off** only (`.switch` without `.on`) |
| Product row | normal, hover (`--surface-2`), warm tint (at/below min), red tint (no cost), 55 % opacity (inactive) |
| Stock pill | `.stock` (normal), `.stock.low` (warm), `.stock.out` (red «ناموجود») |
| Cost cell | number, or `badge st-loss` «بدون بهای تمام‌شده» |
| Status badge | `st-done` فعال, `st-draft` غیرفعال (dashed border) |
| Row buttons | ghost icon, hover `--surface-2`; edit opens the product drawer, ban opens the deactivate dialog |
| Material row | normal, hover, warm tint (goods at/below min); services never tint |
| Material type badge | `st-paid` کالایی, `st-refund` خدماتی |
| **Edit product drawer** | open / closed; cost input in `is-error` with `.err` line; `موجودی فعلی` in `is-disabled`; active switch `on`; footer «غیرفعال کردن» hands off to the deactivate dialog |
| **Edit material drawer** | open / closed; type segment two-way (`کالایی` on); warm `alert-warn` present when below minimum |
| **Deactivate dialog** | open / closed (`role="alertdialog"`, danger icon, two-button footer) |
| Screen | ready (per tab), empty, loading, error; light + dark via the `theme` prop |
| Mobile | ready, empty, loading, error; tabs render but do not switch |

The three overlays are mutually exclusive: `panel` is a single enum (`none | product | material | deactivate`), and every close/cancel action sets it back to `none`. `افزودن ماده` and `ویرایش` on a material row open the *same* drawer; `افزودن محصول`, `ثبت بها` and `ویرایش` on a product row open the *same* product drawer.

Focus ring everywhere: `box-shadow: 0 0 0 3px var(--ring)`. No state is colour-only — every tint is paired with text (`ناموجود`, `کمتر از حداقل (۵)`, `بدون بهای تمام‌شده`) or a badge.

---

## 4. Validation

Only **one** validation rule is designed on this screen.

| # | field | condition | severity | message |
|---|---|---|---|---|
| V1 | `بهای تمام‌شده اولیه` (edit-product drawer) | product has no cost (`cost == null`) | error — input gets `.is-error`, red ring | see below |

```
این محصول بهای تمام‌شده ندارد و تا ثبت آن قابل فروش نیست.
```

Notes the developer needs:

- The rule is the *screen-level* counterpart of record-sale V3 (`../logic/formulas.md` §1: a null cost makes profit unknown). It states the consequence — the product cannot be sold in any non-draft status — but the drawer's `ذخیره` button is **not** disabled in the artboard, so saving a product with an empty cost is still possible by design: a product with no known cost is allowed to exist.
- The banner on the list restates it at page level («۱ محصول بدون بهای تمام‌شده — …») and the `ثبت بها` button is the shortest path to this field.
- Nothing else is validated: no required-field errors for `نام محصول` / `نام`, no uniqueness check, no "retail below cost" or "wholesale above retail" warning, no numeric range checks, no unit/type consistency rules, and no error states at all in the material drawer (its `alert-warn` is informational, not a validation failure). See §7.
- `موجودی فعلی` is not a validated field at all — it is a disabled display box; stock only moves through production, purchase, sale and adjustment.

---

## 5. Logic

### Which cost is shown

Column 4 of the products table shows **one** number: the product's current weighted-average cost (`p.cost`), the same value record-sale uses for `productCost`. It is *not* a recomputed figure and not a price-based margin:

```js
noCost: p.cost == null, hasCost: p.cost != null, costT: fa(p.cost)
```

- `cost == null` → the `badge st-loss` «بدون بهای تمام‌شده» replaces the number and the row is tinted `--loss-soft`. Never render `۰` for an unknown cost.
- The number is maintained elsewhere: production and purchase update it by the weighted average in `../logic/formulas.md` §3, and production batches by §4. The footnote says exactly this («بهای تمام‌شده میانگین موزون است و از «تولید» و «خرید» به‌روز می‌شود»). Past orders and past production runs are never re-costed.
- The drawer's `بهای تمام‌شده اولیه` is the **seed** value for a product that has never been produced or purchased in the app — after the first movement, §3 owns the number.

For materials, `بهای واحد` is the same idea (weighted average of purchases — help text: «میانگین موزون خریدها»), and `ارزش موجودی` is a pure product of the two columns beside it:

```js
valueT: svc ? '—' : fa(m.stock * m.cost)
```

Material costs also feed kit costs (`../logic/formulas.md` §5) and recipe/batch costs (§4), which is why a purchase silently changes `جعبه استاندارد`'s price.

### Low-stock threshold logic

One helper, shared by every screen:

```js
function stockCls(stock, min) {
  return stock === 0 ? 'stock out' : (min && stock <= min ? 'stock low' : 'stock');
}
```

- Zero stock wins: `ناموجود`, red pill, regardless of `min`.
- Otherwise it is **at or below** minimum — `stock <= min`, inclusive — that trips the warm pill. `min` must be truthy, so `min: 0` (p11) never warns.
- The row tint uses a slightly different predicate than the pill: `low = p.stock <= p.min && p.active`, so an **inactive** product is never tinted and its pill is forced to the plain `.stock` class (`stockCls` is only called when `p.active`). p10 (stock 0, min 5) is both `ناموجود` in the pill and warm-tinted in the row, since `0 <= 5`.
- Materials: `low = !svc && m.stock <= m.min`. Services have `stock: null` and `min: null` and are exempt — they render the `.chip` «بدون موجودی» and never tint.
- The «۴ محصول به حداقل موجودی رسیده‌اند یا ناموجودند» banner matches the count of `low` product rows (p2, p3, p10, p9) but is a **hardcoded string** in the artboard, not a computed count.

### Active / inactive

```js
actT: p.active ? 'فعال' : 'غیرفعال',
actCls: p.active ? 'badge st-done' : 'badge st-draft',
op: p.active ? 1 : 0.55
```

Deactivation is the app's substitute for deletion. The dialog enumerates exactly what it does and does not do:

- **Hides** the product from the product pickers in ثبت فروش and تولید.
- **Keeps** orders, reports and stock history untouched — historical rows keep referring to it.
- **Keeps** the current stock, which still counts toward inventory value.
- Reversible: turn on «نمایش غیرفعال‌ها» to see it again (and, by implication, the drawer's `فعال` switch to restore it).

Consequence for implementation: `active` is a filter flag on pickers only; it must never be used to exclude a product from historical aggregates. Note that the list itself does **not** filter — p11 (`active: false`) is rendered even though the «نمایش غیرفعال‌ها» switch is off (see §7).

Materials have the same `فعال` switch in their drawer, but no status column and no inactive material in the sample data.

---

## 6. Sample data used

Source of truth: `../data/sample-data.md` §Products and §Materials; both tables are `.map()`ed straight from `CATALOG` and `MATERIALS` in `helpers.js`, in array order (note `p10` sits between `p3` and `p4`).

### Products tab — all 11 rows as rendered

| # | نام محصول | sub-line | دسته | موجودی | بهای تمام‌شده | خرده | عمده | وضعیت | row tint |
|---|---|---|---|---|---|---|---|---|---|
| 1 | وینیل آلبوم اول | `حداقل ۵` | وینیل | `۱۴ عدد` | `۱٬۳۸۰٬۰۰۰` | `۲٬۴۵۰٬۰۰۰` | `۱٬۹۵۰٬۰۰۰` | فعال | — |
| 2 | وینیل نسخه رنگی | `کمتر از حداقل (۳)` | وینیل | `۲ عدد` low | `۲٬۰۵۰٬۰۰۰` | `۳٬۵۰۰٬۰۰۰` | `۲٬۹۰۰٬۰۰۰` | فعال | warm |
| 3 | کاست نسخه محدود | `کمتر از حداقل (۵)` | کاست | `۳ عدد` low | `۲۹۰٬۰۰۰` | `۶۲۰٬۰۰۰` | `۴۸۰٬۰۰۰` | فعال | warm |
| 4 | کاست آلبوم اول | `ناموجود` | کاست | `ناموجود` out | `۱۹۰٬۰۰۰` | `۴۵۰٬۰۰۰` | `۳۵۰٬۰۰۰` | فعال | warm |
| 5 | سی‌دی آلبوم اول | `حداقل ۵` | آلبوم | `۲۲ عدد` | `۲۱۰٬۰۰۰` | `۴۸۰٬۰۰۰` | `۳۸۰٬۰۰۰` | فعال | — |
| 6 | پوستر تور ۱۴۰۴ | `حداقل ۱۰` | پوستر | `۴۲ عدد` | `۹۵٬۰۰۰` | `۲۹۰٬۰۰۰` | `۲۱۰٬۰۰۰` | فعال | — |
| 7 | تی‌شرت لوگو مشکی (L) | `حداقل ۵` | تی‌شرت | `۷ عدد` | `۴۱۰٬۰۰۰` | `۸۹۰٬۰۰۰` | `۶۹۰٬۰۰۰` | فعال | — |
| 8 | تی‌شرت تور سفید (M) | `حداقل ۵` | تی‌شرت | `۱۲ عدد` | **`بدون بهای تمام‌شده`** | `۹۵۰٬۰۰۰` | `۷۴۰٬۰۰۰` | فعال | red |
| 9 | استیکر پک | `حداقل ۳۰` | استیکر | `۱۲۰ عدد` | `۳۸٬۰۰۰` | `۱۵۰٬۰۰۰` | `۱۱۰٬۰۰۰` | فعال | — |
| 10 | آینه لوگو گرد | `کمتر از حداقل (۵)` | آینه | `۴ عدد` low | `۵۶۰٬۰۰۰` | `۱٬۲۵۰٬۰۰۰` | `۹۸۰٬۰۰۰` | فعال | warm |
| 11 | پوستر تور ۱۴۰۳ | `حداقل ۰` | پوستر | `۶ عدد` | `۹۰٬۰۰۰` | `۲۵۰٬۰۰۰` | `۱۸۰٬۰۰۰` | **غیرفعال** | opacity .55 |

Checks: 4 warm rows (2, 3, 4, 10) = the «۴ محصول» banner. 1 red row (8) = the «۱ محصول بدون بهای تمام‌شده» banner. Row 11 shows the `min: 0` edge case — `min && stock <= min` is false, so the sub-line falls through to `حداقل ۰` and no warning fires.

### Materials tab — all 16 rows, with `ارزش موجودی` arithmetic

| # | نام | نوع | کاربرد | واحد | موجودی | بهای واحد | ارزش موجودی = stock × cost | tint |
|---|---|---|---|---|---|---|---|---|
| 1 | صفحه خام وینیل ۱۲ اینچ | کالایی | تولید | عدد | `۳۸ عدد` | `۶۲۰٬۰۰۰` | 38 × 620,000 = `۲۳٬۵۶۰٬۰۰۰` | — |
| 2 | کاور چاپی وینیل | کالایی | تولید | عدد | `۴۵ عدد` | `۱۸۰٬۰۰۰` | 45 × 180,000 = `۸٬۱۰۰٬۰۰۰` | — |
| 3 | نوار کاست خام | کالایی | تولید | عدد | `۱۲ عدد` low | `۹۵٬۰۰۰` | 12 × 95,000 = `۱٬۱۴۰٬۰۰۰` | warm (min 20) |
| 4 | قاب و جلد کاست | کالایی | تولید | عدد | `۶۰ عدد` | `۴۵٬۰۰۰` | 60 × 45,000 = `۲٬۷۰۰٬۰۰۰` | — |
| 5 | تی‌شرت خام مشکی L | کالایی | تولید | عدد | `۶ عدد` low | `۲۶۰٬۰۰۰` | 6 × 260,000 = `۱٬۵۶۰٬۰۰۰` | warm (min 10) |
| 6 | چاپ سیلک تی‌شرت | خدماتی | تولید | عدد | `بدون موجودی` | `۱۲۰٬۰۰۰` | `—` | — |
| 7 | مسترینگ و کات لاکر | خدماتی | تولید | نوبت | `بدون موجودی` | `۱۲٬۰۰۰٬۰۰۰` | `—` | — |
| 8 | طراحی جلد | خدماتی | تولید | نوبت | `بدون موجودی` | `۴٬۰۰۰٬۰۰۰` | `—` | — |
| 9 | کارتن جعبه استاندارد | کالایی | بسته‌بندی | عدد | `۶۴ عدد` | `۶۰٬۰۰۰` | 64 × 60,000 = `۳٬۸۴۰٬۰۰۰` | — |
| 10 | جعبه وینیل | کالایی | بسته‌بندی | عدد | `۸ عدد` low | `۹۵٬۰۰۰` | 8 × 95,000 = `۷۶۰٬۰۰۰` | warm (min 20) |
| 11 | پاکت حباب‌دار کوچک | کالایی | بسته‌بندی | عدد | `۱۵ عدد` low | `۲۴٬۰۰۰` | 15 × 24,000 = `۳۶۰٬۰۰۰` | warm (min 40) |
| 12 | نوار چسب لوگودار | کالایی | بسته‌بندی | رول | `۲ رول` low | `۱۵۰٬۰۰۰` | 2 × 150,000 = `۳۰۰٬۰۰۰` | warm (min 5) |
| 13 | کاغذ پرکننده | کالایی | بسته‌بندی | کیلوگرم | `۱٫۵ کیلوگرم` low | `۹۰٬۰۰۰` | 1.5 × 90,000 = `۱۳۵٬۰۰۰` | warm (min 3) |
| 14 | برچسب آدرس | کالایی | بسته‌بندی | عدد | `۴۰۰ عدد` | `۲٬۰۰۰` | 400 × 2,000 = `۸۰۰٬۰۰۰` | — |
| 15 | محافظ گوشه | کالایی | بسته‌بندی | عدد | `۹۰ عدد` | `۱۰٬۰۰۰` | 90 × 10,000 = `۹۰۰٬۰۰۰` | — |
| 16 | کاغذ کرافت | کالایی | بسته‌بندی | متر | `۴۲٫۵ متر` | `۱۲٬۰۰۰` | 42.5 × 12,000 = `۵۱۰٬۰۰۰` | — |

Six warm rows (3, 5, 10, 11, 12, 13). Rows 13 and 16 are the fractional-quantity cases: `faQ(1.5)` → `۱٫۵` and `faQ(42.5)` → `۴۲٫۵`, using the Persian decimal mark `٫` (distinct from the thousands mark `٬`). Materials may be fractional; products may not.

For checking only — **the screen shows no totals row** — the goods rows sum to 23,560,000 + 8,100,000 + 1,140,000 + 2,700,000 + 1,560,000 + 3,840,000 + 760,000 + 360,000 + 300,000 + 135,000 + 800,000 + 900,000 + 510,000 = **44,665,000**.

### Overlay sample records

- **Edit product** is opened on `p7` — نام `تی‌شرت تور سفید (M)`, دسته `تی‌شرت`, خرده `۹۵۰٬۰۰۰`, عمده `۷۴۰٬۰۰۰`, cost **empty** with placeholder `مثلاً ۴۳۰٬۰۰۰` and the error line, موجودی فعلی `۱۲ عدد`, حداقل `۵`, active on.
- **Edit material** is opened on `m12` — نام `نوار چسب لوگودار`, نوع کالایی, واحد `رول`, کاربرد `بسته‌بندی`, بهای واحد `۱۵۰٬۰۰۰`, حداقل `۵` رول, and the warning quoting stock `۲ رول` and the kit consumption `۰٫۱ رول` per `جعبه استاندارد` (which matches `../logic/formulas.md` §5: m12 × 0.1 inside جعبه استاندارد).
- **Deactivate** is opened on `p11` — `پوستر تور ۱۴۰۳`, stock `۶ عدد`, the only inactive product in the sample set.

---

## 7. Open questions for this screen

- **Is there a create-product-from-scratch form?** Not designed. `افزودن محصول` and `افزودن ماده` open the *same* drawers as the row edit buttons, pre-filled with `p7` and `m12`; there is no empty-form variant, no «افزودن محصول» dialog title, and no decision about which fields are required on create (especially whether `بهای تمام‌شده اولیه` may be left blank at creation time).
- **Category source.** The toolbar filter shows only `دسته:` + `همه` with no menu, and the drawer's `دسته` select shows `تی‌شرت` with no options. Are categories a fixed enum, free text, or a managed list with its own screen? Nothing in the app creates one.
- **«نمایش غیرفعال‌ها» does nothing in the artboard.** The switch renders off, yet the inactive `p11` is listed anyway. Decide the default (hide inactive) and whether the count pill `۱۱` counts inactive rows.
- **Search is decorative.** No typed state, no filtered result set, and no "no results" copy on this screen (record-sale's picker has `محصولی با «…» پیدا نشد.`). Also undecided: does search cover category as well as name, as it does in the sale picker?
- **The two banners are hardcoded strings.** «۱ محصول بدون بهای تمام‌شده» and «۴ محصول …» happen to match the sample rows. Confirm they must be computed, and decide what the banners look like at counts 0 and >1 (plural naming of several products, or a count-only sentence).
- **No reactivation flow.** The deactivate dialog promises reactivation via «نمایش غیرفعال‌ها», but no reactivate confirm, button or toast is designed; the drawer's `فعال` switch is the only implied path.
- **Materials cannot be deactivated or deleted.** Their drawer has a `فعال` switch, but there is no material equivalent of the deactivate dialog, no وضعیت column in the materials table, and no rule for what an inactive material does to a recipe or a packaging kit that uses it.
- **Can an existing cost be edited?** The cost field is only ever shown in its error state, for a product with no cost. Whether the field is editable (a manual override of the weighted average) once a cost exists — and whether that should be allowed at all — is undecided; so is whether editing it retro-costs anything (per `../logic/formulas.md` §3 it should not).
- **No validation beyond the missing-cost message.** Required names, duplicate names, retail < cost, wholesale > retail, negative or zero prices, min-stock on a خدماتی material (whose `min` is null), and unit changes on a material that already has stock are all unhandled, with no Persian error copy written.
- **Table ergonomics.** No sorting, no pagination and no row-count footer are designed (11 and 16 rows fit on one screen). Both tables will need a decision at realistic catalogue sizes, as will the fixed `88px` / `56px` action columns.
- **No inventory-value total.** The materials tab shows per-row `ارزش موجودی` but no total, and there is no products-side inventory value at all, even though the deactivate dialog talks about «ارزش انبار». Where is total inventory value shown — here, on the dashboard, or only in reports?
- **Mobile is read-only and products-only.** The mobile tabs are static markup (no `مواد و خدمات` mobile board exists), the cards have no edit affordance, and none of the three overlays has a mobile (bottom-sheet) design. The two bottom buttons `ماده` / `محصول` have no target.
- **«هر «جعبه استاندارد» ۰٫۱ رول مصرف می‌کند» is hand-written.** There is no designed "used by" section listing the recipes and kits that consume a material — which is the information the user actually needs before changing its unit or deactivating it.
- **Unit list is a help string, not data:** «عدد، متر، کیلوگرم، رول، لیتر، نوبت» includes `لیتر`, which no sample material uses. Confirm the canonical unit list and whether units are free text.
