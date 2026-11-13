/**
 * Persian copy for the orders list (design/screens/03-orders-list.md §2) and
 * order detail (04-order-detail.md §2), verbatim. Strings marked NEW are not
 * in the design: they cover states the live backend has and the design
 * didn't draw, or replace design copy that would be untrue (see the report).
 */

import { formatJalali } from "@/lib/jalali"
import { currencyLabel, formatMoney, formatMoneyNumber } from "@/lib/money"
import type { VoidRefusal } from "@/lib/order-correction"
import type { EditRefusal } from "@/lib/order-edit"
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
  methodLabel: "روش پرداخت:", // NEW
  allMethods: "همه روش‌ها", // NEW
  inactiveTag: "غیرفعال", // NEW
  unknownMethod: (id: string) => `روش ${toPersianDigits(id)}`, // NEW
  settlementAria: "وضعیت تسویه", // NEW
  settleAll: "همه", // NEW
  settlePending: "تسویه‌نشده", // NEW
  settleSettled: "تسویه‌شده", // NEW
  sheetMethod: "روش پرداخت", // NEW
  sheetSettlement: "وضعیت تسویه", // NEW
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
  get unit() {
    return currencyLabel()
  },

  // ── list: table ──
  colInvoice: "شماره فاکتور",
  colDate: "تاریخ ↓",
  colChannel: "کانال",
  colMethod: "روش پرداخت", // NEW
  colCustomer: "مشتری",
  colStatus: "وضعیت",
  get colTotal() {
    return `مبلغ کل (${currencyLabel()})`
  },
  get colProfit() {
    return `سود (${currencyLabel()})`
  },
  colActions: "عملیات",
  rowActions: "عملیات سفارش",
  viewOrder: "مشاهده سفارش",
  printInvoicePdf: "چاپ فاکتور (PDF)",
  refundOriginal: (n: string) => `فروش اولیه: ${n}`, // NEW

  // ── list: pagination ──
  pageRange: (from: number, to: number, total: number) =>
    `نمایش ${fa(from)} تا ${fa(to)} از ${fa(total)}`, // qty: row counts
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
  segLast30: "۳۰ روز اخیر", // NEW
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

  // ── list: bulk «پرداخت‌شده» → «تکمیل‌شده» (NEW) ──
  selectRow: (invoice: string) => `انتخاب سفارش ${invoice}`, // NEW
  selectShown: "انتخاب همه سفارش‌های نمایش‌داده‌شده", // NEW
  selectShownMobile: "انتخاب همه", // NEW
  bulkSelected: (n: number) => `${fa(n)} سفارش انتخاب شده`, // NEW
  bulkAction: "تغییر به «تکمیل‌شده»", // NEW
  bulkClear: "لغو انتخاب", // NEW
  bulkIneligible: (n: number) =>
    `${fa(n)} سفارش از انتخاب‌ها در وضعیت «پرداخت‌شده» نیست؛ این تغییر فقط برای سفارش‌های پرداخت‌شده ممکن است.`, // NEW
  bulkTooMany: (max: number) => `حداکثر ${fa(max)} سفارش را می‌توان یکجا تغییر داد.`, // NEW
  bulkConfirmTitle: (n: number) => `تکمیل ${fa(n)} سفارش`, // NEW
  bulkConfirmSubtitle: "وضعیت این سفارش‌ها از «پرداخت‌شده» به «تکمیل‌شده» تغییر می‌کند.", // NEW
  bulkConfirmNote: "فقط وضعیت عوض می‌شود؛ موجودی، مبلغ‌ها، تاریخ پرداخت و تسویه تغییری نمی‌کنند.", // NEW
  bulkInvoices: "شماره فاکتورها", // NEW
  bulkConfirm: "تغییر وضعیت", // NEW
  bulkDone: (n: number) => `${fa(n)} سفارش تکمیل شد`, // NEW
  bulkFailed: "تغییر وضعیت انجام نشد؛ دوباره تلاش کنید.", // NEW
  bulkStaleTitle: "هیچ سفارشی تغییر نکرد", // NEW
  bulkStale: (n: number) =>
    `${fa(n)} سفارش دیگر در وضعیت «پرداخت‌شده» نیست. فهرست دوباره خوانده شد؛ انتخاب را از نو انجام دهید.`, // NEW
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
  terminalVoided: "این سفارش باطل شده؛ عملیاتی باقی نمانده.", // NEW
  voidOrder: "باطل‌کردن سفارش", // NEW
  correctOrder: "اصلاح سفارش", // NEW

  // ── detail: items ──
  itemsCard: "اقلام سفارش",
  itemsCaption: (rows: number, units: number) => `${fa(rows)} ردیف · ${fa(units)} عدد`,
  colProduct: "محصول",
  colQty: "تعداد",
  colUnitPrice: "قیمت واحد",
  colDiscount: "تخفیف",
  get colLineTotal() {
    return `جمع (${currencyLabel()})`
  },
  discountReason: (reason: string) => `تخفیف: ${reason}`,
  mobileQty: (qty: number, price: number) => `${formatNumber(qty)} × ${formatMoney(price)}`,
  mobileDiscount: (amount: number, reason: string | null) =>
    `تخفیف ${formatMoney(-amount)}${reason ? ` (${reason})` : ""}`,

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
  payBlock: "پرداخت و تسویه", // NEW
  payMethod: "روش پرداخت", // NEW
  payNone: "بدون روش پرداخت", // NEW
  payRef: "شماره پیگیری", // NEW
  paidDate: "تاریخ پرداخت", // NEW
  expectedDate: "تاریخ مورد انتظار تسویه", // NEW
  settleState: "وضعیت تسویه", // NEW
  unsettled: "تسویه‌نشده", // NEW
  settled: (n: number) => `تسویه‌شده (تسویه شماره ${formatNumber(n)})`, // NEW
  notPaidYet: "هنوز پرداخت نشده", // NEW
  changePaidDate: "تغییر تاریخ پرداخت", // NEW
  paidDateLabel: "تاریخ پرداخت", // NEW
  paidDateHelp: "روزی که مشتری پول را پرداخت کرد؛ تاریخ آینده مجاز نیست.", // NEW
  today: "امروز", // NEW
  paidTitle: (status: string) => `پرداخت شد — تغییر وضعیت به «${status}»؟`, // NEW
  paidBody: "این سفارش حالا پرداخت‌شده حساب می‌شود. روز پرداخت را مشخص کنید؛ تاریخ مورد انتظار تسویه از روی آن حساب می‌شود.", // NEW
  paidConfirm: (status: string) => `ثبت به‌عنوان «${status}»`, // NEW
  changePaidTitle: "تغییر تاریخ پرداخت", // NEW
  changePaidBody: "تاریخ مورد انتظار تسویه و ماه تسویه این سفارش با تاریخ جدید دوباره حساب می‌شوند؛ کارمزد تغییری نمی‌کند.", // NEW
  changePaidConfirm: "ذخیره تاریخ", // NEW
  toastPaidDate: "تاریخ پرداخت تغییر کرد", // NEW
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
    `بسته‌بندی ${formatMoneyNumber(pack)} + پست ${formatMoneyNumber(post)} + کارمزد ${formatMoneyNumber(fee)} ${currencyLabel()}`,

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
  cancelWrongEntry: "اگر این فروش اشتباه ثبت شده، از «باطل‌کردن سفارش» استفاده کنید.", // NEW
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
    `بسته‌بندی ${formatMoneyNumber(pack)} + پست ${formatMoneyNumber(post)} + کارمزد تراکنش ${formatMoneyNumber(fee)} = ${formatMoney(total)}.`,
  effBoxNotReturned: "جعبه مصرف‌شده به موجودی برنمی‌گردد.",
  effRefundMoneyLead: "بازپرداخت پول به مشتری بیرون از برنامه انجام می‌شود.",
  effRefundMoneyBody: "این‌جا مبلغی ثبت نمی‌شود؛ فقط وضعیت سفارش و دلیل آن ذخیره می‌شود.",
  refundReasonLabel: "دلیل مرجوعی",
  refundReasonPlaceholder: "مثلاً: کالا آسیب‌دیده رسید",
  optional: "(اختیاری)",

  // ── void dialog (NEW: accounting-rules section 20) ──
  voidFirstLine: "برای فروشی که اشتباه ثبت شده. اگر مشتری سفارش را لغو کرده، از «لغو سفارش» استفاده کنید.", // NEW
  voidTitle: (inv: string) => `باطل‌کردن سفارش ${inv}؟`, // NEW
  voidSubtitle: "با باطل‌کردن:", // NEW
  voidProductsLead: "کالا به موجودی برمی‌گردد:", // NEW
  voidMaterialsLead: "متریال به موجودی برمی‌گردد:", // NEW
  voidReasonMade: "تولید سفارشی", // NEW
  voidReasonPack: "بسته‌بندی", // NEW
  voidNothingBack: "این سفارش کالا یا متریالی از موجودی کم نکرده بود؛ چیزی برنمی‌گردد.", // NEW
  voidCostLead: "بهای واحد تغییر می‌کند:", // NEW
  voidCost: (name: string, before: number, after: number) => `«${name}» از ${formatMoney(before)} به ${formatMoney(after)}`, // NEW
  voidLegacyLead: "با بهای فعلی برمی‌گردند:", // NEW
  voidLegacyCost: (names: string) =>
    `${names}؛ این سفارش پیش از ثبت بهای زمان فروش روی موجودی ثبت شده، پس بهای این اقلام تغییر نمی‌کند.`, // NEW
  voidReportsBody: (month: string, total: number, profit: number) =>
    `از فروش و سود ${month} حذف می‌شود: مبلغ ${formatMoney(total)}، سود ${formatMoney(profit)}.`, // NEW
  voidFeeLead: "کارمزد زیان حساب نمی‌شود:", // NEW
  voidFeeBody: (fee: number) => `${formatMoney(fee)}؛ این فروش انجام نشده بوده است.`, // NEW
  voidPendingLead: "تسویه:", // NEW
  voidPendingBody: "از تسویه‌های در انتظار خارج می‌شود.", // NEW
  voidKeptLead: "سابقه:", // NEW
  voidKeptBody: "وضعیت سفارش «باطل‌شده» می‌شود؛ خودِ سفارش، اقلام و شماره فاکتورش برای سابقه می‌مانند.", // NEW
  voidReasonLabel: "دلیل باطل‌کردن", // NEW
  voidReasonPlaceholder: "مثلاً: محصول اشتباه ثبت شد", // NEW
  voidReasonHelp: "روی سفارش ذخیره می‌شود.", // NEW
  voidLoading: "در حال بررسی اثر باطل‌کردن…", // NEW
  voidPreviewFailed: "اثر باطل‌کردن خوانده نشد؛ دوباره تلاش کنید.", // NEW
  toastVoided: "سفارش باطل شد", // NEW
  voidRefusal: (r: VoidRefusal): string => {
    switch (r.kind) {
      case "voided":
        return "این سفارش قبلاً باطل شده است."
      case "returned":
        return "برای این سفارش لغو یا مرجوعی ثبت شده؛ باطل‌کردن آن ممکن نیست."
      case "draft":
        return "پیش‌نویس چیزی ثبت نکرده؛ برای کنار گذاشتن آن «لغو سفارش» را بزنید."
      case "settled":
        return r.settlementId == null
          ? "این سفارش در یک تسویه آمده و پولش دریافت شده؛ باطل‌کردن آن ممکن نیست."
          : `این سفارش در تسویهٔ شمارهٔ ${formatNumber(r.settlementId)} آمده و پولش دریافت شده؛ باطل‌کردن آن ممکن نیست.`
      case "closed":
        return `سود تا ${formatJalali(r.periodEnd)} بین شرکا تقسیم شده؛ فروش‌های این روزها دیگر تغییر نمی‌کند.`
      case "stocktake":
        return `«${r.itemName}» بعد از این فروش در شمارش موجودی ${formatJalali(r.stocktakeDate)} شمرده شده است. باطل‌کردن یا اصلاح، کالای این سفارش را به موجودی برمی‌گرداند و آن شمارش دوبار حساب می‌شود. برای تاریخ، روش پرداخت، هزینهٔ ارسال یا پست از «ویرایش سفارش» استفاده کنید.`
      case "reason":
        return "دلیل باطل‌کردن را بنویسید."
    }
  }, // NEW

  // ── voided order and its correction (NEW) ──
  voidedTitle: "این سفارش باطل شده است", // NEW
  voidedWhen: (when: string) => `باطل‌شده در ${when}`, // NEW
  voidedReason: (reason: string) => `دلیل: ${reason}`, // NEW
  voidedNote: "در هیچ گزارش، سود، تسویه یا سهم شرکا حساب نمی‌شود؛ کالای آن به موجودی برگشته است.", // NEW
  replacedByLead: "سفارش جایگزین:", // NEW
  replacesLead: "این سفارش اصلاحِ این فاکتور است:", // NEW
  replacesVoided: "(باطل‌شده)", // NEW

  // ── states ──
  notFoundTitle: (inv: string | null) => (inv ? `سفارش ${inv} پیدا نشد` : "سفارش پیدا نشد"),
  notFoundTitleMobile: "سفارش پیدا نشد",
  notFoundBody:
    "ممکن است نشانی اشتباه باشد یا ارتباط با سرور قطع شده باشد. اگر این سفارش را تازه ثبت کرده‌اید، چند لحظه بعد دوباره تلاش کنید.",
  notFoundBodyMobile: "ممکن است ارتباط قطع شده باشد. دوباره تلاش کنید.",
  backToOrders: "بازگشت به سفارش‌ها",
  // ── light edit «ویرایش سفارش» (NEW) ──
  editOrder: "ویرایش سفارش", // NEW
  editTitle: (inv: string) => `ویرایش سفارش ${inv}`, // NEW
  editSubtitle: "تاریخ، پرداخت، هزینهٔ ارسال، پست، مشتری و یادداشت؛ اقلام و تعداد با «اصلاح سفارش».", // NEW
  editReview: "بررسی تغییرات", // NEW
  editSave: "ذخیره تغییرات", // NEW
  editBack: "بازگشت به فرم", // NEW
  editNoChange: "چیزی تغییر نکرده است.", // NEW
  editLoading: "در حال بررسی اثر تغییرات…", // NEW
  editPreviewFailed: "اثر تغییرات خوانده نشد؛ دوباره تلاش کنید.", // NEW
  editReviewLead: "این تغییرات ذخیره می‌شوند:", // NEW
  editFiguresLead: "اثر روی حساب‌ها:", // NEW
  editBefore: "قبل", // NEW
  editAfter: "بعد", // NEW
  editNone: "—", // NEW
  toastEdited: "سفارش ویرایش شد", // NEW
  editItemsNote: "اقلام، تعداد، قیمت، تخفیف و بسته‌بندی فقط با «اصلاح سفارش» تغییر می‌کنند.", // NEW
  editLockedSettled: "این سفارش تسویه شده؛ تاریخ، روش پرداخت و هزینهٔ ارسال دیگر تغییر نمی‌کنند. هزینهٔ پست، مشتری و یادداشت هنوز قابل ویرایش‌اند.", // NEW
  editLockedStatus: "برای این وضعیت فقط مشتری، شمارهٔ پیگیری و یادداشت قابل ویرایش‌اند.", // NEW
  editPaidFollows: "تاریخ پرداخت هم همراه تاریخ سفارش جابه‌جا شد؛ در صورت نیاز تغییرش دهید.", // NEW
  editOrderDateLabel: "تاریخ سفارش", // NEW
  editMethodLabel: "روش پرداخت", // NEW
  editMethodNone: "بدون روش پرداخت", // NEW
  editMethodHelp: "کارمزد با قانون فعلی این روش دوباره حساب می‌شود.", // NEW
  editReferenceLabel: "شمارهٔ پیگیری پرداخت", // NEW
  editShippingLabel: "هزینهٔ ارسال (از مشتری)", // NEW
  editShippingHelp: "جمع فاکتور و کارمزد تغییر می‌کنند؛ فاکتور را دوباره چاپ کنید.", // NEW
  editPostageLabel: "هزینهٔ پست (هزینهٔ فروشگاه)", // NEW
  editPostageHelp: "فقط سود این سفارش تغییر می‌کند.", // NEW
  editCustomerLabel: "نام مشتری", // NEW
  editNotesLabel: "یادداشت", // NEW
  editFieldName: (field: string): string =>
    ({
      order_date: "تاریخ سفارش",
      payment_method_id: "روش پرداخت",
      transaction_fee: "کارمزد",
      payment_reference: "شمارهٔ پیگیری",
      paid_date: "تاریخ پرداخت",
      shipping_charge: "هزینهٔ ارسال",
      postage_cost: "هزینهٔ پست",
      customer_name: "نام مشتری",
      notes: "یادداشت",
    })[field] ?? field, // NEW
  editFigureName: (figure: string): string =>
    ({
      order_day: "روز فروش در گزارش‌ها",
      customer_total: "جمع فاکتور",
      transaction_fee: "کارمزد",
      profit: "سود سفارش",
      expected_settlement_date: "تاریخ مورد انتظار تسویه",
      paid_date: "تاریخ پرداخت",
      settlement_amount: "مبلغ در انتظار تسویه",
    })[figure] ?? figure, // NEW
  editRefusal: (r: EditRefusal): string => {
    switch (r.kind) {
      case "voided":
        return "این سفارش باطل شده و دیگر ویرایش نمی‌شود."
      case "notAllowed":
        return "در این وضعیت تاریخ و مبلغ‌های سفارش تغییر نمی‌کنند؛ فقط مشتری، شمارهٔ پیگیری و یادداشت."
      case "notPaid":
        return "این سفارش هنوز پرداخت نشده و تاریخ پرداخت ندارد."
      case "settled":
        return r.settlementId == null
          ? "این سفارش تسویه شده؛ تاریخ، روش پرداخت و هزینهٔ ارسال آن دیگر تغییر نمی‌کند."
          : `این سفارش در تسویهٔ شمارهٔ ${formatNumber(r.settlementId)} آمده؛ تاریخ، روش پرداخت و هزینهٔ ارسال آن دیگر تغییر نمی‌کند.`
      case "closed":
        return `سود تا ${formatJalali(r.periodEnd)} بین شرکا تقسیم شده؛ مبلغ و تاریخ فروش‌های این روزها دیگر تغییر نمی‌کند.`
      case "month":
        return r.jalaliYear != null && r.jalaliMonth != null
          ? `ماه ${fa(r.jalaliMonth)}/${fa(r.jalaliYear)} این روش پرداخت تسویه شده؛ تاریخ پرداخت یا روش دیگری انتخاب کنید.`
          : "ماه این تاریخ پرداخت برای این روش تسویه شده؛ تاریخ یا روش دیگری انتخاب کنید."
    }
  }, // NEW
} as const
