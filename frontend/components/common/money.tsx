"use client"

import { currencyLabel, formatMoneyNumber } from "@/lib/money"
import { useCurrency } from "@/lib/use-currency"
import { cn } from "@/lib/utils"

/**
 * A money VALUE: the amount in the display currency with its unit, kept on
 * one line. `value` is integer Rial (straight from the API); Toman shows one
 * decimal digit only when needed (lib/money.ts). The number is
 * bidi-isolated so a minus (LRM + U+2212) stays on the digits' left whatever
 * text surrounds it. The unit is small and muted by default (dense tables);
 * `plainUnit` makes it inherit the text's own size/weight/colour; pass
 * `unitClassName` to adjust it, or `unit={false}` only where the unit already
 * sits right next to the figure.
 */
export function Money({
  value,
  unit = true,
  className,
  unitClassName,
  plainUnit = false,
}: {
  value: number
  unit?: boolean
  plainUnit?: boolean
  className?: string
  unitClassName?: string
}) {
  const currency = useCurrency()
  return (
    <span className={cn("whitespace-nowrap", className)}>
      <span dir="ltr" className="tabular-nums">
        {formatMoneyNumber(value, currency)}
      </span>
      {unit && (
        <>
          {" "}
          <span className={cn(!plainUnit && "text-[0.8em] font-medium text-text-3", unitClassName)}>{currencyLabel(currency)}</span>
        </>
      )}
    </span>
  )
}
