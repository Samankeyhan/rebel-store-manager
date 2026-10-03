/**
 * Persian copy for the dashboard (design/screens/01-dashboard.md §2),
 * verbatim where the design has the string. Strings marked NEW are not in the
 * design: they cover the period selector, states the design didn't draw
 * (profitable / break-even shipping, a per-card error), and replace design
 * copy that would be untrue against the live backend (no minimum stock, no
 * month-over-month deltas).
 */

import { toPersianDigits } from "@/lib/persian-numbers"

const fa = toPersianDigits

export const D = {
  // ── header ──
  newSale: "ثبت فروش",
  newPurchase: "ثبت خرید", // NEW (quick action)
  newProduction: "ثبت تولید", // NEW (quick action)
  quickActionsAria: "اقدام‌های سریع", // NEW
  periodAria: "بازه گزارش", // NEW
  periodToday: "امروز", // NEW
  periodLast7: "۷ روز اخیر", // NEW
  periodThisMonth: "این ماه", // NEW
  periodLastMonth: "ماه گذشته", // NEW
  periodCustom: "بازه دلخواه", // NEW
  periodRange: (from: string, to: string) => `${from} تا ${to}`, // NEW

  // The period as it reads after a KPI label: «درآمد این ماه».
  periodWord: {
    today: "امروز",
    last7: "۷ روز اخیر",
    thisMonth: "این ماه",
    lastMonth: "ماه گذشته",
    custom: "بازه انتخابی",
  } as const, // NEW (all but «این ماه»)

  // ── KPIs ──
  kpiAria: "شاخص‌های کلیدی",
  kpiRevenue: (period: string) => `درآمد ${period}`,
  kpiNet: (period: string) => `سود خالص ${period}`,
  kpiOrders: (period: string) => `سفارش‌های ${period}`,
  toman: "تومان",
  orderUnit: "سفارش",
  revenueCaption: (items: string, shipping: string) => `کالا ${items} · ارسال ${shipping}`, // NEW (replaces the delta)
  margin: (pct: string) => `حاشیه سود ${pct}`,
  ordersExcluded: "بدون پیش‌نویس، لغوشده و مرجوعی", // NEW (tooltip)
  ordersExcludedAria: "کدام سفارش‌ها شمرده می‌شوند", // NEW
  channelCount: (n: number, name: string) => `${fa(n)} ${name}`, // NEW
  nil: "—",
  unavailable: "در دسترس نیست",
  retry: "تلاش دوباره",
  retryAria: (what: string) => `تلاش دوباره: ${what}`, // NEW

  // ── purchases & costs (NEW card: not in the design) ──
  costsTitle: "خرید و هزینه‌ها", // NEW
  costsOperating: "هزینه‌های عملیاتی", // NEW
  costsMaterials: "خرید متریال", // NEW
  costsProducts: "خرید محصول آماده", // NEW
  costsPostage: "هزینه پست پرداخت‌شده", // NEW
  costsCount: (n: number) => `(${fa(n)})`, // NEW
  costsNote: "خرید متریال و محصول، موجودی می‌شود و مستقیماً در سود و زیان نمی‌آید", // NEW
  costsLinkAria: (what: string) => `مشاهده ${what} در این بازه`, // NEW

  // ── shipping economics ──
  shipTitle: (period: string) => `اقتصاد ارسال ${period}`,
  shipCaption: (n: number, range: string) => `${fa(n)} سفارش ارسالی · ${range}`,
  shipCaptionMobile: (n: number) => `${fa(n)} سفارش ارسالی`,
  shipCaptionHelp: "سفارش‌های کانال‌هایی که هزینه پست دارند، بدون پیش‌نویس، لغوشده و مرجوعی.", // NEW
  badgeLoss: "زیان‌ده",
  badgeEven: "سربه‌سر", // NEW
  badgeProfit: "سودده", // NEW
  figCharged: "دریافتی از مشتری",
  figPackaging: "هزینه بسته‌بندی",
  figPostage: "هزینه پست (تخمینی)",
  figResult: "نتیجه هر سفارش",
  perOrder: "تومان برای هر سفارش",
  postageRateCaption: "جمع پرداختی ÷ جمع سفارش‌ها",
  postageRateNote: "نرخ فعلی هر مرسوله", // NEW
  resultLoss: "تومان زیان",
  resultProfit: "تومان سود", // NEW
  periodSum: (v: string) => `جمع بازه: ${v}`, // NEW (design: «جمع ماه:»; the period can be any range)
  periodSumLabel: "جمع نتیجه بازه", // NEW (design: «جمع زیان ماه»)
  barsAria: (charged: string, cost: string) => `مقایسه دریافتی ${charged} تومان با هزینه ${cost} تومان در این بازه`, // NEW wording
  barCharged: "دریافتی",
  barCost: "هزینه",
  barPackaging: "بسته‌بندی",
  barPostage: "پست",
  barShortfall: "کسری",
  breakEven: (gap: string) =>
    `برای سربه‌سر شدن، هزینه ارسال دریافتی هر سفارش باید دست‌کم ${gap} تومان بیشتر باشد، یا هزینه بسته‌بندی و پست هر سفارش همین‌قدر کمتر شود.`, // NEW wording (no target sum)
  breakEvenLink: "هزینه‌های ارسال",
  paidSoFar: "پرداخت‌شده تاکنون", // NEW
  unpaidNote: "بخشی از هزینه پست این بازه هنوز پرداخت یا ثبت نشده", // NEW
  shipEmptyTitle: "هنوز سفارش ارسالی ندارید",
  shipEmptyBody:
    "پس از ثبت اولین سفارش وب‌سایت یا اینستاگرام، این‌جا می‌بینید هزینه ارسال دریافتی چقدر از هزینه بسته‌بندی و پست را پوشش می‌دهد.",
  shipEmptyPeriodTitle: "در این بازه سفارش ارسالی ثبت نشده", // NEW
  shipEmptyPeriodBody: "در این بازه سفارشی از کانال‌هایی که هزینه پست دارند ثبت نشده است.", // NEW
  shipErrorTitle: "اقتصاد ارسال بارگذاری نشد", // NEW

  // ── out of stock (the design's low-stock card; there is no minimum stock) ──
  stockTitle: "ناموجود", // NEW (design: «هشدار کمبود موجودی»)
  stockBadge: (n: number) => `${fa(n)} مورد`,
  stockTabProducts: "محصولات",
  stockTabMaterials: "متریال",
  stockTabsAria: "نوع کالا", // NEW
  stockOut: "ناموجود",
  stockMore: (n: number) => `و ${fa(n)} مورد دیگر`, // NEW
  stockAll: "مشاهده همه در محصولات و متریال",
  stockEmptyTitle: "کمبودی وجود ندارد",
  stockEmptyBody: "موجودی هیچ کالای فعالی صفر نیست.", // NEW (the design's sentence promised a minimum that doesn't exist)
  stockEmptyTab: { products: "هیچ محصول فعالی ناموجود نیست.", materials: "هیچ متریال فعالی ناموجود نیست." }, // NEW
  stockErrorTitle: "موجودی بارگذاری نشد", // NEW

  // ── recent orders ──
  ordersTitle: "آخرین سفارش‌ها",
  ordersAll: "همه سفارش‌ها",
  ordersAllMobile: "همه",
  colDate: "تاریخ",
  ordersEmptyTitle: "هنوز سفارشی ثبت نشده",
  ordersEmptyBody: "اولین فروش را ثبت کنید تا فهرست سفارش‌ها و سود هر کدام این‌جا نمایش داده شود.",
  ordersEmptyCta: "ثبت اولین فروش",
  ordersErrorTitle: "سفارش‌ها بارگذاری نشد", // NEW

  // ── first run ──
  welcomeTitle: "به مدیریت ربل شاپ خوش آمدید",
  welcomeBody: "برای دیدن گزارش‌ها، ابتدا محصولات و کیت‌های بسته‌بندی را تعریف کنید و سپس اولین فروش را ثبت کنید.",
  welcomeCta: "تعریف محصولات",

  // ── shared states ──
  loadingAria: "در حال بارگذاری",
  errorCode: (code: string) => `کد خطا: ${code}`,
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
}
