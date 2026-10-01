# Design system

Source of truth: `tokens.css` (the file every artboard links). This document explains it and adds the rules that are not expressible in CSS.

---

## 1. Foundations

### Font

- **Vazirmatn**, variable weight 100–900, self-hosted (`assets/Vazirmatn-Variable.woff2`), **not** Google Fonts.
  Reason: Google Fonts is unreliable from Iran, and subset copies may drop the OpenType features we depend on.
- Next.js: `next/font/local` with that file, `display: 'swap'`, and expose it as `--font-vazir`.

```css
@font-face{font-family:'Vazirmatn';src:url('/fonts/Vazirmatn-Variable.woff2') format('woff2');font-weight:100 900;font-style:normal;font-display:swap}
```

### Numerals (do not skip)

Vazirmatn's Persian digits are **proportional by default** — «۱» is less than half the width of «۳» — so money columns will not line up unless tabular figures are switched on. Verified in the font binary; the `tnum` feature exists and covers U+06F0–U+06F9.

```css
html { font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }
```

Applied once at the root, not per-component.

### Direction

- `<html dir="rtl" lang="fa">`. The whole app is RTL; there is no LTR mode.
- Use **logical properties** everywhere: `margin-inline-start`, `padding-inline-end`, `inset-inline-start`, `border-start-start-radius`. Tailwind: `ms-*`, `me-*`, `ps-*`, `pe-*`, `start-*`, `end-*`. No `left/right` except where a thing is pinned to a physical edge on purpose (toast, sheet).
- **Sidebar is at the inline start (right).** Table action columns sit at the inline end (left). Breadcrumbs read right → left.
- **Icon mirroring:** directional icons are mirrored with `transform: scaleX(-1)` (class `.flip` in `tokens.css`): the truck, the "undo / refund" arrow, the logout arrow. Chevrons are *not* mirrored — they are chosen per direction: "next / forward" uses `chevron-left`, "previous / back" uses `chevron-right`, "open submenu" uses `chevron-left`. Calendar: previous month on the right with `chevron-right`, next month on the left with `chevron-left`.
- Number runs stay LTR inside RTL text automatically; invoice codes (`INV-000038`) are wrapped in a `.inv` span with `direction: ltr; unicode-bidi: isolate`.

---

## 2. Color tokens

Every color is a CSS variable on `.rs` (the app root), redefined under `.rs[data-theme="dark"]`. Dark mode is a **designed** palette, not an inversion.

### Brand

| Token | Light | Dark | Use |
|---|---|---|---|
| `--brand-red` | `#F03045` | `#F03045` | logo only, and the active-item marker in the sidebar |
| `--red` | `#D21F37` | `#EC4257` | primary action, active tab underline, selected option ring |
| `--red-hover` | `#B3182D` | `#F25C6E` | primary hover |
| `--red-soft` | `#FDECEE` | `#3B1A22` | selected option background, active nav item in settings list |
| `--ring` | `rgba(210,31,55,.30)` | `rgba(236,66,87,.38)` | focus ring |
| `--navy` / `--heading` | `#26364C` | `#A9B8D6` / `#DCE2F0` | headings, secondary emphasis |
| `--navy-2` | `#33496A` | `#BCC8E2` | input focus border, chart bars |
| `--navy-soft` | `#ECEFF5` | `#1F2740` | secondary button, hero cards |

`#F03045` (logo red) fails contrast for white text (~3.9:1), so the action red is `#D21F37` (~5:1). Keep them separate.

### Surfaces and text

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#F5F5F2` | `#0E1220` |
| `--surface` | `#FFFFFF` | `#161B29` |
| `--surface-2` | `#F2F2EE` | `#1C2232` |
| `--surface-3` | `#E7E7E1` | `#272E41` |
| `--border` | `#E1E1DA` | `#262E43` |
| `--border-strong` | `#C6C6BE` | `#3B445E` |
| `--text` | `#171A21` | `#E8EAF0` |
| `--text-2` | `#454C59` | `#B4BACA` |
| `--text-3` | `#5D6471` | `#959DB0` |

### Semantic

| Token | Light | Dark | Use |
|---|---|---|---|
| `--profit` / `--profit-soft` | `#137A38` / `#E5F4EA` | `#4CC476` / `#12301E` | profit, success, "completed" |
| `--loss` / `--loss-soft` / `--loss-border` | `#B42318` / `#FDECEA` / `#F1B5AE` | `#F4776C` / `#3A1C1A` / `#6B2C27` | loss, blocking error, destructive |
| `--warn` / `--warn-soft` | `#955104` / `#FDF1DC` | `#EBA94D` / `#372811` | soft warning, "pending" |
| `--info` / `--info-soft` | `#1E4FC0` / `#E8F0FE` | `#86A9F8` / `#172549` | info, "paid" |
| `--violet` / `--violet-soft` | `#6A3DBD` / `#F0EAFC` | `#B99BF4` / `#292044` | "refunded", service-type material |
| `--cancel-bg` / `--cancel-fg` | `#474C57` / `#FFFFFF` | `#4B5268` / `#F1F3F8` | "cancelled" badge |

Loss red is deliberately a different red from the action red; loss is always accompanied by a minus sign and a label, never color alone.

### Channels and chart bars

| Token | Light | Dark |
|---|---|---|
| `--ch-web` | `#0E7470` | `#4FC2BB` |
| `--ch-insta` | `#B8266A` | `#EE7FB2` |
| `--ch-wholesale` | `#33496A` | `#A9B8D6` |
| `--ch-inperson` | `#8F520C` | `#E0A55B` |
| `--ch-other` | `#5D6471` | `#959DB0` |
| `--bar-a` / `--bar-b` / `--bar-c` | `#33496A` / `#A7AFBF` / `#6B7384` | `#8FA3CC` / `#4A536B` / `#6F7892` |

Channel colors are for small labels only. **Charts do not use them** — that 5-color set fails color-blind separation. Charts are single-hue (`--bar-a`, or `--profit` for the profit chart) with the category name written next to every bar.

### Sidebar (own scale, same in both themes' structure)

`--side-bg` `#26364C` / `#111628`, `--side-fg` `#D8DEEA` / `#C6CCDD`, `--side-muted` `#98A5BD` / `#7F89A5`, `--side-hover` `#2E4059` / `#1A2137`, `--side-active` `#384C69` / `#232C47`, `--side-line` `#34465F` / `#1E253B`.

---

## 3. Typography scale

| Class | Size / line-height | Weight | Use |
|---|---|---|---|
| `.t-kpi` | 26 / 38 | 700 | KPI numbers |
| `.t-h1` | 20 / 32 | 700 | page title (top bar) |
| `.t-h2` | 16 / 26 | 700 | card title |
| `.t-h3` | 14 / 22 | 700 | section title inside a card |
| `.t-body` | 14 / 23 | 400 | body |
| `.t-sm` | 13 / 21 | 400 | tables, menus, helper text |
| `.t-cap` | 12 / 19 | 400 | labels, timestamps, sub-values |

Colors: `.muted` = `--text-3`, `.muted2` = `--text-2`, `.b` = 700. Headings use `--heading`. Base `font-size: 14px`, `line-height: 1.65`.

---

## 4. Spacing, radius, shadow

- **Spacing** is a 4-multiple scale; the ones actually used: 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32.
  Page padding 32 (desktop) / 16 (mobile); gap between sections 20–24; card padding 16–20; form field gap 14–16; inline gap 6–10.
- **Radius:** card 12, dialog 14, button/input/select 8, small control 6–7, badge 999, sheet 14 on the inner corners only.
- **Shadow:** `--shadow` `0 1px 2px rgba(18,22,38,.06)` (cards), `--shadow-md` `0 4px 14px rgba(18,22,38,.08)` (segmented active), `--shadow-lg` `0 18px 44px rgba(18,22,38,.18), 0 2px 6px rgba(18,22,38,.08)` (menus, dialogs, toasts, sheets). Dark theme uses black-based equivalents.
- **Overlay:** `--overlay` `rgba(14,18,32,.46)` / `rgba(3,5,12,.62)`.
- **Grid:** desktop 1440 = sidebar 264 (collapsed 72) + content 1176; top bar 64; content max-width is not capped — cards stretch. Mobile 390, top bar 56, bottom action bar ~80.
- **Control heights:** desktop button/input 40, small 32, large 48; mobile 44–48 (44 minimum touch target). Table header 40, table row 52.

---

## 5. Components

Class names in `tokens.css` map to shadcn/ui components; keep the mapping when porting.

### Button — `Button`
`.btn` + one of `.btn-primary` (red fill), `.btn-secondary` (navy-soft), `.btn-outline`, `.btn-ghost`, `.btn-link`, `.btn-danger` (loss fill), `.btn-danger-o` (loss outline). Sizes `.btn-sm` 32 / default 40 / `.btn-lg` 48, `.btn-icon` square. States: hover, `:focus-visible` ring (`--ring`), `[disabled]` opacity .45 + `not-allowed`, loading = `.spin` spinner + label «در حال ثبت…».
Rule: **destructive is outline in a page, filled inside a confirmation dialog.** Icon comes before the label (i.e. on the right).

### Input — `Input`
`.input` (40 tall). Variants: `.is-focus` (navy border + ring), `.is-error` (loss border + loss-soft ring), `.is-warn` (warn border — used for "manually overridden"), `[disabled]`/`.is-disabled` (surface-2, text-3).
Money/number inputs add `.input-num` (tabular). A unit suffix («تومان», «عدد», «رول») is rendered inside the field with `.ig > .sfx` at the inline end; the suffix is decoration, never part of the value. A leading icon uses `.ig > .pfx`.
Parsing: accept Persian, Arabic-Indic and Latin digits; strip separators; `٫` and `/` both mean decimal point for quantities. Money fields are integers only.

### Field wrapper
`.field` = label + control + helper/error, gap 6. `.label` 13/600 with optional «(اختیاری)» in `.opt`. `.help` 12 `--text-3`. `.err` 12 `--loss` with an alert icon. `.warn-t` 12 `--warn` with an info icon (soft warning — the non-blocking twin of `.err`).

### Stepper (quantity)
`.stepper` = `−` button, centered input, `+` button in one 40-tall shell. `.is-error` / `.is-warn` mirror the input states. Mobile height 48 with 40-wide buttons.

### Select / combobox — `Select`, `Command`
`.select` is a 40-tall button with a chevron; `.ph` for placeholder text. The open menu is `.menu` with `.mi` rows, `.ml` group labels, `.msep` separators, `.hl` for the highlighted row. The product picker is a combobox: search field on top, rows showing name + category/cost note + price + stock badge; out-of-stock rows stay selectable.

### Option card — `RadioGroup`
`.opt` (+`.on` selected → red border + red-soft background). Title `.o-t`, sub-lines `.o-s`, corner tag `.o-tag` («پیش‌فرض»). Used for sale channel, packaging kit, adjustment type.

### Segmented — `ToggleGroup`
`.seg` with `.on` for the active button. Used for order status, waste/correction, +/−, report presets.

### Tabs — `Tabs`
`.tabs` / `.tab` / `.tab.on` (red underline) with `.cnt` count pill.

### Badges — `Badge`
Status: `.badge` + `.st-draft` (dashed outline), `.st-pending` (amber), `.st-paid` (blue), `.st-done` (green), `.st-cancel` (dark fill), `.st-refund` (violet). Every status badge has a leading dot.
Channel: `.ch` + `.ch-web` / `.ch-insta` / `.ch-wholesale` / `.ch-inperson` / `.ch-other` — outline chip with a colored square; `.ch.ico` swaps the square for the channel icon.
Category: `.chip` (neutral). Stock: `.stock`, `.stock.low` (warn), `.stock.out` (loss). Keyboard: `.kbd`.

### Table — `Table`
`.tbl`: header 40 (`--surface-2`, 12/600 `--text-3`), rows 52, 1px `--border` separators, row hover `--surface-2`, `tfoot` = totals row on `--surface-2`.
Money columns: `.n` (text-align inline-start = right in RTL) + `.num`; unit goes in the header, e.g. «مبلغ کل (تومان)». Invoice number uses `.inv` (monospace, LTR isolate) and links to the detail page. Actions column is last (visual left), width 56.
Row emphasis: `--loss-soft` background for a blocking problem (product with no cost), `--warn-soft` at 55% for "below minimum".

### Alerts — `Alert`
`.alert` + `.alert-err` / `.alert-warn` / `.alert-info` / `.alert-ok`. Structure: icon, `.a-t` title, body, optional action button on the inline end.

### Toast — `Toaster`
`.toast` 360 wide, `--shadow-lg`, icon + title + description + optional action. Position: **bottom inline-start (bottom-left)**. Success auto-dismiss 4s; error stays until dismissed.

### Dialog — `AlertDialog` / `Dialog`
`.dialog` with `.d-h` (icon `.d-ico.danger|.info` + title + subtitle), `.d-b` (body), `.d-f` (footer on `--surface-2`).
Destructive dialogs list consequences as `.effect` rows: icon chip `.e-ico` with `.e-up` (something returns — green), `.e-down` (something is lost — red), `.e-flat` (neutral), then one sentence each. Footer: destructive button first (right), «انصراف» second; initial focus on «انصراف».

### Sheet — `Sheet`
Edit forms (product, material, purchase, supplier) open as a 460–500 wide panel pinned to the inline end (left) with an overlay; header with title + close, body, sticky footer with «ذخیره» / «انصراف» and (where relevant) a destructive action pushed to the far side.

### Tooltip — `Tooltip`
`.tipwrap` > `.tipbtn` (22px info button) + `.tipbox` (300 wide, dark). Used on every P&L line. Keyboard accessible (`:focus-within`), `aria-describedby`.

### Empty / loading / error patterns
- **Empty** `.empty`: rounded icon tile `.e-art`, title `.e-t`, one-sentence explanation `.e-d` that says what the screen is for, and a primary CTA. Filtered-empty variant instead offers «پاک کردن فیلترها».
- **Loading** `.sk`: skeleton blocks that mimic the real layout (KPI row, table rows), shimmer 1.4s. Not a spinner.
- **Error**: same shell as empty with `--loss-soft` icon tile, a sentence naming the cause, «تلاش دوباره», and a monospace error code (`NET_TIMEOUT`, `CATALOG_503`, `ORDERS_500`). Inline banner variant when part of the page still works.

### Calendar (Jalali) — `Calendar` + `Popover`
`.cal` 266 wide. Weekday header ش ی د س چ پ ج (week starts Saturday); Friday column in `--loss`. Day cell 36×36, radius 8. States: `.today` (red inset ring), `.sel` (red fill), range `.s` / `.in` / `.e` (start/middle/end, square middles). Range picker = two months side by side + preset list on the inline start (امروز، دیروز، ۷ روز اخیر، ۳۰ روز اخیر، این ماه، ماه گذشته، سال ۱۴۰۵، بازه دلخواه) + footer «از … تا … (۳۱ روز)» with «انصراف» / «اعمال».
Implementation note: no Gregorian dates are shown anywhere; convert at the data layer.

---

## 6. Formatting rules

### Money
- Toman, **integer only**, never decimals; round at the edge of the calculation.
- Persian digits, thousands separator `٬` (U+066C).
- Inline: «۱۸۰٬۰۰۰ تومان». In tables: number only, unit in the column header. In inputs: number only, «تومان» as a static suffix.
- Profit: green, no plus sign needed. Loss: red, always with a minus: «−۱۱۵٬۰۰۰».
- Unknown / not applicable: «—» (draft, cancelled, product with no cost).

### Quantities
- Products are integers. Materials may be fractional, shown with `٫` (U+066B): «۱٫۵ کیلوگرم», «۰٫۱ رول».

### Dates
- Jalali only. Short «۱۴۰۵/۰۶/۳۱»; with time «۱۴۰۵/۰۶/۳۱ · ۱۳:۴۲»; long «سه‌شنبه، ۳۱ شهریور ۱۴۰۵»; relative «امروز / دیروز» where it helps.
- Months: فروردین، اردیبهشت، خرداد، تیر، مرداد، شهریور، مهر، آبان، آذر، دی، بهمن، اسفند.
- All sample screens are dated **۳۱ شهریور ۱۴۰۵** (Tuesday).

### Percentages
«۲۲٫۶٪» — Persian digits, `٫` decimal, percent sign after the number.

---

## 7. Accessibility rules that must survive implementation

- Real `<button>`, `<a href>`, `<input>`+`<label>` everywhere; no click handlers on `div`/`span`.
- `aria-label` on every icon-only button; `role="radiogroup"`/`radio` on option cards, `role="tab"` on tabs, `role="switch"` + `aria-checked` on switches, `role="alertdialog"` on destructive dialogs, `role="alert"` on blocking errors, `role="status"` on soft warnings and toasts, `aria-busy` on loading regions.
- Visible focus ring on every interactive element.
- Text contrast ≥ 4.5:1 (≥ 3:1 at 24px+). `--text-3` is the lightest allowed text color.
- Color is never the only signal: statuses carry text, profit/loss carry a sign, chart bars carry a value label.
- Touch targets ≥ 44px on mobile.
