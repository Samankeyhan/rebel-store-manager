"use client"

/**
 * One independent load per dashboard card, so a failing request only blanks
 * its own card and each card has its own retry. Every figure is read from
 * the API as returned; nothing here adds up money.
 */

import * as React from "react"
import {
  ApiError,
  getCatalog,
  getChannelBreakdown,
  getPostageEstimate,
  getProfitAndLoss,
  getPurchasesSummary,
  getSettings,
  getShippingSummary,
  listLowStockMaterials,
  listOrders,
  type Catalog,
  type ChannelBreakdown,
  type Material,
  type OrderListItem,
  type PostageEstimate,
  type ProfitAndLoss,
  type PurchasesSummary,
  type ShippingSummary,
} from "@/lib/api"
import type { IsoRange } from "@/lib/jalali"
import { DEFAULT_TZ } from "./period"

export type Load<T> =
  | { status: "loading" }
  | { status: "error"; code: string }
  | { status: "ready"; data: T }

export type Loader<T> = Load<T> & { retry: () => void }

function errorCode(prefix: string, error: unknown): string {
  return error instanceof ApiError && error.status > 0 ? `${prefix}_${error.status}` : "NET_TIMEOUT"
}

/** Runs `fetcher` whenever `key` changes (null = wait), with a retry. */
function useLoad<T>(prefix: string, key: string | null, fetcher: () => Promise<T>): Loader<T> {
  const [attempt, setAttempt] = React.useState(0)
  const [state, setState] = React.useState<{ key: string; load: Load<T> } | null>(null)
  const fetchRef = React.useRef(fetcher)
  React.useEffect(() => {
    fetchRef.current = fetcher
  })
  const fullKey = key === null ? null : `${key}#${attempt}`

  React.useEffect(() => {
    if (fullKey === null) return
    let cancelled = false
    fetchRef.current().then(
      (data) => !cancelled && setState({ key: fullKey, load: { status: "ready", data } }),
      (error: unknown) =>
        !cancelled && setState({ key: fullKey, load: { status: "error", code: errorCode(prefix, error) } })
    )
    return () => {
      cancelled = true
    }
  }, [fullKey, prefix])

  const retry = React.useCallback(() => setAttempt((a) => a + 1), [])
  // A new key shows loading instead of the previous period's figures.
  const load: Load<T> = state && state.key === fullKey ? state.load : { status: "loading" }
  return { ...load, retry }
}

/** settings.timezone; falls back to the accounting-rules zone if /settings fails. */
export function useStoreTimeZone(): string | null {
  const [tz, setTz] = React.useState<string | null>(null)
  React.useEffect(() => {
    let cancelled = false
    getSettings().then(
      (s) => !cancelled && setTz(s.timezone || DEFAULT_TZ),
      () => !cancelled && setTz(DEFAULT_TZ)
    )
    return () => {
      cancelled = true
    }
  }, [])
  return tz
}

export type ShippingData = { summary: ShippingSummary; estimate: PostageEstimate | null }

export const RECENT_ORDERS = 8

export function useDashboardData(range: IsoRange | null) {
  const rangeKey = range ? `${range.from}|${range.to}` : null

  const pnl = useLoad<ProfitAndLoss>("REPORTS", rangeKey, () => getProfitAndLoss(range!))
  const channels = useLoad<ChannelBreakdown[]>("REPORTS", rangeKey, () => getChannelBreakdown(range!))
  const purchases = useLoad<PurchasesSummary>("REPORTS", rangeKey, () => getPurchasesSummary(range!))
  const shipping = useLoad<ShippingData>("REPORTS", rangeKey, async () => {
    const [summary, estimate] = await Promise.all([
      getShippingSummary(range!),
      // The estimate is a reference line only; the card still works without it.
      getPostageEstimate().catch(() => null),
    ])
    return { summary, estimate }
  })
  // GET /orders has no limit: the newest rows are the first ones returned
  // (order_date DESC, id DESC). Backend gap: a ?limit= parameter.
  const orders = useLoad<OrderListItem[]>("ORDERS", "all", () => listOrders())
  const catalog = useLoad<Catalog>("CATALOG", "all", () => getCatalog())
  // Low-stock materials, most urgent first (the rule and the order are db/'s).
  const lowStock = useLoad<Material[]>("MATERIALS", "all", () => listLowStockMaterials())

  return { pnl, channels, purchases, shipping, orders, catalog, lowStock }
}
