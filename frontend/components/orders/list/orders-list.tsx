"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ChevronDown, Plus, Search, X } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ORDER_STATUS_IDS } from "@/components/common/status"
import { CHANNEL_IDS, CHANNELS } from "@/components/record-sale/copy"
import { Btn, btnClass } from "@/components/record-sale/primitives"
import { ApiError, getSettings, listOrders, type OrderListItem } from "@/lib/api"
import { jalaliMonthRange, wholeMonthLabel, type IsoRange } from "@/lib/jalali"
import { toLatinDigits } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { L } from "../copy"
import { LIST_QUERY_KEY, matchesSearch } from "../order-figures"
import { DateRangePopover } from "./date-range-popover"
import { MobileFilterSheet, MobileFilterChips } from "./mobile-filters"
import { OrderCards } from "./order-cards"
import { OrdersTable, PAGE_SIZE } from "./orders-table"
import { EmptyState, ErrorState, LoadingState } from "./states"
import { useCurrency } from "@/lib/use-currency"

const ISO_RE = /^\d{4}-\d{2}-\d{2}$/
/** Store time zone (accounting-rules header) until /settings answers. */
const DEFAULT_TZ = "Asia/Tehran"

export type Filters = {
  status: string
  channel: string
  range: IsoRange
  q: string
  page: number
}

function readFilters(params: URLSearchParams, defaultRange: IsoRange): Filters {
  const status = params.get("status") ?? ""
  const channel = params.get("channel") ?? ""
  const from = params.get("from") ?? ""
  const to = params.get("to") ?? ""
  const page = Number(params.get("page") ?? 1)
  const validRange = ISO_RE.test(from) && ISO_RE.test(to) && from <= to
  return {
    status: (ORDER_STATUS_IDS as readonly string[]).includes(status) ? status : "",
    channel: (CHANNEL_IDS as readonly string[]).includes(channel) ? channel : "",
    range: validRange ? { from, to } : defaultRange,
    q: params.get("q") ?? "",
    page: Number.isInteger(page) && page > 0 ? page : 1,
  }
}

type Load =
  | { status: "loading" }
  | { status: "error"; code: string }
  | { status: "ready"; rows: OrderListItem[]; storeHasOrders: boolean }

function errorCode(error: unknown): string {
  return error instanceof ApiError && error.status > 0 ? `ORDERS_${error.status}` : "NET_TIMEOUT"
}

export function OrdersList() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()
  const [sheetOpen, setSheetOpen] = React.useState(false)
  const [today] = React.useState(() => new Date())
  const defaultRange = React.useMemo(() => jalaliMonthRange(today), [today])
  const filters = readFilters(new URLSearchParams(params.toString()), defaultRange)

  // Filters live in the URL so they survive opening an order and coming back.
  const setFilters = React.useCallback(
    (patch: Partial<Filters>) => {
      const next = { ...readFilters(new URLSearchParams(window.location.search), defaultRange), page: 1, ...patch }
      const qs = new URLSearchParams()
      if (next.status) qs.set("status", next.status)
      if (next.channel) qs.set("channel", next.channel)
      if (next.range.from !== defaultRange.from || next.range.to !== defaultRange.to) {
        qs.set("from", next.range.from)
        qs.set("to", next.range.to)
      }
      if (next.q) qs.set("q", next.q)
      if (next.page > 1) qs.set("page", String(next.page))
      const query = qs.toString()
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false })
    },
    [router, pathname, defaultRange]
  )

  const clearFilters = () => {
    setSearch("")
    router.replace(pathname, { scroll: false })
  }

  const queryString = params.toString()
  React.useEffect(() => {
    try {
      window.sessionStorage.setItem(LIST_QUERY_KEY, queryString)
    } catch {
      // Storage unavailable (private mode): the crumb just opens the plain list.
    }
  }, [queryString])

  // Search is typed locally and pushed to the URL after a short pause.
  const [search, setSearch] = React.useState(filters.q)
  React.useEffect(() => {
    if (search === filters.q) return
    const t = window.setTimeout(() => setFilters({ q: search }), 250)
    return () => window.clearTimeout(t)
  }, [search, filters.q, setFilters])

  const [timeZone, setTimeZone] = React.useState(DEFAULT_TZ)
  React.useEffect(() => {
    getSettings().then(
      (s) => setTimeZone(s.timezone || DEFAULT_TZ),
      () => {}
    )
  }, [])

  // Status, search and paging are client-side over the rows for the current
  // channel + date range (GET /orders has no search or paging).
  const [load, setLoad] = React.useState<Load>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)
  const fetchKey = `${filters.channel}|${filters.range.from}|${filters.range.to}|${attempt}`
  const [loadedKey, setLoadedKey] = React.useState<string | null>(null)
  if (loadedKey !== fetchKey && load.status !== "loading") {
    // A new fetch is starting: show the loading state instead of stale rows.
    setLoad({ status: "loading" })
  }
  React.useEffect(() => {
    let cancelled = false
    const [channel, from, to] = fetchKey.split("|")
    ;(async () => {
      try {
        const rows = await listOrders({ channel: channel || null, start_date: from, end_date: to })
        // An empty result needs one unfiltered look to tell "no orders at
        // all" (empty state) from "nothing matches" (filtered-empty).
        const storeHasOrders = rows.length > 0 || (await listOrders()).length > 0
        if (!cancelled) setLoad({ status: "ready", rows, storeHasOrders })
      } catch (error) {
        if (!cancelled) setLoad({ status: "error", code: errorCode(error) })
      } finally {
        if (!cancelled) setLoadedKey(fetchKey)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [fetchKey])

  const rows = React.useMemo(() => (load.status === "ready" ? load.rows : []), [load])
  const counts = React.useMemo(() => {
    const c: Record<string, number> = { "": rows.length }
    for (const r of rows) c[r.status] = (c[r.status] ?? 0) + 1
    return c
  }, [rows])
  const visible = rows.filter(
    (r) => (!filters.status || r.status === filters.status) && matchesSearch(r, filters.q, toLatinDigits)
  )
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const page = Math.min(filters.page, pageCount)

  const month = wholeMonthLabel(filters.range)
  const subtitle =
    load.status === "ready" && !load.storeHasOrders
      ? L.emptySubtitle
      : load.status === "ready"
        ? month
          ? L.subtitleMonth(rows.length, month)
          : L.subtitleRange(rows.length)
        : null

  const storeEmpty = load.status === "ready" && !load.storeHasOrders
  const retry = () => setAttempt((a) => a + 1)

  if (mobile) {
    return (
      <div className="flex flex-col gap-3 pb-24">
        {!storeEmpty && (
          <>
            <SearchBox value={search} onChange={setSearch} mobile />
            <MobileFilterChips filters={filters} defaultRange={defaultRange} onOpen={() => setSheetOpen(true)} />
          </>
        )}
        {load.status === "loading" && <LoadingState mobile />}
        {load.status === "error" && <ErrorState code={load.code} onRetry={retry} mobile />}
        {storeEmpty && <EmptyState mobile />}
        {load.status === "ready" && !storeEmpty && (
          <OrderCards
            rows={visible}
            timeZone={timeZone}
            resetKey={`${filters.status}|${filters.q}|${fetchKey}`}
            onClearFilters={clearFilters}
          />
        )}
        <MobileFilterSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          filters={filters}
          defaultRange={defaultRange}
          today={today}
          onApply={(patch) => setFilters(patch)}
          onClear={clearFilters}
        />
        {!storeEmpty && (
          <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
            <Link href="/sales/new" className={btnClass("primary", "lg", "w-full")}>
              <Plus className="size-[18px]" />
              {L.newSale}
            </Link>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[13px] text-text-3">{subtitle}</span>
        {!storeEmpty && (
          <Link href="/sales/new" className={btnClass("primary")}>
            <Plus className="size-4" />
            {L.newSale}
          </Link>
        )}
      </div>

      {!storeEmpty && (
        <div role="search" aria-label={L.filterAria} className="flex flex-wrap items-center gap-2.5">
          <SearchBox value={search} onChange={setSearch} />
          <ChannelFilter value={filters.channel} onChange={(channel) => setFilters({ channel })} />
          <DateRangePopover value={filters.range} onApply={(range) => setFilters({ range })} />
          <Btn variant="ghost" size="sm" onClick={clearFilters}>
            <X className="size-3.5" />
            {L.clearFilters}
          </Btn>
        </div>
      )}

      {load.status === "loading" && <LoadingState mobile={false} />}
      {load.status === "error" && <ErrorState code={load.code} onRetry={retry} mobile={false} />}
      {storeEmpty && <EmptyState mobile={false} />}
      {load.status === "ready" && !storeEmpty && (
        <OrdersTable
          rows={visible}
          counts={counts}
          status={filters.status}
          page={page}
          pageCount={pageCount}
          timeZone={timeZone}
          onStatus={(status) => setFilters({ status })}
          onPage={(p) => setFilters({ page: p })}
          onClearFilters={clearFilters}
        />
      )}
    </div>
  )
}

function SearchBox({
  value,
  onChange,
  mobile,
}: {
  value: string
  onChange: (v: string) => void
  mobile?: boolean
}) {
  return (
    <div className={cn("relative flex items-center", mobile ? "w-full" : "w-[300px]")}>
      <Search className="pointer-events-none absolute start-3 size-4 text-text-3" aria-hidden />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={L.searchPlaceholder}
        aria-label={mobile ? L.searchAriaMobile : L.searchAria}
        className={cn(
          "w-full rounded-lg border border-border-strong bg-card ps-[38px] pe-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
          mobile ? "h-11" : "h-10"
        )}
      />
    </div>
  )
}

function ChannelFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const label = value ? CHANNELS[value as keyof typeof CHANNELS].name : L.allChannels
  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-10 cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
        >
          <span className="text-text-3">{L.channelLabel}</span>
          <span className="font-bold">{label}</span>
          <ChevronDown className="size-3.5 text-text-3" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          <DropdownMenuRadioItem value="">{L.allChannels}</DropdownMenuRadioItem>
          {CHANNEL_IDS.map((id) => (
            <DropdownMenuRadioItem key={id} value={id}>
              {CHANNELS[id].name}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

