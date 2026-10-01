# 08 — بسته‌بندی (Packaging)

Route: `/packaging` · sidebar key `packaging` · page title in top bar: **بسته‌بندی** (mobile bar: **بسته‌بندی**)

A packaging kit is a small bill of materials: a named set of `MATERIALS` rows with a quantity each. Its cost is not typed in — it is **derived from the materials' current unit costs**, which is why a purchase of cardboard silently re-prices every kit that contains it, and why the sale screen can show `بسته‌بندی · جعبه استاندارد` as an internal cost without anyone maintaining a number. The screen is a master/detail: a 340px list of kits on the start side, the selected kit's editor filling the rest. Two derived numbers matter — the kit's cost (Σ material cost × qty) and how many kits the current material stock can still produce, with the limiting material named.

Artboards: `Packaging.dc.html` (default, `kit="k1"` = جعبه استاندارد), `Packaging-VinylBox` (`kit="k2"` = جعبه وینیل), `Packaging-States` (empty · loading · error, three 1440×760 frames), `PackagingMobile`, `PackagingMobile-States` (three 390×844 frames).
Props on `Packaging`: `kit` (`k1 | k2 | k3 | k0`, default `k1`), `state` (`ready | empty | loading | error`), `theme` (`light | dark`), `h` (int, default 900). Selecting a kit in the list is live (`pick()` → `setState({kit})`), so all four kits are reachable in the desktop artboard even though only `k1` and `k2` got their own frames. **No `-Dark` artboard** was generated (`extra_dark=False`).
The kit definitions and both derived numbers are executable JS in the artboard (`KITDEF`, `kitInfo()`); §5 quotes them.

---

## 1. Layout

### Desktop (1440 × 900 default; the states frames are 1440 × 760)

```
┌ sidebar 264 (right) ┬───────────────────── content 1176 ──────────────────────┐
│                     │ top bar 64: «بسته‌بندی»                                  │
│                     ├─────────────────────────────────────────────────────────┤
│                     │ main: padding 24 32 40, flex-column, gap 20             │
│                     │                                                         │
│                     │ [0] hint line (t-sm muted) ........... [＋ کیت جدید]     │
│                     │                                                         │
│                     │ [1] flex, gap 24, align-items: flex-start               │
│                     │ ┌ kit list 340 ─┐ ┌ editor card .grow (fills rest) ───┐ │
│                     │ │ gap 10        │ │ .card-h  16/20  «جعبه استاندارد»  │ │
│                     │ │ [kit card]    │ │    caption + [غیرفعال][ذخیره]     │ │
│                     │ │ [kit card]    │ ├───────────────────────────────────┤ │
│                     │ │ [kit card]    │ │ .card-b 20, gap 14                │ │
│                     │ │ [kit card]    │ │  نام کیت (max-width 360)          │ │
│                     │ │               │ │  column header row (border-bottom)│ │
│                     │ │               │ │  material row × n (40px controls) │ │
│                     │ │               │ │  [＋ افزودن ماده] (sm, start)      │ │
│                     │ │               │ │  3-tile grid (repeat(3), gap 12)  │ │
│                     │ └───────────────┘ └───────────────────────────────────┘ │
└─────────────────────┴─────────────────────────────────────────────────────────┘
```

- `main`: `padding: 24px 32px 40px; gap: 20px` (`[[PAGE:]]` macro).
- Row [1]: `display:flex; gap:24px; align-items:flex-start` — the list does not stretch to the editor's height.
- Kit list: `width:340px; flex-shrink:0; gap:10px`, `aria-label="کیت‌ها"`.
- Editor: `section.card.grow` (`flex-grow:1; min-width:0`), `overflow:hidden`, `aria-labelledby="ke"` → the `h2#ke` in its header. At 1176 − 32 − 32 padding − 340 − 24 gap the editor is ≈ **716px** wide at 1440.

### Kit list card (each of the four)

`button.card` — `text-align:right; padding:14px 16px; display:flex; flex-direction:column; gap:8px; cursor:pointer; font:inherit; color:var(--text)`, with `border-color` and `box-shadow` driven by selection. Content order:

1. Row (`space-between`, full width): kit name (`.b`) · kit cost (`.num.b`).
2. `.t-cap.muted` meta line, full width.
3. Row (`gap:6px`, wrap): one `.ch` channel chip per default channel, then a `.t-cap.muted` fallback caption when there are none.
4. Availability pill (`.stock` / `.stock.low`).

### Editor — field order, exact

1. `.card-h`: `h2#ke.t-h2` = kit name; `.t-cap.muted` = usage caption. On the other side, two buttons: `btn btn-danger-o btn-sm` with the ban icon 14 → `غیرفعال کردن`, and `btn btn-primary btn-sm` → `ذخیره کیت`.
2. **نام کیت** — `.field` `max-width:360px`, `label for="kn"`, `input#kn.input` prefilled with the kit name.
3. Column header row — `grid-template-columns: minmax(0,1fr) 120px 150px 130px 36px; gap:12px; padding-bottom:6px; border-bottom:1px solid var(--border)`, classes `t-cap muted b`: `ماده` · `مقدار در هر کیت` · `بهای واحد فعلی` · `هزینه در کیت` · (empty, the delete column).
4. One material row per kit item, **same 5-column grid**, `align-items:center`:
   1. `button.select` — two stacked lines (`line-height:1.3`): material name (`.b`) and `.t-cap.muted` `موجودی <stock> <unit>` — plus a chevron-down 14.
   2. `.ig` → `input.input.input-num` (`padding-left:56px`) with the per-kit quantity, `.sfx` = the material's unit.
   3. `.num.muted2` — `<current unit cost> / <unit>`.
   4. `.num.b` — the line's cost in the kit.
   5. `button.btn.btn-ghost.btn-icon.btn-sm`, `aria-label="حذف"`, trash icon 16.
5. (Only when the kit has no materials) a `.t-sm.muted` note, `padding:12px 0`.
6. `button.btn.btn-outline.btn-sm`, `align-self:flex-start`, plus icon 14 → `افزودن ماده`.
7. Three tiles — `grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; margin-top:4px`, each radius 10, padding 12:
   1. **هزینه هر کیت** — `t-cap muted b` label, then `.num.b` at 22px + a 12px `تومان`, then a `t-cap muted` footnote. Background `--surface-2`.
   2. **پیش‌فرض کانال‌ها** — label, then the channel chips (or the "no channel" caption) with `margin-top:4px`, then a `t-cap b` link to `Settings.dc.html`. Background `--surface-2`.
   3. **کیت قابل آماده‌سازی** — label, then the count at 22px `.num.b`, then the limiting-material caption. Background **is state-driven**: `--warn-soft` when fewer than 10 kits can be built, otherwise `--surface-2`.

### Mobile (390 × 844)

Top bar 56 (`MobileBar title="بسته‌بندی"`), `main { padding: 14px 16px 100px; gap: 12px }`, plus a fixed bottom bar (`position:absolute; left:0; right:0; bottom:0; padding:12px 16px 20px;` on `--surface`, 1px top border) holding one full-width `btn btn-primary btn-lg` (48px) `کیت جدید` with a plus icon 18.

```
┌──────────── 390 ─────────────┐
│ mobile bar 56 «بسته‌بندی»      │
├──────────────────────────────┤
│ ┌ expanded card (red ring) ─┐│  ← the selected kit, fully expanded
│ │ name ............ ۹۵٬۰۰۰ ││
│ │ [وب‌سایت][اینستاگرام][عمده] ││
│ │ ──── .sep ────            ││
│ │ 4 × material line (sl)    ││
│ │ [⚠ alert-warn, 12px]      ││
│ │ [ویرایش کیت] outline 44   ││
│ └───────────────────────────┘│
│ card 12/14  جعبه وینیل  ۱۴۰٬۰۰۰│  ← the other kits, collapsed
│ card 12/14  پاکت کوچک   ۳۵٬۰۰۰ │
│ card 12/14  بدون بسته‌بندی   ۰  │
├──────────────────────────────┤
│ bottom bar [＋ کیت جدید]      │
└──────────────────────────────┘
```

Mobile order, exact:

1. Expanded card for the selected kit — `padding:14px; gap:8px; border-color:var(--red); box-shadow:0 0 0 1px var(--red)`: name + cost row; channel chips row; `.sep`; one `.sl.t-sm` per material (label `<name> × <qty><unit?>`, value = cost in kit); an `.alert.alert-warn` (`padding:8px 10px; font-size:12px`) with the triangle icon 16 carrying the availability + limiting material; a 44px `btn btn-outline` with the edit icon 16 → `ویرایش کیت`.
2. Three collapsed cards, `padding:12px 14px`, `space-between`, `align-items:center`: bold 13px name + a `t-cap muted` meta line (or, for `بدون بسته‌بندی`, a row of channel chips instead), and the cost on the other side as `num b t-sm`.

Mobile differences: **there is no editor on mobile** — quantities, the material list, the delete buttons, `نام کیت`, `افزودن ماده`, `ذخیره کیت`, `غیرفعال کردن`, the three tiles and the settings link are all desktop-only. `ویرایش کیت` is a button with no designed destination. The collapsed cards omit the availability line entirely, and only the expanded card's cost carries the `تومان` unit.

---

## 2. Copy (verbatim)

### Page chrome

| element | string |
|---|---|
| hint line above the content | `هزینه هر کیت از بهای فعلی مواد محاسبه می‌شود و با هر خرید جدید به‌روز می‌شود.` |
| primary button (desktop + mobile bottom bar) | `کیت جدید` |
| kit list aria-label | `کیت‌ها` |

### Kit list cards (all four, as generated)

| kit | name | cost | meta | channel chips | availability pill |
|---|---|---|---|---|---|
| k1 | `جعبه استاندارد` | `۹۵٬۰۰۰ تومان` | `۴ ماده · ۷۲ سفارش در شهریور` | `وب‌سایت` `اینستاگرام` `عمده‌فروشی` | `فقط ۷ کیت با موجودی فعلی` (`stock low`) |
| k2 | `جعبه وینیل` | `۱۴۰٬۰۰۰ تومان` | `۵ ماده · ۶ سفارش در شهریور (انتخاب دستی)` | — + `پیش‌فرض هیچ کانالی نیست` | `فقط ۷ کیت با موجودی فعلی` (`stock low`) |
| k3 | `پاکت کوچک` | `۳۵٬۰۰۰ تومان` | `۳ ماده · ۳ سفارش در شهریور (انتخاب دستی)` | — + `پیش‌فرض هیچ کانالی نیست` | `۱۵ کیت قابل آماده‌سازی` (`stock`) |
| k0 | `بدون بسته‌بندی` | `۰ تومان` | `بدون مواد` | `حضوری` `سایر` | `نامحدود` (`stock`) |

The two availability phrasings and the two "no default channel" phrasings are produced by these expressions — copy them exactly:

```js
availT: na ? 'نامحدود'
            : (inf.avail < 10 ? 'فقط ' + fa(inf.avail) + ' کیت با موجودی فعلی'
                              : fa(inf.avail) + ' کیت قابل آماده‌سازی')
noDef:  k.chs.length ? '' : 'پیش‌فرض هیچ کانالی نیست'      // in the list
noDef:  k.chs.length ? '' : 'هیچ کانالی'                   // in the editor's tile
```

### Editor header and fields

| element | string |
|---|---|
| title (h2) | the kit name, e.g. `جعبه استاندارد` |
| caption under the title | `استفاده: ` + the kit's usage — see the table below |
| danger button | `غیرفعال کردن` |
| primary button | `ذخیره کیت` |
| field label | `نام کیت` |
| column header 1 | `ماده` |
| column header 2 | `مقدار در هر کیت` |
| column header 3 | `بهای واحد فعلی` |
| column header 4 | `هزینه در کیت` |
| row: stock caption | `موجودی ` + `<qty> <unit>`, e.g. `موجودی ۶۴ عدد` |
| row: delete aria-label | `حذف` |
| add-material button | `افزودن ماده` |
| empty-kit note | `این کیت ماده‌ای ندارد و هزینه آن صفر است — برای فروش حضوری.` |

Usage captions (`sel.use`), per kit:

| kit | caption |
|---|---|
| k1 | `استفاده: ۷۲ سفارش در شهریور` |
| k2 | `استفاده: ۶ سفارش در شهریور (انتخاب دستی)` |
| k3 | `استفاده: ۳ سفارش در شهریور (انتخاب دستی)` |
| k0 | `استفاده: فروش حضوری` |

### Editor — the three tiles

| tile | label | value | footnote |
|---|---|---|---|
| 1 | `هزینه هر کیت` | the number + a small `تومان` | `با بهای فعلی مواد` |
| 2 | `پیش‌فرض کانال‌ها` | channel chips, or `هیچ کانالی` | link `تغییر در تنظیمات` → `Settings.dc.html` |
| 3 | `کیت قابل آماده‌سازی` | the count, or `∞` | `محدودکننده: «<material>» (<stock> <unit>)`, or `بدون محدودیت` |

Limiting captions as generated, per kit:

| kit | tile 3 value | tile 3 footnote |
|---|---|---|
| k1 | `۷` | `محدودکننده: «کاغذ پرکننده» (۱٫۵ کیلوگرم)` (bold) |
| k2 | `۷` | `محدودکننده: «کاغذ پرکننده» (۱٫۵ کیلوگرم)` (bold) |
| k3 | `۱۵` | `محدودکننده: «پاکت حباب‌دار کوچک» (۱۵ عدد)` (muted) |
| k0 | `∞` | `بدون محدودیت` (muted) |

### Editor rows — جعبه استاندارد (k1, the default artboard)

| ماده | موجودی | مقدار در هر کیت | بهای واحد فعلی | هزینه در کیت |
|---|---|---|---|---|
| `کارتن جعبه استاندارد` | `موجودی ۶۴ عدد` | `۱` `عدد` | `۶۰٬۰۰۰ / عدد` | `۶۰٬۰۰۰` |
| `نوار چسب لوگودار` | `موجودی ۲ رول` | `۰٫۱` `رول` | `۱۵۰٬۰۰۰ / رول` | `۱۵٬۰۰۰` |
| `کاغذ پرکننده` | `موجودی ۱٫۵ کیلوگرم` | `۰٫۲` `کیلوگرم` | `۹۰٬۰۰۰ / کیلوگرم` | `۱۸٬۰۰۰` |
| `برچسب آدرس` | `موجودی ۴۰۰ عدد` | `۱` `عدد` | `۲٬۰۰۰ / عدد` | `۲٬۰۰۰` |

Tile 1 value: `۹۵٬۰۰۰` `تومان`.

### Editor rows — جعبه وینیل (k2, artboard `Packaging-VinylBox`)

| ماده | موجودی | مقدار در هر کیت | بهای واحد فعلی | هزینه در کیت |
|---|---|---|---|---|
| `جعبه وینیل` | `موجودی ۸ عدد` | `۱` `عدد` | `۹۵٬۰۰۰ / عدد` | `۹۵٬۰۰۰` |
| `نوار چسب لوگودار` | `موجودی ۲ رول` | `۰٫۱` `رول` | `۱۵۰٬۰۰۰ / رول` | `۱۵٬۰۰۰` |
| `کاغذ پرکننده` | `موجودی ۱٫۵ کیلوگرم` | `۰٫۲` `کیلوگرم` | `۹۰٬۰۰۰ / کیلوگرم` | `۱۸٬۰۰۰` |
| `برچسب آدرس` | `موجودی ۴۰۰ عدد` | `۱` `عدد` | `۲٬۰۰۰ / عدد` | `۲٬۰۰۰` |
| `محافظ گوشه` | `موجودی ۹۰ عدد` | `۱` `عدد` | `۱۰٬۰۰۰ / عدد` | `۱۰٬۰۰۰` |

Tile 1 value: `۱۴۰٬۰۰۰` `تومان`.

### Editor rows — پاکت کوچک (k3, reachable by clicking the kit)

| ماده | موجودی | مقدار در هر کیت | بهای واحد فعلی | هزینه در کیت |
|---|---|---|---|---|
| `پاکت حباب‌دار کوچک` | `موجودی ۱۵ عدد` | `۱` `عدد` | `۲۴٬۰۰۰ / عدد` | `۲۴٬۰۰۰` |
| `برچسب آدرس` | `موجودی ۴۰۰ عدد` | `۱` `عدد` | `۲٬۰۰۰ / عدد` | `۲٬۰۰۰` |
| `نوار چسب لوگودار` | `موجودی ۲ رول` | `۰٫۰۶` `رول` | `۱۵۰٬۰۰۰ / رول` | `۹٬۰۰۰` |

Tile 1 value: `۳۵٬۰۰۰` `تومان`.

### Editor — بدون بسته‌بندی (k0)

No rows; the note `این کیت ماده‌ای ندارد و هزینه آن صفر است — برای فروش حضوری.` replaces them. Tile 1 shows `۰ تومان`, tile 2 the chips `حضوری` `سایر`, tile 3 `∞` with `بدون محدودیت`.

### Desktop empty / loading / error (from `[[STATES:box|…]]`)

**Empty** — `.empty` `padding: 96px 24px`, box icon 28:

- `.e-t` → `هنوز کیتی تعریف نشده`
- `.e-d` → `کیت بسته‌بندی مجموعه‌ای از مواد است (مثلاً کارتن، نوار چسب، پرکننده) که با هر سفارش ارسالی از موجودی کم می‌شود.`
- CTA `button.btn.btn-primary` with plus 16 → `تعریف اولین کیت`

**Loading** — `aria-busy="true"`, `aria-label="در حال بارگذاری"`, one `.sk` 20×180 + **8** `.sk` rows of 40px, radius 10, gap 12.

**Error** — cloud-off icon on `--loss-soft`:

- `.e-t` → `کیت‌های بسته‌بندی بارگذاری نشد`
- `.e-d` → `اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.`
- `button.btn.btn-outline` with the refresh icon 16 → `تلاش دوباره`

### Mobile copy

Expanded card (جعبه استاندارد): title `جعبه استاندارد`, cost `۹۵٬۰۰۰ تومان`, chips `وب‌سایت` `اینستاگرام` `عمده‌فروشی`.

| material line (label) | value |
|---|---|
| `کارتن جعبه استاندارد × ۱` | `۶۰٬۰۰۰` |
| `نوار چسب لوگودار × ۰٫۱ رول` | `۱۵٬۰۰۰` |
| `کاغذ پرکننده × ۰٫۲ کیلوگرم` | `۱۸٬۰۰۰` |
| `برچسب آدرس × ۱` | `۲٬۰۰۰` |

(The unit is printed only for non-`عدد` materials.)

Warning alert: `فقط ۷ کیت با موجودی فعلی — محدودکننده: «کاغذ پرکننده» (۱٫۵ کیلوگرم)`
Button: `ویرایش کیت`

Collapsed cards:

| name | meta / chips | value |
|---|---|---|
| `جعبه وینیل` | `۵ ماده · پیش‌فرض هیچ کانالی نیست` | `۱۴۰٬۰۰۰` |
| `پاکت کوچک` | `۳ ماده · پیش‌فرض هیچ کانالی نیست` | `۳۵٬۰۰۰` |
| `بدون بسته‌بندی` | chips `حضوری` `سایر` | `۰` |

Mobile states (from `[[MSTATES:box|هنوز کیتی تعریف نشده|کیت‌ها با هر سفارش ارسالی از موجودی کم می‌شوند.|تعریف کیت|کیت‌ها]]`), `.empty` padding `48px 20px`, CTA `btn btn-primary btn-lg`:

- empty title `هنوز کیتی تعریف نشده`, body `کیت‌ها با هر سفارش ارسالی از موجودی کم می‌شوند.`, CTA `تعریف کیت`
- error title `کیت‌ها بارگذاری نشد`, body `اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.`, button `تلاش دوباره`
- loading: **5** `.sk` blocks 84px tall after the 20×180 header skeleton

---

## 3. Interactive states designed

| element | states |
|---|---|
| Kit list card | default (`border-color: var(--border)`, `box-shadow: var(--shadow)`) · **selected** (`border-color: var(--red)`, `box-shadow: 0 0 0 1px var(--red)`) · focus-visible ring. Click → `pick()` → `setState({kit})`, which re-renders the whole editor |
| Availability pill (list) | `stock` (≥ 10 kits, or `نامحدود`) · `stock low` (< 10 kits, orange). No `stock out` variant is produced here even at 0 |
| Editor title / caption | follow the selected kit |
| `ذخیره کیت` | enabled only — no dirty/clean distinction, no saving or saved state |
| `غیرفعال کردن` | `btn-danger-o` default + hover (`--loss-soft`); **no confirmation dialog designed** (unlike `Products-Deactivate`) |
| `نام کیت` input | default only; prefilled with the kit name. No error state |
| Material select (per row) | one selected material with its stock caption and a chevron; **no picker popover, no empty row, no placeholder** |
| Material stock caption | plain text; it is **not** colour-coded by low stock (`stockCls` is not used on this screen) even when the material is under its minimum |
| Quantity input (per row) | default only, static in the artboard (`value="{{r.qtyT}}"` with no change handler) — **nothing recomputes as you type** |
| Delete row button | `btn-ghost btn-icon btn-sm` default + hover; no confirm, no undo |
| `افزودن ماده` | default only; adds nothing in the artboard |
| Empty-kit note | shown only when the kit has no materials (`sel.isEmpty`), i.e. `بدون بسته‌بندی` |
| Tile 3 (کیت قابل آماده‌سازی) | two visual states: `--warn-soft` background + **bold** limiting caption when `avail < 10`; `--surface-2` + muted caption otherwise. `∞` for a material-less kit |
| `تغییر در تنظیمات` link | link to `Settings.dc.html`; `.rs a:hover` turns it `--red` |
| Screen | `ready`, `empty`, `loading`, `error` (desktop + mobile). `theme: dark` exists as a prop but no dark artboard was built |
| Kit selection via props | `k1` (default artboard), `k2` (`Packaging-VinylBox`), `k3`, `k0` — the last two only via the live `kit` prop / clicking |
| Mobile | one state: first kit expanded with the warning alert, the rest collapsed. `ویرایش کیت` and `کیت جدید` have no designed target |

Focus ring everywhere: `.rs :focus-visible { box-shadow: 0 0 0 3px var(--ring) }`. The low-availability signal is never colour-only: the pill and the alert both carry text, and the mobile alert adds the triangle icon.

---

## 4. Validation

**No validation was designed on this screen.** There are no error messages, no warnings other than the *informational* low-availability signals, no disabled buttons and no blocking rules in `Packaging.dc.html` or `PackagingMobile.dc.html`. Specifically:

| what is unguarded | consequence in the design as it stands |
|---|---|
| quantity per kit | the input has no change handler, no min, no max and no parser; nothing rejects `۰`, a negative value or a non-number |
| duplicate materials in one kit | `kitInfo` would simply add both lines and take the stricter availability; nothing detects it |
| a kit with no materials | allowed by design — that is exactly `بدون بسته‌بندی`, whose editor shows a note instead of rows and whose cost is `۰` |
| empty `نام کیت` | nothing prevents saving a kit with no name |
| deleting the last material of a kit | no confirm, no message; the kit would silently become a zero-cost kit |
| deactivating a kit that channels default to | `غیرفعال کردن` has no confirmation and no warning, even for `جعبه استاندارد`, which three channels (`وب‌سایت`, `اینستاگرام`, `عمده‌فروشی`) use as their default |
| a material's stock below what one kit needs | produces `۰` in tile 3 and `فقط ۰ کیت با موجودی فعلی` in the pill — **still not an error**, and nothing stops a sale from consuming the kit |

The two low-stock signals, for completeness, are thresholds not rules:

- `avail < 10` → the pill becomes `stock low`, the phrasing switches to `فقط <n> کیت با موجودی فعلی`, tile 3's background becomes `--warn-soft` and its caption becomes bold.
- On mobile the same condition is rendered as an `alert alert-warn`: `فقط ۷ کیت با موجودی فعلی — محدودکننده: «کاغذ پرکننده» (۱٫۵ کیلوگرم)`.

The `10` is a hard-coded literal in the artboard, not a setting. Logged in §7.

---

## 5. Logic

Canonical derivation: `../logic/formulas.md` §5 (kit cost and availability); the consumption side is §1 (order profit) and §6 (stock effects by order status). This section records the screen's own code and the pieces §5 does not cover.

### Kit definitions (`KITDEF`) — the shape of a kit

```js
var KITDEF = [
  { id: 'k1', name: 'جعبه استاندارد', items: [['m9', 1], ['m12', 0.1], ['m13', 0.2], ['m14', 1]],
    chs: ['web', 'insta', 'wholesale'], use: '۷۲ سفارش در شهریور' },
  { id: 'k2', name: 'جعبه وینیل', items: [['m10', 1], ['m12', 0.1], ['m13', 0.2], ['m14', 1], ['m15', 1]],
    chs: [], use: '۶ سفارش در شهریور (انتخاب دستی)' },
  { id: 'k3', name: 'پاکت کوچک', items: [['m11', 1], ['m14', 1], ['m12', 0.06]],
    chs: [], use: '۳ سفارش در شهریور (انتخاب دستی)' },
  { id: 'k0', name: 'بدون بسته‌بندی', items: [], chs: ['inperson', 'other'], use: 'فروش حضوری' }
];
```

A kit is therefore: `id`, `name`, an ordered list of `[materialId, qtyPerKit]` pairs, the channels that default to it, and a usage string. **No cost field** — cost is always derived. Quantities are per **one** kit and may be fractional (`0.1` رول, `0.2` کیلوگرم, `0.06` رول); materials are the side of the app where fractions are allowed.

### Kit cost and availability (`kitInfo`)

```js
function kitInfo(k) {
  var cost = 0, avail = Infinity, limit = null;
  var rows = k.items.map(function (it) {
    var m = mat(it[0]), c = it[1] * m.cost; cost += c;
    var n = Math.floor(m.stock / it[1] + 1e-9); if (n < avail) { avail = n; limit = m; }
    return { name: m.name, qtyT: faQ(it[1]), unit: m.unit, unitCostT: fa(m.cost), costT: fa(c),
             stockT: faQ(m.stock) + ' ' + m.unit };
  });
  return { cost: cost, rows: rows, avail: avail, limit: limit };
}
```

In prose:

```
lineCost   = qtyPerKit × material.currentUnitCost          (the material's cost today, not at any past date)
kitCost    = Σ lineCost
kitsReady  = min over the kit's materials of floor(material.stock ÷ qtyPerKit)
limiting   = the material that produced that minimum
```

Three details worth carrying into the implementation:

- **`+ 1e-9` is a float guard, not a tolerance.** `2 / 0.1` evaluates to `19.999999999999996` in IEEE-754, and `floor` of that is 19, not 20. The epsilon restores the intended 20. Any port must keep an equivalent guard (or hold quantities as integer thousandths — `faQ`/`numQ` already work to 3 decimals).
- **Ties keep the first material.** `if (n < avail)` is strict, so when two materials give the same count the **earliest in the kit's item list** is named as the limiting one. For `جعبه وینیل`, `جعبه وینیل` (m10) gives 8 and `کاغذ پرکننده` (m13) gives 7, so m13 wins on value; but had they tied at 7, m10 would be reported. Deliberate or not, it is the behaviour the artboard shows.
- **A material-less kit is a separate branch, not `avail = Infinity` rendered.** `na = !k.items.length` short-circuits every display: cost `۰ تومان` (a literal string, not `fa(0)` — in the editor tile the same kit shows `fa(0)` = `۰`), availability `نامحدود` in the list and `∞` in the tile, footnote `بدون محدودیت`.

### What consuming a kit does

The consumption itself lives on the sale and order screens; this screen is where the numbers it uses come from.

1. **On sale** — saving an order in any status other than `پیش‌نویس` decrements **one** kit from packaging stock immediately, together with the products (`../logic/formulas.md` §6; screen 02 §5). "One kit" means **every material in the kit, times its per-kit quantity**: saving one order with `جعبه استاندارد` removes `۱ عدد` cardboard, `۰٫۱ رول` tape, `۰٫۲ کیلوگرم` filler and `۱ عدد` label. This is why `کیت قابل آماده‌سازی` is the number that matters operationally, not any single material's stock, and why fractional material stock exists at all.
2. A `پیش‌نویس` order reserves nothing, so it consumes no kit.
3. **The cost is copied onto the order at save time.** `kitCost` here is computed from *current* material costs, so it moves whenever a packaging material is purchased (screen 07 §5) or corrected (`formulas.md` §8); the figure recorded on an existing order never moves with it. That is the same copy-at-save rule as the postage estimate.
4. **Cancel returns the kit; refund does not.** Cancelling an unshipped order returns products **and** the packaging kit to stock; a refund on a paid/completed order returns products only — the kit was used, so `kitCost` becomes part of `refundLoss = kitCost + postageEstimate + transactionFee` (`formulas.md` §6). Nothing on this screen shows those returns, but they are what keeps `kitsReady` honest.
5. **Aggregate check.** The month's `packaging` line in the P&L (7,120,000 over 72 shipped orders, `formulas.md` §7) is the sum of the per-order kit costs recorded at save time — not 72 × today's 95,000 (= 6,840,000), because some orders used `جعبه وینیل` at 140,000 and `پاکت کوچک` at 35,000. Do not reconstruct it from current kit costs.

### Channel defaults

`chs` on each kit is the reverse view of the channel defaults table in `../data/sample-data.md` §Channel defaults: `وب‌سایت`, `اینستاگرام` and `عمده‌فروشی` default to `جعبه استاندارد`; `حضوری` and `سایر` default to `بدون بسته‌بندی`; `جعبه وینیل` and `پاکت کوچک` are manual-only choices at sale time (hence `(انتخاب دستی)` in their usage strings). The mapping is **owned by the settings screen** — this screen only displays it and links out (`تغییر در تنظیمات`).

---

## 6. Sample data used

Materials come from `../data/sample-data.md` §Materials (`MATERIALS` in `helpers.js`). Only packaging-use materials matter here:

| id | نام | واحد | موجودی | بهای واحد | حداقل |
|---|---|---|---|---|---|
| m9 | کارتن جعبه استاندارد | عدد | 64 | 60,000 | 30 |
| m10 | جعبه وینیل | عدد | 8 | 95,000 | 20 |
| m11 | پاکت حباب‌دار کوچک | عدد | 15 | 24,000 | 40 |
| m12 | نوار چسب لوگودار | رول | 2 | 150,000 | 5 |
| m13 | کاغذ پرکننده | کیلوگرم | 1.5 | 90,000 | 3 |
| m14 | برچسب آدرس | عدد | 400 | 2,000 | 100 |
| m15 | محافظ گوشه | عدد | 90 | 10,000 | 30 |

(`m16 کاغذ کرافت` is a packaging material but belongs to no kit.)

### جعبه استاندارد (k1) — cost and availability

```
m9  کارتن جعبه استاندارد   1    × 60,000  =  60,000     floor(64  ÷ 1   ) = 64
m12 نوار چسب لوگودار       0.1  × 150,000 =  15,000     floor(2   ÷ 0.1 ) = 20
m13 کاغذ پرکننده           0.2  × 90,000  =  18,000     floor(1.5 ÷ 0.2 ) =  7   ← min
m14 برچسب آدرس             1    × 2,000   =   2,000     floor(400 ÷ 1   ) = 400
                                   kitCost =  95,000     kitsReady          =  7
```
Limiting material `کاغذ پرکننده` at `۱٫۵ کیلوگرم` → tile 3 on `--warn-soft` (7 < 10), pill `فقط ۷ کیت با موجودی فعلی`.

### جعبه وینیل (k2) — cost and availability

```
m10 جعبه وینیل             1    × 95,000  =  95,000     floor(8   ÷ 1   ) =  8
m12 نوار چسب لوگودار       0.1  × 150,000 =  15,000     floor(2   ÷ 0.1 ) = 20
m13 کاغذ پرکننده           0.2  × 90,000  =  18,000     floor(1.5 ÷ 0.2 ) =  7   ← min
m14 برچسب آدرس             1    × 2,000   =   2,000     floor(400 ÷ 1   ) = 400
m15 محافظ گوشه             1    × 10,000  =  10,000     floor(90  ÷ 1   ) = 90
                                   kitCost = 140,000     kitsReady          =  7
```
Note this kit is limited by filler paper (7) and not by the vinyl boxes themselves (8) — which is the whole point of the limiting-material caption.

### پاکت کوچک (k3) — cost and availability

```
m11 پاکت حباب‌دار کوچک     1    × 24,000  =  24,000     floor(15  ÷ 1   ) = 15   ← min
m14 برچسب آدرس             1    ×  2,000  =   2,000     floor(400 ÷ 1   ) = 400
m12 نوار چسب لوگودار       0.06 × 150,000 =   9,000     floor(2   ÷ 0.06) = 33
                                   kitCost =  35,000     kitsReady          = 15
```
15 ≥ 10, so the pill reads `۱۵ کیت قابل آماده‌سازی`, the tile stays on `--surface-2` and the limiting caption is muted — even though `پاکت حباب‌دار کوچک` is well under its own minimum of 40. The low-stock-vs-low-availability distinction is deliberate here; see §7.

### بدون بسته‌بندی (k0)

No materials. `kitCost = 0`; availability `نامحدود` / `∞`, footnote `بدون محدودیت`; the editor shows the note instead of rows. This is the kit `حضوری` and `سایر` default to, and the reason a walk-in sale carries no packaging cost.

All four figures match `../logic/formulas.md` §5 and the kits table in `../data/sample-data.md` (95,000 / 140,000 / 35,000 / 0; 7 / 7 / 15 / ∞).

### Cross-check against the month

`جعبه استاندارد` was used on 72 orders, `جعبه وینیل` on 6 and `پاکت کوچک` on 3 (from the usage strings). The month's packaging cost in the P&L is 7,120,000 — reconstructable only from the per-order recorded costs, not from `72 × 95,000` (see §5 item 5). Note also that the usage counts (72 + 6 + 3 = 81) exceed the 72 shipped orders in `formulas.md` §7; the usage strings are display copy in the artboard and were not reconciled with the order fixture. Logged in §7.

---

## 7. Open questions for this screen

- **The editor is not wired.** Quantity inputs have no change handler, `افزودن ماده` adds nothing, the delete button removes nothing and `ذخیره کیت` has no dirty/saving/saved state. What a save does to *in-flight* orders and to the kit's history is undecided: the design says cost is always "current", but nothing states whether editing a kit should leave a cost-version trail so past orders remain explainable.
- **No validation at all** (see §4): nothing rejects a zero, negative or unparsable quantity, a duplicate material, a nameless kit, or a kit emptied of every material. Decide the minimum rule set, and specifically whether a quantity of `۰` should be an error or a way to keep a material listed but unused.
- **`غیرفعال کردن` has no confirmation and no consequence design** — even for `جعبه استاندارد`, which three channels default to. Undecided: what happens to those channel defaults, whether an inactive kit remains selectable on the sale screen for historical orders, whether it disappears from this list, and whether there is any way back (no "reactivate" affordance exists).
- **No material picker and no "create kit" flow.** The per-row `.select` is static — no popover, no search, no filtering to `use: 'بسته‌بندی'` materials, no way to add a material that does not exist yet. `کیت جدید` (desktop and mobile) has no designed destination, so the empty state's `تعریف اولین کیت` leads nowhere either.
- **Low availability and low material stock are different signals, and only the first is shown.** The threshold for `stock low` is a hard-coded `avail < 10` in the artboard, unrelated to each material's own `min`. `پاکت کوچک` therefore reads as healthy at 15 kits while `پاکت حباب‌دار کوچک` sits at 15 against a minimum of 40, and the row's `موجودی …` caption is never colour-coded (`stockCls` from `helpers.js` is unused here). Decide whether the threshold is a setting, whether it should derive from the materials' minimums, and whether the row captions should warn.
- **Mobile has no editor.** Quantities, material rows, the three tiles, the settings link, rename, save and deactivate are desktop-only, and `ویرایش کیت` points nowhere. Decide whether mobile gets a real editor (a sheet?) or is explicitly read-only — and, if read-only, why it still offers `کیت جدید`.
- **The usage strings are unsourced copy.** `۷۲ سفارش در شهریور` / `۶` / `۳` are literals in `KITDEF`, they sum to 81 against the 72 shipped orders in `formulas.md` §7, and the period is fixed to شهریور with no control to change it. Decide the real definition (shipped orders in the selected period?) and add the period control, or drop the counts.
- **Tie-breaking on the limiting material is incidental.** `if (n < avail)` names the earliest material in the item list when two tie. Confirm that is intended, or show all materials at the minimum.
- **`۰ تومان` vs `۰`.** The material-less kit prints a literal `۰ تومان` in the list but `fa(0)` = `۰` in the editor tile; mobile prints `۰` with no unit on the collapsed card and `۹۵٬۰۰۰ تومان` with the unit on the expanded one. Settle one rule for the zero case and for when `تومان` is shown.
- **No consumption history or forecast on this screen.** There is no "kits used this month", no link to the orders that consumed them, and no "you can ship N more orders" roll-up across kits — the only forward-looking number is per-kit `کیت قابل آماده‌سازی`. Also undecided: whether the app should ever *assemble* kits in advance as stock (the wording `کیت قابل آماده‌سازی` hints at it) or only ever consume materials at sale time, which is what the logic actually does.
- **No dark artboard** was generated (`extra_dark=False`), although the `theme` prop exists; the red selection ring on the kit card and the `--warn-soft` tile are untested in dark mode.
