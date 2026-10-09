"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Factory, Info, Plus, Truck } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { DateRangePopover } from "@/components/orders/list/date-range-popover"
import { JalaliDateRangePicker, type IsoDateRange } from "@/components/jalali-date-picker"
import { btnClass } from "@/components/record-sale/primitives"
import { formatJalali, wholeMonthLabel, type IsoRange } from "@/lib/jalali"
import { cn } from "@/lib/utils"
import { D } from "./copy"
import { KpiCards } from "./kpi-cards"
import { PRESET_KINDS, periodQuery, presets, readPeriod, storeToday, type PeriodKind } from "./period"
import { RecentOrders } from "./recent-orders"
import { SettlementsCard } from "./settlements-card"
import { ShippingCard } from "./shipping-card"
import { StockCard } from "./stock-card"
import { useDashboardData, useStoreTimeZone } from "./use-dashboard-data"
import { useCurrency } from "@/lib/use-currency"

const short = (iso: string) => formatJalali(iso, "yyyy/MM/dd")

/** «شهریور ۱۴۰۵» for a whole month, else «۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۱۵». */
function rangeText(range: IsoRange): string {
  return wholeMonthLabel(range) ?? D.periodRange(short(range.from), short(range.to))
}

/**
 * خانه (design/screens/01-dashboard.md). Read-only: KPIs from the P&L for the
 * selected period, «فروش امروز» for the store's today, shipping economics,
 * stock warnings and the newest orders. Each card loads (and fails)
 * on its own. The period lives in the URL (?from=&to=; none = this month).
 */
export function Dashboard() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()

  const timeZone = useStoreTimeZone()
  const [now] = React.useState(() => new Date())
  const today = timeZone ? storeToday(now, timeZone) : null
  const period = today ? readPeriod(new URLSearchParams(params.toString()), today) : null

  const data = useDashboardData(period?.range ?? null)

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

      <KpiCards
        periodWord={periodWord}
        range={period?.range ?? null}
        pnl={data.pnl}
        channels={data.channels}
        purchases={data.purchases}
        mobile={mobile}
      />

      <div className={cn("flex flex-col", mobile ? "gap-4" : "gap-5 lg:flex-row lg:items-stretch")}>
        <StockCard catalog={data.catalog} lowStock={data.lowStock} mobile={mobile} />
        <div className="min-w-0 grow">
          <RecentOrders orders={data.orders} timeZone={timeZone ?? "Asia/Tehran"} mobile={mobile} />
        </div>
      </div>

      <SettlementsCard pending={data.settlements} mobile={mobile} />

      <ShippingCard
        periodWord={periodWord}
        rangeText={period ? rangeText(period.range) : ""}
        shipping={data.shipping}
        storeHasOrders={data.orders.status !== "ready" || data.orders.data.length > 0}
        mobile={mobile}
      />

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

const PRESET_LABELS: Record<PeriodKind, string> = {
  today: D.periodToday,
  last7: D.periodLast7,
  thisMonth: D.periodThisMonth,
  lastMonth: D.periodLastMonth,
  custom: D.periodCustom,
}

/**
 * `.seg` that scrolls sideways instead of overflowing: five options don't fit
 * a 358px phone row. `value` null = no option selected (a custom range on
 * desktop, where the range button stands in for «بازه دلخواه»).
 */
function PeriodSegment({
  value,
  options,
  onChange,
  mobile,
}: {
  value: PeriodKind | null
  options: readonly PeriodKind[]
  onChange: (k: PeriodKind) => void
  mobile: boolean
}) {
  return (
    <div className={cn(mobile && "-mx-4 overflow-x-auto px-4 [scrollbar-width:none]")}>
      <div
        role="radiogroup"
        aria-label={D.periodAria}
        className="flex w-max gap-0.5 rounded-[10px] border border-border bg-surface-2 p-[3px]"
      >
        {options.map((k) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={value === k}
            onClick={() => onChange(k)}
            className={cn(
              "shrink-0 cursor-pointer rounded-[7px] px-3 text-[13px] font-semibold whitespace-nowrap text-text-2 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
              mobile ? "h-10" : "h-[32px]",
              value === k && "bg-card text-heading shadow-[0_4px_14px_rgba(18,22,38,.08)]"
            )}
          >
            {PRESET_LABELS[k]}
          </button>
        ))}
      </div>
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

  const longDate = today ? formatJalali(today, "EEEE، d MMMM yyyy") : "\u00a0"

  if (mobile) {
    return (
      <div className="flex flex-col gap-2.5">
        <span className="text-[13px] font-semibold text-text-2">{longDate}</span>
        {kind && (
          <PeriodSegment
            value={kind}
            options={[...PRESET_KINDS, "custom"]}
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
          <PeriodSegment value={kind === "custom" ? null : kind} options={PRESET_KINDS} mobile={false} onChange={onPick} />
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
