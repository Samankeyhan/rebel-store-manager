"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Factory, Info, Plus, Truck } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { Segment } from "@/components/common/segment"
import { DateRangePopover } from "@/components/orders/list/date-range-popover"
import { JalaliDateRangePicker, type IsoDateRange } from "@/components/jalali-date-picker"
import { btnClass } from "@/components/record-sale/primitives"
import { formatJalali, wholeMonthLabel, type IsoRange } from "@/lib/jalali"
import { cn } from "@/lib/utils"
import { D } from "./copy"
import { KpiCards } from "./kpi-cards"
import { periodQuery, presets, readPeriod, storeToday, type PeriodKind } from "./period"
import { RecentOrders } from "./recent-orders"
import { ShippingCard } from "./shipping-card"
import { StockCard } from "./stock-card"
import { useDashboardData, useStoreTimeZone } from "./use-dashboard-data"

const short = (iso: string) => formatJalali(iso, "yyyy/MM/dd")

/** «شهریور ۱۴۰۵» for a whole month, else «۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۱۵». */
function rangeText(range: IsoRange): string {
  return wholeMonthLabel(range) ?? D.periodRange(short(range.from), short(range.to))
}

/**
 * خانه (design/screens/01-dashboard.md). Read-only: KPIs from the P&L for the
 * selected period, «فروش امروز» for the store's today, shipping economics,
 * out-of-stock items and the newest orders. Each card loads (and fails)
 * on its own. The period lives in the URL (?from=&to=; none = this month).
 */
export function Dashboard() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()

  const timeZone = useStoreTimeZone()
  const [now] = React.useState(() => new Date())
  const today = timeZone ? storeToday(now, timeZone) : null
  const period = today ? readPeriod(new URLSearchParams(params.toString()), today) : null

  const data = useDashboardData(period?.range ?? null, today)

  const setRange = (range: IsoRange) => {
    if (!today) return
    const qs = periodQuery(range, today)
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
  }

  const firstRun =
    data.catalog.status === "ready" &&
    data.catalog.data.products.length === 0 &&
    data.orders.status === "ready" &&
    data.orders.data.length === 0

  const periodWord = period ? D.periodWord[period.kind] : D.periodWord.thisMonth

  return (
    <div className={cn("flex flex-col", mobile ? "gap-4 pb-28" : "gap-6")}>
      <Header
        today={today}
        period={period}
        mobile={mobile}
        onPick={(kind) => today && kind !== "custom" && setRange(presets(today)[kind])}
        onRange={setRange}
      />

      {firstRun && (
        <div role="status" className="flex items-start gap-3 rounded-xl bg-info-soft px-4 py-3.5 text-[13.5px]">
          <Info className="mt-0.5 size-5 shrink-0 text-info" aria-hidden />
          <div className="flex grow flex-col gap-0.5">
            <b className="text-heading">{D.welcomeTitle}</b>
            <span className="text-text-2">{D.welcomeBody}</span>
          </div>
          <Link href="/products" className={btnClass("outline", "sm", "shrink-0 self-center")}>
            {D.welcomeCta}
          </Link>
        </div>
      )}

      <KpiCards periodWord={periodWord} pnl={data.pnl} channels={data.channels} today={data.today} mobile={mobile} />

      <div className={cn("flex flex-col", mobile ? "gap-4" : "gap-5 lg:flex-row lg:items-stretch")}>
        <ShippingCard
          periodWord={periodWord}
          rangeText={period ? rangeText(period.range) : ""}
          shipping={data.shipping}
          storeHasOrders={data.orders.status !== "ready" || data.orders.data.length > 0}
          mobile={mobile}
        />
        <StockCard catalog={data.catalog} mobile={mobile} />
      </div>

      <RecentOrders orders={data.orders} timeZone={timeZone ?? "Asia/Tehran"} mobile={mobile} />

      {mobile && (
        <nav
          aria-label={D.quickActionsAria}
          className="fixed inset-x-0 bottom-0 z-30 flex gap-2 border-t border-border bg-card px-4 pt-3 pb-[max(20px,env(safe-area-inset-bottom))]"
        >
          <Link href="/sales/new" className={btnClass("primary", "lg", "grow")}>
            <Plus className="size-[18px]" aria-hidden />
            {D.newSale}
          </Link>
          <Link href="/purchases" className={btnClass("outline", "lg", "px-3")}>
            <Truck className="size-[18px] -scale-x-100" aria-hidden />
            {D.newPurchase}
          </Link>
          <Link href="/production" className={btnClass("outline", "lg", "px-3")}>
            <Factory className="size-[18px]" aria-hidden />
            {D.newProduction}
          </Link>
        </nav>
      )}
    </div>
  )
}

function Header({
  today,
  period,
  mobile,
  onPick,
  onRange,
}: {
  today: string | null
  period: { kind: PeriodKind; range: IsoRange } | null
  mobile: boolean
  onPick: (kind: PeriodKind) => void
  onRange: (range: IsoRange) => void
}) {
  // Mobile «بازه دلخواه»: a draft until both ends are picked.
  const [customOpen, setCustomOpen] = React.useState(false)
  const [draft, setDraft] = React.useState<IsoDateRange>({ from: null, to: null })
  const kind: PeriodKind | null = period ? (customOpen ? "custom" : period.kind) : null

  const longDate = today ? formatJalali(today, "EEEE، d MMMM yyyy") : " "
  const options: [PeriodKind, string][] = [
    ["thisMonth", D.periodThisMonth],
    ["lastMonth", D.periodLastMonth],
    ["custom", D.periodCustom],
  ]

  if (mobile) {
    return (
      <div className="flex flex-col gap-2.5">
        <span className="text-[13px] font-semibold text-text-2">{longDate}</span>
        {kind && (
          <Segment
            value={kind}
            options={options}
            label={D.periodAria}
            mobile
            onChange={(k) => {
              if (k === "custom") {
                setDraft(period ? { from: period.range.from, to: period.range.to } : { from: null, to: null })
                setCustomOpen(true)
                return
              }
              setCustomOpen(false)
              onPick(k)
            }}
          />
        )}
        {kind === "custom" && period && (
          <JalaliDateRangePicker
            value={customOpen ? draft : period.range}
            className="h-11 w-full"
            onChange={(r) => {
              setDraft(r)
              if (r.from && r.to) {
                setCustomOpen(false)
                onRange({ from: r.from, to: r.to })
              }
            }}
          />
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <span className="text-[15px] font-semibold text-text-2">{longDate}</span>
      <div className="flex flex-wrap items-center gap-2">
        {kind && (
          <Segment
            value={kind === "custom" ? "custom" : kind}
            options={options.slice(0, 2)}
            label={D.periodAria}
            onChange={(k) => onPick(k)}
          />
        )}
        {period && <DateRangePopover value={period.range} onApply={onRange} />}
        <span className="mx-1 h-6 w-px bg-border" aria-hidden />
        <nav aria-label={D.quickActionsAria} className="flex items-center gap-2">
          <Link href="/production" className={btnClass("outline", "md")}>
            <Factory className="size-4" aria-hidden />
            {D.newProduction}
          </Link>
          <Link href="/purchases" className={btnClass("outline", "md")}>
            <Truck className="size-4 -scale-x-100" aria-hidden />
            {D.newPurchase}
          </Link>
          <Link href="/sales/new" className={btnClass("primary", "md")}>
            <Plus className="size-4" aria-hidden />
            {D.newSale}
          </Link>
        </nav>
      </div>
    </div>
  )
}
