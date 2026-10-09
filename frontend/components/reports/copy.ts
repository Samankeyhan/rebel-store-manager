/**
 * Reports screen copy («گزارش‌ها»). // NEW file
 * Labels and state copy follow design/screens/12-reports.md §2. Every
 * explanation of a figure is written from docs/accounting-rules.md (§7, §8,
 * §9, §14) and the order statuses db/orders.py counts
 * (REVENUE_ELIGIBLE_STATUSES = PENDING, PAID, COMPLETED), not from the
 * design's tooltips, which predate those rules. Status names come from
 * components/common/status.tsx.
 */

import { ORDER_STATUSES } from "@/components/common/status"
import { currencyLabel, formatMoney, formatMoneyNumber } from "@/lib/money"
import { formatNumber } from "@/lib/persian-numbers"
import type { PnlFigures, PnlKey } from "@/lib/reports"

const fa = formatNumber
const st = (s: keyof typeof ORDER_STATUSES) => `«${ORDER_STATUSES[s].name}»`
/** «در انتظار»، «پرداخت‌شده» و «تکمیل‌شده»: the revenue-eligible statuses. */
const ELIGIBLE = `${st("PENDING")}، ${st("PAID")} و ${st("COMPLETED")}`

export const R = {
  get unit() {
    return currencyLabel()
  },
  nil: "—", // NEW
  retry: "تلاش دوباره",
  loadingAria: "در حال بارگذاری",

  // ── shell ──
  tabsLabel: "نوع گزارش", // NEW
  tabPnl: "سود و زیان",
  tabProducts: "عملکرد محصولات",
  tabProductsShort: "محصولات",
  tabChannels: "کانال‌ها",
  periodAria: "بازه گزارش", // NEW
  presetThisMonth: "این ماه",
  presetLastMonth: "ماه گذشته",
  presetThisYear: "امسال",
  presetLast30: "۳۰ روز اخیر", // NEW
  presetAll: "از ابتدا", // NEW
  presetCustom: "بازه دلخواه", // NEW
  allTime: "از ابتدا", // NEW
  rangeText: (from: string, to: string) => `${from} تا ${to}`,

  // ── states ──
  emptyTitle: "در این بازه داده‌ای وجود ندارد",
  emptyBody: "در بازه انتخاب‌شده سفارش، هزینه یا ضایعاتی ثبت نشده است. بازه دیگری انتخاب کنید.", // NEW (design: «تعدیلی»; adjustments never reach a report)
  emptyBodyMobile: "بازه دیگری انتخاب کنید.",
  errorTitle: "گزارش بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",

  // ── «مطابقت» ──
  checkOk: (what: string) => `مطابقت: ${what}`, // NEW
  checkBad: (what: string) => `عدم مطابقت: ${what}`, // NEW
  checkBadDetail: (rows: string, pnl: string, diff: string) => `جمع ردیف‌ها ${rows} · سود و زیان ${pnl} · اختلاف ${diff}`, // NEW
  checkInvalid: (what: string) => `مطابقت بررسی نشد: ${what} (عدد نامعتبر از سرور)`, // NEW
  checkUnavailable: "مطابقت بررسی نشد: سود و زیان این بازه بارگذاری نشد.", // NEW
  checkStatement: (total: string) => `سطرهای بالای «${total}» با خود آن`, // NEW
  checkProductsRevenue: "جمع درآمد محصولات = «درآمد فروش اقلام» سود و زیان", // NEW
  checkProductsCost: "جمع بهای تمام‌شده محصولات = «بهای تمام‌شده کالای فروخته‌شده» سود و زیان", // NEW
  checkChannelsOrders: "جمع سفارش کانال‌ها = «تعداد سفارش» سود و زیان", // NEW
  checkChannelsRevenue: "جمع درآمد کانال‌ها = «جمع درآمد» سود و زیان", // NEW
  checkChannelsProfit: "جمع سود سفارش‌های کانال‌ها = «سود ناخالص» سود و زیان", // NEW

  // ── P&L ──
  statementTitle: (period: string) => `صورت سود و زیان — ${period}`,
  statementCaption: (orders: number) => `${fa(orders)} سفارش · مبالغ به ${currencyLabel()}`,
  pctLegend: "درصد از جمع درآمد",
  groupRevenue: "درآمد", // NEW
  groupOrderCosts: "هزینه‌های سفارش‌ها", // NEW
  groupAfterGross: "پس از سود ناخالص", // NEW
  infoTitle: "اطلاعات تکمیلی (در جمع‌ها نمی‌آید)", // NEW
  explainAria: (label: string) => `توضیح «${label}»`,
  showAll: "نمایش همه توضیحات", // NEW
  hideAll: "بستن همه توضیحات", // NEW
  howTitle: "چطور حساب می‌شود", // NEW
  formulaTitle: "در این بازه", // NEW
  kpiNet: "سود خالص",
  kpiGross: "سود ناخالص",
  kpiNetCaption: (pct: string) => `${pct} از جمع درآمد`, // NEW
  kpiGrossCaption: "سود خود سفارش‌ها، پیش از مغایرت پست، زیان مرجوعی، ضایعات و هزینه‌های عملیاتی", // NEW
  ordersCount: (n: number) => `${fa(n)} سفارش`,
  /** Replaces the design's alert: pending orders do count (rules §9). */
  scopeNote:
    `سفارش‌های ${ELIGIBLE} با تاریخ سفارش در این بازه در درآمد و هزینه‌ها حساب می‌شوند؛ ` +
    `سفارش ${st("PENDING")} هم حساب می‌شود، حتی اگر پولش هنوز نرسیده باشد. ` +
    `سفارش‌های ${st("DRAFT")} در گزارش نمی‌آیند. سفارش‌های ${st("CANCELLED")} و ${st("REFUNDED")} در درآمد نمی‌آیند؛ ` +
    `هزینه‌ای که با آن‌ها از دست رفته در «زیان مرجوعی و لغو» آمده است.`, // NEW
  signAdd: "به سود اضافه می‌شود", // NEW (screen-reader text for «+»)
  signSub: "از سود کم می‌شود", // NEW (screen-reader text for «−»)

  // ── products ──
  searchLabel: "جستجوی محصول", // NEW
  searchPlaceholder: "نام محصول…", // NEW
  colProduct: "محصول",
  colUnits: "تعداد فروش",
  get colRevenue() {
    return `درآمد (${currencyLabel()})`
  },
  get colCost() {
    return `بهای تمام‌شده (${currencyLabel()})`
  },
  get colProfit() {
    return `سود (${currencyLabel()})`
  },
  colMargin: "حاشیه سود",
  sortBy: "مرتب‌سازی", // NEW
  sortAsc: "صعودی", // NEW
  sortDesc: "نزولی", // NEW
  sortLabels: {
    name: "نام", // NEW
    units: "تعداد فروش",
    revenue: "درآمد", // NEW
    cost: "بهای تمام‌شده", // NEW
    profit: "سود", // NEW
    margin: "حاشیه سود",
  },
  total: "جمع",
  totalFiltered: (n: number) => `جمع ${fa(n)} نتیجه`, // NEW
  productsNote:
    "سود محصول = درآمد اقلام پس از تخفیف − بهای تمام‌شده. هزینه ارسال، بسته‌بندی، پست و کارمزد در سطح سفارش است و در «سود و زیان» می‌آید.", // NEW (design text plus fees)
  productsEmptyTitle: "در این بازه محصولی فروخته نشده", // NEW
  productsEmptyBody: "سفارش‌های این بازه هیچ قلم محصولی ندارند، یا فقط هزینه و ضایعات ثبت شده است.", // NEW
  searchEmpty: (q: string) => `محصولی با «${q}» پیدا نشد`, // NEW
  clearSearch: "پاک کردن جستجو", // NEW
  productsAria: "عملکرد محصولات", // NEW

  // ── channels ──
  chartRevenue: "درآمد به تفکیک کانال",
  chartProfit: "سود سفارش‌ها به تفکیک کانال",
  get chartCaption() {
    return currencyLabel()
  },
  chartRevenueAria: "نمودار میله‌ای درآمد کانال‌ها",
  chartProfitAria: "نمودار میله‌ای سود کانال‌ها",
  colChannel: "کانال",
  colOrders: "سفارش",
  get colOrderProfit() {
    return `سود سفارش‌ها (${currencyLabel()})`
  },
  channelsNote:
    "سود سفارش = درآمد سفارش − بهای تمام‌شده − بسته‌بندی − پست (تخمینی) − کارمزد. مغایرت پست، زیان مرجوعی، ضایعات و هزینه‌های عملیاتی به کانال نسبت داده نمی‌شوند. کانالی که در این بازه سفارش نداشته، نمایش داده نمی‌شود.", // NEW (rules §7)
  channelsEmptyTitle: "در این بازه سفارشی ثبت نشده", // NEW
  channelsEmptyBody: "فقط سفارش‌های در انتظار، پرداخت‌شده و تکمیل‌شده به کانال‌ها می‌آیند.", // NEW
  channelsAria: "کانال‌ها", // NEW
}

// ── P&L key explanations ───────────────────────────────────────────────────

type Explain = {
  label: string
  /** Mobile label where design 12 shortens it. */
  short?: string
  /** What the figure means, in plain Persian. */
  meaning: string
  /** How db/ computes it (accounting-rules). */
  how: string
  /** The sum with this period's figures, when every operand is a returned key. */
  formula?: (p: PnlFigures) => string
}

const n = (rial: number) => formatMoneyNumber(rial)
/** «a − b + c = r تومان», each term signed by its real value. */
function sum(first: number, terms: [sign: 1 | -1, value: number][], result: number): string {
  let s = n(first)
  for (const [sign, v] of terms) {
    const signed = sign * v
    s += signed < 0 ? ` − ${n(Math.abs(v))}` : ` + ${n(Math.abs(v))}`
  }
  return `${s} = ${formatMoney(result)}`
}

const DAYS = "بازه روزهای کامل به وقت فروشگاه است و هر دو سر آن حساب می‌شود."

export const PNL_EXPLAIN: Record<PnlKey, Explain> = {
  items_revenue: {
    label: "درآمد فروش اقلام",
    meaning: "مبلغ اقلام فروخته‌شده پس از کسر تخفیف هر ردیف، بدون هزینه ارسال.", // NEW
    how: `برای هر ردیف سفارش: تعداد × قیمت واحد − تخفیف ردیف. جمع روی سفارش‌های ${ELIGIBLE} که تاریخ سفارششان در این بازه است. ${st("PENDING")} هم حساب می‌شود، حتی اگر پولش هنوز نرسیده باشد. پیش‌نویس، ${st("CANCELLED")} و ${st("REFUNDED")} حساب نمی‌شوند. ${DAYS}`, // NEW
  },
  shipping_revenue: {
    label: "درآمد هزینه ارسال",
    meaning: "هزینه ارسالی که از مشتری‌ها گرفته شده است.", // NEW
    how: `جمع هزینه ارسال همان سفارش‌ها (${ELIGIBLE}). پیش‌فرض آن از تنظیمات کانال می‌آید (فقط کانال‌هایی که هزینه ارسال می‌گیرند) و روی هر سفارش قابل تغییر است.`, // NEW
  },
  total_revenue: {
    label: "جمع درآمد",
    meaning: "کل مبلغی که مشتری‌ها بابت سفارش‌های این بازه پرداخت می‌کنند؛ همان مبلغ فاکتور مشتری.", // NEW
    how: "درآمد فروش اقلام + درآمد هزینه ارسال. درصدهای ستون آخر نسبت به همین عدد است.", // NEW
    formula: (p) => sum(p.items_revenue, [[1, p.shipping_revenue]], p.total_revenue),
  },
  cogs: {
    label: "بهای تمام‌شده کالای فروخته‌شده",
    short: "بهای تمام‌شده کالا",
    meaning: "بهای ساخت یا خرید همان کالاهایی که در این سفارش‌ها فروخته شده.", // NEW
    how: "برای هر ردیف: تعداد × بهای تمام‌شده واحد در لحظه ثبت سفارش (میانگین موزون موجودی). برای محصول «ساخت هنگام فروش»، واحدهایی که ساخته می‌شوند به بهای دستور ساخت در همان لحظه حساب می‌شوند. این عدد روی سفارش ثبت می‌شود و با تغییر بعدی بهای کالا عوض نمی‌شود.", // NEW
  },
  packaging_cost: {
    label: "بسته‌بندی",
    meaning: "بهای کیت بسته‌بندی سفارش‌ها.", // NEW
    how: "کیت سفارش: کیتی که روی سفارش انتخاب شده، وگرنه کیت پیش‌فرض کانال، وگرنه هیچ. بهای کیت = جمع (مقدار × بهای متریال) در لحظه ثبت سفارش؛ روی سفارش ثبت می‌شود و دیگر تغییر نمی‌کند.", // NEW
  },
  postage_estimated: {
    label: "هزینه پست (تخمینی)",
    meaning: "تخمین هزینه پستی که هنگام ثبت روی هر سفارش گذاشته شد.", // NEW
    how: "در لحظه ثبت سفارش: مبلغی که دستی وارد شده؛ وگرنه اگر کانال پست دارد، تخمین فعلی پست (جمع پرداختی ÷ جمع تعداد سفارش در چند پرداخت اخیر به پست؛ تعداد در تنظیمات؛ بدون هیچ پرداخت ثبت‌شده، تخمین پیش‌فرض تنظیمات)؛ وگرنه صفر. روی سفارش ثبت می‌شود و دیگر تغییر نمی‌کند.", // NEW
  },
  transaction_fees: {
    label: "کارمزد تراکنش",
    meaning: "کارمزدی که روش پرداخت (درگاه، کارت‌خوان…) از مبلغ سفارش برمی‌دارد.", // NEW
    how: "هنگام ثبت سفارش از روی روش پرداخت حساب می‌شود: درصد کارمزد × جمع مبلغ سفارش (با سقف، اگر روش سقف داشته باشد) + مبلغ ثابت هر تراکنش؛ یا دستی وارد می‌شود. روی سفارش ثبت می‌شود و تغییر بعدی کارمزد روش پرداخت، سفارش‌های قبلی را عوض نمی‌کند. سفارش بدون روش پرداخت کارمزد ندارد.", // NEW
  },
  gross_profit: {
    label: "سود ناخالص",
    meaning: "سود خود سفارش‌ها: درآمد منهای هزینه‌هایی که مستقیم روی سفارش ثبت شده.", // NEW
    how: "جمع درآمد − بهای تمام‌شده − بسته‌بندی − پست (تخمینی) − کارمزد.", // NEW
    formula: (p) =>
      sum(
        p.total_revenue,
        [
          [-1, p.cogs],
          [-1, p.packaging_cost],
          [-1, p.postage_estimated],
          [-1, p.transaction_fees],
        ],
        p.gross_profit
      ),
  },
  postage_variance: {
    label: "مغایرت هزینه پست",
    meaning: "فرق پولی که واقعاً به پست پرداخت شد با تخمین‌هایی که روی سفارش‌ها ثبت شده بود.", // NEW
    how: `پرداختی واقعی به پست در این بازه − جمع پست ثبت‌شده روی سفارش‌های ${ELIGIBLE} و ${st("REFUNDED")} همین بازه. مثبت یعنی پست بیش از تخمین هزینه داشته و از سود کم می‌شود (−)؛ منفی یعنی کمتر از تخمین بوده و به سود برمی‌گردد (+).`, // NEW
  },
  refund_losses: {
    label: "زیان مرجوعی و لغو",
    meaning: "هزینه‌هایی که با مرجوعی یا لغو سفارش‌ها از دست رفت. درآمد این سفارش‌ها در درآمد نمی‌آید.", // NEW
    how: `برای سفارش‌های ${st("REFUNDED")} این بازه: بسته‌بندی + پست + کارمزد. برای سفارش‌های ${st("CANCELLED")} که کالایشان کسر شده بود: فقط کارمزد (چیزی ارسال نشده، پس بسته‌بندی و پست زیان نیست).`, // NEW
  },
  waste_cost: {
    label: "ضایعات",
    meaning: "ارزش کالا و متریالی که به‌عنوان ضایعات ثبت شده.", // NEW
    how: "برای هر کالا: جمع (مقدار × بهای واحد در لحظه ثبت ضایعات)، که یک بار گرد می‌شود؛ این ردیف جمع همین مبلغ‌هاست. ضایعاتی که بهای واحدش معلوم نبود حساب نمی‌شود. «تعدیل موجودی» (اصلاح شمارش) در سود و زیان نمی‌آید.", // NEW
  },
  operating_expenses: {
    label: "هزینه‌های عملیاتی",
    meaning: "هزینه‌های جاری فروشگاه که در «هزینه‌ها» ثبت شده و به سفارش خاصی مربوط نیست.", // NEW
    how: "جمع هزینه‌هایی که تاریخشان در این بازه است. خرید متریال و محصول جزو آن نیست: خرید، موجودی است و فقط وقتی فروخته یا مصرف شود به‌صورت بهای تمام‌شده می‌آید. پرداخت سود به شرکا هم هزینه نیست.", // NEW
  },
  net_profit: {
    label: "سود خالص",
    meaning: "آنچه پس از همه هزینه‌ها برای فروشگاه می‌ماند؛ مبنای تقسیم سود بین شرکا.", // NEW
    how: "سود ناخالص − مغایرت هزینه پست − زیان مرجوعی و لغو − ضایعات − هزینه‌های عملیاتی.", // NEW
    formula: (p) =>
      sum(
        p.gross_profit,
        [
          [-1, p.postage_variance],
          [-1, p.refund_losses],
          [-1, p.waste_cost],
          [-1, p.operating_expenses],
        ],
        p.net_profit
      ),
  },
  postage_actual: {
    label: "پرداختی واقعی به پست", // NEW
    meaning: "جمع پرداخت‌های ثبت‌شده به اداره پست که تاریخ پرداختشان در این بازه است.", // NEW
    how: "مستقیم از سود کم نمی‌شود؛ فقط در «مغایرت هزینه پست» با تخمین‌های ثبت‌شده روی سفارش‌ها مقایسه می‌شود.", // NEW
  },
  order_count: {
    label: "تعداد سفارش", // NEW
    meaning: "سفارش‌هایی که درآمد و هزینه‌هایشان در این گزارش آمده.", // NEW
    how: `سفارش‌های ${ELIGIBLE} با تاریخ سفارش در این بازه. پیش‌نویس، ${st("CANCELLED")} و ${st("REFUNDED")} شمرده نمی‌شوند.`, // NEW
  },
}
