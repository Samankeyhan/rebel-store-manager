/**
 * Every Persian string on the record-sale screen, verbatim from
 * design/screens/02-record-sale.md §2 (plus the few strings agreed for the
 * made-to-order rule). Amounts and counts are interpolated from live data —
 * never the design's sample numbers.
 */

import { Boxes, Camera, Ellipsis, Globe, Store, type LucideIcon } from "lucide-react"
import { currencyLabel, formatMoney } from "@/lib/money"
import { formatNumber, toPersianDigits } from "@/lib/persian-numbers"

export const CHANNEL_IDS = [
  "WEBSITE",
  "INSTAGRAM",
  "WHOLESALE",
  "IN_PERSON",
  "OTHER",
] as const
export type Channel = (typeof CHANNEL_IDS)[number]

export const STATUS_IDS = ["DRAFT", "PENDING", "PAID", "COMPLETED"] as const
export type SaleStatus = (typeof STATUS_IDS)[number]

type ChannelMeta = {
  name: string
  icon: LucideIcon
  /** Tailwind classes; literal so the JIT sees them. */
  text: string
  square: string
  /** Line 2 of the tile when the channel applies no shipping charge. */
  noShipTile: string
  /** Shipping help when the channel applies no shipping charge. */
  noShipHelp: string
}

export const CHANNELS: Record<Channel, ChannelMeta> = {
  WEBSITE: {
    name: "وب‌سایت",
    icon: Globe,
    text: "text-ch-web",
    square: "bg-ch-web",
    noShipTile: "بدون هزینه ارسال",
    noShipHelp: "در صورت نیاز مبلغ را وارد کنید.",
  },
  INSTAGRAM: {
    name: "اینستاگرام",
    icon: Camera,
    text: "text-ch-insta",
    square: "bg-ch-insta",
    noShipTile: "بدون هزینه ارسال",
    noShipHelp: "در صورت نیاز مبلغ را وارد کنید.",
  },
  WHOLESALE: {
    name: "عمده‌فروشی",
    icon: Boxes,
    text: "text-ch-wholesale",
    square: "bg-ch-wholesale",
    noShipTile: "بدون هزینه ارسال",
    noShipHelp:
      "عمده‌فروشی هزینه ارسال از مشتری نمی‌گیرد؛ هزینه پست جداگانه ثبت می‌شود.",
  },
  IN_PERSON: {
    name: "حضوری",
    icon: Store,
    text: "text-ch-inperson",
    square: "bg-ch-inperson",
    noShipTile: "بدون ارسال",
    noShipHelp: "فروش حضوری ارسال ندارد.",
  },
  OTHER: {
    name: "سایر",
    icon: Ellipsis,
    text: "text-ch-other",
    square: "bg-ch-other",
    noShipTile: "مقادیر دستی",
    noShipHelp: "در صورت نیاز مبلغ را وارد کنید.",
  },
}

export const STATUSES: Record<SaleStatus, { name: string; help: string; badge: string }> = {
  DRAFT: {
    name: "پیش‌نویس",
    help: "فقط ذخیره می‌شود؛ بعداً می‌توانید آن را به «در انتظار»، «پرداخت‌شده» یا «تکمیل‌شده» تغییر دهید.",
    badge: "border border-dashed border-border-strong bg-card text-text-2",
  },
  PENDING: {
    name: "در انتظار",
    help: "کالا و بسته‌بندی کسر می‌شود؛ پس از دریافت وجه، وضعیت را «پرداخت‌شده» کنید.",
    badge: "bg-warn-soft text-warn",
  },
  PAID: {
    name: "پرداخت‌شده",
    help: "وجه دریافت شده ولی سفارش هنوز ارسال یا تحویل نشده است.",
    badge: "bg-info-soft text-info",
  },
  COMPLETED: {
    name: "تکمیل‌شده",
    help: "وجه دریافت و سفارش ارسال یا تحویل شده است.",
    badge: "bg-profit-soft text-profit",
  },
}

const fa = toPersianDigits

export const T = {
  // channel card
  channelCard: "کانال فروش و مشتری",
  channelCardCaption: "پیش‌فرض‌ها بر اساس کانال پر می‌شوند",
  channelLabel: "کانال فروش",
  channelHelp:
    "تغییر کانال، هزینه ارسال و بسته‌بندی را به پیش‌فرض همان کانال برمی‌گرداند و هزینه پست را روشن یا خاموش می‌کند و قیمت‌ها را خرده یا عمده می‌کند؛ قیمت‌هایی که دستی ویرایش کرده‌اید دست نمی‌خورند.",
  tileShip: (amount: number) => `ارسال ${formatMoney(amount)}`,
  tilePostOn: "با هزینه پست",
  tilePostOff: "بدون پست",
  customerLabel: "نام مشتری",
  optional: "(اختیاری)",
  customerPlaceholder: "مثلاً: خریدار اینستاگرام",
  customerHelp: "روی فاکتور چاپ می‌شود.",

  // items card
  itemsCard: "اقلام سفارش",
  rowCount: (n: number) => `${fa(n)} ردیف`,
  colProduct: "محصول",
  colQty: "تعداد",
  get colUnitPrice() {
    return `قیمت واحد (${currencyLabel()})`
  },
  colRowTotal: "جمع ردیف",
  pickProduct: "انتخاب محصول…",
  pickProductHelp: "جستجو با نام یا دسته",
  outOfStock: "ناموجود",
  stockPill: (n: number) => `موجودی ${formatNumber(n)}`,
  priceRetail: "قیمت خرده",
  priceWholesale: "قیمت عمده",
  priceManual: (def: number) => `دستی · پیش‌فرض ${formatMoney(def)}`,
  addDiscount: "افزودن تخفیف",
  discountAmount: "مبلغ تخفیف",
  discountReason: "دلیل تخفیف",
  discountReasonPlaceholder: "مثلاً: مشتری ثابت",
  removeDiscount: "حذف تخفیف",
  addRow: "افزودن ردیف",
  addProductMobile: "افزودن محصول",
  itemsNetFooter: "جمع اقلام پس از تخفیف:",
  rowTotalMobile: "جمع:",
  get toman() {
    return currencyLabel()
  },
  increase: "افزایش",
  decrease: "کاهش",
  removeRow: "حذف ردیف",
  unitPriceAria: "قیمت واحد",

  // made-to-order (agreed additions)
  madeToOrder: "ساخت هنگام فروش",
  recipeChecking: "در حال بررسی دستور تولید…",
  estimatedCost: (n: number) => `بهای تخمینی ${formatMoney(n)}`,

  // picker
  pickerSearchPlaceholder: "جستجوی نام یا دسته…",
  pickerSearchAria: "جستجوی محصول",
  pickerListAria: "فهرست محصولات",
  pickerPriceCol: (wholesale: boolean) => (wholesale ? "قیمت عمده" : "قیمت خرده"),
  pickerStockCol: "موجودی",
  pickerNoCost: "بهای تمام‌شده ثبت نشده",
  pickerStockUnits: (n: number) => `${formatNumber(n)} عدد`,
  pickerNoResult: (q: string) => `محصولی با «${q}» پیدا نشد.`,

  // shipping & packaging
  shippingCard: "ارسال و بسته‌بندی",
  shippingLabel: "هزینه ارسال دریافتی از مشتری",
  shippingLabelMobile: "هزینه ارسال دریافتی",
  shippingDefaultHelp: (channelName: string) => `پیش‌فرض ${channelName}؛ قابل ویرایش است.`,
  shippingOverride: (channelName: string, def: number) =>
    `مقدار دستی — پیش‌فرض «${channelName}» ${formatMoney(def)} است.`,
  shippingOverrideMobile: (def: number) => `مقدار دستی — پیش‌فرض ${formatMoney(def)} ·`,
  restore: "بازگردانی",
  kitLabel: "کیت بسته‌بندی",
  internalChip: "هزینه داخلی",
  kitCost: (n: number) => (n ? formatMoney(n) : "بدون هزینه"),
  noKit: "بدون بسته‌بندی",
  noKitDesc: "تحویل دستی",
  defaultTag: "پیش‌فرض",
  kitHelp: "با ثبت فروش، یک عدد از این کیت از موجودی بسته‌بندی کم می‌شود.",

  // internal costs
  internalCard: "هزینه‌های داخلی",
  internalCardCaption: "به مشتری نمایش داده نمی‌شود",
  get internalMobileNote() {
    return `مبالغ به ${currencyLabel()} · به مشتری نمایش داده نمی‌شود.`
  },
  postageLabel: "هزینه پست (تخمینی)",
  postageLabelMobile: "پست (تخمینی)",
  postageOn: "روشن برای این کانال",
  postageOff: "خاموش برای این کانال",
  postageHelpOn: (window: number) =>
    `جمع پرداختی ÷ جمع سفارش‌ها در ${fa(window)} پرداخت اخیر به پست · یک تخمین برای کل فروشگاه؛ مبلغ واقعی را پس از ارسال در سفارش ثبت کنید.`,
  postageHelpOff: (channelName: string) => `«${channelName}» ارسال پستی ندارد؛ هزینه پست صفر است.`,
  postageHint: (window: number) => `جمع پرداختی ÷ جمع سفارش‌ها در ${fa(window)} پرداخت اخیر`,
  postageHintShort: "جمع پرداختی ÷ جمع سفارش‌ها",
  feeLabel: "کارمزد تراکنش",
  feeHelp: "کارمزد درگاه پرداخت یا کارت‌خوان، اگر دارد.",

  // status
  statusCard: "وضعیت سفارش",
  statusAria: "وضعیت",
  draftNoteBold: "پیش‌نویس موجودی را رزرو نمی‌کند",
  draftNoteRest:
    " و در گزارش فروش و سود حساب نمی‌شود؛ سایر وضعیت‌ها کالا و بسته‌بندی را همان لحظه از موجودی کم می‌کنند.",
  draftNoteRestMobile: "؛ سایر وضعیت‌ها کالا و بسته‌بندی را همان لحظه از موجودی کم می‌کنند.",

  // summary
  summaryAria: "خلاصه سفارش",
  customerPart: "پرداختی مشتری",
  itemsGross: (qty: number) => `جمع اقلام (${formatNumber(qty)} عدد)`,
  discount: "تخفیف",
  shipping: "هزینه ارسال",
  manualChip: "دستی",
  payable: "مبلغ قابل پرداخت",
  internalPart: "داخلی",
  internalPartCaption: "هرگز به مشتری نمایش داده نمی‌شود",
  internalPartMobile: "داخلی — به مشتری نمایش داده نمی‌شود",
  cogs: "بهای تمام‌شده کالا",
  packaging: (kitName: string) => `بسته‌بندی · ${kitName}`,
  postageRow: "پست (تخمینی)",
  fee: "کارمزد تراکنش",
  profit: "سود این سفارش",
  loss: "زیان این سفارش",
  unknown: "نامشخص",
  margin: "حاشیه سود",
  shipEcon: "ارسال این سفارش: دریافتی",
  shipEconCost: "− هزینه",
  saveSale: "ثبت فروش",
  saveDraft: "ذخیره پیش‌نویس",
  saving: "در حال ثبت…",
  cancel: "انصراف",
  quickSave: "ثبت سریع",
  profitShort: "سود",
  showSummary: "نمایش خلاصه کامل",
  close: "بستن",

  // validation
  errorCount: (n: number) => `${fa(n)} مورد مانع ثبت است`,
  v1: (row: number) => `برای ردیف ${fa(row)} محصول انتخاب نشده است.`,
  v2Blocking: (available: string, name: string) =>
    `موجودی کافی نیست — فقط ${available} «${name}» موجود است.`,
  v2BlockingZero: (name: string) =>
    `«${name}» ناموجود است؛ برای ثبت با این وضعیت ابتدا موجودی را افزایش دهید.`,
  v2UseMax: (n: number) => `تعداد را ${formatNumber(n)} کن`,
  v2Summary: (name: string) => `تعداد «${name}» از موجودی بیشتر است.`,
  v2Draft: (name: string, stock: number) =>
    `پیش‌نویس موجودی را رزرو نمی‌کند — موجودی فعلی «${name}»: ${
      stock === 0 ? "ناموجود" : `${formatNumber(stock)} عدد`
    }. پیش از تغییر وضعیت، موجودی را بررسی کنید.`,
  saveAsDraft: "ذخیره به‌عنوان پیش‌نویس",
  v3BannerTitle: (name: string) => `«${name}» بهای تمام‌شده ندارد — ثبت با این وضعیت ممکن نیست`,
  v3BannerBody:
    "تا بهای تمام‌شده این محصول مشخص نشود، سود این سفارش قابل محاسبه نیست. ابتدا در «محصولات و متریال» بهای تمام‌شده را وارد کنید (یا از تولید/خرید محاسبه شود)، سپس به همین فرم برگردید؛ اطلاعات فرم حفظ می‌شود. اگر عجله دارید، فعلاً به‌صورت پیش‌نویس ذخیره کنید.",
  v3SetCost: "ثبت بهای تمام‌شده",
  v3Inline:
    "بهای تمام‌شده این محصول ثبت نشده است؛ ثبت با وضعیت‌های در انتظار، پرداخت‌شده و تکمیل‌شده مسدود است.",
  v3Summary: (name: string) => `«${name}» بهای تمام‌شده ندارد.`,
  v3DraftTitle: (name: string) => `«${name}» بهای تمام‌شده ندارد — سود این سفارش نامشخص می‌ماند`,
  v3DraftBody:
    "پیش‌نویس ذخیره می‌شود، ولی تا ثبت بهای تمام‌شده نمی‌توان سود را حساب کرد و وضعیت را از «پیش‌نویس» تغییر داد.",
  v3DraftInline:
    "بهای تمام‌شده این محصول ثبت نشده است؛ در پیش‌نویس اشکالی ندارد، فقط سود «نامشخص» می‌ماند.",
  noRecipe: (name: string) => `«${name}» دستور تولید ندارد — ثبت با این وضعیت ممکن نیست`,
  noRecipeSummary: (name: string) => `«${name}» دستور تولید ندارد.`,
  noRecipeDraft: (name: string) =>
    `پیش‌نویس ذخیره می‌شود، ولی «${name}» دستور تولید ندارد؛ پیش از تغییر وضعیت آن را تعریف کنید.`,
  v4: (discount: number, gross: number) =>
    `تخفیف (${formatMoney(discount)}) از جمع این ردیف (${formatMoney(gross)}) بیشتر است. حداکثر تخفیف ${formatMoney(gross)} است.`,
  v4Summary: (name: string) => `تخفیف «${name}» از جمع ردیف بیشتر است.`,
  v5: "حداقل یک قلم به سفارش اضافه کنید.",
  vMoney: "مبلغی که وارد شده دقیق نیست؛ آن را اصلاح کنید.", // NEW (MoneyInput null: Rial amount not a multiple of 10)
  v6: "تعداد باید حداقل ۱ باشد.",
  saveFailedTitle: "ثبت سفارش انجام نشد",
  errorCode: "کد خطا:",

  // success
  successTitle: "فروش ثبت شد",
  tileTotal: "مبلغ کل",
  tileProfit: "سود",
  tileItems: "اقلام",
  units: (n: number) => `${formatNumber(n)} عدد`,
  stockNote: (qty: number, kitName: string | null) =>
    kitName
      ? `موجودی ${formatNumber(qty)} کالا و ۱ «${kitName}» کسر شد.`
      : `موجودی ${formatNumber(qty)} کالا کسر شد.`,
  stockNoteDraft: "پیش‌نویس ذخیره شد؛ موجودی تغییری نکرد.",
  printInvoice: "چاپ فاکتور (PDF)",
  viewOrder: "مشاهده سفارش",
  newSale: "ثبت فروش جدید",
  toastTitle: (inv: string) => `سفارش ${inv} ذخیره شد`,
  toastBody: "موجودی و گزارش‌ها به‌روز شدند.",

  // load states
  loadErrorTitle: "فهرست محصولات و کیت‌های بسته‌بندی بارگذاری نشد",
  loadErrorTitleMobile: "فهرست محصولات بارگذاری نشد",
  loadErrorBody:
    "بدون موجودی و بهای تمام‌شده به‌روز نمی‌توان فروش را ثبت کرد. اتصال را بررسی کنید و دوباره تلاش کنید.",
  loadErrorBodyMobile: "بدون موجودی و بهای تمام‌شده به‌روز نمی‌توان فروش را ثبت کرد.",
  retry: "تلاش دوباره",
  productsUnavailable: "محصولات در دسترس نیستند",
  emptyTitle: "برای ثبت فروش، ابتدا محصول تعریف کنید",
  emptyBody:
    "هنوز هیچ محصولی ثبت نشده است. هر محصول به قیمت خرده، قیمت عمده و بهای تمام‌شده نیاز دارد تا سود هر فروش درست محاسبه شود.",
  emptyTitleMobile: "ابتدا محصول تعریف کنید",
  emptyBodyMobile: "هر محصول به قیمت خرده، قیمت عمده و بهای تمام‌شده نیاز دارد تا سود هر فروش محاسبه شود.",
  addProduct: "افزودن محصول",
  defineKit: "تعریف کیت بسته‌بندی",
} as const
