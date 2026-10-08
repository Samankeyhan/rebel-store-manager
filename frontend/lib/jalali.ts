/**
 * Jalali (Solar Hijri) date helpers. EVERY date shown in the UI goes through
 * formatJalali, and every date input uses JalaliDatePicker.
 *
 * All values are date-only local dates as "YYYY-MM-DD" Gregorian strings —
 * exactly what the API accepts and returns. No timezone math happens here;
 * the backend owns that.
 *
 * Built on date-fns-jalali, the same library react-day-picker's Persian
 * calendar uses, so the picker and the formatting always agree.
 */

import {
  differenceInCalendarDays,
  endOfMonth,
  endOfYear,
  format,
  getDate,
  getMonth,
  getYear,
  isValid,
  newDate,
  startOfMonth,
  startOfYear,
  subDays,
  subMonths,
} from "date-fns-jalali"

import { toLatinDigits, toPersianDigits } from "./persian-numbers.ts"

export type JalaliDate = { year: number; month: number; day: number }

const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})$/

/** "2026-09-22" → local-midnight Date. Throws on a malformed string. */
export function isoToDate(iso: string): Date {
  const m = ISO_RE.exec(iso)
  if (!m) throw new Error(`Not a YYYY-MM-DD date: ${iso}`)
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  if (d.getMonth() !== Number(m[2]) - 1) throw new Error(`Invalid date: ${iso}`)
  return d
}

/** Local Date → "YYYY-MM-DD" (its local calendar day, no UTC shift). */
export function dateToISO(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

/** "2026-09-22" → { year: 1405, month: 6, day: 31 } (month is 1-based). */
export function toJalali(iso: string): JalaliDate {
  const d = isoToDate(iso)
  return { year: getYear(d), month: getMonth(d) + 1, day: getDate(d) }
}

/**
 * "2026-09-22" → "۳۱ شهریور ۱۴۰۵". `fmt` is a date-fns format string,
 * interpreted in the Jalali calendar.
 */
export function formatJalali(iso: string, fmt = "d MMMM yyyy"): string {
  return toPersianDigits(format(isoToDate(iso), fmt))
}

/**
 * Jalali "1405/06/31" (Persian or Latin digits, / or - separators)
 * → Gregorian "2026-09-22". Throws on an invalid date.
 */
export function toGregorianISO(jalali: string): string {
  const parts = toLatinDigits(jalali.trim()).split(/[/-]/).map(Number)
  if (parts.length !== 3 || parts.some((p) => !Number.isInteger(p))) {
    throw new Error(`Not a Jalali Y/M/D date: ${jalali}`)
  }
  const [year, month, day] = parts
  const d = newDate(year, month - 1, day)
  // newDate rolls over out-of-range days (e.g. 1405/07/31 → 1405/08/01).
  if (!isValid(d) || getMonth(d) !== month - 1 || getDate(d) !== day) {
    throw new Error(`Invalid Jalali date: ${jalali}`)
  }
  return dateToISO(d)
}

const UTC_STAMP_RE = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/

/**
 * A stored UTC moment ("YYYY-MM-DD HH:MM:SS", as the API returns order_date)
 * → its local calendar day and wall-clock time in `timeZone` (the store's
 * settings.timezone). Display only: the browser's Intl does the zone
 * conversion; nothing here does offset arithmetic. Returns null on a
 * malformed value.
 */
export function utcToLocal(
  utc: string,
  timeZone: string
): { iso: string; time: string } | null {
  const m = UTC_STAMP_RE.exec(utc)
  if (!m) return null
  const instant = new Date(
    Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] ?? 0))
  )
  let parts: Intl.DateTimeFormatPart[]
  try {
    parts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(instant)
  } catch {
    return null
  }
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ""
  return {
    iso: `${get("year")}-${get("month")}-${get("day")}`,
    time: `${get("hour")}:${get("minute")}`,
  }
}

/** UTC moment → "۱۴۰۵/۰۶/۳۰ · ۱۶:۲۴" in the store's time zone. */
export function formatJalaliDateTime(utc: string, timeZone: string): string {
  const local = utcToLocal(utc, timeZone)
  if (!local) return toPersianDigits(utc)
  return `${formatJalali(local.iso, "yyyy/MM/dd")} · ${toPersianDigits(local.time)}`
}

export type IsoRange = { from: string; to: string }

/** The Jalali month containing `date`, as Gregorian ISO days. */
export function jalaliMonthRange(date: Date): IsoRange {
  return { from: dateToISO(startOfMonth(date)), to: dateToISO(endOfMonth(date)) }
}

export type RangePreset =
  | "today"
  | "yesterday"
  | "last7"
  | "last30"
  | "thisMonth"
  | "lastMonth"
  | "thisYear"

/** Preset ranges relative to `today` (the browser's local day). */
export function presetRange(preset: RangePreset, today: Date): IsoRange {
  const iso = (d: Date) => dateToISO(d)
  switch (preset) {
    case "today":
      return { from: iso(today), to: iso(today) }
    case "yesterday": {
      const y = subDays(today, 1)
      return { from: iso(y), to: iso(y) }
    }
    case "last7":
      return { from: iso(subDays(today, 6)), to: iso(today) }
    case "last30":
      return { from: iso(subDays(today, 29)), to: iso(today) }
    case "thisMonth":
      return jalaliMonthRange(today)
    case "lastMonth":
      return jalaliMonthRange(subMonths(today, 1))
    case "thisYear":
      return { from: iso(startOfYear(today)), to: iso(endOfYear(today)) }
  }
}

/** Inclusive length of a range in days: ۱ → ۳۱ شهریور = 31. */
export function rangeDays(range: IsoRange): number {
  return differenceInCalendarDays(isoToDate(range.to), isoToDate(range.from)) + 1
}

/** Jalali year of a date, e.g. 1405 (for the «سال ۱۴۰۵» preset label). */
export function jalaliYear(date: Date): number {
  return getYear(date)
}

/** "شهریور ۱۴۰۵" when the range is exactly one whole Jalali month, else null. */
export function wholeMonthLabel(range: IsoRange): string | null {
  const month = jalaliMonthRange(isoToDate(range.from))
  if (month.from !== range.from || month.to !== range.to) return null
  return formatJalali(range.from, "MMMM yyyy")
}
