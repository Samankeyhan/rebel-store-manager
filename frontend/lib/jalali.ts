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
  format,
  getDate,
  getMonth,
  getYear,
  isValid,
  newDate,
} from "date-fns-jalali"

import { toLatinDigits, toPersianDigits } from "@/lib/persian-numbers"

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
