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
