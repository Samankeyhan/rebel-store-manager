/**
 * Payment-method helpers with no React and no API calls, so `npm test` can
 * run them: the fee percentage typed by the owner ↔ integer basis points, and
 * the classification of the backend's payment errors.
 *
 * The frontend never computes a fee: GET /payment-methods/{id}/fee-preview
 * does. Percent ↔ basis points is only input conversion, done on the digit
 * string with integer arithmetic (never parseFloat, never a float multiply).
 */

import { type CodedError, detailNum, hasCode } from "./error-codes.ts"
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

/**
 * The fee cap typed by the owner (MoneyInput with allowEmpty): undefined =
 * empty = no cap, null = text that gives no exact amount, else integer Rial.
 * A cap only applies with a percentage fee (db/payment_methods.py); while the
 * percentage is empty, 0 or invalid (`bps` 0 or null) the field is off and
 * ignored, so it has no error then.
 */
export type CapError = "inexact" | "min"

export function capError(bps: number | null, cap: number | null | undefined): CapError | null {
  if (!bps || cap === undefined) return null
  if (cap === null) return "inexact"
  if (!Number.isSafeInteger(cap) || cap < 1) return "min"
  return null
}

/** The fee_cap to send: null (no cap) without a percentage fee or when empty. */
export function capForSave(bps: number | null, cap: number | null | undefined): number | null {
  return bps ? (cap ?? null) : null
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

/**
 * Classifies a payment-related API error by its code and details
 * (db/orders.py, db/payment_methods.py; see lib/error-codes.ts).
 */
export function classifyPaymentError(e: CodedError): PaymentError | null {
  if (e.status === 409) {
    switch (e.code) {
      case "MONTH_ALREADY_SETTLED": {
        const year = detailNum(e, "jalali_year")
        const month = detailNum(e, "jalali_month")
        return year != null && month != null ? { kind: "closedMonth", year, month } : null
      }
      case "ORDER_ALREADY_SETTLED": {
        const settlementId = detailNum(e, "settlement_id")
        return settlementId != null ? { kind: "settled", settlementId } : null
      }
      case "ORDER_NOT_PAID":
        return { kind: "unpaid" }
      case "PAYMENT_METHOD_RULE_PENDING": {
        const count = detailNum(e, "pending_count")
        return count != null ? { kind: "rulePending", count } : null
      }
      case "PAYMENT_METHOD_DUPLICATE_NAME":
        return { kind: "duplicateName" }
      default:
        return null
    }
  }
  if (e.status === 422) {
    // Any other paid_date refusal (given where not allowed, or not a date) is paidDateNotAllowed.
    if (e.field === "paid_date") return hasCode(e, "DATE_IN_FUTURE") ? { kind: "futurePaidDate" } : { kind: "paidDateNotAllowed" }
    if (e.field === "payment_method_id" && hasCode(e, "PAYMENT_METHOD_INACTIVE")) return { kind: "inactiveMethod" }
    if (e.field === "default_payment_method_id") return { kind: "inactiveDefault" }
  }
  return null
}
