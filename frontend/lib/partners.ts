/**
 * Partner and payout helpers with no React and no API calls, so `npm test`
 * can run them: percentage parsing and the exact 100 check, the backend's
 * own sum check (to block payouts), name clashes, the default payout period
 * and the classification of the backend's distribution errors.
 *
 * Shares are never computed here: the split and its rounding come from
 * POST /distributions/preview (db/distributions.py), and the saved shares
 * from POST /distributions.
 */

import { type CodedError, detailNum, detailStr, hasCode } from "./error-codes.ts"
import { dateToISO, isoToDate, toGregorianISO, toJalali } from "./jalali.ts"
import { formatQuantity, toLatinDigits, toPersianDigits } from "./persian-numbers.ts"

/** The owner's 100 is "hundredths of a percent", so 33.33 + 33.33 + 33.34 is exactly 10000. */
export const HUNDRED_PERCENT = 10000

/** db/distributions.py PERCENTAGE_SUM_TOLERANCE. */
const BACKEND_SUM_TOLERANCE = 0.01

export type PercentError = "empty" | "format" | "decimals" | "range"
export type ParsedPercent = { hundredths: number; error: null } | { hundredths: null; error: PercentError }

/**
 * A typed percentage → whole hundredths: Persian, Arabic-Indic or Latin
 * digits, "." / "٫" / "/" as the decimal mark, at most 2 decimals, and
 * 0 < p ≤ 100 (db/partners.py's range). The 2-decimal limit is the screen's,
 * so the total can be checked exactly.
 */
export function parsePercent(text: string): ParsedPercent {
  const s = toLatinDigits(text.trim()).replace(/[٫/]/g, ".")
  if (s === "") return { hundredths: null, error: "empty" }
  const m = /^(\d*)(?:\.(\d*))?$/.exec(s)
  if (!m || (m[1] === "" && !m[2])) return { hundredths: null, error: "format" }
  const frac = m[2] ?? ""
  if (frac.length > 2) return { hundredths: null, error: "decimals" }
  const whole = m[1] === "" ? 0 : Number(m[1])
  const hundredths = whole * 100 + Number(frac.padEnd(2, "0"))
  if (!Number.isSafeInteger(hundredths) || hundredths <= 0 || hundredths > HUNDRED_PERCENT)
    return { hundredths: null, error: "range" }
  return { hundredths, error: null }
}

/** Hundredths → the number sent as current_percentage (3333 → 33.33, the same double Python parses). */
export function percentOf(hundredths: number): number {
  return hundredths / 100
}

/** A stored percentage as typed text for the editor: 33.33 → "۳۳٫۳۳". */
export function percentText(pct: number): string {
  const s = String(pct)
  return /e/i.test(s) ? formatQuantity(pct) : toPersianDigits(s.replace(".", "٫"))
}

/** Σ of whole hundredths; null while any row is invalid. */
export function totalHundredths(values: readonly (number | null)[]): number | null {
  let total = 0
  for (const v of values) {
    if (v === null) return null
    total += v
  }
  return total
}

/** "ok" only at exactly 100.00. */
export function splitState(total: number | null): "ok" | "under" | "over" | "invalid" {
  if (total === null) return "invalid"
  return total === HUNDRED_PERCENT ? "ok" : total < HUNDRED_PERCENT ? "under" : "over"
}

type PartnerLike = { id: number; name: string; current_percentage: number; is_active: number }

/** Σ current_percentage of the active partners, summed in list order as db/ does. */
export function activeTotal(partners: readonly PartnerLike[]): number {
  return partners.filter((p) => p.is_active === 1).reduce((s, p) => s + p.current_percentage, 0)
}

/** db/distributions.py _validate_percentage_sum: |Σ − 100| ≤ 0.01; payouts are blocked otherwise. */
export function backendAcceptsTotal(partners: readonly PartnerLike[]): boolean {
  return Math.abs(activeTotal(partners) - 100) <= BACKEND_SUM_TOLERANCE
}

/** The rows whose percentage changes, in the given order. */
export function percentChanges(
  partners: readonly Pick<PartnerLike, "id" | "current_percentage">[],
  edited: ReadonlyMap<number, number>
): { partnerId: number; percentage: number }[] {
  const out: { partnerId: number; percentage: number }[] = []
  for (const p of partners) {
    const h = edited.get(p.id)
    if (h === undefined) continue
    const next = percentOf(h)
    if (next !== p.current_percentage) out.push({ partnerId: p.id, percentage: next })
  }
  return out
}

/**
 * /partners/totals has no partner_id, so two partners with one name would
 * merge: a name is taken when it matches any partner, active or not, ignoring
 * case and surrounding spaces (db/ strips the name).
 */
export function isNameTaken(name: string, partners: readonly Pick<PartnerLike, "name">[]): boolean {
  const key = name.trim().toLowerCase()
  return key !== "" && partners.some((p) => p.name.trim().toLowerCase() === key)
}

/** First day of the Jalali year containing `iso`, as Gregorian "YYYY-MM-DD". */
export function jalaliYearStart(iso: string): string {
  return toGregorianISO(`${toJalali(iso).year}/01/01`)
}

function nextDay(iso: string): string {
  const d = isoToDate(iso)
  d.setDate(d.getDate() + 1)
  return dateToISO(d)
}

/**
 * The payout period offered by default: the day after the latest recorded
 * period through today, or (first payout) the start of the current Jalali
 * year through today. Never an empty range; always editable.
 */
export function defaultPeriod(today: string, distributions: readonly { period_end: string }[]): { from: string; to: string } {
  let latest: string | null = null
  for (const d of distributions) if (latest === null || d.period_end > latest) latest = d.period_end
  if (latest === null) return { from: jalaliYearStart(today), to: today }
  const from = nextDay(latest)
  return { from, to: from > today ? from : today }
}

/** amount − undistributed, exact; null outside the safe-integer range. */
export function overCapBy(amount: number, undistributed: number): number | null {
  const d = amount - undistributed
  return Number.isSafeInteger(amount) && Number.isSafeInteger(undistributed) && Number.isSafeInteger(d) ? d : null
}

export type DistributionError =
  | { kind: "overlap"; id: number; from: string; to: string }
  | { kind: "noPartners" }
  | { kind: "percentSum" }
  | { kind: "overCap" }
  | { kind: "badAmount" }
  | { kind: "periodOrder" }
  | { kind: "badDate" }

/** The backend's distribution errors (db/distributions.py codes); null = show its message. */
export function classifyDistributionError(e: CodedError): DistributionError | null {
  if (e.status === 409) {
    const id = detailNum(e, "distribution_id")
    const from = detailStr(e, "period_start")
    const to = detailStr(e, "period_end")
    return hasCode(e, "DISTRIBUTION_PERIOD_OVERLAP") && id != null && from != null && to != null
      ? { kind: "overlap", id, from, to }
      : null
  }
  if (e.status !== 422) return null
  if (hasCode(e, "DISTRIBUTION_NO_ACTIVE_PARTNERS")) return { kind: "noPartners" }
  if (hasCode(e, "DISTRIBUTION_PERCENT_SUM")) return { kind: "percentSum" }
  if (e.field === "total_amount_distributed")
    return hasCode(e, "DISTRIBUTION_EXCEEDS_UNDISTRIBUTED") ? { kind: "overCap" } : { kind: "badAmount" }
  if (e.field === "period_end" && hasCode(e, "DISTRIBUTION_PERIOD_ORDER")) return { kind: "periodOrder" }
  if (e.field === "date" || e.field === "period_start" || e.field === "period_end" || e.field === "distribution_date")
    return { kind: "badDate" }
  return null
}
