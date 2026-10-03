"use client"

import * as React from "react"
import Link from "next/link"
import { ChartNoAxesColumn, ChevronLeft, Info, Package, RotateCw, Wallet, WalletCards } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cardClass } from "@/components/record-sale/primitives"
import { CHANNELS, type Channel } from "@/components/record-sale/copy"
import { marginPct } from "@/components/orders/order-figures"
import type { ChannelBreakdown, ProfitAndLoss, PurchasesSummary } from "@/lib/api"
import type { IsoRange } from "@/lib/jalali"
import { formatNumber } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { cn } from "@/lib/utils"
import { D } from "./copy"
import { sk } from "./parts"
import type { Loader } from "./use-dashboard-data"

type Tone = "plain" | "profit" | "loss"

function Kpi({
  className,
  label,
  icon: Icon,
  value,
  unit,
  tone = "plain",
  caption,
  hint,
  load,
  mobile,
}: {
  className?: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  value: number | null
  unit: string
  tone?: Tone
  caption: React.ReactNode
  hint?: React.ReactNode
  /** The request behind the value: loading → skeleton, error → «—» + retry. */
  load: Loader<unknown>
  mobile: boolean
}) {
  return (
    <div className={cn(cardClass, "flex min-w-0 flex-col", mobile ? "gap-0.5 px-3.5 py-3" : "gap-1.5 px-5 py-[18px]", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className={cn("flex min-w-0 items-center gap-1 font-semibold text-text-2", mobile ? "text-xs" : "text-[13px]")}>
          <span className="truncate">{label}</span>
          {hint}
        </span>
        {!mobile && <Icon className="size-[18px] shrink-0 text-text-3" aria-hidden />}
      </div>
      {load.status === "loading" ? (
        <div aria-busy="true" aria-label={D.loadingAria} className="flex flex-col gap-2 py-1">
          <Skeleton className={cn(sk, mobile ? "h-5 w-24" : "h-7 w-36")} />
          <Skeleton className={cn(sk, "h-3.5 w-28")} />
        </div>
      ) : load.status === "error" ? (
        <>
          <span className={cn("font-bold text-text-3", mobile ? "text-lg" : "text-[26px] leading-[38px]")}>{D.nil}</span>
          <span className="flex items-center gap-1.5 text-xs text-text-3">
            {D.unavailable}
            <button
              type="button"
              onClick={load.retry}
              aria-label={D.retryAria(label)}
              className="inline-flex size-7 cursor-pointer items-center justify-center rounded-md text-text-2 outline-none hover:bg-surface-2 focus-visible:ring-3 focus-visible:ring-ring/30"
            >
              <RotateCw className="size-3.5" aria-hidden />
            </button>
          </span>
        </>
      ) : (
        <>
          <span className="flex items-baseline gap-1.5">
            <span
              className={cn(
                "font-bold tabular-nums",
                mobile ? "text-lg" : "text-[26px] leading-[38px]",
                tone === "profit" && "text-profit",
                tone === "loss" && "text-loss",
                value === 0 && "text-text-3"
              )}
            >
              {value == null ? D.nil : formatNumber(value)}
            </span>
            <span className="text-[13px] font-medium text-text-3">{unit}</span>
          </span>
          <span className={cn("text-xs text-text-3", mobile ? "truncate" : "line-clamp-2")}>{caption}</span>
        </>
      )}
    </div>
  )
}

function OrdersHint() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={D.ordersExcludedAria}
          className="inline-flex size-6 shrink-0 cursor-help items-center justify-center rounded-full text-text-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
        >
          <Info className="size-3.5" aria-hidden />
        </button>
      </TooltipTrigger>
      <TooltipContent>{D.ordersExcluded}</TooltipContent>
    </Tooltip>
  )
}

/** «۳ وب‌سایت · ۲ اینستاگرام …» — counts from /reports/channels, largest revenue first. */
function channelSplit(rows: ChannelBreakdown[]): string {
  return rows.map((r) => D.channelCount(r.order_count, CHANNELS[r.channel as Channel]?.name ?? r.channel)).join(" · ")
}

export function KpiCards({
  periodWord,
  range,
  pnl,
  channels,
  purchases,
  mobile,
}: {
  periodWord: string
  range: IsoRange | null
  pnl: Loader<ProfitAndLoss>
  channels: Loader<ChannelBreakdown[]>
  purchases: Loader<PurchasesSummary>
  mobile: boolean
}) {
  const p = pnl.status === "ready" ? pnl.data : null
  const empty = p !== null && p.order_count === 0

  // Display ratio only: net ÷ revenue, both straight from the P&L.
  const margin = p ? marginPct(p.net_profit, p.total_revenue) : null
  const netTone: Tone = !p || p.net_profit === 0 ? "plain" : p.net_profit > 0 ? "profit" : "loss"

  const split = channels.status === "ready" ? channelSplit(channels.data) : ""

  return (
    <section
      aria-label={mobile ? undefined : D.kpiAria}
      className={cn("grid", mobile ? "grid-cols-2 gap-2.5" : "grid-cols-2 gap-5 xl:grid-cols-4")}
    >
      <Kpi
        label={D.kpiRevenue(periodWord)}
        icon={Wallet}
        value={p ? p.total_revenue : null}
        unit={mobile ? "" : D.toman}
        caption={
          !p || empty
            ? D.nil
            : mobile
              ? D.toman
              : D.revenueCaption(formatNumber(p.items_revenue), formatNumber(p.shipping_revenue))
        }
        load={pnl}
        mobile={mobile}
      />
      <Kpi
        label={D.kpiNet(periodWord)}
        icon={ChartNoAxesColumn}
        value={p ? p.net_profit : null}
        unit={mobile ? "" : D.toman}
        tone={netTone}
        caption={margin == null ? D.nil : D.margin(`${formatNumber(margin)}٪`)}
        load={pnl}
        mobile={mobile}
      />
      <Kpi
        label={D.kpiOrders(periodWord)}
        icon={Package}
        value={p ? p.order_count : null}
        unit={mobile ? "" : D.orderUnit}
        hint={<OrdersHint />}
        className={mobile ? "col-span-2" : undefined}
        caption={empty ? D.nil : split || D.nil}
        load={pnl}
        mobile={mobile}
      />
      <CostsCard range={range} pnl={pnl} purchases={purchases} mobile={mobile} />
    </section>
  )
}

/**
 * «خرید و هزینه‌ها»: four separate figures for the period, never added
 * together — operating expenses and postage paid come from the P&L,
 * purchases from /reports/purchases (inventory, not P&L). Each line opens
 * its own screen on the same range.
 */
function CostsCard({
  range,
  pnl,
  purchases,
  mobile,
}: {
  range: IsoRange | null
  pnl: Loader<ProfitAndLoss>
  purchases: Loader<PurchasesSummary>
  mobile: boolean
}) {
  const qs = range ? new URLSearchParams({ from: range.from, to: range.to }).toString() : ""
  const p = pnl.status === "ready" ? pnl.data : null
  const b = purchases.status === "ready" ? purchases.data : null

  const lines: { label: string; href: string; value: number | null; count?: number; load: Loader<unknown> }[] = [
    { label: D.costsOperating, href: `/expenses?${qs}`, value: p?.operating_expenses ?? null, load: pnl },
    {
      label: D.costsMaterials,
      href: `/purchases?type=material&${qs}`,
      value: b?.material_purchases_total ?? null,
      count: b?.material_purchases_count,
      load: purchases,
    },
    {
      label: D.costsProducts,
      href: `/purchases?type=product&${qs}`,
      value: b?.product_purchases_total ?? null,
      count: b?.product_purchases_count,
      load: purchases,
    },
    { label: D.costsPostage, href: `/postage?${qs}`, value: p?.postage_actual ?? null, load: pnl },
  ]

  return (
    <div className={cn(cardClass, "flex min-w-0 flex-col gap-1.5", mobile ? "col-span-2 px-3.5 py-3" : "px-5 py-[18px]")}>
      <div className="flex items-center justify-between gap-2">
        <span className={cn("font-semibold text-text-2", mobile ? "text-xs" : "text-[13px]")}>{D.costsTitle}</span>
        {!mobile && <WalletCards className="size-[18px] shrink-0 text-text-3" aria-hidden />}
      </div>
      <ul className="flex flex-col">
        {lines.map((l) => (
          <li key={l.label} className={cn("flex min-h-7 items-center justify-between gap-2 py-0.5", mobile ? "text-[13px]" : "text-[12.5px]")}>
            <Link
              href={l.href}
              aria-label={D.costsLinkAria(l.label)}
              className="inline-flex min-w-0 items-center gap-1 rounded-sm leading-[18px] text-text-2 outline-none hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/30"
            >
              <span>{l.label}</span>
              {l.count != null && <span className="text-xs text-text-3 tabular-nums">{D.costsCount(l.count)}</span>}
              <ChevronLeft className="size-3.5 shrink-0 text-text-3" aria-hidden />
            </Link>
            {l.load.status === "loading" ? (
              <Skeleton className={cn(sk, "h-4 w-20")} />
            ) : l.load.status === "error" ? (
              <span className="flex items-center gap-1 text-text-3">
                {D.nil}
                <button
                  type="button"
                  onClick={l.load.retry}
                  aria-label={D.retryAria(l.label)}
                  className="inline-flex size-6 cursor-pointer items-center justify-center rounded-md outline-none hover:bg-surface-2 focus-visible:ring-3 focus-visible:ring-ring/30"
                >
                  <RotateCw className="size-3" aria-hidden />
                </button>
              </span>
            ) : (
              <span className={cn("font-bold whitespace-nowrap tabular-nums", l.value === 0 && "text-text-3")}>
                {formatMoney(l.value ?? 0)}
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="text-[11.5px] leading-[18px] text-text-3">{D.costsNote}</p>
    </div>
  )
}
