/**
 * Copy for shared components (components/common, MoneyInput). // NEW file
 */

import { currencyLabel, type MoneyInputError } from "../../lib/money.ts"

export const M = {
  negative: "مبلغ منفی مجاز نیست", // NEW
  get tomanDecimals() {
    return `در ${currencyLabel("TOMAN")} حداکثر یک رقم اعشار مجاز است` // NEW
  },
  get rialDecimal() {
    return `${currencyLabel("RIAL")} عدد صحیح است و اعشار ندارد` // NEW
  },
  tooLarge: "این مبلغ بیش از حد بزرگ است", // NEW
  reenter: "این مبلغ را دوباره وارد کنید.", // NEW
}

/** The message under a MoneyInput whose text gives no exact Rial amount. */
export function moneyInputMessage(error: MoneyInputError): string {
  return M[error]
}

const NAME_TAKEN_BY: Record<string, string> = {
  product: "محصولی", // NEW
  material: "متریالی", // NEW
  supplier: "تأمین‌کننده‌ای", // NEW
  partner: "شریکی", // NEW
  category: "دسته‌ای", // NEW
  payment_method: "روش پرداختی", // NEW
  packaging_kit: "کیتی", // NEW
  expense_category: "دسته هزینه‌ای", // NEW
}

/** The message under a name field when the name (or a spelling variant of it) is already taken. */
export function nameDuplicateMessage(entity: string | null): string {
  const what = (entity != null && NAME_TAKEN_BY[entity]) || "موردی" // NEW
  return `${what} با این نام (یا نوشتاری مشابه، مثلاً «ي» و «ی») از قبل وجود دارد. نام دیگری انتخاب کنید.` // NEW
}

/** Row actions and the delete confirmation shared by the expenses and postage screens. */
export const RowActions = {
  menuAria: "عملیات ردیف", // NEW
  edit: "ویرایش", // NEW
  remove: "حذف", // NEW
  cancel: "انصراف", // NEW
  deleting: "در حال حذف…", // NEW
  deleteNote: "حذف دائمی است و برگرداندن ندارد؛ فقط سابقهٔ آن در گزارش تغییرات می‌ماند.", // NEW
}

/**
 * The refusal for a change or delete on a day closed by a profit payout (409 PERIOD_ALREADY_DISTRIBUTED).
 * `periodEnd` is a formatted Jalali day. No way out is promised: there is no undo for a payout.
 */
export function closedDayMessage(periodEnd: string): string {
  return `این روز با تقسیم سود تا تاریخ ${periodEnd} بسته شده است؛ مبلغ یا تاریخ آن را نمی‌شود تغییر داد و خودِ ردیف را هم نمی‌شود حذف کرد.` // NEW
}
