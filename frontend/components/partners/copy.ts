/**
 * Partners screen copy («شرکا»). // NEW file
 * No design exists for this screen: every string is NEW. Relative imports
 * only, so lib/partners.test.mjs can load it.
 */

import { currencyLabel } from "../../lib/money.ts"
import { formatJalali } from "../../lib/jalali.ts"
import { formatNumber, toPersianDigits } from "../../lib/persian-numbers.ts"
import type { DistributionError, PercentError } from "../../lib/partners.ts"

const fa = formatNumber
const day = (iso: string) => formatJalali(iso)

export const S = {
  title: "شرکا", // NEW
  tabsLabel: "بخش‌های شرکا", // NEW
  tabPartners: "شرکا", // NEW
  tabPayouts: "پرداخت‌ها", // NEW
  close: "بستن", // NEW
  cancel: "انصراف", // NEW
  retry: "تلاش دوباره", // NEW
  loadingAria: "در حال بارگذاری", // NEW
  nil: "—", // NEW
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.", // NEW
  get unit() {
    return currencyLabel()
  },

  // ── partners tab ──
  intro: "سهم هر شریک از سود را این‌جا تعیین کنید. جمع درصد شرکای فعال باید دقیقاً ۱۰۰ باشد.", // NEW
  addPartner: "افزودن شریک", // NEW
  editSplit: "ویرایش سهم‌ها", // NEW
  recordPayout: "ثبت پرداخت", // NEW
  deactivate: "غیرفعال‌سازی", // NEW
  inactive: "غیرفعال", // NEW
  inactiveList: (n: number) => `شرکای غیرفعال (${fa(n)})`, // NEW
  colName: "نام", // NEW
  colPercent: "درصد", // NEW
  colReceived: "جمع دریافتی", // NEW
  colPayouts: "تعداد پرداخت", // NEW
  colContact: "تماس", // NEW
  colNotes: "یادداشت", // NEW
  colActions: "عملیات", // NEW
  percent: (text: string) => `${text}٪`, // NEW (text is Persian digits)
  activeTotal: "جمع درصد شرکای فعال", // NEW
  totalBadTitle: "جمع درصدها ۱۰۰ نیست", // NEW
  totalBadBody: (total: string) => `جمع درصد شرکای فعال ${total}٪ است. تا آن را به ۱۰۰ نرسانید، ثبت پرداخت ممکن نیست.`, // NEW
  totalsFailed: "جمع دریافتی شرکا بارگذاری نشد؛ بقیه اطلاعات درست است.", // NEW
  partnersErrorTitle: "فهرست شرکا بارگذاری نشد", // NEW
  emptyTitle: "هنوز شریکی ثبت نشده", // NEW
  emptyBody: "شرکا و درصد سهم هر کدام از سود را اضافه کنید تا بتوانید سود را بینشان تقسیم کنید.", // NEW
  noActiveTitle: "شریک فعالی نیست", // NEW
  noActiveBody: "برای ثبت پرداخت، دست‌کم یک شریک فعال با جمع درصد ۱۰۰ لازم است.", // NEW
  partialTitle: "ذخیره نیمه‌کاره ماند", // NEW
  partialSaved: "این تغییرها ذخیره شد:", // NEW
  partialBlocked: "تا جمع درصد شرکای فعال دوباره ۱۰۰ نشود، ثبت پرداخت ممکن نیست. «ویرایش سهم‌ها» را باز کنید و درصدها را درست کنید.", // NEW
  stepCreated: (name: string) => `«${name}» اضافه شد`, // NEW
  stepDeactivated: (name: string) => `«${name}» غیرفعال شد`, // NEW
  stepPercent: (name: string, pct: string) => `درصد «${name}» ${pct}٪ شد`, // NEW
  failedAt: (message: string) => `خطا: ${message}`, // NEW

  // ── split dialog ──
  addTitle: "افزودن شریک", // NEW
  editTitle: "ویرایش سهم‌ها", // NEW
  deactivateTitle: (name: string) => `غیرفعال‌سازی «${name}»`, // NEW
  deactivateHelp: "پرداخت‌های قبلی این شریک در سابقه می‌ماند. سهم او را بین شرکای باقی‌مانده تقسیم کنید تا جمع ۱۰۰ شود.", // NEW
  deactivateLast: "پس از غیرفعال‌سازی، شریک فعالی نمی‌ماند و ثبت پرداخت تا افزودن شریک جدید ممکن نیست.", // NEW
  irreversible: "غیرفعال‌سازی برگشت‌پذیر نیست.", // NEW
  name: "نام", // NEW
  phone: "تلفن", // NEW
  email: "ایمیل", // NEW
  notes: "یادداشت", // NEW
  newPartnerPercent: "درصد شریک جدید", // NEW
  otherPartners: "درصد شرکای فعلی", // NEW
  nameRequired: "نام را وارد کنید.", // NEW
  nameTaken: "شریکی با این نام وجود دارد (فعال یا غیرفعال). نام دیگری انتخاب کنید.", // NEW
  percentHelp: "تا دو رقم اعشار، بیشتر از ۰ و حداکثر ۱۰۰.", // NEW
  percentAria: (name: string) => `درصد ${name}`, // NEW
  total: "جمع", // NEW
  totalOk: "دقیقاً ۱۰۰ است", // NEW
  totalUnder: (left: string) => `${left}٪ کم است`, // NEW
  totalOver: (extra: string) => `${extra}٪ زیاد است`, // NEW
  totalInvalid: "درصدهای نادرست را اصلاح کنید", // NEW
  save: "ذخیره", // NEW
  confirmDeactivate: "غیرفعال‌سازی و ذخیره", // NEW
  toastAdded: "شریک اضافه شد", // NEW
  toastSplit: "سهم‌ها ذخیره شد", // NEW
  toastDeactivated: "شریک غیرفعال شد", // NEW
  noChanges: "تغییری برای ذخیره نیست.", // NEW

  // ── payout dialog ──
  payoutTitle: "ثبت پرداخت به شرکا", // NEW
  payoutIntro: "مبلغ کل پرداخت را وارد کنید؛ سیستم آن را به نسبت درصد بین همه شرکای فعال تقسیم می‌کند.", // NEW
  amount: "مبلغ کل پرداخت", // NEW
  amountRequired: "مبلغ پرداخت را وارد کنید.", // NEW
  amountZero: "مبلغ پرداخت باید بیشتر از صفر باشد.", // NEW
  payoutDate: "تاریخ پرداخت", // NEW
  today: "امروز", // NEW
  period: "دوره سود", // NEW
  periodHelp: "دوره‌ای که این سود به آن مربوط است. دوره پرداخت‌ها نباید با هم هم‌پوشانی داشته باشند.", // NEW
  periodRequired: "شروع و پایان دوره را انتخاب کنید.", // NEW
  undistributed: (date: string) => `سود توزیع‌نشده تا ${date}`, // NEW (date is formatJalali)
  periodProfit: "سود خالص این دوره", // NEW
  preview: "پیش‌نمایش", // NEW
  previewTitle: "سهم هر شریک", // NEW
  previewHelp: "محاسبه را سرور انجام می‌دهد، دقیقاً همان‌طور که ثبت می‌شود. باقی‌مانده گرد کردن به شریکِ با بیشترین درصد می‌رسد.", // NEW
  previewLoading: "در حال محاسبه سهم‌ها…", // NEW
  previewWaiting: "مبلغ و دوره را وارد کنید تا سهم هر شریک نمایش داده شود.", // NEW
  previewFailed: "پیش‌نمایش محاسبه نشد.", // NEW
  colShare: "سهم", // NEW
  sum: "جمع", // NEW
  overCapWarn: "این مبلغ از سود توزیع‌نشده بیشتر است؛ پیش از ثبت دوباره تأیید می‌خواهیم.", // NEW
  confirmTitle: "بیش از سود توزیع‌نشده", // NEW
  confirmBody: "این پرداخت از سود توزیع‌نشده بیشتر است. با این حال ثبت شود؟", // NEW
  confirmAmount: "مبلغ پرداخت", // NEW
  confirmUndistributed: "سود توزیع‌نشده", // NEW
  confirmDifference: "مازاد", // NEW
  confirmYes: "با این حال ثبت شود", // NEW
  back: "بازگشت", // NEW
  submit: "ثبت پرداخت", // NEW
  toastPayout: "پرداخت ثبت شد", // NEW

  // ── payouts tab ──
  payoutsNote: "پرداخت‌های ثبت‌شده قابل ویرایش یا حذف نیستند. درصدها و مبالغ همان زمان پرداخت را نشان می‌دهند.", // NEW
  payoutsAria: "سابقه پرداخت‌ها", // NEW
  payoutsErrorTitle: "سابقه پرداخت‌ها بارگذاری نشد", // NEW
  payoutsEmptyTitle: "هنوز پرداختی ثبت نشده", // NEW
  payoutsEmptyBody: "هر بار که سود را بین شرکا تقسیم کردید، این‌جا ثبت کنید.", // NEW
  colDate: "تاریخ پرداخت", // NEW
  colPeriod: "دوره", // NEW
  colTotal: "مبلغ کل", // NEW
  colPeriodProfit: "سود دوره", // NEW
  periodText: (from: string, to: string) => `${day(from)} تا ${day(to)}`, // NEW
  sharesOf: "سهم شرکا", // NEW
  sharesToggle: "سهم شرکا", // NEW
  sharesFailed: "سهم شرکا بارگذاری نشد.", // NEW
  expand: "نمایش سهم شرکا", // NEW (aria)
  payoutNo: (id: number) => `پرداخت ${fa(id)}`, // NEW (aria)
  percentAtTime: "درصد در زمان پرداخت", // NEW
}

export function percentErrorText(e: PercentError): string {
  switch (e) {
    case "empty":
      return "درصد را وارد کنید." // NEW
    case "format":
      return "درصد را به عدد وارد کنید." // NEW
    case "decimals":
      return "حداکثر دو رقم اعشار." // NEW
    case "range":
      return "درصد باید بیشتر از ۰ و حداکثر ۱۰۰ باشد." // NEW
  }
}

export function distributionErrorText(e: DistributionError): string {
  switch (e.kind) {
    case "overlap":
      return `این دوره با پرداخت ${fa(e.id)} (${day(e.from)} تا ${day(e.to)}) هم‌پوشانی دارد. دوره دیگری انتخاب کنید.` // NEW
    case "noPartners":
      return "شریک فعالی نیست؛ ابتدا شریک اضافه کنید." // NEW
    case "percentSum":
      return "جمع درصد شرکای فعال ۱۰۰ نیست؛ ابتدا سهم‌ها را اصلاح کنید." // NEW
    case "overCap":
      return "این مبلغ از سود توزیع‌نشده بیشتر است." // NEW
    case "badAmount":
      return "مبلغ پرداخت نادرست است." // NEW
    case "periodOrder":
      return "پایان دوره نباید پیش از شروع آن باشد." // NEW
    case "badDate":
      return "تاریخ نادرست است." // NEW
  }
}

/** Whole hundredths of a percent as Persian text, unsigned: 3333 → "۳۳٫۳۳", 10000 → "۱۰۰". */
export function hundredthsText(h: number): string {
  const a = Math.abs(h)
  const frac = String(a % 100).padStart(2, "0").replace(/0+$/, "")
  return toPersianDigits(String(Math.floor(a / 100))) + (frac ? "٫" + toPersianDigits(frac) : "")
}
