"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ChevronLeft, Plus, ReceiptText } from "lucide-react"
import { ChannelBadge, StatusBadge } from "@/components/common/status"
import { btnClass } from "@/components/record-sale/primitives"
import { L } from "@/components/orders/copy"
import { profitView } from "@/components/orders/order-figures"
import { ProfitFigure } from "@/components/orders/profit"
import { orderHref } from "@/components/orders/list/orders-table"
import type { OrderListItem } from "@/lib/api"
import { formatJalaliDateTime } from "@/lib/jalali"
import { Money } from "@/components/common/money"
import { D } from "./copy"
import { CardEmpty, CardError, CardLoading, DashCard } from "./parts"
import { RECENT_ORDERS, type Loader } from "./use-dashboard-data"

/**
 * The newest orders of every status — recent activity, not sales: drafts,
 * cancellations and refunds appear here though the KPIs exclude them.
 * Badges and profit display are the orders list's own (common/status,
 * orders/order-figures + orders/profit).
 */
export function RecentOrders({
  orders,
  timeZone,
  mobile,
}: {
  orders: Loader<OrderListItem[]>
  timeZone: string
  mobile: boolean
}) {
  const router = useRouter()
  const id = "dash-orders"
  const allLink = (
    <Link
      href="/orders"
      className="inline-flex shrink-0 items-center gap-1 text-[13px] font-semibold text-heading outline-none hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/30"
    >
      {mobile ? D.ordersAllMobile : D.ordersAll}
      <ChevronLeft className="size-4" aria-hidden />
    </Link>
  )

  if (orders.status !== "ready") {
    return (
      <DashCard id={id} title={D.ordersTitle}>
        {orders.status === "loading" ? (
          <CardLoading rows={mobile ? 4 : RECENT_ORDERS} />
        ) : (
          <CardError title={D.ordersErrorTitle} code={orders.code} onRetry={orders.retry} mobile={mobile} />
        )}
      </DashCard>
    )
  }

  const rows = orders.data.slice(0, RECENT_ORDERS)

  if (rows.length === 0) {
    return (
      <DashCard id={id} title={D.ordersTitle}>
        <CardEmpty
          icon={ReceiptText}
          title={D.ordersEmptyTitle}
          body={D.ordersEmptyBody}
          className={mobile ? "py-9" : "py-14"}
          action={
            <Link href="/sales/new" className={btnClass("primary", mobile ? "lg" : "md", "mt-1.5")}>
              <Plus className="size-4" aria-hidden />
              {D.ordersEmptyCta}
            </Link>
          }
        />
      </DashCard>
    )
  }

  if (mobile) {
    return (
      <DashCard id={id} title={D.ordersTitle} aside={allLink} headerRule={false}>
        {rows.map((o) => (
          <Link
            key={o.id}
            href={orderHref(o.id)}
            className="flex flex-col gap-1.5 border-t border-border px-4 py-3 text-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
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
      </DashCard>
    )
  }

  return (
    <DashCard id={id} title={D.ordersTitle} aside={allLink} className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[13.5px]">
          <thead>
            <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
              <th scope="col">{L.colInvoice}</th>
              <th scope="col">{D.colDate}</th>
              <th scope="col">{L.colChannel}</th>
              <th scope="col" className="w-full">
                {L.colCustomer}
              </th>
              <th scope="col">{L.colStatus}</th>
              <th scope="col">{L.colTotal}</th>
              <th scope="col">{L.colProfit}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr
                key={o.id}
                onClick={() => router.push(orderHref(o.id))}
                className="cursor-pointer hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap last:[&>td]:border-b-0"
              >
                <td>
                  <Link
                    href={orderHref(o.id)}
                    dir="ltr"
                    onClick={(e) => e.stopPropagation()}
                    className="font-mono text-[12.5px] font-semibold text-heading outline-none hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/30"
                  >
                    {o.invoice_number}
                  </Link>
                </td>
                <td className="text-text-2 tabular-nums">{formatJalaliDateTime(o.order_date, timeZone)}</td>
                <td>
                  <ChannelBadge channel={o.channel} />
                </td>
                <td className="max-w-[260px] truncate">{o.customer_name || "—"}</td>
                <td>
                  <StatusBadge status={o.status} />
                </td>
                <td className="font-bold">
                  <Money value={o.customer_total} />
                </td>
                <td>
                  <ProfitFigure view={profitView(o.status, o.profit, o)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DashCard>
  )
}
