"use client"

import { Store } from "lucide-react"
import { ChannelBadge } from "@/components/common/status"
import { Money } from "@/components/common/money"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { useLoad, type Loader } from "@/components/dashboard/use-dashboard-data"
import { CHANNELS, type Channel } from "@/components/record-sale/copy"
import { cardClass } from "@/components/record-sale/primitives"
import { getChannelBreakdown, type ChannelBreakdown, type ProfitAndLoss } from "@/lib/api"
import { formatMoney } from "@/lib/money"
import { formatNumber } from "@/lib/persian-numbers"
import { apiRange, periodKey, type ReportPeriod } from "@/lib/report-period"
import { barPercent, channelChecks, percentText, ratioTenths } from "@/lib/reports"
import { cn } from "@/lib/utils"
import { CheckLines } from "./check-line"
import { R } from "./copy"

const channelName = (c: string) => CHANNELS[c as Channel]?.name ?? c
const profitTone = (v: number) => (v > 0 ? "text-profit" : v < 0 ? "text-loss" : "text-text-3")

/**
 * Single-hue bars with the value written on every row (design 12 §5: the
 * channel colours fail as a chart palette). Scaled to the period's largest
 * value; a zero or negative value draws no bar and keeps its written figure.
 */
function BarChart({
  title,
  aria,
  rows,
  pick,
  fill,
  mobile,
}: {
  title: string
  aria: string
  rows: ChannelBreakdown[]
  pick: (r: ChannelBreakdown) => number
  fill: string
  mobile: boolean
}) {
  const max = Math.max(0, ...rows.map(pick))
  return (
    <section className={cn(cardClass, "min-w-0")}>
      <div className={cn("flex items-center justify-between gap-2 border-b border-border", mobile ? "px-3.5 py-3" : "px-5 py-4")}>
        <h2 className="text-[15px] font-bold text-heading">{title}</h2>
        <span className="text-xs text-text-3">{R.chartCaption}</span>
      </div>
      <div role="img" aria-label={aria} className={cn("flex flex-col gap-3.5", mobile ? "p-3.5" : "p-5")}>
        {rows.map((r) => {
          const v = pick(r)
          return (
            <div
              key={r.channel}
              title={`${channelName(r.channel)}: ${formatMoney(v)}`}
              className="grid grid-cols-[76px_minmax(0,1fr)] items-center gap-2.5 sm:grid-cols-[88px_minmax(0,1fr)_auto]"
            >
              <span className="truncate text-[13px] text-text-2">{channelName(r.channel)}</span>
              <span className="h-[22px] overflow-hidden rounded-e-[4px] bg-surface-2">
                <span className={cn("block h-full rounded-e-[4px]", fill)} style={{ width: `${barPercent(v, max)}%` }} />
              </span>
              <Money
                value={v}
                unit={false}
                className={cn("col-start-2 text-[12.5px] font-bold sm:col-start-auto sm:text-end", v < 0 && "text-loss")}
              />
            </div>
          )
        })}
      </div>
    </section>
  )
}

/**
 * «کانال‌ها»: GET /reports/channels for the period, revenue-eligible orders
 * only, channels without orders omitted by the backend. Order count, revenue
 * and order profit are checked against the P&L's order_count, total_revenue
 * and gross_profit.
 */
export function ChannelsTab({
  period,
  pnl,
  mobile,
}: {
  period: ReportPeriod
  pnl: Loader<ProfitAndLoss>
  mobile: boolean
}) {
  const rows = useLoad<ChannelBreakdown[]>("REPORTS", periodKey(period), () => getChannelBreakdown(apiRange(period)))

  if (rows.status === "loading") return <LoadingBlock mobile={mobile} label={R.loadingAria} />
  if (rows.status === "error")
    return <ErrorBlock title={R.errorTitle} body={R.errorBody} retry={R.retry} onRetry={rows.retry} mobile={mobile} />

  const data = rows.data
  const checks =
    pnl.status === "ready"
      ? (() => {
          const c = channelChecks(data, pnl.data)
          return [
            { label: R.checkChannelsOrders, check: c.orders },
            { label: R.checkChannelsRevenue, check: c.revenue },
            { label: R.checkChannelsProfit, check: c.profit },
          ]
        })()
      : pnl.status === "error"
        ? null
        : []

  if (data.length === 0)
    return (
      <div className="flex flex-col gap-3">
        <StateShell icon={Store} mobile={mobile} title={R.channelsEmptyTitle} body={R.channelsEmptyBody} />
        <CheckLines checks={checks} />
      </div>
    )

  const sum = (pick: (r: ChannelBreakdown) => number) => data.reduce((s, r) => s + pick(r), 0)
  const margin = (r: ChannelBreakdown) => {
    const t = ratioTenths(r.total_profit, r.total_revenue)
    return t == null ? R.nil : percentText(t)
  }

  const table = mobile ? (
    <ul aria-label={R.channelsAria} className="flex flex-col gap-2">
      {data.map((r) => (
        <li key={r.channel} className={cn(cardClass, "flex flex-col gap-1.5 px-3.5 py-3 text-[13px]")}>
          <span className="flex items-center justify-between gap-2">
            <ChannelBadge channel={r.channel} />
            <Money value={r.total_profit} className={cn("font-bold", profitTone(r.total_profit))} />
          </span>
          <span className="flex flex-wrap gap-x-3 text-xs text-text-3">
            <span>
              {R.colOrders}: <span className="tabular-nums text-text-2">{formatNumber(r.order_count)}</span>
            </span>
            <span>
              {R.sortLabels.revenue}: <Money value={r.total_revenue} className="text-text-2" />
            </span>
            <span>
              {R.colMargin}: <span className="tabular-nums text-text-2">{margin(r)}</span>
            </span>
          </span>
        </li>
      ))}
      <li className={cn(cardClass, "flex flex-col gap-1 bg-surface-2 px-3.5 py-3 text-[13px]")}>
        <span className="flex items-center justify-between gap-2 font-bold">
          {R.total}
          <Money value={sum((r) => r.total_profit)} className={profitTone(sum((r) => r.total_profit))} />
        </span>
        <span className="flex flex-wrap gap-x-3 text-xs text-text-3">
          <span>
            {R.colOrders}: <span className="tabular-nums">{formatNumber(sum((r) => r.order_count))}</span>
          </span>
          <span>
            {R.sortLabels.revenue}: <Money value={sum((r) => r.total_revenue)} />
          </span>
        </span>
      </li>
    </ul>
  ) : (
    <section aria-label={R.channelsAria} className={cn(cardClass, "overflow-hidden")}>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[13.5px]">
          <thead>
            <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:whitespace-nowrap">
              <th scope="col" className="w-full text-start">
                {R.colChannel}
              </th>
              <th scope="col" className="text-end">
                {R.colOrders}
              </th>
              <th scope="col" className="text-end">
                {R.colRevenue}
              </th>
              <th scope="col" className="text-end">
                {R.colOrderProfit}
              </th>
              <th scope="col" className="text-end">
                {R.colMargin}
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr
                key={r.channel}
                className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
              >
                <td>
                  <ChannelBadge channel={r.channel} />
                </td>
                <td className="text-end tabular-nums">{formatNumber(r.order_count)}</td>
                <td className="text-end">
                  <Money value={r.total_revenue} />
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
              <td>{R.total}</td>
              <td className="text-end tabular-nums">{formatNumber(sum((r) => r.order_count))}</td>
              <td className="text-end">
                <Money value={sum((r) => r.total_revenue)} />
              </td>
              <td className={cn("text-end", profitTone(sum((r) => r.total_profit)))}>
                <Money value={sum((r) => r.total_profit)} />
              </td>
              <td className="text-end text-text-3">{R.nil}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  )

  return (
    <div className="flex flex-col gap-4">
      <div className={cn("grid gap-4", !mobile && "grid-cols-2 gap-5")}>
        <BarChart
          title={R.chartRevenue}
          aria={R.chartRevenueAria}
          rows={data}
          pick={(r) => r.total_revenue}
          fill="bg-bar-a"
          mobile={mobile}
        />
        <BarChart
          title={R.chartProfit}
          aria={R.chartProfitAria}
          rows={data}
          pick={(r) => r.total_profit}
          fill="bg-profit"
          mobile={mobile}
        />
      </div>
      {table}
      <CheckLines checks={checks} />
      <p className="text-xs text-text-3">{R.channelsNote}</p>
    </div>
  )
}
