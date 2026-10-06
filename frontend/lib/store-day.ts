/**
 * The store's calendar day. "Today" for any business rule shown in the UI
 * (a default date, a "no future dates" limit, the payment day an order is
 * sent with) is the day in the store's time zone (settings.timezone), not the
 * browser's: the backend's today_local() uses the same zone. The browser's Intl
 * does the conversion; nothing here does offset arithmetic.
 *
 * Read it when it's needed (e.g. at submit time): a session can cross midnight.
 */

/** The zone the accounting rules name, used when settings.timezone is missing, invalid or unreadable. */
export const DEFAULT_TZ = "Asia/Tehran"

function dayIn(now: Date, timeZone: string): string | null {
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(now)
    const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ""
    return `${get("year")}-${get("month")}-${get("day")}`
  } catch {
    return null
  }
}

/** The store's calendar day for `now`, as "YYYY-MM-DD"; an unknown zone falls back to Asia/Tehran. */
export function storeToday(now: Date, timeZone: string | null | undefined): string {
  return (timeZone ? dayIn(now, timeZone) : null) ?? (dayIn(now, DEFAULT_TZ) as string)
}
