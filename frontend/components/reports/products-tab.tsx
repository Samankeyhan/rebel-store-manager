"use client"

import * as React from "react"
import { ArrowDown, ArrowUp, ArrowUpDown, PackageOpen, Search, SearchX } from "lucide-react"
import { Money } from "@/components/common/money"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { useLoad, type Loader } from "@/components/dashboard/use-dashboard-data"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import { getProductPerformance, type ProductPerformance, type ProfitAndLoss } from "@/lib/api"
import { formatNumber } from "@/lib/persian-numbers"
import { apiRange, periodKey, type ReportPeriod } from "@/lib/report-period"
import {
  PRODUCT_SORT_KEYS,
  filterProducts,
  percentText,
  productChecks,
  ratioTenths,
  sortProducts,
  type ProductSortKey,
  type SortDir,
} from "@/lib/reports"
import { cn } from "@/lib/utils"
import { CheckLines } from "./check-line"
import { R } from "./copy"

const COLUMNS: { key: ProductSortKey; label: () => string; numeric: boolean }[] = [
  { key: "name", label: () => R.colProduct, numeric: false },
  { key: "units", label: () => R.colUnits, numeric: true },
  { key: "revenue", label: () => R.colRevenue, numeric: true },
  { key: "cost", label: () => R.colCost, numeric: true },
  { key: "profit", label: () => R.colProfit, numeric: true },
  { key: "margin", label: () => R.colMargin, numeric: true },
]

/** Names sort A→Z first; figures largest first. */
const firstDir = (key: ProductSortKey): SortDir => (key === "name" ? "asc" : "desc")

const profitTone = (v: number) => (v > 0 ? "text-profit" : v < 0 ? "text-loss" : "text-text-3")

function margin(r: ProductPerformance): string {
  const t = ratioTenths(r.total_profit, r.total_revenue)
  return t == null ? R.nil : percentText(t)
}

/**
 * «عملکرد محصولات»: GET /reports/products for the period, searchable and
 * sortable on the client. Revenue and cost are checked against the P&L's
 * items_revenue and cogs over all rows (accounting-rules §9), whatever the
 * search shows.
 */
export function ProductsTab({
  period,
  pnl,
  mobile,
}: {
  period: ReportPeriod
  pnl: Loader<ProfitAndLoss>
  mobile: boolean
}) {
  const rows = useLoad<ProductPerformance[]>("REPORTS", periodKey(period), () => getProductPerformance(apiRange(period)))
  const [query, setQuery] = React.useState("")
  const [sort, setSort] = React.useState<{ key: ProductSortKey; dir: SortDir }>({ key: "profit", dir: "desc" })

  if (rows.status === "loading") return <LoadingBlock mobile={mobile} label={R.loadingAria} />
  if (rows.status === "error")
    return <ErrorBlock title={R.errorTitle} body={R.errorBody} retry={R.retry} onRetry={rows.retry} mobile={mobile} />

  const all = rows.data
  const checks =
    pnl.status === "ready"
      ? (() => {
          const c = productChecks(all, pnl.data)
          return [
            { label: R.checkProductsRevenue, check: c.revenue },
            { label: R.checkProductsCost, check: c.cost },
          ]
        })()
      : pnl.status === "error"
        ? null
        : []

  if (all.length === 0)
    return (
      <div className="flex flex-col gap-3">
        <StateShell icon={PackageOpen} mobile={mobile} title={R.productsEmptyTitle} body={R.productsEmptyBody} />
        <CheckLines checks={checks} />
      </div>
    )

  const shown = sortProducts(filterProducts(all, query), sort.key, sort.dir)
  const filtered = query.trim() !== ""
  const sumOf = (pick: (r: ProductPerformance) => number) => shown.reduce((s, r) => s + pick(r), 0)

  const onSort = (key: ProductSortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: firstDir(key) }))

  const search = (
    <div className={cn("relative flex items-center", mobile ? "w-full" : "w-[260px]")}>
      <Search className="pointer-events-none absolute start-3 size-4 text-text-3" aria-hidden />
      <input
        type="search"
        aria-label={R.searchLabel}
        placeholder={R.searchPlaceholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className={cn(
          "w-full rounded-lg border border-border-strong bg-card ps-9 pe-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
          mobile ? "h-11" : "h-10"
        )}
      />
    </div>
  )

  const noMatch = (
    <StateShell
      icon={SearchX}
      mobile={mobile}
      title={R.searchEmpty(query.trim())}
      action={
        <Btn size={mobile ? "lg" : "sm"} className="mt-1" onClick={() => setQuery("")}>
          {R.clearSearch}
        </Btn>
      }
    />
  )

  const totalLabel = filtered ? R.totalFiltered(shown.length) : R.total

  let body: React.ReactNode
  if (shown.length === 0) body = noMatch
  else if (mobile)
    body = (
      <ul aria-label={R.productsAria} className="flex flex-col gap-2">
        {shown.map((r) => (
          <li key={r.product_id} className={cn(cardClass, "flex flex-col gap-1.5 px-3.5 py-3 text-[13px]")}>
            <span className="flex items-start justify-between gap-2">
              <b className="min-w-0 text-[13.5px] text-heading">{r.product_name}</b>
              <Money value={r.total_profit} className={cn("shrink-0 font-bold", profitTone(r.total_profit))} />
            </span>
            <span className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-text-3">
              <span>
                {R.sortLabels.units}: <span className="tabular-nums text-text-2">{formatNumber(r.units_sold)}</span>
              </span>
              <span>
                {R.sortLabels.revenue}: <Money value={r.total_revenue} className="text-text-2" />
              </span>
              <span>
                {R.sortLabels.cost}: <Money value={r.total_cost} className="text-text-2" />
              </span>
              <span>
                {R.colMargin}: <span className="tabular-nums text-text-2">{margin(r)}</span>
              </span>
            </span>
          </li>
        ))}
        <li className={cn(cardClass, "flex flex-col gap-1 bg-surface-2 px-3.5 py-3 text-[13px]")}>
          <span className="flex items-center justify-between gap-2 font-bold">
            {totalLabel}
            <Money value={sumOf((r) => r.total_profit)} className={profitTone(sumOf((r) => r.total_profit))} />
          </span>
          <span className="flex flex-wrap gap-x-3 text-xs text-text-3">
            <span>
              {R.sortLabels.units}: <span className="tabular-nums">{formatNumber(sumOf((r) => r.units_sold))}</span>
            </span>
            <span>
              {R.sortLabels.revenue}: <Money value={sumOf((r) => r.total_revenue)} />
            </span>
            <span>
              {R.sortLabels.cost}: <Money value={sumOf((r) => r.total_cost)} />
            </span>
          </span>
        </li>
      </ul>
    )
  else
    body = (
      <section aria-label={R.productsAria} className={cn(cardClass, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:whitespace-nowrap">
                {COLUMNS.map((c) => {
                  const on = sort.key === c.key
                  const Icon = on ? (sort.dir === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown
                  return (
                    <th
                      key={c.key}
                      scope="col"
                      aria-sort={on ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                      className={cn(c.numeric ? "text-end" : "w-full text-start")}
                    >
                      <button
                        type="button"
                        onClick={() => onSort(c.key)}
                        className={cn(
                          "inline-flex h-8 cursor-pointer items-center gap-1 rounded-md outline-none hover:text-heading focus-visible:ring-3 focus-visible:ring-ring/30",
                          on && "text-heading"
                        )}
                      >
                        {c.label()}
                        <Icon className={cn("size-3.5", !on && "opacity-50")} aria-hidden />
                      </button>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr
                  key={r.product_id}
                  className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
                >
                  <td className="font-semibold">{r.product_name}</td>
                  <td className="text-end tabular-nums">{formatNumber(r.units_sold)}</td>
                  <td className="text-end">
                    <Money value={r.total_revenue} />
                  </td>
                  <td className="text-end text-text-2">
                    <Money value={r.total_cost} />
                  </td>
                  <td className={cn("text-end font-bold", profitTone(r.total_profit))}>
                    <Money value={r.total_profit} />
                  </td>
                  <td className="text-end text-text-2 tabular-nums">{margin(r)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-bold [&>td]:h-12 [&>td]:bg-surface-2 [&>td]:px-4 [&>td]:whitespace-nowrap">
                <td>{totalLabel}</td>
                <td className="text-end tabular-nums">{formatNumber(sumOf((r) => r.units_sold))}</td>
                <td className="text-end">
                  <Money value={sumOf((r) => r.total_revenue)} />
                </td>
                <td className="text-end">
                  <Money value={sumOf((r) => r.total_cost)} />
                </td>
                <td className={cn("text-end", profitTone(sumOf((r) => r.total_profit)))}>
                  <Money value={sumOf((r) => r.total_profit)} />
                </td>
                <td className="text-end text-text-3">{R.nil}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    )

  return (
    <div className="flex flex-col gap-3">
      <div className={cn("flex gap-2", mobile ? "flex-col" : "items-center justify-between")}>
        {search}
        {mobile && (
          <div className="flex gap-2">
            <label className="flex min-w-0 grow items-center gap-2 text-[13px] text-text-3">
              {R.sortBy}
              <select
                value={sort.key}
                onChange={(e) => {
                  const key = e.target.value as ProductSortKey
                  setSort({ key, dir: firstDir(key) })
                }}
                className="h-11 min-w-0 grow rounded-lg border border-border-strong bg-card px-3 text-sm text-foreground outline-none focus:border-heading focus:ring-3 focus:ring-ring/30"
              >
                {PRODUCT_SORT_KEYS.map((k) => (
                  <option key={k} value={k}>
                    {R.sortLabels[k]}
                  </option>
                ))}
              </select>
            </label>
            <Btn
              size="lg"
              aria-label={`${R.sortBy}: ${sort.dir === "asc" ? R.sortAsc : R.sortDesc}`}
              onClick={() => setSort((s) => ({ ...s, dir: s.dir === "asc" ? "desc" : "asc" }))}
            >
              {sort.dir === "asc" ? <ArrowUp className="size-4" aria-hidden /> : <ArrowDown className="size-4" aria-hidden />}
              {sort.dir === "asc" ? R.sortAsc : R.sortDesc}
            </Btn>
          </div>
        )}
      </div>
      {body}
      <CheckLines checks={checks} />
      <p className="text-xs text-text-3">{R.productsNote}</p>
    </div>
  )
}
