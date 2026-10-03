"use client"

import * as React from "react"
import { ChartNoAxesColumn, Info, Package, ReceiptText, RotateCw, Wallet } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cardClass } from "@/components/record-sale/primitives"
import { CHANNELS, type Channel } from "@/components/record-sale/copy"
import { marginPct } from "@/components/orders/order-figures"
import type { ChannelBreakdown, ProfitAndLoss } from "@/lib/api"
import { formatNumber } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { D } from "./copy"
import { sk } from "./parts"
import type { Loader, TodayData } from "./use-dashboard-data"

type Tone = "plain" | "profit" | "loss"

function Kpi({
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
    <div className={cn(cardClass, "flex min-w-0 flex-col", mobile ? "gap-0.5 px-3.5 py-3" : "gap-1.5 px-5 py-[18px]")}>
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
  pnl,
  channels,
  today,
  mobile,
}: {
  periodWord: string
  pnl: Loader<ProfitAndLoss>
  channels: Loader<ChannelBreakdown[]>
  today: Loader<TodayData>
  mobile: boolean
}) {
  const p = pnl.status === "ready" ? pnl.data : null
  const t = today.status === "ready" ? today.data : null
  const empty = p !== null && p.order_count === 0

  const todayCaption = t
    ? t.summary.order_count === 0
      ? D.todayNone
      : mobile
        ? D.todayCaptionMobile(t.summary.order_count)
        : D.todayCaption(t.summary.order_count, t.pending)
    : ""

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
        label={D.kpiToday}
        icon={ReceiptText}
        value={t ? t.summary.total_revenue : null}
        unit={mobile ? "" : D.toman}
        caption={todayCaption}
        load={today}
        mobile={mobile}
      />
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
        caption={
          margin == null ? D.nil : D.margin(`${formatNumber(margin)}٪`)
        }
        load={pnl}
        mobile={mobile}
      />
      <Kpi
        label={D.kpiOrders(periodWord)}
        icon={Package}
        value={p ? p.order_count : null}
        unit={mobile ? "" : D.orderUnit}
        hint={<OrdersHint />}
        caption={empty ? D.nil : split || D.nil}
        load={pnl}
        mobile={mobile}
      />
    </section>
  )
}
