"use client"

import * as React from "react"
import { ChevronDown, Search } from "lucide-react"
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover"
import { categoryPath } from "@/lib/category-path"
import { cn } from "@/lib/utils"
import { Money } from "@/components/common/money"
import { T, type Channel } from "./copy"
import type { LineView } from "./derive"
import { StockPill } from "./primitives"
import { channelPrice, type Product } from "./state"

/** Folds Arabic ي/ك into Persian ی/ک and lowercases, for search. */
function norm(s: string): string {
  return s.replace(/ي/g, "ی").replace(/ك/g, "ک").toLowerCase().trim()
}

function rowSub(p: Product): { text: string; className: string } {
  if (p.made_to_order) return { text: T.madeToOrder, className: "text-text-3" }
  if (p.unit_cost == null) return { text: T.pickerNoCost, className: "font-bold text-loss" }
  return { text: categoryPath(p), className: "text-text-3" }
}

function rowStock(p: Product): { text: string; tone: "neutral" | "out" } {
  if (p.current_stock === 0) {
    return p.made_to_order ? { text: T.madeToOrder, tone: "neutral" } : { text: T.outOfStock, tone: "out" }
  }
  return { text: T.pickerStockUnits(p.current_stock), tone: "neutral" }
}

/**
 * The product select + its combobox popover (design §2 "Product picker").
 * Search by name or category; ↑/↓ move, Enter picks, Esc closes.
 * Out-of-stock rows stay selectable (V2 then decides).
 */
export function ProductPicker({
  view,
  products,
  channel,
  open,
  onOpenChange,
  onPick,
  mobile,
}: {
  view: LineView
  products: Product[]
  channel: Channel
  open: boolean
  onOpenChange: (open: boolean) => void
  onPick: (p: Product) => void
  mobile?: boolean
}) {
  const [query, setQuery] = React.useState("")
  const [highlight, setHighlight] = React.useState(0)
  const listId = React.useId()
  const wholesale = channel === "WHOLESALE"
  const { product } = view

  const q = norm(query)
  const items = q
    ? products.filter((p) => norm(p.name).includes(q) || norm(categoryPath(p)).includes(q))
    : products

  const setOpen = (next: boolean) => {
    if (next) {
      setQuery("")
      setHighlight(0)
    }
    onOpenChange(next)
  }

  const pick = (p: Product) => {
    onPick(p)
    onOpenChange(false)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setHighlight((h) => Math.min(h + 1, items.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setHighlight((h) => Math.max(h - 1, 0))
    } else if (e.key === "Enter") {
      e.preventDefault()
      const p = items[highlight]
      if (p) pick(p)
    }
  }

  const priceNote = wholesale ? T.priceWholesale : T.priceRetail

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <button
          type="button"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label={T.pickProduct}
          onClick={() => setOpen(!open)}
          className={cn(
            "flex w-full min-w-0 cursor-pointer items-center justify-between gap-2 rounded-lg border border-border-strong bg-card px-3 text-start text-sm text-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
            mobile ? "h-12" : "h-10",
            view.selectError && "border-loss ring-3 ring-loss-soft"
          )}
        >
          <span className="flex min-w-0 flex-col leading-[1.3]">
            <span className={cn("truncate", product ? "font-bold" : "text-text-3")}>
              {product ? product.name : T.pickProduct}
            </span>
            {mobile && product && (
              <span className="truncate text-xs text-text-3">
                {view.meta} · {view.line.priceEdited ? T.priceManual(view.defaultPrice) : priceNote}
              </span>
            )}
          </span>
          <span className="flex shrink-0 items-center gap-1.5">
            {view.stockPill && <StockPill {...view.stockPill} />}
            {!mobile && <ChevronDown className="size-3.5 text-text-3" aria-hidden />}
          </span>
        </button>
      </PopoverAnchor>
      <PopoverContent
        align="start"
        sideOffset={4}
        className="w-[min(440px,calc(100vw-32px))] gap-0 rounded-[10px] border border-border bg-card p-2 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)] ring-0"
        onOpenAutoFocus={(e) => {
          // Focus the search field rather than the first focusable.
          e.preventDefault()
          ;(e.currentTarget as HTMLElement).querySelector("input")?.focus()
        }}
      >
        <div className="relative mb-1.5 flex items-center">
          <Search className="pointer-events-none absolute start-3 size-4 text-text-3" aria-hidden />
          <input
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={items[highlight] ? `${listId}-${items[highlight].id}` : undefined}
            aria-label={T.pickerSearchAria}
            placeholder={T.pickerSearchPlaceholder}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setHighlight(0)
            }}
            onKeyDown={onKeyDown}
            className="h-10 w-full rounded-lg border border-heading bg-card ps-[38px] pe-3 text-sm outline-none ring-3 ring-ring/30 placeholder:text-text-3"
          />
        </div>
        <div className="grid grid-cols-[minmax(0,1fr)_96px_96px] gap-2 px-2.5 py-1 text-xs font-bold text-text-3">
          <span>{T.colProduct}</span>
          <span>{T.pickerPriceCol(wholesale)}</span>
          <span>{T.pickerStockCol}</span>
        </div>
        <div id={listId} role="listbox" aria-label={T.pickerListAria} className="max-h-[min(360px,50vh)] overflow-y-auto">
          {items.map((p, i) => {
            const sub = rowSub(p)
            return (
              <button
                key={p.id}
                id={`${listId}-${p.id}`}
                type="button"
                role="option"
                aria-selected={i === highlight}
                tabIndex={-1}
                onMouseEnter={() => setHighlight(i)}
                onClick={() => pick(p)}
                className={cn(
                  "grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_96px_96px] items-center gap-2 rounded-md px-2.5 py-2 text-start text-[13.5px]",
                  i === highlight && "bg-surface-2"
                )}
              >
                <span className="flex min-w-0 flex-col leading-[1.35]">
                  <span className="truncate font-bold">{p.name}</span>
                  <span className={cn("text-xs", sub.className)}>{sub.text}</span>
                </span>
                <Money value={channelPrice(p, channel)} className="text-[13px]" />
                <span>
                  <StockPill {...rowStock(p)} />
                </span>
              </button>
            )
          })}
          {items.length === 0 && (
            <div className="px-2.5 py-4 text-center text-[13px] text-text-3">{T.pickerNoResult(query.trim())}</div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
