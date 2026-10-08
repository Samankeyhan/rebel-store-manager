/**
 * Expenses screen copy (design/screens/11-expenses.md §2, verbatim).
 * Strings the design doesn't have are marked // NEW.
 */

import { currencyLabel } from "@/lib/money"
import { formatNumber, toPersianDigits } from "@/lib/persian-numbers"

export const E = {
  // toolbar
  search: "جستجوی شرح",
  searchAria: "جستجو",
  categoryPrefix: "دسته:",
  categoryAll: "همه",
  categoryAllMobile: "همه دسته‌ها",
  inactive: "(غیرفعال)", // NEW
  add: "ثبت هزینه",

  // table
  listAria: "فهرست هزینه‌ها",
  colDate: "تاریخ",
  colCategory: "دسته",
  colDescription: "شرح",
  get colAmount() {
    return `مبلغ (${currencyLabel()})`
  },
  noDescription: "—", // NEW
  footerMonth: (month: string, n: number) => `جمع هزینه‌های ${month} (${formatNumber(n)} مورد)`,
  footerRange: (n: number) => `جمع هزینه‌های این بازه (${formatNumber(n)} مورد)`, // NEW (range not a whole month)
  noMatch: (q: string) => `هزینه‌ای با «${q}» پیدا نشد.`, // NEW
  noMatchFiltered: "هزینه‌ای با این فیلترها پیدا نشد.", // NEW
  clearFilters: "پاک کردن فیلترها", // NEW

  // breakdown card
  breakdownTitle: "به تفکیک دسته",
  /** `amount` is a formatMoney string. */
  breakdownTip: (name: string, amount: string) => `${name}: ${amount}`,
  breakdownScope: "همه دسته‌های این بازه؛ فیلتر دسته و جستجو روی این کارت اعمال نمی‌شود.", // NEW
  breakdownEmpty: "در این بازه هزینه‌ای ثبت نشده.", // NEW
  breakdownScopeMobile: "سهم همه دسته‌ها در این بازه؛ فیلتر دسته روی این کارت اعمال نمی‌شود.", // NEW
  // Isolated left-to-right (LRI … PDI) so «٪» stays after the digits inside RTL running text.
  percent: (p: number) => `\u2066${toPersianDigits(p)}٪\u2069`,

  // category card
  categoriesTitle: "دسته‌ها",
  newCategory: "دسته جدید",
  categoriesEmpty: "هنوز دسته‌ای ساخته نشده.", // NEW

  // new category dialog
  newCategoryTitle: "دسته جدید", // NEW
  fieldCategoryName: "نام دسته", // NEW
  categoryNamePlaceholder: "مثلاً: اجاره انبار", // NEW
  categoryNameRequired: "نام دسته را وارد کنید.", // NEW
  categoryExists: "دسته‌ای با این نام از قبل وجود دارد.", // NEW
  create: "ساختن", // NEW
  toastCategory: (name: string) => `دسته «${name}» ساخته شد`, // NEW

  // form dialog
  formTitle: "ثبت هزینه",
  close: "بستن",
  fieldDate: "تاریخ",
  today: "امروز",
  fieldCategory: "دسته",
  pickCategory: "انتخاب دسته", // NEW
  addCategoryOption: "دسته جدید…", // NEW
  noCategoriesYet: "هنوز دسته‌ای نیست؛ اول یک دسته بسازید.", // NEW
  fieldDescription: "شرح",
  fieldAmount: "مبلغ",
  get unit() {
    return currencyLabel()
  },
  amountHelp: "در ردیف «هزینه‌های عملیاتی» سود و زیان همان ماه حساب می‌شود.",
  submit: "ثبت هزینه",
  cancel: "انصراف",
  categoryRequired: "دسته را انتخاب کنید.", // NEW
  categoryGone: "این دسته دیگر در دسترس نیست — لطفاً دوباره انتخاب کنید", // NEW
  amountRequired: "مبلغ باید بیشتر از صفر باشد.", // NEW
  toastSaved: (amount: string, category: string) => `هزینه ${amount} در «${category}» ثبت شد`, // NEW; amount is a formatMoney string

  // mobile
  mobileTotal: (label: string) => `جمع ${label}`,
  mobileTotalRange: "جمع این بازه", // NEW
  barAria: "سهم دسته‌ها",
  monthMenuLabel: "ماه", // NEW (aria)

  // states
  emptyTitle: "هنوز هزینه‌ای ثبت نشده",
  emptyBody: "هزینه‌های عملیاتی مثل اجاره، تبلیغات و اینترنت را ثبت کنید تا سود خالص واقعی در گزارش‌ها دیده شود.",
  emptyBodyMobile: "هزینه‌های عملیاتی را ثبت کنید تا سود خالص درست محاسبه شود.",
  emptyCta: "ثبت اولین هزینه",
  errorTitle: "فهرست هزینه‌ها بارگذاری نشد",
  errorTitleMobile: "هزینه‌ها بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",
  loadingAria: "در حال بارگذاری",
}
