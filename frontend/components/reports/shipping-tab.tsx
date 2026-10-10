"use client"

import * as React from "react"
import { Truck } from "lucide-react"
import { ChannelBadge } from "@/components/common/status"
import { Money } from "@/components/common/money"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { useLoad, type Loader } from "@/components/dashboard/use-dashboard-data"
import { cardClass } from "@/components/record-sale/primitives"
import {
  getShippingByChannel,
  getShippingSummary,
  type ProfitAndLoss,
  type ShippingByChannel,
  type ShippingSummary,
} from "@/lib/api"
import { formatNumber } from "@/lib/persian-numbers"
import { apiRange, periodKey, type ReportPeriod } from "@/lib/report-period"
import { shippingChecks, shippingIsEmpty, shippingPnlChecks } from "@/lib/reports"
import { cn } from "@/lib/utils"
import { CheckLines, pnlChecks } from "./check-line"
import { R, SHIPPING_EXPLAIN as X } from "./copy"
import { ExplainRow, ReportNote, SignedMoney } from "./report-bits"

type Data = { summary: ShippingSummary; rows: ShippingByChannel[] }

/**
 * «ارسال و پست»: GET /reports/shipping and /reports/shipping-by-channel for
 * the period (rules §9 «Shipping summary»): shipped orders only, i.e.
 * revenue-eligible orders on channels that apply postage. Every figure is
 * the API's; the summary is checked against its channel rows and its own
 * definitions, and its order count and postage paid against the P&L.
 */
export function ShippingTab({
  period,
  pnl,
  mobile,
}: {
  period: ReportPeriod
  pnl: Loader<ProfitAndLoss>
  mobile: boolean
}) {
  const load = useLoad<Data>("REPORTS", periodKey(period), async () => {
    const r = apiRange(period)
    const [summary, rows] = await Promise.all([getShippingSummary(r), getShippingByChannel(r)])
    return { summary, rows }
  })

  if (load.status === "loading") return <LoadingBlock mobile={mobile} label={R.loadingAria} />
  if (load.status === "error")
    return <ErrorBlock title={R.errorTitle} body={R.errorBody} retry={R.retry} onRetry={load.retry} mobile={mobile} />

  const { summary: s, rows } = load.data
  const fromPnl = pnlChecks(pnl, (p) => {
    const c = shippingPnlChecks(s, p)
    return [
      { label: R.checkShipOrders, check: c.orders },
      { label: R.checkShipPostageActual, check: c.postageActual },
    ]
  })

  if (shippingIsEmpty(s, rows))
    return (
      <div className="flex flex-col gap-3">
        <StateShell icon={Truck} mobile={mobile} title={R.shippingEmptyTitle} body={R.shippingEmptyBody} />
        <CheckLines checks={fromPnl} />
      </div>
    )

  const c = shippingChecks(s, rows)
  const own = [
    { label: R.checkShipShipped, check: c.shipped },
    { label: R.checkShipRevenue, check: c.revenue },
    { label: R.checkShipPackaging, check: c.packaging },
    { label: R.checkShipEstimated, check: c.estimated },
    { label: R.checkShipNet, check: c.net },
    { label: R.checkShipActualResult, check: c.actualResult },
    { label: R.checkShipGap, check: c.gap },
  ]

  /** The per-shipped-order figure: its own column on desktop, inside the explanation on mobile. */
  const avg = (node: React.ReactNode) => (
    <>
      {mobile && `${R.perOrder}: `}
      {node}
    </>
  )

  const kpis = (
    <div className={cn("grid gap-3", mobile ? "grid-cols-2" : "grid-cols-4 gap-4")}>
      <Kpi label={X.net_shipping_result_estimated.label} mobile={mobile}>
        <SignedMoney value={s.net_shipping_result_estimated} />
      </Kpi>
      <Kpi label={X.net_shipping_result.label} mobile={mobile}>
        <SignedMoney value={s.net_shipping_result} />
      </Kpi>
      <Kpi label={X.postage_gap.label} mobile={mobile}>
        <SignedMoney value={s.postage_gap} neutral />
      </Kpi>
      <Kpi label={R.colShipped} mobile={mobile}>
        <span className="tabular-nums">{formatNumber(s.shipped_order_count)}</span>
      </Kpi>
    </div>
  )

  const statement = (
    <section aria-labelledby="ship-title" className={cn(cardClass, "overflow-hidden")}>
      <div className={cn("flex flex-wrap items-end justify-between gap-x-4 gap-y-1 border-b border-border", mobile ? "px-3.5 py-3" : "px-5 py-4")}>
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 id="ship-title" className={cn("font-bold text-heading", mobile ? "text-[15px]" : "text-lg")}>
            {R.shippingTitle}
          </h2>
          <span className="text-xs text-text-3">{R.shippingCaption(s.shipped_order_count, s.order_count)}</span>
        </div>
        {!mobile && <span className="text-xs text-text-3">{X.averages.label}</span>}
      </div>
      <ExplainRow
        id="ship-revenue"
        mobile={mobile}
        label={X.shipping_revenue.label}
        meaning={X.shipping_revenue.meaning}
        how={X.shipping_revenue.how}
        value={<Money value={s.shipping_revenue} />}
        second={avg(<Money value={s.avg_shipping_revenue} />)}
      />
      <ExplainRow
        id="ship-packaging"
        mobile={mobile}
        label={X.packaging_cost.label}
        meaning={X.packaging_cost.meaning}
        how={X.packaging_cost.how}
        value={<Money value={s.packaging_cost} />}
        second={avg(<Money value={s.avg_packaging_cost} />)}
      />
      <ExplainRow
        id="ship-estimated"
        mobile={mobile}
        label={X.postage_estimated.label}
        meaning={X.postage_estimated.meaning}
        how={X.postage_estimated.how}
        value={<Money value={s.postage_estimated} />}
        // Backend gap: no avg_postage_estimated.
        second={mobile ? undefined : R.nil}
      />
      <ExplainRow
        id="ship-net-estimated"
        mobile={mobile}
        bold
        label={X.net_shipping_result_estimated.label}
        meaning={X.net_shipping_result_estimated.meaning}
        how={X.net_shipping_result_estimated.how}
        value={<SignedMoney value={s.net_shipping_result_estimated} />}
        second={avg(<SignedMoney value={s.avg_net_shipping_result_estimated} />)}
      />
      <ExplainRow
        id="ship-actual"
        mobile={mobile}
        label={X.postage_actual.label}
        meaning={X.postage_actual.meaning}
        how={X.postage_actual.how}
        value={<Money value={s.postage_actual} />}
        second={avg(<Money value={s.avg_postage_actual} />)}
      />
      <ExplainRow
        id="ship-net-actual"
        mobile={mobile}
        bold
        label={X.net_shipping_result.label}
        meaning={X.net_shipping_result.meaning}
        how={X.net_shipping_result.how}
        value={<SignedMoney value={s.net_shipping_result} />}
        second={avg(<SignedMoney value={s.avg_net_shipping_result} />)}
      />
      <ExplainRow
        id="ship-gap"
        mobile={mobile}
        label={X.postage_gap.label}
        meaning={X.postage_gap.meaning}
        how={X.postage_gap.how}
        value={<SignedMoney value={s.postage_gap} neutral />}
        second={mobile ? undefined : R.nil}
      />
      <CheckLines className={cn("border-t border-border", mobile ? "px-3.5 py-3" : "px-5 py-3")} checks={own} />
    </section>
  )

  const sum = (pick: (r: ShippingByChannel) => number) => rows.reduce((t, r) => t + pick(r), 0)

  const channels =
    rows.length === 0 ? (
      <p className="text-xs text-text-3">{R.shippingNoChannels}</p>
    ) : mobile ? (
      <ul aria-label={R.shippingByChannel} className="flex flex-col gap-2">
        {rows.map((r) => (
          <li key={r.channel} className={cn(cardClass, "flex flex-col gap-1.5 px-3.5 py-3 text-[13px]")}>
            <span className="flex items-center justify-between gap-2">
              <ChannelBadge channel={r.channel} />
              <SignedMoney value={r.net} className="font-bold" />
            </span>
            <span className="flex flex-wrap gap-x-3 text-xs text-text-3">
              <span>
                {R.colShipped}: <span className="tabular-nums text-text-2">{formatNumber(r.shipped_order_count)}</span>
              </span>
              <span>
                {X.shipping_revenue.label}: <Money value={r.shipping_revenue} className="text-text-2" />
              </span>
              <span>
                {X.packaging_cost.label}: <Money value={r.packaging_cost} className="text-text-2" />
              </span>
              <span>
                {X.postage_estimated.label}: <Money value={r.postage_estimated} className="text-text-2" />
              </span>
              <span>
                {R.perOrder}: <SignedMoney value={r.net_per_order} />
              </span>
            </span>
          </li>
        ))}
      </ul>
    ) : (
      <section aria-label={R.shippingByChannel} className={cn(cardClass, "overflow-hidden")}>
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-[15px] font-bold text-heading">{R.shippingByChannel}</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:whitespace-nowrap">
                <th scope="col" className="w-full text-start">
                  {R.colChannel}
                </th>
                <th scope="col" className="text-end">
                  {R.colShipped}
                </th>
                <th scope="col" className="text-end">
                  {R.colShippingRevenue}
                </th>
                <th scope="col" className="text-end">
                  {R.colPackaging}
                </th>
                <th scope="col" className="text-end">
                  {R.colPostageEstimated}
                </th>
                <th scope="col" className="text-end">
                  {R.colShipNet}
                </th>
                <th scope="col" className="text-end">
                  {R.colShipNetPerOrder}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.channel}
                  className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
                >
                  <td>
                    <ChannelBadge channel={r.channel} />
                  </td>
                  <td className="text-end tabular-nums">{formatNumber(r.shipped_order_count)}</td>
                  <td className="text-end">
                    <Money value={r.shipping_revenue} />
                  </td>
                  <td className="text-end">
                    <Money value={r.packaging_cost} />
                  </td>
                  <td className="text-end">
                    <Money value={r.postage_estimated} />
                  </td>
                  <td className="text-end font-bold">
                    <SignedMoney value={r.net} />
                  </td>
                  <td className="text-end">
                    <SignedMoney value={r.net_per_order} />
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-bold [&>td]:h-12 [&>td]:bg-surface-2 [&>td]:px-4 [&>td]:whitespace-nowrap">
                <td>{R.total}</td>
                <td className="text-end tabular-nums">{formatNumber(sum((r) => r.shipped_order_count))}</td>
                <td className="text-end">
                  <Money value={sum((r) => r.shipping_revenue)} />
                </td>
                <td className="text-end">
                  <Money value={sum((r) => r.packaging_cost)} />
                </td>
                <td className="text-end">
                  <Money value={sum((r) => r.postage_estimated)} />
                </td>
                <td className="text-end">
                  <SignedMoney value={sum((r) => r.net)} />
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
      {kpis}
      {statement}
      {channels}
      {rows.length > 0 && <p className="text-xs text-text-3">{R.shippingChannelNote}</p>}
      <CheckLines checks={fromPnl} />
      <ReportNote>
        <span>{R.shippingScope}</span>
        <span>
          {X.averages.label}: {X.averages.meaning}
        </span>
      </ReportNote>
    </div>
  )
}

function Kpi({ label, mobile, children }: { label: string; mobile: boolean; children: React.ReactNode }) {
  return (
    <div className={cn(cardClass, "flex min-w-0 flex-col gap-1", mobile ? "px-3.5 py-3" : "px-5 py-4")}>
      <span className="text-xs font-semibold text-text-2">{label}</span>
      <span className={cn("font-bold", mobile ? "text-[15px]" : "text-xl")}>{children}</span>
    </div>
  )
}
