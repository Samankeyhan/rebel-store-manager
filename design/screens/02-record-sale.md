# 02 — ثبت فروش (Record sale)

Route: `/sale` · sidebar key `sale` · page title in top bar: **ثبت فروش**

The most complex screen in the app. It is a single form with a sticky summary that is split in two: what the customer pays, and the internal cost/profit that must never be shown to a customer. Four of the six agreed corrections live here.

Artboards: `RecordSale.dc.html` (default), `RecordSale-Validation`, `RecordSale-DraftStock`, `RecordSale-Picker`, `RecordSale-Success`, `RecordSale-Loading`, `RecordSale-Error`, `RecordSale-Empty`, `RecordSale-Dark`, and `RecordSaleMobile{,-Sheet,-Success,-Loading,-Error,-Empty}`.
The desktop artboard is fully interactive: its `preset` prop (`default | errors | draft | picker | success | loading | error | empty`) switches every state, and all the logic below is executable JS in that file's `<script>`.

---

## 1. Layout

### Desktop (1440 × ~1640, fluid 1024–1600)

```
┌ sidebar 264 (right) ┬───────────────── content 1176 ─────────────────┐
│                     │ top bar 64: «ثبت فروش»                        │
│                     ├───────────────────────────┬───────────────────┤
│                     │ form column (grow)        │ summary 384       │
│                     │                           │ position: sticky  │
│                     │ [0] blocking/soft banners │ top: 24           │
│                     │ [1] کانال فروش و مشتری     │                   │
│                     │ [2] اقلام سفارش            │  پرداختی مشتری     │
│                     │ [3] ارسال و بسته‌بندی       │  ──── dashed ──── │
│                     │ [4a] هزینه‌های داخلی  [4b] وضعیت سفارش │  داخلی │
│                     │      (2-col grid, gap 20) │  [error list]     │
│                     │                           │  [ثبت فروش]        │
└─────────────────────┴───────────────────────────┴───────────────────┘
```

- `main` padding `24px 32px 40px`, `display:flex; gap:24px; align-items:flex-start`.
- Form column: `flex-grow:1; min-width:0; gap:20px`.
- Summary: `width:384px; flex-shrink:0; position:sticky; top:24px; gap:12px`.
- Cards 4a/4b sit in `grid-template-columns: repeat(2, minmax(0,1fr)); gap:20px`.

### Field order (exact)

1. **کانال فروش** — radio group, 5 tiles, `grid-template-columns: repeat(5, minmax(0,1fr)); gap:10px`.
2. Help paragraph under the tiles.
3. **نام مشتری** — text input, `max-width:360px`, optional.
4. **اقلام سفارش** — header row + one block per line + footer row.
   Line grid: `minmax(0,1fr) 104px 144px 110px 36px; gap:12px` → product select · quantity stepper · unit price · row total · delete.
   Per-line optional sub-block: discount amount (170px) · discount reason (grow) · «حذف تخفیف».
5. **هزینه ارسال دریافتی از مشتری** — number input + `تومان` suffix, `max-width:320px`.
6. **کیت بسته‌بندی** — radio group, 4 tiles, `repeat(4, minmax(0,1fr))`.
7. **هزینه پست (تخمینی)** — read-only display box (dashed border), not an input.
8. **کارمزد تراکنش** — number input + suffix.
9. **وضعیت سفارش** — segmented control, 4 options, full width.
10. Two help paragraphs under the status control.

### Mobile (390 × ~1920)

Single column, `padding: 16px 16px 150px` (bottom padding clears the sticky sheet). Card order is the same, except:

- Channel tiles become `repeat(3, minmax(0,1fr))` (5 tiles wrap 3+2), icon above label, `min-height:64px`.
- The per-channel "ارسال … · با هزینه پست · جعبه استاندارد" summary replaces the three lines of tile sub-text: `وب‌سایت: ارسال ۱۸۰٬۰۰۰ · با هزینه پست · جعبه استاندارد`.
- Each order line is a stacked block: product select (48px) + delete button (44×44) on row 1, then `grid 120px 1fr` with the stepper (44px) and the price input.
- کیت بسته‌بندی becomes `repeat(2, minmax(0,1fr))`.
- هزینه‌های داخلی is one card with `background: var(--surface-2)` and a 2-column grid; it carries the note `مبالغ به تومان · به مشتری نمایش داده نمی‌شود.`
- Status segmented control becomes a 2×2 grid, each 40px.
- All touch targets ≥ 44px.

**Mobile summary = bottom sheet, two states.**
Collapsed (`.m-sheet`, always visible): grab handle, then a button showing `مبلغ قابل پرداخت` + amount on the right and `🔒 سود` + amount on the left, a chevron-up, then the full-width primary button. `aria-expanded="false"`.
Expanded (`preset: sheet`): `.overlay` + `.m-sheet` with `border-radius:18px 18px 0 0`, `role="dialog"`, title «خلاصه سفارش» and a close button; body is the same two-part summary as desktop (customer part on `--surface`, internal part on `--surface-2` with a 2px dashed top border), then the primary button.

---

## 2. Copy (verbatim)

### Channel tiles

Each tile: name, then two sub-lines.

| tile | line 1 | line 2 | line 3 |
|---|---|---|---|
| وب‌سایت | `وب‌سایت` | `ارسال ۱۸۰٬۰۰۰` | `با هزینه پست` |
| اینستاگرام | `اینستاگرام` | `ارسال ۱۸۰٬۰۰۰` | `با هزینه پست` |
| عمده‌فروشی | `عمده‌فروشی` | `بدون هزینه ارسال` | `با هزینه پست` |
| حضوری | `حضوری` | `بدون ارسال` | `بدون پست` |
| سایر | `سایر` | `مقادیر دستی` | `بدون پست` |

Icons: globe / camera / boxes / store / dots, each tinted with `--ch-web`, `--ch-insta`, `--ch-wholesale`, `--ch-inperson`, `--ch-other`.

Card header: `کانال فروش و مشتری` · caption `پیش‌فرض‌ها بر اساس کانال پر می‌شوند`

Help under tiles:

```
تغییر کانال، هزینه ارسال و بسته‌بندی را به پیش‌فرض همان کانال برمی‌گرداند و هزینه پست را روشن یا خاموش می‌کند و قیمت‌ها را خرده یا عمده می‌کند؛ قیمت‌هایی که دستی ویرایش کرده‌اید دست نمی‌خورند.
```

Customer field: label `نام مشتری` + `(اختیاری)` in `.opt`; placeholder `مثلاً: خریدار اینستاگرام`; help `روی فاکتور چاپ می‌شود.`

### Order items

- Card header: `اقلام سفارش` · caption `۲ ردیف` (`faD(lines.length) + ' ردیف'`).
- Column headers: `محصول` · `تعداد` · `قیمت واحد (تومان)` · `جمع ردیف` · (empty).
- Empty product select: `انتخاب محصول…` with help `جستجو با نام یا دسته`.
- Selected product help: `<category>` or `<category> · موجودی کم` when `stock <= min`.
- Stock pill: `ناموجود` when `stock === 0`, else `موجودی ۱۴`.
- Price note under the price input: `قیمت خرده` / `قیمت عمده`, or after manual edit `دستی · پیش‌فرض ۲٬۴۵۰٬۰۰۰`.
- Discount reveal button: `افزودن تخفیف` (tag icon). Discount block labels: `مبلغ تخفیف`, `دلیل تخفیف (اختیاری)`, placeholder `مثلاً: مشتری ثابت`, button `حذف تخفیف`.
- Footer: `افزودن ردیف` (outline, plus icon) on one side, `جمع اقلام پس از تخفیف: ۲٬۸۷۰٬۰۰۰ تومان` on the other.

**Product picker popover** (`.menu`, 440px wide, `top:44px; right:0`, `role="listbox"`):

- Search input placeholder `جستجوی نام یا دسته…`, aria-label `جستجوی محصول`.
- Column headers: `محصول` · `قیمت خرده` / `قیمت عمده` (`priceKind`) · `موجودی`.
- Row sub-label: the category, or **`بهای تمام‌شده ثبت نشده`** in `.neg.b` when `cost == null`.
- Stock cell: `ناموجود` (`.stock.out`) / `۱۴ عدد` (`.stock` or `.stock.low`).
- No result: `محصولی با «<query>» پیدا نشد.`

### Shipping & packaging

- Card header `ارسال و بسته‌بندی`.
- Label `هزینه ارسال دریافتی از مشتری`, suffix `تومان`.
- Default help per channel:
  - web `پیش‌فرض وب‌سایت؛ قابل ویرایش است.`
  - insta `پیش‌فرض اینستاگرام؛ قابل ویرایش است.`
  - wholesale `عمده‌فروشی هزینه ارسال از مشتری نمی‌گیرد؛ هزینه پست جداگانه ثبت می‌شود.`
  - inperson `فروش حضوری ارسال ندارد.`
  - other `در صورت نیاز مبلغ را وارد کنید.`
- Override help (input gets `.is-warn`): `مقدار دستی — پیش‌فرض «وب‌سایت» ۱۸۰٬۰۰۰ تومان است.` + link button `بازگردانی`.
- Packaging label `کیت بسته‌بندی` + chip `🔒 هزینه داخلی`; tiles show name, cost (`۹۵٬۰۰۰ تومان` or `بدون هزینه`), description, and the tag `پیش‌فرض` on the channel's default kit.
- Help: `با ثبت فروش، یک عدد از این کیت از موجودی بسته‌بندی کم می‌شود.`

### Internal costs

- Card header `🔒 هزینه‌های داخلی` · caption `به مشتری نمایش داده نمی‌شود`.
- `هزینه پست (تخمینی)` — read-only box showing `۱۹۹٬۲۷۳ تومان` (or `۰ تومان`) plus a badge: `روشن برای این کانال` (`badge st-paid`) / `خاموش برای این کانال` (`badge st-draft`).
- Help when postage is on:
  ```
  جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر به پست · یک تخمین برای کل فروشگاه؛ مبلغ واقعی را پس از ارسال در سفارش ثبت کنید.
  ```
  Help when off: `«حضوری» ارسال پستی ندارد؛ هزینه پست صفر است.` (channel name interpolated).
- `کارمزد تراکنش` help: `کارمزد درگاه پرداخت یا کارت‌خوان، اگر دارد.`

### Status

- Card header `وضعیت سفارش`. Options in order: `پیش‌نویس` · `در انتظار` · `پرداخت‌شده` · `تکمیل‌شده`.
  (لغوشده and مرجوعی are **not** selectable here — they only exist as actions on an existing order.)
- Per-status help (info icon):
  - draft `فقط ذخیره می‌شود؛ بعداً می‌توانید آن را به «در انتظار»، «پرداخت‌شده» یا «تکمیل‌شده» تغییر دهید.`
  - pending `کالا و بسته‌بندی کسر می‌شود؛ پس از دریافت وجه، وضعیت را «پرداخت‌شده» کنید.`
  - paid `وجه دریافت شده ولی سفارش هنوز ارسال یا تحویل نشده است.`
  - done `وجه دریافت و سفارش ارسال یا تحویل شده است.`
- Always-visible second paragraph:
  ```
  **پیش‌نویس موجودی را رزرو نمی‌کند** و در گزارش فروش و سود حساب نمی‌شود؛ سایر وضعیت‌ها کالا و بسته‌بندی را همان لحظه از موجودی کم می‌کنند.
  ```

### Summary panel

Customer part — header `🔒`-free: `👤 پرداختی مشتری` + channel badge.

| row | label |
|---|---|
| 1 | `جمع اقلام (۳ عدد)` |
| 2 | `تخفیف` |
| 3 | `هزینه ارسال` |
| — | separator |
| 4 | `مبلغ قابل پرداخت` (`.total`) + unit `تومان` |

Internal part (on `--surface-2`, separated by `border-top: 2px dashed var(--border-strong)`): header `🔒 داخلی` + caption `هرگز به مشتری نمایش داده نمی‌شود`.

| row | label |
|---|---|
| 1 | `بهای تمام‌شده کالا` |
| 2 | `بسته‌بندی · جعبه استاندارد` (kit name interpolated) |
| 3 | `پست (تخمینی)` with sub-line `جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر` |
| 4 | `کارمزد تراکنش` |
| — | separator |
| 5 | `سود این سفارش` / `زیان این سفارش` (label flips when negative), tinted background |
| 6 | `حاشیه سود` · value `۳۹٪` or `—` |
| 7 | shipping economics line (below) |

Shipping economics line (shown when `ship > 0 || postage > 0`), truck icon mirrored:

```
ارسال این سفارش: دریافتی ۱۸۰٬۰۰۰ − هزینه ۲۹۴٬۲۷۳ = −۱۱۴٬۲۷۳
```

Footer: primary button `ثبت فروش` (or `ذخیره پیش‌نویس` when status is draft) · ghost `انصراف` · hint `Ctrl Enter ثبت سریع` (kbd chip, LTR).

### Success state

Green check disc 64px, then:

- `فروش ثبت شد`
- `INV-000042` in `.inv` at 18px + status badge + channel badge
- three tiles: `مبلغ کل` · `سود` · `اقلام` (`۳ عدد`)
- stock note: `موجودی ۳ کالا و ۱ «جعبه استاندارد» کسر شد.` — or, for a draft, `پیش‌نویس ذخیره شد؛ موجودی تغییری نکرد.`
- buttons: `چاپ فاکتور (PDF)` · `مشاهده سفارش` · `ثبت فروش جدید`
- toast, bottom-left, `role="status"`: title `سفارش INV-000042 ذخیره شد`, body `موجودی و گزارش‌ها به‌روز شدند.`

### Error state

Alert (cloud-off icon): title `فهرست محصولات و کیت‌های بسته‌بندی بارگذاری نشد`, body `بدون موجودی و بهای تمام‌شده به‌روز نمی‌توان فروش را ثبت کرد. اتصال را بررسی کنید و دوباره تلاش کنید.`, code line `کد خطا: CATALOG_503` (LTR), button `تلاش دوباره`. The two cards below render at `opacity:.55` with `aria-disabled="true"`; the items card shows `محصولات در دسترس نیستند`.
Mobile variant title: `فهرست محصولات بارگذاری نشد`.

### Empty state (no products defined yet)

`برای ثبت فروش، ابتدا محصول تعریف کنید` / `هنوز هیچ محصولی ثبت نشده است. هر محصول به قیمت خرده، قیمت عمده و بهای تمام‌شده نیاز دارد تا سود هر فروش درست محاسبه شود.` / buttons `افزودن محصول` (primary) + `تعریف کیت بسته‌بندی`.
Mobile: title `ابتدا محصول تعریف کنید`, body `هر محصول به قیمت خرده، قیمت عمده و بهای تمام‌شده نیاز دارد تا سود هر فروش محاسبه شود.`

### Loading state

Skeletons only (`.sk`), `aria-busy="true"`: three form cards (76px tiles / 40px rows / 70px tiles) plus a 384px summary column. Mobile: three rounded blocks 200 / 260 / 160px.

---

## 3. Interactive states designed

| element | states |
|---|---|
| Channel tile | default, `on` (selected, brand ring), hover, focus-visible |
| Product select | default, placeholder (`.ph` text), `is-error`, open (popover) |
| Picker row | default, hover, and the "no cost" sub-label variant |
| Quantity stepper | default, `is-error` (red), `is-warn` (orange), min clamp at 1 via the − button |
| Price input | default, manual-override note |
| Discount | hidden → revealed block → `is-error` |
| Shipping input | default, `is-warn` override + `بازگردانی` |
| Kit tile | default, `on`, `پیش‌فرض` tag |
| Status segment | 4 options, one `on` |
| Save button | enabled, `disabled` (any error), label swaps for draft |
| Screen | form, success (+toast), loading, error, empty, dark |
| Mobile sheet | collapsed, expanded (+overlay) |

Focus ring is `box-shadow: 0 0 0 3px var(--ring)` on every interactive element; no state is conveyed by colour alone (every error/warning has an icon and text).

---

## 4. Validation

`blocking = status !== 'draft'` — i.e. in `در انتظار` / `پرداخت‌شده` / `تکمیل‌شده`.

### Rules

| # | condition | draft | non-draft |
|---|---|---|---|
| V1 | line has no product | error | error |
| V2 | `qty > product.stock` | soft warning | error |
| V3 | `product.cost == null` | soft warning | error |
| V4 | `discount > lineGross` (and gross > 0) | error | error |
| V5 | no lines at all | error | error |

`saveDisabled = errors.length > 0`. Warnings never disable saving.

### Exact messages

**V1** (in the summary error list only):
```
برای ردیف ۳ محصول انتخاب نشده است.
```

**V2 — blocking**, inline under the line, red, with two link buttons `تعداد را ۳ کن` and `ذخیره به‌عنوان پیش‌نویس`:
```
موجودی کافی نیست — فقط ۳ عدد «کاست نسخه محدود» موجود است.
```
When the product is completely out of stock (`stock === 0`, so no "use max" link):
```
«کاست آلبوم اول» ناموجود است؛ برای ثبت با این وضعیت ابتدا موجودی را افزایش دهید.
```
Summary list entry: `تعداد «کاست نسخه محدود» از موجودی بیشتر است.`

**V2 — draft**, inline, orange `.warn-t`, info icon:
```
پیش‌نویس موجودی را رزرو نمی‌کند — موجودی فعلی «کاست نسخه محدود»: ۳ عدد. پیش از تغییر وضعیت، موجودی را بررسی کنید.
```
For a zero-stock product the quantity part reads `ناموجود` instead of `۰ عدد`.

**V3 — blocking.** Two places. Banner at the top of the form (`.alert-err`, lock icon):
```
title: «تی‌شرت تور سفید (M)» بهای تمام‌شده ندارد — ثبت با این وضعیت ممکن نیست
body:  تا بهای تمام‌شده این محصول مشخص نشود، سود این سفارش قابل محاسبه نیست. ابتدا در «محصولات و مواد» بهای تمام‌شده را وارد کنید (یا از تولید/خرید محاسبه شود)، سپس به همین فرم برگردید؛ اطلاعات فرم حفظ می‌شود. اگر عجله دارید، فعلاً به‌صورت پیش‌نویس ذخیره کنید.
actions: [ثبت بهای تمام‌شده ↗] (outline, links to products) + [ذخیره به‌عنوان پیش‌نویس] (ghost, sets status = draft)
```
and inline on the line (red):
```
بهای تمام‌شده این محصول ثبت نشده است؛ ثبت با وضعیت‌های در انتظار، پرداخت‌شده و تکمیل‌شده مسدود است.
```
Summary list entry: `«تی‌شرت تور سفید (M)» بهای تمام‌شده ندارد.`

**V3 — draft.** Banner (`.alert-warn`, triangle icon):
```
title: «تی‌شرت تور سفید (M)» بهای تمام‌شده ندارد — سود این سفارش نامشخص می‌ماند
body:  پیش‌نویس ذخیره می‌شود، ولی تا ثبت بهای تمام‌شده نمی‌توان سود را حساب کرد و وضعیت را از «پیش‌نویس» تغییر داد.
action: [ثبت بهای تمام‌شده ↗]
```
and inline (`.warn-t`):
```
بهای تمام‌شده این محصول ثبت نشده است؛ در پیش‌نویس اشکالی ندارد، فقط سود «نامشخص» می‌ماند.
```
With V3 active the summary shows `بهای تمام‌شده کالا` = `نامشخص`, profit = `نامشخص` on `--surface-3` with class `.nil`, margin = `—`.

**V4**, inline, red:
```
تخفیف (۳۵۰٬۰۰۰ تومان) از جمع این ردیف (۳۰۰٬۰۰۰ تومان) بیشتر است. حداکثر تخفیف ۳۰۰٬۰۰۰ تومان است.
```
Summary list entry: `تخفیف «استیکر پک» از جمع ردیف بیشتر است.`

**V5**: `حداقل یک قلم به سفارش اضافه کنید.`

### Error summary block

Above the save button, `.alert-err`, alert icon; title is the count and then one bullet per error:
```
۲ مورد مانع ثبت است
• تعداد «کاست نسخه محدود» از موجودی بیشتر است.
• «تی‌شرت تور سفید (M)» بهای تمام‌شده ندارد.
```

---

## 5. Logic

Full derivations are in `../logic/formulas.md` §1 (order profit) and §2 (postage estimate). Screen-specific behaviour:

### Channel defaults

```js
const POSTAGE_EST = 199273;            // store-wide, from the last 3 postage payments
const CHANNEL_DEFAULTS = {
  web:       { ship: 180000, post: true,  kit: 'k1' },
  insta:     { ship: 180000, post: true,  kit: 'k1' },
  wholesale: { ship: 0,      post: true,  kit: 'k1' },
  inperson:  { ship: 0,      post: false, kit: 'k0' },
  other:     { ship: 0,      post: false, kit: 'k0' },
};
```
`post` is a **boolean only** — no channel carries its own postage amount. `postage = post ? POSTAGE_EST : 0`.

**Changing the channel** (`pickCh`) resets `ship = null` and `kit = null` (so both fall back to the new channel's default) and re-prices every line **whose price has not been manually edited** (`!line.priceEdited`) to `wholesale ? product.wholesale : product.retail`. Manually edited prices are left untouched. This is exactly what the help text promises.

### Per-line

```js
lineGross = qty * unitPrice
lineNet   = lineGross - discount        // shown bold; gross shown struck-through when discount > 0
```
Stepper − clamps at 1; typing clamps at 0 (`Math.max(0, num(value))`). Quantities here are integers — fractional amounts exist only for materials, on the production/adjustment screens.

### Totals (recomputed on every keystroke — pure derivation from state, no debounce)

```js
itemsGross = Σ lineGross
discount   = Σ lineDiscount
itemsNet   = itemsGross - discount
total      = itemsNet + shipping              // what the customer pays
cost       = Σ product.cost * qty             // null-safe: costKnown = false if any cost is null
packaging  = kit.cost
postage    = channelDefaults[channel].post ? POSTAGE_EST : 0
profit     = costKnown ? total - cost - packaging - postage - fee : null
margin     = profit == null || !total ? null : round(profit / total * 100)
shipCost   = packaging + postage
shipResult = shipping - shipCost              // the "shipping economics" line; usually negative
```

`profit == null` → label `سود این سفارش`, value `نامشخص`, class `.nil`, background `--surface-3`, margin `—`.
`profit < 0` → label changes to `زیان این سفارش`, class `.neg`, background `--loss-soft`.

### Saving

- `saveDisabled = errors.length > 0`; the button is `disabled` and keeps its label.
- Saving a draft: no stock movement at all.
- Saving in any other status: decrements each product by `qty` and the selected kit by 1, immediately.
- The `ذخیره به‌عنوان پیش‌نویس` buttons inside the two blocking messages simply set `status = 'draft'`, which converts every blocking error of type V2/V3 into a warning and enables the save button. They do not save by themselves — the user still presses the primary button, whose label is now `ذخیره پیش‌نویس`.
- Invoice number is assigned by the backend on save; the success screen shows it (`INV-000042`).

---

## 6. Sample data used

Catalog subset (full list in `../data/sample-data.md`): note `p7` has `cost: null` and `p10` has `stock: 0` — they exist specifically to exercise V2/V3.

| id | name | retail | wholesale | cost | stock | min |
|---|---|---|---|---|---|---|
| p1 | وینیل آلبوم اول | 2,450,000 | 1,950,000 | 1,380,000 | 14 | 5 |
| p2 | وینیل نسخه رنگی | 3,500,000 | 2,900,000 | 2,050,000 | 2 | 3 |
| p3 | کاست نسخه محدود | 620,000 | 480,000 | 290,000 | 3 | 5 |
| p10 | کاست آلبوم اول | 450,000 | 350,000 | 190,000 | **0** | 5 |
| p4 | سی‌دی آلبوم اول | 480,000 | 380,000 | 210,000 | 22 | 5 |
| p5 | پوستر تور ۱۴۰۴ | 290,000 | 210,000 | 95,000 | 42 | 10 |
| p6 | تی‌شرت لوگو مشکی (L) | 890,000 | 690,000 | 410,000 | 7 | 5 |
| p7 | تی‌شرت تور سفید (M) | 950,000 | 740,000 | **null** | 12 | 5 |
| p8 | استیکر پک | 150,000 | 110,000 | 38,000 | 120 | 30 |
| p9 | آینه لوگو گرد | 1,250,000 | 980,000 | 560,000 | 4 | 5 |

Kits: `جعبه استاندارد` 95,000 (`تا ۳ قلم کوچک`) · `جعبه وینیل` 140,000 (`صفحه ۱۲ اینچ`) · `پاکت کوچک` 35,000 (`استیکر و کاست`) · `بدون بسته‌بندی` 0 (`تحویل دستی`).

### Preset `default` (desktop artboard)

channel web · customer `نگار ک.` · fee 30,000 · status تکمیل‌شده · lines: p1 ×1, p5 ×2 with discount 80,000 «مشتری ثابت».

```
itemsGross 3,030,000 − discount 80,000 = 2,950,000
+ shipping 180,000            → total 3,130,000
− cost 1,570,000 − packaging 95,000 − postage 199,273 − fee 30,000
= profit 1,235,727            margin 39٪
shipping economics: 180,000 − 294,273 = −114,273
```

### Preset `errors` (RecordSale-Validation)

channel insta · customer `رها س.` · fee 0 · status تکمیل‌شده · lines p3 ×5 (stock 3 → V2), p7 ×1 (no cost → V3), p8 ×2 with discount 350,000 on a 300,000 row (→ V4). Three errors; save disabled; profit `نامشخص`.

### Preset `draft` (RecordSale-DraftStock)

Same channel/customer, status پیش‌نویس, lines p10 ×1 (out of stock), p3 ×5 (over stock), p7 ×1 (no cost). All three become soft warnings, save is **enabled** with the label `ذخیره پیش‌نویس`, profit `نامشخص`.

### Mobile artboard numbers

Same two lines as `default` but shipping manually set to 150,000 (so the override warning shows) and fee 30,000:
`3,030,000 − 80,000 + 150,000 = 3,100,000`; `profit = 3,100,000 − 1,570,000 − 95,000 − 199,273 − 30,000 = 1,205,727`; shipping economics `150,000 − 294,273 = −144,273`.

---

## 7. Open questions for this screen

- The picker lists every product including inactive ones; there is no "غیرفعال" filter or badge in the picker (the products screen has one). Decide whether inactive products should be hidden here.
- There is no keyboard-only flow designed for the picker (arrow keys / type-ahead selection). `Ctrl+Enter` is advertised as "save" but no other shortcut is defined.
- Line-level quantity accepts 0 by typing; nothing validates 0 explicitly (`0 × price = 0`, so it silently contributes nothing). Decide whether 0 should be an error.
- No customer record is created — `نام مشتری` is a free-text string printed on the invoice. There is no customer list anywhere in the app.
- `کارمزد تراکنش` is entered manually every time; there is no per-channel default fee and no settings field for it.
- The form does not offer "actual postage" entry at save time; the estimate is always used and reconciled later on the postage screen. See `../open-questions.md`.
