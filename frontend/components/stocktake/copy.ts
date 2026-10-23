import { formatNumber, formatQuantity } from "@/lib/persian-numbers"

/** «شمارش موجودی» copy. `// NEW` = not in the design files (there is no design for this screen). */
export const S = {
  title: "شمارش موجودی", // NEW
  intro: "تعداد واقعی هر کالا را بشمارید و وارد کنید؛ کالاهای خالی شمرده‌نشده حساب می‌شوند و تغییری نمی‌کنند.", // NEW
  pauseTitle: "تا پایان شمارش، فروش و تعدیل موجودی را متوقف کنید", // NEW
  pauseBody:
    "اگر در حین شمارش موجودی سیستم تغییر کند، ردیف‌های تغییرکرده علامت می‌خورند؛ شمارش‌تان نگه داشته می‌شود ولی باید دوباره بررسی شود.", // NEW

  tabProducts: "محصولات", // NEW
  tabMaterials: "متریال", // NEW
  tabsLabel: "نوع کالا", // NEW

  fieldDate: "تاریخ شمارش", // NEW
  fieldNote: "یادداشت (اختیاری)", // NEW
  notePlaceholder: "مثلاً: قفسه ۲", // NEW
  search: "جستجوی نام", // NEW
  allCategories: "همهٔ دسته‌ها", // NEW
  onlyDifferences: "فقط تفاوت‌ها", // NEW
  showInactive: "نمایش غیرفعال‌ها", // NEW
  clearDraft: "پاک کردن پیش‌نویس", // NEW
  clearDraftConfirm: "همهٔ شمارش‌های واردشده پاک شود؟", // NEW
  clearDraftYes: "پاک کن", // NEW
  keep: "نگه دار", // NEW

  colName: "نام", // NEW
  colCategory: "دسته", // NEW
  colUnit: "واحد", // NEW
  colSystem: "موجودی سیستم", // NEW
  colCounted: "شمارش‌شده", // NEW
  colDiff: "تفاوت", // NEW
  colCost: "بهای واحد", // NEW
  countedAria: (name: string) => `شمارش ${name}`, // NEW
  costPlaceholderRequired: "بها لازم است", // NEW
  costPlaceholderOptional: "بهای فعلی", // NEW
  costPrefilled: "بها از دستور تولید پر شده (برآورد)؛ قابل ویرایش است.", // NEW
  costZeroWarning: "بهای این متریال ثبت نشده (۰) است؛ بدون وارد کردن بها، بهای آن صفر می‌ماند.", // NEW
  costRequired:"برای موجودی اضافه‌شده بهای واحد لازم است.", // NEW
  costInvalid: "بهای واحد معتبر نیست.", // NEW
  noCost: "بدون بها", // NEW
  inactive: "غیرفعال", // NEW
  invalidFormat: "عدد معتبر نیست؛ فقط رقم و ممیز (٫ یا .).", // NEW
  invalidAmbiguous: "ویرگول یا / مبهم است؛ از ٫ یا . برای اعشار استفاده کنید.", // NEW
  invalidNotWhole: "تعداد محصول باید عدد صحیح باشد.", // NEW
  invalidTooLarge: "این عدد بیش از حد بزرگ است.", // NEW
  moved: "موجودی سیستم تغییر کرده؛ شمارش را دوباره بررسی کنید.", // NEW
  recheck: "شمارش درست است", // NEW
  recheckNeeded: "ردیف‌های علامت‌خورده را بررسی کنید.", // NEW

  progress: (counted: number, of: number, diffs: number) =>
    `${formatNumber(counted)} از ${formatNumber(of)} شمرده شد · ${formatNumber(diffs)} تفاوت`, // NEW
  noRows: "کالایی برای نمایش نیست.", // NEW
  noMatch: "کالایی با این فیلتر پیدا نشد.", // NEW
  clearFilters: "پاک کردن فیلترها", // NEW
  nothingCounted: "هنوز چیزی شمرده نشده.", // NEW

  review: "بازبینی و اعمال", // NEW
  reviewCount: (n: number) => `بازبینی و اعمال (${formatNumber(n)} مورد)`, // NEW
  reviewing: "در حال بررسی…", // NEW
  invalidRows: (n: number) => `${formatNumber(n)} ردیف شمارش نامعتبر دارد.`, // NEW

  dialogTitle: "تأیید اصلاح‌ها", // NEW
  dialogLead: (n: number, same: number) =>
    `${formatNumber(n)} اصلاح ثبت می‌شود${same ? ` · ${formatNumber(same)} مورد بدون تفاوت` : ""}.`, // NEW
  dialogNote: (note: string) => `یادداشت ثبت‌شده روی هر اصلاح: ${note}`, // NEW
  dialogNothing: "هیچ تفاوتی نیست؛ چیزی ثبت نمی‌شود.", // NEW
  colOld: "قبلی", // NEW
  colNew: "جدید", // NEW
  colValue: "ارزش", // NEW
  total: "جمع ارزش", // NEW
  unvalued: (n: number) => `${formatNumber(n)} مورد بدون بها و بدون ارزش`, // NEW
  apply: "اعمال شمارش", // NEW
  applying: "در حال ثبت…", // NEW
  back: "بازگشت", // NEW
  close: "بستن", // NEW
  retry: "تلاش دوباره", // NEW

  staleTitle: "موجودی سیستم تغییر کرده است", // NEW
  staleBody: (n: number) =>
    `موجودی ${formatNumber(n)} کالا از زمان بارگذاری صفحه عوض شده. چیزی ثبت نشد؛ شمارش‌تان نگه داشته شده و ردیف‌ها علامت خورده‌اند. آن‌ها را دوباره بررسی کنید.`, // NEW
  applyFailed: "ثبت شمارش انجام نشد", // NEW
  errorCode: "کد خطا", // NEW

  resultTitle: "شمارش ثبت شد", // NEW
  resultBody: (n: number, same: number) =>
    `${formatNumber(n)} اصلاح ثبت شد${same ? ` · ${formatNumber(same)} مورد بدون تفاوت` : ""}.`, // NEW
  resultHistory: "مشاهدهٔ تعدیل‌ها", // NEW
  resultAgain: "شمارش تازه", // NEW

  loadingAria: "در حال بارگذاری شمارش موجودی", // NEW
  errorTitle: "کالاها بارگذاری نشدند", // NEW
  errorBody: "اتصال به سرور برقرار نشد. شمارش واردشده در مرورگر نگه داشته می‌شود.", // NEW
  draftRestored: (n: number) => `${formatNumber(n)} شمارش از پیش‌نویس قبلی بازیابی شد.`, // NEW
  unitPiece: "عدد", // NEW
  signed: (n: number) => (n > 0 ? `+${formatQuantity(n)}` : formatQuantity(n)), // NEW
}
