"use client"

import * as React from "react"
import { ChevronDown, Search, X } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Btn } from "@/components/record-sale/primitives"
import { isFiltering, type CategoryOption, type ProductFilter } from "@/lib/production-filter"
import { cn } from "@/lib/utils"
import { R } from "./copy"

/**
 * The search box (by product name) and the category dropdown of the recipe and history tabs, with the result
 * count and «پاک کردن فیلترها». The filter lives in the URL (?q=, ?cat=, owned by the page): the box is typed
 * locally and pushed after a short pause, like the orders list. `children` are the tab's own controls (the
 * history's product and date filters, the recipes' «no recipe» toggle).
 */
export function ProductFilterBar({
  filter,
  onChange,
  options,
  count,
  mobile,
  children,
}: {
  filter: ProductFilter
  onChange: (next: ProductFilter) => void
  options: CategoryOption[]
  /** «۳ از ۴۱ محصول», or null to leave it out. */
  count: string | null
  mobile: boolean
  children?: React.ReactNode
}) {
  const [text, setText] = React.useState(filter.q)
  // The URL changed from outside (cleared, another tab's link): follow it.
  const [seen, setSeen] = React.useState(filter.q)
  if (seen !== filter.q) {
    setSeen(filter.q)
    setText(filter.q)
  }
  React.useEffect(() => {
    if (text === filter.q) return
    const t = window.setTimeout(() => onChange({ ...filter, q: text }), 250)
    return () => window.clearTimeout(t)
  }, [text, filter, onChange])

  const category = options.find((o) => o.id === filter.categoryId)
  return (
    <div role="search" aria-label={R.filterAria} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className={cn("relative flex items-center", mobile ? "w-full" : "w-[260px]")}>
          <Search className="pointer-events-none absolute start-3 size-4 text-text-3" aria-hidden />
          <input
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={R.searchPlaceholder}
            aria-label={R.searchAria}
            className={cn(
              "w-full rounded-lg border border-border-strong bg-card ps-[38px] pe-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
              mobile ? "h-11" : "h-10"
            )}
          />
        </div>
        <DropdownMenu dir="rtl">
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className={cn(
                "flex cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                mobile ? "h-11" : "h-10 max-w-[280px]"
              )}
            >
              <span className="shrink-0 text-text-3">{R.filterCategory}</span>
              <span className="truncate font-bold">{category ? category.label : R.filterAllCategories}</span>
              <ChevronDown className="size-3.5 shrink-0 text-text-3" aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="max-h-80 w-64 overflow-y-auto">
            <DropdownMenuRadioGroup
              value={filter.categoryId == null ? "" : String(filter.categoryId)}
              onValueChange={(v) => onChange({ ...filter, categoryId: v ? Number(v) : null })}
            >
              <DropdownMenuRadioItem value="">{R.filterAllCategories}</DropdownMenuRadioItem>
              {options.map((o) => (
                <DropdownMenuRadioItem key={o.id} value={String(o.id)}>
                  {o.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
        {children}
        {isFiltering(filter) && (
          <Btn
            variant="ghost"
            size="sm"
            onClick={() => {
              setText("")
              onChange({ q: "", categoryId: null })
            }}
          >
            <X className="size-3.5" />
            {R.clearFilters}
          </Btn>
        )}
      </div>
      {count && (
        <span className="text-xs text-text-3" aria-live="polite">
          {count}
        </span>
      )}
    </div>
  )
}
