/**
 * Production screen copy (design/screens/06-production.md §2, verbatim).
 * Strings the design doesn't have are marked // NEW.
 */

import { formatMoney, formatNumber, formatQuantity } from "@/lib/persian-numbers"

export const R = {
  // tabs
  tabRun: "اجرای تولید",
  tabRecipe: "دستور تولید",
  tabHistory: "سوابق تولید",
  segRun: "اجرا",
  segRecipe: "دستور",
  segHistory: "سوابق",
  tabsLabel: "بخش‌های تولید", // NEW

  // run form
  formTitle: "تولید جدید",
  fieldProduct: "محصول",
  productHelp: "فقط محصولاتی که دستور تولید دارند.",
  pickProduct: "انتخاب محصول", // NEW
  searchProduct: "جستجوی محصول", // NEW
  noProductsWithRecipe: "هنوز هیچ محصولی دستور تولید ندارد.", // NEW
  noProductMatch: (q: string) => `محصولی با «${q}» پیدا نشد.`,
  stockPill: (n: number) => `موجودی ${formatNumber(n)}`,
  fieldQty: "تعداد تولید",
  qtyHelpMaxPrefix: "عدد صحیح؛ حداکثر با موجودی فعلی مواد: ",
  qtyHelpUnbounded: "عدد صحیح؛ مواد کالایی این دستور محدودیتی ایجاد نمی‌کنند.", // NEW (design printed «∞»)
  qtyMin: "تعداد تولید باید دست‌کم ۱ باشد.", // NEW
  fieldDate: "تاریخ تولید",
  today: "امروز",
  fieldNote: "یادداشت",
  optional: "(اختیاری)",
  notePlaceholder: "مثلاً: پرس نوبت دوم",

  // preview
  previewTitle: "پیش‌نمایش مصرف مواد",
  previewCaption: (n: number, name: string) => `${formatNumber(n)} عدد «${name}»`,
  editRecipe: "ویرایش دستور",
  colMaterial: "متریال",
  colBasis: "نحوه محاسبه",
  colNeed: "مقدار لازم",
  colStock: "موجودی",
  colAfter: "پس از تولید",
  colCost: "هزینه (تومان)",
  perUnit: "به ازای هر عدد",
  perBatch: "یک‌بار برای کل تولید",
  service: "خدماتی",
  shortCell: (q: number) => `کمبود ${formatQuantity(q)}`,
  totalLabel: "هزینه کل این تولید",
  unitTile: "بهای هر عدد در این تولید",
  unitTileDerivation: (n: number) => `هزینه کل ÷ ${formatNumber(n)}`,
  avgTile: (name: string) => `میانگین بهای تمام‌شده «${name}»`,
  avgFormula: (stock: number, cost: number, total: number, after: number) =>
    `(${formatNumber(stock)} عدد × ${formatNumber(cost)} + ${formatNumber(total)}) ÷ ${formatNumber(after)} عدد`,
  avgNoCost: "بهای ثبت‌شده ندارد", // NEW
  avgFirstCost: "اولین بها؛ میانگین = بهای هر عدد این تولید", // NEW
  avgNoStock: "موجودی فعلی صفر است؛ میانگین = بهای هر عدد این تولید", // NEW
  previewNote: "پیش‌نمایش بر اساس بهای فعلی مواد است؛ بهای نهایی از پاسخ ثبت می‌آید.", // NEW
  submit: (n: number) => `ثبت تولید ${formatNumber(n)} عدد`,
  submitNote: (n: number) => `مواد کالایی از موجودی کم و ${formatNumber(n)} عدد به موجودی محصول اضافه می‌شود.`,
  pickToPreview: "محصولی را انتخاب کنید تا مصرف مواد و بهای تولید را ببینید.", // NEW
  recipeLoading: "در حال بررسی دستور تولید…", // NEW
  recipeFailed: "دستور تولید بارگذاری نشد؛ ثبت تولید را سرور بررسی می‌کند.", // NEW
  noRecipeTitle: "این محصول دستور تولید ندارد", // NEW
  noRecipeBody: "تا وقتی دستور تولید تعریف نشده، تولید آن ممکن نیست.", // NEW
  makeRecipe: "ساخت دستور تولید",

  // shortage
  shortTitle: "کمبود مواد — تولید ممکن نیست",
  shortTitleMobile: "کمبود مواد",
  shortLine: (q: number, unit: string, name: string) => `${formatQuantity(q)} ${unit} «${name}» کم است.`,
  shortTail: (n: number) => `حداکثر قابل تولید با موجودی فعلی: ${formatNumber(n)} عدد.`,
  shortTailMobile: (n: number) => `حداکثر قابل تولید: ${formatNumber(n)}.`,
  buyMaterials: "ثبت خرید مواد",
  produceMax: (n: number) => `تولید ${formatNumber(n)} عدد`,
  serverShortTitle: "موجودی مواد تغییر کرده — تولید ثبت نشد", // NEW
  serverShortLine: (name: string, needed: number, available: number, unit: string) =>
    `«${name}»: لازم ${formatQuantity(needed)} ${unit}، موجود ${formatQuantity(available)} ${unit}.`, // NEW

  // after run
  toastRun: (n: number, name: string, unitCost: number) =>
    `تولید ${formatNumber(n)} عدد «${name}» ثبت شد — بهای هر عدد: ${formatMoney(unitCost)}`, // NEW
  saveFailed: "ثبت نشد", // NEW
  errorCode: "کد خطا:", // NEW

  // mobile run
  mobileSection: "مصرف مواد",
  mobileLineNeed: (basis: string, need: string, stock: string | null) =>
    stock == null ? `${basis} · لازم ${need}` : `${basis} · لازم ${need} · موجودی ${stock}`,
  mobileTotal: "هزینه کل",
  mobileUnit: "بهای هر عدد",
  mobileAvg: "میانگین بها",

  // recipe tab
  listLabel: "محصولات",
  itemCount: (n: number) => `${formatNumber(n)} متریال`,
  noRecipeBadge: "بدون دستور",
  editorTitle: (name: string) => `دستور تولید: ${name}`,
  editorCaption: "هر تغییر همان لحظه ذخیره می‌شود.", // NEW (the API saves line by line; no «ذخیره دستور»)
  colLineMaterial: "متریال یا خدمت",
  colLineQty: "مقدار",
  colLineBasis: "نحوه محاسبه",
  colLineCost: "هزینه",
  lineSub: (service: boolean, cost: number, unit: string) =>
    `${service ? "خدماتی" : "کالایی"} · ${formatNumber(cost)} تومان / ${unit}`,
  lineCostPerUnit: (cost: number) => `${formatNumber(cost)} × تعداد`,
  lineCostOnce: (cost: number) => `${formatNumber(cost)} یک‌بار`,
  deleteLine: "حذف",
  addLine: "افزودن متریال یا خدمت",
  searchMaterial: "جستجوی متریال یا خدمت", // NEW
  noMaterialsLeft: "همه مواد فعال در این دستور هستند.", // NEW
  noMaterialMatch: (q: string) => `متریالی با «${q}» پیدا نشد.`, // NEW
  explainTitle: "«به ازای هر عدد» یا «یک‌بار برای کل تولید»؟",
  explainPerUnit: "به ازای هر عدد",
  explainPerUnitBody: ": مقدار در تعداد تولید ضرب می‌شود — هر وینیل یک «صفحه خام» لازم دارد. ",
  explainPerBatch: "یک‌بار برای کل تولید",
  explainPerBatchBody:
    ": هزینه‌ای که هر نوبت تولید فقط یک بار پرداخت می‌شود، مثل مسترینگ یا طراحی جلد. هرچه تعداد تولید بیشتر باشد، سهم این هزینه در هر عدد کمتر است.",
  tilePerUnit: "هزینه به ازای هر عدد",
  tilePerBatch: "هزینه یک‌بار برای هر تولید",
  tileAt: "بهای هر عدد در تولید ۳۰ / ۱۰۰ عددی",
  emptyRecipe: "این محصول هنوز دستور تولید ندارد. اولین متریال یا خدمت را اضافه کنید.", // NEW
  qtyInvalid: "مقدار باید بیشتر از صفر باشد.", // NEW
  duplicateLine: "این متریال در دستور هست.", // NEW
  lastLineWarnTitle: "حذف آخرین ردیف دستور", // NEW
  lastLineWarn: "این محصول «ساخت هنگام فروش» است؛ بدون دستور تولید، فروش آن ثبت نمی‌شود.", // NEW
  lastLineConfirm: "حذف کن", // NEW
  cancel: "انصراف",
  inactiveMaterial: "غیرفعال", // NEW
  noProducts: "هنوز محصول فعالی تعریف نشده.", // NEW

  // history
  filterProduct: "محصول:",
  filterAll: "همه",
  colDate: "تاریخ",
  colProduct: "محصول",
  colQty: "تعداد",
  colUnitCost: "بهای هر عدد (تومان)",
  colNote: "یادداشت",
  historyNoMatch: "تولیدی با این فیلترها پیدا نشد.", // NEW
  clearFilters: "پاک کردن فیلترها", // NEW
  historyFootnote: "هزینه کل هر تولید در جزئیات آن آمده است.", // NEW
  qtyUnits: (n: number) => `${formatNumber(n)} عدد`,

  // batch detail
  batchTitle: "جزئیات تولید", // NEW
  batchFacts: (n: number) => `${formatNumber(n)} عدد`,
  batchUnitCost: "بهای هر عدد", // NEW
  batchMaterials: "مواد مصرف‌شده", // NEW
  colUsed: "مقدار مصرف", // NEW
  colUnitCostAt: "بهای واحد در زمان تولید", // NEW
  colLineTotal: "هزینه", // NEW
  close: "بستن",
  batchLoadFailed: "جزئیات این تولید بارگذاری نشد.", // NEW

  // states
  emptyTitle: "هنوز تولیدی ثبت نشده",
  emptyBody:
    "ابتدا برای یک محصول «دستور تولید» بسازید: مواد، مقدار و این‌که هر متریال به ازای هر عدد مصرف می‌شود یا یک‌بار برای کل تولید.",
  emptyBodyMobile: "ابتدا دستور تولید یک محصول را بسازید.",
  errorTitle: "اطلاعات تولید بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",
  loadingAria: "در حال بارگذاری",
}
