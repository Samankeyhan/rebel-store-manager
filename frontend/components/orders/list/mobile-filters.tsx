"use client"

import * as React from "react"
import { Check, X } from "lucide-react"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { JalaliDatePicker } from "@/components/jalali-date-picker"
import { ORDER_STATUS_IDS, ORDER_STATUSES, badgeBase, statusName } from "@/components/common/status"
import { CHANNEL_IDS, CHANNELS } from "@/components/record-sale/copy"
import { Btn } from "@/components/record-sale/primitives"
import { presetRange, wholeMonthLabel, type IsoRange } from "@/lib/jalali"
import { toPersianDigits } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { L } from "../copy"
import { rangeLabel } from "./date-range-popover"
import type { Filters } from "./orders-list"

type DateMode = "last7" | "thisMonth" | "custom"

function activeCount(filters: Filters, defaultRange: IsoRange): number {
  let n = 0
  if (filters.status) n++
  if (filters.channel) n++
  if (filters.range.from !== defaultRange.from || filters.range.to !== defaultRange.to) n++
  return n
}

const chipBase =
  "inline-flex h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-full border border-border-strong bg-card px-3 text-[13px] font-medium whitespace-nowrap outline-none focus-visible:ring-3 focus-visible:ring-ring/30"

/**
 * The chip row under the search box. Scrolls horizontally (the design's row
 * is overflow:hidden and clips its last chip); every chip opens the sheet.
 */
export function MobileFilterChips({
  filters,
  defaultRange,
  onOpen,
}: {
  filters: Filters
  defaultRange: IsoRange
  onOpen: () => void
}) {
  const count = activeCount(filters, defaultRange)
  return (
    <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
      <button type="button" onClick={onOpen} className={cn(chipBase, count > 0 && "border-heading")}>
        {L.filtersChip}
        {count > 0 && (
          <span className="rounded-full bg-primary px-1.5 text-[11px] text-white tabular-nums">
            {toPersianDigits(count)}
          </span>
        )}
      </button>
      <button type="button" onClick={onOpen} className={cn(chipBase, "tabular-nums")}>
        {wholeMonthLabel(filters.range) ?? rangeLabel(filters.range)}
      </button>
      <button type="button" onClick={onOpen} className={chipBase}>
        {filters.status ? statusName(filters.status) : L.allStatuses}
      </button>
      <button type="button" onClick={onOpen} className={chipBase}>
        {filters.channel ? CHANNELS[filters.channel as keyof typeof CHANNELS].name : L.allChannels}
      </button>
    </div>
  )
}

/**
 * Bottom filter sheet (design 03 «OrdersMobile-Filters»). Single-select
 * status and channel, matching the desktop tabs/dropdown. Edits are a draft
 * until the apply button; a close button is added (the design had none).
 */
export function MobileFilterSheet({
  open,
  onOpenChange,
  filters,
  defaultRange,
  today,
  onApply,
  onClear,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  filters: Filters
  defaultRange: IsoRange
  today: Date
  onApply: (patch: Partial<Filters>) => void
  onClear: () => void
}) {
  const [status, setStatus] = React.useState(filters.status)
  const [channel, setChannel] = React.useState(filters.channel)
  const [range, setRange] = React.useState<IsoRange>(filters.range)
  const [mode, setMode] = React.useState<DateMode>("thisMonth")

  const modeOf = (r: IsoRange): DateMode => {
    const last7 = presetRange("last7", today)
    if (r.from === last7.from && r.to === last7.to) return "last7"
    if (r.from === defaultRange.from && r.to === defaultRange.to) return "thisMonth"
    return "custom"
  }

  // Each time the sheet opens, seed the draft from the current filters.
  const [seededFor, setSeededFor] = React.useState(false)
  if (open && !seededFor) {
    setSeededFor(true)
    setStatus(filters.status)
    setChannel(filters.channel)
    setRange(filters.range)
    setMode(modeOf(filters.range))
  } else if (!open && seededFor) {
    setSeededFor(false)
  }

  const pickMode = (m: DateMode) => {
    setMode(m)
    if (m === "last7") setRange(presetRange("last7", today))
    if (m === "thisMonth") setRange(defaultRange)
  }

  const statusRing: Record<string, string> = {
    DRAFT: "ring-text-3",
    PENDING: "ring-warn",
    PAID: "ring-info",
    COMPLETED: "ring-profit",
    CANCELLED: "ring-cancel-bg",
    REFUNDED: "ring-violet",
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        className="max-h-[90vh] gap-3.5 overflow-y-auto rounded-t-[18px] bg-card px-4 pb-5"
      >
        <div className="mx-auto mt-2 h-1 w-10 rounded bg-border-strong" aria-hidden />
        <div className="flex items-center justify-between">
          <SheetTitle className="text-base font-bold text-heading">{L.sheetTitle}</SheetTitle>
          <SheetDescription className="sr-only">{L.filterAria}</SheetDescription>
          <span className="flex items-center gap-1">
            <Btn
              variant="ghost"
              size="sm"
              onClick={() => {
                onClear()
                onOpenChange(false)
              }}
            >
              {L.sheetClear}
            </Btn>
            <Btn variant="ghost" className="size-11 px-0" aria-label={L.close} onClick={() => onOpenChange(false)}>
              <X className="size-4" />
            </Btn>
          </span>
        </div>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-[13px] font-semibold">{L.sheetStatus}</legend>
          <div className="flex flex-wrap gap-2">
            {ORDER_STATUS_IDS.map((id) => {
              const on = status === id
              return (
                <button
                  key={id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setStatus(on ? "" : id)}
                  className={cn(
                    badgeBase,
                    ORDER_STATUSES[id].badge,
                    "h-9 cursor-pointer px-3",
                    on && cn("ring-2", statusRing[id])
                  )}
                >
                  {ORDER_STATUSES[id].name}
                  {on && <Check className="size-3" aria-hidden />}
                </button>
              )
            })}
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-[13px] font-semibold">{L.sheetChannel}</legend>
          <div className="flex flex-wrap gap-2">
            {CHANNEL_IDS.map((id) => {
              const on = channel === id
              return (
                <button
                  key={id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setChannel(on ? "" : id)}
                  className={cn(
                    "inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-md border border-border bg-card px-3 text-xs font-medium text-text-2",
                    on && "border-heading ring-2 ring-heading/40"
                  )}
                >
                  <span className={cn("size-2 rounded-[2px]", CHANNELS[id].square)} aria-hidden />
                  {CHANNELS[id].name}
                  {on && <Check className="size-3" aria-hidden />}
                </button>
              )
            })}
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-[13px] font-semibold">{L.sheetDate}</legend>
          <div className="grid grid-cols-3 gap-0.5 rounded-[10px] border border-border bg-surface-2 p-[3px]">
            {(
              [
                ["last7", L.segLast7],
                ["thisMonth", L.segThisMonth],
                ["custom", L.segCustom],
              ] as const
            ).map(([m, label]) => (
              <button
                key={m}
                type="button"
                aria-pressed={mode === m}
                onClick={() => pickMode(m)}
                className={cn(
                  "h-10 cursor-pointer rounded-[7px] text-[13px] font-semibold text-text-2",
                  mode === m && "bg-card text-heading shadow-[0_4px_14px_rgba(18,22,38,.08)]"
                )}
              >
                {label}
              </button>
            ))}
          </div>
          {mode === "custom" && (
            <div className="grid grid-cols-2 gap-2">
              <JalaliDatePicker
                value={range.from}
                onChange={(v) => v && setRange((r) => ({ from: v, to: v > r.to ? v : r.to }))}
                className="h-11 w-full"
                placeholder={L.sheetFrom}
              />
              <JalaliDatePicker
                value={range.to}
                onChange={(v) => v && setRange((r) => ({ from: v < r.from ? v : r.from, to: v }))}
                className="h-11 w-full"
                placeholder={L.sheetTo}
              />
            </div>
          )}
        </fieldset>

        <Btn
          variant="primary"
          size="lg"
          className="w-full"
          onClick={() => {
            onApply({ status, channel, range })
            onOpenChange(false)
          }}
        >
          {L.sheetApply}
        </Btn>
      </SheetContent>
    </Sheet>
  )
}
