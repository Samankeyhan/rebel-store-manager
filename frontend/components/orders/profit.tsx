import { cn } from "@/lib/utils"
import { formatNumber } from "@/lib/persian-numbers"
import { D, L } from "./copy"
import type { ProfitView } from "./order-figures"

export function profitTone(n: number) {
  return n < 0 ? "text-loss" : "text-profit"
}

/**
 * A profit figure as the list shows it: green/red by sign, «—» when there
 * is none, and for a refund the loss with the original sale profit under it
 * (the two are kept apart, as in the P&L).
 */
export function ProfitFigure({
  view,
  className,
  prefix = "",
}: {
  view: ProfitView
  className?: string
  /** Mobile cards prefix the value with «سود ». */
  prefix?: string
}) {
  if (view.kind === "none") {
    return <span className={cn("font-bold text-text-3", className)}>{prefix ? L.mobileProfitNone : "—"}</span>
  }
  if (view.kind === "known") {
    return (
      <span className={cn("font-bold whitespace-nowrap tabular-nums", profitTone(view.profit), className)}>
        {prefix}
        {formatNumber(view.profit)}
      </span>
    )
  }
  return (
    <span className={cn("inline-flex flex-col leading-tight", className)}>
      <span className="font-bold whitespace-nowrap text-loss tabular-nums">
        {/* A refund's figure is a loss, not a profit: label it as such. */}
        {prefix ? `${D.refundLoss} ` : ""}
        {formatNumber(-view.loss)}
      </span>
      <span className="text-[11px] font-normal whitespace-nowrap text-text-3 tabular-nums">
        {L.refundOriginal(formatNumber(view.original))}
      </span>
    </span>
  )
}
