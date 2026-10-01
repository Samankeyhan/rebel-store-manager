# 00 — پوسته برنامه (App shell)

Route: none — this is the layout that wraps every route · sidebar key: the `active` prop (`home | sale | orders | products | production | purchases | packaging | postage | adjust | expenses | reports | partners | suppliers | settings | none`) · page title in top bar: the `title` prop (default **خانه**)

The shell is three components: a dark navy sidebar pinned to the **right** (RTL inline-start), a white top bar, and the page's `main`. It has no content of its own — the `Shell` artboard fills `main` with a dashed placeholder box so the padding and rhythm can be measured. Everything a screen shows sits inside that `main`; every screen file in this folder describes only that part. The shell carries the two global affordances: the search field in the top bar (with its results popover) and the user menu (which is also where the theme switch lives). On mobile the sidebar is not visible at all — it becomes a 264px drawer opened from the hamburger in a 56px top bar. The three build macros `[[PAGE:active|title]]`, `[[MPAGE:title]]` and `[[ENDPAGE]]` / `[[ENDMPAGE]]` in `build.py` are the canonical way every other artboard assembles this shell, so the padding values they emit (not the ones in `Shell.dc.html`) are the ones to implement — see §7.

Artboards: `Shell.dc.html` (light, sidebar expanded, **search popover open** — `menu` defaults to `search`), `Shell-Collapsed.dc.html` (`collapsed: true`, `menu: user` — 72px rail + user menu + the collapsed tooltip), `Shell-Dark.dc.html` (`theme: dark`, `menu: none`), `ShellMobile.dc.html` (`drawer: true` — drawer open over skeletons), plus the three components on their own: `Sidebar.dc.html` (264 × 900, `active: home`), `Topbar.dc.html` (1176 × 64, `title: خانه`), `MobileBar.dc.html` (390 × 56, `title: خانه`).
Source: `src/Shell.dc.html`, `src/Sidebar.dc.html`, `src/Topbar.dc.html`, `src/ShellMobile.dc.html`, `src/MobileBar.dc.html`.

---

## 1. Layout

### Desktop (1440 × 920 in the artboard; fluid 1024–1600)

```
+-- sidebar 264 (RIGHT / inline-start) --+---------------- content 1176 -----------------+
| brand row          h 72                | top bar  h 64, padding 0 24, gap 16          |
|  logo 36x36 circle + 2 text lines      |  [h1 title .......] [search 380x38] [th][usr]|
+----------------------------------------+-----------------------------------------------+
| nav  flex-grow, gap 2, overflow-y auto |  main                                        |
|  nav-item h 40, radius 8, padding 0 12 |  padding 24 32 40  ·  flex column  ·  gap 20 |
|  group heading .nav-g  padding 14 12 6 |                                              |
|  ... 14 items in 4 groups ...          |  (each screen's own content goes here)       |
|                                        |                                              |
+----------------------------------------+                                              |
| footer  border-top 1, padding 14 0 16  |                                              |
|  wordmark img h 40                     |                                              |
|  collapse button h 40 + kbd "Ctrl B"   |                                              |
+----------------------------------------+-----------------------------------------------+
```

- Sidebar: `width: 264` expanded, `width: 72` collapsed (`.side.is-col`), `padding: 0 12px`, `flex-shrink: 0`, full artboard height. `1440 − 264 = 1176` content; collapsed `1440 − 72 = 1368`.
- Collapsed rail hides `.nav-label`, `.nav-g-t` and `.hide-col`; `.nav-item` becomes `justify-content: center; padding: 0`; each group heading turns into a 1px `--side-line` divider (`.nav-g::after`).
- Active item: `background: --side-active`, weight 700, white icon, plus a 3px `--brand-red` rail at `right: -12px` (bleeds into the 12px sidebar padding, so it sits flush on the screen edge), `top/bottom: 8px`, radius `3px 0 0 3px`.
- Top bar: `height: 64`, `background: --surface`, 1px bottom border, `display: flex; align-items: center; gap: 16px; padding: 0 24px`. Title block grows; the search group is `width: 380; flex-shrink: 0` with a 38px input (shorter than the standard 40px control); then a 40×40 ghost icon button; then the user button.
- Search popover (`.menu`): `position: absolute; left: 246px; top: 58px; width: 470px; padding: 8px`, `role="listbox"`.
- User menu (`.menu`): `position: absolute; left: 24px; top: 58px; width: 250px`, `role="menu"`.
- Collapsed tooltip (`.tip`): `position: absolute; right: 80px; top: 164px` — i.e. 8px clear of the 72px rail, vertically aligned with the third nav item (`سفارش‌ها`, the artboard's active one).

### Element order, desktop (exact)

Sidebar, top to bottom:

1. Brand row — logo image 36×36 circle, then `ربل شاپ` (15px/800, `#ffffff`) and `مدیریت فروشگاه` (11.5px, `--side-muted`) stacked. In the collapsed rail the text block is hidden and the row centres the logo.
2. `خانه` — icon `home` — → `Dashboard.dc.html`
3. `ثبت فروش` — icon `pluscircle` — → `RecordSale.dc.html`
4. `سفارش‌ها` — icon `receipt` — → `Orders.dc.html` — **+ count pill `۳`** pushed to the inline end (11px/700, `--brand-red` fill, white text, radius 999, `padding: 0 7px`, `line-height: 18px`)
5. Group heading `انبار و عملیات`
6. `محصولات و مواد` — icon `package` — → `Products.dc.html`
7. `تولید` — icon `factory` — → `Production.dc.html`
8. `خرید` — icon `cart` — → `Purchases.dc.html`
9. `بسته‌بندی` — icon `box` — → `Packaging.dc.html`
10. `هزینه‌های ارسال` — icon `truck` **mirrored** (`class="flip"`) — → `Postage.dc.html`
11. `تعدیل موجودی` — icon `sliders` — → `Adjustments.dc.html`
12. Group heading `مالی`
13. `هزینه‌ها` — icon `wallet` — → `Expenses.dc.html`
14. `گزارش‌ها` — icon `chart` — → `Reports.dc.html`
15. `شرکا و تقسیم سود` — icon `users` — → `Partners.dc.html`
16. Group heading `اطلاعات پایه`
17. `تأمین‌کنندگان` — icon `building` — → `Suppliers.dc.html`
18. `تنظیمات` — icon `gear` — → `Settings.dc.html`
19. Footer: wordmark image (40px tall, `opacity: .92`, hidden when collapsed), then the collapse button — icon `panel`, label `جمع کردن منو`, and a `.kbd` chip `Ctrl B` pushed to the inline end.

Top bar, inline-start → inline-end (right → left):

1. Page title — `<h1 class="t-h1">` **overridden to `font-size: 18px`**. When the `crumb` prop is set this is replaced by a `.crumb` nav (`aria-label="مسیر"`): parent link in `--text-3`, a 14px `chevL` icon, then the title at 18px. Only the order-detail screen uses the crumb form.
2. Global search — `.ig` group: `search` icon prefix at `right: 12`, `<input type="search">` 38px on `--surface-2`, `.kbd` chip `Ctrl K` as the suffix at `left: 8`.
3. Theme toggle — 40×40 ghost icon button, `moon` icon.
4. User button — ghost, `padding: 0 8px 0 6px; gap: 10px`: avatar (32px circle, `--navy-soft`, letter `م`), then `مدیر فروشگاه` (13/700) over `مالک` (11, `--text-3`), then a 14px `chevD`.

### Mobile (390 × 844)

```
+------------------------- 390 -------------------------+
| mobile bar  h 56, padding 0 6, gap 4                  |
| [menu 44] [logo 26] [h1 17px .......] [search 44][av] |
+-------------------------------------------------------+
| main   padding 14 16 100  ·  flex column  ·  gap 12   |
|                                                       |
+-------------------------------------------------------+

drawer open:
+--------------- overlay ---------------+---- 264 ------+
|                                       | Sidebar       |
|              [x] 44x44 circle         | (full 844,    |
|              at right:276 top:14      |  shadow-lg)   |
+---------------------------------------+---------------+
```

1. Hamburger — 44×44 ghost icon button, `menu` icon 20, `aria-label="باز کردن منو"`. On a sub-page this slot becomes a back link instead (`chevR` 20, `aria-label="بازگشت"`, `href` = the `backHref` prop, default `OrdersMobile.dc.html`).
2. Logo 26×26 circle (`alt=""`, decorative) — **only in the no-back variant**.
3. `<h1 class="t-h1">` **overridden to 17px**, single line, `text-overflow: ellipsis`.
4. Search — 44×44 ghost icon button, `search` 20, `aria-label="جستجو"`.
5. User — 44×44 ghost icon button containing the 32px avatar `م`, `aria-label="منوی کاربر"`.

Drawer: `.overlay` (`position: absolute; inset: 0`, `--overlay`) + the same `Sidebar` component at its full 264px width, pinned `top: 0; right: 0`, height 844, `box-shadow: --shadow-lg`; the close button is a 44×44 circle **outside** the panel at `right: 276px; top: 14px` on `--surface` with `--shadow-lg`, `aria-label="بستن منو"`. All mobile touch targets are 44px.

---

## 2. Copy (verbatim)

### Sidebar

| Slot | String |
|---|---|
| logo `alt` | `لوگوی ربل شاپ` |
| brand name | `ربل شاپ` |
| brand sub | `مدیریت فروشگاه` |
| `nav` `aria-label` | `منوی اصلی` |
| group 1 | `انبار و عملیات` |
| group 2 | `مالی` |
| group 3 | `اطلاعات پایه` |
| wordmark `alt` | `ربل شاپ` |
| collapse button label | `جمع کردن منو` |
| collapse `kbd` | `Ctrl B` |
| collapse `aria-label`, expanded | `جمع کردن منو` |
| collapse `aria-label`, collapsed | `باز کردن منو` |

Nav items — the `title` attribute (native tooltip) is identical to the visible label in every case:

| key | label = `title` |
|---|---|
| `home` | `خانه` |
| `sale` | `ثبت فروش` |
| `orders` | `سفارش‌ها` |
| `products` | `محصولات و مواد` |
| `production` | `تولید` |
| `purchases` | `خرید` |
| `packaging` | `بسته‌بندی` |
| `postage` | `هزینه‌های ارسال` |
| `adjust` | `تعدیل موجودی` |
| `expenses` | `هزینه‌ها` |
| `reports` | `گزارش‌ها` |
| `partners` | `شرکا و تقسیم سود` |
| `suppliers` | `تأمین‌کنندگان` |
| `settings` | `تنظیمات` |

Orders count pill: `۳`

### Top bar

| Slot | String |
|---|---|
| breadcrumb `nav` `aria-label` | `مسیر` |
| default `title` prop | `خانه` |
| search `aria-label` | `جستجوی سراسری` |
| search placeholder | `جستجوی فاکتور، محصول یا مشتری…` |
| search `kbd` | `Ctrl K` |
| theme button `aria-label` | `تغییر پوسته روشن و تیره` |
| user button `aria-label` | `منوی کاربر` |
| avatar | `م` |
| user name | `مدیر فروشگاه` |
| user role | `مالک` |

The `Shell` artboard passes `title="سفارش‌ها"`.

### Search results popover (`Shell.dc.html`, `menu: search`)

| Slot | String |
|---|---|
| popover `aria-label` | `نتایج جستجو` |
| input `value` (typed query) | `وینیل` |
| input `aria-label` | `جستجو` |
| suffix `kbd` | `Esc` |
| group label 1 | `محصولات` |
| result 1 (match emboldened) | `وینیل ` + `<b>آلبوم اول</b>` → renders as `وینیل آلبوم اول` |
| result 1 stock pill | `موجودی ۱۴` |
| result 2 | `وینیل نسخه رنگی` |
| result 2 stock pill (`.stock low`) | `موجودی ۲` |
| group label 2 | `سفارش‌ها` |
| result 3 invoice | `INV-000038` |
| result 3 sub | `نگار ک. · وینیل آلبوم اول، پوستر تور ۱۴۰۴` |
| result 3 badge | `پرداخت‌شده` |
| result 4 invoice | `INV-000030` |
| result 4 sub | `فروشگاه صفحه‌گردان · ۵ وینیل` |
| result 4 badge | `تکمیل‌شده` |
| footer hint 1 | `↑↓` (`.kbd`) + `جابه‌جایی` |
| footer hint 2 | `Enter` (`.kbd`) + `باز کردن` |

### User menu (`Shell.dc.html`, `menu: user` — shown in `Shell-Collapsed`)

| Slot | String |
|---|---|
| menu `aria-label` | `منوی کاربر` |
| avatar (38px here) | `م` |
| name | `مدیر فروشگاه` |
| sub | `کاربر اصلی · تنها کاربر` |
| item 1 | `حساب کاربری` + chip `به‌زودی` |
| item 2 | `کاربران و دسترسی‌ها` + chip `به‌زودی` |
| section label | `پوسته` |
| segmented, option 1 (`on`) | `روشن` |
| segmented, option 2 | `تیره` |
| segmented, option 3 | `خودکار` |
| item 3 (`.mi.danger`) | `خروج` |

### Collapsed tooltip

`سفارش‌ها`

### `main` placeholder (artboard scaffolding only — do not ship)

| Slot | String |
|---|---|
| caption above the box | `۸۷ سفارش در شهریور ۱۴۰۵` |
| outline button | `خروجی Excel` |
| primary button | `ثبت فروش` |
| box title | `ناحیه محتوای صفحه` |
| box sub | `فاصله از لبه‌ها ۳۲ · فاصله بین بخش‌ها ۲۴ · کارت‌ها با گوشه ۱۲` |

### Mobile bar

| Slot | String |
|---|---|
| default `title` prop | `خانه` |
| hamburger `aria-label` | `باز کردن منو` |
| back link `aria-label` | `بازگشت` |
| search `aria-label` | `جستجو` |
| user `aria-label` | `منوی کاربر` |
| avatar | `م` |
| drawer close `aria-label` | `بستن منو` |

`ShellMobile` passes `title="سفارش‌ها"`.

### Loading skeleton (`[[STATES]]` / `[[MSTATES]]` macro, shared by every screen)

The macro's loading board wraps its skeletons in `aria-busy="true"` with `aria-label="در حال بارگذاری"` — that label is shell-level copy and is the same on every screen.

---

## 3. Interactive states designed

| element | states |
|---|---|
| Sidebar | expanded 264 (`Shell`) · collapsed 72 (`Shell-Collapsed`, `.side.is-col`) |
| Nav item | default · hover (`--side-hover`, white text) · active `.on` (`--side-active`, 700, white icon, red rail) · collapsed icon-only (label hidden, centred) |
| Nav group heading | text heading when expanded · 1px divider when collapsed |
| Orders count pill | one state, always visible (hidden with the label in the collapsed rail) |
| Collapse button | default · hover; `aria-label` swaps `جمع کردن منو` ⇄ `باز کردن منو` |
| Collapsed tooltip | shown for the active item only (`.tip`, dark `--text` on `--surface` text) |
| Top-bar search input | resting (`.input` on `--surface-2`, 38px) · `.is-focus` (navy border + 3px `--ring`) shown inside the open popover · popover open |
| Search result row | default · hover (`--surface-2`) · `.hl` (keyboard-highlighted, same `--surface-2`) — first product row is `.hl` in the artboard |
| Theme toggle button | default · hover (ghost) |
| User button | default · hover · menu open |
| User menu item | default · hover (`--surface-2`) · `.mi.danger` (`--loss` text, for `خروج`) |
| Theme segmented | `روشن` `on` · `تیره` · `خودکار` (only the first is drawn selected) |
| Shell theme | light (`Shell`) · dark (`Shell-Dark`) |
| Mobile bar leading slot | hamburger (`back: false`) · back chevron (`back: true`) |
| Mobile drawer | closed (`drawer: false`) · open: overlay + 264 panel + external close FAB |

Focus: `.input:focus` = navy border + `box-shadow: 0 0 0 3px var(--ring)`; see `../design-system.md` §7 for the rules that must survive implementation. No shell state is conveyed by colour alone.

---

## 4. Validation

None on this screen. The shell has one text input (global search) and it has no validation, no minimum length and no error state designed.

---

## 5. Logic

There is no arithmetic in the shell. The whole of its executable logic is prop → class mapping:

```js
// Sidebar
var act = this.props.active || 'home';
var a = {}; ['home','sale','orders','products','production','purchases','packaging','postage',
            'adjust','expenses','reports','partners','suppliers','settings']
            .forEach(function (k) { a[k] = k === act ? 'on' : ''; });
var col = this.props.collapsed === true || this.props.collapsed === 'true';
return { a: a, h: this.props.h || 900, w: col ? 72 : 264,
         colCls: col ? 'is-col' : '', brandJustify: col ? 'center' : 'flex-start',
         toggleLabel: col ? 'باز کردن منو' : 'جمع کردن منو' };
```

```js
// Shell — the collapsed rail drives the content width
var sideW = col ? 72 : 264;
return { ..., sideW: sideW, mainW: 1440 - sideW, searchLeft: 246 };
```

```js
// Topbar — the breadcrumb is present iff a parent label was passed
var crumb = this.props.crumb || '';
return { title: this.props.title || 'خانه', crumb: crumb,
         crumbHref: this.props.crumbHref || 'Orders.dc.html',
         hasCrumb: !!crumb, noCrumb: !crumb, w: this.props.w || 1176 };
```

```js
// MobileBar — leading slot is exclusive: hamburger XOR back
var back = this.props.back === true || this.props.back === 'true';
return { title: ..., back: back, noBack: !back,
         backHref: this.props.backHref || 'OrdersMobile.dc.html' };
```

Exactly one nav key may be `on`; passing `active="none"` leaves every item inactive (used by no artboard, but supported). Theme is a `data-theme` attribute on the outermost `.rs` element and is threaded into every child component as a prop — there is no media query in the artboards, so `خودکار` has no implementation (see §7).

### Page-shell contract every other screen inherits

`build.py` expands `[[PAGE:<activeKey>|<title>]]` to the desktop shell and `[[MPAGE:<title>]]` to the mobile one:

```python
# desktop
'<div class="rs" data-theme="{{theme}}" style="width: 1440px; height: {{h}}px; display: flex;">'
'  <div style="width: 264px; ...">Sidebar active=<activeKey> …</div>'
'  <div style="flex-grow: 1; min-width: 0; …">'
'    Topbar title=<title> w="1176"'
'    <main style="padding: 24px 32px 40px; display: flex; flex-direction: column; gap: 20px;">'

# mobile
'<div class="rs" data-theme="{{theme}}" style="width: 390px; height: {{h}}px;">'
'  MobileBar title=<title>'
'  <main style="padding: 14px 16px 100px; display: flex; flex-direction: column; gap: 12px;">'
```

These two are the values to implement (`24 32 40` / gap 20 desktop; `14 16 100` / gap 12 mobile). `Shell.dc.html` and `ShellMobile.dc.html` use `28px 32px` and `16px` respectively because they are hand-written demos of the chrome, not page instances — see §7.

Nothing in the shell reads from `../logic/formulas.md`; the one number it shows (`۸۷ سفارش در شهریور ۱۴۰۵`) is placeholder text.

---

## 6. Sample data used

All shell sample values are drawn from `../data/sample-data.md`; nothing is computed here.

| Where | Value | Where it comes from |
|---|---|---|
| Sidebar width arithmetic | `1440 − 264 = 1176` (expanded), `1440 − 72 = 1368` (collapsed) | layout only |
| `main` placeholder caption | `۸۷ سفارش در شهریور ۱۴۰۵` | month totals: 87 orders in شهریور ۱۴۰۵ |
| Search result 1 | `وینیل آلبوم اول`, `موجودی ۱۴` | `CATALOG` p1 — stock 14, min 5 → `.stock` (14 > 5, neither low nor out) |
| Search result 2 | `وینیل نسخه رنگی`, `موجودی ۲` | `CATALOG` p2 — stock 2, min 3 → `2 ≤ 3` → `.stock.low` ✓ matches `stockCls()` |
| Search result 3 | `INV-000038` · `نگار ک.` · `پرداخت‌شده` | `ORDERS[3]`; its lines are وینیل آلبوم اول ×1 and پوستر تور ۱۴۰۴ ×2, which is exactly the sub-label `وینیل آلبوم اول، پوستر تور ۱۴۰۴` |
| Search result 4 | `INV-000030` · `فروشگاه صفحه‌گردان` · `تکمیل‌شده` | `ORDERS[11]`; the sub-label `۵ وینیل` is a summary, not a field that exists in the data |
| Sidebar orders pill | `۳` | **not derivable** — the sample month has ۴ orders in `در انتظار`; see §7 |

---

## 7. Open questions for this screen

- **Routes are undefined.** The artboards link to relative filenames (`Dashboard.dc.html`, `RecordSale.dc.html`, …), not URLs. Only `screens/02-record-sale.md` states a route (`/sale`); the rest of the map — including what the shell's root path is — has to be agreed before the sidebar can be built.
- **The `سفارش‌ها` count pill `۳` is unexplained.** It is a hardcoded string with no formula and no tooltip. The sample month has ۴ orders in `در انتظار` and ۲ in `پیش‌نویس`, so it matches nothing in `../data/sample-data.md`. Decide what it counts (pending? needs action? unshipped paid?), whether it is capped (`۹+`), and whether it disappears at zero. No zero state is designed.
- **Two theme controls, no precedence.** The top bar has a `moon` icon button (`تغییر پوسته روشن و تیره`, a 2-state toggle) and the user menu has a 3-way segmented `روشن / تیره / خودکار`. Nothing says which wins, what the icon becomes in dark mode (`sun` exists in the icon set but is unused here), where the choice is persisted, or what `خودکار` follows — there is no `prefers-color-scheme` anywhere in the source.
- **The dark theme of the two overlays was never drawn.** `Shell-Dark` is built with `menu: none`, so neither the search popover nor the user menu has a dark artboard.
- **Global search is a single frozen frame.** Designed: one query (`وینیل`), two groups (`محصولات`, `سفارش‌ها`), four results, one `.hl` row, and the hints `↑↓` / `Enter` / `Esc`. Not designed: the resting/unopened popover, a loading state, a no-results state, a "see all results" row, result counts, grouping for materials/suppliers/expenses, and — although the placeholder promises `مشتری` — any customer results, which cannot exist because the app stores no customer records (see `screens/02-record-sale.md` §7). The keyboard model beyond the three advertised keys is undefined.
- **Collapsed-rail tooltips are one static example.** A single `.tip` is positioned absolutely for the third item. There is no hover/focus tooltip design for the other 13 items, no delay, and no tooltip for the group dividers, which lose their text entirely when collapsed.
- **Collapse behaviour is undefined.** `Ctrl B` is advertised on the button but no shortcut handling exists; whether the collapsed state persists per user, and whether the sidebar auto-collapses below some viewport width (and at which width the desktop shell switches to the mobile drawer at all), is not specified.
- **Two conflicting `main` paddings.** `Shell.dc.html` uses `padding: 28px 32px` with `gap: 20`, and its own placeholder box tells the reader `فاصله از لبه‌ها ۳۲ · فاصله بین بخش‌ها ۲۴`, while the `[[PAGE]]` macro every real screen uses emits `padding: 24px 32px 40px; gap: 20px` (and `Dashboard` overrides that again to `24px 32px 32px; gap: 24px`). Pick one and fix the placeholder copy, which is currently wrong about both numbers.
- **Identity copy disagrees with itself.** The top bar labels the user `مالک`; the user menu labels the same user `کاربر اصلی · تنها کاربر`. Also, the avatar letter `م` is hardcoded — no rule for deriving initials from a name, and no avatar-image case.
- **`حساب کاربری` and `کاربران و دسترسی‌ها` are marked `به‌زودی`** and have no screens. `خروج` has no confirmation dialog and no post-logout destination; there is **no sign-in screen anywhere in the design**, so the authenticated-shell assumption is undocumented.
- **Breadcrumb is under-specified.** `Topbar` supports `crumb` + `crumbHref` (default parent `Orders.dc.html`) but only one screen uses it; there is no truncation rule for a long title, no multi-level crumb, and the mobile bar has a back link instead with a per-screen `backHref` that must be maintained by hand.
- **`.t-h1` is overridden everywhere it is used.** `../design-system.md` §3 defines `.t-h1` as 20/32, but the desktop top bar renders it at 18px and the mobile bar at 17px. Either change the token or record these as intentional per-slot overrides.
- **Mobile navigation has gaps.** There is no bottom tab bar — the drawer is the only way to reach 14 destinations. Not designed: closing by tapping the overlay or swiping, the open/close transition, focus trapping and restore, and what the drawer looks like scrolled (14 items + 3 headings + footer in 844px). The mobile search button and the mobile user button both open nothing that exists — there is no mobile search overlay artboard and no mobile user menu artboard.
- **No notification surface.** A `bell` icon is defined in `build.py`'s icon set but appears in no shell artboard; if alerts (low stock, pending orders) are meant to surface globally, that was not designed.
- **Accessibility scaffolding is incomplete.** `main` has no `aria-label` and there is no skip-to-content link; the `role="listbox"` search popover has no `aria-activedescendant` wiring designed; and the drawer has no `role="dialog"`/`aria-modal` markup (unlike the mobile summary sheet on the record-sale screen, which does).
