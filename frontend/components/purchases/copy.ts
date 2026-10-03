/**
 * Purchases screen copy (design/screens/07-purchases.md §2, verbatim).
 * Strings the design doesn't have are marked // NEW.
 */

import { formatMoney, formatNumber, formatQuantity, toPersianDigits } from "@/lib/persian-numbers"

export const U = {
  // toolbar
  search: "جستجوی کالا",
  searchAria: "جستجو",
  typeAll: "همه",
  typeMaterials: "متریال",
  typeProducts: "محصولات",
  typeFilterLabel: "نوع کالا", // NEW (aria)
  supplierPrefix: "تأمین‌کننده:",
  supplierAll: "همه",
  add: "ثبت خرید",

  // table
  colDate: "تاریخ",
  colItem: "کالا",
  colType: "نوع",
  colSupplier: "تأمین‌کننده",
  colQty: "مقدار",
  colTotal: "مبلغ پرداختی (تومان)",
  colUnit: "بهای واحد (تومان)",
  badgeMaterial: "متریال",
  badgeProduct: "محصول",
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
  segMaterial: "متریال یا بسته‌بندی",
  segProduct: "محصول آماده",
  fieldItem: "کالا",
  pickItem: "انتخاب کالا", // NEW
  searchItem: "جستجوی کالا",
  noItems: "کالای فعالی برای خرید نیست.", // NEW
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
  fieldTotal: "مبلغ کل پرداختی",
  toman: "تومان",
  fieldDate: "تاریخ خرید",
  fieldDateMobile: "تاریخ",
  today: "امروز",
  fieldNote: "یادداشت",
  optional: "(اختیاری)",
  notePlaceholder: "مثلاً: شماره فاکتور تأمین‌کننده",
  submit: "ثبت خرید",
  cancel: "انصراف",
  itemRequired: "کالا را انتخاب کنید.", // NEW
  qtyRequired: "مقدار باید بیشتر از صفر باشد.", // NEW
  qtyInteger: "تعداد محصول باید عدد صحیح باشد.", // NEW
  totalZero: "مبلغ صفر است؛ میانگین بهای این کالا پایین می‌آید.", // NEW
  saveFailed: "ثبت نشد", // NEW
  errorCode: "کد خطا:", // NEW

  // preview
  previewTitle: "پیش‌نمایش بهای تمام‌شده",
  unitThis: "بهای واحد این خرید",
  avgNow: "میانگین فعلی",
  avgAfter: "میانگین پس از خرید",
  inStock: (q: string, unit: string) => `${q} ${unit} در انبار`,
  avgNowMobile: (q: string) => `میانگین فعلی (${q})`,
  avgAfterMobile: (q: string) => `میانگین پس از خرید (${q})`,
  formula: (stock: number, cost: number, total: number, after: number) =>
    `میانگین موزون = (${formatQuantity(stock)} × ${formatNumber(cost)} + ${formatNumber(total)}) ÷ ${formatQuantity(after)}`,
  formulaMobile: (stock: number, cost: number, total: number, after: number) =>
    `(${formatQuantity(stock)} × ${formatNumber(cost)} + ${formatNumber(total)}) ÷ ${formatQuantity(after)}`,
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
  detailTotal: "مبلغ پرداختی", // NEW
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
