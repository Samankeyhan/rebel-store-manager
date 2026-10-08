/**
 * Settings screen copy (design/screens/15-settings.md §2, verbatim).
 * Strings the design doesn't have are marked // NEW.
 */

import { currencyLabel, formatMoney, formatMoneyNumber } from "@/lib/money"
import { formatNumber } from "@/lib/persian-numbers"

const fa = formatNumber

export const S = {
  // section nav
  navAria: "بخش‌های تنظیمات",
  navShip: "ارسال و کانال‌ها",
  navPost: "تخمین هزینه پست",
  navGeneral: "عمومی", // NEW
  navPay: "روش‌های پرداخت", // NEW

  // [1] shipping and channels
  shipTitle: "ارسال و کانال‌ها",
  shipTitleMobile: "ارسال",
  channelsTitleMobile: "کانال‌ها",
  shipCaption: "این مقادیر فقط پیش‌فرض فرم ثبت فروش هستند و روی سفارش‌های ثبت‌شده اثری ندارند.",
  shippingLabel: "هزینه ارسال پیش‌فرض",
  shippingHelp: "برای کانال‌هایی که «هزینه ارسال» آن‌ها روشن است؛ در هر سفارش قابل تغییر است.",
  get unit() {
    return currencyLabel()
  },
  colChannel: "کانال",
  colShipping: "دریافت هزینه ارسال از مشتری",
  colPostage: "هزینه پست",
  colKit: "کیت بسته‌بندی پیش‌فرض",
  switchShippingMobile: "هزینه ارسال",
  switchPostageMobile: "هزینه پست",
  switchShippingAria: (channel: string) => `هزینه ارسال ${channel}`,
  switchPostageAria: (channel: string) => `هزینه پست ${channel}`,
  off: "خاموش",
  shipOn: (amount: number) => formatMoney(amount),
  postOn: (estimate: number) => `تخمین ${formatMoney(estimate)}`,
  noPackaging: "بدون بسته‌بندی",
  kitAria: (channel: string) => `کیت بسته‌بندی پیش‌فرض ${channel}`, // NEW
  kitInactive: (name: string) => `${name} (غیرفعال)`, // NEW
  kitInactiveTitle: "کیت پیش‌فرض غیرفعال", // NEW
  colMethod: "روش پرداخت پیش‌فرض", // NEW
  methodAria: (channel: string) => `روش پرداخت پیش‌فرض ${channel}`, // NEW
  methodInactiveTitle: "روش پرداخت پیش‌فرض غیرفعال", // NEW
  methodInactiveWarn: (channels: string) =>
    `روش پرداخت پیش‌فرض ${channels} غیرفعال است؛ سفارش‌های این کانال با روش پیش‌فرض ثبت نمی‌شوند. روش دیگری یا «بدون روش» انتخاب کنید.`, // NEW
  kitInactiveWarn: (channels: string) =>
    `کیت پیش‌فرض ${channels} غیرفعال است؛ سفارش‌های این کانال با کیت پیش‌فرض ثبت نمی‌شوند. کیت دیگری یا «بدون بسته‌بندی» انتخاب کنید.`, // NEW

  // [2] postage estimate
  postTitle: "تخمین هزینه پست",
  windowLabel: "تعداد پرداخت‌های اخیر در محاسبه",
  windowLabelMobile: "تعداد پرداخت‌های اخیر",
  windowInputAria: "تعداد پرداخت",
  windowHelp: "عدد کمتر = تخمین سریع‌تر به تغییر نرخ پست واکنش نشان می‌دهد؛ عدد بیشتر = پایدارتر.",
  windowForward: "تخمین هنگام ثبت هر سفارش روی آن ثابت می‌شود؛ تغییر این عدد سفارش‌های قبلی را عوض نمی‌کند.", // NEW
  windowError: "تعداد پرداخت باید دست‌کم ۱ باشد.", // NEW
  defaultPostLabel: "تخمین پیش‌فرض (پیش از اولین پرداخت پست)", // NEW
  defaultPostHelp: "تا وقتی هیچ پرداختی به پست ثبت نشده، همین مبلغ برای هر سفارش در نظر گرفته می‌شود.", // NEW
  heroCaption: "تخمین با این تنظیم",
  heroCaptionMobile: "تخمین فعلی",
  heroPreview: (n: number) => `پیش‌نمایش با ${fa(n)} پرداخت — هنوز ذخیره نشده`, // NEW
  get perOrder() {
    return `${currencyLabel()} / سفارش`
  },
  divisor: (n: number, paid: number, orders: number) =>
    `جمع پرداختی ÷ جمع سفارش‌ها در ${fa(n)} پرداخت اخیر: ${formatMoneyNumber(paid)} ÷ ${fa(orders)}`,
  divisorMobile: (paid: number, orders: number) => `جمع پرداختی ÷ جمع سفارش‌ها: ${formatMoneyNumber(paid)} ÷ ${fa(orders)}`,
  fewerThanN: (count: number) => `فقط ${fa(count)} پرداخت ثبت شده؛ همه در محاسبه‌اند.`, // NEW
  noPayments: "هنوز پرداختی به پست ثبت نشده — از تخمین پیش‌فرض استفاده می‌شود.", // NEW

  // [3] general
  generalTitle: "عمومی", // NEW
  tzLabel: "منطقه زمانی", // NEW
  currencyLabel: "واحد پول", // NEW
  currencyAria: "واحد پول نمایش مبالغ", // NEW
  currencyOptions: [
    ["TOMAN", currencyLabel("TOMAN")],
    ["RIAL", currencyLabel("RIAL")],
  ] as const, // NEW
  // Amounts are stored, computed and sent as integer Rial; this only changes how they are shown and typed.
  get currencyNote() {
    const rial = currencyLabel("RIAL")
    const toman = currencyLabel("TOMAN")
    return `مبالغ همیشه به ${rial} ذخیره و محاسبه می‌شوند و این گزینه فقط واحد نمایش و ورود مبالغ را عوض می‌کند؛ داده‌ها و گزارش‌ها تغییری نمی‌کنند. هر ${toman} ۱۰ ${rial} است: مبلغی که مضرب ۱۰ ${rial} نباشد در ${toman} با یک رقم اعشار نمایش داده می‌شود (مثلاً ۱۸۰٬۰۰۰٫۵) و هنگام ورود به ${toman} هم یک رقم اعشار مجاز است.` // NEW
  },
  currencySaved: (label: string) => `واحد پول به ${label} تغییر کرد`, // NEW
  currencyFailed: (msg: string) => `واحد پول ذخیره نشد: ${msg}`, // NEW
  tzHelp:
    "تاریخ‌ها با این منطقه ذخیره و گزارش شده‌اند؛ تغییر آن تاریخ همه سوابق را جابه‌جا می‌کند و از این صفحه ممکن نیست.", // NEW

  // dirty bar / save
  unsaved: (n: number, list: string) => `${fa(n)} تغییر ذخیره‌نشده — ${list}`,
  unsavedMobile: (n: number) => `${fa(n)} تغییر ذخیره‌نشده`, // NEW
  more: (n: number) => `${fa(n)} مورد دیگر`, // NEW
  and: " و ",
  listSep: "، ",
  revert: "بازگردانی",
  save: "ذخیره تغییرات",
  invalid: "برخی مقادیر نامعتبرند؛ پیش از ذخیره درستشان کنید.", // NEW
  saveFailed: "ذخیره نشد", // NEW
  saveStep: (what: string, msg: string) => `«${what}» ذخیره نشد: ${msg}`, // NEW
  savePartial: (what: string) => `این موارد ذخیره شد: ${what}. بقیه هنوز ذخیره نشده‌اند.`, // NEW
  kitsReloaded: "فهرست کیت‌ها دوباره خوانده شد.", // NEW
  methodsReloaded: "فهرست روش‌های پرداخت دوباره خوانده شد.", // NEW
  toastSaved: "تنظیمات ذخیره شد", // NEW
  close: "بستن",

  // change labels (dirty bar, partial-save messages)
  chShipping: "هزینه ارسال پیش‌فرض",
  chWindow: "تعداد پرداخت‌های اخیر", // NEW
  chDefaultPost: "تخمین پیش‌فرض پست", // NEW
  chChannelShipping: (channel: string) => `هزینه ارسال «${channel}»`, // NEW
  chChannelPostage: (channel: string) => `هزینه پست «${channel}»`, // NEW
  chChannelKit: (channel: string) => `کیت «${channel}»`,
  chChannelMethod: (channel: string) => `روش پرداخت «${channel}»`, // NEW
  chChannel: (channel: string) => `تنظیمات «${channel}»`, // NEW

  // states
  loadingAria: "در حال بارگذاری",
  errorTitle: "تنظیمات بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",

  amountError: "این مبلغ بیش از حد بزرگ است.", // NEW

  // [4] payment methods
  payTitle: "روش‌های پرداخت", // NEW
  payCaption: "کارمزد هر روش هنگام ثبت فروش خودکار حساب و روی سفارش ثابت می‌شود؛ قاعده تسویه می‌گوید پول کی به حساب می‌رسد.", // NEW
  payAdd: "افزودن روش پرداخت", // NEW
  payEmptyTitle: "هنوز روش پرداختی تعریف نشده", // NEW
  payEmptyBody: "روش‌هایی مثل کارت‌به‌کارت یا درگاه پرداخت را با کارمزد و زمان تسویه‌شان اضافه کنید.", // NEW
  payShowInactive: "نمایش روش‌های غیرفعال", // NEW
  payColName: "نام", // NEW
  payColFee: "کارمزد", // NEW
  payColRule: "تسویه", // NEW
  payColPending: "در انتظار تسویه", // NEW
  payColActions: "عملیات", // NEW
  payActive: "فعال", // NEW
  payInactive: "غیرفعال", // NEW
  payNoPending: "—", // NEW
  payEdit: "ویرایش", // NEW
  payEditAria: (name: string) => `ویرایش ${name}`, // NEW
  payDeactivate: "غیرفعال‌سازی", // NEW
  payReactivate: "فعال‌سازی", // NEW
  payDeactivateTitle: (name: string) => `غیرفعال‌سازی «${name}»`, // NEW
  payDeactivateSubtitle: "روش غیرفعال پاک نمی‌شود و هر وقت بخواهید دوباره فعال می‌شود.", // NEW
  payEffNew: "برای فروش جدید و به‌عنوان پیش‌فرض کانال قابل انتخاب نیست.", // NEW
  payEffExisting: "سفارش‌های قبلی این روش همچنان پرداخت و تسویه می‌شوند.", // NEW
  payEffDefault: (channels: string) => `پیش‌فرض ${channels} است؛ بعد از غیرفعال‌سازی، روش پیش‌فرض این کانال‌ها را عوض کنید.`, // NEW
  payDeactivated: (name: string) => `«${name}» غیرفعال شد`, // NEW
  payReactivated: (name: string) => `«${name}» دوباره فعال شد`, // NEW
  payActionFailed: (msg: string) => `انجام نشد: ${msg}`, // NEW
  paySaved: (name: string) => `«${name}» ذخیره شد`, // NEW
  payCreated: (name: string) => `«${name}» اضافه شد`, // NEW

  // payment method drawer
  drawerAdd: "روش پرداخت جدید", // NEW
  drawerEdit: (name: string) => `ویرایش «${name}»`, // NEW
  fName: "نام روش", // NEW
  fNamePlaceholder: "مثلاً زرین‌پال", // NEW
  fNameError: "نام روش را بنویسید.", // NEW
  fPercent: "کارمزد درصدی", // NEW
  fPercentHelp: "تا دو رقم اعشار؛ مثلاً ۱٫۵ یعنی یک‌ونیم درصد مبلغی که مشتری می‌پردازد.", // NEW
  fPercentFormat: "یک عدد بنویسید؛ مثلاً ۱٫۵", // NEW
  fPercentDecimals: "حداکثر دو رقم اعشار.", // NEW
  fPercentRange: "کارمزد درصدی باید بین ۰ و ۱۰۰ باشد.", // NEW
  fFixed: "کارمزد ثابت هر تراکنش", // NEW
  fFixedHelp: "به کارمزد درصدی اضافه می‌شود؛ اگر ندارد صفر بگذارید.", // NEW
  fFixedError: "کارمزد ثابت معتبر نیست.", // NEW
  fCap: "سقف بخش درصدی کارمزد", // NEW
  get fCapHelp() {
    return `به ${currencyLabel()}؛ خالی یعنی بدون سقف. سقف فقط بخش درصدی را محدود می‌کند و کارمزد ثابت جدا روی آن اضافه می‌شود.` // NEW
  },
  fCapNeedsPercent: "سقف فقط برای کارمزد درصدی است؛ اول کارمزد درصدی را وارد کنید.", // NEW
  fCapMin: "سقف باید بیشتر از صفر باشد؛ برای بدون سقف خالی بگذارید.", // NEW
  fRule: "زمان تسویه", // NEW
  fRuleAria: "قاعده تسویه", // NEW
  fDays: "تعداد روز بعد از پرداخت", // NEW
  fDayOfMonth: "روز ماه بعد (شمسی)", // NEW
  fDaysRange: (min: number, max: number) => `عددی از ${fa(min)} تا ${fa(max)}.`, // NEW
  fDaysError: (min: number, max: number) => `باید عددی از ${fa(min)} تا ${fa(max)} باشد.`, // NEW
  fRuleError: "قاعده تسویه معتبر نیست.", // NEW
  fRuleLocked: "قاعده تسویه", // NEW
  fCancel: "انصراف", // NEW
  fSave: "ذخیره", // NEW
  fAdd: "افزودن", // NEW
  fNoChanges: "تغییری نداده‌اید.", // NEW
}

/** «a، b و c»; past `max` items, «a، b، c و ۲ مورد دیگر». */
export function joinList(items: string[], max = 3): string {
  const shown = items.length > max ? [...items.slice(0, max), S.more(items.length - max)] : items
  if (shown.length <= 1) return shown.join("")
  return `${shown.slice(0, -1).join(S.listSep)}${S.and}${shown[shown.length - 1]}`
}
