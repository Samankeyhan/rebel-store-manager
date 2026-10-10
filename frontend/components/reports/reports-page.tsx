"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ChartColumn, CreditCard, Package, Scale, Store, Trash2, Truck, Wallet, type LucideIcon } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { Segment } from "@/components/common/segment"
import { useLoad, useStoreTimeZone, type Loader } from "@/components/dashboard/use-dashboard-data"
import { getProfitAndLoss, type ProfitAndLoss } from "@/lib/api"
import { formatJalali, wholeMonthLabel } from "@/lib/jalali"
import {
  apiRange,
  periodKey,
  readReportPeriod,
  readReportTab,
  writeReportPeriod,
  writeReportTab,
  type ReportPeriod,
  type ReportTab,
} from "@/lib/report-period"
import { pnlIsEmpty } from "@/lib/reports"
import { storeToday } from "@/lib/store-day"
import { useCurrency } from "@/lib/use-currency"
import { cn } from "@/lib/utils"
import { ChannelsTab } from "./channels-tab"
import { R } from "./copy"
import { ExpensesTab } from "./expenses-tab"
import { PaymentsTab } from "./payments-tab"
import { PeriodBar } from "./period-bar"
import { PnlTab } from "./pnl-tab"
import { ProductsTab } from "./products-tab"
import { ShippingTab } from "./shipping-tab"
import { WasteTab } from "./waste-tab"

type TabProps = { period: ReportPeriod; pnl: Loader<ProfitAndLoss>; periodTitle: string; mobile: boolean }

type TabDef = {
  label: string
  short: string
  icon: LucideIcon
  Body: React.ComponentType<TabProps>
  /**
   * The tab shows figures that are not in the P&L (settlements by
   * settled_date, purchases, unknown-cost waste), so an all-zero P&L does not
   * mean it is empty: the shell leaves the empty state to the tab.
   */
  ownEmpty?: true
}

/**
 * The reports, in tab order (the same as REPORT_TAB_IDS in
 * lib/report-period.ts). The shell, the period and the P&L load are shared.
 */
const TABS: Record<ReportTab, TabDef> = {
  pnl: {
    label: R.tabPnl,
    short: R.tabPnl,
    icon: Scale,
    Body: PnlBody,
  },
  products: {
    label: R.tabProducts,
    short: R.tabProductsShort,
    icon: Package,
    Body: ProductsTab,
  },
  channels: {
    label: R.tabChannels,
    short: R.tabChannels,
    icon: Store,
    Body: ChannelsTab,
  },
  shipping: {
    label: R.tabShipping,
    short: R.tabShippingShort,
    icon: Truck,
    Body: ShippingTab,
  },
  payments: {
    label: R.tabPayments,
    short: R.tabPaymentsShort,
    icon: CreditCard,
    Body: PaymentsTab,
    ownEmpty: true,
  },
  waste: {
    label: R.tabWaste,
    short: R.tabWaste,
    icon: Trash2,
    Body: WasteTab,
    ownEmpty: true,
  },
  expenses: {
    label: R.tabExpenses,
    short: R.tabExpensesShort,
    icon: Wallet,
    Body: ExpensesTab,
    ownEmpty: true,
  },
}

function PnlBody({ pnl, periodTitle, mobile }: TabProps) {
  if (pnl.status === "loading") return <LoadingBlock mobile={mobile} label={R.loadingAria} />
  if (pnl.status === "error")
    return <ErrorBlock title={R.errorTitle} body={R.errorBody} retry={R.retry} onRetry={pnl.retry} mobile={mobile} />
  return <PnlTab pnl={pnl.data} periodTitle={periodTitle} mobile={mobile} />
}

const short = (iso: string) => formatJalali(iso, "yyyy/MM/dd")

/** «مهر ۱۴۰۵» for a whole Jalali month, «از ابتدا» for all time, else the range. */
function periodTitle(period: ReportPeriod): string {
  if (!period.range) return R.allTime
  return wholeMonthLabel(period.range) ?? R.rangeText(short(period.range.from), short(period.range.to))
}

/**
 * گزارش‌ها (design/screens/12-reports.md): read-only reports over one
 * period. The period (?from=&to= or ?period=all; none = this Jalali month)
 * and the tab (?tab=) live in the URL. The P&L for the period loads once
 * here: the P&L tab shows it, and the other tabs check their totals against
 * it («مطابقت»). "Today" is the store's day (settings.timezone).
 */
export function ReportsPage() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()

  const search = new URLSearchParams(params.toString())
  const tab = readReportTab(search)

  const timeZone = useStoreTimeZone()
  const [now] = React.useState(() => new Date())
  const today = timeZone ? storeToday(now, timeZone) : null
  const period = today ? readReportPeriod(search, today) : null

  const pnl = useLoad<ProfitAndLoss>("REPORTS", period ? periodKey(period) : null, () => getProfitAndLoss(apiRange(period!)))

  const navigate = (next: URLSearchParams) => {
    const qs = next.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
  }
  const setTab = (t: ReportTab) => navigate(writeReportTab(new URLSearchParams(window.location.search), t))
  const setPeriod = (p: ReportPeriod) => {
    if (today) navigate(writeReportPeriod(new URLSearchParams(window.location.search), p, today))
  }

  const ids = Object.keys(TABS) as ReportTab[]
  const tabs = mobile ? (
    <div className="-mx-4 overflow-x-auto px-4 [scrollbar-width:none]">
      <Segment<ReportTab>
        value={tab}
        options={ids.map((id) => [id, TABS[id].short] as const)}
        onChange={setTab}
        label={R.tabsLabel}
        mobile
        className="w-max min-w-full"
      />
    </div>
  ) : (
    <div role="tablist" aria-label={R.tabsLabel} className="flex gap-1 overflow-x-auto border-b border-border [scrollbar-width:none]">
      {ids.map((id) => {
        const { label, icon: Icon } = TABS[id]
        const on = tab === id
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => setTab(id)}
            className={cn(
              "-mb-px inline-flex h-10 cursor-pointer items-center gap-1.5 border-b-2 border-transparent px-3 text-[13.5px] font-semibold whitespace-nowrap text-text-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
              on && "border-primary text-heading"
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </button>
        )
      })}
    </div>
  )

  let body: React.ReactNode
  if (!period) body = <LoadingBlock mobile={mobile} label={R.loadingAria} />
  // Nothing at all happened in the period: one friendly state, not tables of zeros.
  else if (pnl.status === "ready" && pnlIsEmpty(pnl.data) && !TABS[tab].ownEmpty)
    body = (
      <StateShell icon={ChartColumn} mobile={mobile} title={R.emptyTitle} body={mobile ? R.emptyBodyMobile : R.emptyBody} />
    )
  else {
    const { Body } = TABS[tab]
    // Keyed by tab: a tab's own load starts when it is shown.
    body = <Body key={tab} period={period} pnl={pnl} periodTitle={periodTitle(period)} mobile={mobile} />
  }

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-5")}>
      <PeriodBar period={period} today={today} mobile={mobile} onChange={setPeriod} />
      {tabs}
      {body}
    </div>
  )
}
