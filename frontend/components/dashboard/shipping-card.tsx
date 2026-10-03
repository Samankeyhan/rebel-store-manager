"use client"

import * as React from "react"
import Link from "next/link"
import { Info, TriangleAlert, Truck } from "lucide-react"
import { badgeBase } from "@/components/common/status"
import { formatMoney, formatMoneyNumber } from "@/lib/money"
import { cn } from "@/lib/utils"
import { D } from "./copy"
import { Amount, CardEmpty, CardError, CardLoading, DashCard } from "./parts"
import type { Loader, ShippingData } from "./use-dashboard-data"

type Verdict = "loss" | "even" | "profit"

const VERDICT: Record<Verdict, { label: string; badge: string }> = {
  loss: { label: D.badgeLoss, badge: "bg-loss-soft text-loss" },
  even: { label: D.badgeEven, badge: "bg-surface-2 text-text-2" },
  profit: { label: D.badgeProfit, badge: "bg-profit-soft text-profit" },
}

const hatch: React.CSSProperties = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--loss-soft) 0 5px, color-mix(in srgb, var(--loss) 22%, transparent) 5px 7px)",
}

/** Width of a bar segment as a share of the larger side (display only). */
const pct = (part: number, whole: number) => (whole > 0 ? Math.max(0, Math.min(100, (part / whole) * 100)) : 0)

function Segment({
  width,
  className,
  style,
  label,
  showLabel,
  edge,
}: {
  width: number
  className: string
  style?: React.CSSProperties
  label?: string
  showLabel: boolean
  edge: "start" | "end" | "both"
}) {
  if (width <= 0) return null
  return (
    <div
      className={cn(
        "flex h-full min-w-0 items-center overflow-hidden px-2 text-xs font-semibold whitespace-nowrap tabular-nums",
        edge !== "end" && "rounded-s-md",
        edge !== "start" && "rounded-e-md",
        className
      )}
      style={{ width: `${width}%`, ...style }}
    >
      {showLabel && label && width >= 14 ? label : null}
    </div>
  )
}

/**
 * «اقتصاد ارسال» from GET /reports/shipping. The headline result, the badge
 * and the break-even sentence use the estimate-based figures (postage frozen
 * on each shipped order), so a period whose postage batches are not yet paid
 * doesn't look profitable. Postage actually paid is a reference line, with an
 * amber note while part of the period's estimate is still unpaid.
 */
export function ShippingCard({
  periodWord,
  rangeText,
  shipping,
  storeHasOrders,
  mobile,
}: {
  periodWord: string
  /** False on a brand-new store: the empty card then uses the design's first-run copy. */
  storeHasOrders: boolean
  rangeText: string
  shipping: Loader<ShippingData>
  mobile: boolean
}) {
  const id = "dash-shipping"
  const title = D.shipTitle(periodWord)

  if (shipping.status !== "ready") {
    return (
      <DashCard id={id} title={title} className="grow">
        {shipping.status === "loading" ? (
          <CardLoading rows={mobile ? 5 : 4} />
        ) : (
          <CardError title={D.shipErrorTitle} code={shipping.code} onRetry={shipping.retry} mobile={mobile} />
        )}
      </DashCard>
    )
  }

  const s = shipping.data.summary
  const estimate = shipping.data.estimate

  if (s.shipped_order_count === 0) {
    return (
      <DashCard id={id} title={title} className="grow">
        <CardEmpty
          icon={({ className }) => <Truck className={cn(className, "-scale-x-100")} aria-hidden />}
          title={storeHasOrders ? D.shipEmptyPeriodTitle : D.shipEmptyTitle}
          body={storeHasOrders ? D.shipEmptyPeriodBody : D.shipEmptyBody}
          className="grow justify-center"
        />
      </DashCard>
    )
  }

  const net = s.net_shipping_result_estimated
  const verdict: Verdict = net < 0 ? "loss" : net > 0 ? "profit" : "even"
  const v = VERDICT[verdict]
  const avgNet = s.avg_net_shipping_result_estimated

  // Bars compare the period's totals, scaled to the larger side (display only).
  const cost = s.packaging_cost + s.postage_estimated
  const scale = Math.max(s.shipping_revenue, cost)

  const badge = <span className={cn(badgeBase, v.badge)}>{v.label}</span>
  const caption = (
    <span title={D.shipCaptionHelp}>{mobile ? D.shipCaptionMobile(s.shipped_order_count) : D.shipCaption(s.shipped_order_count, rangeText)}</span>
  )

  const bars = (
    <div
      role="img"
      aria-label={D.barsAria(formatMoney(s.shipping_revenue), formatMoney(cost))}
      className="flex flex-col gap-2.5"
    >
      <div className="flex items-center">
        <span className="w-16 shrink-0 text-xs font-semibold text-text-2">{D.barCharged}</span>
        <div className={cn("flex grow", mobile ? "h-3.5" : "h-[26px]")}>
          <Segment
            width={pct(s.shipping_revenue, scale)}
            className="bg-bar-a text-white"
            label={formatMoney(s.shipping_revenue)}
            showLabel={!mobile}
            edge={net < 0 ? "start" : "both"}
          />
          {net < 0 && (
            <Segment
              width={pct(-net, scale)}
              className="text-loss"
              style={hatch}
              label={`${D.barShortfall} ${formatMoney(-net)}`}
              showLabel={!mobile}
              edge={s.shipping_revenue > 0 ? "end" : "both"}
            />
          )}
        </div>
      </div>
      <div className="flex items-center">
        <span className="w-16 shrink-0 text-xs font-semibold text-text-2">{D.barCost}</span>
        <div className={cn("flex grow gap-0.5", mobile ? "h-3.5" : "h-[26px]")}>
          <Segment
            width={pct(s.packaging_cost, scale)}
            className="bg-bar-b text-foreground"
            label={`${D.barPackaging} ${formatMoney(s.packaging_cost)}`}
            showLabel={!mobile}
            edge={s.postage_estimated > 0 ? "start" : "both"}
          />
          <Segment
            width={pct(s.postage_estimated, scale)}
            className="bg-bar-c text-white"
            label={`${D.barPostage} ${formatMoney(s.postage_estimated)}`}
            showLabel={!mobile}
            edge={s.packaging_cost > 0 ? "end" : "both"}
          />
        </div>
      </div>
      {mobile && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-text-3">
          <Legend swatch="bg-bar-a" label={D.barCharged} />
          <Legend swatch="bg-bar-b" label={D.barPackaging} />
          <Legend swatch="bg-bar-c" label={D.barPostage} />
          {net < 0 && <span className="text-loss">▨ {D.barShortfall}</span>}
        </div>
      )}
    </div>
  )

  const paid = (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3 text-[13px]">
        <span className="text-text-2">{D.paidSoFar}</span>
        <Amount n={s.postage_actual} className="font-semibold" />
      </div>
      {s.postage_gap > 0 && (
        <div role="status" className="flex items-start gap-2 rounded-lg bg-warn-soft px-3 py-2 text-[13px] text-warn">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {D.unpaidNote}: <Amount n={s.postage_gap} className="font-bold" />
          </span>
        </div>
      )}
    </div>
  )

  const breakEven =
    avgNet < 0 ? (
      <div className="flex items-start gap-2.5 rounded-lg bg-info-soft px-3.5 py-2.5 text-[13px] text-foreground">
        <Info className="mt-0.5 size-4 shrink-0 text-info" aria-hidden />
        <span className="grow">{D.breakEven(formatMoney(-avgNet))}</span>
        <Link href="/postage" className="shrink-0 font-semibold whitespace-nowrap text-info hover:underline">
          {D.breakEvenLink}
        </Link>
      </div>
    ) : null

  const resultTone = verdict === "loss" ? "text-loss" : verdict === "profit" ? "text-profit" : "text-text-2"

  if (mobile) {
    const row = "flex items-baseline justify-between gap-3 text-[13.5px] leading-[22px]"
    return (
      <DashCard id={id} title={title} caption={caption} aside={badge} headerRule={false}>
        <div className="flex flex-col gap-3.5 px-4 pb-4">
          <div className="flex flex-col gap-1">
            <div className={row}>
              <span>{D.figCharged}</span>
              <Amount n={s.avg_shipping_revenue} />
            </div>
            <div className={row}>
              <span>{D.figPackaging}</span>
              <Amount n={-s.avg_packaging_cost} />
            </div>
            <div className={row}>
              <span>
                {D.figPostage}
                <span className="block text-xs text-text-3">
                  {D.postageRateNote} · {D.postageRateCaption}
                </span>
              </span>
              {estimate ? <Amount n={-estimate.estimate} className="shrink-0" /> : D.nil}
            </div>
            <div className="my-1 border-t border-border" />
            <div
              className={cn(
                row,
                "-mx-2 rounded-lg p-2 text-[15px] font-bold",
                verdict === "loss" ? "bg-loss-soft" : verdict === "profit" ? "bg-profit-soft" : "bg-surface-2"
              )}
            >
              <span className={resultTone}>{D.figResult}</span>
              <Amount n={avgNet} className={cn("text-xl", resultTone)} />
            </div>
            <div className={row}>
              <span className="text-text-3">{D.periodSumLabel}</span>
              <Amount n={net} className={cn("font-bold", resultTone)} />
            </div>
          </div>
          {bars}
          {paid}
        </div>
      </DashCard>
    )
  }

  const cell = (label: string, value: React.ReactNode, qualifier: string, sum: number, tone?: string, tint?: string) => (
    <div className={cn("flex min-w-0 flex-col gap-0.5", tint && cn("-my-2.5 rounded-[10px] px-3 py-2.5", tint))}>
      <span className={cn("text-xs font-bold text-text-2", tone)}>{label}</span>
      <span className={cn("text-xl font-bold tabular-nums", tone)}>{value}</span>
      <span className={cn("text-xs text-text-3", tone)}>{qualifier}</span>
      <span className={cn("text-xs text-text-3 tabular-nums", tone)}>{D.periodSum(formatMoney(sum))}</span>
    </div>
  )

  return (
    <DashCard id={id} title={title} caption={caption} aside={badge} className="grow">
      <div className="flex grow flex-col gap-5 p-5">
        <div className="grid grid-cols-4 gap-3">
          {/* The big figure's unit is the qualifier line right under it (D.perOrder: «<unit> برای هر سفارش»). */}
          {cell(D.figCharged, formatMoneyNumber(s.avg_shipping_revenue), D.perOrder, s.shipping_revenue)}
          {cell(D.figPackaging, formatMoneyNumber(s.avg_packaging_cost), D.perOrder, s.packaging_cost)}
          {cell(
            D.figPostage,
            estimate ? formatMoney(estimate.estimate) : D.nil,
            `${D.postageRateNote}: ${D.postageRateCaption}`,
            s.postage_estimated
          )}
          {cell(
            D.figResult,
            formatMoneyNumber(avgNet),
            verdict === "profit" ? D.resultProfit : verdict === "loss" ? D.resultLoss : D.perOrder,
            net,
            resultTone,
            verdict === "loss" ? "bg-loss-soft" : verdict === "profit" ? "bg-profit-soft" : "bg-surface-2"
          )}
        </div>
        {bars}
        {paid}
        {breakEven}
      </div>
    </DashCard>
  )
}

function Legend({ swatch, label }: { swatch: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("size-2 rounded-[2px]", swatch)} aria-hidden />
      {label}
    </span>
  )
}
