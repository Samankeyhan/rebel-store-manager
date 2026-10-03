"use client"

import { Info } from "lucide-react"
import { cardClass } from "@/components/record-sale/primitives"
import type { ExpenseBreakdown } from "@/lib/api"
import { Money } from "@/components/common/money"
import { formatMoney } from "@/lib/money"
import { cn } from "@/lib/utils"
import { E } from "./copy"
import { sharesOf } from "./shares"

/** Mobile stacked-bar fills: a neutral ramp, never the channel colours (design 11 §3). */
const RAMP = ["bg-bar-a", "bg-bar-c", "bg-bar-b", "bg-border-strong", "bg-surface-3"]
const rampOf = (i: number) => RAMP[Math.min(i, RAMP.length - 1)]

export const breakdownTotal = (rows: ExpenseBreakdown[]) => rows.reduce((s, r) => s + r.total_amount, 0)

/**
 * «به تفکیک دسته» (desktop aside). Rows come straight from GET
 * /reports/expenses — the same source the reports screen uses — for the whole
 * range and every category; `highlight` marks the category the list is
 * filtered to, and `scoped` adds the note saying the card ignores filters.
 */
export function BreakdownCard({
  rows,
  highlight,
  scoped,
}: {
  rows: ExpenseBreakdown[]
  highlight: string | null
  scoped: boolean
}) {
  const shares = sharesOf(rows.map((r) => r.total_amount))
  return (
    <section aria-labelledby="exp-breakdown" className={cardClass}>
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
        <h2 id="exp-breakdown" className="text-base font-bold text-heading">
          {E.breakdownTitle}
        </h2>
        <b>
          <Money value={breakdownTotal(rows)} />
        </b>
      </div>
      <div className="flex flex-col gap-3.5 p-5">
        {scoped && (
          <p className="flex items-start gap-1.5 text-xs leading-[19px] text-text-3">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            {E.breakdownScope}
          </p>
        )}
        {rows.length === 0 ? (
          <p className="text-[13px] text-text-3">{E.breakdownEmpty}</p>
        ) : (
          rows.map((r, i) => (
            <div
              key={r.category_name}
              title={E.breakdownTip(r.category_name, formatMoney(r.total_amount))}
              className={cn(
                "flex flex-col gap-1.5",
                highlight != null && highlight !== r.category_name && "opacity-55"
              )}
            >
              <div className="flex items-center justify-between gap-3 text-[13px]">
                <span className={cn("min-w-0 truncate", highlight === r.category_name && "font-bold text-heading")}>
                  {r.category_name}
                </span>
                <span className="flex shrink-0 items-center gap-2 tabular-nums">
                  <b>
                    <Money value={r.total_amount} />
                  </b>
                  <span className="w-9 text-end text-text-3">{E.percent(shares[i])}</span>
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                <i className="block h-full rounded-full bg-bar-a" style={{ width: `${shares[i]}%` }} />
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  )
}

/** Mobile summary card: period total, stacked share bar, legend. */
export function MobileSummary({ rows, label, scoped }: { rows: ExpenseBreakdown[]; label: string; scoped: boolean }) {
  const shares = sharesOf(rows.map((r) => r.total_amount))
  return (
    <section className={cn(cardClass, "flex flex-col gap-2.5 p-3.5")}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13px] font-bold text-heading">{label}</span>
        <b className="text-xl">
          <Money value={breakdownTotal(rows)} />
        </b>
      </div>
      {scoped && <p className="text-xs leading-[19px] text-text-3">{E.breakdownScopeMobile}</p>}
      {rows.length > 0 && (
        <>
          <div role="img" aria-label={E.barAria} className="flex h-3 gap-0.5 overflow-hidden rounded-md">
            {rows.map(
              (r, i) =>
                shares[i] > 0 && <i key={r.category_name} className={cn("block h-full", rampOf(i))} style={{ width: `${shares[i]}%` }} />
            )}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-text-3">
            {rows.map((r, i) => (
              <span key={r.category_name} className="flex items-center gap-1.5">
                <i className={cn("block size-2 rounded-sm", rampOf(i))} aria-hidden />
                {r.category_name} <span className="tabular-nums">{E.percent(shares[i])}</span>
              </span>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
