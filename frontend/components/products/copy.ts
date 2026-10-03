/**
 * Persian copy for products & materials (design/screens/05-products-materials.md
 * §2), verbatim. Strings marked NEW are not in the design: they cover what the
 * live backend can and can't do (see the report).
 */

import { currencyLabel, formatMoney } from "@/lib/money"
import { formatNumber, toPersianDigits } from "@/lib/persian-numbers"

const fa = toPersianDigits

export const P = {
  // toolbar
  searchPlaceholder: "جستجوی نام",
  searchAria: "جستجو",
  categoryLabel: "دسته:",
  categoryAll: "همه",
  showInactive: "نمایش غیرفعال‌ها",
  addMaterial: "اضافه کردن متریال",
  addProduct: "اضافه کردن محصول",

  // tabs
  tabProducts: "محصولات",
  tabMaterials: "متریال",

  // banner (computed; the design's string for one product, a count for more)
  bannerOne: "۱ محصول بدون بهای تمام‌شده",
  bannerOneRest: (name: string) => ` — «${name}» تا تعیین بها قابل فروش نیست.`,
  bannerMany: (n: number) => `${fa(n)} محصول بدون بهای تمام‌شده`, // NEW
  bannerManyRest: " — تا تعیین بها قابل فروش نیستند.", // NEW
  // NEW: no endpoint sets a cost; it comes from a purchase or production run.
  bannerPurchase: "ثبت خرید",
  bannerProduction: "برنامه تولید",

  // products table
  colName: "نام محصول",
  colCategory: "دسته",
  colStock: "موجودی",
  get colCost() {
    return `بهای تمام‌شده (${currencyLabel()})`
  },
  get colRetail() {
    return `قیمت خرده (${currencyLabel()})`
  },
  get colWholesale() {
    return `قیمت عمده (${currencyLabel()})`
  },
  colStatus: "وضعیت",
  colActions: "عملیات",
  outOfStock: "ناموجود",
  stockUnits: (n: number) => `${formatNumber(n)} عدد`,
  noCost: "بدون بهای تمام‌شده",
  fromRecipe: "هنگام فروش از دستور تولید", // NEW
  // NEW: an estimate only — the real cost is frozen again at the moment of sale.
  recipeEstimate: (n: number) => `برآورد: ${formatMoney(n)} (بر اساس بهای فعلی متریال)`,
  madeToOrder: "ساخت هنگام فروش", // NEW
  active: "فعال",
  inactive: "غیرفعال",
  edit: "ویرایش",
  deactivate: "غیرفعال کردن",
  reactivate: "فعال کردن دوباره", // NEW
  productsFootnote:
    "بهای تمام‌شده میانگین موزون است و از «تولید» و «خرید» به‌روز می‌شود. محصولات حذف نمی‌شوند؛ غیرفعال‌سازی سوابق فروش را حفظ می‌کند.",

  // materials table
  colMatName: "نام",
  colType: "نوع",
  colUnit: "واحد",
  get colUnitCost() {
    return `بهای واحد (${currencyLabel()})`
  },
  get colValue() {
    return `ارزش موجودی (${currencyLabel()})`
  },
  typeStock: "کالایی",
  typeService: "خدماتی",
  noStock: "بدون موجودی",
  materialsFootnote:
    "«خدماتی» (مثل مسترینگ یا چاپ سیلک) موجودی ندارد و فقط هزینه‌اش در تولید حساب می‌شود. مقدار متریال می‌تواند اعشاری باشد (۱٫۵ کیلوگرم).",

  // mobile cards
  stockPillMobile: (n: number) => `موجودی ${formatNumber(n)}`,
  priceLine: (retail: number, wholesale: number) =>
    `خرده ${formatMoney(retail)} · عمده ${formatMoney(wholesale)}`,
  costLine: (cost: number) => `بهای تمام‌شده ${formatMoney(cost)}`,
  costLineMissing: "بدون بهای تمام‌شده — قابل فروش نیست",
  rowActions: "عملیات", // NEW

  // product drawer
  addProductTitle: "اضافه کردن محصول", // NEW (design only drew the edit drawer)
  editProductTitle: "ویرایش محصول",
  close: "بستن",
  fieldName: "نام محصول",
  fieldCategory: "دسته",
  pickCategory: "انتخاب دسته", // NEW
  noCategory: "بدون دسته", // NEW
  categoryHasChildren: "این دسته زیردسته دارد؛ یکی از زیردسته‌ها را انتخاب کنید.", // NEW
  categoryUnavailable: "این دسته دیگر قابل انتخاب نیست؛ صفحه را دوباره بارگذاری کنید.", // NEW
  colMatCategory: "دسته", // NEW
  fieldRetail: "قیمت خرده",
  fieldWholesale: "قیمت عمده",
  get toman() {
    return currencyLabel()
  },
  fieldCost: "بهای تمام‌شده",
  costMissingErr: "این محصول بهای تمام‌شده ندارد و تا ثبت آن قابل فروش نیست.",
  // NEW: replaces the design's editable «بهای تمام‌شده اولیه» — no endpoint sets it.
  costHelp:
    "بهای تمام‌شده با «خرید» یا «تولید» ثبت می‌شود و پس از آن به‌صورت میانگین موزون به‌روز می‌شود.",
  costFromRecipeHelp:
    "این محصول هنگام فروش از دستور تولید ساخته می‌شود؛ بهای هر فروش همان لحظه از دستور تولید حساب می‌شود.", // NEW
  fieldStock: "موجودی فعلی",
  stockHelp: "فقط از تولید، خرید، فروش و تعدیل تغییر می‌کند.",
  readOnlyNote: "نام پس از ثبت قابل تغییر نیست.", // NEW (no endpoint edits it)
  fieldMadeToOrder: "ساخت هنگام فروش", // NEW
  madeToOrderHelp: "موجودی آماده نگه داشته نمی‌شود؛ هر فروش از دستور تولید ساخته می‌شود.", // NEW
  madeToOrderCreateHelp:
    "تا دستور تولید این محصول در «تولید» تعریف نشود، قابل فروش نیست.", // NEW
  madeToOrderNoRecipe:
    "این محصول دستور تولید ندارد؛ ابتدا در «تولید» دستور تولید آن را تعریف کنید.", // NEW
  wholesaleAboveRetail: "قیمت عمده از قیمت خرده بیشتر است.", // NEW (soft warning)
  nameRequired: "نام را وارد کنید.", // NEW
  categoryRequired: "دسته را انتخاب کنید.", // NEW
  save: "ذخیره",
  cancel: "انصراف",
  saveFailed: "ذخیره انجام نشد", // NEW
  errorCode: "کد خطا:",

  // material drawer
  addMaterialTitle: "اضافه کردن متریال", // NEW
  fieldMatName: "نام",
  fieldType: "نوع",
  typeStockSeg: "کالایی — موجودی دارد",
  typeServiceSeg: "خدماتی — بدون موجودی",
  typeHelp: "خدماتی مثل مسترینگ، طراحی یا چاپ سیلک: فقط هزینه دارد و موجودی نگه داشته نمی‌شود.",
  fieldUnit: "واحد",
  fieldUnitCost: "بهای واحد",
  unitCostHelp: "میانگین موزون خریدها",
  fieldInitialStock: "موجودی اولیه", // NEW
  initialStockHelp: "می‌تواند اعشاری باشد (۱٫۵). خالی یعنی صفر.", // NEW
  invalidQuantity: "مقدار معتبر وارد کنید.", // NEW

  // deactivate dialog
  deactivateTitle: (name: string) => `غیرفعال کردن «${name}»؟`,
  deactivateSubtitle: "محصولات حذف نمی‌شوند تا سوابق حفظ شود.",
  effHidden: "از فهرست انتخاب محصول در «ثبت فروش» و «تولید» پنهان می‌شود.",
  effHistory: "سفارش‌ها، گزارش‌ها و تاریخچه موجودی آن دست‌نخورده می‌مانند.",
  effStock: (stock: number) => `موجودی فعلی (${formatNumber(stock)} عدد) باقی می‌ماند و در ارزش انبار حساب می‌شود.`,
  deactivateFinal: "هر زمان با روشن کردن «نمایش غیرفعال‌ها» می‌توانید دوباره فعالش کنید.",
  matDeactivateSubtitle: "متریال حذف نمی‌شود تا سوابق حفظ شود.", // NEW
  matEffHidden: "از فهرست انتخاب متریال در «خرید»، دستور تولید و کیت‌های بسته‌بندی پنهان می‌شود.", // NEW
  matEffStock: (stock: string) => `موجودی فعلی (${stock}) باقی می‌ماند.`, // NEW

  // toasts (NEW)
  toastProductAdded: (name: string) => `«${name}» اضافه شد`,
  toastMaterialAdded: (name: string) => `«${name}» اضافه شد`,
  toastSaved: "تغییرات ذخیره شد",
  toastDeactivated: (name: string) => `«${name}» غیرفعال شد`,
  toastReactivated: (name: string) => `«${name}» دوباره فعال شد`,

  // states
  emptyTitle: "هنوز محصولی تعریف نشده",
  emptyBody: "اولین محصول را با دسته، قیمت خرده و قیمت عمده تعریف کنید. بهای تمام‌شده از تولید یا خرید محاسبه می‌شود.",
  emptyBodyMobile: "اولین محصول را تعریف کنید.",
  emptyCta: "اضافه کردن اولین محصول",
  emptyCtaMobile: "اضافه کردن محصول",
  emptyMatTitle: "هنوز متریالی تعریف نشده", // NEW
  emptyMatBody: "متریال، بسته‌بندی و خدمات تولید را این‌جا تعریف کنید.", // NEW
  emptyMatCta: "اضافه کردن اولین متریال", // NEW
  noProductMatch: (q: string) => `محصولی با «${q}» پیدا نشد.`,
  noMaterialMatch: (q: string) => `متریالی با «${q}» پیدا نشد.`, // NEW
  noMatchFiltered: "با این فیلترها چیزی پیدا نشد.", // NEW
  clearFilters: "پاک کردن فیلترها",
  errorTitle: "فهرست محصولات و متریال بارگذاری نشد",
  errorTitleMobile: "محصولات بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",
  loadingAria: "در حال بارگذاری",
} as const
