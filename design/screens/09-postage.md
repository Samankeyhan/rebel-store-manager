# 09 — هزینه‌های ارسال (Postage payments)

Route: undefined (the artboards link to `Postage.dc.html`; see §7 and `00-app-shell.md` §7) · sidebar key `postage` (icon `truck`, **mirrored** with `class="flip"`) · page title in top bar: **هزینه‌های ارسال**

This screen owns the single most-reused number in the whole product: the store-wide postage estimate, **۱۹۹٬۲۷۳ تومان / سفارش**. The shop pays the post office in lumps — one payment covers a batch of parcels — so there is no per-order postage receipt to record. Instead the shop records each lump payment (amount + how many orders it covered) and the app derives one estimate for every future order from the last N payments (N is a setting, default ۳). The estimate is computed as **Σ paid ÷ Σ orders**, never as the mean of each payment's own per-order rate; the whole screen is built to make that visible, which is why the hero card prints the arithmetic and why the on-screen caption «جمع پرداختی ÷ جمع سفارش‌ها» follows the figure on every screen that shows it. The screen has three parts: the hero estimate card (current figure + the three payments feeding it + a link to the setting), the "record a payment" form (which previews what the estimate will become before you commit), and the payment ledger with a month footer. The estimate itself is never typed by hand anywhere in the app.

Artboards: `Postage.dc.html` (light, `state: ready`, 1440 × 940), `Postage-Dark.dc.html` (`theme: dark`, 1440 × 940), `Postage-States.dc.html` (three 1440 × 760 boards side by side: `state: empty` · `loading` · `error`), `PostageMobile.dc.html` (390 × 1060), `PostageMobile-States.dc.html` (three 390 × 844 boards: `empty` · `loading` · `error`).
Source: `src/Postage.dc.html`, `src/PostageMobile.dc.html`. The desktop artboard is live: the two inputs are wired to JS state (`total`, `ord`) and the per-payment rate, the projected estimate, the delta badge and the disabled state of the save button all recompute as you type. The mobile artboard is a static frame — its `renderVals()` returns `stateVals()` only, so every value in it is a hardcoded string.

---

## 1. Layout

### Desktop (1440 × 940, fluid 1024–1600)

```
┌ sidebar 264 (RIGHT / inline-start) ┬──────────────── content 1176 ────────────────┐
│                                    │ top bar 64: «هزینه‌های ارسال»                  │
│                                    ├───────────────────────────────────────────────┤
│                                    │ main  padding 24 32 40 · column · gap 20      │
│                                    │                                               │
│  ┌── hero estimate card 1112 (background --navy-soft, border transparent) ───────┐  │
│  │ [ label + ۱۹۹٬۲۷۳ + caption + arithmetic chip ] [3 mini cards] [تغییر link ] │  │
│  │   min-width 300, gap 4          gap 28  flex-grow 1, gap 10     nowrap       │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│  ┌── row: flex, gap 24, align-items flex-start ────────────────────────────────┐   │
│  │ form card 420 (flex-shrink 0)        │ ledger card grow (668) overflow hidden│   │
│  │  «ثبت پرداخت به پست»                  │  «پرداخت‌ها به پست» + date-range select │   │
│  │  date select                          │  table: 5 columns, 6 rows, tfoot      │   │
│  │  [مبلغ کل پرداختی | تعداد سفارش]        │                                       │   │
│  │  (error row)                          │                                       │   │
│  │  per-payment rate strip (surface-2)   │                                       │   │
│  │  projection box (1px border)          │                                       │   │
│  │  help paragraph                       │                                       │   │
│  │  یادداشت input                         │                                       │   │
│  │  [ثبت پرداخت]                          │                                       │   │
│  └───────────────────────────────────────┴───────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────┘
```

- Content width `1440 − 264 = 1176`; `main` padding `24px 32px 40px` and `gap: 20px` come from the `[[PAGE:postage|هزینه‌های ارسال]]` macro (see `00-app-shell.md` §5), so the usable inner width is `1176 − 64 = 1112`.
- Hero card: `.card` with `padding: 22px 24px; display: flex; gap: 28px; align-items: center; background: var(--navy-soft); border-color: transparent`, `aria-labelledby="est"`.
- The row is `display: flex; gap: 24px; align-items: flex-start`. **The form card is the first DOM child, so in RTL it sits at the inline start — the right-hand side** — and the ledger (`.card.grow`, `overflow: hidden`) fills the remaining `1112 − 420 − 24 = 668`.
- The two amount inputs sit in `grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px`.
- Both the rate strip and the projection box are full width inside the card body (`.card-b`, `display: flex; flex-direction: column; gap: 14px`).

### Field order, desktop form (exact)

1. **تاریخ پرداخت** — a `.select` button (not an input): `cal` icon 16 + `<b class="num">۱۴۰۵/۰۶/۳۱</b>` at the inline start, and `امروز` in `.t-cap.muted` at the inline end.
2. **مبلغ کل پرداختی** — `#pt`, `.input.input-num` inside `.ig` with the `.sfx` suffix `تومان`. Wired to `onTotal` → `num()`.
3. **تعداد سفارش ارسالی** — `#po`, `.input.input-num` (gains `.is-error`) inside `.ig` with the `.sfx` suffix `سفارش`. Wired to `onOrd` → `num()`.
   Fields 2 and 3 are one 2-column grid; 2 is the first child, so it is on the right.
4. Conditional `.err` row (full width, below the grid) — only when `ordErr`.
5. **Per-payment rate strip** — `.sl` on `var(--surface-2)`, `border-radius: 10px; padding: 12px`: label `هزینه هر سفارش در این پرداخت` at the inline start, value `.v.b` at 18px at the inline end.
6. **Projection box** — `1px solid var(--border)`, radius 10, padding 12, `flex-direction: column; gap: 8px`: a `.t-cap.b.muted` heading, then a row `[old estimate 17px --text-2] [chevL 18] [new estimate 22px bold] [delta badge]`, then a `.t-cap.muted.num` line printing the arithmetic.
7. **Help paragraph** (`p.help`).
8. **یادداشت** — `#pn`, plain `.input`, label carries `(اختیاری)` in `.opt`.
9. **Primary button** `ثبت پرداخت`, `disabled="{{ordErr}}"`.

### Ledger table columns (exact order, first = rightmost in RTL)

1. `تاریخ` — `.num`, muted (`.muted2`) on rows outside the current estimate window.
2. `مبلغ پرداختی (تومان)` — `.n.num.b`.
3. `تعداد سفارش` — `.n.num`.
4. `هزینه هر سفارش (تومان)` — `.n.num`.
5. (empty header) — the `در تخمین فعلی` badge, present on the top three rows only.

`tfoot`: `جمع شهریور` · `۱۴٬۷۶۰٬۰۰۰` · `۷۵` · `۱۹۶٬۸۰۰` · `.t-cap.muted` = `جمع ÷ جمع`.

### Mobile (390 × 1060)

```
┌────────────────────── 390 ──────────────────────┐
│ mobile bar 56: «هزینه‌های ارسال»                   │
├─────────────────────────────────────────────────┤
│ main  padding 14 16 100 · column · gap 12       │
│ ┌ hero card (padding 16, --navy-soft) ────────┐ │
│ │ label / ۱۹۹٬۲۷۳ تومان (30px) / caption      │ │
│ └─────────────────────────────────────────────┘ │
│ ┌ form card (padding 14, gap 12) ─────────────┐ │
│ │ t-h3 «ثبت پرداخت به پست»                     │ │
│ │ تاریخ select 48                              │ │
│ │ مبلغ کل پرداختی input 48                      │ │
│ │ تعداد سفارش ارسالی input 48                    │ │
│ │ .sl rate strip (surface-2)                  │ │
│ │ .sl projection strip (1px border)           │ │
│ └─────────────────────────────────────────────┘ │
│ t-h3 «پرداخت‌های اخیر»                            │
│ ┌ payment card ۳٬۹۶۰٬۰۰۰ ─────────────────────┐ │
│ ┌ payment card ۳٬۴۰۰٬۰۰۰ ─────────────────────┐ │
├─────────────────────────────────────────────────┤
│ sticky footer: [ ثبت پرداخت ] full width btn-lg  │
└─────────────────────────────────────────────────┘
```

- `main` padding `14px 16px 100px`, `gap: 12px` (from `[[MPAGE:هزینه‌های ارسال]]`); inner width `390 − 32 = 358`. The 100px bottom padding clears the sticky footer.
- Sticky footer: `position: absolute; left: 0; right: 0; bottom: 0; padding: 12px 16px 20px; background: var(--surface); border-top: 1px solid var(--border)`, containing one `.btn.btn-primary.btn-lg` at `width: 100%`.
- Every mobile control is 48px tall (select and all three inputs), above the 44px minimum.
- Mobile field order is the same as desktop 1→3, then the two `.sl` strips; **the note field, the help paragraph, the conditional error row and the save button inside the card are all absent** — the save button lives in the sticky footer instead.
- The mobile hero card drops the three per-payment mini cards and the `تعداد پرداخت‌ها: ۳ · تغییر` link, and folds the arithmetic into the caption line.
- The mobile ledger is two cards, not a table: each is `padding: 12px 14px; display: flex; justify-content: space-between` with amount + `date · N سفارش` on the inline start and the per-order rate on the inline end. Only two of the six payments are shown, with no badges, no month footer and no date-range control.
- The mobile projection strip uses a literal `←` character between the two figures where desktop uses a `chevL` icon.

---

## 2. Copy (verbatim)

### Hero estimate card (desktop)

| Slot | String |
|---|---|
| label (`#est`, `.t-sm.b`, `--heading`) | `تخمین فعلی هزینه پست برای سفارش‌های جدید` |
| figure (36px/48, `.num.b`) | `۱۹۹٬۲۷۳` |
| figure unit (`.t-body`, weight 500) | `تومان / سفارش` |
| caption (`.t-sm.muted2`) | `جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر · برای وب‌سایت، اینستاگرام و عمده‌فروشی` |
| arithmetic chip (`.t-cap.num`, `--surface` on a 1px border, radius 8, padding 6 10) | `(۳٬۹۶۰٬۰۰۰ + ۳٬۴۰۰٬۰۰۰ + ۳٬۶۰۰٬۰۰۰) ÷ (۱۸ + ۱۷ + ۲۰) = ۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵` |
| link to settings (`a[href=Settings.dc.html]`, `.t-cap.b`) | `تعداد پرداخت‌ها: ۳ · تغییر` |

The three mini cards (each `.card`, `flex: 1`, `padding: 10px 12px`, three stacked lines — date `.t-cap.muted.num`, amount `.num.b`, arithmetic `.t-cap.muted.num`):

| # | date | amount | arithmetic |
|---|---|---|---|
| 1 | `۱۴۰۵/۰۶/۲۸` | `۲۲۰٬۰۰۰` | `۳٬۹۶۰٬۰۰۰ ÷ ۱۸` |
| 2 | `۱۴۰۵/۰۶/۲۱` | `۲۰۰٬۰۰۰` | `۳٬۴۰۰٬۰۰۰ ÷ ۱۷` |
| 3 | `۱۴۰۵/۰۶/۱۴` | `۱۸۰٬۰۰۰` | `۳٬۶۰۰٬۰۰۰ ÷ ۲۰` |

Note what the mini cards deliberately show: the three per-order rates are `۲۲۰٬۰۰۰`, `۲۰۰٬۰۰۰`, `۱۸۰٬۰۰۰`, whose mean is exactly `۲۰۰٬۰۰۰` — and the headline figure is `۱۹۹٬۲۷۳`, not `۲۰۰٬۰۰۰`. See §5.

### Record-payment form (desktop)

| Slot | String |
|---|---|
| card title (`#nf`, `.t-h2`) | `ثبت پرداخت به پست` |
| label 1 | `تاریخ پرداخت` |
| date value | `۱۴۰۵/۰۶/۳۱` |
| date hint (inline end of the select) | `امروز` |
| label 2 (`for="pt"`) | `مبلغ کل پرداختی` |
| suffix 2 | `تومان` |
| label 3 (`for="po"`) | `تعداد سفارش ارسالی` |
| suffix 3 | `سفارش` |
| validation error (`.err`, `alert` icon 14) | `تعداد سفارش باید دست‌کم ۱ باشد.` |
| rate strip label | `هزینه هر سفارش در این پرداخت` |
| rate strip value | `۲۳۰٬۰۰۰ تومان` |
| projection heading | `پس از ثبت، تخمین فروشگاه` |
| projection: old → new → delta | `۱۹۹٬۲۷۳` → `۲۱۷٬۴۵۵` → `+۱۸٬۱۸۲` |
| projection arithmetic (`.t-cap.muted.num`) | `(۴٬۶۰۰٬۰۰۰ + ۳٬۹۶۰٬۰۰۰ + ۳٬۴۰۰٬۰۰۰) ÷ (۲۰ + ۱۸ + ۱۷) — پرداخت ۱۴۰۵/۰۶/۱۴ از محاسبه خارج می‌شود.` |
| help paragraph | `سفارش‌های قبلی تغییر نمی‌کنند. اختلاف پرداخت واقعی با تخمین‌ها در گزارش سود و زیان به‌عنوان «مغایرت هزینه پست» می‌آید.` |
| label 4 (`for="pn"`) | `یادداشت` + `(اختیاری)` in `.opt` |
| placeholder 4 | `مثلاً: شماره رسید اداره پست` |
| primary button | `ثبت پرداخت` |

The first two figures of the projection arithmetic are interpolated (`{{totalT}}`, `{{ordT}}`) — the literal template is `({{totalT}} + ۳٬۹۶۰٬۰۰۰ + ۳٬۴۰۰٬۰۰۰) ÷ ({{ordT}} + ۱۸ + ۱۷) — پرداخت ۱۴۰۵/۰۶/۱۴ از محاسبه خارج می‌شود.`, so the trailing sentence naming the payment that drops out is **hardcoded** to `۱۴۰۵/۰۶/۱۴`.

### Ledger (desktop)

| Slot | String |
|---|---|
| card title (`#pl`, `.t-h2`) | `پرداخت‌ها به پست` |
| date-range select (`cal` 14, height 34) | `۱۴۰۵/۰۵/۰۱ تا ۱۴۰۵/۰۶/۳۱` |
| column header 1 | `تاریخ` |
| column header 2 | `مبلغ پرداختی (تومان)` |
| column header 3 | `تعداد سفارش` |
| column header 4 | `هزینه هر سفارش (تومان)` |
| column header 5 | (empty string) |
| in-window badge (`.badge.st-paid`) | `در تخمین فعلی` |
| footer label | `جمع شهریور` |
| footer note (`.t-cap.muted`) | `جمع ÷ جمع` |

Rows, verbatim:

| تاریخ | مبلغ پرداختی (تومان) | تعداد سفارش | هزینه هر سفارش (تومان) | badge |
|---|---|---|---|---|
| `۱۴۰۵/۰۶/۲۸` | `۳٬۹۶۰٬۰۰۰` | `۱۸` | `۲۲۰٬۰۰۰` | `در تخمین فعلی` |
| `۱۴۰۵/۰۶/۲۱` | `۳٬۴۰۰٬۰۰۰` | `۱۷` | `۲۰۰٬۰۰۰` | `در تخمین فعلی` |
| `۱۴۰۵/۰۶/۱۴` | `۳٬۶۰۰٬۰۰۰` | `۲۰` | `۱۸۰٬۰۰۰` | `در تخمین فعلی` |
| `۱۴۰۵/۰۶/۰۷` | `۳٬۸۰۰٬۰۰۰` | `۲۰` | `۱۹۰٬۰۰۰` | — |
| `۱۴۰۵/۰۵/۳۱` | `۳٬۵۷۰٬۰۰۰` | `۱۷` | `۲۱۰٬۰۰۰` | — |
| `۱۴۰۵/۰۵/۲۴` | `۳٬۲۳۰٬۰۰۰` | `۱۷` | `۱۹۰٬۰۰۰` | — |
| **جمع شهریور** | `۱۴٬۷۶۰٬۰۰۰` | `۷۵` | `۱۹۶٬۸۰۰` | `جمع ÷ جمع` |

### Mobile copy

| Slot | String |
|---|---|
| hero label (`.t-cap.b`) | `تخمین فعلی پست برای سفارش‌های جدید` |
| hero figure (30px/42) | `۱۹۹٬۲۷۳` |
| hero unit (`.t-sm`, weight 500) | `تومان` |
| hero caption (`.t-cap.muted2.num`) | `جمع پرداختی ÷ جمع سفارش‌ها: ۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵ در ۳ پرداخت اخیر` |
| form title (`.t-h3`) | `ثبت پرداخت به پست` |
| label 1 | `تاریخ` |
| date value | `۱۴۰۵/۰۶/۳۱` |
| label 2 | `مبلغ کل پرداختی` |
| value 2 | `۴٬۶۰۰٬۰۰۰` |
| suffix 2 | `تومان` |
| label 3 | `تعداد سفارش ارسالی` |
| value 3 | `۲۰` |
| suffix 3 | `سفارش` |
| rate strip label | `هزینه هر سفارش در این پرداخت` |
| rate strip value | `۲۳۰٬۰۰۰` |
| projection label | `تخمین پس از ثبت` |
| projection value | `۱۹۹٬۲۷۳` ` ← ` `۲۱۷٬۴۵۵` + `.badge.st-warn` `+۱۸٬۱۸۲` |
| section heading (`.t-h3`) | `پرداخت‌های اخیر` |
| payment card 1 | `۳٬۹۶۰٬۰۰۰` / `۱۴۰۵/۰۶/۲۸ · ۱۸ سفارش` / `۲۲۰٬۰۰۰ / سفارش` |
| payment card 2 | `۳٬۴۰۰٬۰۰۰` / `۱۴۰۵/۰۶/۲۱ · ۱۷ سفارش` / `۲۰۰٬۰۰۰ / سفارش` |
| sticky footer button | `ثبت پرداخت` |

Note the mobile label is `تاریخ`, not `تاریخ پرداخت`, and the mobile rate value omits `تومان` where desktop includes it.

### Empty · loading · error (the `[[STATES:…]]` / `[[MSTATES:…]]` macro)

The macro arguments **are** the copy. Desktop: `[[STATES:truck|هنوز پرداختی به پست ثبت نشده|تا ثبت اولین پرداخت، تخمین پست برای سفارش‌ها صفر است. هر بار که هزینه چند مرسوله را یک‌جا پرداخت می‌کنید، مبلغ و تعداد سفارش‌ها را این‌جا ثبت کنید.|ثبت اولین پرداخت|پرداخت‌های پست]]`. Mobile: `[[MSTATES:truck|هنوز پرداختی ثبت نشده|تا اولین پرداخت، تخمین پست صفر است.|ثبت پرداخت|پرداخت‌ها]]`.

| Board | Slot | String |
|---|---|---|
| desktop empty | art icon | `truck` at 28 (in `.e-art`) |
| desktop empty | title (`.e-t`) | `هنوز پرداختی به پست ثبت نشده` |
| desktop empty | body (`.e-d`) | `تا ثبت اولین پرداخت، تخمین پست برای سفارش‌ها صفر است. هر بار که هزینه چند مرسوله را یک‌جا پرداخت می‌کنید، مبلغ و تعداد سفارش‌ها را این‌جا ثبت کنید.` |
| desktop empty | CTA (`.btn.btn-primary`, `plus` 16) | `ثبت اولین پرداخت` |
| mobile empty | title | `هنوز پرداختی ثبت نشده` |
| mobile empty | body | `تا اولین پرداخت، تخمین پست صفر است.` |
| mobile empty | CTA (`.btn.btn-primary.btn-lg`, `plus` 16) | `ثبت پرداخت` |
| loading (both) | `aria-label` | `در حال بارگذاری` |
| desktop error | title | `پرداخت‌های پست بارگذاری نشد` |
| mobile error | title | `پرداخت‌ها بارگذاری نشد` |
| error (both) | body | `اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.` |
| error (both) | button (`.btn.btn-outline`, `refresh` 16) | `تلاش دوباره` |

Empty/error padding is `96px 24px` desktop, `48px 20px` mobile; the error art disc is recoloured `background: var(--loss-soft); color: var(--loss)` with the `cloudoff` icon at 28. The loading board is `.sk` skeletons only inside `<section aria-busy="true">`: a 20 × 180px bar then 8 × 40px rows (desktop) / 5 × 84px blocks (mobile), radius 10.

### Where this screen's number is quoted elsewhere (do not re-translate — reuse these strings)

| Screen | String |
|---|---|
| record sale, internal costs | `هزینه پست (تخمینی)` + `جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر به پست · یک تخمین برای کل فروشگاه؛ مبلغ واقعی را پس از ارسال در سفارش ثبت کنید.` |
| record sale, per-channel badge | `روشن برای این کانال` / `خاموش برای این کانال` |
| order detail | `پست` + chip `تخمینی` + `جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر`, and the action `ثبت هزینه واقعی پست` |
| dashboard | `هزینه پست (تخمینی)` + `جمع پرداختی ÷ جمع سفارش‌ها` |
| reports, P&L | `هزینه پست (تخمینی)` and `مغایرت هزینه پست` |
| reports, shipping tab | `پست واقعی / سفارش` and `مغایرت هزینه پست (پرداخت واقعی ۱۴٬۷۶۰٬۰۰۰ − تخمین‌ها ۱۴٬۳۴۷٬۶۵۶)` |
| settings | `تخمین هزینه پست` · `تعداد پرداخت‌های اخیر در محاسبه` · `عدد کمتر = تخمین سریع‌تر به تغییر نرخ پست واکنش نشان می‌دهد؛ عدد بیشتر = پایدارتر.` · `تخمین با این تنظیم` · `جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر: ۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵` |

---

## 3. Interactive states designed

| element | states |
|---|---|
| **مبلغ کل پرداختی** input | default; live — every keystroke re-derives the rate strip, the projection figure, the delta badge and the projection arithmetic line. No error state exists for this field (see §4) |
| **تعداد سفارش ارسالی** input | default; `.is-error` (red border) when the parsed value is `0`; live like the amount field |
| Validation row | hidden; visible `.err` with an `alert` icon (no artboard captures it — it appears only by typing `۰` in the live board) |
| Per-payment rate strip | value figure; `—` when the order count is invalid |
| Projection box | figure pair + delta badge `.badge.st-warn` when the estimate would **rise** (`d > 0`); `.badge.st-done` when it would fall or not move (`d ≤ 0`); when the order count is invalid the box falls back to the current estimate and a `+۰` `.badge.st-done` |
| ثبت پرداخت button | enabled; `disabled` when the order count is invalid |
| یادداشت input | default only (placeholder shown) |
| تاریخ پرداخت | a `.select` button in one resting state — **no date picker is opened by any artboard on this screen** |
| Date-range select (ledger) | one resting state, shows `۱۴۰۵/۰۵/۰۱ تا ۱۴۰۵/۰۶/۳۱`; no open popover designed |
| Ledger row | in-window (full-strength date + `در تخمین فعلی` badge) · out-of-window (`.muted2` date, no badge). No hover, no row action, no sort |
| Hero `تغییر` link | default link to `Settings.dc.html` (the `تخمین هزینه پست` card, anchor `#post`) |
| Screen | ready · empty · loading · error · dark (desktop only) |
| Mobile screen | ready · empty · loading · error — all four are static frames; no mobile control is wired |

Focus ring is `box-shadow: 0 0 0 3px var(--ring)` on inputs and buttons, per `../design-system.md` §7. The two colour-coded signals (`.is-error` border, delta badge colour) are both accompanied by text, so nothing is conveyed by colour alone.

---

## 4. Validation

There is exactly **one** rule on this screen.

| # | field | condition | effect | message |
|---|---|---|---|---|
| V1 | تعداد سفارش ارسالی | `num(value) < 1` (i.e. `0`, empty, or any text that parses to nothing) | input gets `.is-error`; the `.err` row appears; the per-payment rate shows `—`; the projection falls back to the current estimate with `+۰`; `ثبت پرداخت` is `disabled` | `تعداد سفارش باید دست‌کم ۱ باشد.` |

```js
var ok = S.ord >= 1;
// …
ordErr: !ok, ordCls: ok ? '' : 'is-error'
```
and in the markup: `<button type="button" class="btn btn-primary" disabled="{{ordErr}}">ثبت پرداخت</button>`.

Not validated anywhere, by design or by omission (see §7):

- **مبلغ کل پرداختی** has no rule at all. `num()` strips every non-digit, so a negative or fractional amount is impossible to enter, but `۰` is accepted: the form will happily record a payment of zero Toman, which drives the estimate down.
- Both numeric fields are integers by construction: `num()` (in `helpers.js`) maps Persian and Arabic-Indic digits to ASCII and then deletes everything else, so `parseInt` never sees a separator or a sign. The displayed values are re-formatted with `fa()`, which re-inserts `٬`.
- **تاریخ پرداخت** is not validated — there is no picker, no "not in the future" rule, and no duplicate-date rule.
- **یادداشت** is optional and unconstrained.
- The count of orders in a payment is not cross-checked against the orders actually shipped in that period (see the `۷۵` vs `۷۲` discrepancy in §6).

---

## 5. Logic

### 5.1 The estimate — the one formula to get right

This is the correction that touches the most screens in the product. The store-wide postage estimate is

```
estimate = Σ payment.totalPaid ÷ Σ payment.ordersShipped      over the last N payments (N is a setting, default ۳)
```

It is **not** the arithmetic mean of each payment's own per-order rate. With the sample data the two answers differ:

```
correct   (۱۹۹٬۲۷۳)  = (3,960,000 + 3,400,000 + 3,600,000) ÷ (18 + 17 + 20)
                     = 10,960,000 ÷ 55
                     = 199,272.72…  → displayed ۱۹۹٬۲۷۳   (fa() rounds on display)

wrong     (۲۰۰٬۰۰۰)  = (220,000 + 200,000 + 180,000) ÷ 3
                     = 600,000 ÷ 3
```

The hero card prints the correct arithmetic verbatim — `(۳٬۹۶۰٬۰۰۰ + ۳٬۴۰۰٬۰۰۰ + ۳٬۶۰۰٬۰۰۰) ÷ (۱۸ + ۱۷ + ۲۰) = ۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵` — and the three mini cards print the three per-order rates next to it precisely so the reader can see that the headline is not their average. Every surface that shows the figure carries the caption **«جمع پرداختی ÷ جمع سفارش‌ها»** (in its short or its long form); that caption is a contract, not decoration. Full derivation: `../logic/formulas.md` §2.

Rounding: the estimate is kept as a float internally and rounded only by `fa()` at display time (`Math.round`). Do not round it into storage — `۱۹۹٬۲۷۳` is a display of `199272.727…`, and the month total on the reports screen (`۱۴٬۳۴۷٬۶۵۶`) is `72 × 199,273`, i.e. computed from the **rounded** per-order figure. Pick one and state it (see §7).

### 5.2 The live projection in the form

```js
constructor(p) { super(p); this.state = { total: 4600000, ord: 20 }; }

var ok = S.ord >= 1, avg = ok ? S.total / S.ord : 0;
var est = ok ? (S.total + 3960000 + 3400000) / (S.ord + 18 + 17) : 199273, d = est - 199273;
// …
avgT: ok ? fa(avg) : '—', newEstT: fa(est),
deltaT: (d >= 0 ? '+' : '') + fa(d),
deltaCls: d > 0 ? 'badge st-warn' : 'badge st-done',
```

- `avg` is this one payment's own per-order cost — `4,600,000 ÷ 20 = 230,000` — shown in the rate strip. It is **informational only**; it never feeds the estimate.
- `est` re-runs the §5.1 formula over *the payment being typed plus the two most recent stored payments*, because N = 3 and the new payment pushes `۱۴۰۵/۰۶/۱۴` out of the window. That is exactly what the caption says: `پرداخت ۱۴۰۵/۰۶/۱۴ از محاسبه خارج می‌شود.`
  `(4,600,000 + 3,960,000 + 3,400,000) ÷ (20 + 18 + 17) = 11,960,000 ÷ 55 = 217,454.54…` → `۲۱۷٬۴۵۵`.
- `d = 217,454.54… − 199,273 = 18,181.54…` → `fa()` → `+۱۸٬۱۸۲`. Note the baseline in the subtraction is the **rounded** `199273` constant, not the unrounded current estimate — a 0.27 Toman inconsistency that shows up in the delta's last digit.
- Sign semantics: a **rising** estimate is amber (`st-warn`) because postage is getting more expensive; falling or flat is green (`st-done`). `fa()` renders a negative delta with U+2212 `−`, and the `+` is prepended manually for `d ≥ 0`.
- `199273` is a **hardcoded literal** in this artboard (as it is in `RecordSale.dc.html`: `var POSTAGE_EST = 199273;`). In the real app it must come from the same derivation as the hero card, so that changing N in settings moves the form's baseline too.
- The three stored payments (`3,960,000 / 18`, `3,400,000 / 17`, `3,600,000 / 20`) and the window size are likewise hardcoded in the projection expression; only `total` and `ord` are state.

### 5.3 Committing a payment — what must and must not change

The help paragraph is the specification: `سفارش‌های قبلی تغییر نمی‌کنند. اختلاف پرداخت واقعی با تخمین‌ها در گزارش سود و زیان به‌عنوان «مغایرت هزینه پست» می‌آید.`

1. The estimate is **copied onto each order at save time** (`../logic/formulas.md` §2). Recording a new payment changes the estimate for *future* orders only; no historical order is re-costed, and no historical profit figure moves.
2. The oldest payment in the window silently stops counting — the ledger reflects this by dropping its `در تخمین فعلی` badge and muting its date.
3. The gap between what was estimated on orders and what was actually paid to the post office is never absorbed into an order. It surfaces once, at period level, as `مغایرت هزینه پست`.

### 5.4 Where the figure is consumed

| Consumer | How it is used | Sample value |
|---|---|---|
| **Record sale** (`02-record-sale.md`) | `postage = channelDefaults[channel].post ? POSTAGE_EST : 0`. A read-only display box, never an input; a badge says whether the channel has postage on. It is subtracted in `profit = total − cost − packaging − postage − fee`. | `۱۹۹٬۲۷۳` |
| **Order detail** (`04-order-detail.md`) | The value stored on the order, shown as `پست` + chip `تخمینی` with the ÷ caption, `−۱۹۹٬۲۷۳`. A ghost action `ثبت هزینه واقعی پست` is offered; it also drives the refund loss `kitCost + postageEstimate + fee` (sample `140,000 + 199,273 + 31,000 = 370,273`). | `−۱۹۹٬۲۷۳` |
| **Dashboard** (`01-dashboard.md`) | Shipping-economics card: `هزینه پست (تخمینی)` `۱۹۹٬۲۷۳` with the ÷ caption and a month total `۱۲٬۷۵۳٬۴۷۲` (= 64 web+Instagram orders × 199,273); the cost bar segment `پست ۱۹۹٬۲۷۳`; and the break-even line — charged `۱۸۰٬۰۰۰` vs cost `۲۹۴٬۲۷۳` → `−۱۱۴٬۲۷۳` per order, `−۷٬۳۱۳٬۴۷۲` for the month. | `۱۹۹٬۲۷۳` |
| **Reports** (`12-reports.md`) | P&L line `هزینه پست (تخمینی)` `−۱۴٬۳۴۷٬۶۵۶` (= 72 shipped orders × 199,273) and the separate line `مغایرت هزینه پست` `−۴۱۲٬۳۴۴`; shipping tab KPI `پست واقعی / سفارش` `۲۰۵٬۰۰۰` (= `۱۴٬۷۶۰٬۰۰۰ ÷ ۷۲`) and per-channel پست columns. | see §6 |
| **Settings** (`15-settings.md`) | Owns **N**: a `.stepper` labelled `تعداد پرداخت‌های اخیر در محاسبه`, clamped `1…6` (`Math.min(6, n+1)` / `Math.max(1, n-1)`), with a live re-derivation `تخمین با این تنظیم` and the caption `جمع پرداختی ÷ جمع سفارش‌ها در {n} پرداخت اخیر: {Σpaid} ÷ {Σorders}`. Also the per-channel on/off switches, whose off-label is `خاموش` and whose on-label is `تخمین ۱۹۹٬۲۷۳`. | N = `۳` |

`Settings.dc.html` holds the authoritative payment array and the authoritative loop; this screen's hero card is the same computation with N fixed at 3:

```js
/* each payment: [total paid, orders shipped] — estimate = total paid ÷ total orders */
var PAY = [[3960000, 18], [3400000, 17], [3600000, 20], [3800000, 20], [3570000, 17], [3230000, 17]];
var used = PAY.slice(0, n);
var sumPaid = used.reduce(function (a, b) { return a + b[0]; }, 0),
    sumOrd  = used.reduce(function (a, b) { return a + b[1]; }, 0),
    est     = sumPaid / sumOrd;
```

N sweep over the sample payments (useful as a test table):

| N | Σ paid | Σ orders | estimate |
|---|---|---|---|
| 1 | 3,960,000 | 18 | 220,000 |
| 2 | 7,360,000 | 35 | 210,286 |
| **3** | **10,960,000** | **55** | **199,273** |
| 4 | 14,760,000 | 75 | 196,800 |
| 5 | 18,330,000 | 92 | 199,239 |
| 6 | 21,560,000 | 109 | 197,798 |

N = 4 is exactly the ledger's `جمع شهریور` footer (`۱۴٬۷۶۰٬۰۰۰ ÷ ۷۵ = ۱۹۶٬۸۰۰`), which is why the footer's note reads `جمع ÷ جمع`.

### 5.5 Estimate vs actual — how the variance is reported

The variance is **not** shown on this screen. It is a period-level P&L line, computed from the totals, and it is the reason the estimate never has to be "corrected":

```
postageVariance = (actual paid to the post office in the period) − (Σ postage estimates recorded on the period's orders)
                = 14,760,000 − 14,347,656
                = 412,344                → shown as −۴۱۲٬۳۴۴ (a deduction)
```

- P&L row (`Reports.dc.html`, `12-reports.md`): label `مغایرت هزینه پست`, value `−۴۱۲٬۳۴۴`, tooltip `پولی که واقعاً به پست دادید (۱۴٬۷۶۰٬۰۰۰) منهای تخمین‌هایی که روی سفارش‌ها ثبت شده بود (۱۴٬۳۴۷٬۶۵۶). مثبت یعنی پست گران‌تر از تخمین بوده است.`
- It sits **below** `سود ناخالص`, so gross profit is stated on estimates and net profit on actuals. See `../logic/formulas.md` §7.
- The shipping tab repeats it as a table row spanning the first four columns: `مغایرت هزینه پست (پرداخت واقعی ۱۴٬۷۶۰٬۰۰۰ − تخمین‌ها ۱۴٬۳۴۷٬۶۵۶)` → `−۴۱۲٬۳۴۴`.
- Per-order reconciliation is offered only as an undesigned affordance on the order-detail screen (`ثبت هزینه واقعی پست`), and the record-sale form deliberately does not ask for an actual amount at save time.

---

## 6. Sample data used

Source of truth: `../data/sample-data.md` § "Postage payments". Nothing on this screen is invented here.

### Stored payments

| # | تاریخ | paid | orders | per-order | in current window (N = 3) |
|---|---|---|---|---|---|
| 1 | ۱۴۰۵/۰۶/۲۸ | 3,960,000 | 18 | 3,960,000 ÷ 18 = **220,000** | ✓ |
| 2 | ۱۴۰۵/۰۶/۲۱ | 3,400,000 | 17 | 3,400,000 ÷ 17 = **200,000** | ✓ |
| 3 | ۱۴۰۵/۰۶/۱۴ | 3,600,000 | 20 | 3,600,000 ÷ 20 = **180,000** | ✓ |
| 4 | ۱۴۰۵/۰۶/۰۷ | 3,800,000 | 20 | 3,800,000 ÷ 20 = **190,000** | |
| 5 | ۱۴۰۵/۰۵/۳۱ | 3,570,000 | 17 | 3,570,000 ÷ 17 = **210,000** | |
| 6 | ۱۴۰۵/۰۵/۲۴ | 3,230,000 | 17 | 3,230,000 ÷ 17 = **190,000** | |

### Hero card

```
Σ paid   = 3,960,000 + 3,400,000 + 3,600,000 = 10,960,000
Σ orders = 18 + 17 + 20                      = 55
estimate = 10,960,000 ÷ 55 = 199,272.727…    → ۱۹۹٬۲۷۳
(mean of the three rates would be 600,000 ÷ 3 = 200,000 — NOT used)
```

### Ledger footer (`جمع شهریور`)

```
paid   = 3,960,000 + 3,400,000 + 3,600,000 + 3,800,000 = 14,760,000
orders = 18 + 17 + 20 + 20                             = 75
rate   = 14,760,000 ÷ 75 = 196,800                     → ۱۹۶٬۸۰۰
```
Only the four شهریور rows are in the footer; rows 5 and 6 are مرداد, although the date-range control above the table reads `۱۴۰۵/۰۵/۰۱ تا ۱۴۰۵/۰۶/۳۱` (see §7).

### The pending payment in the form (both breakpoints)

```
total = 4,600,000   orders = 20
this payment's rate = 4,600,000 ÷ 20 = 230,000                  → ۲۳۰٬۰۰۰
projected estimate  = (4,600,000 + 3,960,000 + 3,400,000) ÷ (20 + 18 + 17)
                    = 11,960,000 ÷ 55 = 217,454.545…            → ۲۱۷٬۴۵۵
delta               = 217,454.545… − 199,273 = 18,181.545…      → +۱۸٬۱۸۲   (badge st-warn)
```

### Downstream figures that depend on this screen

| Figure | Arithmetic | Where shown |
|---|---|---|
| `۱۴٬۳۴۷٬۶۵۶` | 72 shipped orders × 199,273 | reports P&L `هزینه پست (تخمینی)` |
| `۱۲٬۷۵۳٬۴۷۲` | 64 web + Instagram orders × 199,273 | dashboard month total |
| `۴۱۲٬۳۴۴` | 14,760,000 − 14,347,656 | reports `مغایرت هزینه پست` |
| `۲۰۵٬۰۰۰` | 14,760,000 ÷ 72 | reports `پست واقعی / سفارش` |
| `۲۹۴٬۲۷۳` | 95,000 (جعبه استاندارد) + 199,273 | dashboard/reports break-even |
| `−۱۱۴٬۲۷۳` | 180,000 − 294,273 | per-order shipping result |
| `−۷٬۳۱۳٬۴۷۲` | 64 × −114,273 | dashboard month total |
| `۳۷۰٬۲۷۳` | 140,000 + 199,273 + 31,000 | refund loss, INV-000035 / order detail |

Cross-check to note: the postage ledger accounts for **۷۵** orders in شهریور while the reports screen divides by **۷۲** shipped orders. Both numbers are in `../data/sample-data.md` and they disagree — see §7.

---

## 7. Open questions for this screen

- **The ledger footer and the date-range control disagree.** The table lists six payments spanning مرداد and شهریور, the filter chip says `۱۴۰۵/۰۵/۰۱ تا ۱۴۰۵/۰۶/۳۱`, and the single `tfoot` is labelled `جمع شهریور` and totals only the four شهریور rows. Decide whether the footer totals the filtered range (then relabel it) or the calendar month (then the table must be month-scoped), and design the multi-month case.
- **۷۵ paid-for orders vs ۷۲ shipped orders.** The payments say 75 parcels were paid for in شهریور; the reports screen computes `پست واقعی / سفارش` and the postage estimate over 72 shipped orders. Nothing reconciles the two, and nothing validates `تعداد سفارش ارسالی` against orders actually shipped in the period. Decide which population is authoritative, and whether a mismatch should warn.
- **Rounding of the estimate is unspecified.** `199272.727…` is displayed as `۱۹۹٬۲۷۳`, but the downstream month total `۱۴٬۳۴۷٬۶۵۶` is `72 × 199273` (the rounded figure), and the form's delta subtracts the hardcoded `199273` rather than the live value. Decide whether the estimate is rounded once at derivation and stored, or kept as a float and rounded per display — the two give different P&L numbers.
- **The postage estimate is a hardcoded constant in two artboards** (`199273` in `Postage.dc.html`'s projection and `var POSTAGE_EST = 199273` in `RecordSale.dc.html`), and this screen's projection also hardcodes the two preceding payments and the window size 3. Nothing in the design shows what the form's baseline or the record-sale figure looks like when N is changed in settings, when fewer than N payments exist, or when there are **zero** payments (the empty-state copy promises `تخمین پست برای سفارش‌ها صفر است` — so the estimate is 0, but no screen is drawn in that condition).
- **There is no date picker.** `تاریخ پرداخت` is a `.select` button showing today (`۱۴۰۵/۰۶/۳۱`) with the hint `امروز`; no calendar popover artboard exists on this screen, although `monthGrid()` exists in `helpers.js` and the orders screen has one. Back-dating a payment is therefore undesigned — which matters, because back-dating would change which payments fall in the "last N" window and could retroactively move the estimate.
- **No success, no editing, no deleting.** There is no toast, no success board and no post-save behaviour designed for `ثبت پرداخت` (contrast the record-sale screen, which has both a success board and a toast). Ledger rows have no hover state, no row menu, no edit and no delete; correcting a mistyped payment — the most likely real-world need, since a wrong `تعداد سفارش` silently skews every future order's profit — has no path.
- **`مبلغ کل پرداختی` has no validation.** Zero is accepted and would drag the estimate down; there is no upper sanity bound and no confirmation for an amount far from the recent average. Only the order count is validated, and its error (`تعداد سفارش باید دست‌کم ۱ باشد.`) has **no artboard** — it exists only in the live board's JS.
- **The mobile screen is a dead frame.** No input is wired, the note field, help paragraph and validation row are dropped, only two of six payments are listed, and there is no month footer, no date-range control, no `در تخمین فعلی` badge and no equivalent of the `تعداد پرداخت‌ها: ۳ · تغییر` link to settings. Decide what mobile is for here (view-only vs full entry) before building it.
- **`.badge.st-warn` and `.badge.st-loss` are undocumented tokens.** The delta badge uses `st-warn`, which exists in `rebel.css` (`background: var(--warn-soft); color: var(--warn)`) but is **not** in the badge list in `../design-system.md` §badges (which stops at `st-draft/pending/paid/done/cancel/refund`). Add it to the design system or reuse a documented variant.
- **`ثبت هزینه واقعی پست` on the order-detail screen has no destination.** The variance model says per-order actuals are never needed, yet that button is drawn. Either remove it or design what it does — and if it does write a per-order actual, decide how that interacts with `مغایرت هزینه پست`, which currently assumes every order carries an estimate.
- **`در تخمین فعلی` is a computed badge with no zero/edge design.** With N = 1 only the newest row is badged, with N = 6 every row is; no design exists for the "fewer payments than N" case or for a badge legend explaining the term.
- **Route and navigation are undefined**, as for every screen: the artboards link by filename (`Settings.dc.html`), not by URL, and the hero link needs to land on the `تخمین هزینه پست` card (anchor `#post` in `Settings.dc.html`). See `00-app-shell.md` §7. `Postage-Dark` exists but neither the mobile screen nor any state board has a dark variant.
