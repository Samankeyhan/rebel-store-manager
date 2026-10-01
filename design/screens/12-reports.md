# 12 — گزارش‌ها (Reports)

Route: `/reports` · sidebar key `reports` · page title in top bar: **گزارش‌ها**

Five period reports behind one tab strip, over one date range: the profit & loss statement, product performance, a channel breakdown with two bar charts, a shipping summary, and waste + operating expenses. It is the only **read-only** screen in the app — nothing here writes anything — and it is where the accounting rules the client corrected during design become visible: the P&L is the canonical statement (`../logic/formulas.md` §7), stock corrections are excluded from it entirely, each waste loss is valued at the cost that applied on the day it was recorded, and the single store-wide postage estimate appears as an estimated cost line with a separate **variance** line that reconciles it against what was actually paid to the post office. The date-range toolbar sits outside the tab set and stays on screen in every state, including empty, loading and error; the five tabs are a client-side `view` enum, so exactly one tab body exists in the DOM at a time. Mobile implements **only** the P&L tab.

Artboards:

| file | props | canvas | what it shows |
|---|---|---|---|
| `Reports.dc.html` | `view: pl`, `state: ready`, `theme: light`, `h: 1060` | 1440 × 1060 | the P&L tab; the «مغایرت هزینه پست» tooltip is rendered **open** (`open: i === 8` in `renderVals`) so the tooltip design is visible on the board |
| `Reports-Products.dc.html` | `view: products`, `h: 860` | 1440 × 860 | product-performance table |
| `Reports-Channels.dc.html` | `view: channels`, `h: 960` | 1440 × 960 | two bar charts + the channel table |
| `Reports-Shipping.dc.html` | `view: shipping`, `h: 860` | 1440 × 860 | four KPIs + the shipping table + the break-even note |
| `Reports-Waste.dc.html` | `view: waste`, `h: 800` | 1440 × 800 | waste table + operating-expense bars |
| `Reports-Dark.dc.html` | `theme: dark`, `h: 940` | 1440 × 940 | dark theme, **P&L tab only** |
| `Reports-States.dc.html` | three boards side by side, gap 48 | 4416 × 760 | `state: empty` · `state: loading` · `state: error` |
| `ReportsMobile.dc.html` | `state: ready`, `theme: light`, `h: 900` | 390 × 900 | mobile — P&L only |
| `ReportsMobile-States.dc.html` | three boards side by side | 1266 × 844 | `empty` · `loading` · `error` |

Source: `src/Reports.dc.html`, `src/ReportsMobile.dc.html`. The desktop artboard is interactive — the five tabs are real `setState` buttons, so every tab body can be reached from the default board. There is **no** `ReportsMobile-Dark` artboard and no dark artboard for any tab other than the P&L.

---

## 1. Layout

### Desktop (1440 × 1060 default; fluid 1024–1600)

```
+-- sidebar 264 (RIGHT) --+-------------------- content 1176 --------------------+
|                         | top bar 64: <<گزارش‌ها>>                               |
|                         +-----------------------------------------------------+
|                         | main  padding 24 32 40 · flex column · gap 20       |
|                         |                                                     |
|                         | [0] TOOLBAR - OUTSIDE the isReady guard, so it is   |
|                         |     present in ready / empty / loading / error       |
|                         |   inline-start: [cal <<بازه:>> <range> v] [seg x4] |
|                         |   inline-end:   [Excel] [PDF]                       |
|                         +-----------------------------------------------------+
|                         | [1] TAB STRIP  role=tablist · gap 4 · 1px bottom    |
|                         |     .tab h 40 · padding 0 12 · 13.5/600             |
|                         |     .tab.on = --heading text + 2px --red underline  |
|                         +-----------------------------------------------------+
|                         | [2] the ONE active tab body (five sibling sc-if)    |
+-------------------------+-----------------------------------------------------+
```

`main` is emitted by the `[[PAGE:reports|گزارش‌ها]]` macro — `padding: 24px 32px 40px; gap: 20px` (see `00-app-shell.md` §5). The toolbar row is `display:flex; justify-content:space-between; gap:12px`; its leading group is `flex; gap:10px`, its trailing group `flex; gap:8px`.

### Tab order (exact)

| # | `view` key | tab label (desktop) | body |
|---|---|---|---|
| 1 | `pl` | `سود و زیان` | statement + KPI side column |
| 2 | `products` | `عملکرد محصولات` | one wide table |
| 3 | `channels` | `کانال‌ها` | two charts + one table |
| 4 | `shipping` | `ارسال` | four KPIs + one table + note |
| 5 | `waste` | `ضایعات و هزینه‌ها` | two cards side by side |

The default is `pl`. `aria-selected` is `"true"` on the active tab and `"false"` on the other four; the container is `role="tablist"`, each button `role="tab"`. No `.cnt` count pill is used on any tab.

### Tab 1 — `سود و زیان`

```
flex · gap 24 · align-items flex-start
+-- .card.grow ------------------------------+ +-- side column 320 ------+
| .card-h  padding 16 20 · 1px bottom        | | flex column · gap 16    |
|   [h2 18px]  <<statement title>>           | | +---------------------+ |
|   [caption]  <<order count · unit>>        | | | .card.kpi  سود خالص | |
|                     [caption] <<% legend>> | | |  .t-kpi 26/38 + unit| |
+--------------------------------------------+ | |  .t-cap + .delta    | |
| 13 x .stmt-row                             | | +---------------------+ |
|   grid: minmax(0,1fr) | 180px | 90px       | | | .card.kpi سود ناخالص| |
|   gap 16 · padding 0 20 · min-height 44    | | +---------------------+ |
|   [sign 14px][label][info 22px tip]        | | | .alert.alert-info   | |
|                    [amt right][pct right]  | | |  padding 12         | |
|   .sub   -> --surface-2, weight 700        | | +---------------------+ |
|   .total -> --profit-soft, 800, 16px, h 56 | +-------------------------+
+--------------------------------------------+
```

Column order inside a `.stmt-row`, inline-start → inline-end: **sign glyph** (fixed 14px, centred, 700) · **label** · **tooltip button** (`.tipbtn` 22 × 22, `info` icon 14) · **amount** (`.amt`, 180px, right-aligned, `tnum`, `nowrap`) · **percent** (`.pct`, 90px, right-aligned, 12.5px, `--text-3`). The `.tipbox` is 300px wide, `top: 26px; right: -8px`, dark (`--text` background / `--surface` text), `z-index: 40`.

### Tab 2 — `عملکرد محصولات`

```
+-- .card (overflow hidden) -> table.tbl, 7 columns ---------------------+
| th h 40 · --surface-2 · 12/600 · --text-3 · padding 0 16 · nowrap     |
| td h 52 · 13.5px · padding 0 16 · nowrap · row hover --surface-2      |
| 8 body rows (sorted by profit, descending) + tfoot on --surface-2     |
+-----------------------------------------------------------------------+
p.t-cap.muted  (the product-profit definition note)
```

Column order and widths:

| # | header | align | width | content |
|---|---|---|---|---|
| 1 | `محصول` | start | auto (grows) | `.b` product name |
| 2 | `تعداد فروش` | end (`.n`) | auto | unit count |
| 3 | `درآمد (تومان)` | end (`.n`) | auto | revenue |
| 4 | `بهای تمام‌شده (تومان)` | end (`.n`) | auto | cost, `.muted2` |
| 5 | `سود ↓ (تومان)` | end (`.n`) | auto | `.b.pos` profit |
| 6 | `حاشیه سود` | end (`.n`) | auto | margin |
| 7 | `سهم از سود` | start | **180px** (the only explicit width) | `.meter` 8px tall, `--bar-a` fill, native `title` |

Every other column is auto-width with `white-space: nowrap`, so the real widths are content-driven; only «سهم از سود» is pinned.

### Tab 3 — `کانال‌ها`

```
grid-template-columns: repeat(2, minmax(0,1fr)) · gap 20
+-- .card ------------------------+ +-- .card ------------------------+
| .card-h  [h2] .... [caption]    | | .card-h  [h2] .... [caption]    |
| .card-b  padding 20 · gap 14    | | .card-b  padding 20 · gap 14    |
|   role="img" + aria-label       | |   role="img" + aria-label       |
|   5 rows, each:                 | |   5 rows, each:                 |
|   grid 88px | minmax(0,1fr) | 70| |   grid 88px | minmax(0,1fr) | 70|
|   gap 10 · align center         | |   gap 10 · align center         |
|   track h 22 --surface-2        | |   track h 22 --surface-2        |
|   fill --bar-a, radius 0 4 4 0  | |   fill --profit, radius 0 4 4 0 |
|   value label at the inline end | |   value label at the inline end |
+---------------------------------+ +---------------------------------+
+-- .card (overflow hidden) -> table.tbl, 6 columns ------------------+
| 5 body rows (fixed channel order) + tfoot                          |
+--------------------------------------------------------------------+
```

Chart row column order: **channel name** (88px, `.t-sm`) · **bar track** (grow) · **value in millions** (70px, `.num.t-sm.b`). The bar tracks and fills carry `border-radius: 0 4px 4px 0`, i.e. rounded at the growth end for RTL.

Channel-table column order and widths (no explicit widths anywhere; all auto + `nowrap`):

| # | header | align | content |
|---|---|---|---|
| 1 | `کانال` | start | `.ch.ch-<key>` chip |
| 2 | `سفارش` | end (`.n`) | order count |
| 3 | `درآمد (تومان)` | end (`.n`) | revenue |
| 4 | `سود سفارش‌ها (تومان)` | end (`.n`) | profit, `.b`, `.pos` or `.nil` |
| 5 | `میانگین سفارش (تومان)` | end (`.n`) | revenue ÷ orders |
| 6 | `حاشیه سود` | end (`.n`) | profit ÷ revenue |

### Tab 4 — `ارسال`

```
grid-template-columns: repeat(4, minmax(0,1fr)) · gap 16
+-- .card.kpi --+ +-- .card.kpi --+ +-- .card.kpi --+ +-- .card.kpi --+
| .kpi-l label  | | .kpi-l        | | .kpi-l        | | .kpi-l.neg    |
| .t-kpi 26/38  | | .t-kpi        | | .t-kpi        | | .t-kpi.neg    |
| .t-cap arith  | | .t-cap        | | .t-cap        | | .t-cap.neg.b  |
+---------------+ +---------------+ +---------------+ +---------------+
                                        (4th card: background --loss-soft,
                                         border-color --loss-border)
+-- .card (overflow hidden) -> table.tbl, 7 columns -----------------+
| 3 channel rows (only the channels that ship)                      |
| 1 variance row on --surface-2: colspan=4 label + 2 cells + empty   |
| tfoot                                                             |
+-------------------------------------------------------------------+
.alert.alert-info  (the break-even note)
```

Shipping-table column order (all auto width, `nowrap`):

| # | header | align | content |
|---|---|---|---|
| 1 | `کانال` | start | `.ch` chip |
| 2 | `سفارش ارسالی` | end (`.n`) | shipped orders |
| 3 | `دریافتی ارسال (تومان)` | end (`.n`) | shipping charged to customers |
| 4 | `بسته‌بندی (تومان)` | end (`.n`) | packaging, negative |
| 5 | `پست (تومان)` | end (`.n`) | postage, negative |
| 6 | `نتیجه (تومان)` | end (`.n`) | result, `.b.neg` |
| 7 | `نتیجه / سفارش` | end (`.n`) | result ÷ orders, `.neg` |

The variance row spans columns 1–4 with one `.muted2` label, puts its amount in the «پست (تومان)» column and repeats it in the «نتیجه (تومان)» column, and leaves the last cell empty.

### Tab 5 — `ضایعات و هزینه‌ها`

```
grid-template-columns: repeat(2, minmax(0,1fr)) · gap 20 · align-items start
+-- .card (overflow hidden) ------+ +-- .card ------------------------+
| .card-h [h2] ... [total .neg]   | | .card-h [h2] ... [total .b]     |
| table.tbl, 4 columns, 5 rows    | | .card-b padding 20 · gap 12     |
|  (no tfoot - total is in card-h)| |  5 blocks, each:                |
| p.t-cap.muted padding 12 20     | |   .sl row: label .... value + % |
|  (waste valuation + correction  | |   .meter h 8, --bar-a fill      |
|   exclusion note)               | |   native title on the block     |
+---------------------------------+ +---------------------------------+
```

Waste-table column order (all auto, `nowrap`):

| # | header | align | content |
|---|---|---|---|
| 1 | `کالا` | start | `.b` item name (product **or** material) |
| 2 | `مقدار` | end (`.n`) | quantity + unit |
| 3 | `ارزش (تومان)` | end (`.n`) | value, `.neg`, negative |
| 4 | `دلیل` | start | reason, `.muted2` |

Neither of the two cards in this tab has a footer row; each total lives in the `.card-h` at the inline end.

### Mobile (390 × 900)

```
+---------------------------- 390 ----------------------------+
| mobile bar 56: <<گزارش‌ها>>                                    |
+-------------------------------------------------------------+
| main  padding 14 16 100 · flex column · gap 12              |
|                                                             |
| [0] toolbar row · flex · gap 8                              |
|     [ .select h 44  cal  <range>  v ]  [ 44x44 export btn ] |
|                                                             |
| [1] chip row · flex · gap 6 · overflow hidden               |
|     [badge st-paid h34] [chip][chip][chip][chip]            |
|     - five <span>s, NOT buttons, no role, no aria-selected  |
|                                                             |
| [2] .card (overflow hidden) - 13 rows                       |
|     each row: flex space-between · min-height 44            |
|       padding 0 14 · 1px bottom border                      |
|       [sign 12px][label][info 12px] ....... [amount]        |
|       total  -> --profit-soft, 700, .pos.b                  |
|       sub    -> --surface-2, 700                            |
|       normal -> transparent, 400                            |
|                                                             |
| [3] .t-cap.muted caption with an info icon 14               |
+-------------------------------------------------------------+
```

Mobile is the P&L tab **only** — there is no mobile body for the other four chips. The date button is 44px tall and the export button 44 × 44, so both clear the 44px touch-target rule; the chips are 34px tall, which does **not**. There is no percent column on mobile: each row is label + amount.

---

## 2. Copy (verbatim)

Every string below is copied character-for-character from the artboard source, including ZWNJ (نیم‌فاصله) and the Persian thousands separator `٬`. Percentages use `٪`, decimals use `٫`.

### Page chrome (always visible, in every state)

| slot | string |
|---|---|
| date-range button, muted prefix | `بازه:` |
| date-range button, value (`.b.num`) | `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` |
| preset segment 1 | `این هفته` |
| preset segment 2 (`on`) | `این ماه` |
| preset segment 3 | `ماه گذشته` |
| preset segment 4 | `امسال` |
| export button 1 (`download` icon 16) | `Excel` |
| export button 2 (`printer` icon 16) | `PDF` |

The date-range button is `class="select"` with `aria-haspopup="dialog"` and a `cal` icon 16 + `chevD` 14. The four presets are a `.seg` control; segment 2 is the one drawn `on`.

### Tab labels

| `view` | desktop `.tab` | mobile chip |
|---|---|---|
| `pl` | `سود و زیان` | `سود و زیان` |
| `products` | `عملکرد محصولات` | `محصولات` |
| `channels` | `کانال‌ها` | `کانال‌ها` |
| `shipping` | `ارسال` | `ارسال` |
| `waste` | `ضایعات و هزینه‌ها` | `ضایعات` |

**The two label sets are not the same.** Desktop says «عملکرد محصولات» and «ضایعات و هزینه‌ها» where mobile says «محصولات» and «ضایعات». Tooltip `aria-label` on every P&L tooltip button is built as `توضیح «{{r.label}}»` (the row label is interpolated).

### Tab 1 — `سود و زیان` (P&L statement)

#### Card chrome and side column

| slot | string |
|---|---|
| statement `h2` (`#plt`) | `صورت سود و زیان — شهریور ۱۴۰۵` |
| statement caption | `۸۷ سفارش · مبالغ به تومان` |
| percent-column legend (trailing caption in `.card-h`) | `درصد از جمع درآمد` |
| KPI 1 label | `سود خالص` |
| KPI 1 value (`.t-kpi.num.pos`) | `۴۲٬۰۴۶٬۰۰۰` + unit `تومان` |
| KPI 1 caption | `۲۲٫۶٪ از درآمد ·` `۳٪` `نسبت به مرداد` |
| KPI 2 label | `سود ناخالص` |
| KPI 2 value (`.t-kpi.num`) | `۷۲٬۳۵۶٬۳۴۴` + unit `تومان` |
| KPI 2 caption | `جمع سود سفارش‌ها پیش از هزینه‌های ماه` |
| `.alert.alert-info` body (`info` icon 18) | `پیش‌نویس‌ها در گزارش نمی‌آیند. سفارش‌های لغوشده و مرجوعی از درآمد حذف و زیان آن‌ها جداگانه نمایش داده می‌شود.` |

KPI 1's caption is three fragments in one line: the margin text, then a `.delta.neg` chip containing a `down` icon 12 and `۳٪`, then the comparison text. Rendered together it reads `۲۲٫۶٪ از درآمد · ۳٪ نسبت به مرداد`.

#### The statement, line by line (exact order)

Index table first, then each line in full with its tooltip. `sign` is the glyph in the fixed 14px leading cell; `—` means the cell is rendered empty. `row` is the `.stmt-row` modifier.

| # | sign | label | amount shown | ٪ of `جمع درآمد` | row | amount class |
|---|---|---|---|---|---|---|
| 1 | — | `درآمد فروش اقلام` | `۱۷۴٬۹۰۰٬۰۰۰` | `۹۳٫۸٪` | plain | `—` |
| 2 | — | `درآمد هزینه ارسال` | `۱۱٬۵۲۰٬۰۰۰` | `۶٫۲٪` | plain | `—` |
| 3 | `=` | `جمع درآمد` | `۱۸۶٬۴۲۰٬۰۰۰` | `۱۰۰٪` | `.sub` | `—` |
| 4 | `−` | `بهای تمام‌شده کالای فروخته‌شده` | `۹۱٬۳۳۶٬۰۰۰` | `۴۹٪` | plain | `neg` |
| 5 | `−` | `بسته‌بندی` | `۷٬۱۲۰٬۰۰۰` | `۳٫۸٪` | plain | `neg` |
| 6 | `−` | `هزینه پست (تخمینی)` | `۱۴٬۳۴۷٬۶۵۶` | `۷٫۷٪` | plain | `neg` |
| 7 | `−` | `کارمزد تراکنش` | `۱٬۲۶۰٬۰۰۰` | `۰٫۷٪` | plain | `neg` |
| 8 | `=` | `سود ناخالص` | `۷۲٬۳۵۶٬۳۴۴` | `۳۸٫۸٪` | `.sub` | `—` |
| 9 | `−` | `مغایرت هزینه پست` | `۴۱۲٬۳۴۴` | `۰٫۲٪` | plain | `neg` |
| 10 | `−` | `زیان مرجوعی و لغو` | `۱٬۶۱۰٬۰۰۰` | `۰٫۹٪` | plain | `neg` |
| 11 | `−` | `ضایعات` | `۱٬۲۸۸٬۰۰۰` | `۰٫۷٪` | plain | `neg` |
| 12 | `−` | `هزینه‌های عملیاتی` | `۲۷٬۰۰۰٬۰۰۰` | `۱۴٫۵٪` | plain | `neg` |
| 13 | `=` | `سود خالص` | `۴۲٬۰۴۶٬۰۰۰` | `۲۲٫۶٪` | `.total` | `pos` |

Note that the amount cell always shows the **absolute** value (`fa(Math.abs(...))`); the minus is carried by the `−` sign glyph in the leading cell and by the `.neg` colour, never by the number itself. Only three rows carry a background: the two `.sub` rows `جمع درآمد` (line 3) and `سود ناخالص` (line 8), and the single `.total` row `سود خالص` (line 13). The other ten are plain rows on `--surface`, and the eight cost rows are distinguished only by the `−` glyph and the `.neg` amount colour.

Full lines with verbatim tooltip copy:

**1. درآمد فروش اقلام** — sign `(no sign)` · amount `۱۷۴٬۹۰۰٬۰۰۰` · percent `۹۳٫۸٪` · `.stmt-row`

> جمع مبلغ کالاهای فروخته‌شده پس از کسر تخفیف، بدون هزینه ارسال. پیش‌نویس، لغوشده و مرجوعی حساب نمی‌شوند.

**2. درآمد هزینه ارسال** — sign `(no sign)` · amount `۱۱٬۵۲۰٬۰۰۰` · percent `۶٫۲٪` · `.stmt-row`

> مبلغی که مشتری‌ها بابت ارسال پرداخت کرده‌اند.

**3. جمع درآمد** — sign `=` · amount `۱۸۶٬۴۲۰٬۰۰۰` · percent `۱۰۰٪` · `.stmt-row.sub`

> کل پولی که از مشتری‌ها بابت سفارش‌های این بازه گرفته‌اید.

**4. بهای تمام‌شده کالای فروخته‌شده** — sign `−` · amount `۹۱٬۳۳۶٬۰۰۰` · percent `۴۹٪` · `.stmt-row`

> هزینه ساخت یا خرید همان کالاهایی که فروخته شده، بر اساس میانگین بهای تمام‌شده در لحظه فروش.

**5. بسته‌بندی** — sign `−` · amount `۷٬۱۲۰٬۰۰۰` · percent `۳٫۸٪` · `.stmt-row`

> هزینه کیت‌های بسته‌بندی مصرف‌شده برای سفارش‌ها، با بهای مواد در لحظه ثبت سفارش.

**6. هزینه پست (تخمینی)** — sign `−` · amount `۱۴٬۳۴۷٬۶۵۶` · percent `۷٫۷٪` · `.stmt-row`

> تخمین پستی که روی هر سفارش ثبت شد: جمع پرداختی ÷ جمع سفارش‌ها در ۳ پرداخت اخیر به پست در آن زمان (اکنون ۱۹۹٬۲۷۳ تومان برای هر سفارش).

**7. کارمزد تراکنش** — sign `−` · amount `۱٬۲۶۰٬۰۰۰` · percent `۰٫۷٪` · `.stmt-row`

> کارمزد درگاه پرداخت یا کارت‌خوان که روی سفارش‌ها ثبت شده است.

**8. سود ناخالص** — sign `=` · amount `۷۲٬۳۵۶٬۳۴۴` · percent `۳۸٫۸٪` · `.stmt-row.sub`

> سود خود سفارش‌ها: درآمد منهای همه هزینه‌هایی که مستقیم به سفارش مربوط است.

**9. مغایرت هزینه پست** — sign `−` · amount `۴۱۲٬۳۴۴` · percent `۰٫۲٪` · `.stmt-row`

> پولی که واقعاً به پست دادید (۱۴٬۷۶۰٬۰۰۰) منهای تخمین‌هایی که روی سفارش‌ها ثبت شده بود (۱۴٬۳۴۷٬۶۵۶). مثبت یعنی پست گران‌تر از تخمین بوده است.

**10. زیان مرجوعی و لغو** — sign `−` · amount `۱٬۶۱۰٬۰۰۰` · percent `۰٫۹٪` · `.stmt-row`

> بسته‌بندی، پست و کارمزدی که در سفارش‌های مرجوعی از دست رفت، به‌علاوه کارمزد سفارش‌های پرداخت‌شده‌ای که لغو شدند.

**11. ضایعات** — sign `−` · amount `۱٬۲۸۸٬۰۰۰` · percent `۰٫۷٪` · `.stmt-row`

> ارزش کالا و موادی که خراب یا دور ریخته شده، به بهای تمام‌شده همان روزِ ثبت ضایعات. «اصلاح موجودی» (تصحیح شمارش انبار) در این ردیف و در هیچ ردیف دیگری از سود و زیان نمی‌آید.

**12. هزینه‌های عملیاتی** — sign `−` · amount `۲۷٬۰۰۰٬۰۰۰` · percent `۱۴٫۵٪` · `.stmt-row`

> هزینه‌های جاری فروشگاه مثل اجاره، تبلیغات و اینترنت که به سفارش خاصی مربوط نیستند.

**13. سود خالص** — sign `=` · amount `۴۲٬۰۴۶٬۰۰۰` · percent `۲۲٫۶٪` · `.stmt-row.total`

> آنچه واقعاً برای فروشگاه و شرکا می‌ماند؛ مبنای تقسیم سود.

The tooltip on line 9 (`مغایرت هزینه پست`) is the one rendered open in the `Reports.dc.html` artboard.

### Tab 2 — `عملکرد محصولات`

Column headers, in order: `محصول` · `تعداد فروش` · `درآمد (تومان)` · `بهای تمام‌شده (تومان)` · `سود ↓ (تومان)` · `حاشیه سود` · `سهم از سود`

| `محصول` | `تعداد فروش` | `درآمد (تومان)` | `بهای تمام‌شده (تومان)` | `سود ↓ (تومان)` | `حاشیه سود` | `سهم از سود` (meter) |
|---|---|---|---|---|---|---|
| وینیل آلبوم اول | `۳۲` | `۷۲٬۴۰۰٬۰۰۰` | `۴۴٬۱۶۰٬۰۰۰` | `۲۸٬۲۴۰٬۰۰۰` | `۳۹٪` | `۳۳٫۸٪` at 99% |
| تی‌شرت لوگو مشکی (L) | `۲۶` | `۲۲٬۱۴۰٬۰۰۰` | `۱۰٬۶۶۰٬۰۰۰` | `۱۱٬۴۸۰٬۰۰۰` | `۵۱٫۹٪` | `۱۳٫۷٪` at 40% |
| پوستر تور ۱۴۰۴ | `۶۴` | `۱۶٬۹۰۰٬۰۰۰` | `۶٬۰۸۰٬۰۰۰` | `۱۰٬۸۲۰٬۰۰۰` | `۶۴٪` | `۱۲٫۹٪` at 38% |
| استیکر پک | `۹۲` | `۱۲٬۶۶۰٬۰۰۰` | `۳٬۴۹۶٬۰۰۰` | `۹٬۱۶۴٬۰۰۰` | `۷۲٫۴٪` | `۱۱٪` at 32% |
| وینیل نسخه رنگی | `۶` | `۲۰٬۴۰۰٬۰۰۰` | `۱۲٬۳۰۰٬۰۰۰` | `۸٬۱۰۰٬۰۰۰` | `۳۹٫۷٪` | `۹٫۷٪` at 29% |
| کاست نسخه محدود | `۲۲` | `۱۳٬۱۶۰٬۰۰۰` | `۶٬۳۸۰٬۰۰۰` | `۶٬۷۸۰٬۰۰۰` | `۵۱٫۵٪` | `۸٫۱٪` at 24% |
| آینه لوگو گرد | `۸` | `۹٬۰۰۰٬۰۰۰` | `۴٬۴۸۰٬۰۰۰` | `۴٬۵۲۰٬۰۰۰` | `۵۰٫۲٪` | `۵٫۴٪` at 16% |
| سی‌دی آلبوم اول | `۱۸` | `۸٬۲۴۰٬۰۰۰` | `۳٬۷۸۰٬۰۰۰` | `۴٬۴۶۰٬۰۰۰` | `۵۴٫۱٪` | `۵٫۳٪` at 16% |
| **`جمع`** | `۲۶۸` | `۱۷۴٬۹۰۰٬۰۰۰` | `۹۱٬۳۳۶٬۰۰۰` | `۸۳٬۵۶۴٬۰۰۰` | `۴۷٫۸٪` | — |

The meter carries a native `title` built as `{{p.name}}: {{p.shT}} از سود`. Footer label is `جمع`. The note under the card:

```
سود محصول = درآمد اقلام پس از تخفیف − بهای تمام‌شده. هزینه ارسال، بسته‌بندی و پست در سطح سفارش است و در «سود و زیان» و «ارسال» می‌آید.
```

The header «سود ↓ (تومان)» contains a literal down arrow `↓`; there is no sort control — the order is fixed in code.

### Tab 3 — `کانال‌ها`

| slot | string |
|---|---|
| chart 1 `h2` (`#c1`) | `درآمد به تفکیک کانال` |
| chart 1 caption | `میلیون تومان` |
| chart 1 `role="img"` `aria-label` | `نمودار میله‌ای درآمد کانال‌ها` |
| chart 1 per-bar native `title` | `{{c.name}}: {{c.rT}} تومان · {{c.o}} سفارش` |
| chart 2 `h2` (`#c2`) | `سود سفارش‌ها به تفکیک کانال` |
| chart 2 caption | `میلیون تومان` |
| chart 2 `role="img"` `aria-label` | `نمودار میله‌ای سود کانال‌ها` |
| chart 2 per-bar native `title` | `{{c.name}}: {{c.pT}} تومان سود` |

Channel names come from `helpers.js` `CH` and are the same five strings used everywhere else in the app: `وب‌سایت` · `اینستاگرام` · `عمده‌فروشی` · `حضوری` · `سایر`.

Bar value labels (millions, one decimal, `mil()`):

| channel | revenue chart label | profit chart label |
|---|---|---|
| وب‌سایت | `۶۸٫۲` | `۲۵٫۶` |
| اینستاگرام | `۵۲٫۹` | `۱۸٫۵` |
| عمده‌فروشی | `۴۶٫۳` | `۲۰٫۲` |
| حضوری | `۱۹` | `۸٫۱` |
| سایر | `۰` | `۰` |

Channel table — headers in order: `کانال` · `سفارش` · `درآمد (تومان)` · `سود سفارش‌ها (تومان)` · `میانگین سفارش (تومان)` · `حاشیه سود`

| `کانال` | `سفارش` | `درآمد (تومان)` | `سود سفارش‌ها (تومان)` | `میانگین سفارش (تومان)` | `حاشیه سود` |
|---|---|---|---|---|---|
| وب‌سایت | `۳۴` | `۶۸٬۲۰۰٬۰۰۰` | `۲۵٬۶۲۴٬۷۱۸` | `۲٬۰۰۵٬۸۸۲` | `۳۷٫۶٪` |
| اینستاگرام | `۳۰` | `۵۲٬۹۰۰٬۰۰۰` | `۱۸٬۴۷۱٬۸۱۰` | `۱٬۷۶۳٬۳۳۳` | `۳۴٫۹٪` |
| عمده‌فروشی | `۸` | `۴۶٬۳۰۰٬۰۰۰` | `۲۰٬۱۵۹٬۸۱۶` | `۵٬۷۸۷٬۵۰۰` | `۴۳٫۵٪` |
| حضوری | `۱۵` | `۱۹٬۰۲۰٬۰۰۰` | `۸٬۱۰۰٬۰۰۰` | `۱٬۲۶۸٬۰۰۰` | `۴۲٫۶٪` |
| سایر | `۰` | `۰` | `۰` | `—` | `—` |
| **`جمع`** | `۸۷` | `۱۸۶٬۴۲۰٬۰۰۰` | `۷۲٬۳۵۶٬۳۴۴` | `۲٬۱۴۲٬۷۵۹` | `۳۸٫۸٪` |

`سایر` renders `۰` / `۰` / `۰` and both derived cells fall back to `—`; its profit cell carries `.nil` instead of `.pos`.

### Tab 4 — `ارسال`

| KPI | label | value | caption |
|---|---|---|---|
| 1 | `دریافتی ارسال / سفارش` | `۱۶۰٬۰۰۰` | `۱۱٬۵۲۰٬۰۰۰ ÷ ۷۲ سفارش ارسالی` |
| 2 | `بسته‌بندی / سفارش` | `۹۸٬۸۸۹` | `۷٬۱۲۰٬۰۰۰ ÷ ۷۲` |
| 3 | `پست واقعی / سفارش` | `۲۰۵٬۰۰۰` | `۱۴٬۷۶۰٬۰۰۰ ÷ ۷۲` |
| 4 | `نتیجه / سفارش` | `−۱۴۳٬۸۸۹` | `جمع ماه: −۱۰٬۳۶۰٬۰۰۰` |

KPI 4 is the only one styled as a loss: card `background: var(--loss-soft); border-color: var(--loss-border)`, label `.kpi-l.neg`, value `.t-kpi.num.neg`, caption `.t-cap.neg.b`.

Shipping table — headers in order: `کانال` · `سفارش ارسالی` · `دریافتی ارسال (تومان)` · `بسته‌بندی (تومان)` · `پست (تومان)` · `نتیجه (تومان)` · `نتیجه / سفارش`

| `کانال` | `سفارش ارسالی` | `دریافتی ارسال (تومان)` | `بسته‌بندی (تومان)` | `پست (تومان)` | `نتیجه (تومان)` | `نتیجه / سفارش` |
|---|---|---|---|---|---|---|
| وب‌سایت | `۳۴` | `۶٬۱۲۰٬۰۰۰` | `−۳٬۲۳۰٬۰۰۰` | `−۶٬۷۷۵٬۲۸۲` | `−۳٬۸۸۵٬۲۸۲` | `−۱۱۴٬۲۷۳` |
| اینستاگرام | `۳۰` | `۵٬۴۰۰٬۰۰۰` | `−۲٬۸۵۰٬۰۰۰` | `−۵٬۹۷۸٬۱۹۰` | `−۳٬۴۲۸٬۱۹۰` | `−۱۱۴٬۲۷۳` |
| عمده‌فروشی | `۸` | `۰` | `−۱٬۰۴۰٬۰۰۰` | `−۱٬۵۹۴٬۱۸۴` | `−۲٬۶۳۴٬۱۸۴` | `−۳۲۹٬۲۷۳` |
| مغایرت هزینه پست (پرداخت واقعی ۱۴٬۷۶۰٬۰۰۰ − تخمین‌ها ۱۴٬۳۴۷٬۶۵۶) | | | | `−۴۱۲٬۳۴۴` | `−۴۱۲٬۳۴۴` | |
| **`جمع`** | `۷۲` | `۱۱٬۵۲۰٬۰۰۰` | `−۷٬۱۲۰٬۰۰۰` | `−۱۴٬۷۶۰٬۰۰۰` | `−۱۰٬۳۶۰٬۰۰۰` | `−۱۴۳٬۸۸۹` |

The variance row is verbatim, as one `colspan="4"` `.muted2` cell:

```
مغایرت هزینه پست (پرداخت واقعی ۱۴٬۷۶۰٬۰۰۰ − تخمین‌ها ۱۴٬۳۴۷٬۶۵۶)
```

The `.alert.alert-info` below the table, verbatim (the amount is a `<b class="num">`):

```
برای سربه‌سر شدن ارسال وب‌سایت و اینستاگرام، هزینه ارسال دریافتی باید حدود ۲۹۴٬۲۷۳ تومان باشد. عمده‌فروشی هزینه ارسال نمی‌گیرد، پس کل هزینه آن زیان ارسال است.
```

### Tab 5 — `ضایعات و هزینه‌ها`

| slot | string |
|---|---|
| waste card `h2` (`#w1`) | `ضایعات` |
| waste card total (`.num.b.neg`) | `−۱٬۲۸۸٬۰۰۰` |
| expenses card `h2` (`#w2`) | `هزینه‌های عملیاتی` |
| expenses card total (`.num.b`) | `۲۷٬۰۰۰٬۰۰۰` |

Waste table — headers in order: `کالا` · `مقدار` · `ارزش (تومان)` · `دلیل`

| `کالا` | `مقدار` | `ارزش (تومان)` | `دلیل` |
|---|---|---|---|
| تی‌شرت خام مشکی L | `۲ عدد` | `−۵۲۰٬۰۰۰` | خطای چاپ |
| کاست نسخه محدود | `۱ عدد` | `−۲۹۰٬۰۰۰` | شکستگی قاب |
| پوستر تور ۱۴۰۴ | `۳ عدد` | `−۲۸۵٬۰۰۰` | آب‌دیدگی |
| جعبه وینیل | `۲ عدد` | `−۱۹۰٬۰۰۰` | له‌شدگی |
| کاغذ کرافت | `۰٫۲۵ متر` | `−۳٬۰۰۰` | پارگی |

Note under the waste table (`p.t-cap.muted`, `padding: 12px 20px`) — this is the on-screen statement of two of the client corrections and must ship verbatim:

```
ارزش هر ضایعات با بهای تمام‌شده همان روزِ ثبت محاسبه و ذخیره می‌شود؛ تغییر بعدی بهای تمام‌شده این عددها را عوض نمی‌کند. «اصلاح موجودی» (تصحیح شمارش انبار) در این گزارش و در سود و زیان نمی‌آید — آن را در «تعدیل موجودی» ببینید.
```

Operating-expense rows, in order — each is a `.sl.t-sm` label/value line over an 8px `.meter`, with a native `title`:

| category | amount (`<b>`) | share caption | meter width | native `title` |
|---|---|---|---|---|
| `اجاره انبار` | `۱۲٬۰۰۰٬۰۰۰` | `۴۴٪` | 44% | `اجاره انبار: ۱۲٬۰۰۰٬۰۰۰` |
| `تبلیغات` | `۸٬۵۰۰٬۰۰۰` | `۳۱٪` | 31% | `تبلیغات: ۸٬۵۰۰٬۰۰۰` |
| `اینترنت و نرم‌افزار` | `۲٬۴۰۰٬۰۰۰` | `۹٪` | 9% | `اینترنت و نرم‌افزار: ۲٬۴۰۰٬۰۰۰` |
| `متفرقه` | `۲٬۲۰۰٬۰۰۰` | `۸٪` | 8% | `متفرقه: ۲٬۲۰۰٬۰۰۰` |
| `حمل‌ونقل داخلی` | `۱٬۹۰۰٬۰۰۰` | `۷٪` | 7% | `حمل‌ونقل داخلی: ۱٬۹۰۰٬۰۰۰` |

### Empty / loading / error (the shared `[[STATES]]` macro)

Desktop macro arguments, verbatim: icon `chart`, empty title, empty description, **no CTA** (the fourth argument is empty), error noun `گزارش`.

| state | slot | string |
|---|---|---|
| empty | `.e-t` | `در این بازه داده‌ای وجود ندارد` |
| empty | `.e-d` | `در بازه انتخاب‌شده سفارش، هزینه یا تعدیلی ثبت نشده است. بازه دیگری انتخاب کنید.` |
| empty | CTA | **none** — the macro renders no button |
| loading | `aria-label` | `در حال بارگذاری` |
| error | `.e-t` | `گزارش بارگذاری نشد` |
| error | `.e-d` | `اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.` |
| error | button | `تلاش دوباره` (`refresh` icon 16, `.btn.btn-outline`) |

Desktop padding is `96px 24px`, the empty art is a 56px `.e-art` with a `chart` icon 28, and the error art swaps to `--loss-soft` / `--loss` with a `cloudoff` icon 28. The loading board is one 20 × 180px `.sk` bar plus eight 40px `.sk` rows inside `aria-busy="true"`.

Mobile macro arguments differ in the description only: icon `chart`, title `در این بازه داده‌ای وجود ندارد`, description `بازه دیگری انتخاب کنید.`, no CTA, error noun `گزارش`. Mobile padding is `48px 20px`, the CTA button would be `.btn.btn-primary.btn-lg`, and the loading board is five 84px blocks.

### Mobile-only copy

| slot | string |
|---|---|
| date button (`.select`, h 44) | `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` |
| export icon button `aria-label` | `خروجی` |
| per-row info icon `aria-label` | `توضیح` |
| caption under the card | `روی هر ردیف بزنید تا توضیح آن باز شود.` |

Mobile statement rows use the same order and the same values as desktop, but **one label is shortened**:

| # | desktop label | mobile label |
|---|---|---|
| 4 | `بهای تمام‌شده کالای فروخته‌شده` | `بهای تمام‌شده کالا` |

All other mobile labels are identical to the desktop ones. Amounts are identical; there is no percent column and no tooltip text at all on mobile.

Mobile row values, in order:

| # | label | amount | background | weight |
|---|---|---|---|---|
| 1 | `درآمد فروش اقلام` | `۱۷۴٬۹۰۰٬۰۰۰` | `transparent` | 400 |
| 2 | `درآمد هزینه ارسال` | `۱۱٬۵۲۰٬۰۰۰` | `transparent` | 400 |
| 3 | `جمع درآمد` | `۱۸۶٬۴۲۰٬۰۰۰` | `--surface-2` | 700 |
| 4 | `بهای تمام‌شده کالا` | `۹۱٬۳۳۶٬۰۰۰` | `transparent` | 400 |
| 5 | `بسته‌بندی` | `۷٬۱۲۰٬۰۰۰` | `transparent` | 400 |
| 6 | `هزینه پست (تخمینی)` | `۱۴٬۳۴۷٬۶۵۶` | `transparent` | 400 |
| 7 | `کارمزد تراکنش` | `۱٬۲۶۰٬۰۰۰` | `transparent` | 400 |
| 8 | `سود ناخالص` | `۷۲٬۳۵۶٬۳۴۴` | `--surface-2` | 700 |
| 9 | `مغایرت هزینه پست` | `۴۱۲٬۳۴۴` | `transparent` | 400 |
| 10 | `زیان مرجوعی و لغو` | `۱٬۶۱۰٬۰۰۰` | `transparent` | 400 |
| 11 | `ضایعات` | `۱٬۲۸۸٬۰۰۰` | `transparent` | 400 |
| 12 | `هزینه‌های عملیاتی` | `۲۷٬۰۰۰٬۰۰۰` | `transparent` | 400 |
| 13 | `سود خالص` | `۴۲٬۰۴۶٬۰۰۰` | `--profit-soft` | 700 |

---

## 3. Interactive states designed

| element | states |
|---|---|
| Tab (`.tab`, `role="tab"`) | default (`--text-3`, 600) · `.on` (`--heading` + 2px `--red` bottom border, `aria-selected="true"`) — **no hover and no focus-visible rule exists in the stylesheet for `.tab`** |
| Tab body | exactly one of five, driven by `this.state.view`; switching is instant, no transition, no loading step |
| Date-range button | `.select` resting only; `aria-haspopup="dialog"` but the dialog it opens has no artboard on this screen |
| Preset segment (`.seg`) | segment 2 (`این ماه`) drawn `on` (`--surface` + `--shadow-md`); the other three default. No handler — they are decorative on the board |
| Excel / PDF buttons | `.btn.btn-outline` resting only; no busy, disabled or failure state |
| P&L tooltip | hidden (default) · shown on `.tipwrap:hover` · shown on `.tipwrap:focus-within` · forced open via `.tipbox.open` (line 9 on the artboard). `.tipbtn` has its own hover/focus-visible state (`--heading` text on `--surface-2`) and `cursor: help` |
| `.stmt-row` | plain · `.sub` (`--surface-2`, 700) · `.total` (`--profit-soft`, 800, 16px, 56px tall, no bottom border) |
| Product `.meter` | single resting fill; the only feedback is the native `title` |
| Channel bars | single resting fill per chart (`--bar-a` for revenue, `--profit` for profit); native `title` per row; the whole chart body is one `role="img"` with an `aria-label`, so the bars are not individually exposed |
| Table row | default · `:hover` → `--surface-2` (from `.tbl tbody tr:hover td`). **No row anywhere in this screen is clickable**, so the hover affordance is decoration |
| Screen | ready · empty · loading · error (`Reports-States`) · dark (`Reports-Dark`, P&L tab only) |
| Mobile chips | the first is a `.badge.st-paid`, the other four are `.chip`; all five are `<span>`s with no `role`, no `aria-selected`, no pressed state and no handler |
| Mobile row | plain · `sub` · `total` backgrounds as on desktop; the info icon has an `aria-label` but opens nothing |

The toolbar is rendered **outside** the `isReady` guard, so the date range, the presets and the export buttons stay visible and apparently operable in the empty, loading and error states. Nothing disables them there.

Focus: the screen inherits the global `box-shadow: 0 0 0 3px var(--ring)` focus ring (`../design-system.md` §7). No state on this screen is conveyed by colour alone — every loss carries a `−` glyph and a `.neg` class, and every bar carries a written value.

---

## 4. Validation

**None.** This screen is read-only: it has no inputs, no form, no submit and no destructive action, so there is nothing to validate and no message copy exists.

Two things that *look* like they would need validation, and do not have any designed:

- The date-range button (`aria-haspopup="dialog"`) — the picker itself is not part of this screen's artboards, so its rules (start ≤ end, maximum span, future dates, empty range) are undefined here. See §7.
- The export buttons — no scope, no confirmation and no failure message.

---

## 5. Logic

All arithmetic on this screen is already specified in `../logic/formulas.md`; this section says which formula feeds which cell and what the screen itself computes on top. Nothing is restated.

### View state machine

```js
constructor(p) { this.state = { view: p.view || 'pl' }; }
// names: pl: 'سود و زیان', products: 'عملکرد محصولات', channels: 'کانال‌ها', shipping: 'ارسال', waste: 'ضایعات و هزینه‌ها'
var v = {}; Object.keys(names).forEach(k => v[k] = k === V);
// tabs[] carries { name, on, aria, pick: () => setState({ view: k }) }
```

The `view` prop is only the initial value; after the first click the component owns it. There is no URL, no hash and no persistence, so a reload always returns to `سود و زیان`.

### Formatting helpers (screen-local)

```js
pct(a, b) = round(a / b * 1000) / 10        // one decimal, "٫" separator, "٪" suffix
                                            // a whole number prints with NO decimal: 100 -> «۱۰۰٪»
mil(n)    = round(n / 100000) / 10          // millions, one decimal; 0 -> «۰»
fa(n)     = helpers.js — Persian digits, "٬" thousands, "−" for negatives
```

Every amount on the statement is printed as `fa(Math.abs(value))`, so the **sign is never part of the number**; it is the separate 14px sign cell plus the `.neg` colour. Percentages in the statement are always `pct(Math.abs(value), totalRevenue)` — i.e. every line, cost lines included, is expressed as a positive share of `جمع درآمد`.

### Tab 1 — how each P&L line is derived

The statement is `../logic/formulas.md` §7 rendered literally, in that order. `REV` (`۱۸۶٬۴۲۰٬۰۰۰`) is the percent denominator for every row.

| # | line | derived from |
|---|---|---|
| 1 | `درآمد فروش اقلام` | Σ order `itemsNet` for the period — `formulas.md` §1 (`itemsGross − discountSum`), summed over the orders in range. Drafts, cancellations and refunds are excluded from this line. |
| 2 | `درآمد هزینه ارسال` | Σ order `shippingCharge` for the period — the amount the customer was charged for shipping, `formulas.md` §1. |
| 3 | `جمع درآمد` | Sum of the two lines above. This is the percent denominator for the whole statement. |
| 4 | `بهای تمام‌شده کالای فروخته‌شده` | Σ `productCost` **recorded on each order at sale time** — `formulas.md` §1 and §3 (weighted average). Past orders are never re-costed, so this is a historical figure, not a recomputation at today's costs. |
| 5 | `بسته‌بندی` | Σ `kitCost` recorded on each order — `formulas.md` §5. The kit cost is copied onto the order at sale time. |
| 6 | `هزینه پست (تخمینی)` | Σ of the postage **estimate** that was stamped onto each shipped order — `formulas.md` §2. One store-wide number per order, not a per-channel amount: `72 × 199,273`. |
| 7 | `کارمزد تراکنش` | Σ `transactionFee` entered on each order (`02-record-sale.md` §5; there is no default, it is typed per order). |
| 8 | `سود ناخالص` | The four cost lines subtracted from `جمع درآمد`. This is the same figure as the channel tab's profit total — see §6. |
| 9 | `مغایرت هزینه پست` | See **the postage variance line** below. |
| 10 | `زیان مرجوعی و لغو` | Σ of the loss left behind by cancelled and refunded orders — `formulas.md` §6: for a refund, `kitCost + postageEstimate + transactionFee`; for a cancellation, the transaction fee only. Revenue is removed from the revenue lines, and only the loss appears here. |
| 11 | `ضایعات` | Σ waste value — `formulas.md` §8. **Only ضایعات.** Stock corrections (اصلاح موجودی) are excluded from this line and from every other line of the statement. |
| 12 | `هزینه‌های عملیاتی` | Σ of the period's expense records — `10-expenses` / `data/sample-data.md` § Expenses. These are the costs not attached to any order. |
| 13 | `سود خالص` | The bottom line: `سود ناخالص` minus the four lines above it. It is the figure the partners screen distributes — `formulas.md` §9, `13-partners.md` §5. |

**The postage variance line (`مغایرت هزینه پست`).** The estimate that is stamped onto an order is never rewritten when the estimate changes (`formulas.md` §2), so the statement first charges the **estimates actually recorded** (line 6, `۱۴٬۳۴۷٬۶۵۶`) and then corrects the whole period once:

```
postageVariance = actual paid to the post office − Σ estimates recorded on orders
                = 14,760,000 − 14,347,656 = 412,344      (a cost: postage was dearer than estimated)
```

A positive variance means postage cost more than estimated — which is exactly what the tooltip says: «پولی که واقعاً به پست دادید (۱۴٬۷۶۰٬۰۰۰) منهای تخمین‌هایی که روی سفارش‌ها ثبت شده بود (۱۴٬۳۴۷٬۶۵۶). مثبت یعنی پست گران‌تر از تخمین بوده است.». The same number appears again inside the shipping tab's table as a shaded row; it is the same figure computed the same way, shown twice on two different surfaces.

The postage estimate itself is **one store-wide number**: total paid ÷ total orders over the last 3 postage payments = `۱۹۹٬۲۷۳`, not the mean of the three per-payment rates. On this screen the mandated caption «جمع پرداختی ÷ جمع سفارش‌ها» is carried inside the line-6 tooltip rather than as a standalone caption. See `formulas.md` §2 and `15-settings.md` §5.

The two KPI cards restate two rows of the statement: `سود خالص` = line 13 and `سود ناخالص` = line 8. The `سود خالص` KPI's caption also carries a month-over-month delta which is **not derivable from the sample data** — see §7.

### Tab 2 — product performance

```js
profit  = revenue − cost                    // per product, from the PROD rows
margin  = pct(profit, revenue)
share   = pct(profit, Σ profit)              // the "سهم از سود" caption
width   = round(profit / Σ profit * 100 / 0.34)   // the meter, normalised
sort    = by profit, DESCENDING
```

Product profit here is deliberately **narrower** than order profit: it is item revenue after discount minus product cost, and it excludes shipping, packaging and postage, because those are recorded per order and not per line. That is what the note under the table says, and it is why this tab's profit total (`۸۳٬۵۶۴٬۰۰۰`) is larger than the statement's `سود ناخالص` (`۷۲٬۳۵۶٬۳۴۴`). The `0.34` in the meter formula is a hardcoded normaliser: the top product holds `۳۳٫۸٪` of total profit, so dividing by `0.34` makes its bar ≈100% wide and the rest proportional to it.

The revenue column sums to `۱۷۴٬۹۰۰٬۰۰۰`, which is exactly statement line 1 — the two tabs agree on revenue; and the cost column sums to `۹۱٬۳۳۶٬۰۰۰`, exactly statement line 4.

### Tab 3 — channel breakdown

```js
// per channel, from the CHR rows [key, orders, revenue, orderProfit]
avg    = orders ? fa(revenue / orders) : '—'         // "میانگین سفارش (تومان)"
margin = revenue ? pct(orderProfit, revenue) : '—'  // "حاشیه سود"
rw     = round(revenue / 68,200,000 * 100)          // revenue bar, scaled to the MAX channel
pw     = round(orderProfit / 25,624,718 * 100)      // profit bar,  scaled to the MAX channel
rM/pM  = mil(value)                                  // the printed label, in millions
```

Both bar scales are **relative to the largest channel, not to a total or a fixed axis**, and both maxima (`68,200,000` and `25,624,718`) are hardcoded in `renderVals` rather than computed from the array. So the longest bar in each chart is always 100% wide and the two charts cannot be compared to each other.

The channel `orderProfit` is order-level profit (`formulas.md` §1) aggregated by channel, which is why the five values sum to exactly the statement's `سود ناخالص` — see §6. The per-order lines below the gross-profit subtotal (variance, refund/cancel loss, waste, operating expenses) are **not** attributed to channels anywhere.

**Chart colour is a constraint, not an omission.** The five channel tokens (`--ch-web`, `--ch-insta`, `--ch-wholesale`, `--ch-inperson`, `--ch-other`) were evaluated as a categorical chart palette and failed the separation/contrast check in **both** light and dark, so they are deliberately **not** used as a chart palette anywhere in the product. They are kept for small `.ch` label chips only, where the text carries the meaning. Charts on this screen are therefore **single-hue with a direct value label on every bar**: the revenue chart is all `--bar-a`, the profit chart is all `--profit`, and each row prints its own number at the inline end so no colour lookup is ever needed. See `../design-system.md` § «Channels and chart bars». Any implementation that reintroduces a five-colour categorical palette here is a regression.

### Tab 4 — shipping summary

This tab answers one question: does shipping pay for itself? Per shipped channel,

```
result        = shippingCharged − packaging − actualPostageShare
resultPerOrder= result ÷ shippedOrders
```

and the period is closed out with the same `مغایرت هزینه پست` row as the statement, so the table's total postage column is the **actual** `۱۴٬۷۶۰٬۰۰۰` (estimates `۱۴٬۳۴۷٬۶۵۶` + variance `۴۱۲٬۳۴۴`) while the three channel rows carry only the estimates. The four KPIs are plain per-order averages over the `۷۲` shipped orders: `۱۱٬۵۲۰٬۰۰۰ ÷ ۷۲`, `۷٬۱۲۰٬۰۰۰ ÷ ۷۲`, `۱۴٬۷۶۰٬۰۰۰ ÷ ۷۲`, and their signed sum.

The break-even figure in the alert is the per-order cost of shipping for a web/Instagram order — packaging `۹۵٬۰۰۰` + postage estimate `۱۹۹٬۲۷۳` = `۲۹۴٬۲۷۳` — i.e. `formulas.md` §1 «shipping result» set to zero. Wholesale charges nothing for shipping, so its whole shipping cost is a loss; that is what the second sentence of the alert states.

Only the three channels with postage on appear. «حضوری» and «سایر» ship nothing, so they have no row — there is no zero row and no explanatory line.

### Tab 5 — waste and operating expenses

**Waste valuation.** Each row is `quantity × the item's cost on the day the loss was recorded`. That value is computed once, at the moment the ضایعات record is written, and **stored on the record**. A later purchase or production run that moves the item's weighted-average cost does not change any historical waste row, and nothing on this screen re-prices waste at the item's current cost. The note under the table says this in the product, verbatim, and `formulas.md` §8 is the rule.

**Corrections are excluded.** اصلاح موجودی records — the ± entries that only fix a miscount — never appear in this table and never appear in the P&L, in the `ضایعات` line or in any other line. They only adjust the count and the inventory value (`formulas.md` §8). The sample month contains two of them and neither one is in this report or in the statement: see §6.

**Operating expenses.** The card groups the period's expense records by category, sorted by amount descending, with a share caption and an 8px meter per category. Both the amounts and the share percentages are hardcoded strings in the artboard — there is no `pct()` call in this block — and the total in the `.card-h` is the statement's line 12.

Neither card in this tab is computed from a JS array; unlike tabs 1–3, both the waste rows and the expense rows are literal markup.

---

## 6. Sample data used

Period: `۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` (شهریور ۱۴۰۵), today `۱۴۰۵/۰۶/۳۱`. Full source in `../data/sample-data.md`; everything below is the arithmetic a reviewer needs to check that each tab closes.

### The statement adds up

```
  items revenue        174,900,000
+ shipping revenue        11,520,000
= TOTAL REVENUE          186,420,000      <- percent denominator
− cost of goods sold      91,336,000
− packaging                7,120,000
− postage (estimated)     14,347,656      = 72 shipped orders x 199,273
− transaction fees         1,260,000
= GROSS PROFIT            72,356,344      186,420,000 − 114,063,656
− postage variance           412,344      = 14,760,000 actual − 14,347,656 estimated
− refund & cancel loss     1,610,000
− waste                    1,288,000      ضایعات only; corrections excluded
− operating expenses      27,000,000
= NET PROFIT              42,046,000      72,356,344 − 30,310,344
```

Check: `114,063,656 = 91,336,000 + 7,120,000 + 14,347,656 + 1,260,000`; `186,420,000 − 114,063,656 = 72,356,344` ✓. `30,310,344 = 412,344 + 1,610,000 + 1,288,000 + 27,000,000`; `72,356,344 − 30,310,344 = 42,046,000` ✓. Net margin `42,046,000 ÷ 186,420,000 = 22.6%` → «۲۲٫۶٪», which is both the `.total` row's percent cell and the KPI caption.

Every percent cell, recomputed: `۹۳٫۸٪` درآمد فروش اقلام · `۶٫۲٪` درآمد هزینه ارسال · `۱۰۰٪` جمع درآمد · `۴۹٪` بهای تمام‌شده کالای فروخته‌شده · `۳٫۸٪` بسته‌بندی · `۷٫۷٪` هزینه پست (تخمینی) · `۰٫۷٪` کارمزد تراکنش · `۳۸٫۸٪` سود ناخالص · `۰٫۲٪` مغایرت هزینه پست · `۰٫۹٪` زیان مرجوعی و لغو · `۰٫۷٪` ضایعات · `۱۴٫۵٪` هزینه‌های عملیاتی · `۲۲٫۶٪` سود خالص.

### Tab 2 — products

| product | units | revenue | cost | profit = revenue − cost | margin | share of profit | meter |
|---|---|---|---|---|---|---|---|
| وینیل آلبوم اول | 32 | 72,400,000 | 44,160,000 | **28,240,000** | ۳۹٪ | ۳۳٫۸٪ | 99% |
| تی‌شرت لوگو مشکی (L) | 26 | 22,140,000 | 10,660,000 | **11,480,000** | ۵۱٫۹٪ | ۱۳٫۷٪ | 40% |
| پوستر تور ۱۴۰۴ | 64 | 16,900,000 | 6,080,000 | **10,820,000** | ۶۴٪ | ۱۲٫۹٪ | 38% |
| استیکر پک | 92 | 12,660,000 | 3,496,000 | **9,164,000** | ۷۲٫۴٪ | ۱۱٪ | 32% |
| وینیل نسخه رنگی | 6 | 20,400,000 | 12,300,000 | **8,100,000** | ۳۹٫۷٪ | ۹٫۷٪ | 29% |
| کاست نسخه محدود | 22 | 13,160,000 | 6,380,000 | **6,780,000** | ۵۱٫۵٪ | ۸٫۱٪ | 24% |
| آینه لوگو گرد | 8 | 9,000,000 | 4,480,000 | **4,520,000** | ۵۰٫۲٪ | ۵٫۴٪ | 16% |
| سی‌دی آلبوم اول | 18 | 8,240,000 | 3,780,000 | **4,460,000** | ۵۴٫۱٪ | ۵٫۳٪ | 16% |
| **جمع** | **268** | **174,900,000** | **91,336,000** | **83,564,000** | **۴۷٫۸٪** | ۱۰۰٪ | — |

The five footer figures printed on the board (`۲۶۸`, `۱۷۴٬۹۰۰٬۰۰۰`, `۹۱٬۳۳۶٬۰۰۰`, `۸۳٬۵۶۴٬۰۰۰`, `۴۷٫۸٪`) are hardcoded strings, and all five match the sum of the eight computed rows. Revenue `174,900,000` = statement line 1 ✓; cost `91,336,000` = statement line 4 ✓. Product profit `83,564,000` exceeds gross profit `72,356,344` by `11,207,656 = 7,120,000 packaging + 14,347,656 postage + 1,260,000 fees − 11,520,000 shipping revenue`, which is the order-level layer this tab deliberately omits ✓.

### Tab 3 — channels

| channel | orders | revenue | order profit | avg = revenue ÷ orders | margin | rev bar | profit bar |
|---|---|---|---|---|---|---|---|
| وب‌سایت | 34 | 68,200,000 | 25,624,718 | 2,005,882 | ۳۷٫۶٪ | 100% | 100% |
| اینستاگرام | 30 | 52,900,000 | 18,471,810 | 1,763,333 | ۳۴٫۹٪ | 78% | 72% |
| عمده‌فروشی | 8 | 46,300,000 | 20,159,816 | 5,787,500 | ۴۳٫۵٪ | 68% | 79% |
| حضوری | 15 | 19,020,000 | 8,100,000 | 1,268,000 | ۴۲٫۶٪ | 28% | 32% |
| سایر | 0 | 0 | 0 | — | — | 0% | 0% |
| **جمع** | **87** | **186,420,000** | **72,356,344** | **2,142,759** | **۳۸٫۸٪** | | |

Checks: orders `34+30+8+15+0 = 87` ✓. Revenue `68,200,000 + 52,900,000 + 46,300,000 + 19,020,000 = 186,420,000` = statement line 3 ✓. Profit `25,624,718 + 18,471,810 + 20,159,816 + 8,100,000 = 72,356,344` = statement line 8, **exactly** ✓. Footer average `186,420,000 ÷ 87 = 2,142,758.6 → 2,142,759` ✓ (the footer is hardcoded and matches). Bar labels in millions: `68.2 / 52.9 / 46.3 / 19 / ۰` and `25.6 / 18.5 / 20.2 / 8.1 / ۰` — note «حضوری» prints `۱۹`, not `۱۹٫۰`, because `mil()` drops a trailing `.0`.

### Tab 4 — shipping

```
web        34 orders : 34 x 180,000 = 6,120,000 charged
                       34 x  95,000 = 3,230,000 packaging
                       34 x 199,273 = 6,775,282 postage (estimate)
                       result 6,120,000 − 3,230,000 − 6,775,282 = −3,885,282   (−114,273 / order)
instagram  30 orders : 30 x 180,000 = 5,400,000
                       30 x  95,000 = 2,850,000
                       30 x 199,273 = 5,978,190
                       result 5,400,000 − 2,850,000 − 5,978,190 = −3,428,190   (−114,273 / order)
wholesale   8 orders :  8 x       0 =         0   (wholesale charges nothing)
                        8 x 130,000 = 1,040,000   <- 130,000, NOT the 95,000 kit; see §7
                        8 x 199,273 = 1,594,184
                       result 0 − 1,040,000 − 1,594,184 = −2,634,184           (−329,273 / order)
variance                                −412,344
---------------------------------------------------------------------------------------------
total      72 orders   11,520,000 charged
                       −7,120,000 packaging      (3,230,000 + 2,850,000 + 1,040,000)
                      −14,760,000 postage        (6,775,282 + 5,978,190 + 1,594,184 = 14,347,656
                                                  + 412,344 variance = 14,760,000 actual)
                      −10,360,000 result         (−3,885,282 −3,428,190 −2,634,184 −412,344)
                         −143,889 per order      (−10,360,000 ÷ 72)
```

KPI checks: `11,520,000 ÷ 72 = 160,000` ✓ · `7,120,000 ÷ 72 = 98,888.9 → 98,889` ✓ · `14,760,000 ÷ 72 = 205,000` ✓ · `160,000 − 98,889 − 205,000 = −143,889` ✓ (and `−10,360,000 ÷ 72 = −143,888.9` rounds to the same). Break-even `95,000 + 199,273 = 294,273` ✓; a web order charging `180,000` is therefore `−114,273` short, matching both its row and `formulas.md` §1.

### Tab 5 — waste and expenses

| item | qty | unit cost on the day recorded | value |
|---|---|---|---|
| تی‌شرت خام مشکی L | 2 عدد | 260,000 (material m5) | 520,000 |
| کاست نسخه محدود | 1 عدد | 290,000 (product p3) | 290,000 |
| پوستر تور ۱۴۰۴ | 3 عدد | 95,000 (product p5) | 285,000 |
| جعبه وینیل | 2 عدد | 95,000 (material m10) | 190,000 |
| کاغذ کرافت | 0.25 متر | 12,000 (material m16) | 3,000 |
| **total** | | | **1,288,000** |

`520,000 + 290,000 + 285,000 + 190,000 + 3,000 = 1,288,000` ✓ = the card header `−۱٬۲۸۸٬۰۰۰` = statement line 11 ✓.

**The two corrections in the same month are absent, by design:** `۱۴۰۵/۰۶/۱۶ کاغذ پرکننده اصلاح + ۰٫۵ کیلوگرم (+45,000)` and `۱۴۰۵/۰۶/۰۹ استیکر پک اصلاح − ۷ عدد (−266,000)`. Neither appears in the waste table, and neither is netted into the `ضایعات` line or any other statement line. If they were included the waste line would read `1,288,000 + 266,000 − 45,000 = 1,509,000` and net profit would be `41,825,000` — both figures are wrong and must not appear anywhere.

Operating expenses: `12,000,000 + 8,500,000 + 2,400,000 + 2,200,000 + 1,900,000 = 27,000,000` ✓ = statement line 12. Category rollups from `../data/sample-data.md`: تبلیغات `5,000,000 + 3,500,000 = 8,500,000`; اینترنت و نرم‌افزار `1,400,000 + 1,000,000 = 2,400,000`; متفرقه `700,000 + 1,500,000 = 2,200,000`. Shares as printed: `۴۴٪ / ۳۱٪ / ۹٪ / ۸٪ / ۷٪` — true values are 44.44 / 31.48 / 8.89 / 8.15 / 7.04, so the printed set sums to **۹۹٪**, not ۱۰۰٪.

---

## 7. Open questions for this screen

- **The date range is a frozen label.** `بازه: ۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱` is a hardcoded string on a `.select` with `aria-haspopup="dialog"`, and that dialog has no artboard on this screen (`Orders-DateRange` exists for the orders screen; whether reports reuse it is undecided). Undesigned: the picker itself, its validation (start ≤ end, maximum span, future dates), what happens when the range crosses a Jalali month boundary — every figure on the screen is labelled «شهریور ۱۴۰۵» in the statement heading, which only holds for a whole-month range — and whether the range is shared with the other screens or per screen.
- **The four presets are decorative and can contradict the label.** `این ماه` is drawn `on` with no handler, and nothing keeps it in sync with the range text. Which preset is selected when an arbitrary range is picked, and whether the presets are Jalali-aware (`امسال` = this Jalali month? this Jalali year?), is not specified.
- **Export is a button and nothing else.** `Excel` and `PDF` have no designed scope (current tab or all five?), no file naming, no column set, no busy state, no success confirmation and no failure message. `PDF` is also the only «print» affordance in the app apart from the invoice document, and it is not stated whether it produces this screen or a report layout.
- **Mobile implements one tab out of five.** The four remaining chips are static `<span>`s — not buttons, no `role="tab"`, no `aria-selected`, no handler — and there is no mobile design for product performance, channels, shipping or waste. Either mobile is P&L-only by decision (in which case the four chips should not be drawn) or four mobile bodies are missing. The chips are also 34px tall, below the 44px touch target the rest of the mobile design holds to.
- **Mobile copy diverges from desktop in two places and neither is confirmed intentional.** Row label: desktop «بهای تمام‌شده کالای فروخته‌شده» vs mobile «بهای تمام‌شده کالا». Tab labels: «عملکرد محصولات»/«ضایعات و هزینه‌ها» vs «محصولات»/«ضایعات». Pick one set per string; if the short forms exist because of width, say so, because the developer will otherwise treat one of them as a typo.
- **Mobile tooltips have no content.** Every mobile row carries an info icon with `aria-label="توضیح"` and the card is captioned «روی هر ردیف بزنید تا توضیح آن باز شود.», but no tooltip, sheet, accordion or popover is designed, and none of the 13 desktop tooltip strings is carried over. The promise in the caption is currently unfulfillable.
- **The month-over-month delta contradicts the sample data.** The `سود خالص` KPI shows `۳٪ نسبت به مرداد` (a `.delta.neg` with a `down` icon), but `../data/sample-data.md` records مرداد net profit as `38,900,000` against this month's `42,046,000` — an **increase** of about 8%. Nothing defines what the delta compares (net profit? net margin? percentage points?), where the previous period comes from when the range is not a whole month, how it rounds, or what it shows when there is no previous period. It is the only comparison anywhere on the screen.
- **The channel table's order count is the whole month, including drafts.** Its footer reads `۸۷` — the same 87 as `../data/sample-data.md`'s month total, which includes ۲ پیش‌نویس — while this tab's own alert states «پیش‌نویس‌ها در گزارش نمی‌آیند. سفارش‌های لغوشده و مرجوعی از درآمد حذف و زیان آن‌ها جداگانه نمایش داده می‌شود.». The same 87 is the denominator of the footer's `میانگین سفارش (تومان)` (`2,142,759`). Either the count must drop the drafts (and the average and the per-channel counts with it) or the exclusion rule needs restating.
- **Two different shipped-order counts exist for the same month.** The shipping tab divides everything by `۷۲` shipped orders, but `../data/sample-data.md` records the month's postage payments as `14,760,000` across **75** orders. Which count is authoritative for «پست واقعی / سفارش» is undecided, and the answer changes that KPI (`205,000` vs `196,800`) and the per-order result.
- **Wholesale packaging is `130,000` per order and nothing explains why.** The row shows `−۱٬۰۴۰٬۰۰۰ ÷ ۸ = ۱۳۰٬۰۰۰`, but wholesale's default kit is «جعبه استاندارد» at `95,000` (`15-settings.md` §6, `formulas.md` §5). Presumably wholesale orders use larger or multiple boxes, but no rule, no mix and no per-order kit count is documented anywhere, and the break-even note deliberately covers only web and Instagram.
- **The postage variance is shown twice, with two different labels and two different roles.** It is statement line 9 («مغایرت هزینه پست») and also a shaded row inside the shipping table («مغایرت هزینه پست (پرداخت واقعی ۱۴٬۷۶۰٬۰۰۰ − تخمین‌ها ۱۴٬۳۴۷٬۶۵۶)»). In the shipping table it is lumped into the postage column so that the footer mixes actual postage with estimates + variance, while the three channel rows carry estimates only. Decide which surface owns the variance, whether it should be allocated per channel, and what the footer column actually means.
- **Zero and negative cases are undesigned across every tab.** «سایر» renders `۰ / — / —` with a `.nil` class but no copy explaining an unused channel; «حضوری» and «سایر» simply have no row in the shipping tab; the product table's profit column is unconditionally `.pos` (no product with zero or negative profit is drawn, and no `.neg` variant exists); and no tab has a partial-empty state — the shared empty board covers only «no data at all in this range».
- **The bar scales are hardcoded to this month's winners.** Both channel charts divide by literal maxima (`68,200,000` and `25,624,718`) and the product meter divides by a literal `0.34`. For any other period those constants are wrong; whether bars should scale to the period maximum, to the total, or to a fixed axis is not decided. Nor is a negative-bar direction defined for a loss-making channel or product.
- **The product table promises sorting it does not have.** The header «سود ↓ (تومان)» carries a literal `↓`, but no column is a button and the order is fixed in `renderVals` (profit, descending). Whether any column is sortable, whether the table paginates or caps at N products, and what happens to products with no sales in the period (they are simply absent — there is no zero row) are all undecided.
- **The tab strip has no navigation model.** No `.cnt` counts, no URL or hash per tab, no keyboard arrow-key `tablist` behaviour, no `aria-controls`/`tabpanel` wiring (the bodies are plain `<div>`s, not `role="tabpanel"`), no remembered tab across reloads, and no transition or loading step when a tab body swaps.
- **The dark theme covers only the P&L tab, at a shorter canvas.** `Reports-Dark` is `h: 940` while the light default is `h: 1060`, so the dark board is 120px shorter than the content it renders; and no dark artboard exists for the product, channel, shipping or waste tabs, nor for mobile. The chart fills (`--bar-a`, `--profit`) and the `--loss-soft` KPI card are therefore unverified in dark.
- **The toolbar stays live in the empty, loading and error states.** It renders outside the `isReady` guard and nothing disables the range button, the presets or the export buttons there — so «Excel» is offered on a screen with no data. Decide whether they should be disabled, and whether the tab strip (which *is* inside the guard, and so disappears) should also stay visible.
- **Table rows hover but do nothing.** `.tbl tbody tr:hover` tints every row on all four table tabs, yet no row on this screen links anywhere. Drilling from a product, a channel or a waste row into the underlying orders or adjustment records is an obvious next step and is not designed — the waste table in particular has no link back to the `تعدیل موجودی` record, no date column, no reason grouping, no pagination and no export.
- **Two blocks are hardcoded markup rather than data.** The waste rows and the operating-expense rows (amounts, shares and meter widths alike) are literal HTML, unlike the statement, the product table and the channel table, which are computed from arrays. The expense shares are also rounded independently and sum to **۹۹٪**; no rounding rule is defined, and no overflow behaviour («بیشتر» / «سایر») exists if a period has more than five expense categories.
- **Nothing on this screen shows an order count per line of the statement, and none of the 13 lines is drillable.** The heading caption says «۸۷ سفارش · مبالغ به تومان», but there is no way to see which orders make up a figure, and no note explaining how a partially-refunded or edited order is treated between the revenue lines and the `زیان مرجوعی و لغو` line.

See also `../open-questions.md` for the cross-screen items (routes, the export format, and the period model shared with `13-partners.md`).
