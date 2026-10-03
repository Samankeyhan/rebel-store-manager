/**
 * The dashboard's reporting period: the current Jalali month by default,
 * the previous month, or any range, kept in the URL as ?from=&to=
 * (Gregorian "YYYY-MM-DD", whole local days, both ends inclusive).
 *
 * "Today" is the store's calendar day (settings.timezone), not the
 * browser's: lib/jalali's utcToLocal does the zone conversion with Intl.
 */

import { isoToDate, jalaliMonthRange, presetRange, utcToLocal, type IsoRange } from "@/lib/jalali"

export const DEFAULT_TZ = "Asia/Tehran"
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/

export type PeriodKind = "thisMonth" | "lastMonth" | "custom"
export type Period = { kind: PeriodKind; range: IsoRange }

/** The store's calendar day for `now`, as "YYYY-MM-DD". */
export function storeToday(now: Date, timeZone: string): string {
  const stamp = now.toISOString().slice(0, 19).replace("T", " ")
  return (utcToLocal(stamp, timeZone) ?? utcToLocal(stamp, DEFAULT_TZ))!.iso
}

export function presets(todayIso: string): Record<Exclude<PeriodKind, "custom">, IsoRange> {
  const today = isoToDate(todayIso)
  return { thisMonth: jalaliMonthRange(today), lastMonth: presetRange("lastMonth", today) }
}

const same = (a: IsoRange, b: IsoRange) => a.from === b.from && a.to === b.to

/** Reads ?from=&to=; anything missing or malformed falls back to this month. */
export function readPeriod(params: URLSearchParams, todayIso: string): Period {
  const p = presets(todayIso)
  const from = params.get("from")
  const to = params.get("to")
  const valid = from && to && ISO_DAY.test(from) && ISO_DAY.test(to) && from <= to
  const range = valid ? { from, to } : p.thisMonth
  if (same(range, p.thisMonth)) return { kind: "thisMonth", range }
  if (same(range, p.lastMonth)) return { kind: "lastMonth", range }
  return { kind: "custom", range }
}

/** The query string for a range: empty for the default (this month). */
export function periodQuery(range: IsoRange, todayIso: string): string {
  if (same(range, presets(todayIso).thisMonth)) return ""
  return new URLSearchParams({ from: range.from, to: range.to }).toString()
}
