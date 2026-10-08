"use client"

import * as React from "react"
import Link from "next/link"
import { ChevronLeft, CircleCheck } from "lucide-react"
import { badgeBase } from "@/components/common/status"
import type { Catalog, Material, Product } from "@/lib/api"
import { formatQuantity, toPersianDigits } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { unitLabel } from "@/components/products/figures"
import { D } from "./copy"
import { CardEmpty, CardError, CardLoading, DashCard } from "./parts"
import type { Loader } from "./use-dashboard-data"

const SHOWN = 5

type Tab = "products" | "materials"
type Row = { id: number; name: string; meta: string | null; low: boolean; href: string | null }

/*
 * Products have no minimum stock: their tab lists what is OUT of stock.
 * Materials come from GET /materials/low-stock (db/materials.py: active STOCK
 * at stock 0, or at or below its own min_stock), already most urgent first;
 * nothing here re-decides what is low.
 */
export function outOfStockProducts(products: Product[]): Product[] {
  // Made-to-order products are manufactured at sale time: 0 stock is normal.
  return products.filter((p) => p.is_active === 1 && p.made_to_order === 0 && p.current_stock === 0)
}

function materialRow(m: Material): Row {
  const stock = m.current_stock ?? 0
  const unit = unitLabel(m.unit)
  return {
    id: m.id,
    name: m.name,
    meta: m.min_stock != null ? D.stockOfMin(formatQuantity(stock), formatQuantity(m.min_stock), unit) : categoryOf(m),
    low: stock > 0,
    href: `/products?tab=materials&material=${m.id}`,
  }
}

const categoryOf = (x: { category_name?: string | null; parent_category_name?: string | null }) =>
  x.category_name ? (x.parent_category_name ? `${x.parent_category_name} / ${x.category_name}` : x.category_name) : null

export function StockCard({
  catalog,
  lowStock,
  mobile,
}: {
  catalog: Loader<Catalog>
  lowStock: Loader<Material[]>
  mobile: boolean
}) {
  const [tab, setTab] = React.useState<Tab>("products")
  const id = "dash-stock"

  if (catalog.status !== "ready" || lowStock.status !== "ready") {
    const failed = catalog.status === "error" ? catalog : lowStock.status === "error" ? lowStock : null
    const retry = () => {
      if (catalog.status === "error") catalog.retry()
      if (lowStock.status === "error") lowStock.retry()
    }
    return (
      <DashCard id={id} title={D.stockTitle} className="lg:w-[400px] lg:shrink-0">
        {failed ? (
          <CardError title={D.stockErrorTitle} code={failed.code} onRetry={retry} mobile={mobile} />
        ) : (
          <CardLoading rows={4} />
        )}
      </DashCard>
    )
  }

  const lists: Record<Tab, Row[]> = {
    products: outOfStockProducts(catalog.data.products).map((p) => ({
      id: p.id,
      name: p.name,
      meta: categoryOf(p),
      low: false,
      href: null,
    })),
    materials: lowStock.data.map(materialRow),
  }
  const total = lists.products.length + lists.materials.length

  if (total === 0) {
    return (
      <DashCard id={id} title={D.stockTitle} className="lg:w-[400px] lg:shrink-0">
        <CardEmpty
          icon={CircleCheck}
          tone="profit"
          title={D.stockEmptyTitle}
          body={D.stockEmptyBody}
          className="grow justify-center"
        />
      </DashCard>
    )
  }

  const rows = lists[tab]
  const tabs: [Tab, string][] = [
    ["products", D.stockTabProducts],
    ["materials", D.stockTabMaterials],
  ]

  return (
    <DashCard
      id={id}
      title={D.stockTitle}
      headerRule={false}
      aside={<span className={cn(badgeBase, "bg-loss-soft text-loss")}>{D.stockBadge(total)}</span>}
      className="lg:w-[400px] lg:shrink-0"
    >
      <div role="tablist" aria-label={D.stockTabsAria} className="flex gap-1 border-b border-border px-3 md:px-4">
        {tabs.map(([t, label]) => {
          const on = tab === t
          return (
            <button
              key={t}
              type="button"
              role="tab"
              id={`dash-stock-tab-${t}`}
              aria-selected={on}
              aria-controls="dash-stock-panel"
              onClick={() => setTab(t)}
              className={cn(
                "-mb-px inline-flex cursor-pointer items-center gap-1.5 border-b-2 border-transparent px-3 text-[13.5px] font-semibold text-text-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                mobile ? "h-11" : "h-10",
                on && "border-primary text-heading"
              )}
            >
              {label}
              <span
                className={cn(
                  "inline-flex h-[18px] min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] tabular-nums",
                  on ? "bg-red-soft text-primary" : "bg-surface-3 text-text-2"
                )}
              >
                {toPersianDigits(lists[t].length)}
              </span>
            </button>
          )
        })}
      </div>
      <div
        id="dash-stock-panel"
        role="tabpanel"
        aria-labelledby={`dash-stock-tab-${tab}`}
        className="flex grow flex-col px-4 pt-1.5 pb-3 md:px-5"
      >
        {rows.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-text-3">{D.stockEmptyTab[tab]}</p>
        ) : (
          <ul>
            {rows.slice(0, SHOWN).map((r) => {
              const content = (
                <>
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-[13.5px] font-semibold">{r.name}</span>
                    {r.meta && <span className="truncate text-xs text-text-3">{r.meta}</span>}
                  </span>
                  <span
                    className={cn(
                      "inline-flex h-6 shrink-0 items-center rounded-md px-2 text-xs font-semibold",
                      r.low ? "bg-warn-soft text-warn" : "bg-loss-soft text-loss"
                    )}
                  >
                    {r.low ? D.stockLow : D.stockOut}
                  </span>
                </>
              )
              const rowClass = "flex items-center justify-between gap-3 py-3"
              return (
                <li key={r.id} className="border-b border-border last:border-b-0">
                  {r.href ? (
                    <Link
                      href={r.href}
                      className={cn(
                        rowClass,
                        "-mx-2 rounded-md px-2 outline-none hover:bg-surface-2 focus-visible:ring-3 focus-visible:ring-ring/30",
                        mobile && "min-h-11"
                      )}
                    >
                      {content}
                    </Link>
                  ) : (
                    <div className={rowClass}>{content}</div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
        {rows.length > SHOWN && <p className="pt-1 text-xs text-text-3">{D.stockMore(rows.length - SHOWN)}</p>}
      </div>
      <div className="px-4 pb-4 md:px-5">
        <Link
          href={`/products?tab=${tab}`}
          className="inline-flex items-center gap-1 text-[13px] font-semibold text-heading outline-none hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/30"
        >
          {D.stockAll}
          <ChevronLeft className="size-4" aria-hidden />
        </Link>
      </div>
    </DashCard>
  )
}
