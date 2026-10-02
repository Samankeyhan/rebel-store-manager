"use client"

import * as React from "react"
import {
  getSettings,
  listAdjustments,
  listMaterials,
  listProducts,
  type Adjustment,
  type AdjustmentFilters,
  type Material,
  type Product,
} from "@/lib/api"
import type { ItemKind } from "./figures"

type Catalog = { status: "loading" } | { status: "error" } | { status: "ready"; products: Product[]; materials: Material[] }
type List = { status: "loading" } | { status: "error" } | { status: "ready"; rows: Adjustment[] }

const DEFAULT_TZ = "Asia/Tehran"

/**
 * Products, materials and the adjustment history for the current server-side
 * filters (item type, reason, date range). A single-item filter is applied
 * by the caller: GET /adjustments has no item_id parameter.
 */
export function useAdjustmentsData(filters: AdjustmentFilters) {
  const [catalog, setCatalog] = React.useState<Catalog>({ status: "loading" })
  const [list, setList] = React.useState<List>({ status: "loading" })
  const [timeZone, setTimeZone] = React.useState(DEFAULT_TZ)
  const [attempt, setAttempt] = React.useState(0)
  const [listAttempt, setListAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([listProducts(), listMaterials()]).then(
      ([products, materials]) => !cancelled && setCatalog({ status: "ready", products, materials }),
      () => !cancelled && setCatalog({ status: "error" })
    )
    getSettings().then(
      (s) => !cancelled && setTimeZone(s.timezone || DEFAULT_TZ),
      () => {}
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const { itemType = null, reason = null, from = null, to = null } = filters
  React.useEffect(() => {
    let cancelled = false
    listAdjustments({ itemType, reason, from, to }).then(
      (rows) => !cancelled && setList({ status: "ready", rows }),
      () => !cancelled && setList({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [itemType, reason, from, to, attempt, listAttempt])

  const reload = React.useCallback(() => {
    setCatalog({ status: "loading" })
    setList({ status: "loading" })
    setAttempt((a) => a + 1)
  }, [])

  /** After a save: the history, quietly (no loading flash). */
  const refreshList = React.useCallback(() => setListAttempt((a) => a + 1), [])

  /** Products and materials again, quietly — after an item turned out gone or inactive. */
  const refreshCatalog = React.useCallback(async () => {
    const [products, materials] = await Promise.all([listProducts(), listMaterials()])
    setCatalog({ status: "ready", products, materials })
  }, [])

  /** Replace one item so the next preview starts from its new stock / cost. */
  const replaceItem = React.useCallback((kind: ItemKind, item: Product | Material) => {
    setCatalog((c) => {
      if (c.status !== "ready") return c
      return kind === "material"
        ? { ...c, materials: c.materials.map((m) => (m.id === item.id ? (item as Material) : m)) }
        : { ...c, products: c.products.map((p) => (p.id === item.id ? (item as Product) : p)) }
    })
  }, [])

  return { catalog, list, timeZone, reload, refreshList, refreshCatalog, replaceItem }
}
