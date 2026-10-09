/**
 * Settlements screen copy («تسویه‌ها») and the dashboard's pending card. // NEW file
 * No design exists for this screen: every string is NEW. Relative imports
 * only, so lib/settlements.test.mjs can load it.
 */

import { currencyLabel, formatMoney } from "../../lib/money.ts"
import { formatJalali } from "../../lib/jalali.ts"
import { formatNumber, toPersianDigits } from "../../lib/persian-numbers.ts"
import { differenceKind, type SettlementError } from "../../lib/settlements.ts"

const fa = formatNumber
const monthLabel = (year: number, month: number) => toPersianDigits(`${year}/${String(month).padStart(2, "0")}`)
const day = (iso: string) => formatJalali(iso)
/** LRM + "+", the plus twin of persian-numbers' MINUS, so the sign stays on the digits' left in RTL text. */
const PLUS = "‎+"

export const S = {
  title: "تسویه‌ها", // NEW
  tabsLabel: "بخش‌های تسویه", // NEW
  tabPending: "در انتظار", // NEW
  tabHistory: "سابقه", // NEW
  close: "بستن", // NEW
  retry: "تلاش دوباره", // NEW
  loadingAria: "در حال بارگذاری", // NEW
  get unit() {
    return currencyLabel()
  },

  // ── pending ──
  intro: "مبلغی که هر روش پرداخت به حساب واریز می‌کند را این‌جا با سفارش‌هایش تطبیق دهید و تسویه را ثبت کنید.", // NEW
  inactive: "غیرفعال", // NEW
  remaining: "مانده:", // NEW
  expectedOn: (date: string) => `تسویه مورد انتظار: ${date}`, // NEW (date is formatJalali)
  settleOn: (date: string) => `تسویه روز ${date}`, // NEW
  orders: (n: number) => `${fa(n)} سفارش`, // NEW
  overdue: "معوق", // NEW
  dueToday: "سررسید امروز", // NEW
  monthOpen: "ماه هنوز تمام نشده", // NEW
  settleAfter: (date: string) => `پس از پایان ماه (${date}) قابل ثبت است`, // NEW
  settle: "ثبت تسویه", // NEW
  settleMonth: "ثبت تسویه این ماه", // NEW
  selected: (n: number) => `${fa(n)} سفارش انتخاب‌شده`, // NEW
  selectedSum: "جمع مورد انتظار", // NEW
  preview: "پیش‌نمایش", // NEW
  clearSelection: "لغو انتخاب", // NEW
  selectGroup: (title: string) => `انتخاب همه سفارش‌های ${title}`, // NEW (aria)
  selectOrder: (inv: string) => `انتخاب سفارش ${inv}`, // NEW (aria)
  colInvoice: "شماره فاکتور", // NEW
  colPaidDate: "تاریخ پرداخت", // NEW
  colCustomerTotal: "مبلغ مشتری", // NEW
  colFee: "کارمزد", // NEW
  colExpected: "مبلغ مورد انتظار", // NEW
  colReference: "کد پیگیری", // NEW
  nil: "—", // NEW
  refsFailed: "کدهای پیگیری بارگذاری نشد؛ بقیه اطلاعات درست است.", // NEW
  monthlyHelp: "این روش هر ماه شمسی را یک‌جا تسویه می‌کند؛ همه سفارش‌های ماه با هم ثبت می‌شوند.", // NEW
  pendingEmptyTitle: "همه پرداخت‌ها تسویه شده‌اند", // NEW
  pendingEmptyBody: "سفارش پرداخت‌شده‌ای در انتظار تسویه نیست.", // NEW
  toOrders: "مشاهده سفارش‌ها", // NEW
  pendingErrorTitle: "فهرست تسویه‌ها بارگذاری نشد", // NEW
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.", // NEW
  totalTooLarge: "جمع این انتخاب بیش از حد بزرگ است.", // NEW

  // ── record dialog ──
  recordTitle: "ثبت تسویه", // NEW
  method: "روش پرداخت", // NEW
  period: "دوره", // NEW
  expected: "مبلغ مورد انتظار", // NEW
  received: "مبلغ دریافتی", // NEW
  receivedHelp: "مبلغی که واقعاً به حساب آمده را وارد کنید؛ اختلاف را سیستم حساب می‌کند.", // NEW
  receivedRequired: "مبلغ دریافتی را وارد کنید.", // NEW
  settledDate: "تاریخ تسویه", // NEW
  today: "امروز", // NEW
  note: "یادداشت", // NEW
  noteLabel: "یادداشت (اختیاری)", // NEW
  difference: "اختلاف", // NEW
  differencePreview: "پیش‌نمایش اختلاف", // NEW
  over: "بیشتر از انتظار دریافت شد", // NEW
  under: "کمتر از انتظار دریافت شد", // NEW
  equal: "برابر با مبلغ مورد انتظار", // NEW
  cancel: "انصراف", // NEW
  listRefreshed: "فهرست به‌روز شد", // NEW
  toastSaved: (diff: string) => `تسویه ثبت شد · ${diff}`, // NEW (diff is differenceText)

  // ── history ──
  historyAria: "سابقه تسویه‌ها", // NEW
  methodPrefix: "روش:", // NEW
  allMethods: "همه روش‌ها", // NEW
  colSettledDate: "تاریخ تسویه", // NEW
  colMethod: "روش", // NEW
  colPeriod: "دوره", // NEW
  colReceived: "دریافتی", // NEW
  colExpectedShort: "مورد انتظار", // NEW
  colDifference: "اختلاف", // NEW
  colNote: "یادداشت", // NEW
  colActions: "عملیات", // NEW
  colStatus: "وضعیت", // NEW
  edit: "ویرایش", // NEW
  expand: "نمایش سفارش‌ها", // NEW (aria)
  ordersOf: "سفارش‌های این تسویه", // NEW
  ordersToggle: "سفارش‌ها", // NEW
  ordersErrorTitle: "سفارش‌های این تسویه بارگذاری نشد", // NEW
  historyEmptyTitle: "هنوز تسویه‌ای ثبت نشده", // NEW
  historyEmptyBody: "وقتی پول یک روش پرداخت به حساب آمد، از بخش «در انتظار» تسویه‌اش را ثبت کنید.", // NEW
  historyFilteredEmpty: "این روش تسویه‌ای ندارد", // NEW
  showAll: "نمایش همه روش‌ها", // NEW
  historyErrorTitle: "سابقه تسویه‌ها بارگذاری نشد", // NEW
  settlementNo: (id: number) => `تسویه شماره ${fa(id)}`, // NEW

  // ── edit dialog ──
  editTitle: "ویرایش تسویه", // NEW
  editHelp: "فقط مبلغ دریافتی، تاریخ و یادداشت قابل ویرایش است؛ سفارش‌های این تسویه و مبلغ مورد انتظارش تغییر نمی‌کند.", // NEW
  save: "ذخیره", // NEW
  noChanges: "تغییری داده نشده.", // NEW
  toastEdited: "تسویه ویرایش شد", // NEW

  // ── dashboard card ──
  cardTitle: "در انتظار تسویه", // NEW
  cardCaption: "وضعیت همین حالا؛ به بازه انتخابی بستگی ندارد", // NEW
  cardOverdue: (n: number) => `${fa(n)} سفارش معوق`, // NEW
  cardLink: "مشاهده تسویه‌ها", // NEW
  cardEmpty: "چیزی در انتظار تسویه نیست", // NEW
  cardErrorTitle: "تسویه‌ها بارگذاری نشد", // NEW

  // ── errors (backend messages are English; these are what the owner reads) ──
  errors: {
    monthNotEnded: (y: number, m: number, ends: string) =>
      `ماه ${monthLabel(y, m)} هنوز تمام نشده؛ بعد از ${day(ends)} قابل تسویه است.`, // NEW
    monthSettled: (y: number, m: number, id: number | null) =>
      id == null
        ? `ماه ${monthLabel(y, m)} این روش قبلاً تسویه شده.` // NEW
        : `ماه ${monthLabel(y, m)} این روش قبلاً تسویه شده (تسویه شماره ${fa(id)}).`, // NEW
    orderSettled: (order: number, id: number) => `سفارش ${fa(order)} قبلاً در تسویه شماره ${fa(id)} ثبت شده.`, // NEW
    orderNotPaid: (order: number) => `سفارش ${fa(order)} دیگر پرداخت‌شده نیست (لغو یا مرجوع شده) و قابل تسویه نیست.`, // NEW
    nothingPending: "این ماه سفارش در انتظار تسویه‌ای ندارد.", // NEW
    raced: "بعضی از این سفارش‌ها همین حالا تسویه شدند؛ فهرست به‌روز شد، دوباره انتخاب کنید.", // NEW
    conflict: "ثبت تسویه با داده‌های موجود تداخل دارد؛ صفحه را تازه کنید.", // NEW
    futureDate: "تاریخ تسویه نمی‌تواند بعد از امروز باشد.", // NEW
    beforeMonthEnd: (y: number, m: number) => `تاریخ تسویه باید بعد از پایان ماه ${monthLabel(y, m)} باشد.`, // NEW
    beforePaid: (date: string) =>
      `تاریخ تسویه نمی‌تواند قبل از آخرین تاریخ پرداخت این سفارش‌ها (${day(date)}) باشد.`, // NEW
    badAmount: "مبلغ دریافتی باید عددی صحیح و نامنفی باشد.", // NEW
    wrongMethod: (order: number) => `سفارش ${fa(order)} با این روش پرداخت نشده.`, // NEW
    badSelection: "انتخاب سفارش‌ها معتبر نیست؛ صفحه را تازه کنید.", // NEW
    wrongShape: "این روش فقط ماه کامل تسویه می‌کند.", // NEW
    notMonthly: "این روش ماهانه تسویه نمی‌کند.", // NEW
    notFound: "این روش پرداخت یا تسویه دیگر وجود ندارد.", // NEW
  },
}

/** The Persian sentence for a classified settlement error. */
export function settlementErrorText(e: SettlementError): string {
  const t = S.errors
  switch (e.kind) {
    case "monthNotEnded":
      return t.monthNotEnded(e.year, e.month, e.ends)
    case "monthSettled":
      return t.monthSettled(e.year, e.month, e.settlementId)
    case "orderSettled":
      return t.orderSettled(e.orderId, e.settlementId)
    case "orderNotPaid":
      return t.orderNotPaid(e.orderId)
    case "nothingPending":
      return t.nothingPending
    case "raced":
      return t.raced
    case "conflict":
      return t.conflict
    case "futureDate":
      return t.futureDate
    case "beforeMonthEnd":
      return t.beforeMonthEnd(e.year, e.month)
    case "beforePaid":
      return t.beforePaid(e.date)
    case "badAmount":
      return t.badAmount
    case "wrongMethod":
      return t.wrongMethod(e.orderId)
    case "badSelection":
      return t.badSelection
    case "wrongShape":
      return t.wrongShape
    case "notMonthly":
      return t.notMonthly
    case "notFound":
      return t.notFound
  }
}

/** A difference with its sign and unit: «‎+۱۲۳ تومان», «‎−۱۲۳ تومان», «۰ تومان». */
export function signedMoney(difference: number): string {
  return difference > 0 ? PLUS + formatMoney(difference) : formatMoney(difference)
}

/** «بیشتر از انتظار دریافت شد ‎+X» / «کمتر از انتظار دریافت شد ‎−X» / «برابر با مبلغ مورد انتظار». */
export function differenceText(difference: number): string {
  const kind = differenceKind(difference)
  if (kind === "equal") return S.equal
  return `${kind === "over" ? S.over : S.under} ${signedMoney(difference)}`
}
