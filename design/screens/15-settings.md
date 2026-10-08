# 15 — تنظیمات (Settings)

Route: `/settings` · sidebar key `settings` (last item in the sidebar, gear icon) · page title in top bar: **تنظیمات**

The only screen that writes *defaults* rather than records. Nothing here changes history: every value is read by the record-sale form when a new order is started, and the caption at the top of the first card says so explicitly. Three sections exist (shipping/channels, postage estimate, store & invoice) plus a stubbed fourth («کاربران» — «به‌زودی»). The single most important thing on this screen is the postage block: it is where the one store-wide postage estimate is configured, as **total paid ÷ total orders** over the last N postage payments — not as an average of per-payment rates, and not per channel. Channels carry only an on/off switch for postage; there is no per-channel postage amount anywhere in the product.

Artboards: `Settings.dc.html` (default, `state: ready`), `Settings-Dark.dc.html` (1440 × 1200, `theme: dark`), `Settings-States.dc.html` (three 1440 × 760 boards side by side: `empty` · `loading` · `error`), `SettingsMobile.dc.html` (390 × 1100), `SettingsMobile-States.dc.html` (three 390 × 844 boards: `empty` · `loading` · `error`).
The desktop artboard is interactive: the ten channel switches and the payment-count stepper are live (`setState`), and the postage estimate recomputes from the real `PAY` array on every change. `props`: `state` (`ready | empty | loading | error`), `theme` (`light | dark`), `h` (default 1180).
There is **no** `SettingsMobile-Dark` artboard, and the mobile switches are static.

---

## 1. Layout

### Desktop (1440 × 1180, fluid 1024–1600)

```
┌ sidebar 264 (right) ┬───────────────── content 1176 ─────────────────┐
│                     │ top bar 64: «تنظیمات»                          │
│                     ├──────────────┬────────────────────────────────┤
│                     │ section nav  │ panel column (grow)            │
│                     │ 220, card    │                                │
│                     │ padding 8    │ [1] #ship  ارسال و کانال‌ها      │
│                     │              │     default-shipping field     │
│                     │ • ارسال و     │     + channel table (5 rows)   │
│                     │   کانال‌ها ◄on │                                │
│                     │ • تخمین هزینه  │ [2] #post  تخمین هزینه پست     │
│                     │   پست         │     stepper 260 | estimate box │
│                     │ • فروشگاه و   │                                │
│                     │   فاکتور      │ [3] #store فروشگاه و فاکتور     │
│                     │ • کاربران     │     2-col grid, 5 fields       │
│                     │   [به‌زودی]    │                                │
│                     │              │                                │
│                     ├──────────────┴────────────────────────────────┤
│                     │ unsaved-changes bar (absolute, bottom 20,      │
│                     │ left/right 32, dark pill, role="status")       │
└─────────────────────┴───────────────────────────────────────────────┘
```

- `main` padding `24px 32px 40px`, `display:flex; flex-direction:column; gap:20px`.
- Inside it one row: `display:flex; gap:24px; align-items:flex-start`.
- Section nav: `.card`, `width:220px; flex-shrink:0; padding:8px; display:flex; flex-direction:column; gap:2px`, `aria-label="بخش‌های تنظیمات"`. Each entry is an `<a href="#…">` 40px tall, `padding:0 12px; border-radius:8px`. The active one adds `.b` and `background: var(--red-soft)`; inactive ones are `color: var(--text)`; the stub is `color: var(--text-3)` with the chip pushed to the far end by `margin-right:auto`.
- Panel column: `.grow`, `display:flex; flex-direction:column; gap:20px`.
- The unsaved-changes bar is `position:absolute; left:32px; right:32px; bottom:20px`, `background: var(--text); color: var(--surface); border-radius:12px; padding:12px 16px; box-shadow: var(--shadow-lg)`, `role="status"`. It overlays the page rather than sitting in flow, so the last card needs bottom clearance at real content heights.

### Section and field order (exact)

**[1] `#ship` — ارسال و کانال‌ها** (`aria-labelledby="st1"`)

1. Card header: `h2.t-h2` + a caption line under it.
2. **هزینه ارسال پیش‌فرض** — `.field`, `max-width:320px`; `.ig` group = `input.input.input-num` + `.sfx` «تومان»; one help line.
3. Channel table — wrapped in `border:1px solid var(--border); border-radius:10px; overflow:hidden`, `table.tbl`, 4 columns, 5 rows in fixed order وب‌سایت · اینستاگرام · عمده‌فروشی · حضوری · سایر:
   | col | content |
   |---|---|
   | کانال | `.ch` chip (`.ch-web` / `.ch-insta` / `.ch-wholesale` / `.ch-inperson` / `.ch-other`) |
   | دریافت هزینه ارسال از مشتری | `button role="switch" aria-checked` + a caption 10px away (`margin-right:10px`) |
   | هزینه پست | same switch pattern + caption |
   | کیت بسته‌بندی پیش‌فرض | `button.select`, `width:220px; height:36px`, kit name at the start, kit cost (`.num`) at the end |

**[2] `#post` — تخمین هزینه پست** (`aria-labelledby="st2"`)

`.card-b` is `display:flex; gap:24px; align-items:flex-start`:

1. Left: `.field`, `width:260px; flex-shrink:0` — label, `.stepper` `width:140px` (**+** button · input · **−** button, in that RTL order), one help line.
2. Right: `.grow` hero box, `background: var(--navy-soft); border-radius:12px; padding:14px 16px; display:flex; flex-direction:column; gap:4px` — caption, then the estimate at `26px/700` in `--heading` with a `13px/500` unit tail, then the divisor line in `.t-cap.muted2.num`.

**[3] `#store` — فروشگاه و فاکتور** (`aria-labelledby="st3"`)

Card header carries a trailing link. `.card-b` is `display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:16px`, fields in this order:

1. **نام فروشگاه** — text input (row 1, start).
2. **وب‌سایت یا اینستاگرام (روی فاکتور)** — text input, placeholder only (row 1, end).
3. **پیشوند شماره فاکتور** — text input, `direction:ltr; text-align:right` (row 2, start).
4. **شماره فاکتور بعدی** — *not* an input: a `div.input.is-disabled` with `direction:ltr; justify-content:flex-end` holding an `.inv` span, plus a help line (row 2, end).
5. **متن پای فاکتور** — text input, `grid-column: span 2` (row 3, full width).

**[4] کاربران** — nav entry only, `href="#"`, no panel, no `#users` section.

### Mobile (390 × 1100)

`MobileBar` 56px, `main` padding `14px 16px 100px` (the 100px clears the fixed save bar), `gap:12px`. Three cards, in this order:

```
┌──────────── 390 ────────────┐
│ mobile bar 56: «تنظیمات»     │
├─────────────────────────────┤
│ ارسال                        │
│  هزینه ارسال پیش‌فرض           │
│  [ ۱۸۰٬۰۰۰        تومان ] 48 │
├─────────────────────────────┤
│ کانال‌ها                      │
│  ─────────────────────────  │
│  [chip وب‌سایت]  جعبه استاندارد│
│  (•) هزینه ارسال (•) هزینه پست│
│  ─────────────────────────  │
│  … ×5 rows                  │
├─────────────────────────────┤
│ تخمین هزینه پست               │
│  تعداد پرداخت‌های اخیر  [− ۳ +]│
│  ┌ تخمین فعلی   ۱۹۹٬۲۷۳ ت ┐ │
│  جمع پرداختی ÷ جمع سفارش‌ها…   │
├─────────────────────────────┤
│ fixed bar: [ذخیره تغییرات] 48│
└─────────────────────────────┘
```

Differences from desktop, all real:

- The section nav does not exist; the three cards are simply stacked and «کاربران» is gone.
- The shipping input is 48px tall and **has no help line**.
- Each channel row is `padding:12px 14px` with `border-top:1px solid var(--border)`: line 1 = channel chip at the start and the kit name as `.t-cap.muted` at the end; line 2 = two `<label>`s, `gap:16px`, each `min-height:36px`, each a `span.switch` + text. The kit is **read-only text on mobile** — there is no `.select` button.
- The switches are `<span class="switch">`, not `<button role="switch">`: no `aria-checked`, no `aria-label`, no handler.
- The postage card puts the stepper on one row opposite its label (`width:132px; height:44px`, 40px-wide buttons), then a `.sl` row in `--navy-soft` showing «تخمین فعلی» / value, then the divisor caption. The «عدد کمتر = …» help line is **not** on mobile.
- The whole **فروشگاه و فاکتور** section is absent on mobile, including «پیش‌نمایش فاکتور».
- The unsaved-changes pill is replaced by a permanently visible bar: `position:absolute; left:0; right:0; bottom:0; padding:12px 16px 20px; background: var(--surface); border-top:1px solid var(--border)` holding a full-width `.btn.btn-primary.btn-lg`. No change count, no «بازگردانی».

---

## 2. Copy (verbatim)

### Section nav

| entry | text | extra |
|---|---|---|
| 1 | `ارسال و کانال‌ها` | active (`--red-soft`) |
| 2 | `تخمین هزینه پست` | |
| 3 | `فروشگاه و فاکتور` | |
| 4 | `کاربران` | `.chip` reading `به‌زودی`, 20px tall, 11px |

`aria-label` on the nav: `بخش‌های تنظیمات`

### [1] ارسال و کانال‌ها

- Heading: `ارسال و کانال‌ها`
- Caption: `این مقادیر فقط پیش‌فرض فرم ثبت فروش هستند و روی سفارش‌های ثبت‌شده اثری ندارند.`
- Label: `هزینه ارسال پیش‌فرض` · value `۱۸۰٬۰۰۰` · suffix `تومان`
- Help: `برای کانال‌هایی که «هزینه ارسال» آن‌ها روشن است؛ در هر سفارش قابل تغییر است.`
- Table headers: `کانال` · `دریافت هزینه ارسال از مشتری` · `هزینه پست` · `کیت بسته‌بندی پیش‌فرض`

Channel rows as designed:

| کانال | shipping switch | shipping caption | postage switch | postage caption | kit | kit cost |
|---|---|---|---|---|---|---|
| `وب‌سایت` | on | `۱۸۰٬۰۰۰ تومان` | on | `تخمین ۱۹۹٬۲۷۳` | `جعبه استاندارد` | `۹۵٬۰۰۰` |
| `اینستاگرام` | on | `۱۸۰٬۰۰۰ تومان` | on | `تخمین ۱۹۹٬۲۷۳` | `جعبه استاندارد` | `۹۵٬۰۰۰` |
| `عمده‌فروشی` | off | `خاموش` | on | `تخمین ۱۹۹٬۲۷۳` | `جعبه استاندارد` | `۹۵٬۰۰۰` |
| `حضوری` | off | `خاموش` | off | `خاموش` | `بدون بسته‌بندی` | `۰` |
| `سایر` | off | `خاموش` | off | `خاموش` | `بدون بسته‌بندی` | `۰` |

Switch `aria-label`s are built per row: `هزینه ارسال وب‌سایت`, `هزینه پست وب‌سایت`, `هزینه ارسال اینستاگرام`, `هزینه پست اینستاگرام`, `هزینه ارسال عمده‌فروشی`, `هزینه پست عمده‌فروشی`, `هزینه ارسال حضوری`, `هزینه پست حضوری`, `هزینه ارسال سایر`, `هزینه پست سایر`.

The off caption is the bare word `خاموش` in both columns; the on caption differs by column — shipping shows an amount, postage shows `تخمین ` + the live estimate.

### [2] تخمین هزینه پست

- Heading: `تخمین هزینه پست`
- Label: `تعداد پرداخت‌های اخیر در محاسبه`
- Stepper `aria-label`s: input `تعداد پرداخت`, **+** button `افزایش`, **−** button `کاهش`
- Help: `عدد کمتر = تخمین سریع‌تر به تغییر نرخ پست واکنش نشان می‌دهد؛ عدد بیشتر = پایدارتر.`
- Hero caption: `تخمین با این تنظیم`
- Hero value at N = 3: `۱۹۹٬۲۷۳` · unit tail `تومان / سفارش`
- Divisor line at N = 3: `جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر: ۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵`
  (pattern: `جمع پرداختی ÷ جمع سفارش‌ها در ` + N + ` پرداخت اخیر: ` + sumPaid + ` ÷ ` + sumOrders)

### [3] فروشگاه و فاکتور

- Heading: `فروشگاه و فاکتور` · trailing link `پیش‌نمایش فاکتور`
- `نام فروشگاه` — value `ربل شاپ`
- `وب‌سایت یا اینستاگرام (روی فاکتور)` — empty, placeholder `[نشانی وب‌سایت فروشگاه]`
- `پیشوند شماره فاکتور` — value `INV-` (LTR)
- `شماره فاکتور بعدی` — read-only `INV-000043`; help `خودکار؛ قابل تغییر نیست تا شماره‌ها تکراری نشوند.`
- `متن پای فاکتور` — value `از خرید شما سپاسگزاریم. برای پیگیری سفارش، شماره فاکتور را همراه داشته باشید.`

### Unsaved-changes bar (desktop only)

```
۲ تغییر ذخیره‌نشده — هزینه ارسال پیش‌فرض و کیت «عمده‌فروشی»
```
Buttons, in order from the start of the row: `بازگردانی` (transparent, `border-color: rgba(255,255,255,.3)`) then `ذخیره تغییرات` (`.btn-primary.btn-sm`). Leading icon: `info` 18px.

### Mobile-only strings

- Card titles: `ارسال` · `کانال‌ها` · `تخمین هزینه پست`
- Switch labels in each channel row: `هزینه ارسال` · `هزینه پست`
- Stepper row label: `تعداد پرداخت‌های اخیر` · stepper `aria-label`s `تعداد`, `افزایش`, `کاهش` · value `۳`
- `تخمین فعلی` / `۱۹۹٬۲۷۳ تومان`
- `جمع پرداختی ÷ جمع سفارش‌ها: ۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵` (mobile drops the «در ۳ پرداخت اخیر» clause)
- Save bar: `ذخیره تغییرات`

### Empty state (`state: empty`) — generated by `[[STATES:gear|…]]`

`.empty` block, `padding:96px 24px`, `.e-art` with the gear icon at 28px:

- Title: `تنظیمات اولیه انجام نشده`
- Body: `هزینه ارسال پیش‌فرض، کیت بسته‌بندی هر کانال و اطلاعات فاکتور را تنظیم کنید تا فرم ثبت فروش درست پر شود.`
- CTA: `.btn.btn-primary` with a plus icon — `شروع راه‌اندازی`

Mobile variant (`[[MSTATES:gear|…]]`, `padding:48px 20px`, `.btn-lg`):

- Title: `تنظیمات اولیه انجام نشده`
- Body: `هزینه ارسال و کیت هر کانال را تنظیم کنید.`
- CTA: `شروع راه‌اندازی`

### Loading state (`state: loading`)

Skeletons only. `aria-busy="true"`, `aria-label="در حال بارگذاری"`; a 20 × 180 title skeleton then **8** rows of `height:40px; border-radius:10px` on desktop, **5** rows of `height:84px` on mobile. No text.

### Error state (`state: error`)

Same `.empty` shell, `.e-art` on `--loss-soft` / `--loss` with the `cloudoff` icon:

- Title: `تنظیمات بارگذاری نشد`
- Body: `اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.`
- Button: `.btn.btn-outline` with the refresh icon — `تلاش دوباره`

(Title and body are the shared `[[STATES:]]` strings; the title is the macro's last argument «تنظیمات» + « بارگذاری نشد». The body and the retry label are identical on every screen in the app.)

---

## 3. Interactive states designed

| element | states |
|---|---|
| Section nav entry | active (`.b` + `--red-soft`), inactive, disabled-looking stub («کاربران», `--text-3` + chip) — no hover/focus variant drawn |
| هزینه ارسال پیش‌فرض input | default only (no error, no warn, no disabled variant) |
| Channel shipping switch | `on` / off, `aria-checked` true/false, live toggle; caption text swaps |
| Channel postage switch | `on` / off, `aria-checked` true/false, live toggle; caption swaps between `تخمین <est>` and `خاموش` |
| Kit `.select` button | one static appearance — **no open/menu state** |
| Payment-count stepper | default; **+** clamps at 6, **−** clamps at 1; no error/warn variant |
| Estimate hero box | recomputes live from the stepper (value + divisor line both update) |
| Store/invoice text inputs | default; `شماره فاکتور بعدی` is `.is-disabled` (read-only) |
| پیش‌نمایش فاکتور link | default link (`.t-sm.b`), navigates to the invoice document |
| Unsaved-changes bar | present in the `ready` artboard only; no "clean"/hidden variant and no saving/success variant |
| Screen | `ready`, `empty`, `loading`, `error`, plus `dark` for desktop |
| Mobile switches | `on` / off **appearance only** — static spans, not interactive |
| Mobile save button | always enabled; no disabled or loading variant |

Focus ring is the global `box-shadow: 0 0 0 3px var(--ring)`; switches follow the shared `.switch` / `.switch.on` pattern with `role="switch"` + `aria-checked` (desktop). No state on this screen is conveyed by colour alone — every switch has a text caption beside it.

---

## 4. Validation

**None.** No rule, message, required marker or error style is designed anywhere on this screen, on either breakpoint. Specifically:

- `هزینه ارسال پیش‌فرض` accepts anything the number input accepts; nothing rejects empty, zero or a huge value.
- `نام فروشگاه`, `وب‌سایت یا اینستاگرام (روی فاکتور)`, `پیشوند شماره فاکتور` and `متن پای فاکتور` have no length limit, no format rule and no required check.
- `شماره فاکتور بعدی` cannot be edited, so it cannot be invalid.
- The payment-count stepper is *clamped*, not validated: `Math.min(6, n+1)` / `Math.max(1, n-1)`, so out-of-range input is impossible via the buttons and no message exists.
- `ذخیره تغییرات` is never disabled and there is no error summary.

See § 7 — the absence of validation on the invoice prefix and the default-shipping amount is an open decision, not a deliberate "no rules" design.

---

## 5. Logic

Formulas live in `../logic/formulas.md` — § 2 for the postage estimate and § 1 for where it is consumed. This section covers only what the settings screen itself owns.

### 5.1 Setting inventory

| setting | type | default in the artboard | consumed by |
|---|---|---|---|
| `هزینه ارسال پیش‌فرض` | integer Rial | `1800000` | Record sale (`02`): seeds `shippingCharge` for any channel whose shipping switch is on; the field there stays editable per order. Flows into `customerTotal` — `formulas.md` § 1 — and into the invoice's «هزینه ارسال» row (`16`). |
| per-channel `دریافت هزینه ارسال از مشتری` | boolean × 5 | web `true`, insta `true`, wholesale `false`, inperson `false`, other `false` | Record sale: `CHANNEL_DEFAULTS[ch].ship` is the default amount when on, `0` when off. Matches `../data/sample-data.md` § Channel defaults. |
| per-channel `هزینه پست` | boolean × 5 | web `true`, insta `true`, wholesale `true`, inperson `false`, other `false` | Record sale: `postage = post ? POSTAGE_EST : 0`. **Boolean only** — see 5.3. |
| per-channel `کیت بسته‌بندی پیش‌فرض` | kit reference × 5 | web/insta/wholesale = `جعبه استاندارد` (`k1`, 95,000), inperson/other = `بدون بسته‌بندی` (`k0`, 0) | Record sale: preselects the kit tile and so `kitCost` in `formulas.md` § 1; the kit's own cost is derived from materials in `formulas.md` § 5, **not** entered here. |
| `تعداد پرداخت‌های اخیر در محاسبه` (N) | integer 1–6 | `3` | The postage estimate itself (5.2), therefore every screen that shows it: record sale, order detail, postage, dashboard, reports. |
| `نام فروشگاه` | string | `ربل شاپ` | Invoice header (`16`). |
| `وب‌سایت یا اینستاگرام (روی فاکتور)` | string | empty | Invoice header line 3 **and** invoice footer line 2 (`16` prints the placeholder `[نشانی وب‌سایت یا اینستاگرام فروشگاه]` in both places). |
| `پیشوند شماره فاکتور` | string, LTR | `INV-` | Invoice number generation; visible as `INV-000038` on the printed invoice and `INV-000042` / `INV-000043` elsewhere. |
| `شماره فاکتور بعدی` | read-only string | `INV-000043` | Display only. Assigned by the backend at save time (`02` § 5 Saving); the UI must never let it be edited — help text says why. |
| `متن پای فاکتور` | string | `از خرید شما سپاسگزاریم. برای پیگیری سفارش، شماره فاکتور را همراه داشته باشید.` | Invoice footer line 1 (`16`). |

Nothing else on the screen is a setting: the kit *costs* shown in the last table column (`۹۵٬۰۰۰` / `۰`) are read-only echoes of `formulas.md` § 5, and the estimate hero is a computed readout.

### 5.2 The postage block — the real computation

The payments are a plain array of `[totalPaid, ordersShipped]` pairs, newest first. This is verbatim from `Settings.dc.html`:

```js
/* each payment: [total paid, orders shipped] — estimate = total paid ÷ total orders */
var PAY = [[3960000, 18], [3400000, 17], [3600000, 20], [3800000, 20], [3570000, 17], [3230000, 17]];
```

and the arithmetic, also verbatim:

```js
var self = this, S = this.state, n = S.n, used = PAY.slice(0, n);
var sumPaid = used.reduce(function (a, b) { return a + b[0]; }, 0),
    sumOrd  = used.reduce(function (a, b) { return a + b[1]; }, 0),
    est     = sumPaid / sumOrd;
```

with the readouts

```js
nT: fa(n), estT: fa(est), listT: fa(sumPaid) + ' ÷ ' + fa(sumOrd)
```

and the stepper

```js
incN: function () { self.setState({ n: Math.min(6, n + 1) }); },
decN: function () { self.setState({ n: Math.max(1, n - 1) }); }
```

Three things this encodes, all of them deliberate:

1. **It is a pooled ratio, not a mean of ratios.** `Σ paid ÷ Σ orders`, one division at the end. At N = 3 that is `10,960,000 ÷ 55 = 199,272.72…`, displayed as `۱۹۹٬۲۷۳` because `fa()` applies `Math.round` at render time only. The mean of the three per-payment rates (220,000 / 200,000 / 180,000) would be exactly 200,000 — a different number, and wrong. `formulas.md` § 2 states the same.
2. **The estimate is stored at full precision and rounded only for display.** Keep the unrounded value in the domain layer; every screen that prints it uses `fa()` / `faT()` from `helpers.js`.
3. **One number for the whole store.** There is no per-channel, per-kit or per-weight estimate. The postage column in the channel table stores a boolean; `postT: c[1] ? 'تخمین ' + fa(est) : 'خاموش'` merely *echoes* the store-wide `est` on rows where the boolean is on — which is why every "on" row shows the same `تخمین ۱۹۹٬۲۷۳`.

The caption «جمع پرداختی ÷ جمع سفارش‌ها» must accompany the number everywhere; see `../README.md` § Status of corrections.

### 5.3 Channel switches carry no amount

The channel state is five 4-tuples, verbatim:

```js
this.state = { n: 3, ch: {
  web:       [true,  true,  'جعبه استاندارد', 95000],
  insta:     [true,  true,  'جعبه استاندارد', 95000],
  wholesale: [false, true,  'جعبه استاندارد', 95000],
  inperson:  [false, false, 'بدون بسته‌بندی',  0],
  other:     [false, false, 'بدون بسته‌بندی',  0] } };
```

Slot 0 = shipping-charge switch, slot 1 = **postage on/off**, slot 2 = default kit name, slot 3 = that kit's cost. Slot 1 is a boolean and there is no fifth slot; **no channel anywhere in the product holds a postage amount**. The toggle handler rewrites one slot and re-renders:

```js
function tog(i) { return function () {
  var ch = Object.assign({}, S.ch); ch[k] = c.slice(); ch[k][i] = !c[i]; self.setState({ ch: ch });
}; }
```

Consequences the implementation must preserve:

- Turning a channel's postage switch **off** makes `postage = 0` for *new* orders on that channel, which raises their profit by the estimate (`formulas.md` § 1). حضوری and سایر are off by design — there is no shipment, so there is no postage.
- Turning it **on** does not let anyone choose a different amount for that channel; the only lever is N in § 5.2.
- Slot 0 (shipping) and slot 1 (postage) are independent: عمده‌فروشی is the designed case where shipping is off but postage is on — the wholesale buyer is not charged for delivery, but the store still pays the post office. The record-sale help text for that channel says exactly this: «عمده‌فروشی هزینه ارسال از مشتری نمی‌گیرد؛ هزینه پست جداگانه ثبت می‌شود.»

### 5.4 Persistence semantics

- The card caption is the contract: **defaults only**. Changing anything here must not touch a saved order. `formulas.md` § 2 is explicit that the estimate is *copied onto the order at save time* and that later changes never rewrite history; the difference surfaces later as «مغایرت هزینه پست» in the P&L (`formulas.md` § 7).
- The desktop artboard never persists: `setState` is in-memory, the dirty-state bar is hard-coded markup, and `ذخیره تغییرات` has no handler. Treat the bar as a spec for a real dirty-state affordance, not as wiring.
- Formatting on the way out uses `helpers.js`: `fa()` for money and counts, `faD()` for digit-only strings such as `INV-` codes and dates, `num()` to parse whatever the user typed (it strips Persian, Arabic-Indic and Latin digits alike and drops separators). Never parse the displayed `٬`-separated string yourself.

---

## 6. Sample data used

Postage payments, from `PAY` above and cross-checked against `../data/sample-data.md` § Postage payments:

| # | تاریخ | مبلغ پرداختی | سفارش | نرخ هر سفارش | in the N = 3 window |
|---|---|---|---|---|---|
| 1 | ۱۴۰۵/۰۶/۲۸ | 3,960,000 | 18 | 220,000 | ✓ |
| 2 | ۱۴۰۵/۰۶/۲۱ | 3,400,000 | 17 | 200,000 | ✓ |
| 3 | ۱۴۰۵/۰۶/۱۴ | 3,600,000 | 20 | 180,000 | ✓ |
| 4 | ۱۴۰۵/۰۶/۰۷ | 3,800,000 | 20 | 190,000 | |
| 5 | ۱۴۰۵/۰۵/۳۱ | 3,570,000 | 17 | 210,000 | |
| 6 | ۱۴۰۵/۰۵/۲۴ | 3,230,000 | 17 | 190,000 | |

(The dates are not shown on this screen — the postage screen `09` owns them. Settings shows only the count N and the two sums.)

**The designed value, N = 3:**

```
sumPaid = 3,960,000 + 3,400,000 + 3,600,000 = 10,960,000
sumOrd  = 18 + 17 + 20                      = 55
est     = 10,960,000 ÷ 55                   = 199,272.7272…  → displayed ۱۹۹٬۲۷۳
```

Divisor line: `جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر: ۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵`

**Every value the stepper can produce** (use these to test the whole range, and to confirm the estimate is *not* monotonic in N):

| N | sums shown in the caption | estimate shown |
|---|---|---|
| ۱ | ۳٬۹۶۰٬۰۰۰ ÷ ۱۸ | ۲۲۰٬۰۰۰ |
| ۲ | ۷٬۳۶۰٬۰۰۰ ÷ ۳۵ | ۲۱۰٬۲۸۶ |
| **۳** | **۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵** | **۱۹۹٬۲۷۳** |
| ۴ | ۱۴٬۷۶۰٬۰۰۰ ÷ ۷۵ | ۱۹۶٬۸۰۰ |
| ۵ | ۱۸٬۳۳۰٬۰۰۰ ÷ ۹۲ | ۱۹۹٬۲۳۹ |
| ۶ | ۲۱٬۵۶۰٬۰۰۰ ÷ ۱۰۹ | ۱۹۷٬۷۹۸ |

Unrounded, for assertions: 220000 · 210285.714285… · 199272.727272… · 196800 · 199239.130434… · 197798.165137…
N = 4 reproduces the month total from `../data/sample-data.md` exactly: 14,760,000 paid over 75 orders.

**Channel matrix** (identical in `Settings` and `SettingsMobile`, and identical to `CHANNEL_DEFAULTS` in `02`):

| کانال | ship switch | ship default | postage switch | postage applied | kit | kit cost |
|---|---|---|---|---|---|---|
| وب‌سایت | on | 180,000 | on | 199,273 | جعبه استاندارد | 95,000 |
| اینستاگرام | on | 180,000 | on | 199,273 | جعبه استاندارد | 95,000 |
| عمده‌فروشی | off | 0 | on | 199,273 | جعبه استاندارد | 95,000 |
| حضوری | off | 0 | off | 0 | بدون بسته‌بندی | 0 |
| سایر | off | 0 | off | 0 | بدون بسته‌بندی | 0 |

**Store & invoice values** — `ربل شاپ` · website empty (placeholder `[نشانی وب‌سایت فروشگاه]`) · prefix `INV-` · next number `INV-000043` (the last saved order is `INV-000042` from `02`'s success state; the newest listed order is `INV-000041`) · footer text as quoted in § 2, which is the exact string printed in `16`'s footer.

**Dirty-state bar** claims 2 unsaved changes: the default shipping amount and عمده‌فروشی's kit. Those two edits are *not* reflected in the rendered values above — the bar is static copy, so the table still shows 180,000 and جعبه استاندارد.

Worked check that the settings feed the rest of the app: with web's three settings (`ship 180,000`, `post on → 199,273`, `kit جعبه استاندارد → 95,000`) plus a manual fee of 30,000, `02`'s default form yields `3,130,000 − 1,570,000 − 95,000 − 199,273 − 30,000 = 1,235,727`, i.e. `formulas.md` § 1's worked example. Flip web's postage switch off and the same order's profit becomes `1,435,000`.

---

## 7. Open questions for this screen

- **The kit dropdown does not exist.** `کیت بسته‌بندی پیش‌فرض` is a `button.select` (220 × 36) with no `onClick`, no popover, no option list and no keyboard behaviour. Which kits are offered, whether «بدون بسته‌بندی» is always available, and whether a kit with 0 buildable units (`formulas.md` § 5 — جعبه استاندارد is limited to 7) may still be chosen as a default are all undecided.
- **One global shipping amount vs. five.** The screen has a single `هزینه ارسال پیش‌فرض` field but a per-channel on/off switch, and the per-row caption is the hard-coded literal `'۱۸۰٬۰۰۰ تومان'` — it does not read the field. Meanwhile `02`'s `CHANNEL_DEFAULTS` stores an amount per channel. Decide whether each channel gets its own editable amount (and then what the single field means) or whether one amount is shared and the switch just gates it.
- **No validation at all** (§ 4). Needed decisions: minimum/maximum for the default shipping amount; whether it may be 0 while the switch is on; allowed characters and required trailing separator for `پیشوند شماره فاکتور`; max length for `متن پای فاکتور` (it must fit the invoice footer's `max-width:420px` at 12.5px — see `16` § 1); whether `نام فروشگاه` is required.
- **N's real upper bound.** The stepper clamps to 1–6 only because the sample array has six payments. Whether the ceiling is "all recorded payments", a fixed number, or a time window («آخرین ۳۰ روز») is not decided, and nothing is designed for a store with fewer than N payments recorded — or with none at all, where the estimate is `0 ÷ 0`.
- **Changing N is not explained as a forward-only change.** `formulas.md` § 2 says the estimate is copied onto each order at save time and past orders are never rewritten, but no copy on this screen says so, and there is no confirmation step. `../data/sample-data.md` shows the pending payment would move the estimate to 217,455 (+18,182), so the change is material. Decide whether saving a new N needs a warning, and whether the screen should show the previous estimate for comparison.
- **The unsaved-changes bar is unspecified beyond one example.** `۲ تغییر ذخیره‌نشده — هزینه ارسال پیش‌فرض و کیت «عمده‌فروشی»` is hard-coded. Undesigned: the singular form, the list separator and truncation rule for 3+ changes, whether `بازگردانی` confirms before discarding, the saving/spinner state, and what appears after a successful save (no toast or success state exists on this screen, unlike `02`).
- **Mobile is a strict subset and it is not confirmed that this is intentional.** Mobile has no `فروشگاه و فاکتور` section (so store name, website, prefix, next number and footer text are desktop-only), no kit selector (kit is read-only text), no section nav, no dirty-state indicator, and its switches are static `<span>`s with no `role`/`aria-checked`. Either mobile is read-mostly by design — in which case the always-enabled `ذخیره تغییرات` button is wrong — or these are gaps to fill.
- **No `SettingsMobile-Dark` artboard.** Dark mode was only verified for desktop settings; the mobile card/switch/`--navy-soft` combination is untested in dark.
- **The «کاربران» section is a stub.** `به‌زودی`, `href="#"`, no panel. No roles, permissions, invitations or user list are designed anywhere in the product, and nothing says whether the app is single-user for v1.
- **The empty-state CTA has no destination.** `شروع راه‌اندازی` implies a setup wizard; none is designed. Also undefined: what makes the screen "empty" (which settings must be missing) and whether the app is usable at all before setup.
- **Settings that the rest of the app needs and this screen does not have:** a default `کارمزد تراکنش` (entered by hand on every sale — see `02` § 7), any tax/VAT line for the invoice (`16` § 7), a seller tax/registration identifier for the invoice, a currency or unit setting (Toman is hard-coded), and a light/dark preference (theme is a prop on the shell, not a stored setting).
- **Section nav behaviour.** The entries are `#`-anchors with a hard-coded active item; whether the active state follows scroll position, and whether the panels should instead be tabs, is not specified. The nav also has no designed hover or focus appearance.
