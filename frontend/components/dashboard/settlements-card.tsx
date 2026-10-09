"use client"

import * as React from "react"
import Link from "next/link"
import { ChevronLeft, CircleCheck } from "lucide-react"
import { badgeBase } from "@/components/common/status"
import type { PendingMethod } from "@/lib/api"
import { overdueOrderCount } from "@/lib/settlements"
import { cn } from "@/lib/utils"
import { D } from "./copy"
import { Amount, CardEmpty, CardError, CardLoading, DashCard } from "./parts"
import type { Loader } from "./use-dashboard-data"

/**
 * «در انتظار تسویه»: per payment method, what is still to be paid out
 * (total_expected, from GET /settlements/pending) and how many orders are
 * overdue (a count). The situation now, not the selected period. No grand
 * total: the API has none, and the frontend doesn't add up money for display.
 */
export function SettlementsCard({ pending, mobile }: { pending: Loader<PendingMethod[]>; mobile: boolean }) {
  const id = "dash-settlements"
  const link = (
    <Link
      href="/settlements"
      className="inline-flex shrink-0 items-center gap-1 text-[13px] font-semibold text-heading outline-none hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/30"
    >
      {D.settleLink}
      <ChevronLeft className="size-4" aria-hidden />
    </Link>
  )

  if (pending.status !== "ready") {
    return (
      <DashCard id={id} title={D.settleTitle} caption={D.settleCaption}>
        {pending.status === "error" ? (
          <CardError title={D.settleErrorTitle} code={pending.code} onRetry={pending.retry} mobile={mobile} />
        ) : (
          <CardLoading rows={3} />
        )}
      </DashCard>
    )
  }

  if (pending.data.length === 0) {
    return (
      <DashCard id={id} title={D.settleTitle} caption={D.settleCaption}>
        <CardEmpty icon={CircleCheck} tone="profit" title={D.settleEmpty} className="py-8" />
      </DashCard>
    )
  }

  return (
    <DashCard id={id} title={D.settleTitle} caption={D.settleCaption} aside={mobile ? undefined : link}>
      <ul className="flex flex-col px-4 py-1.5 md:px-5">
        {pending.data.map((m) => {
          const overdue = overdueOrderCount(m.groups)
          return (
            <li
              key={m.payment_method_id}
              className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-border py-3 last:border-b-0"
            >
              <span className="flex min-w-0 flex-wrap items-center gap-2">
                <span className="truncate text-[13.5px] font-semibold">{m.name}</span>
                {m.is_active !== 1 && (
                  <span className={cn(badgeBase, "border border-dashed border-border-strong bg-card text-text-2 before:hidden")}>
                    {D.settleInactive}
                  </span>
                )}
                {overdue > 0 && <span className={cn(badgeBase, "bg-loss-soft text-loss")}>{D.settleOverdue(overdue)}</span>}
              </span>
              <Amount n={m.total_expected} className="text-[14px] font-bold" />
            </li>
          )
        })}
      </ul>
      {mobile && <div className="px-4 pb-4">{link}</div>}
    </DashCard>
  )
}
