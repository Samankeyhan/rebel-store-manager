"use client"

import * as React from "react"
import {
  getSettings,
  listMaterialPurchases,
  listMaterials,
  listProductPurchases,
  listProducts,
  listSuppliers,
  type Material,
  type MaterialPurchase,
  type Product,
  type ProductPurchase,
  type Supplier,
} from "@/lib/api"
import type { IsoRange } from "@/lib/jalali"

export type PurchaseKind = "material" | "product"
export type TypeFilter = "all" | PurchaseKind

/** One history row, material or product purchase. */
export type PurchaseRow = {
  key: string
  kind: PurchaseKind
  id: number
  itemId: number
  itemName: string
  date: string
  supplierName: string | null
  quantity: number
  totalPaid: number
  unitCost: number
}

export function toRow(kind: PurchaseKind, p: MaterialPurchase | ProductPurchase): PurchaseRow {
  return {
    key: `${kind}-${p.id}`,
    kind,
    id: p.id,
    itemId: kind === "material" ? (p as MaterialPurchase).material_id : (p as ProductPurchase).product_id,
    itemName: kind === "material" ? (p as MaterialPurchase).material_name : (p as ProductPurchase).product_name,
    date: p.purchase_date,
    supplierName: p.supplier_name,
    quantity: p.quantity_bought,
    totalPaid: p.total_paid,
    unitCost: p.unit_cost,
  }
}

/** Newest first, like each endpoint: date, then id. */
function byNewest(a: PurchaseRow, b: PurchaseRow): number {
  if (a.date !== b.date) return a.date < b.date ? 1 : -1
  return b.id - a.id
}

type Catalog =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; materials: Material[]; products: Product[]; suppliers: Supplier[] }

type List = { status: "loading" } | { status: "error" } | { status: "ready"; rows: PurchaseRow[] }

const DEFAULT_TZ = "Asia/Tehran"

async function fetchRows(type: TypeFilter, supplierId: number | null, range: IsoRange | null): Promise<PurchaseRow[]> {
  const f = { supplierId, from: range?.from, to: range?.to }
  const [materials, products] = await Promise.all([
    type === "product" ? Promise.resolve([]) : listMaterialPurchases(f),
    type === "material" ? Promise.resolve([]) : listProductPurchases(f),
  ])
  return [...materials.map((p) => toRow("material", p)), ...products.map((p) => toRow("product", p))].sort(byNewest)
}

/**
 * Items, suppliers and the purchase history for the current filters. The
 * history is re-fetched when the type / supplier / range change (both
 * endpoints filter server-side); search stays client-side.
 */
export function usePurchasesData(filters: { type: TypeFilter; supplierId: number | null; range: IsoRange | null }) {
  const [catalog, setCatalog] = React.useState<Catalog>({ status: "loading" })
  const [list, setList] = React.useState<List>({ status: "loading" })
  const [timeZone, setTimeZone] = React.useState(DEFAULT_TZ)
  const [attempt, setAttempt] = React.useState(0)
  const [listAttempt, setListAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([listMaterials(), listProducts(), listSuppliers()]).then(
      ([materials, products, suppliers]) =>
        !cancelled && setCatalog({ status: "ready", materials, products, suppliers }),
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

  const { type, supplierId, range } = filters
  const from = range?.from ?? null
  const to = range?.to ?? null
  React.useEffect(() => {
    let cancelled = false
    fetchRows(type, supplierId, from && to ? { from, to } : null).then(
      (rows) => !cancelled && setList({ status: "ready", rows }),
      () => !cancelled && setList({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [type, supplierId, from, to, attempt, listAttempt])

  const reload = React.useCallback(() => {
    setCatalog({ status: "loading" })
    setList({ status: "loading" })
    setAttempt((a) => a + 1)
  }, [])

  /** After a save: the list, quietly (no loading flash). */
  const refreshList = React.useCallback(() => setListAttempt((a) => a + 1), [])

  const refreshSuppliers = React.useCallback(async () => {
    const suppliers = await listSuppliers()
    setCatalog((c) => (c.status === "ready" ? { ...c, suppliers } : c))
  }, [])

  /** Replace one item after a purchase so the next preview starts from its new stock/average. */
  const replaceItem = React.useCallback((kind: PurchaseKind, item: Material | Product) => {
    setCatalog((c) => {
      if (c.status !== "ready") return c
      return kind === "material"
        ? { ...c, materials: c.materials.map((m) => (m.id === item.id ? (item as Material) : m)) }
        : { ...c, products: c.products.map((p) => (p.id === item.id ? (item as Product) : p)) }
    })
  }, [])

  return { catalog, list, timeZone, reload, refreshList, refreshSuppliers, replaceItem }
}
