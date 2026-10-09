"use client"

import * as React from "react"
import { CalendarDays, Check, ChevronDown } from "lucide-react"
import { subMonths } from "date-fns-jalali"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Btn } from "@/components/record-sale/primitives"
import { cn } from "@/lib/utils"
import {
  dateToISO,
  formatJalali,
  isoToDate,
  jalaliYear,
  presetRange,
  rangeDays,
  type IsoRange,
  type RangePreset,
} from "@/lib/jalali"
import { L } from "../copy"

const PRESETS: { id: RangePreset; label: (today: Date) => string }[] = [
  { id: "today", label: () => L.presetToday },
  { id: "yesterday", label: () => L.presetYesterday },
  { id: "last7", label: () => L.presetLast7 },
  { id: "last30", label: () => L.presetLast30 },
  { id: "thisMonth", label: () => L.presetThisMonth },
  { id: "lastMonth", label: () => L.presetLastMonth },
  { id: "thisYear", label: (today) => L.presetYear(jalaliYear(today)) },
]

const short = (iso: string) => formatJalali(iso, "yyyy/MM/dd")

export function rangeLabel(range: IsoRange): string {
  return L.dateValue(short(range.from), short(range.to))
}

/** Which preset (if any) a range equals, for highlighting. */
function matchingPreset(range: IsoRange, today: Date): RangePreset | null {
  for (const p of PRESETS) {
    const r = presetRange(p.id, today)
    if (r.from === range.from && r.to === range.to) return p.id
  }
  return null
}

/**
 * Desktop date filter (design 03 «Orders-DateRange»): presets on the inline
 * start, two Jalali months, and a footer that states the range and its
 * inclusive length. The selection is a draft until «اعمال».
 */
export function DateRangePopover({
  value,
  onApply,
  triggerText,
}: {
  value: IsoRange
  onApply: (range: IsoRange) => void
  /** Shown on the button instead of `value` (e.g. «از ابتدا» when no range applies). */
  triggerText?: string
}) {
  const [open, setOpen] = React.useState(false)
  const [draft, setDraft] = React.useState<{ from: string; to: string | null }>(value)
  const [custom, setCustom] = React.useState(false)
  // Read on the client only (static export): "today" must not be build time.
  const [today] = React.useState(() => new Date())

  const openChange = (next: boolean) => {
    if (next) {
      setDraft(value)
      setCustom(false)
    }
    setOpen(next)
  }

  const resolved: IsoRange = { from: draft.from, to: draft.to ?? draft.from }
  const active = custom ? null : matchingPreset(resolved, today)

  return (
    <Popover open={open} onOpenChange={openChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-haspopup="dialog"
          className={cn(
            "flex h-10 cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
            open && "ring-3 ring-ring/30"
          )}
        >
          <CalendarDays className="size-4 text-text-3" aria-hidden />
          <span className="text-text-3">{L.dateLabel}</span>
          <span className="font-bold tabular-nums">{triggerText ?? rangeLabel(value)}</span>
          <ChevronDown className="size-3.5 text-text-3" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent
        role="dialog"
        aria-label={L.dateDialogAria}
        align="start"
        className="w-auto max-w-[calc(100vw-32px)] flex-row gap-0 rounded-[10px] border border-border bg-card p-0 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)] ring-0"
      >
        <div className="flex w-[150px] shrink-0 flex-col gap-0.5 border-e border-border p-2">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => {
                setCustom(false)
                setDraft(presetRange(p.id, today))
              }}
              className={cn(
                "flex h-9 cursor-pointer items-center justify-between rounded-md px-2.5 text-start text-[13.5px] hover:bg-surface-2",
                active === p.id && "bg-surface-2 font-bold text-primary"
              )}
            >
              {p.label(today)}
              {active === p.id && <Check className="size-3.5" aria-hidden />}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setCustom(true)}
            className={cn(
              "flex h-9 cursor-pointer items-center justify-between rounded-md px-2.5 text-start text-[13.5px] hover:bg-surface-2",
              (custom || active === null) && "bg-surface-2 font-bold text-primary"
            )}
          >
            {L.presetCustom}
            {(custom || active === null) && <Check className="size-3.5" aria-hidden />}
          </button>
        </div>
        <div className="flex flex-col">
          <div className="px-4 py-3">
            <Calendar
              calendar="persian"
              mode="range"
              numberOfMonths={2}
              showOutsideDays={false}
              defaultMonth={subMonths(isoToDate(value.to), 1)}
              selected={{ from: isoToDate(draft.from), to: draft.to ? isoToDate(draft.to) : undefined }}
              disabled={{ after: today }}
              onSelect={(range, day) => {
                setCustom(true)
                // Start a fresh range when one is already complete.
                if (draft.to) {
                  setDraft({ from: dateToISO(day), to: null })
                  return
                }
                if (!range?.from) return
                setDraft({
                  from: dateToISO(range.from),
                  to: range.to ? dateToISO(range.to) : null,
                })
              }}
            />
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3 text-[13px]">
            <span>
              <span className="text-text-3">{L.rangeFrom} </span>
              <b className="tabular-nums">{short(resolved.from)}</b>
              <span className="text-text-3"> {L.rangeTo} </span>
              <b className="tabular-nums">{short(resolved.to)}</b>{" "}
              <span className="text-text-3">{L.rangeDays(rangeDays(resolved))}</span>
            </span>
            <span className="flex gap-2">
              <Btn variant="ghost" size="sm" onClick={() => setOpen(false)}>
                {L.cancel}
              </Btn>
              <Btn
                variant="primary"
                size="sm"
                onClick={() => {
                  onApply(resolved)
                  setOpen(false)
                }}
              >
                {L.apply}
              </Btn>
            </span>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
