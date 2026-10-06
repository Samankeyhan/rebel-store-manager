/**
 * Payment-method helpers with no React and no API calls, so `npm test` can
 * run them: the fee percentage typed by the owner ↔ integer basis points, and
 * the classification of the backend's payment errors.
 *
 * The frontend never computes a fee: GET /payment-methods/{id}/fee-preview
 * does. Percent ↔ basis points is only input conversion, done on the digit
 * string with integer arithmetic (never parseFloat, never a float multiply).
 */

import { toLatinDigits, toPersianDigits } from "./persian-numbers.ts"

export const BPS_MAX = 10000

export type SettlementRule = "IMMEDIATE" | "DAYS_AFTER" | "DAY_OF_NEXT_MONTH"

export const SETTLEMENT_RULES: SettlementRule[] = ["IMMEDIATE", "DAYS_AFTER", "DAY_OF_NEXT_MONTH"]

/** settlement_days bounds per rule (db/payment_methods.py); IMMEDIATE takes none. */
export const DAYS_BOUNDS: Record<SettlementRule, { min: number; max: number } | null> = {
  IMMEDIATE: null,
  DAYS_AFTER: { min: 1, max: 365 },
  DAY_OF_NEXT_MONTH: { min: 1, max: 31 },
}

export type PercentResult =
  | { ok: true; bps: number }
  | { ok: false; error: "format" | "decimals" | "range" }

/**
 * "1.5", "۱٫۵", "١٫٥", "12", "0.05", "" (= 0), optionally with a trailing % or ٪
 * → basis points (1.5% = 150). At most two decimals; 0..100%.
 */
export function parsePercent(text: string): PercentResult {
  const s = toLatinDigits(text)
    .trim()
    .replace(/[%٪]$/, "")
    .trim()
    .replace(/٫/g, ".")
  if (s === "") return { ok: true, bps: 0 }
  const m = /^(\d*)(?:\.(\d*))?$/.exec(s)
  if (!m || (m[1] === "" && !m[2])) return { ok: false, error: "format" }
  const frac = m[2] ?? ""
  if (frac.length > 2) return { ok: false, error: "decimals" }
  const whole = m[1].replace(/^0+(?=\d)/, "") || "0"
  if (whole.length > 3) return { ok: false, error: "range" }
  const bps = Number(whole) * 100 + Number(frac.padEnd(2, "0"))
  if (bps > BPS_MAX) return { ok: false, error: "range" }
  return { ok: true, bps }
}

/** Basis points → «۱٫۵» (Persian digits, ٫, no trailing zero): 150 → ۱٫۵, 5 → ۰٫۰۵, 1200 → ۱۲. */
export function formatPercent(bps: number): string {
  const whole = Math.floor(bps / 100)
  const frac = String(bps % 100).padStart(2, "0").replace(/0+$/, "")
  return toPersianDigits(frac ? `${whole}٫${frac}` : String(whole))
}

/** What a failed payment-related call means for the UI. */
export type PaymentError =
  | { kind: "closedMonth"; year: number; month: number }
  | { kind: "settled"; settlementId: number | null }
  | { kind: "unpaid" }
  | { kind: "rulePending"; count: number }
  | { kind: "duplicateName" }
  | { kind: "futurePaidDate" }
  | { kind: "paidDateNotAllowed" }
  | { kind: "inactiveMethod" }
  | { kind: "inactiveDefault" }

type ErrorLike = { status: number; field?: string | null; message: string }

/**
 * Classifies a payment-related API error. The backend sends no error codes,
 * so the 409s are recognised by their (English) message text; keep these
 * patterns in step with db/orders.py and db/payment_methods.py.
 */
export function classifyPaymentError(e: ErrorLike): PaymentError | null {
  const msg = e.message
  if (e.status === 409) {
    const month = /month (\d{4})\/(\d{1,2}) is already settled/.exec(msg)
    if (month) return { kind: "closedMonth", year: Number(month[1]), month: Number(month[2]) }
    const settled = /is part of settlement #(\d+)/.exec(msg)
    if (settled) return { kind: "settled", settlementId: Number(settled[1]) }
    if (/, not paid\b/.test(msg)) return { kind: "unpaid" }
    const pending = /(\d+) paid orders? (?:is|are) still pending settlement/.exec(msg)
    if (pending) return { kind: "rulePending", count: Number(pending[1]) }
    if (/payment method named .* already exists/.test(msg)) return { kind: "duplicateName" }
    return null
  }
  if (e.status === 422) {
    if (e.field === "paid_date") {
      return /in the future/.test(msg) ? { kind: "futurePaidDate" } : { kind: "paidDateNotAllowed" }
    }
    if (e.field === "payment_method_id" && /is not active/.test(msg)) return { kind: "inactiveMethod" }
    if (e.field === "default_payment_method_id") return { kind: "inactiveDefault" }
  }
  return null
}
