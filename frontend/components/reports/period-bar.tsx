"use client"

import * as React from "react"
import { DateRangePopover } from "@/components/orders/list/date-range-popover"
import { JalaliDateRangePicker, type IsoDateRange } from "@/components/jalali-date-picker"
import { PERIOD_PRESETS, periodPresets, presetPeriod, type PeriodKind, type ReportPeriod } from "@/lib/report-period"
import { cn } from "@/lib/utils"
import { R } from "./copy"

const LABELS: Record<PeriodKind, string> = {
  thisMonth: R.presetThisMonth,
  lastMonth: R.presetLastMonth,
  thisYear: R.presetThisYear,
  last30: R.presetLast30,
  all: R.presetAll,
  custom: R.presetCustom,
}

/**
 * The dashboard's `.seg` that scrolls sideways on a phone. `value` null = no
 * option selected (a custom range on desktop, where the range button stands
 * in for «بازه دلخواه»).
 */
function PeriodSegment({
  value,
  options,
  onChange,
  mobile,
}: {
  value: PeriodKind | null
  options: readonly PeriodKind[]
  onChange: (k: PeriodKind) => void
  mobile: boolean
}) {
  return (
    <div className={cn(mobile && "-mx-4 overflow-x-auto px-4 [scrollbar-width:none]")}>
      <div
        role="radiogroup"
        aria-label={R.periodAria}
        className="flex w-max gap-0.5 rounded-[10px] border border-border bg-surface-2 p-[3px]"
      >
        {options.map((k) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={value === k}
            onClick={() => onChange(k)}
            className={cn(
              "shrink-0 cursor-pointer rounded-[7px] px-3 text-[13px] font-semibold whitespace-nowrap text-text-2 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
              mobile ? "h-10" : "h-[32px]",
              value === k && "bg-card text-heading shadow-[0_4px_14px_rgba(18,22,38,.08)]"
            )}
          >
            {LABELS[k]}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * The period every report uses: presets (this / last Jalali month, this
 * Jalali year, the last 30 days, all time) and a custom range. The parent
 * keeps it in the URL; `period` is null until the store's today is known.
 */
export function PeriodBar({
  period,
  today,
  mobile,
  onChange,
}: {
  period: ReportPeriod | null
  today: string | null
  mobile: boolean
  onChange: (period: ReportPeriod) => void
}) {
  // Mobile «بازه دلخواه»: a draft until both ends are picked.
  const [customOpen, setCustomOpen] = React.useState(false)
  const [draft, setDraft] = React.useState<IsoDateRange>({ from: null, to: null })

  if (!period || !today) return <div className={mobile ? "h-[46px]" : "h-10"} aria-hidden />

  const pick = (k: PeriodKind) => {
    if (k === "custom") return
    onChange(presetPeriod(k, today))
  }
  const fallbackRange = period.range ?? periodPresets(today).thisMonth

  if (mobile) {
    const kind = customOpen ? "custom" : period.kind
    return (
      <div className="flex flex-col gap-2.5">
        <PeriodSegment
          value={kind}
          options={[...PERIOD_PRESETS, "custom"]}
          mobile
          onChange={(k) => {
            if (k === "custom") {
              setDraft(period.range ? { ...period.range } : { from: null, to: null })
              setCustomOpen(true)
              return
            }
            setCustomOpen(false)
            pick(k)
          }}
        />
        {kind === "custom" && (
          <JalaliDateRangePicker
            value={customOpen ? draft : (period.range ?? { from: null, to: null })}
            className="h-11 w-full"
            onChange={(r) => {
              setDraft(r)
              if (r.from && r.to) {
                setCustomOpen(false)
                onChange({ kind: "custom", range: { from: r.from, to: r.to } })
              }
            }}
          />
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <PeriodSegment
        value={period.kind === "custom" ? null : period.kind}
        options={PERIOD_PRESETS}
        mobile={false}
        onChange={pick}
      />
      <DateRangePopover
        value={fallbackRange}
        triggerText={period.range ? undefined : R.allTime}
        onApply={(range) => onChange({ kind: "custom", range })}
      />
    </div>
  )
}
