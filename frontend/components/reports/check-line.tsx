"use client"

import { CircleCheck, CircleHelp, TriangleAlert } from "lucide-react"
import { Money } from "@/components/common/money"
import { formatMoney } from "@/lib/money"
import type { Loader } from "@/components/dashboard/use-dashboard-data"
import type { ProfitAndLoss } from "@/lib/api"
import type { Check } from "@/lib/reports"
import { cn } from "@/lib/utils"
import { R } from "./copy"

const PLUS = "‎+"
const signed = (rial: number) => (rial > 0 ? PLUS + formatMoney(rial) : formatMoney(rial))

/**
 * «مطابقت» lines: each compares a sum of report rows with a P&L figure
 * (exact integer Rial). `checks` null = the P&L isn't available, so nothing
 * can be compared.
 */
export function CheckLines({
  checks,
  className,
}: {
  checks: { label: string; check: Check }[] | null
  className?: string
}) {
  if (checks === null)
    return (
      <p role="status" className={cn("flex items-center gap-1.5 text-xs text-text-3", className)}>
        <CircleHelp className="size-3.5 shrink-0" aria-hidden />
        {R.checkUnavailable}
      </p>
    )
  return (
    <ul className={cn("flex flex-col gap-1", className)}>
      {checks.map(({ label, check }) => (
        <li key={label}>
          {check.status === "ok" ? (
            <span className="flex items-start gap-1.5 text-xs text-profit">
              <CircleCheck className="mt-px size-3.5 shrink-0" aria-hidden />
              <span>
                {R.checkOk(label)} · <Money value={check.actual} unitClassName="text-profit" />
              </span>
            </span>
          ) : check.status === "mismatch" ? (
            <span role="alert" className="flex items-start gap-1.5 rounded-lg bg-warn-soft px-2.5 py-1.5 text-xs text-warn">
              <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
              <span className="flex flex-col gap-0.5">
                <b>{R.checkBad(label)}</b>
                <span className="tabular-nums">
                  {R.checkBadDetail(formatMoney(check.actual), formatMoney(check.expected), signed(check.diff))}
                </span>
              </span>
            </span>
          ) : (
            <span role="alert" className="flex items-start gap-1.5 text-xs text-warn">
              <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
              {R.checkInvalid(label)}
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

export type CheckItem = { label: string; check: Check }

/**
 * The «مطابقت» lines that compare with the shell's P&L: none while it loads,
 * null (cannot compare) when it failed, else `build(pnl)`.
 */
export function pnlChecks(pnl: Loader<ProfitAndLoss>, build: (p: ProfitAndLoss) => CheckItem[]): CheckItem[] | null {
  if (pnl.status === "ready") return build(pnl.data)
  return pnl.status === "error" ? null : []
}
