/**
 * The reports screen's period and tab, kept in the URL so a report can be
 * reloaded and shared:
 *   ?from=YYYY-MM-DD&to=YYYY-MM-DD   a range (Gregorian, whole local days,
 *                                    both ends inclusive, accounting-rules §1)
 *   ?period=all                      all time (no date bounds)
 *   (none)                           the current Jalali month
 *   ?tab=products|channels|shipping|payments|waste|expenses
 *                                    the report; none = the P&L
 * A preset is "selected" when the URL range equals it; any other range is
 * custom. "Today" is the store's day (lib/store-day's storeToday), passed in
 * as "YYYY-MM-DD". Dependency-light so `npm test` can run it.
 */

import { isoToDate, presetRange, type IsoRange } from "./jalali.ts"
import { readUrlRange, writeUrlRange } from "./url-range.ts"

/** The reports, in tab order; the first one is the default. */
export const REPORT_TAB_IDS = ["pnl", "products", "channels", "shipping", "payments", "waste", "expenses"] as const
export type ReportTab = (typeof REPORT_TAB_IDS)[number]

export const PERIOD_PRESETS = ["thisMonth", "lastMonth", "thisYear", "last30", "all"] as const
export type PeriodPreset = (typeof PERIOD_PRESETS)[number]
export type PeriodKind = PeriodPreset | "custom"
type RangePresetKind = Exclude<PeriodPreset, "all">

/** range null = all time. */
export type ReportPeriod = { kind: PeriodKind; range: IsoRange | null }

/**
 * Preset ranges relative to the store's today: the whole current and
 * previous Jalali months, the whole current Jalali year (1 Farvardin to the
 * last day of Esfand), and the last 30 days (today and the 29 before it).
 */
export function periodPresets(todayIso: string): Record<RangePresetKind, IsoRange> {
  const today = isoToDate(todayIso)
  return {
    thisMonth: presetRange("thisMonth", today),
    lastMonth: presetRange("lastMonth", today),
    thisYear: presetRange("thisYear", today),
    last30: presetRange("last30", today),
  }
}

/** The preset a period kind stands for, as a period. */
export function presetPeriod(kind: PeriodPreset, todayIso: string): ReportPeriod {
  if (kind === "all") return { kind, range: null }
  return { kind, range: periodPresets(todayIso)[kind] }
}

function isRealDay(iso: string): boolean {
  try {
    isoToDate(iso)
    return true
  } catch {
    return false
  }
}

export function readReportPeriod(params: URLSearchParams, todayIso: string): ReportPeriod {
  if (params.get("period") === "all") return { kind: "all", range: null }
  const p = periodPresets(todayIso)
  let range = readUrlRange(params, p.thisMonth)
  // The URL is hand-editable: a day that doesn't exist (2026-02-31) falls back too.
  if (!isRealDay(range.from) || !isRealDay(range.to)) range = p.thisMonth
  const kind =
    (Object.keys(p) as RangePresetKind[]).find((k) => p[k].from === range.from && p[k].to === range.to) ?? "custom"
  return { kind, range }
}

/** `params` with the period written in; the default (this month) writes nothing. */
export function writeReportPeriod(params: URLSearchParams, period: ReportPeriod, todayIso: string): URLSearchParams {
  const next = new URLSearchParams(params)
  next.delete("period")
  if (period.range === null) {
    next.delete("from")
    next.delete("to")
    next.set("period", "all")
    return next
  }
  return writeUrlRange(next, period.range, periodPresets(todayIso).thisMonth)
}

export function readReportTab(params: URLSearchParams): ReportTab {
  const t = params.get("tab")
  return (REPORT_TAB_IDS as readonly string[]).includes(t ?? "") ? (t as ReportTab) : REPORT_TAB_IDS[0]
}

/** `params` with the tab written in; the default tab writes nothing. */
export function writeReportTab(params: URLSearchParams, tab: ReportTab): URLSearchParams {
  const next = new URLSearchParams(params)
  if (tab === REPORT_TAB_IDS[0]) next.delete("tab")
  else next.set("tab", tab)
  return next
}

/**
 * The API's date bounds (start_date / end_date, inclusive local days; the
 * backend converts them in the store's time zone). All time sends neither.
 */
export function apiRange(period: ReportPeriod): { from?: string; to?: string } {
  return period.range ? { from: period.range.from, to: period.range.to } : {}
}

/** A stable key for "the same request": changes whenever the bounds do. */
export function periodKey(period: ReportPeriod): string {
  return period.range ? `${period.range.from}|${period.range.to}` : "all"
}
