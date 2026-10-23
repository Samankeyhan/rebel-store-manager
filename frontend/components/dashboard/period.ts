/**
 * The dashboard's reporting period, kept in the URL as ?from=&to=
 * (Gregorian "YYYY-MM-DD", whole local days, both ends inclusive). No
 * parameters = the last 30 days (lib/default-range.ts). A preset is "selected"
 * when the URL range equals it; anything else is a custom range.
 *
 * "Today" is the store's calendar day (settings.timezone), not the
 * browser's: lib/store-day's storeToday does the zone conversion with Intl.
 */

import type { IsoRange } from "@/lib/jalali"
import {
  DASHBOARD_PRESET_KINDS,
  dashboardPresets,
  defaultedRangeQuery,
  readDefaultedRange,
  type DashboardPresetKind,
} from "@/lib/default-range"

// The store's day helper lives in lib/store-day.ts (Record Sale uses it too).
export { DEFAULT_TZ, storeToday } from "@/lib/store-day"

export const PRESET_KINDS = DASHBOARD_PRESET_KINDS
export type PresetKind = DashboardPresetKind
export type PeriodKind = PresetKind | "custom"
export type Period = { kind: PeriodKind; range: IsoRange }

/**
 * Preset ranges relative to the store's today: «امروز» = today only,
 * «۷ روز اخیر» / «۳۰ روز اخیر» = today and the 6 / 29 days before it, and the Jalali months.
 */
export const presets = dashboardPresets

export function readPeriod(params: URLSearchParams, todayIso: string): Period {
  return readDefaultedRange(params, todayIso)
}

/** The query string for a range: empty for the default (last 30 days). */
export function periodQuery(range: IsoRange, todayIso: string): string {
  return defaultedRangeQuery(range, todayIso)
}
