/**
 * The dashboard's reporting period, kept in the URL as ?from=&to=
 * (Gregorian "YYYY-MM-DD", whole local days, both ends inclusive). No
 * parameters = this month. A preset is "selected" when the URL range equals
 * it; anything else is a custom range.
 *
 * "Today" is the store's calendar day (settings.timezone), not the
 * browser's: lib/jalali's utcToLocal does the zone conversion with Intl.
 */

import { isoToDate, presetRange, utcToLocal, type IsoRange } from "@/lib/jalali"
import { readUrlRange, writeUrlRange } from "@/lib/url-range"

export const DEFAULT_TZ = "Asia/Tehran"

export const PRESET_KINDS = ["today", "last7", "thisMonth", "lastMonth"] as const
export type PresetKind = (typeof PRESET_KINDS)[number]
export type PeriodKind = PresetKind | "custom"
export type Period = { kind: PeriodKind; range: IsoRange }

/** The store's calendar day for `now`, as "YYYY-MM-DD". */
export function storeToday(now: Date, timeZone: string): string {
  const stamp = now.toISOString().slice(0, 19).replace("T", " ")
  return (utcToLocal(stamp, timeZone) ?? utcToLocal(stamp, DEFAULT_TZ))!.iso
}

/**
 * Preset ranges relative to the store's today: «امروز» = today only,
 * «۷ روز اخیر» = today and the 6 days before it, and the Jalali months.
 */
export function presets(todayIso: string): Record<PresetKind, IsoRange> {
  const today = isoToDate(todayIso)
  return {
    today: presetRange("today", today),
    last7: presetRange("last7", today),
    thisMonth: presetRange("thisMonth", today),
    lastMonth: presetRange("lastMonth", today),
  }
}

export function readPeriod(params: URLSearchParams, todayIso: string): Period {
  const p = presets(todayIso)
  const range = readUrlRange(params, p.thisMonth)
  const kind = PRESET_KINDS.find((k) => p[k].from === range.from && p[k].to === range.to) ?? "custom"
  return { kind, range }
}

/** The query string for a range: empty for the default (this month). */
export function periodQuery(range: IsoRange, todayIso: string): string {
  return writeUrlRange(new URLSearchParams(), range, presets(todayIso).thisMonth).toString()
}
