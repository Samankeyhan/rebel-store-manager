/**
 * Packaging screen copy (design/screens/08-packaging.md §2, verbatim, with
 * «ماده» standardized on «متریال»). Strings the design doesn't have are // NEW.
 */

import { currencyLabel, formatMoney } from "@/lib/money"
import { formatNumber, formatQuantity } from "@/lib/persian-numbers"

export const K = {
  hint: "هزینه هر کیت از بهای فعلی متریال‌ها محاسبه می‌شود و با هر خرید جدید به‌روز می‌شود.",
  newKit: "کیت جدید",
  listLabel: "کیت‌ها",
  showInactive: "نمایش غیرفعال‌ها", // NEW
  inactive: "غیرفعال", // NEW
  itemCount: (n: number) => (n === 0 ? "بدون متریال" : `${formatNumber(n)} متریال`),
  noDefault: "پیش‌فرض هیچ کانالی نیست",
  noDefaultTile: "هیچ کانالی",
  unlimited: "نامحدود",
  availLow: (n: number) => `فقط ${formatNumber(n)} کیت با موجودی فعلی`,
  availOk: (n: number) => `${formatNumber(n)} کیت قابل آماده‌سازی`,

  // «بدون بسته‌بندی» (channels whose default is no kit)
  noPackaging: "بدون بسته‌بندی",
  noPackagingMeta: "پیش‌فرض این کانال‌ها: بدون کیت؛ هزینه بسته‌بندی صفر.", // NEW
  noPackagingNone: "همه کانال‌ها کیت پیش‌فرض دارند.", // NEW

  // editor
  deactivate: "غیرفعال کردن",
  inactiveNote: "این کیت غیرفعال است و در ثبت فروش انتخاب نمی‌شود.", // NEW
  reactivate: "فعال کردن دوباره",
  toastReactivated: (name: string) => `کیت «${name}» دوباره فعال شد`, // NEW
  nameReadOnly: "نام کیت پس از ساخت قابل تغییر نیست.", // NEW
  colMaterial: "متریال",
  colQty: "مقدار در هر کیت",
  colUnitCost: "بهای واحد فعلی",
  colLineCost: "هزینه در کیت",
  stockCaption: (q: number, unit: string) => `موجودی ${formatQuantity(q)} ${unit}`,
  unitCost: (cost: number, unit: string) => `${formatMoney(cost)} / ${unit}`,
  delete: "حذف",
  addMaterial: "افزودن متریال",
  searchMaterial: "جستجوی متریال", // NEW
  noMaterialsLeft: "متریال کالایی فعالِ دیگری برای افزودن نیست.", // NEW
  noMaterialMatch: (q: string) => `متریالی با «${q}» پیدا نشد.`, // NEW
  emptyKit: "این کیت متریالی ندارد و هزینه آن صفر است.",
  qtyInvalid: "مقدار باید بیشتر از صفر باشد.", // NEW
  duplicate: "این متریال در کیت هست.", // NEW
  savesNote: "هر تغییر همان لحظه ذخیره می‌شود.", // NEW
  tileCost: "هزینه هر کیت",
  tileCostNote: "با بهای فعلی متریال‌ها",
  tileChannels: "پیش‌فرض کانال‌ها",
  tileChannelsLink: "تغییر در تنظیمات",
  tileAvail: "کیت قابل آماده‌سازی",
  limiting: (name: string, q: number, unit: string) => `محدودکننده: «${name}» (${formatQuantity(q)} ${unit})`,
  noLimit: "بدون محدودیت",
  get toman() {
    return currencyLabel()
  },
  editKit: "ویرایش کیت",
  pickKit: "کیتی را انتخاب کنید.", // NEW

  // new kit
  newKitTitle: "کیت جدید", // NEW
  fieldName: "نام کیت",
  namePlaceholder: "مثلاً: جعبه استاندارد", // NEW
  nameRequired: "نام کیت را وارد کنید.", // NEW
  create: "ساخت کیت", // NEW
  cancel: "انصراف",
  toastCreated: (name: string) => `کیت «${name}» ساخته شد`, // NEW

  // deactivate
  deactTitle: (name: string) => `غیرفعال کردن «${name}»؟`, // NEW
  deactSubtitle: "کیت حذف نمی‌شود و سفارش‌های قبلی دست نمی‌خورند؛ فقط دیگر انتخاب نمی‌شود.", // NEW
  deactNoChannels: "این کیت پیش‌فرض هیچ کانالی نیست.", // NEW
  deactChannelsLead: "این کیت پیش‌فرض این کانال‌هاست:", // NEW
  deactChannelsBody:
    "با کیت غیرفعال، ثبت فروش این کانال‌ها با کیت پیش‌فرض رد می‌شود. پیش‌فرض جدید هر کانال را انتخاب کنید:", // NEW
  pickReplacement: "انتخاب پیش‌فرض جدید", // NEW
  replacementRequired: "برای همه کانال‌ها پیش‌فرض جدید را انتخاب کنید.", // NEW
  deactConfirm: "غیرفعال کن", // NEW
  deactChannelFailed: (channel: string, msg: string) => `پیش‌فرض «${channel}» ذخیره نشد: ${msg}`, // NEW
  deactPartial: (channels: string) => `پیش‌فرض این کانال‌ها تغییر کرد: ${channels}. کیت غیرفعال نشد.`, // NEW
  toastDeactivated: (name: string) => `کیت «${name}» غیرفعال شد`, // NEW

  saveFailed: "ثبت نشد", // NEW
  close: "بستن",

  // states
  emptyTitle: "هنوز کیتی تعریف نشده",
  emptyBody: "کیت بسته‌بندی مجموعه‌ای از متریال‌هاست (مثلاً کارتن، نوار چسب، پرکننده) که با هر سفارش ارسالی از موجودی کم می‌شود.",
  emptyBodyMobile: "کیت‌ها با هر سفارش ارسالی از موجودی کم می‌شوند.",
  emptyCta: "تعریف اولین کیت",
  emptyCtaMobile: "تعریف کیت",
  errorTitle: "کیت‌های بسته‌بندی بارگذاری نشد",
  errorTitleMobile: "کیت‌ها بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",
  loadingAria: "در حال بارگذاری",
}
