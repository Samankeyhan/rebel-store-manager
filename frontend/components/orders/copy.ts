/**
 * Persian copy for the orders list (design/screens/03-orders-list.md §2) and
 * order detail (04-order-detail.md §2), verbatim. Strings marked NEW are not
 * in the design: they cover states the live backend has and the design
 * didn't draw, or replace design copy that would be untrue (see the report).
 */

import { formatNumber, toPersianDigits } from "@/lib/persian-numbers"

const fa = toPersianDigits

export const L = {
  // ── list: chrome ──
  subtitleMonth: (n: number, month: string) => `${fa(n)} سفارش در ${month}`,
  subtitleRange: (n: number) => `${fa(n)} سفارش در بازه انتخاب‌شده`, // NEW
  newSale: "ثبت فروش",

  // ── list: filter bar ──
  filterAria: "فیلتر سفارش‌ها",
  searchPlaceholder: "شماره فاکتور یا نام مشتری",
  searchAria: "جستجو در سفارش‌ها",
  searchAriaMobile: "جستجو",
  channelLabel: "کانال:",
  allChannels: "همه کانال‌ها",
  dateLabel: "تاریخ:",
  dateValue: (from: string, to: string) => `${from} تا ${to}`,
  clearFilters: "پاک کردن فیلترها",

  // ── list: date popover ──
  dateDialogAria: "انتخاب بازه تاریخ",
  presetToday: "امروز",
  presetYesterday: "دیروز",
  presetLast7: "۷ روز اخیر",
  presetLast30: "۳۰ روز اخیر",
  presetThisMonth: "این ماه",
  presetLastMonth: "ماه گذشته",
  presetYear: (year: number) => `سال ${fa(year)}`,
  presetCustom: "بازه دلخواه",
  rangeFrom: "از",
  rangeTo: "تا",
  rangeDays: (n: number) => `(${fa(n)} روز)`,
  cancel: "انصراف",
  apply: "اعمال",

  // ── list: tabs ──
  tabsAria: "وضعیت",
  tabAll: "همه",

  // ── list: totals strip ──
  pageCount: (n: number) => `این صفحه: ${fa(n)} سفارش`,
  pageCountStatus: (n: number, status: string) => `${fa(n)} سفارش «${status}» در این صفحه`,
  salesTotal: "جمع فروش:",
  profitTotal: "جمع سود:",
  toman: "تومان",

  // ── list: table ──
  colInvoice: "شماره فاکتور",
  colDate: "تاریخ ↓",
  colChannel: "کانال",
  colCustomer: "مشتری",
  colStatus: "وضعیت",
  colTotal: "مبلغ کل (تومان)",
  colProfit: "سود (تومان)",
  colActions: "عملیات",
  rowActions: "عملیات سفارش",
  viewOrder: "مشاهده سفارش",
  printInvoicePdf: "چاپ فاکتور (PDF)",
  refundOriginal: (n: string) => `فروش اولیه: ${n}`, // NEW

  // ── list: pagination ──
  pageRange: (from: number, to: number, total: number) =>
    `نمایش ${fa(from)} تا ${fa(to)} از ${fa(total)}`,
  prevPage: "صفحه قبل",
  nextPage: "صفحه بعد",

  // ── list: mobile ──
  mobileCount: (n: number) => `${fa(n)} سفارش`,
  mobileMore: (n: number) => `نمایش ${fa(n)} سفارش بعدی`,
  mobileProfit: (v: string) => `سود ${v}`,
  mobileProfitNone: "سود: —",
  filtersChip: "فیلترها",
  allStatuses: "همه وضعیت‌ها",
  sheetTitle: "فیلترها",
  sheetClear: "پاک کردن همه",
  sheetStatus: "وضعیت",
  sheetChannel: "کانال",
  sheetDate: "بازه تاریخ",
  segLast7: "۷ روز",
  segThisMonth: "این ماه",
  segCustom: "دلخواه",
  sheetFrom: "از ",
  sheetTo: "تا ",
  sheetApply: "نمایش سفارش‌ها", // NEW (design's «نمایش ۱۰ سفارش» needs a preview count)
  close: "بستن",

  // ── list: states ──
  filteredEmptyTitle: "هیچ سفارشی با این فیلترها پیدا نشد",
  filteredEmptyBody: "وضعیت یا بازه تاریخ را تغییر دهید.",
  filteredEmptyAction: "پاک کردن فیلترها",
  emptySubtitle: "هنوز سفارشی ندارید",
  emptyTitle: "هنوز سفارشی ثبت نشده",
  emptyBody: "هر فروشی که ثبت کنید با شماره فاکتور، کانال، وضعیت، مبلغ و سود این‌جا فهرست می‌شود.",
  emptyBodyMobile: "هر فروشی که ثبت کنید این‌جا فهرست می‌شود.",
  emptyCta: "ثبت اولین فروش",
  errorTitle: "فهرست سفارش‌ها بارگذاری نشد",
  errorTitleMobile: "سفارش‌ها بارگذاری نشد",
  errorBody: "سرور پاسخ نداد. فیلترهای شما حفظ شده‌اند؛ دوباره تلاش کنید.",
  errorBodyMobile: "سرور پاسخ نداد. فیلترهای شما حفظ شده‌اند.",
  retry: "تلاش دوباره",
  errorCode: "کد خطا:",
} as const

export const D = {
  // ── detail: header ──
  crumbParent: "سفارش‌ها",
  customer: "مشتری: ",
  registered: (when: string) => `ثبت: ${when}`,
  packaging: (name: string) => `بسته‌بندی: ${name}`,
  noPackaging: "بدون بسته‌بندی", // NEW (design only drew an order with a kit)
  unknownKit: "کیت بسته‌بندی", // NEW (kit no longer in the active catalog)
  total: "مبلغ کل",
  transitionsLabel: "تغییر وضعیت به:",
  mobileTransition: (status: string) => `تغییر وضعیت به ${status}`,
  print: "چاپ فاکتور",
  cancelOrder: "لغو سفارش",
  refundOrder: "ثبت مرجوعی",
  sensitive: "عملیات حساس",
  terminalCompleted: "سفارش تکمیل شده است.",
  terminalCancelled: "سفارش لغو شده؛ عملیاتی باقی نمانده.",
  terminalRefunded: "مرجوعی ثبت شده؛ عملیاتی باقی نمانده.",

  // ── detail: items ──
  itemsCard: "اقلام سفارش",
  itemsCaption: (rows: number, units: number) => `${fa(rows)} ردیف · ${fa(units)} عدد`,
  colProduct: "محصول",
  colQty: "تعداد",
  colUnitPrice: "قیمت واحد",
  colDiscount: "تخفیف",
  colLineTotal: "جمع (تومان)",
  discountReason: (reason: string) => `تخفیف: ${reason}`,
  mobileQty: (qty: number, price: number) => `${formatNumber(qty)} × ${formatNumber(price)}`,
  mobileDiscount: (amount: number, reason: string | null) =>
    `تخفیف ${formatNumber(-amount)}${reason ? ` (${reason})` : ""}`,

  // ── detail: customer block ──
  customerBlock: "پرداختی مشتری (روی فاکتور)",
  itemsGross: "جمع اقلام",
  discount: "تخفیف",
  shipping: "هزینه ارسال",

  // ── detail: internal card ──
  internalCard: "بهای تمام‌شده و سود",
  internalCaption: "داخلی",
  revenue: "درآمد سفارش",
  cogs: "بهای تمام‌شده کالا",
  packagingRow: (name: string) => `بسته‌بندی · ${name}`,
  postage: "پست",
  postageMobile: "پست (تخمینی)",
  estimatedChip: "تخمینی",
  postageHint: (window: number) => `جمع پرداختی ÷ جمع سفارش‌ها در ${fa(window)} پرداخت اخیر`,
  postageHintShort: "جمع پرداختی ÷ جمع سفارش‌ها",
  fee: "کارمزد تراکنش",
  profit: "سود این سفارش",
  profitMobile: "سود",
  loss: "زیان این سفارش",
  margin: "حاشیه سود",
  shipEcon: (charged: string, cost: string) => `ارسال: دریافتی ${charged} − هزینه ${cost} =`,
  // NEW: status-specific internal states the design never drew
  draftNote: "پیش‌نویس هنوز کالا و بسته‌بندی را کسر نکرده؛ بهای تمام‌شده و هزینه‌ها هنگام تغییر وضعیت ثبت می‌شوند.",
  cancelledNote: "این سفارش لغو شده و در فروش و سود حساب نمی‌شود.",
  cancelLoss: "زیان لغو: کارمزد تراکنش",
  refundOriginal: "سود فروش اولیه",
  refundOriginalNote: "سود ثبت‌شده هنگام فروش؛ بدون تغییر.",
  refundLoss: "زیان مرجوعی",
  refundLossBreakdown: (pack: number, post: number, fee: number) =>
    `بسته‌بندی ${formatNumber(pack)} + پست ${formatNumber(post)} + کارمزد ${formatNumber(fee)}`,

  // ── detail: actions feedback (NEW) ──
  toastStatus: (status: string) => `وضعیت سفارش به «${status}» تغییر کرد`,
  toastCancelled: "سفارش لغو شد",
  toastRefunded: "مرجوعی ثبت شد",
  toastBody: "موجودی و گزارش‌ها به‌روز شدند.",
  conflict: "وضعیت این سفارش در این فاصله تغییر کرده بود؛ وضعیت فعلی نمایش داده شده است.",
  actionFailed: "تغییر وضعیت انجام نشد",

  // ── commit confirm (NEW: design has no confirmation for leaving DRAFT) ──
  commitTitle: (status: string) => `تغییر وضعیت به «${status}»؟`,
  commitBody:
    "پیش‌نویس هنوز موجودی را رزرو نکرده است. با این تغییر، کالا و بسته‌بندی همین حالا از موجودی کم می‌شوند و بهای تمام‌شده، بسته‌بندی و هزینه پست روی سفارش ثبت می‌شوند.",
  commitConfirm: (status: string) => `تغییر به ${status}`,

  // ── cancel dialog ──
  cancelTitle: (inv: string) => `لغو سفارش ${inv}؟`,
  cancelSubtitle: (status: string) => `این سفارش «${status}» است و هنوز ارسال نشده. با لغو:`,
  cancelSubtitleDraft: (status: string) => `این سفارش «${status}» است. با لغو:`, // NEW
  effProductsLead: "کالا به موجودی برمی‌گردد:",
  effMadeToOrder: (name: string) => `متریال مصرف‌شده برای ساخت «${name}» به موجودی برمی‌گردد.`, // NEW
  effDraftNothing: "پیش‌نویس موجودی رزرو نکرده بود؛ چیزی به موجودی برنمی‌گردد.", // NEW
  effPackagingLead: "بسته‌بندی به موجودی برمی‌گردد:",
  effNoPostageLead: "بدون هزینه پست:",
  effNoPostageBody: "سفارش ارسال نشده، پس هزینه پستی ثبت نمی‌شود.",
  effFeeLead: "تنها زیان، کارمزد تراکنش است:",
  effFeeBody: "به‌عنوان زیان ثبت می‌شود.",
  effNoLossLead: "بدون زیان:", // NEW
  effNoLossBody: "این سفارش کارمزد تراکنش نداشته، پس زیانی ثبت نمی‌شود.", // NEW
  effMoneyLead: "پول مشتری:",
  // Reworded: the app records no money movement (design said «…ثبت می‌شود»).
  effMoneyBody: "دریافت‌شده باید به مشتری بازگردانده شود؛ این کار بیرون از برنامه انجام می‌شود.",
  effReportsLead: "گزارش‌ها:",
  effReportsBody: (month: string) =>
    `این سفارش از فروش و سود ${month} حذف می‌شود و وضعیت آن «لغوشده» می‌شود.`,
  effReportsDraft: "این پیش‌نویس در گزارش‌ها نبود؛ فقط وضعیت آن «لغوشده» می‌شود.", // NEW
  cancelReasonLabel: "دلیل لغو",
  cancelReasonPlaceholder: "مثلاً: مشتری منصرف شد",
  // NEW: the API stores the reason in the stock-movement notes, not a history.
  reasonHelp: "در یادداشت برگشت موجودی این سفارش ذخیره می‌شود.",
  irreversible: "این کار برگشت‌پذیر نیست.",

  // ── refund dialog ──
  refundTitle: (inv: string) => `ثبت مرجوعی برای ${inv}`,
  refundSubtitle: "کالا برگشت داده شده است. با ثبت مرجوعی، وضعیت سفارش «مرجوعی» می‌شود و:",
  effOnlyProductsLead: "فقط کالا به موجودی برمی‌گردد:",
  effLossLead: "این مبالغ زیان این سفارش می‌شوند:",
  effLossBody: (pack: number, post: number, fee: number, total: number) =>
    `بسته‌بندی ${formatNumber(pack)} + پست ${formatNumber(post)} + کارمزد تراکنش ${formatNumber(fee)} = ${formatNumber(total)} تومان.`,
  effBoxNotReturned: "جعبه مصرف‌شده به موجودی برنمی‌گردد.",
  effRefundMoneyLead: "بازپرداخت پول به مشتری بیرون از برنامه انجام می‌شود.",
  effRefundMoneyBody: "این‌جا مبلغی ثبت نمی‌شود؛ فقط وضعیت سفارش و دلیل آن ذخیره می‌شود.",
  refundReasonLabel: "دلیل مرجوعی",
  refundReasonPlaceholder: "مثلاً: کالا آسیب‌دیده رسید",
  optional: "(اختیاری)",

  // ── states ──
  notFoundTitle: (inv: string | null) => (inv ? `سفارش ${inv} پیدا نشد` : "سفارش پیدا نشد"),
  notFoundTitleMobile: "سفارش پیدا نشد",
  notFoundBody:
    "ممکن است نشانی اشتباه باشد یا ارتباط با سرور قطع شده باشد. اگر این سفارش را تازه ثبت کرده‌اید، چند لحظه بعد دوباره تلاش کنید.",
  notFoundBodyMobile: "ممکن است ارتباط قطع شده باشد. دوباره تلاش کنید.",
  backToOrders: "بازگشت به سفارش‌ها",
} as const
