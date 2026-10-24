/**
 * Supplier-payables helpers with no React and no API calls, so `npm test` can
 * run them: the purchase form's payment check, the payment dialog's
 * allocation check, the `?pay=` filter and the classification of the
 * backend's payables errors.
 *
 * Every saved figure (paid, outstanding, payment_status, payables) comes from
 * the API (db/supplier_payments.py). The checks here only mirror its refusals
 * so the form can say what is wrong before sending; the backend decides.
 * Amounts are integer Rial.
 */

import { type CodedError, detailNum, detailStr, hasCode } from "./error-codes.ts"

export type PaymentMode = "FULL" | "NONE" | "PARTIAL"
export type PaymentStatus = "UNPAID" | "PARTIAL" | "PAID"
export type PayFilter = "unpaid" | "partial" | "paid"

export const PAY_FILTERS: readonly PayFilter[] = ["unpaid", "partial", "paid"]

/** The `?pay=` URL value as a filter; anything else is no filter. */
export function parsePayFilter(value: string | null): PayFilter | null {
  return PAY_FILTERS.includes(value as PayFilter) ? (value as PayFilter) : null
}

export function matchesPayFilter(status: PaymentStatus, filter: PayFilter | null): boolean {
  return filter == null || status.toLowerCase() === filter
}

/**
 * What the purchase form's payment part refuses, as db/supplier_payments.py
 * check_purchase_payment does: credit (NONE / PARTIAL) needs a supplier; a
 * partial amount is above 0 and below the invoice total. null = fine.
 * `partial` null means the money text gives no exact amount (MoneyInput).
 */
export function purchasePaymentProblem(
  mode: PaymentMode,
  hasSupplier: boolean,
  total: number | null,
  partial: number | null
): "supplier" | "partial_amount" | null {
  if (mode !== "FULL" && !hasSupplier) return "supplier"
  if (mode === "PARTIAL") {
    if (partial === null || partial <= 0) return "partial_amount"
    if (total !== null && partial >= total) return "partial_amount"
  }
  return null
}

/** The body's `payment` for a purchase: FULL sends no amount, PARTIAL its amount. */
export function purchasePaymentBody<M extends string>(
  mode: PaymentMode,
  partial: number | null,
  method: M,
  reference: string
): { mode: PaymentMode; amount: number | null; method: M; reference: string | null } {
  return {
    mode,
    amount: mode === "PARTIAL" ? partial : null,
    method,
    reference: mode === "NONE" ? null : reference.trim() || null,
  }
}

/** One editable allocation line: what the purchase still owes and what this payment gives it. */
export type AllocationLine = { key: string; outstanding: number; amount: number | null }

/**
 * Sum of the allocation amounts, exact integer Rial; null when a line has no
 * exact amount or the sum leaves the safe-integer range.
 */
export function allocatedTotal(lines: readonly AllocationLine[]): number | null {
  let total = 0
  for (const line of lines) {
    if (line.amount === null || !Number.isSafeInteger(line.amount)) return null
    total += line.amount
    if (!Number.isSafeInteger(total)) return null
  }
  return total
}

/**
 * What the payment dialog refuses before sending, mirroring
 * record_supplier_payment: an amount above 0; no line above what its purchase
 * owes ("over", with the line key); at least one line paid; the lines adding
 * up to the amount exactly ("mismatch"). null = fine.
 */
export function allocationProblem(
  amount: number | null,
  lines: readonly AllocationLine[]
): { kind: "amount" } | { kind: "over"; key: string } | { kind: "empty" } | { kind: "mismatch"; allocated: number | null } | null {
  if (amount === null || amount <= 0) return { kind: "amount" }
  for (const line of lines) {
    if (line.amount !== null && (line.amount < 0 || line.amount > line.outstanding)) return { kind: "over", key: line.key }
  }
  const allocated = allocatedTotal(lines)
  if (allocated === 0) return { kind: "empty" }
  if (allocated !== amount) return { kind: "mismatch", allocated }
  return null
}

/** The lines with an amount above 0, as the body's `allocations`. */
export function allocationsBody<L extends AllocationLine & { purchase_kind: "MATERIAL" | "PRODUCT"; purchase_id: number }>(
  lines: readonly L[]
): { purchase_kind: "MATERIAL" | "PRODUCT"; purchase_id: number; amount: number }[] {
  return lines
    .filter((l) => l.amount !== null && l.amount > 0)
    .map((l) => ({ purchase_kind: l.purchase_kind, purchase_id: l.purchase_id, amount: l.amount as number }))
}

export type PayablesErrorKind =
  | { kind: "supplier_required" }
  | { kind: "exceeds_due"; purchaseKind: string | null; purchaseId: number | null; outstanding: number | null }
  | { kind: "exceeds_balance"; outstanding: number | null }
  | { kind: "supplier_mismatch" }
  | { kind: "allocation_mismatch"; allocated: number | null }
  | { kind: "before_purchase"; purchaseDate: string | null }
  | { kind: "date_in_future" }
  | { kind: "not_found" }
  | { kind: "amount_too_large" }
  | { kind: "other" }

/** Which payables refusal an API error is (by code and details, never the message). */
export function classifyPayablesError(e: CodedError): PayablesErrorKind {
  if (hasCode(e, "SUPPLIER_REQUIRED_FOR_CREDIT")) return { kind: "supplier_required" }
  if (hasCode(e, "SUPPLIER_PAYMENT_EXCEEDS_DUE"))
    return {
      kind: "exceeds_due",
      purchaseKind: detailStr(e, "purchase_kind"),
      purchaseId: detailNum(e, "purchase_id"),
      outstanding: detailNum(e, "outstanding"),
    }
  if (hasCode(e, "SUPPLIER_PAYMENT_EXCEEDS_BALANCE")) return { kind: "exceeds_balance", outstanding: detailNum(e, "outstanding") }
  if (hasCode(e, "SUPPLIER_PAYMENT_SUPPLIER_MISMATCH")) return { kind: "supplier_mismatch" }
  if (hasCode(e, "SUPPLIER_PAYMENT_ALLOCATION_MISMATCH")) return { kind: "allocation_mismatch", allocated: detailNum(e, "allocated") }
  if (hasCode(e, "SUPPLIER_PAYMENT_BEFORE_PURCHASE")) return { kind: "before_purchase", purchaseDate: detailStr(e, "purchase_date") }
  if (hasCode(e, "DATE_IN_FUTURE")) return { kind: "date_in_future" }
  if (hasCode(e, "SUPPLIER_PAYMENT_NOT_FOUND", "PURCHASE_NOT_FOUND", "SUPPLIER_NOT_FOUND")) return { kind: "not_found" }
  if (hasCode(e, "AMOUNT_TOO_LARGE")) return { kind: "amount_too_large" }
  return { kind: "other" }
}
