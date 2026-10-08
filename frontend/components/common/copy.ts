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
