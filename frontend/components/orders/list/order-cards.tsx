"use client"

import * as React from "react"
import Link from "next/link"
import { Filter } from "lucide-react"
import { ChannelBadge, StatusBadge } from "@/components/common/status"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import type { OrderListItem } from "@/lib/api"
import { formatJalaliDateTime } from "@/lib/jalali"
import { Money } from "@/components/common/money"
import { cn } from "@/lib/utils"
import { L } from "../copy"
import { profitView } from "../order-figures"
import { ProfitFigure } from "../profit"
import { PAGE_SIZE, orderHref, pageTotals } from "./orders-table"

/** Mobile list: one card per order (the whole card is the link), load-more paging. */
export function OrderCards({
  rows,
  timeZone,
  resetKey,
  onClearFilters,
}: {
  rows: OrderListItem[]
  timeZone: string
  /** Changes whenever the filters do, which resets the load-more count. */
  resetKey: string
  onClearFilters: () => void
}) {
  const [shown, setShown] = React.useState({ key: resetKey, count: PAGE_SIZE })
  const count = shown.key === resetKey ? shown.count : PAGE_SIZE
  const visible = rows.slice(0, count)
  const remaining = rows.length - visible.length
  const totals = pageTotals(rows)

  if (rows.length === 0) {
    return (
      <section className={cn(cardClass, "flex flex-col items-center gap-2.5 px-5 py-12 text-center")}>
        <div className="mb-1 flex size-14 items-center justify-center rounded-2xl bg-surface-2 text-text-3">
          <Filter className="size-6" aria-hidden />
        </div>
        <div className="text-[15px] font-bold text-heading">{L.filteredEmptyTitle}</div>
        <div className="text-[13px] text-text-3">{L.filteredEmptyBody}</div>
        <Btn className="h-11" onClick={onClearFilters}>
          {L.filteredEmptyAction}
        </Btn>
      </section>
    )
  }

  return (
    <>
      <div className="flex items-baseline justify-between text-[13px]">
        <span className="text-text-3">{L.mobileCount(rows.length)}</span>
        <span>
          {L.salesTotal}{" "}
          <b>
            <Money value={totals.sales} />
          </b>
        </span>
      </div>
      {visible.map((o) => (
        <Link
          key={o.id}
          href={orderHref(o.id)}
          className={cn(
            cardClass,
            "flex flex-col gap-1.5 px-3.5 py-3 text-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
          )}
        >
          <span className="flex items-center justify-between gap-2">
            <span dir="ltr" className="font-mono text-[12.5px] font-semibold text-heading">
              {o.invoice_number}
            </span>
            <StatusBadge status={o.status} />
          </span>
          <span className="flex items-center justify-between gap-2 text-[13px]">
            <span className="flex min-w-0 items-center gap-2">
              <ChannelBadge channel={o.channel} />
              {o.payment_method_name && (
                <span className="max-w-[96px] shrink-0 truncate rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-2">
                  {o.payment_method_name}
                </span>
              )}
              <span className="truncate">{o.customer_name || "—"}</span>
            </span>
            <b>
              <Money value={o.customer_total} />
            </b>
          </span>
          <span className="flex items-start justify-between gap-2 text-xs">
            <span className="text-text-3 tabular-nums">{formatJalaliDateTime(o.order_date, timeZone)}</span>
            <ProfitFigure view={profitView(o.status, o.profit, o)} prefix={L.mobileProfit("")} className="text-end" />
          </span>
        </Link>
      ))}
      {remaining > 0 && (
        <Btn className="h-11 w-full" onClick={() => setShown({ key: resetKey, count: count + PAGE_SIZE })}>
          {L.mobileMore(Math.min(PAGE_SIZE, remaining))}
        </Btn>
      )}
    </>
  )
}
