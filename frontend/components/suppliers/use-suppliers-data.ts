"use client"

import * as React from "react"
import { getSettings, listMaterialPurchases, listProductPurchases, listSuppliers, type Supplier } from "@/lib/api"

export type SupplierStats = { count: number; last: string | null }

type List = { status: "loading" } | { status: "error" } | { status: "ready"; suppliers: Supplier[] }
/** null = the purchase lists failed to load; the columns show «—». */
type Stats = Map<number, SupplierStats> | null

const DEFAULT_TZ = "Asia/Tehran"

const byName = (a: Supplier, b: Supplier) => a.name.localeCompare(b.name, "fa")

/**
 * Suppliers (sorted by Persian collation — the API sorts by SQLite's binary
 * order) plus per-supplier purchase count and newest purchase date, from the
 * two purchase lists. No money is summed here.
 */
export function useSuppliersData() {
  const [list, setList] = React.useState<List>({ status: "loading" })
  const [stats, setStats] = React.useState<Stats>(new Map())
  const [timeZone, setTimeZone] = React.useState(DEFAULT_TZ)
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    listSuppliers().then(
      (suppliers) => !cancelled && setList({ status: "ready", suppliers: [...suppliers].sort(byName) }),
      () => !cancelled && setList({ status: "error" })
    )
    Promise.all([listMaterialPurchases(), listProductPurchases()]).then(
      ([materials, products]) => {
        if (cancelled) return
        const m = new Map<number, SupplierStats>()
        for (const p of [...materials, ...products]) {
          if (p.supplier_id == null) continue
          const s = m.get(p.supplier_id) ?? { count: 0, last: null }
          s.count += 1
          if (s.last == null || p.purchase_date > s.last) s.last = p.purchase_date
          m.set(p.supplier_id, s)
        }
        setStats(m)
      },
      () => !cancelled && setStats(null)
    )
    getSettings().then(
      (s) => !cancelled && setTimeZone(s.timezone || DEFAULT_TZ),
      () => {}
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const reload = React.useCallback(() => {
    setList({ status: "loading" })
    setAttempt((a) => a + 1)
  }, [])

  /** Insert or replace one supplier after a save. */
  const upsert = React.useCallback((s: Supplier) => {
    setList((l) =>
      l.status === "ready"
        ? { status: "ready", suppliers: [...l.suppliers.filter((x) => x.id !== s.id), s].sort(byName) }
        : l
    )
  }, [])

  return { list, stats, timeZone, reload, upsert }
}
