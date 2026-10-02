/**
 * Settings screen copy (design/screens/15-settings.md §2, verbatim).
 * Strings the design doesn't have are marked // NEW.
 */

import { formatNumber } from "@/lib/persian-numbers"

const fa = formatNumber

export const S = {
  // section nav
  navAria: "بخش‌های تنظیمات",
  navShip: "ارسال و کانال‌ها",
  navPost: "تخمین هزینه پست",
  navGeneral: "عمومی", // NEW

  // [1] shipping and channels
  shipTitle: "ارسال و کانال‌ها",
  shipTitleMobile: "ارسال",
  channelsTitleMobile: "کانال‌ها",
  shipCaption: "این مقادیر فقط پیش‌فرض فرم ثبت فروش هستند و روی سفارش‌های ثبت‌شده اثری ندارند.",
  shippingLabel: "هزینه ارسال پیش‌فرض",
  shippingHelp: "برای کانال‌هایی که «هزینه ارسال» آن‌ها روشن است؛ در هر سفارش قابل تغییر است.",
  toman: "تومان",
  colChannel: "کانال",
  colShipping: "دریافت هزینه ارسال از مشتری",
  colPostage: "هزینه پست",
  colKit: "کیت بسته‌بندی پیش‌فرض",
  switchShippingMobile: "هزینه ارسال",
  switchPostageMobile: "هزینه پست",
  switchShippingAria: (channel: string) => `هزینه ارسال ${channel}`,
  switchPostageAria: (channel: string) => `هزینه پست ${channel}`,
  off: "خاموش",
  shipOn: (amount: number) => `${fa(amount)} تومان`,
  postOn: (estimate: number) => `تخمین ${fa(estimate)}`,
  noPackaging: "بدون بسته‌بندی",
  kitAria: (channel: string) => `کیت بسته‌بندی پیش‌فرض ${channel}`, // NEW
  kitInactive: (name: string) => `${name} (غیرفعال)`, // NEW
  kitInactiveTitle: "کیت پیش‌فرض غیرفعال", // NEW
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
  perOrder: "تومان / سفارش",
  divisor: (n: number, paid: number, orders: number) =>
    `جمع پرداختی ÷ جمع سفارش‌ها در ${fa(n)} پرداخت اخیر: ${fa(paid)} ÷ ${fa(orders)}`,
  divisorMobile: (paid: number, orders: number) => `جمع پرداختی ÷ جمع سفارش‌ها: ${fa(paid)} ÷ ${fa(orders)}`,
  fewerThanN: (count: number) => `فقط ${fa(count)} پرداخت ثبت شده؛ همه در محاسبه‌اند.`, // NEW
  noPayments: "هنوز پرداختی به پست ثبت نشده — از تخمین پیش‌فرض استفاده می‌شود.", // NEW

  // [3] general
  generalTitle: "عمومی", // NEW
  tzLabel: "منطقه زمانی", // NEW
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
  toastSaved: "تنظیمات ذخیره شد", // NEW
  close: "بستن",

  // change labels (dirty bar, partial-save messages)
  chShipping: "هزینه ارسال پیش‌فرض",
  chWindow: "تعداد پرداخت‌های اخیر", // NEW
  chDefaultPost: "تخمین پیش‌فرض پست", // NEW
  chChannelShipping: (channel: string) => `هزینه ارسال «${channel}»`, // NEW
  chChannelPostage: (channel: string) => `هزینه پست «${channel}»`, // NEW
  chChannelKit: (channel: string) => `کیت «${channel}»`,
  chChannel: (channel: string) => `تنظیمات «${channel}»`, // NEW

  // states
  loadingAria: "در حال بارگذاری",
  errorTitle: "تنظیمات بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",

  amountError: "این مبلغ بیش از حد بزرگ است.", // NEW
}

/** «a، b و c»; past `max` items, «a، b، c و ۲ مورد دیگر». */
export function joinList(items: string[], max = 3): string {
  const shown = items.length > max ? [...items.slice(0, max), S.more(items.length - max)] : items
  if (shown.length <= 1) return shown.join("")
  return `${shown.slice(0, -1).join(S.listSep)}${S.and}${shown[shown.length - 1]}`
}
