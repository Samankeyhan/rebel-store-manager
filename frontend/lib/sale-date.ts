/**
 * Pure rules for the record-sale «تاریخ فروش» field. Days are Gregorian
 * "YYYY-MM-DD" strings (the store's calendar days, lib/store-day.ts); the day
 * difference is a plain calendar count between two such strings.
 */

/** A sale dated more than this many days before today asks for a confirmation. */
export const STALE_SALE_DAYS = 31

const MS_PER_DAY = 86_400_000

/** Whole calendar days from `from` to `to` (positive when `to` is later). */
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / MS_PER_DAY)
}

/** True when `day` is more than 31 days before `today`: exactly 31 days back is fine, 32 asks. */
export function isStaleSaleDay(day: string, today: string): boolean {
  return daysBetween(day, today) > STALE_SALE_DAYS
}

/** POST /orders refused the sale day itself (DATE_IN_FUTURE on order_date), not the payment day. */
export function isFutureOrderDateError(error: { code?: string | null; field?: string | null }): boolean {
  return error.code === "DATE_IN_FUTURE" && error.field === "order_date"
}
