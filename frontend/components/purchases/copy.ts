/**
 * Purchases screen copy (design/screens/07-purchases.md §2, verbatim).
 * Strings the design doesn't have are marked // NEW.
 */

import { formatNumber, formatQuantity, toPersianDigits } from "@/lib/persian-numbers"
import { currencyLabel, formatMoney, formatMoneyNumber } from "@/lib/money"

export const U = {
  // toolbar
  search: "جستجوی کالا",
  searchAria: "جستجو",
  typeAll: "همه",
  typeMaterials: "متریال",
  typeServices: "خدمت", // NEW
  typeProducts: "محصولات",
  typeFilterLabel: "نوع کالا", // NEW (aria)
  supplierPrefix: "تأمین‌کننده:",
  supplierAll: "همه",
  add: "ثبت خرید",

  // table
  colDate: "تاریخ",
  colItem: "اقلام", // NEW (was «کالا»: a purchase has several lines)
  colType: "نوع",
  colSupplier: "تأمین‌کننده",
  colQty: "مقدار",
  get colTotal() {
    return `مبلغ فاکتور (${currencyLabel()})` // NEW (was «مبلغ پرداختی»: total_paid is the invoice total)
  },
  colPayStatus: "وضعیت پرداخت", // NEW
  get colOutstanding() {
    return `مانده (${currencyLabel()})` // NEW
  },
  payFilterPrefix: "وضعیت پرداخت:", // NEW
  payFilterAll: "همه", // NEW
  get colUnit() {
    return `بهای واحد (${currencyLabel()})`
  },
  badgeMaterial: "متریال",
  badgeService: "خدمت", // NEW
  badgeProduct: "محصول",
  moreItems: (n: number) => `و ${formatNumber(n)} قلم دیگر`, // NEW
  lineCount: (n: number) => `${formatNumber(n)} قلم`, // NEW
  footerMonth: (month: string, n: number) => `جمع خریدهای ${month} (${formatNumber(n)} مورد)`,
  footerRange: (n: number) => `جمع خریدهای این بازه (${formatNumber(n)} مورد)`, // NEW (range not a whole month)
  noSupplier: "—",
  noMatch: (q: string) => `خریدی با «${q}» پیدا نشد.`, // NEW
  noMatchFiltered: "خریدی با این فیلترها پیدا نشد.", // NEW
  clearFilters: "پاک کردن فیلترها", // NEW

  // drawer / form
  formTitle: "ثبت خرید",
  close: "بستن",
  fieldType: "نوع کالا",
  fieldLines: "اقلام فاکتور", // NEW
  lineTitle: (n: number) => `قلم ${formatNumber(n)}`, // NEW
  addLine: "افزودن قلم", // NEW
  removeLine: "حذف این قلم", // NEW
  fieldItem: "کالا",
  pickItem: "انتخاب کالا یا خدمت", // NEW
  searchItem: "جستجوی کالا، متریال یا خدمت",
  noItems: "کالای فعالی برای خرید نیست.", // NEW
  subMaterial: "متریال", // NEW (the picker's second line)
  subService: "خدمت", // NEW
  subProduct: "محصول", // NEW
  noItemMatch: (q: string) => `کالایی با «${q}» پیدا نشد.`, // NEW
  stockPill: (q: string, unit: string) => `موجودی ${q} ${unit}`,
  stockPillMobile: (q: string, unit: string) => `${q} ${unit}`,
  fieldSupplier: "تأمین‌کننده",
  noSupplierOption: "بدون تأمین‌کننده", // NEW (supplier_id is optional)
  searchSupplier: "جستجوی تأمین‌کننده", // NEW
  noSuppliersYet: "هنوز تأمین‌کننده‌ای ثبت نشده؛ خرید را بدون تأمین‌کننده هم می‌توانید ثبت کنید.", // NEW
  noSupplierMatch: (q: string) => `تأمین‌کننده‌ای با «${q}» پیدا نشد.`, // NEW
  supplierGone: "این تأمین‌کننده دیگر در دسترس نیست — لطفاً دوباره انتخاب کنید",
  fieldQty: "مقدار",
  fieldLineTotal: "مبلغ این قلم", // NEW
  fieldTotal: "مبلغ فاکتور", // NEW (was «مبلغ کل پرداختی»): the sum of the lines
  invoiceTotalHelp: "جمع مبلغ اقلام؛ پرداخت و بدهی بر پایهٔ همین مبلغ است.", // NEW
  serviceHelp: "هزینهٔ خدمت از راه تولید و ضایعات به سود و زیان می‌رسد؛ همین فاکتور را در هزینه‌ها ثبت نکنید.", // NEW
  fieldPayment: "پرداخت", // NEW
  payFull: "پرداخت کامل", // NEW
  payNone: "نسیه", // NEW
  payPartial: "پرداخت بخشی", // NEW
  fieldPaidAmount: "مبلغ پرداخت‌شده", // NEW
  fieldMethod: "روش پرداخت", // NEW
  searchMethod: "جستجوی روش پرداخت", // NEW
  fieldReference: "شماره پیگیری", // NEW
  creditHelp: "مانده را بعداً از «تسویه‌ها ← بدهی به تأمین‌کنندگان» پرداخت کنید.", // NEW
  supplierRequired: "برای خرید نسیه یا پرداخت بخشی، تأمین‌کننده را انتخاب کنید", // NEW
  partialRange: "مبلغ پرداخت‌شده باید بیشتر از صفر و کمتر از مبلغ فاکتور باشد.", // NEW
  get unit() {
    return currencyLabel()
  },
  fieldDate: "تاریخ خرید",
  fieldDateMobile: "تاریخ",
  today: "امروز",
  fieldNote: "یادداشت",
  optional: "(اختیاری)",
  notePlaceholder: "مثلاً: شماره فاکتور تأمین‌کننده",
  submit: "ثبت خرید",
  cancel: "انصراف",
  itemRequired: "کالا را انتخاب کنید.", // NEW
  duplicateItem: "این کالا قبلاً در همین فاکتور آمده است؛ مقدارها را در یک قلم جمع کنید.", // NEW
  qtyRequired: "مقدار باید بیشتر از صفر باشد.", // NEW
  qtyInteger: "تعداد محصول باید عدد صحیح باشد.", // NEW
  totalInvalid: "مبلغ را دقیق وارد کنید.", // NEW
  serviceTotal: "مبلغ خدمت باید بیشتر از صفر باشد؛ بهای هر واحد خدمت از همین مبلغ ساخته می‌شود.", // NEW
  totalZero: "مبلغ صفر است؛ میانگین بهای این کالا پایین می‌آید.", // NEW
  saveFailed: "ثبت نشد", // NEW
  errorCode: "کد خطا:", // NEW

  // preview (one per line)
  previewTitle: "پیش‌نمایش بهای تمام‌شده",
  previewUnit: "بهای واحد این قلم", // NEW
  previewAvg: "میانگین جدید", // NEW
  previewService: "قیمت جدید خدمت", // NEW
  previewServiceFrom: (name: string, now: string, after: string) => `قیمت «${name}» از ${now} به ${after}`, // NEW
  previewServiceNote: (name: string) => `تولیدها و ضایعات بعدی «${name}» با قیمت جدید محاسبه می‌شوند؛ گذشته تغییر نمی‌کند.`, // NEW
  servicePriceNotEntered: "ثبت نشده", // NEW
  unitThis: "بهای واحد این خرید",
  avgNow: "میانگین فعلی",
  avgAfter: "میانگین پس از خرید",
  inStock: (q: string, unit: string) => `${q} ${unit} در انبار`,
  avgNowMobile: (q: string) => `میانگین فعلی (${q})`,
  avgAfterMobile: (q: string) => `میانگین پس از خرید (${q})`,
  formula: (stock: number, cost: number, total: number, after: number) =>
    `میانگین موزون = (${formatQuantity(stock)} × ${formatMoneyNumber(cost)} + ${formatMoneyNumber(total)}) ÷ ${formatQuantity(after)}`,
  formulaMobile: (stock: number, cost: number, total: number, after: number) =>
    `(${formatQuantity(stock)} × ${formatMoneyNumber(cost)} + ${formatMoneyNumber(total)}) ÷ ${formatQuantity(after)}`,
  firstPurchase: "اولین خرید — میانگین قبلی ندارد؛ میانگین = بهای واحد این خرید.", // NEW
  noStockNow: "موجودی فعلی صفر است؛ میانگین = بهای واحد این خرید.", // NEW
  noCost: "—",
  noteMaterial: (name: string) => `تولیدهای بعدی «${name}» با بهای جدید محاسبه می‌شوند؛ تولیدهای گذشته تغییر نمی‌کنند.`,
  noteProduct: (name: string) => `فروش‌های بعدی «${name}» با بهای جدید محاسبه می‌شوند؛ فروش‌های گذشته تغییر نمی‌کنند.`, // NEW
  previewNote: "پیش‌نمایش است؛ میانگین نهایی پس از ثبت از سرور خوانده می‌شود.", // NEW
  pickToPreview: "کالا، مقدار و مبلغ را وارد کنید تا بهای جدید را ببینید.", // NEW

  // after save
  toastSaved: (name: string, avg: number | null) =>
    avg == null ? `خرید «${name}» ثبت شد` : `خرید ثبت شد · میانگین جدید «${name}»: ${formatMoney(avg)}`, // NEW
  toastSavedLines: (invoice: string | null, n: number) =>
    invoice ? `خرید ${invoice} ثبت شد (${formatNumber(n)} قلم)` : `خرید ثبت شد (${formatNumber(n)} قلم)`, // NEW

  // mobile
  recent: "خریدهای اخیر",
  recentMeta: (date: string, qty: string, supplier: string | null) =>
    supplier ? `${date} · ${qty} · ${supplier}` : `${date} · ${qty}`,

  // detail sheet
  detailTitle: "جزئیات خرید", // NEW
  detailInvoice: "شماره خرید", // NEW
  detailDate: "تاریخ", // NEW
  detailSupplier: "تأمین‌کننده", // NEW
  detailQty: "مقدار", // NEW
  detailLines: "اقلام", // NEW
  detailLineTotal: "مبلغ", // NEW
  detailTotal: "مبلغ فاکتور", // NEW
  detailPaymentStatus: "وضعیت پرداخت", // NEW
  detailPaid: "پرداخت‌شده", // NEW
  detailOutstanding: "مانده", // NEW
  detailPayments: "پرداخت‌ها", // NEW
  noPayments: "هنوز پرداختی برای این خرید ثبت نشده.", // NEW
  paymentOfWhole: (whole: string) => `از پرداخت ${whole}`, // NEW (a payment split over several purchases)
  detailUnit: "بهای واحد این خرید", // NEW
  detailNote: "یادداشت", // NEW
  detailLoadFailed: "جزئیات این خرید بارگذاری نشد.", // NEW

  // states
  emptyTitle: "هنوز خریدی ثبت نشده",
  emptyBody: "خرید متریال، بسته‌بندی یا محصولات آماده را ثبت کنید تا موجودی و بهای تمام‌شده خودکار به‌روز شود.",
  emptyBodyMobile: "خریدها موجودی و بهای تمام‌شده را به‌روز می‌کنند.",
  emptyCta: "ثبت اولین خرید",
  errorTitle: "فهرست خریدها بارگذاری نشد",
  errorTitleMobile: "خریدها بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",
  loadingAria: "در حال بارگذاری",
  units: (n: number) => toPersianDigits(n),
}

/** db/supplier_payments.py METHODS (not the sales payment methods). // NEW */
export const METHOD_LABELS = {
  CASH: "نقدی",
  CARD: "کارت به کارت",
  BANK_TRANSFER: "حواله بانکی",
  CHEQUE: "چک",
  OTHER: "سایر",
} as const

export const METHOD_ORDER = ["CARD", "CASH", "BANK_TRANSFER", "CHEQUE", "OTHER"] as const

/** A purchase's payment_status (computed by db/supplier_payments.py). // NEW */
export const PAY_STATUS_LABELS = {
  UNPAID: "پرداخت‌نشده",
  PARTIAL: "پرداخت بخشی",
  PAID: "پرداخت‌شده",
} as const
