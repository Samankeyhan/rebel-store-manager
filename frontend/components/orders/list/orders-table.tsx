"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ChevronLeft, ChevronRight, ExternalLink, Filter, MoreHorizontal, Printer } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChannelBadge, ORDER_STATUS_IDS, StatusBadge, statusName } from "@/components/common/status"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import { invoicePdfUrl, type OrderListItem } from "@/lib/api"
import { formatJalaliDateTime } from "@/lib/jalali"
import { formatNumber, toPersianDigits } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { L } from "../copy"
import { REVENUE_ELIGIBLE, profitView } from "../order-figures"
import { ProfitFigure, profitTone } from "../profit"

export const PAGE_SIZE = 12

export const orderHref = (id: number) => `/orders/view/?id=${id}`

/** Page numbers with gaps: 1 … 4 5 6 … 12. */
function pageItems(page: number, count: number): (number | "gap")[] {
  const keep = new Set([1, count, page - 1, page, page + 1].filter((p) => p >= 1 && p <= count))
  const out: (number | "gap")[] = []
  let prev = 0
  for (const p of [...keep].sort((a, b) => a - b)) {
    if (p - prev > 1) out.push("gap")
    out.push(p)
    prev = p
  }
  return out
}

/**
 * Sales and profit totals for the rows on screen. Only the revenue-eligible
 * statuses count (accounting-rules §9), so drafts, cancellations and refunds
 * are excluded from both — matching the P&L, unlike the design's markup.
 */
export function pageTotals(rows: OrderListItem[]) {
  let sales = 0
  let profit = 0
  for (const r of rows) {
    if (!REVENUE_ELIGIBLE.has(r.status)) continue
    sales += r.customer_total
    profit += r.profit ?? 0
  }
  return { sales, profit }
}

export function OrdersTable({
  rows,
  counts,
  status,
  page,
  pageCount,
  timeZone,
  onStatus,
  onPage,
  onClearFilters,
}: {
  rows: OrderListItem[]
  counts: Record<string, number>
  status: string
  page: number
  pageCount: number
  timeZone: string
  onStatus: (status: string) => void
  onPage: (page: number) => void
  onClearFilters: () => void
}) {
  const router = useRouter()
  const start = (page - 1) * PAGE_SIZE
  const pageRows = rows.slice(start, start + PAGE_SIZE)
  const totals = pageTotals(pageRows)
  const tabs = [{ id: "", name: L.tabAll }, ...ORDER_STATUS_IDS.map((id) => ({ id, name: statusName(id) }))]

  return (
    <>
      <div role="tablist" aria-label={L.tabsAria} className="flex gap-1 overflow-x-auto border-b border-border">
        {tabs.map((t) => {
          const on = status === t.id
          return (
            <button
              key={t.id || "all"}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => onStatus(t.id)}
              className={cn(
                "-mb-px inline-flex h-10 shrink-0 cursor-pointer items-center gap-1.5 border-b-2 border-transparent px-3 text-[13.5px] font-semibold whitespace-nowrap text-text-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                on && "border-primary text-heading"
              )}
            >
              {t.name}
              <span
                className={cn(
                  "inline-flex h-[18px] min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] tabular-nums",
                  on ? "bg-red-soft text-primary" : "bg-surface-3 text-text-2"
                )}
              >
                {toPersianDigits(counts[t.id] ?? 0)}
              </span>
            </button>
          )
        })}
      </div>

      <section className={cn(cardClass, "overflow-hidden")}>
        <div className="flex flex-wrap gap-x-7 gap-y-1 border-b border-border px-4 py-3 text-[13px]">
          <span className="text-text-3">
            {status ? L.pageCountStatus(pageRows.length, statusName(status)) : L.pageCount(pageRows.length)}
          </span>
          <span>
            {L.salesTotal}{" "}
            <b className="tabular-nums">
              {formatNumber(totals.sales)} {L.toman}
            </b>
          </span>
          <span>
            {L.profitTotal}{" "}
            <b className={cn("tabular-nums", profitTone(totals.profit))}>
              {formatNumber(totals.profit)} {L.toman}
            </b>
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col">{L.colInvoice}</th>
                <th scope="col">{L.colDate}</th>
                <th scope="col">{L.colChannel}</th>
                <th scope="col" className="w-full">
                  {L.colCustomer}
                </th>
                <th scope="col">{L.colStatus}</th>
                <th scope="col">{L.colTotal}</th>
                <th scope="col">{L.colProfit}</th>
                <th scope="col" className="w-14">
                  <span className="sr-only">{L.colActions}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((o) => (
                <tr
                  key={o.id}
                  // The whole row opens the order; the invoice link is the
                  // keyboard/screen-reader target.
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
                  <td className="font-bold tabular-nums">{formatNumber(o.customer_total)}</td>
                  <td>
                    <ProfitFigure view={profitView(o.status, o.profit, o)} />
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <RowMenu order={o} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {pageRows.length === 0 && (
          <div className="flex flex-col items-center gap-2.5 px-6 py-10 text-center">
            <div className="mb-1 flex size-14 items-center justify-center rounded-2xl bg-surface-2 text-text-3">
              <Filter className="size-6" aria-hidden />
            </div>
            <div className="text-[15px] font-bold text-heading">{L.filteredEmptyTitle}</div>
            <div className="max-w-[380px] text-[13px] text-text-3">{L.filteredEmptyBody}</div>
            <Btn size="sm" onClick={onClearFilters}>
              {L.filteredEmptyAction}
            </Btn>
          </div>
        )}

        {rows.length > 0 && (
          <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
            <span className="text-[13px] text-text-3">
              {L.pageRange(start + 1, start + pageRows.length, rows.length)}
            </span>
            <nav className="flex items-center gap-1" aria-label={L.pageRange(start + 1, start + pageRows.length, rows.length)}>
              <Btn
                size="sm"
                className="w-8 px-0"
                aria-label={L.prevPage}
                disabled={page <= 1}
                onClick={() => onPage(page - 1)}
              >
                <ChevronRight className="size-4" />
              </Btn>
              {pageItems(page, pageCount).map((p, i) =>
                p === "gap" ? (
                  <span key={`g${i}`} className="px-1 text-text-3">
                    …
                  </span>
                ) : (
                  <Btn
                    key={p}
                    size="sm"
                    variant="ghost"
                    aria-current={p === page ? "page" : undefined}
                    className={cn("min-w-8 px-2 tabular-nums", p === page && "bg-navy-soft text-heading hover:bg-navy-soft")}
                    onClick={() => onPage(p)}
                  >
                    {toPersianDigits(p)}
                  </Btn>
                )
              )}
              <Btn
                size="sm"
                className="w-8 px-0"
                aria-label={L.nextPage}
                disabled={page >= pageCount}
                onClick={() => onPage(page + 1)}
              >
                <ChevronLeft className="size-4" />
              </Btn>
            </nav>
          </div>
        )}
      </section>
    </>
  )
}

/** «⋯» menu: view and print only — cancel/refund need the detail page's dialog. */
function RowMenu({ order }: { order: OrderListItem }) {
  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <Btn variant="ghost" size="sm" className="w-8 px-0" aria-label={L.rowActions}>
          <MoreHorizontal className="size-4" />
        </Btn>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuItem asChild>
          <Link href={orderHref(order.id)}>
            <ExternalLink />
            {L.viewOrder}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <a href={invoicePdfUrl(order.id)}>
            <Printer />
            {L.printInvoicePdf}
          </a>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
