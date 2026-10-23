/**
 * The default period of the orders list and the dashboard: the last 30 days,
 * today and the 29 days before it (the store's day, lib/store-day.ts). A
 * default is written as no URL parameters, so a link without parameters means
 * "last 30 days". Other report screens keep their own default (report-period.ts).
 * Dependency-free so `npm test` covers it.
 */

import { isoToDate, presetRange, type IsoRange } from "./jalali.ts"
import { readUrlRange, writeUrlRange } from "./url-range.ts"

/** Today and the 29 days before it. */
export function last30Range(todayIso: string): IsoRange {
  return presetRange("last30", isoToDate(todayIso))
}

/** The dashboard's presets, in the order of its segment. */
export const DASHBOARD_PRESET_KINDS = ["today", "last7", "last30", "thisMonth", "lastMonth"] as const
export type DashboardPresetKind = (typeof DASHBOARD_PRESET_KINDS)[number]

export function dashboardPresets(todayIso: string): Record<DashboardPresetKind, IsoRange> {
  const today = isoToDate(todayIso)
  return {
    today: presetRange("today", today),
    last7: presetRange("last7", today),
    last30: presetRange("last30", today),
    thisMonth: presetRange("thisMonth", today),
    lastMonth: presetRange("lastMonth", today),
  }
}

/** The range in the URL (valid from & to), else the last 30 days; plus the preset it equals, if any. */
export function readDefaultedRange(
  params: URLSearchParams,
  todayIso: string
): { kind: DashboardPresetKind | "custom"; range: IsoRange } {
  const presets = dashboardPresets(todayIso)
  const range = readUrlRange(params, presets.last30)
  const kind = DASHBOARD_PRESET_KINDS.find((k) => presets[k].from === range.from && presets[k].to === range.to)
  return { kind: kind ?? "custom", range }
}

/** The query string for a range: empty for the default (last 30 days). */
export function defaultedRangeQuery(range: IsoRange, todayIso: string): string {
  return writeUrlRange(new URLSearchParams(), range, last30Range(todayIso)).toString()
}
