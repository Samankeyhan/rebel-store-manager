/**
 * Postage screen copy (design/screens/09-postage.md §2, verbatim).
 * Strings the design doesn't have are marked // NEW.
 */

import { formatNumber } from "@/lib/persian-numbers"

const fa = formatNumber

export const T = {
  // hero
  heroLabel: "تخمین فعلی هزینه پست برای سفارش‌های جدید",
  heroLabelMobile: "تخمین فعلی پست برای سفارش‌های جدید",
  perOrder: "تومان / سفارش",
  toman: "تومان",
  heroCaption: (n: number, channels: string) =>
    `جمع پرداختی ÷ جمع سفارش‌ها در ${fa(n)} پرداخت اخیر${channels ? ` · برای ${channels}` : ""}`,
  heroCaptionMobile: (total: number, orders: number, n: number) =>
    `جمع پرداختی ÷ جمع سفارش‌ها: ${fa(total)} ÷ ${fa(orders)} در ${fa(n)} پرداخت اخیر`,
  heroDefault: "هنوز پرداختی ثبت نشده؛ این مقدار پیش‌فرض تنظیمات است.", // NEW
  heroNotAverage: "میانگین نرخ تک‌تک پرداخت‌ها نیست؛ جمع مبالغ تقسیم بر جمع سفارش‌هاست.", // NEW
  windowLink: (n: number) => `تعداد پرداخت‌ها: ${fa(n)} · تغییر`,
  and: " و ",
  listSep: "، ",

  // form
  formTitle: "ثبت پرداخت به پست",
  fieldDate: "تاریخ پرداخت",
  fieldDateMobile: "تاریخ",
  today: "امروز",
  fieldTotal: "مبلغ کل پرداختی",
  fieldOrders: "تعداد سفارش ارسالی",
  orderSuffix: "سفارش",
  ordersError: "تعداد سفارش باید دست‌کم ۱ باشد.",
  totalZero: "مبلغ صفر است؛ تخمین پست را پایین می‌آورد.", // NEW
  rateLabel: "هزینه هر سفارش در این پرداخت",
  projLabel: "پس از ثبت، تخمین فروشگاه",
  projLabelMobile: "تخمین پس از ثبت",
  projDropped: (date: string) => ` — پرداخت ${date} از محاسبه خارج می‌شود.`,
  projOutside: "این پرداخت با این تاریخ خارج از پرداخت‌های اخیر است و تخمین را تغییر نمی‌دهد.", // NEW
  projNote: "پیش‌نمایش است؛ تخمین نهایی پس از ثبت از سرور خوانده می‌شود.", // NEW
  help: "سفارش‌های قبلی تغییر نمی‌کنند. اختلاف پرداخت واقعی با تخمین‌ها در گزارش سود و زیان به‌عنوان «مغایرت هزینه پست» می‌آید.",
  fieldNote: "یادداشت",
  notePlaceholder: "مثلاً: شماره رسید اداره پست",
  submit: "ثبت پرداخت",
  saveFailed: "ثبت نشد", // NEW
  toastSaved: (estimate: number) => `پرداخت ثبت شد · تخمین جدید: ${fa(estimate)} تومان / سفارش`, // NEW

  // ledger
  ledgerTitle: "پرداخت‌ها به پست",
  colDate: "تاریخ",
  colTotal: "مبلغ پرداختی (تومان)",
  colOrders: "تعداد سفارش",
  colRate: "هزینه هر سفارش (تومان)",
  inWindow: "در تخمین فعلی",
  footerMonth: (month: string) => `جمع ${month}`,
  footerRange: "جمع این بازه", // NEW
  footerNote: "جمع ÷ جمع",
  noMatch: "پرداختی در این بازه نیست.", // NEW
  recent: "پرداخت‌های اخیر",
  recentMeta: (date: string, n: number) => `${date} · ${fa(n)} سفارش`,
  recentRate: (rate: number) => `${fa(rate)} / سفارش`,

  // states
  emptyTitle: "هنوز پرداختی به پست ثبت نشده",
  emptyTitleMobile: "هنوز پرداختی ثبت نشده",
  emptyBody:
    "تا ثبت اولین پرداخت، تخمین پست برای سفارش‌ها صفر است. هر بار که هزینه چند مرسوله را یک‌جا پرداخت می‌کنید، مبلغ و تعداد سفارش‌ها را این‌جا ثبت کنید.",
  emptyBodyMobile: "تا اولین پرداخت، تخمین پست صفر است.",
  emptyCta: "ثبت اولین پرداخت",
  errorTitle: "پرداخت‌های پست بارگذاری نشد",
  errorTitleMobile: "پرداخت‌ها بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",
  loadingAria: "در حال بارگذاری",
  close: "بستن",
}
