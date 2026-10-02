"use client"

import * as React from "react"
import Link from "next/link"
import { Ban, Lock, Pencil, RotateCcw } from "lucide-react"
import { Btn, StockPill, btnClass, cardClass } from "@/components/record-sale/primitives"
import type { Product } from "@/lib/api"
import { categoryLabel } from "@/lib/categories"
import { formatNumber } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { ActiveBadge, Chip, NoCostBadge } from "./badges"
import { P } from "./copy"
import { costState } from "./figures"

/** Zero stock is a warning for a normal product, but the usual state of a made-to-order one. */
function stockPill(p: Product, mobile = false) {
  if (p.current_stock === 0 && !p.made_to_order) return { text: P.outOfStock, tone: "out" as const }
  return {
    text: mobile ? P.stockPillMobile(p.current_stock) : P.stockUnits(p.current_stock),
    tone: "neutral" as const,
  }
}

/** «۱ محصول بدون بهای تمام‌شده — «X» …», computed from the rows. */
function MissingCostBanner({ missing }: { missing: Product[] }) {
  if (missing.length === 0) return null
  const one = missing.length === 1
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-3 rounded-[10px] border border-loss-border bg-loss-soft px-3.5 py-2.5 text-[13px] leading-[21px]"
    >
      <Lock className="size-[18px] shrink-0 text-loss" aria-hidden />
      <span className="min-w-0 grow">
        <b>{one ? P.bannerOne : P.bannerMany(missing.length)}</b>
        {one ? P.bannerOneRest(missing[0].name) : P.bannerManyRest}
      </span>
      {/* No endpoint sets a cost: it comes from a purchase or a production run. */}
      <span className="flex shrink-0 gap-2">
        <Link href="/purchases" className={btnClass("outline", "sm")}>
          {P.bannerPurchase}
        </Link>
        <Link href="/production" className={btnClass("ghost", "sm")}>
          {P.bannerProduction}
        </Link>
      </span>
    </div>
  )
}

/** Made-to-order cost text: the recipe estimate when known, else the plain note. */
export function fromRecipeText(p: Product, estimates: Record<number, number>): string {
  const estimate = estimates[p.id]
  return estimate == null ? P.fromRecipe : P.recipeEstimate(estimate)
}

function CostCell({ p, estimates }: { p: Product; estimates: Record<number, number> }) {
  const c = costState(p)
  if (c.kind === "known") return <span className="tabular-nums">{formatNumber(c.cost)}</span>
  if (c.kind === "fromRecipe") return <span className="text-xs text-text-3 tabular-nums">{fromRecipeText(p, estimates)}</span>
  return <NoCostBadge />
}

export function ProductsTab({
  rows,
  missingCost,
  mobile,
  onEdit,
  onDeactivate,
  onReactivate,
  estimates,
}: {
  rows: Product[]
  /** Visible active products that can't be sold for lack of a cost. */
  missingCost: Product[]
  mobile: boolean
  onEdit: (p: Product) => void
  onDeactivate: (p: Product) => void
  onReactivate: (p: Product) => void
  /** Recipe cost per unit for made-to-order products with no stock (an estimate). */
  estimates: Record<number, number>
}) {
  if (mobile) {
    return (
      <div className="flex flex-col gap-3">
        <MissingCostBanner missing={missingCost} />
        {rows.map((p) => {
          const c = costState(p)
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onEdit(p)}
              className={cn(
                cardClass,
                "flex flex-col gap-2 px-3.5 py-3 text-start outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                c.kind === "missing" && p.is_active === 1 && "border-loss-border",
                p.is_active !== 1 && "opacity-55"
              )}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="font-bold">{p.name}</span>
                <StockPill {...stockPill(p, true)} />
              </span>
              <span className="flex items-center justify-between gap-2 text-xs">
                <span className="flex gap-1.5">
                  <Chip>{categoryLabel(p.category)}</Chip>
                  {p.made_to_order === 1 && <Chip>{P.madeToOrder}</Chip>}
                </span>
                <span className="text-text-2 tabular-nums">{P.priceLine(p.retail_price, p.wholesale_price)}</span>
              </span>
              <span className="flex items-center justify-between gap-2 text-xs">
                <span
                  className={cn(
                    "tabular-nums",
                    c.kind === "missing" ? "font-bold text-loss" : "text-text-3"
                  )}
                >
                  {c.kind === "known" ? P.costLine(c.cost) : c.kind === "fromRecipe" ? fromRecipeText(p, estimates) : P.costLineMissing}
                </span>
                <ActiveBadge active={p.is_active === 1} />
              </span>
            </button>
          )
        })}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <MissingCostBanner missing={missingCost} />
      <section className={cn(cardClass, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col" className="w-full">
                  {P.colName}
                </th>
                <th scope="col">{P.colCategory}</th>
                <th scope="col">{P.colStock}</th>
                <th scope="col">{P.colCost}</th>
                <th scope="col">{P.colRetail}</th>
                <th scope="col">{P.colWholesale}</th>
                <th scope="col">{P.colStatus}</th>
                <th scope="col" className="w-[88px]">
                  <span className="sr-only">{P.colActions}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => {
                const active = p.is_active === 1
                const missing = active && costState(p).kind === "missing"
                return (
                  <tr
                    key={p.id}
                    className={cn(
                      "[&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap last:[&>td]:border-b-0",
                      missing ? "[&>td]:bg-loss-soft" : "hover:[&>td]:bg-surface-2",
                      !active && "opacity-55"
                    )}
                  >
                    <td>
                      <div className="flex flex-col gap-0.5 leading-tight">
                        <span className="font-bold">{p.name}</span>
                        {p.made_to_order === 1 && <span className="text-xs text-text-3">{P.madeToOrder}</span>}
                      </div>
                    </td>
                    <td>
                      <Chip>{categoryLabel(p.category)}</Chip>
                    </td>
                    <td>
                      <StockPill {...stockPill(p)} />
                    </td>
                    <td>
                      <CostCell p={p} estimates={estimates} />
                    </td>
                    <td className="font-bold tabular-nums">{formatNumber(p.retail_price)}</td>
                    <td className="tabular-nums">{formatNumber(p.wholesale_price)}</td>
                    <td>
                      <ActiveBadge active={active} />
                    </td>
                    <td>
                      <span className="flex gap-1">
                        <Btn variant="ghost" size="sm" className="size-8 px-0" aria-label={P.edit} onClick={() => onEdit(p)}>
                          <Pencil className="size-4" />
                        </Btn>
                        {active ? (
                          <Btn
                            variant="ghost"
                            size="sm"
                            className="size-8 px-0"
                            aria-label={P.deactivate}
                            onClick={() => onDeactivate(p)}
                          >
                            <Ban className="size-4" />
                          </Btn>
                        ) : (
                          <Btn
                            variant="ghost"
                            size="sm"
                            className="size-8 px-0"
                            aria-label={P.reactivate}
                            onClick={() => onReactivate(p)}
                          >
                            <RotateCcw className="size-4" />
                          </Btn>
                        )}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
      <p className="text-xs text-text-3">{P.productsFootnote}</p>
    </div>
  )
}
