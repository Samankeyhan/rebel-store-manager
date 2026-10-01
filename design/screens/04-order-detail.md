# 04 — جزئیات سفارش (Order detail)

Route: **not defined** — the artboards link by filename (the top bar's crumb points at `Orders.dc.html`, mobile's back link at `OrdersMobile.dc.html`); a detail route keyed by invoice number has to be agreed, see `00-app-shell.md` §7 · sidebar key `orders` · top bar: **breadcrumb form** — parent `سفارش‌ها` + `chevL` + title `INV-000038` (this is the only screen in the app that uses `Topbar`'s `crumb` / `crumbHref` props).

One saved order, read-only, plus the two irreversible actions that can be taken on it. The screen is deliberately split into three audiences: the header and the items table are what the customer would recognise (and are the only parts that reach the printed invoice), the `بهای تمام‌شده و سود` card is internal-only, and the status timeline is the audit trail. Two of the six agreed client corrections live here and nowhere else: **cancelling** returns products *and* packaging to stock, records **no** postage cost and turns only the transaction fee into a loss; **refunding** captures a **status and an optional reason only** — there is no editable refund amount anywhere on this screen, and packaging + postage + fee become the order's loss. Everything else on the screen is display logic over an already-saved order.

Artboards: `OrderDetail.dc.html` (default — status `پرداخت‌شده`, no dialog), `OrderDetail-Draft` (`status: draft`), `OrderDetail-Completed` (`status: done`, h 1180), `OrderDetail-Cancel` (`dialog: cancel`), `OrderDetail-Refund` (`dialog: refund`), `OrderDetail-Dark` (`theme: dark`), `OrderDetail-Loading` (`state: loading`, h 760), `OrderDetail-Error` (`state: error`, h 760), and `OrderDetailMobile{,-Cancel,-Loading,-Error}`.
Source: `src/OrderDetail.dc.html` (desktop, 1440 × 1080) and `src/OrderDetailMobile.dc.html` (mobile, 390 × 1560).
The desktop artboard is interactive: props `status` (`draft | pending | paid | done | cancel | refund`, default `paid`), `dialog` (`none | cancel | refund`), `state` (`ready | loading | error`), `theme`, `h`. `status` drives the badge, the transition buttons, the terminal note, which destructive actions exist and the whole timeline; the two dialogs also open from the header buttons at runtime (`openCancel` / `openRefund` → `setState`). Everything else on the board — the items, both money blocks and every string inside the dialogs — is **static markup for INV-000038** and does not react to `status`; see §7.

---

## 1. Layout

### Desktop (1440 × 1080; `-Completed` is 1180 because its timeline has one entry more)

```
┌ sidebar 264 (RIGHT) ┬──────────────────────── content 1176 ────────────────────────┐
│                     │ top bar 64  ·  crumb: سفارش‌ها ‹ INV-000038                   │
│                     ├──────────────────────────────────────────────────────────────┤
│                     │ [1] HEADER CARD  (full width, padding 18 20, gap 16)         │
│                     │  ┌ right block ─────────────┐        ┌ left block ────────┐  │
│                     │  │ INV-000038 (20px, .inv)  │        │ مبلغ کل   (caption)│  │
│                     │  │ [badge status][ch وب‌سایت] │        │ ۳٬۱۳۰٬۰۰۰ تومان 22px│ │
│                     │  │ مشتری: نگار ک. · ثبت: … · بسته‌بندی: جعبه وینیل         │  │
│                     │  └──────────────────────────┘        └────────────────────┘  │
│                     │  ──────────────────── sep 1px ─────────────────────────────  │
│                     │  تغییر وضعیت به: [تکمیل‌شده]  [چاپ فاکتور] ←spacer→ [لغو سفارش][ثبت مرجوعی]
│                     ├────────────────────────────────────┬─────────────────────────┤
│                     │ [2] اقلام سفارش   (flex-grow, min-0)│ [3] بهای تمام‌شده و سود  │
│                     │  card-h: title + «۲ ردیف · ۳ عدد»  │     (card, surface-2,   │
│                     │  ┌ table .tbl width 100% ────────┐ │      width 388, fixed)  │
│                     │  │ th 40px  محصول تعداد قیمت‌واحد │ │  6 rows + sep + total   │
│                     │  │          تخفیف  جمع (تومان)    │ │  + حاشیه سود + ship box │
│                     │  │ td 52px  row 1: وینیل آلبوم اول│ │  + «ثبت هزینه واقعی پست»│
│                     │  │ td 52px  row 2: پوستر تور ۱۴۰۴ │ ├─────────────────────────┤
│                     │  └───────────────────────────────┘ │ [4] تاریخچه وضعیت        │
│                     │  ── border-top 1px ──              │     (card, width 388)   │
│                     │        ┌ customer total 340 ─────┐ │  <ol> newest → oldest   │
│                     │        │ 👤 پرداختی مشتری (روی…) │ │  dot 12px + 2px rail    │
│                     │        │ جمع اقلام / تخفیف /      │ │  from ← to badges,      │
│                     │        │ هزینه ارسال / sep /      │ │  when · مدیر فروشگاه,    │
│                     │        │ مبلغ کل (.total)        │ │  note                   │
│                     │        └─────────────────────────┘ │                         │
└─────────────────────┴────────────────────────────────────┴─────────────────────────┘
```

- `main` padding `24px 32px 40px`, `display:flex; flex-direction:column; gap:20px` — the `[[PAGE]]` contract from `00-app-shell.md` §5, written out by hand here because this screen needs the crumb props on `Topbar`.
- The two-column row below the header is `display:flex; gap:24px; align-items:flex-start`. Left (visual) column: `width:388px; flex-shrink:0; gap:20px`. Right (content) column: `flex-grow:1; min-width:0; gap:20px`. **Nothing is `position:sticky`** on this screen.
- Header card: `display:flex; justify-content:space-between; align-items:flex-start; gap:16px` for the top row; the action row is `display:flex; align-items:center; gap:8px; flex-wrap:wrap` with a `<span style="flex-grow:1">` spacer between `چاپ فاکتور` and the two destructive buttons — so status changes + print sit at the inline start (visual right) and the destructive pair is pushed to the inline end (visual left). **There is no separate destructive section on desktop** (mobile has one).
- Items table columns: `محصول` (default alignment, contains a two-line stack) then four `.n` columns (`تعداد`, `قیمت واحد`, `تخفیف`, `جمع (تومان)`). `.tbl` is `width:100%; border-collapse:separate` with **automatic layout — no column widths are set in the source** (`th`: 12px/600, height 40, `padding:0 16px`, `background:--surface-2`; `td`: height 52, 13.5px, `padding:0 16px`; `.n` = text-align right + `tnum`). See §7.
- Customer total block: inside the items card, `border-top:1px solid --border`, `padding:14px 20px`, `display:flex; justify-content:flex-end` with an inner `width:340px; gap:6px` column of `.sl` rows.
- Internal card: `background: var(--surface-2)`, its `card-h` has `border-bottom-style: dashed`; body `card-b` with `gap:8px`. The profit row is a `.sl.total` on `--profit-soft`, bled out with `margin:0 -10px; padding:8px 10px; border-radius:8px`. Below it: the margin row (`.sl.t-cap`), then the shipping-economics box (`--surface`, 1px border, radius 8, `padding:8px 10px`), then a `btn btn-ghost btn-sm` with `padding:0`.
- Timeline: `<ol style="list-style:none; margin:0; padding:16px 20px">`; each `<li>` is `display:flex; gap:12px` — a 12px dot (`border-radius:50%`, `box-shadow:0 0 0 3px var(--surface)`, `margin-top:5px`) over a 2px `--border` rail that is `display:none` on the last item, then a `gap:3px` text column with `padding-bottom:16px`.
- **Dialogs** are siblings of the content column inside the outer 1440 `.rs`, so `left:50%` centres them on the **whole board including the sidebar**, not on the 1176 content area: cancel `top:96px; width:560px; margin-left:-280px`; refund `top:110px; width:580px; margin-left:-290px`. Both are `role="alertdialog"` with `aria-labelledby` and sit over a full-board `.overlay`. Dialog internals: `.d-h` `padding:20px 24px 0; gap:14px` (40px `.d-ico.danger` + title stack), `.d-b` `padding:16px 24px; gap:14px`, `.d-f` `padding:16px 24px` on `--surface-2` with the primary destructive button first (inline start).

### Mobile (390 × 1560)

```
┌───────────────────────── 390 ─────────────────────────┐
│ MobileBar 56  ·  back chevron + «INV-000038»          │
├───────────────────────────────────────────────────────┤
│ main padding 16 16 100 · column · gap 14              │
│ ┌ [1] header card (padding 14, gap 10) ─────────────┐ │
│ │ [badge پرداخت‌شده][ch وب‌سایت]                      │ │
│ │ مشتری: نگار ک.  /  ثبت: ۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴        │ │
│ │ مبلغ کل ................ ۳٬۱۳۰٬۰۰۰ تومان  (.total)│ │
│ │ grid 1fr 48: [تغییر وضعیت به تکمیل‌شده][🖨 48×48]  │ │
│ └───────────────────────────────────────────────────┘ │
│ ┌ [2] اقلام سفارش (card, rows split by 1px border) ─┐ │
│ │ وینیل آلبوم اول / ۱ × ۲٬۴۵۰٬۰۰۰ ...... ۲٬۴۵۰٬۰۰۰  │ │
│ │ پوستر تور ۱۴۰۴ / ۲ × ۲۹۰٬۰۰۰ · تخفیف … .. ۵۰۰٬۰۰۰ │ │
│ │ ── totals block: جمع اقلام/تخفیف/ارسال/مبلغ کل ──  │ │
│ └───────────────────────────────────────────────────┘ │
│ ┌ [3] 🔒 بهای تمام‌شده و سود (surface-2, padding 14) ─┐│
│ │ 4 cost rows + سود (tinted .total)                 │ │
│ └───────────────────────────────────────────────────┘ │
│ ┌ [4] تاریخچه وضعیت (padding 14, gap 12) ───────────┐ │
│ │ ● newest first, 10px dot + 2 text lines           │ │
│ └───────────────────────────────────────────────────┘ │
│ ── border-top 1px dashed --border-strong ──           │
│ [5] عملیات حساس                                       │
│     [ لغو سفارش       ] full-width, btn-danger-o, lg  │
│     [ ثبت مرجوعی      ] full-width, btn-danger-o, lg  │
└───────────────────────────────────────────────────────┘

cancel sheet (OrderDetailMobile-Cancel, board h 844):
┌ .overlay (inset 0) ───────────────────────────────────┐
│                  ┌ .m-sheet bottom, radius 18 18 0 0 ┐│
│                  │ grab handle                        ││
│                  │ [🚫 40] لغو سفارش INV-000038؟      ││
│                  │ 4 × .effect rows                   ││
│                  │ input «دلیل لغو» h 44              ││
│                  │ [لغو سفارش] danger, full, lg       ││
│                  │ [انصراف]   outline, full, lg       ││
└──────────────────┴────────────────────────────────────┘
```

Mobile differences from desktop, exactly as built:

- `main` padding is `16px 16px 100px; gap:14px` — **not** the `[[MPAGE]]` contract (`14px 16px 100px; gap:12px`); this screen is hand-assembled. See §7.
- The invoice number appears only in the bar title; the header card drops the `.inv` line and the `بسته‌بندی: جعبه وینیل` fragment, and stacks `مشتری` / `ثبت` vertically instead of inline.
- One hardcoded primary action `تغییر وضعیت به تکمیل‌شده` (48px tall) + a 48×48 icon-only print button with `aria-label="چاپ فاکتور"`; the transition list is not computed on mobile.
- Items are stacked rows (`padding:10px 14px`, 1px top border each), not a table: name + `qty × unitPrice` (+ discount fragment) on the right, row total on the left. No column headers, no per-row discount column, no `جمع (تومان)` header.
- The internal card omits `درآمد سفارش`, `حاشیه سود`, the shipping-economics box and the `ثبت هزینه واقعی پست` button, and shortens the postage caption; the profit row's label is just `سود`.
- The timeline is two hand-written rows (no `<ol>`, no rail, 10px dots) and carries only the paid-state history.
- The destructive pair gets its own labelled section (`عملیات حساس`), full-width 48px buttons, above the 100px bottom padding.
- Touch targets ≥ 44px throughout (48px for the primary/lg buttons, 44px for the sheet's reason input).

---

## 2. Copy (verbatim)

### Header card

| Slot | String |
|---|---|
| top-bar crumb parent | `سفارش‌ها` |
| top-bar / mobile-bar title | `INV-000038` |
| invoice number (`.inv`, 20px) | `INV-000038` |
| status badge (`{{stName}}`) | `پرداخت‌شده` (default) — the six possible values are in §4 |
| channel chip | `وب‌سایت` |
| customer | `مشتری: ` + bold `نگار ک.` |
| registered at | `ثبت: ۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴` |
| packaging (desktop only) | `بسته‌بندی: جعبه وینیل` |
| total caption | `مبلغ کل` |
| total value | `۳٬۱۳۰٬۰۰۰` + `تومان` |
| transitions label | `تغییر وضعیت به:` |
| transition button (paid) | `تکمیل‌شده` |
| print button | `چاپ فاکتور` |
| cancel button | `لغو سفارش` |
| refund button | `ثبت مرجوعی` |
| mobile primary | `تغییر وضعیت به تکمیل‌شده` |
| mobile print `aria-label` | `چاپ فاکتور` |
| mobile destructive section label | `عملیات حساس` |

Terminal note (`{{terminalNote}}`, replaces the transition buttons, info icon 16):

| status | String |
|---|---|
| `تکمیل‌شده` | `سفارش تکمیل شده است.` |
| `لغوشده` | `سفارش لغو شده؛ عملیاتی باقی نمانده.` |
| `مرجوعی` | `مرجوعی ثبت شده؛ عملیاتی باقی نمانده.` |

### Items card

Card header `اقلام سفارش` · caption `۲ ردیف · ۳ عدد`.

Column headers, inline start → inline end:

| # | header | class |
|---|---|---|
| 1 | `محصول` | — |
| 2 | `تعداد` | `n` |
| 3 | `قیمت واحد` | `n` |
| 4 | `تخفیف` | `n` |
| 5 | `جمع (تومان)` | `n` |

Rows (desktop):

| محصول | sub-label | تعداد | قیمت واحد | تخفیف | جمع (تومان) |
|---|---|---|---|---|---|
| `وینیل آلبوم اول` | `وینیل` | `۱` | `۲٬۴۵۰٬۰۰۰` | `—` (`.nil`) | `۲٬۴۵۰٬۰۰۰` |
| `پوستر تور ۱۴۰۴` | `پوستر · تخفیف: مشتری ثابت` | `۲` | `۲۹۰٬۰۰۰` | `−۸۰٬۰۰۰` | `۵۰۰٬۰۰۰` |

Mobile row sub-lines instead of columns: `۱ × ۲٬۴۵۰٬۰۰۰` and `۲ × ۲۹۰٬۰۰۰ · تخفیف −۸۰٬۰۰۰ (مشتری ثابت)`.

### Customer total block (this is also exactly what the printed invoice carries)

Block header (user icon 14): `پرداختی مشتری (روی فاکتور)`

| row | label | value |
|---|---|---|
| 1 | `جمع اقلام` | `۳٬۰۳۰٬۰۰۰` |
| 2 | `تخفیف` | `−۸۰٬۰۰۰` |
| 3 | `هزینه ارسال` | `۱۸۰٬۰۰۰` |
| — | separator | |
| 4 | `مبلغ کل` (`.sl.total`) | `۳٬۱۳۰٬۰۰۰` + `تومان` |

Mobile is the same four rows, with `مبلغ کل` = `۳٬۱۳۰٬۰۰۰` and no unit span.

### Internal cost breakdown (`داخلی` — never printed, never shown to a customer)

Card header (lock icon 16): `بهای تمام‌شده و سود` · caption `داخلی`

| row | label | value | notes |
|---|---|---|---|
| 1 | `درآمد سفارش` | `۳٬۱۳۰٬۰۰۰` | desktop only |
| 2 | `بهای تمام‌شده کالا` | `−۱٬۵۷۰٬۰۰۰` | |
| 3 | `بسته‌بندی · جعبه وینیل` | `−۱۴۰٬۰۰۰` | kit name interpolated |
| 4 | `پست` + chip `تخمینی`, sub-line `جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر` | `−۱۹۹٬۲۷۳` | mobile label is `پست (تخمینی)` with sub-line `جمع پرداختی ÷ جمع سفارش‌ها` |
| 5 | `کارمزد تراکنش` | `−۳۱٬۰۰۰` | |
| — | separator | | |
| 6 | `سود این سفارش` (mobile: `سود`) | `۱٬۱۸۹٬۷۲۷` + `تومان` | `.pos` on `--profit-soft` |
| 7 | `حاشیه سود` | `۳۸٪` | desktop only |

Shipping-economics box (desktop only), verbatim:

```
ارسال: دریافتی ۱۸۰٬۰۰۰ − هزینه ۳۳۹٬۲۷۳ = −۱۵۹٬۲۷۳
```

Ghost button under it (edit icon 14), desktop only: `ثبت هزینه واقعی پست`

### Status history timeline

Each desktop entry renders: `from` badge (or the bold text `ایجاد` when there is no previous status) · `chevL` 14 · `to` badge, then `{{e.when}} · مدیر فروشگاه`, then the note. Newest first.

Entries per status — every string and Jalali date exactly as in the source's `HIST`:

| status | from → to | when (`{{e.when}}`) | note |
|---|---|---|---|
| all | `ایجاد` → `در انتظار` | `۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴` | `ثبت سفارش از فرم ثبت فروش` |
| paid, done, cancel, refund | `در انتظار` → `پرداخت‌شده` | `۱۴۰۵/۰۶/۳۰ · ۱۸:۱۰` | `پرداخت کارت‌به‌کارت تأیید شد` |
| done, refund | `پرداخت‌شده` → `تکمیل‌شده` | `۱۴۰۵/۰۶/۳۱ · ۰۹:۳۰` | `ارسال با پست پیشتاز` |
| cancel | `پرداخت‌شده` → `لغوشده` | `۱۴۰۵/۰۶/۳۱ · ۱۱:۰۰` | `مشتری منصرف شد · ۳٬۱۳۰٬۰۰۰ تومان بازپرداخت شد` |
| refund | `تکمیل‌شده` → `مرجوعی` | `۱۴۰۵/۰۶/۳۱ · ۱۷:۴۵` | `کالا آسیب‌دیده رسید · زیان ۳۷۰٬۲۷۳ تومان` |
| draft (replaces all of the above) | `ایجاد` → `پیش‌نویس` | `۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴` | `ذخیره به‌صورت پیش‌نویس` |

Actor on every row: `مدیر فروشگاه` (hardcoded, joined to the date with ` · `).

Mobile timeline (two hand-written rows, different wording from desktop):

| row | line 1 | line 2 |
|---|---|---|
| 1 | `در انتظار` ← `پرداخت‌شده` (both bold, literal `←`) | `۱۴۰۵/۰۶/۳۰ · ۱۸:۱۰ · پرداخت کارت‌به‌کارت تأیید شد` |
| 2 | `ثبت با وضعیت ` + bold `در انتظار` | `۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴` |

### Cancel dialog — `OrderDetail-Cancel` (desktop), word for word

Title: `لغو سفارش INV-000038؟`
Sub-title: `این سفارش «پرداخت‌شده» است و هنوز ارسال نشده. با لغو:`

Effect rows, in order (marker = the `.e-ico` tint: **↑** `e-up` green `--profit`, **↓** `e-down` red `--loss`, **=** `e-flat` neutral `--text-2`):

| # | marker | icon | string (bold lead-in, then body) |
|---|---|---|---|
| 1 | ↑ | `package` | `کالا به موجودی برمی‌گردد:` `۱ «وینیل آلبوم اول» و ۲ «پوستر تور ۱۴۰۴».` |
| 2 | ↑ | `box` | `بسته‌بندی به موجودی برمی‌گردد:` `۱ «جعبه وینیل».` |
| 3 | = | `truck` (mirrored) | `بدون هزینه پست:` `سفارش ارسال نشده، پس هزینه پستی ثبت نمی‌شود.` |
| 4 | ↓ | `percent` | `تنها زیان، کارمزد تراکنش است:` `۳۱٬۰۰۰ تومان` `به‌عنوان زیان ثبت می‌شود. اگر سفارش کارمزد نداشته باشد، زیانی ثبت نمی‌شود.` |
| 5 | = | `wallet` | `پول مشتری:` `۳٬۱۳۰٬۰۰۰ تومان` `دریافت‌شده باید به مشتری بازگردانده شود و به‌عنوان بازپرداخت ثبت می‌شود.` |
| 6 | = | `chart` | `گزارش‌ها:` `این سفارش از فروش و سود شهریور حذف می‌شود و وضعیت آن «لغوشده» می‌شود.` |

Reason field: label `دلیل لغو` · placeholder `مثلاً: مشتری منصرف شد` · help `در تاریخچه وضعیت ثبت می‌شود.`
Warning line (`.t-cap.neg.b`, alert icon 14): `این کار برگشت‌پذیر نیست.`
Footer buttons, inline start → inline end: `لغو سفارش` (`btn btn-danger`, ban icon) · `انصراف` (`btn btn-outline`, closes the dialog).

Mobile cancel sheet (`OrderDetailMobile-Cancel`) — same title, four condensed effect rows, no sub-title, no reports row, no irreversibility line:

| # | marker | icon | string |
|---|---|---|---|
| 1 | ↑ | `package` | `۱ «وینیل آلبوم اول» و ۲ «پوستر تور ۱۴۰۴» به موجودی برمی‌گردند.` |
| 2 | ↑ | `box` | `۱ «جعبه وینیل» به موجودی بسته‌بندی برمی‌گردد.` |
| 3 | ↓ | `percent` | `هزینه پستی ثبت نمی‌شود (ارسال نشده).` + bold `تنها زیان: کارمزد تراکنش ۳۱٬۰۰۰ تومان` + `.` |
| 4 | = | `wallet` | `۳٬۱۳۰٬۰۰۰ تومان` `باید به مشتری بازگردانده شود.` |

Reason input: placeholder and `aria-label` both `دلیل لغو` (no visible label, no help text).
Buttons, stacked full width: `لغو سفارش` (danger) then `انصراف` (outline).

### Refund dialog — `OrderDetail-Refund` (desktop only), word for word

Title: `ثبت مرجوعی برای INV-000038`
Sub-title: `کالا برگشت داده شده است. با ثبت مرجوعی، وضعیت سفارش «مرجوعی» می‌شود و:`

| # | marker | icon | string |
|---|---|---|---|
| 1 | ↑ | `package` | `فقط کالا به موجودی برمی‌گردد:` `۱ «وینیل آلبوم اول» و ۲ «پوستر تور ۱۴۰۴».` |
| 2 | ↓ | `box` | `این مبالغ زیان این سفارش می‌شوند:` `بسته‌بندی ۱۴۰٬۰۰۰ + پست ۱۹۹٬۲۷۳ + کارمزد تراکنش ۳۱٬۰۰۰ = ۳۷۰٬۲۷۳ تومان. جعبه مصرف‌شده به موجودی برنمی‌گردد.` |
| 3 | = | `wallet` | `بازپرداخت پول به مشتری بیرون از برنامه انجام می‌شود.` `این‌جا مبلغی ثبت نمی‌شود؛ فقط وضعیت سفارش و دلیل آن ذخیره می‌شود.` |

Profit comparison (2-column grid on `--surface-2`, radius 10, padding 12):

| caption | value |
|---|---|
| `سود فعلی سفارش` | `۱٬۱۸۹٬۷۲۷ تومان` (`.pos`) |
| `پس از مرجوعی` | `−۳۷۰٬۲۷۳ تومان` (`.neg`) |

Reason field: label `دلیل مرجوعی` + `(اختیاری)` in `.opt` · control is a `.select` **button** (not a text input) showing `کالا آسیب‌دیده رسید` with a `chevD` 14 · help `در تاریخچه وضعیت سفارش ثبت می‌شود.`
Footer buttons: `ثبت مرجوعی` (`btn btn-danger`, undo icon mirrored) · `انصراف` (`btn btn-outline`).

**There is no amount input in this dialog.** The only editable control is the reason.

### Loading state (desktop + mobile)

Skeletons only, `aria-busy="true"`, no copy. Desktop: a header card (320×24, 420×14, 520×40) then the two columns (18px/120 title, two 44px rows, a 340×110 block aligned to the inline end; right column 388px with a 160px title and three 16px rows plus a 36px block). Mobile: three rounded blocks, 180 / 220 / 160px.

### Error state — “order not found”

| Slot | String |
|---|---|
| desktop title | `سفارش INV-000038 پیدا نشد` |
| desktop body | `ممکن است نشانی اشتباه باشد یا ارتباط با سرور قطع شده باشد. اگر این سفارش را تازه ثبت کرده‌اید، چند لحظه بعد دوباره تلاش کنید.` |
| desktop buttons | `تلاش دوباره` (outline, refresh icon) · `بازگشت به سفارش‌ها` (ghost link → `Orders.dc.html`) |
| mobile title | `سفارش پیدا نشد` |
| mobile body | `ممکن است ارتباط قطع شده باشد. دوباره تلاش کنید.` |
| mobile buttons | `تلاش دوباره` · `بازگشت به سفارش‌ها` (→ `OrdersMobile.dc.html`) |

Art: triangle icon (`tri`, 28 desktop / 26 mobile) in a `--loss-soft` disc. Desktop padding `110px 24px`, mobile `48px 20px`. This is a **bespoke** empty block, not the shared `[[STATES:…]]` macro (which this screen does not use).

### Status names (from `helpers.js` `ST`) and channel names (`CH`)

`پیش‌نویس` (`st-draft`) · `در انتظار` (`st-pending`) · `پرداخت‌شده` (`st-paid`) · `تکمیل‌شده` (`st-done`) · `لغوشده` (`st-cancel`) · `مرجوعی` (`st-refund`); channel here is `وب‌سایت` (`ch-web`).

---

## 3. Interactive states designed

| element | states |
|---|---|
| Screen status | `پرداخت‌شده` (`OrderDetail`, default) · `پیش‌نویس` (`-Draft`) · `تکمیل‌شده` (`-Completed`) — and `در انتظار`, `لغوشده`, `مرجوعی` are supported by the `status` prop but **have no built artboard** |
| Screen state | ready · loading (`-Loading`) · error/not-found (`-Error`) · dark (`-Dark`, ready + paid) |
| Status badge | six variants, one per status (`st-draft` dashed outline, `st-pending` amber, `st-paid` blue, `st-done` green, `st-cancel` grey, `st-refund` violet) |
| Transition buttons | 0–3 buttons; the **last** one is `btn btn-primary`, all earlier ones `btn btn-outline`; the whole group is replaced by the info-icon terminal note when there are none. No hover/pressed/confirm state is drawn, and nothing happens on click in the artboard |
| `چاپ فاکتور` | single state, present in every status (including terminal ones); no `href` is wired |
| `لغو سفارش` | present for `پیش‌نویس` / `در انتظار` / `پرداخت‌شده`; absent otherwise (`canCancel`) |
| `ثبت مرجوعی` | present for `پرداخت‌شده` / `تکمیل‌شده`; absent otherwise (`canRefund`) |
| Cancel dialog | closed (`dialog: none`) · open (`-Cancel`) + `.overlay`; opened by `openCancel`, closed by `انصراف` (`closeDialog`); suppressed unless `state === 'ready'` |
| Refund dialog | closed · open (`-Refund`) + `.overlay`; same open/close wiring; desktop only |
| Dialog reason controls | cancel: empty text input (placeholder only) — no filled, focus or error state drawn. refund: `.select` button in its **chosen** state (`کالا آسیب‌دیده رسید`); the open list, the empty/unchosen state and the option set are not designed |
| Items table row | default · hover (`--surface-2` via `.tbl tbody tr:hover td`) |
| Discount cell | `—` (`.nil`) when no discount · `−۸۰٬۰۰۰` when there is one |
| Timeline entry | first/middle entries draw the connecting rail; the last (oldest) sets `display:none` on it. `ایجاد` renders as bold text, every other `from` as a badge |
| Mobile | ready · cancel sheet (`-Cancel`) · loading · error. **No mobile refund sheet, and no mobile dark, draft or completed artboard** |
| Mobile sheet | grab handle + overlay; `role="alertdialog"`, `aria-labelledby="mc-t"` |

Focus ring is the global `box-shadow: 0 0 0 3px var(--ring)`; every effect row carries an icon *and* a bold text lead-in, so no cause/effect on this screen is conveyed by colour alone.

---

## 4. Validation + allowed transitions

There is **no form validation on this screen**: the only two inputs are the cancel reason (free text, no rule, no max length drawn) and the refund reason (explicitly `(اختیاری)`). Nothing is required, nothing can be invalid, and no error message is designed for either dialog. What this screen validates instead is *which status you are allowed to move to*, and that is data, not input.

The transition map, verbatim from the source:

```js
var NEXT = { draft: ['pending', 'paid', 'done'], pending: ['paid', 'done'], paid: ['done'], done: [], cancel: [], refund: [] };
```

As a matrix (rows = current status, columns = target offered by the transition buttons; **·** = not offered):

| from ↓ / to → | پیش‌نویس | در انتظار | پرداخت‌شده | تکمیل‌شده | لغوشده | مرجوعی |
|---|---|---|---|---|---|---|
| **پیش‌نویس** | · | ✔ | ✔ | ✔ (primary) | via `لغو سفارش` | · |
| **در انتظار** | · | · | ✔ | ✔ (primary) | via `لغو سفارش` | · |
| **پرداخت‌شده** | · | · | · | ✔ (primary) | via `لغو سفارش` | via `ثبت مرجوعی` |
| **تکمیل‌شده** | · | · | · | · (terminal) | · | via `ثبت مرجوعی` |
| **لغوشده** | · | · | · | · | · (terminal) | · |
| **مرجوعی** | · | · | · | · | · | · (terminal) |

Explicitly impossible in this design:

- **No backwards move, ever.** `پرداخت‌شده` cannot return to `در انتظار`; `تکمیل‌شده` cannot return to `پرداخت‌شده`; nothing can return to `پیش‌نویس`. `NEXT` is forward-only and `done`, `cancel`, `refund` have empty lists.
- **`لغوشده` and `مرجوعی` are never offered as buttons in `تغییر وضعیت به:`** — they are reachable *only* through the two destructive actions, each behind its own confirmation dialog. This mirrors the record-sale form, where the status control offers only the four non-terminal statuses (`02-record-sale.md` §2, Status).
- **Cancel and refund never overlap except at `پرداخت‌شده`**, the one status where both are offered: `canCancel = ['draft','pending','paid']`, `canRefund = ['paid','done']`. A completed (shipped) order cannot be cancelled; a draft or pending order cannot be refunded (nothing was paid or shipped yet).
- Once in `لغوشده` or `مرجوعی` the order is frozen: no transitions, no cancel, no refund — only `چاپ فاکتور` and the terminal note remain.

This matrix is the same one recorded in `../logic/formulas.md` §6, which also gives the stock consequence of each status (draft = not reserved; pending/paid/done = deducted; cancelled/refunded = returned).

---

## 5. Logic

All money arithmetic is shared: see `../logic/formulas.md` §1 (order profit and margin), §2 (the store-wide postage estimate), §5 (kit cost) and §6 (stock effects, cancel and refund). This screen only *displays* those numbers for an order that is already saved — nothing is recomputed from inputs here. What follows is what each action on this screen does.

### The internal breakdown and the order's profit

```
درآمد سفارش        = customerTotal = itemsNet + shippingCharge      = 3,130,000
بهای تمام‌شده کالا   = Σ (qty × product.cost at time of sale)         = 1,570,000
بسته‌بندی           = kitCost (جعبه وینیل)                            =   140,000
پست (تخمینی)      = postageEstimate if the channel has postage on   =   199,273
کارمزد تراکنش       = transactionFee                                  =    31,000
سود این سفارش      = 3,130,000 − 1,570,000 − 140,000 − 199,273 − 31,000 = 1,189,727
حاشیه سود          = 1,189,727 ÷ 3,130,000 = 38.0%  →  ۳۸٪
```

The postage line is **the one store-wide estimate**, not a per-order measurement: `۱۹۹٬۲۷۳ = ۱۰٬۹۶۰٬۰۰۰ ÷ ۵۵` — total paid ÷ total orders over the last 3 postage payments (`../logic/formulas.md` §2; `../data/sample-data.md` § Postage payments). It enters this screen in exactly one place, row 4 of the internal card, and it is always shown with its caption «جمع پرداختی ÷ جمع سفارش‌ها» (desktop appends «در ۳ پرداخت اخیر»). Per §2 the estimate is **copied onto the order at save time**, so this row shows the value as of that order, and changing the setting later never rewrites it. The `ثبت هزینه واقعی پست` button is the (undesigned) escape hatch for replacing the estimate with the real cost for this one order — see §7.

Shipping economics for the order, the same formula as the record-sale summary (`../logic/formulas.md` § “Shipping result for one order”), with this order's vinyl box instead of the standard box:

```
shippingResult = shippingCharge − (kitCost + postageEstimate)
               = 180,000 − (140,000 + 199,273) = 180,000 − 339,273 = −159,273
```

Nothing about the internal card, the shipping box or the profit row ever reaches the customer: the printed invoice carries only `جمع اقلام`, `تخفیف`, `هزینه ارسال` and `مبلغ قابل پرداخت` (`src/Invoice.dc.html` contains no postage, packaging, fee, cost or profit string at all) — which is why the customer block is labelled `پرداختی مشتری (روی فاکتور)` and the internal card `داخلی` with a lock icon.

### Cancel — `لغو سفارش`

Stock:

- **Products return to stock**: `+۱ وینیل آلبوم اول`, `+۲ پوستر تور ۱۴۰۴`.
- **Packaging returns to stock too**: `+۱ جعبه وینیل` — the kit was allocated but never consumed, because the parcel was never sent. (This is the correction: cancel is the only action that returns packaging.)

Money:

- **No postage cost is recorded.** Nothing was posted, so the `۱۹۹٬۲۷۳` estimate is *not* charged to this order — the dialog says so in its own row (`بدون هزینه پست`, neutral marker, not a loss).
- **The only loss is the transaction fee, if the order had one.** With no fee, cancelling costs the store nothing:

```
cancelLoss = transactionFee = 31,000                    (this order)
cancelLoss = 0                                          (an order with no fee)
             ↑ products 1,570,000 back in stock, packaging 140,000 back in stock,
               postage 0 (never posted), so nothing else is written off.
```

- The customer's `۳٬۱۳۰٬۰۰۰` must be handed back, and the dialog says it is recorded as a refund of money; the movement itself happens outside the app.
- Reporting: `این سفارش از فروش و سود شهریور حذف می‌شود` — the order leaves the period's revenue and profit entirely (it does not stay in at `−31,000`); the fee survives as a loss. Compare `../logic/formulas.md` §7.

### Refund — `ثبت مرجوعی`

**What is captured: a status and an optional reason. Nothing else.** There is no refund-amount field anywhere on this screen — not in the dialog, not in the header, not in the internal card. The dialog states it outright: `بازپرداخت پول به مشتری بیرون از برنامه انجام می‌شود. این‌جا مبلغی ثبت نمی‌شود؛ فقط وضعیت سفارش و دلیل آن ذخیره می‌شود.`

Stock: **products only** (`فقط کالا به موجودی برمی‌گردد`) — `+۱ وینیل آلبوم اول`, `+۲ پوستر تور ۱۴۰۴`. The box is gone: `جعبه مصرف‌شده به موجودی برنمی‌گردد`.

Money — the three unrecoverable amounts become the order's loss:

```
refundLoss = kitCost + postageEstimate + transactionFee
           = 140,000 + 199,273 + 31,000 = 370,273
profit: +1,189,727  →  −370,273
```

Both sides of that swing are printed in the dialog's own 2-column grid (`سود فعلی سفارش` `۱٬۱۸۹٬۷۲۷ تومان` → `پس از مرجوعی` `−۳۷۰٬۲۷۳ تومان`), and the resulting timeline note reads `کالا آسیب‌دیده رسید · زیان ۳۷۰٬۲۷۳ تومان`. The same rule reproduces the refunded sample order in the list: INV-000035's profit `−۲۹۴٬۲۷۳` = `95,000 (جعبه استاندارد) + 199,273 (پست) + 0 (کارمزد)` — see `../data/sample-data.md` § Orders.

### Everything else on the screen

```js
// status → what the header offers
var nx = NEXT[st];
var transitions = nx.map(function (k, i) {
  return { name: ST[k].name, cls: i === nx.length - 1 ? 'btn btn-primary' : 'btn btn-outline', dot: '' };
});
hasTransitions: nx.length > 0, isTerminal: nx.length === 0,
canCancel: ['draft', 'pending', 'paid'].indexOf(st) >= 0,
canRefund: ['paid', 'done'].indexOf(st) >= 0,
```

```js
// timeline: built per status, then reversed so the newest entry is first;
// the rail is hidden on the last (oldest) row only
var history = hist.slice().reverse().map(function (e, i, arr) {
  return { from: e.from ? ST[e.from].name : 'ایجاد',
           fromCls: e.from ? 'badge ' + ST[e.from].cls : 't-sm b',
           to: ST[e.to].name, toCls: 'badge ' + ST[e.to].cls, arrow: 'inline-flex',
           when: e.when, note: e.note, color: colorOf[e.to],
           line: i === arr.length - 1 ? 'none' : 'block' };
});
```

Dot colours (`colorOf`): draft `--text-3`, pending `--warn`, paid `--info`, done `--profit`, cancel `--cancel-bg`, refund `--violet`.

Dialog visibility is state, not routing: `showCancel = dialog === 'cancel' && state === 'ready'`, `showRefund = dialog === 'refund' && state === 'ready'` — so neither dialog can appear over the loading or not-found board. Numbers are formatted with `fa()` / `faT()` and dates with `faD()` from `helpers.js` (Persian tabular digits, `٬` thousands separator, `−` for negatives, Toman with no decimals).

---

## 6. Sample data used

The order is `ORDERS[3]` — INV-000038, the one order written out in full in `../data/sample-data.md` § “INV-000038 in full”, and also the order behind the shell's search result 3 (`00-app-shell.md` §6).

| field | value |
|---|---|
| invoice | `INV-000038` |
| date · time | `۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴` (today in the sample world is ۳۱ شهریور ۱۴۰۵) |
| channel | `وب‌سایت` (`ch-web`) — postage **on**, default shipping charge 180,000, retail prices |
| status | `پرداخت‌شده` (`st-paid`) |
| customer | `نگار ک.` (free-text; the app stores no customer records) |
| packaging kit | `جعبه وینیل` (k2, 140,000) — **not** the channel default `جعبه استاندارد` (95,000), so this order's packaging and postage figures differ from the record-sale screen's default preset |
| transaction fee | 31,000 |

Line items:

| product | cat | qty | unit price | discount | line total | unit cost | line cost |
|---|---|---|---|---|---|---|---|
| وینیل آلبوم اول (p1) | وینیل | 1 | 2,450,000 | — | 2,450,000 | 1,380,000 | 1,380,000 |
| پوستر تور ۱۴۰۴ (p5) | پوستر | 2 | 290,000 | 80,000 («مشتری ثابت») | 500,000 | 95,000 | 190,000 |
| | | **3** | | **80,000** | **2,950,000** | | **1,570,000** |

Customer total:

```
itemsGross    2,450,000 + 2 × 290,000 = 3,030,000
− discount                               −80,000
= itemsNet                             2,950,000
+ shippingCharge                        +180,000
= مبلغ کل                              3,130,000
```

Internal:

```
درآمد سفارش                              3,130,000
− بهای تمام‌شده کالا (1,380,000 + 190,000) −1,570,000
− بسته‌بندی · جعبه وینیل                   −140,000
− پست (تخمینی، store-wide 10,960,000 ÷ 55) −199,273
− کارمزد تراکنش                             −31,000
= سود این سفارش                          1,189,727     ✓ matches ORDERS[3][7]
حاشیه سود = 1,189,727 ÷ 3,130,000 = 38.0% → ۳۸٪
ارسال: 180,000 − (140,000 + 199,273) = −159,273
```

Destructive-action arithmetic for this same order:

```
لغو سفارش : stock +1 p1, +2 p5, +1 k2 ; postage 0 ; loss = fee 31,000 ;
            3,130,000 returned to the customer outside the app ; order leaves شهریور's revenue and profit
ثبت مرجوعی : stock +1 p1, +2 p5 (k2 consumed) ;
            loss = 140,000 + 199,273 + 31,000 = 370,273 ; profit 1,189,727 → −370,273
```

Timeline entries used by each artboard:

| artboard | entries (newest first) |
|---|---|
| `OrderDetail` (paid) | `در انتظار → پرداخت‌شده` ۱۴۰۵/۰۶/۳۰ · ۱۸:۱۰ · `ایجاد → در انتظار` ۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴ |
| `OrderDetail-Draft` | `ایجاد → پیش‌نویس` ۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴ (single entry) |
| `OrderDetail-Completed` | `پرداخت‌شده → تکمیل‌شده` ۱۴۰۵/۰۶/۳۱ · ۰۹:۳۰ · then the two paid-state entries |
| `status: cancel` (no artboard) | `پرداخت‌شده → لغوشده` ۱۴۰۵/۰۶/۳۱ · ۱۱:۰۰ · then the two paid-state entries |
| `status: refund` (no artboard) | `تکمیل‌شده → مرجوعی` ۱۴۰۵/۰۶/۳۱ · ۱۷:۴۵ · then the three completed-state entries |
| `OrderDetailMobile` | the two paid-state entries, re-worded (see §2) |

Cross-checks against the rest of the sample set: the postage estimate `199,273` is the same number used by the dashboard, reports, record-sale and postage screens; `جعبه وینیل` = 140,000 comes from `../data/sample-data.md` § Packaging kits (k2); and the refunded order INV-000035 in the same list confirms the refund formula (`−294,273`).

---

## 7. Open questions for this screen

- **Line items cannot be edited after saving, and nothing says whether that is intentional.** The items table is pure display: no edit affordance, no “add line”, no delete, no price or quantity control, no per-line discount control, and no edit-order action anywhere on the screen. If a mis-keyed quantity has to be fixed after save, the only designed paths are cancel + re-enter, or a stock adjustment — neither of which restates the invoice. Decide whether a saved order is immutable by design, and if not, design the edit flow (and what it does to stock, to the invoice number and to the timeline).
- **The refund reason is a `.select` (a chosen option), the cancel reason is a free-text `input` — and the option list does not exist.** The refund dialog shows `کالا آسیب‌دیده رسید` inside a select button with a chevron, but no list of reasons is designed anywhere, no empty/unchosen state is drawn, and nothing says whether a custom reason can be typed. Cancel, by contrast, takes free text with only a placeholder. Decide whether both should be one pattern, and if the refund reason is a list, who owns that list (settings? hardcoded?) and whether `(اختیاری)` means the select can be left unset.
- **Partial refunds are not designed at all.** The dialog is all-or-nothing: every line returns to stock and the whole `kitCost + postage + fee` becomes the loss. There is no per-line selection, no quantity-returned field and — by the client's own correction — no amount field, so returning one poster out of two, or refunding money while keeping the goods, cannot be recorded. Decide whether partial returns are out of scope for v1 or need their own flow.
- **The actual postage for this order has no recording path.** The internal card offers `ثبت هزینه واقعی پست`, but there is no dialog, field, or artboard behind it, and no state showing an order whose estimate has been replaced by a real figure. Unresolved: does it edit this order's postage only, does it also feed the store-wide estimate, does the profit row then recompute (and does the period's «مغایرت هزینه پست» in `../logic/formulas.md` §7 shrink), and what is shown next to the number afterwards — the chip `تخمینی` presumably has a «واقعی» counterpart that was never drawn. This is the same gap flagged from the record-sale side (`02-record-sale.md` §7).
- **Forward status changes have no confirmation and no side-effect disclosure.** `تغییر وضعیت به:` renders plain buttons that do nothing in the artboard. The two destructive actions get a full effect list; moving `پیش‌نویس → تکمیل‌شده`, which deducts stock for the first time (`../logic/formulas.md` §6), gets nothing — no dialog, no “stock will be deducted” note, no stock-shortage guard (the record-sale form blocks that case; here it is unhandled), and no success feedback or toast.
- **The whole body is static markup for a paid order, so three of the six statuses render contradictory copy.** Only the badge, the transition buttons, the terminal note and the timeline react to `status`; the header total, the items, both money blocks and every string in both dialogs are hardcoded. Consequences to resolve before implementation: in `-Draft` the internal card still shows a full profit of `۱٬۱۸۹٬۷۲۷` even though a draft reserves no stock and is excluded from sales and profit; the cancel dialog always opens with the sentence `این سفارش «پرداخت‌شده» است و هنوز ارسال نشده.` and always claims `۳٬۱۳۰٬۰۰۰` must be returned, which is wrong for a draft or pending order where no money was received; and no artboard exists for `status: cancel` or `status: refund`, so a cancelled or refunded order — the one place a reader would look to confirm the loss figures — was never drawn. A refunded order's internal card in particular (profit `−۳۷۰٬۲۷۳`, the `.neg` treatment, whether the postage and packaging rows stay) is undefined.
- **Mobile is missing the refund path entirely.** There is a full-width `ثبت مرجوعی` button in `عملیات حساس`, but the mobile artboard's `state` prop is `ready | cancel | loading | error` — no refund sheet exists, and the mobile cancel sheet also drops the reports row, the irreversibility warning and the reason label/help that the desktop dialog has. Also absent on mobile: dark, draft and completed variants, the transition list (a single hardcoded `تغییر وضعیت به تکمیل‌شده`), `حاشیه سود`, the shipping-economics line and the `ثبت هزینه واقعی پست` action. Decide what is an intentional mobile reduction and what is an omission.
- **`چاپ فاکتور` is not wired and is offered in every status.** No `href`, no print dialog, no PDF affordance (the record-sale success screen advertises `چاپ فاکتور (PDF)` instead — two different labels for what is presumably one action), and nothing says whether a `پیش‌نویس`, `لغوشده` or `مرجوعی` order should be printable at all, or whether the printout gets a watermark in those statuses. The invoice artboard itself is screen 16.
- **The timeline's actor and provenance are hardcoded.** Every row reads `مدیر فروشگاه`; there is one user in the app and no audit source. Also undefined: pagination or collapsing for a long history, whether a reason typed at cancel/refund time is appended to the note exactly as the samples show it (`مشتری منصرف شد · ۳٬۱۳۰٬۰۰۰ تومان بازپرداخت شد`), whether the money figure in that note is generated or typed, and what an entry looks like when no reason was given. The desktop and mobile timelines also word the same two events differently (`ایجاد → در انتظار` + `ثبت سفارش از فرم ثبت فروش` vs `ثبت با وضعیت در انتظار`), and the mobile wording is the one `../data/sample-data.md` records — pick one.
- **Table column widths are unspecified.** `.tbl` is `width:100%` with automatic layout and no `<colgroup>`, so the five columns are content-sized in the artboard; a long product name will reflow the money columns. `../design-system.md` (tables) fixes only the actions column at 56px, which this table does not have. Agree widths (or `table-layout: fixed`) before building.
- **Dialogs are centred on the 1440 board, not on the content area.** Both are `left:50%` siblings of the sidebar, so on a real page they will sit 132px off-centre relative to `main` unless the implementation re-anchors them. Also undesigned: focus trapping and restore, Esc-to-close, overlay-click behaviour, scroll locking, and the dark theme of both dialogs (`-Dark` is built with `dialog: none`).
- **No permission model.** The two irreversible actions are always available to whoever opens the screen; there is no confirmation beyond the dialog, no re-authentication, no undo window, and no “cancelled by” attribution. Given `00-app-shell.md` §7 records that there is no sign-in screen at all, who may cancel or refund is an open question at the app level.
- The breadcrumb parent is hardcoded to `سفارش‌ها` / `Orders.dc.html`; arriving from the dashboard or from global search still shows that parent, and there is no truncation rule for the title. See `00-app-shell.md` §7 and `../open-questions.md`.
