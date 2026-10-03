/**
 * Persian copy for «دسته‌ها» (manage categories). There is no design file for
 * this screen; tone and terms follow design 05 (products & materials).
 * «متریال», never «ماده».
 */

import type { CategoryKind } from "@/lib/api"
import { formatNumber } from "@/lib/persian-numbers"

const fa = formatNumber

/** «محصول» / «متریال» — the item noun for a tree. */
export const itemNoun = (kind: CategoryKind) => (kind === "PRODUCT" ? "محصول" : "متریال")

export const C = {
  tab: "دسته‌ها",
  kindLabel: "نوع دسته",
  kindProducts: "محصولات",
  kindMaterials: "متریال",
  add: "اضافه کردن دسته",

  // table
  colName: "نام دسته",
  colItems: "کالاها",
  colStatus: "وضعیت",
  colActions: "عملیات",
  subChip: "زیردسته",
  itemCount: (n: number, kind: CategoryKind) => `${fa(n)} ${itemNoun(kind)}`,
  inactiveCount: (n: number) => `(${fa(n)} غیرفعال)`,
  noItems: "بدون کالا",
  uncategorised: "بدون دسته",
  uncategorisedHelp: "متریال‌هایی که هنوز دسته ندارند.",
  showItems: (kind: CategoryKind) => (kind === "PRODUCT" ? "نمایش محصولات این دسته" : "نمایش متریال‌های این دسته"),
  // Strict leaf assignment: items left on a parent once it has subcategories.
  strandedNote: (n: number, kind: CategoryKind, parent: string) =>
    `${fa(n)} ${itemNoun(kind)} هنوز روی خود «${parent}» است — به یکی از زیردسته‌ها منتقل کنید.`,
  parentInactiveNote: (parent: string) => `دسته‌ی اصلی «${parent}» غیرفعال است؛ اول آن را فعال کنید.`,
  footnote:
    "دسته‌ها حذف نمی‌شوند؛ غیرفعال کردن، دسته را از فهرست انتخاب پنهان می‌کند. هر کالا فقط در دسته‌ای قرار می‌گیرد که زیردسته‌ی فعال ندارد.",

  // row actions
  addSub: "افزودن زیردسته",
  rename: "تغییر نام",
  move: "انتقال کالاها",
  moveShort: "انتقال",
  deactivate: "غیرفعال کردن",
  reactivate: "فعال کردن دوباره",
  moreActions: (name: string) => `عملیات «${name}»`,

  // create / rename drawer
  newTitle: "دسته‌ی جدید",
  newSubTitle: "زیردسته‌ی جدید",
  renameTitle: "تغییر نام دسته",
  fieldLevel: "سطح",
  levelTop: "دسته‌ی اصلی",
  levelSub: "زیردسته",
  fieldParent: "دسته‌ی اصلی",
  pickParent: "انتخاب دسته‌ی اصلی",
  noParents: "دسته‌ی اصلیِ فعالی وجود ندارد؛ اول یک دسته‌ی اصلی بسازید.",
  parentRequired: "دسته‌ی اصلی را انتخاب کنید.",
  parentUnavailable: "این دسته‌ی اصلی دیگر قابل انتخاب نیست (غیرفعال شده یا تغییر کرده)؛ فهرست به‌روز شد، دوباره انتخاب کنید.",
  fieldName: "نام",
  namePlaceholder: "مثلاً وینیل",
  nameRequired: "نام را وارد کنید.",
  nameUnchanged: "نام تغییری نکرده است.",
  duplicateActive: (name: string) => `دسته‌ای با نام «${name}» در همین سطح وجود دارد.`,
  duplicateInactive: (name: string) =>
    `دسته‌ای غیرفعال با نام «${name}» در همین سطح وجود دارد و نامش رزرو است. می‌توانید همان را دوباره فعال کنید.`,
  duplicateUnknown: "دسته‌ای با این نام در همین سطح وجود دارد.",
  splitWarn: (n: number, kind: CategoryKind, parent: string) =>
    `${fa(n)} ${itemNoun(kind)} در «${parent}» هست. بعد از ساختن زیردسته همان‌جا می‌مانند تا منتقلشان کنید؛ ${itemNoun(kind)}های جدید باید در یکی از زیردسته‌ها قرار بگیرند.`,
  topHelp: "دسته‌ی اصلی می‌تواند زیردسته داشته باشد؛ زیردسته‌ها زیردسته‌ی دیگری ندارند.",
  create: "ساختن",
  save: "ذخیره",
  cancel: "انصراف",

  // deactivate dialog
  deactivateTitle: (name: string) => `غیرفعال کردن «${name}»؟`,
  deactivateSubtitle: "دسته‌ها حذف نمی‌شوند تا سوابق حفظ شود.",
  effHidden: "از فهرست انتخاب دسته پنهان می‌شود و کالای جدیدی در آن قرار نمی‌گیرد.",
  effHistory: "سفارش‌ها، گزارش‌ها و تاریخچه دست‌نخورده می‌مانند.",
  deactivateFinal: "هر زمان با روشن کردن «نمایش غیرفعال‌ها» می‌توانید دوباره فعالش کنید.",
  blockedTitle: (name: string) => `«${name}» فعلاً غیرفعال نمی‌شود`,
  blockedSubtitle: "پیش از غیرفعال کردن، این موارد را برطرف کنید.",
  blockedItems: (n: number, kind: CategoryKind) =>
    `این دسته هنوز ${fa(n)} ${itemNoun(kind)} دارد (${itemNoun(kind)}های غیرفعال هم حساب می‌شوند). پیش از غیرفعال کردن، آن‌ها را به دسته‌ی دیگری منتقل کنید.`,
  blockedItemsNoCount: (kind: CategoryKind) =>
    `این دسته هنوز ${itemNoun(kind)} دارد (${itemNoun(kind)}های غیرفعال هم حساب می‌شوند). پیش از غیرفعال کردن، آن‌ها را به دسته‌ی دیگری منتقل کنید.`,
  blockedChildren: (names: string[]) =>
    names.length
      ? `این دسته زیردسته‌ی فعال دارد: ${names.join("، ")}. اول زیردسته‌ها را غیرفعال کنید.`
      : "این دسته زیردسته‌ی فعال دارد. اول زیردسته‌ها را غیرفعال کنید.",
  moveItems: (kind: CategoryKind) => (kind === "PRODUCT" ? "انتقال محصولات" : "انتقال متریال‌ها"),
  understood: "متوجه شدم",

  // move sheet
  moveTitle: (from: string) => `انتقال کالاها از «${from}»`,
  fieldDestination: "دسته‌ی مقصد",
  noDestination: "دسته‌ی دیگری برای انتقال وجود ندارد؛ اول یک دسته‌ی فعال بسازید.",
  destinationRequired: "دسته‌ی مقصد را انتخاب کنید.",
  destinationUnavailable:
    "دسته‌ی مقصد دیگر قابل انتخاب نیست (غیرفعال شده یا زیردسته‌ی فعال دارد)؛ فهرست به‌روز شد، مقصد را دوباره انتخاب کنید.",
  destinationHelp: "فقط دسته‌هایی که زیردسته‌ی فعال ندارند قابل انتخاب‌اند.",
  selectAll: "انتخاب همه",
  selectedOf: (n: number, total: number) => `${fa(n)} از ${fa(total)} انتخاب شده`,
  moveN: (n: number, kind: CategoryKind) => `انتقال ${fa(n)} ${itemNoun(kind)}`,
  progress: (done: number, total: number) => `در حال انتقال… ${fa(done)} از ${fa(total)}`,
  summary: (ok: number, failed: number) => `${fa(ok)} منتقل شد، ${fa(failed)} ناموفق.`,
  retryFailed: "تلاش دوباره برای ناموفق‌ها",
  stQueued: "در صف",
  stSubmitting: "در حال انتقال",
  stDone: "منتقل شد",
  stFailed: "ناموفق",
  inactiveItem: "غیرفعال",
  emptySource: "کالایی در این دسته نمانده است.",
  close: "بستن",

  // states
  emptyTitle: (kind: CategoryKind) =>
    kind === "PRODUCT" ? "هنوز دسته‌ای برای محصولات تعریف نشده" : "هنوز دسته‌ای برای متریال‌ها تعریف نشده",
  emptyBody: (kind: CategoryKind) =>
    kind === "PRODUCT"
      ? "دسته‌ها محصولات را در فهرست‌ها و گزارش‌ها گروه‌بندی می‌کنند. هر محصول باید یک دسته داشته باشد."
      : "دسته‌ها متریال‌ها را گروه‌بندی می‌کنند. دسته برای متریال اختیاری است.",
  emptyCta: "اضافه کردن اولین دسته",
  allInactiveTitle: "همه‌ی دسته‌ها غیرفعال‌اند",
  allInactiveCta: "نمایش غیرفعال‌ها",

  // toasts
  toastCreated: (name: string) => `دسته‌ی «${name}» اضافه شد`,
  toastRenamed: (name: string) => `نام دسته به «${name}» تغییر کرد`,
  toastDeactivated: (name: string) => `«${name}» غیرفعال شد`,
  toastReactivated: (name: string) => `«${name}» دوباره فعال شد`,
  toastMoved: (n: number, kind: CategoryKind, to: string) => `${fa(n)} ${itemNoun(kind)} به «${to}» منتقل شد`,

  saveFailed: "ذخیره انجام نشد",
} as const
