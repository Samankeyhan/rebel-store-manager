"use client"

import * as React from "react"
import { ChevronDown, Search } from "lucide-react"
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover"
import { StockPill } from "@/components/record-sale/primitives"
import { cn } from "@/lib/utils"

export type PickerItem = {
  id: number
  name: string
  /** Second line in the list (category, type…). */
  sub?: string
  pill?: { text: string; tone: "neutral" | "out" }
}

/** Folds Arabic ي/ك into Persian ی/ک and lowercases, for search. */
function norm(s: string): string {
  return s.replace(/ي/g, "ی").replace(/ك/g, "ک").toLowerCase().trim()
}

/**
 * A `.select`-styled trigger with a searchable list (the record-sale product
 * picker's pattern, generic): search by name or sub-line; ↑/↓ move, Enter
 * picks, Esc closes.
 */
export function ItemPicker({
  id,
  items,
  value,
  onPick,
  placeholder,
  searchLabel,
  emptyText,
  noMatchText,
  mobile,
  error,
  disabled,
}: {
  id?: string
  items: PickerItem[]
  value: number | null
  onPick: (id: number) => void
  placeholder: string
  searchLabel: string
  emptyText: string
  noMatchText: (q: string) => string
  mobile?: boolean
  error?: boolean
  disabled?: boolean
}) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState("")
  const [highlight, setHighlight] = React.useState(0)
  const listId = React.useId()
  const selected = items.find((i) => i.id === value) ?? null

  const q = norm(query)
  const rows = q ? items.filter((i) => norm(i.name).includes(q) || norm(i.sub ?? "").includes(q)) : items

  const pick = (item: PickerItem) => {
    onPick(item.id)
    setOpen(false)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setHighlight((h) => Math.min(h + 1, rows.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setHighlight((h) => Math.max(h - 1, 0))
    } else if (e.key === "Enter") {
      e.preventDefault()
      if (rows[highlight]) pick(rows[highlight])
    }
  }

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (o) {
          setQuery("")
          setHighlight(0)
        }
      }}
    >
      <PopoverAnchor asChild>
        <button
          id={id}
          type="button"
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className={cn(
            "flex w-full min-w-0 cursor-pointer items-center justify-between gap-2 rounded-lg border border-border-strong bg-card px-3 text-start text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50",
            mobile ? "h-12" : "h-10",
            error && "border-loss ring-3 ring-loss-soft"
          )}
        >
          <span className={cn("min-w-0 truncate", selected ? "font-bold" : "text-text-3")}>
            {selected ? selected.name : placeholder}
          </span>
          <span className="flex shrink-0 items-center gap-2">
            {selected?.pill && <StockPill {...selected.pill} />}
            <ChevronDown className="size-3.5 text-text-3" aria-hidden />
          </span>
        </button>
      </PopoverAnchor>
      <PopoverContent align="start" className="w-(--radix-popover-trigger-width) min-w-[300px] p-0" onKeyDown={onKeyDown}>
        <div className="relative flex items-center border-b border-border">
          <Search className="pointer-events-none absolute start-3 size-4 text-text-3" aria-hidden />
          <input
            autoFocus
            role="combobox"
            aria-label={searchLabel}
            aria-controls={listId}
            aria-expanded
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setHighlight(0)
            }}
            className="h-11 w-full bg-transparent ps-9 pe-3 text-sm outline-none"
          />
        </div>
        <ul id={listId} role="listbox" className="max-h-72 overflow-y-auto p-1">
          {rows.length === 0 && (
            <li className="px-3 py-6 text-center text-[13px] text-text-3">{items.length === 0 ? emptyText : noMatchText(query)}</li>
          )}
          {rows.map((item, index) => (
            <li
              key={item.id}
              role="option"
              aria-selected={item.id === value}
              onMouseEnter={() => setHighlight(index)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(item)}
              className={cn(
                "flex cursor-pointer items-center justify-between gap-3 rounded-md px-3 py-2",
                index === highlight && "bg-surface-2",
                item.id === value && "font-bold"
              )}
            >
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-sm">{item.name}</span>
                {item.sub && <span className="truncate text-xs text-text-3">{item.sub}</span>}
              </span>
              {item.pill && <StockPill {...item.pill} />}
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  )
}
