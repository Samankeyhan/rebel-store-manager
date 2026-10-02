/**
 * Suppliers screen copy (design/screens/14-suppliers.md §2, verbatim).
 * Strings the design doesn't have are marked // NEW.
 */
export const S = {
  search: "جستجوی نام، تلفن یا ایمیل", // NEW (design: «جستجوی نام یا کالا» — there are no supplied items)
  searchAria: "جستجو",
  add: "تأمین‌کننده جدید",

  colName: "نام",
  colPhone: "شماره تماس",
  colEmail: "ایمیل", // NEW
  colWebsite: "نشانی یا شناسه آنلاین",
  colPurchases: "تعداد خرید", // NEW
  colLast: "آخرین خرید",
  edit: "ویرایش",

  titleNew: "تأمین‌کننده جدید", // NEW
  titleEdit: "ویرایش تأمین‌کننده",
  close: "بستن",
  fieldName: "نام",
  fieldPhone: "شماره تماس",
  phonePlaceholder: "۰۲۱-۰۰۰۰۰۰۰۰",
  fieldEmail: "ایمیل", // NEW
  emailPlaceholder: "name@example.com", // NEW
  fieldWebsite: "نشانی یا شناسه آنلاین",
  websitePlaceholder: "مثلاً نشانی کارگاه یا صفحه اینستاگرام",
  fieldNotes: "یادداشت",
  notesPlaceholder: "مثلاً حداقل سفارش یا زمان تحویل", // NEW
  save: "ذخیره",
  cancel: "انصراف",
  nameRequired: "نام تأمین‌کننده را وارد کنید.", // NEW
  toastCreated: (name: string) => `تأمین‌کننده «${name}» ثبت شد`, // NEW
  toastUpdated: (name: string) => `تغییرات «${name}» ذخیره شد`, // NEW

  lastPurchase: (date: string) => `آخرین خرید ${date}`,
  noPurchases: "هنوز خریدی ثبت نشده", // NEW
  purchaseCount: (n: string) => `${n} خرید`, // NEW

  emptyTitle: "هنوز تأمین‌کننده‌ای ثبت نشده",
  emptyBody: "تأمین‌کنندگان را ثبت کنید تا در «خرید» انتخاب شوند و مجموع خرید از هر کدام را ببینید.",
  emptyBodyMobile: "تأمین‌کنندگان در فرم خرید انتخاب می‌شوند.",
  emptyCta: "افزودن تأمین‌کننده",
  noMatch: (q: string) => `تأمین‌کننده‌ای با «${q}» پیدا نشد.`, // NEW
  clearSearch: "پاک کردن جستجو", // NEW
  loadingAria: "در حال بارگذاری",
  errorTitle: "فهرست تأمین‌کنندگان بارگذاری نشد",
  errorTitleMobile: "تأمین‌کنندگان بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",
} as const
