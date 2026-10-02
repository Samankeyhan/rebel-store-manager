"use client"

import * as React from "react"
import { ChevronDown, ClipboardList, Layers, SearchX } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { StateShell } from "@/components/common/screen-states"
import { DateRangePopover } from "@/components/orders/list/date-range-popover"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import type { ProductionBatchListItem } from "@/lib/api"
import { formatJalali, formatJalaliDateTime, utcToLocal, type IsoRange } from "@/lib/jalali"
import { formatMoney, formatNumber, toPersianDigits } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { BatchSheet } from "./batch-sheet"
import { R } from "./copy"
import { groupBySitting, sittingIndex, type SittingGroup } from "./group-sessions"
import type { Material } from "@/lib/api"

/**
 * سوابق تولید: newest first. One fetch of GET /production; the product and
 * date filters apply client-side (the list has no date filter). No total-cost
 * column — the list endpoint has no batch total; the detail sheet shows it.
 */
export function HistoryTab({
  batches,
  materials,
  timeZone,
  range,
  onRangeChange,
  defaultRange,
  mobile,
}: {
  batches: ProductionBatchListItem[]
  materials: Material[]
  timeZone: string
  range: IsoRange
  onRangeChange: (r: IsoRange) => void
  defaultRange: IsoRange
  mobile: boolean
}) {
  const [productFilter, setProductFilter] = React.useState("")
  const [openId, setOpenId] = React.useState<number | null>(null)
  // Sittings are expanded by default; this holds the ones the user collapsed.
  const [collapsed, setCollapsed] = React.useState<Set<string>>(new Set())
  // Sittings come from the full list, so filters can't split or merge them.
  const sittings = React.useMemo(() => sittingIndex(batches), [batches])

  const productsInHistory = React.useMemo(() => {
    const seen = new Map<number, string>()
    for (const b of batches) if (!seen.has(b.product_id)) seen.set(b.product_id, b.product_name)
    return [...seen].sort((a, b) => a[1].localeCompare(b[1], "fa"))
  }, [batches])

  const rows = batches.filter((b) => {
    if (productFilter && b.product_id !== Number(productFilter)) return false
    const day = utcToLocal(b.production_date, timeZone)?.iso
    return !day || (day >= range.from && day <= range.to)
  })
  const open = batches.find((b) => b.id === openId) ?? null
  const groups = groupBySitting(rows, sittings)
  const toggle = (key: string) =>
    setCollapsed((c) => {
      const next = new Set(c)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  if (batches.length === 0) {
    return <StateShell icon={ClipboardList} mobile={mobile} title={R.emptyTitle} body={mobile ? R.emptyBodyMobile : undefined} />
  }

  const productLabel = productFilter
    ? (productsInHistory.find(([id]) => id === Number(productFilter))?.[1] ?? R.filterAll)
    : R.filterAll

  const filters = (
    <div className="flex flex-wrap items-center gap-2.5">
      <DropdownMenu dir="rtl">
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="flex h-10 cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
          >
            <span className="text-text-3">{R.filterProduct}</span>
            <span className="font-bold">{productLabel}</span>
            <ChevronDown className="size-3.5 text-text-3" aria-hidden />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="max-h-80 w-60 overflow-y-auto">
          <DropdownMenuRadioGroup value={productFilter} onValueChange={setProductFilter}>
            <DropdownMenuRadioItem value="">{R.filterAll}</DropdownMenuRadioItem>
            {productsInHistory.map(([id, name]) => (
              <DropdownMenuRadioItem key={id} value={String(id)}>
                {name}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <DateRangePopover value={range} onApply={onRangeChange} />
    </div>
  )

  const clear = () => {
    setProductFilter("")
    onRangeChange(defaultRange)
  }

  let body: React.ReactNode
  if (rows.length === 0) {
    body = (
      <StateShell
        icon={SearchX}
        mobile={mobile}
        title={R.historyNoMatch}
        action={
          <Btn size="sm" className="mt-1" onClick={clear}>
            {R.clearFilters}
          </Btn>
        }
      />
    )
  } else if (mobile) {
    const card = (b: (typeof rows)[number]) => (
      <button
        key={b.id}
        type="button"
        onClick={() => setOpenId(b.id)}
        className={cn(cardClass, "flex flex-col gap-1.5 px-3.5 py-3 text-start outline-none focus-visible:ring-3 focus-visible:ring-ring/30")}
      >
        <span className="flex items-center justify-between gap-2">
          <span className="font-bold">{b.product_name}</span>
          <span className="text-sm tabular-nums">{R.qtyUnits(b.quantity_produced)}</span>
        </span>
        <span className="flex items-center justify-between gap-2 text-xs text-text-3">
          <span className="tabular-nums">{formatJalaliDateTime(b.production_date, timeZone)}</span>
          <span className="tabular-nums">
            {R.batchUnitCost}: <b className="text-foreground">{formatNumber(b.unit_cost)}</b>
          </span>
        </span>
        {b.notes && <span className="text-xs text-text-3">{b.notes}</span>}
      </button>
    )
    body = (
      <div className="flex flex-col gap-3">
        {groups.map((g) =>
          g.batches.length === 1 ? (
            card(g.batches[0])
          ) : (
            <div key={g.key} className="flex flex-col gap-2 rounded-2xl border border-border bg-surface-2 p-2">
              <SittingHeader group={g} timeZone={timeZone} open={!collapsed.has(g.key)} onToggle={() => toggle(g.key)} mobile />
              {!collapsed.has(g.key) && g.batches.map(card)}
            </div>
          )
        )}
      </div>
    )
  } else {
    const row = (b: (typeof rows)[number], inSitting: boolean) => (
      <tr
        key={b.id}
        tabIndex={0}
        onClick={() => setOpenId(b.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            setOpenId(b.id)
          }
        }}
        className="cursor-pointer outline-none hover:[&>td]:bg-surface-2 focus-visible:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
      >
        <td className={cn("text-text-3 tabular-nums", inSitting && "border-s-[3px] border-s-border-strong")}>
          {formatJalaliDateTime(b.production_date, timeZone)}
        </td>
        <td className="font-bold">{b.product_name}</td>
        <td className="text-end tabular-nums">{formatNumber(b.quantity_produced)}</td>
        <td className="text-end font-bold tabular-nums">{formatNumber(b.unit_cost)}</td>
        <td className="max-w-[320px] truncate text-text-3">{b.notes || "—"}</td>
      </tr>
    )
    body = (
      <>
        <section className={cn(cardClass, "overflow-hidden")}>
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0 text-[13.5px]">
              <thead>
                <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                  <th scope="col">{R.colDate}</th>
                  <th scope="col">{R.colProduct}</th>
                  <th scope="col" className="text-end!">
                    {R.colQty}
                  </th>
                  <th scope="col" className="text-end!">
                    {R.colUnitCost}
                  </th>
                  <th scope="col" className="w-full">
                    {R.colNote}
                  </th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => {
                  if (g.batches.length === 1) return row(g.batches[0], false)
                  const isOpen = !collapsed.has(g.key)
                  return (
                    <React.Fragment key={g.key}>
                      <tr className="[&>td]:border-b [&>td]:border-border [&>td]:bg-surface-2 [&>td]:p-0">
                        <td colSpan={5}>
                          <SittingHeader group={g} timeZone={timeZone} open={isOpen} onToggle={() => toggle(g.key)} />
                        </td>
                      </tr>
                      {isOpen && g.batches.map((b) => row(b, true))}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
        <p className="text-xs text-text-3">{R.historyFootnote}</p>
      </>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {filters}
      {body}
      <BatchSheet
        batch={open}
        materials={materials}
        timeZone={timeZone}
        mobile={mobile}
        onClose={() => setOpenId(null)}
      />
    </div>
  )
}

/**
 * Header of a sitting of 2+ batches: its day, how many runs, when they were
 * recorded, and the sum of their real totals — labelled as a sum of separate
 * runs, never as one production's cost. Toggles the rows below it.
 */
function SittingHeader({
  group,
  timeZone,
  open,
  onToggle,
  mobile,
}: {
  group: SittingGroup
  timeZone: string
  open: boolean
  onToggle: () => void
  mobile?: boolean
}) {
  const first = group.batches[0]
  const day = utcToLocal(first.production_date, timeZone)
  // When the sitting started: its earliest created_at (rows are newest first).
  const start = group.batches
    .map((b) => b.created_at)
    .filter((c): c is string => c != null)
    .sort()[0]
  const recorded = start ? utcToLocal(start, timeZone) : null
  const shown = group.batches.length
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-label={`${open ? R.sittingCollapse : R.sittingExpand}: ${R.sittingCount(group.sittingSize)}`}
      className={cn(
        "flex w-full cursor-pointer flex-wrap items-center justify-between gap-x-4 gap-y-1 text-start text-[13px] outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
        mobile ? "rounded-xl px-2 py-1.5" : "px-4 py-2.5 hover:bg-surface-3"
      )}
    >
      <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <Layers className="size-4 text-text-3" aria-hidden />
        <b className="tabular-nums">{day ? formatJalali(day.iso, "yyyy/MM/dd") : toPersianDigits(first.production_date)}</b>
        <span className="font-semibold">
          {shown === group.sittingSize ? R.sittingCount(shown) : R.sittingPartial(shown, group.sittingSize)}
        </span>
        {recorded && <span className="text-xs text-text-3 tabular-nums">{R.sittingRecorded(toPersianDigits(recorded.time))}</span>}
      </span>
      <span className="flex items-center gap-3">
        {group.total != null && (
          <span className="flex flex-col items-end leading-tight">
            <span className="text-xs text-text-3">
              {R.sittingTotal} <span className="hidden sm:inline">({R.sittingTotalCaption})</span>
            </span>
            <b className="tabular-nums">{formatMoney(group.total)}</b>
          </span>
        )}
        <ChevronDown className={cn("size-4 text-text-3 transition-transform", open && "rotate-180")} aria-hidden />
      </span>
    </button>
  )
}
