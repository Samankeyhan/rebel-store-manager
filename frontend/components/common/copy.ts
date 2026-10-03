/**
 * Copy for shared components (components/common, MoneyInput). // NEW file
 */

import { currencyLabel } from "@/lib/money"

export const M = {
  // Only shown in Rial mode (a Toman amount is always exact).
  get notMultipleOf10() {
    return `مبلغ به ${currencyLabel("RIAL")} باید مضرب ۱۰ باشد (رقم آخر صفر).` // NEW
  },
  reenter: "این مبلغ را دوباره وارد کنید.", // NEW
}
