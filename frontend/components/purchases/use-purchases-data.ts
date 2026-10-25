"use client"

import * as React from "react"
import {
  getSettings,
  listMaterials,
  listProducts,
  listPurchases,
  listSuppliers,
  type Material,
  type Product,
  type Purchase,
  type PurchaseLine,
  type Supplier,
} from "@/lib/api"
import type { IsoRange } from "@/lib/jalali"
import type { PaymentStatus } from "@/lib/payables"
import { apiItemType, type ItemKind, type ItemType, type TypeFilter } from "@/lib/purchase-lines"

export type { TypeFilter }

/** An item re-read from the server after a purchase. */
export type RefreshedItem = { kind: ItemKind; item: Material | Product }

/** One history row: a purchase invoice with its lines. */
export type PurchaseRow = {
  key: string
  id: number
  invoiceNumber: string | null
  date: string
  supplierName: string | null
  /** The lines in order (materials and services, then products). */
  lines: PurchaseLine[]
  itemNames: string[]
  types: ItemType[]
  /** From the API (db/purchases.py, db/supplier_payments.py): never computed here, except the search below. */
  total: number
  paymentStatus: PaymentStatus
  outstanding: number
  notes: string | null
}

export function toRow(p: Purchase): PurchaseRow {
  return {
    key: `purchase-${p.id}`,
    id: p.id,
    invoiceNumber: p.invoice_number,
    date: p.purchase_date,
    supplierName: p.supplier_name,
    lines: p.lines,
    itemNames: p.lines.map((l) => l.item_name),
    types: [...new Set(p.lines.map((l) => l.item_type))],
    total: p.total,
    paymentStatus: p.payment_status,
    outstanding: p.outstanding,
    notes: p.notes,
  }
}

type Catalog =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; materials: Material[]; products: Product[]; suppliers: Supplier[] }

type List = { status: "loading" } | { status: "error" } | { status: "ready"; rows: PurchaseRow[] }

const DEFAULT_TZ = "Asia/Tehran"

async function fetchRows(type: TypeFilter, supplierId: number | null, range: IsoRange | null): Promise<PurchaseRow[]> {
  const purchases = await listPurchases({ supplierId, from: range?.from, to: range?.to, itemType: apiItemType(type) })
  return purchases.map(toRow)
}

/**
 * Items, suppliers and the purchase history for the current filters. The
 * history is re-fetched when the type / supplier / range change (the
 * endpoint filters server-side); search stays client-side.
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

  /** Replace the items of a purchase's lines so the next preview starts from their new stock/average/price. */
  const replaceItems = React.useCallback((items: RefreshedItem[]) => {
    setCatalog((c) => {
      if (c.status !== "ready") return c
      const material = new Map(items.filter((i) => i.kind === "MATERIAL").map((i) => [i.item.id, i.item as Material]))
      const product = new Map(items.filter((i) => i.kind === "PRODUCT").map((i) => [i.item.id, i.item as Product]))
      return {
        ...c,
        materials: c.materials.map((m) => material.get(m.id) ?? m),
        products: c.products.map((p) => product.get(p.id) ?? p),
      }
    })
  }, [])

  return { catalog, list, timeZone, reload, refreshList, refreshSuppliers, replaceItems }
}
