/**
 * Settlement helpers with no React and no API calls, so `npm test` can run
 * them: the selection preview total, the difference preview, overdue counts,
 * group titles, the payment_reference join and the classification of the
 * backend's settlement errors.
 *
 * Every saved figure (expected_amount, difference, total_expected, the group
 * sums) comes from the API (db/settlements.py). The two sums made here are
 * labelled previews and mirror db/ exactly: integer Rial, difference =
 * amount_received − expected_amount.
 */

import { formatJalali } from "./jalali.ts"

/** The pending-order fields these helpers read (PendingOrderOut). */
export type PendingOrderLike = { id: number; expected_amount: number }

export type DateGroupLike = { expected_date: string; overdue: boolean; due: boolean; order_count: number }
export type MonthGroupLike = DateGroupLike & {
  jalali_year: number
  jalali_month: number
  month_first_day: string
  month_last_day: string
  can_settle: boolean
}
export type GroupLike = DateGroupLike | MonthGroupLike

/** A DAY_OF_NEXT_MONTH group (PendingMonthGroupOut) rather than a date group. */
export function isMonthGroup<G extends GroupLike>(g: G): g is G & MonthGroupLike {
  return "jalali_month" in g && (g as MonthGroupLike).jalali_month != null
}

/** Adds two integer Rial amounts; null when either or the result is not a safe integer. */
function addRial(a: number | null, b: number): number | null {
  if (a === null || !Number.isSafeInteger(a) || !Number.isSafeInteger(b)) return null
  const s = a + b
  return Number.isSafeInteger(s) ? s : null
}

/**
 * Preview of the expected amount of a chosen set of orders: the exact sum of
 * their expected_amount (db/settlements.py sums the same field). 0 for none;
 * null when a value or the sum leaves the safe-integer range.
 */
export function selectionTotal(amounts: readonly number[]): number | null {
  let total: number | null = 0
  for (const a of amounts) total = addRial(total, a)
  return total
}

/** The sum of the selected orders' expected_amount (see selectionTotal). */
export function selectedExpected(orders: readonly PendingOrderLike[], selected: ReadonlySet<number>): number | null {
  return selectionTotal(orders.filter((o) => selected.has(o.id)).map((o) => o.expected_amount))
}

/**
 * Preview of the difference the backend will store: received − expected,
 * exactly as db/settlements.py. null while the amount is empty or inexact,
 * or when the result is not a safe integer.
 */
export function previewDifference(received: number | null | undefined, expected: number | null): number | null {
  if (received == null || expected === null) return null
  if (!Number.isSafeInteger(received) || !Number.isSafeInteger(expected)) return null
  const d = received - expected
  return Number.isSafeInteger(d) ? d : null
}

export type DifferenceKind = "over" | "under" | "equal"

/** over: more arrived than expected; under: less; equal: exactly as expected. */
export function differenceKind(difference: number): DifferenceKind {
  return difference > 0 ? "over" : difference < 0 ? "under" : "equal"
}

/** Orders in overdue groups (a count, never money): the sum of order_count over groups with overdue set. */
export function overdueOrderCount(groups: readonly GroupLike[]): number {
  return groups.reduce((n, g) => (g.overdue ? n + g.order_count : n), 0)
}

/** «مهر ۱۴۰۵» for a month group; the expected date «۱۵ مهر ۱۴۰۵» for a date group. */
export function groupTitle(g: GroupLike): string {
  return isMonthGroup(g) ? formatJalali(g.month_first_day, "MMMM yyyy") : formatJalali(g.expected_date)
}

/**
 * Pending orders carry no payment_reference (backend gap): join it from
 * GET /orders?settlement_state=pending by order id. An order missing from
 * `refs` gets null (shown as «—»).
 */
export function attachReferences<T extends { id: number }>(
  orders: readonly T[],
  refs: ReadonlyMap<number, string | null>
): (T & { payment_reference: string | null })[] {
  return orders.map((o) => ({ ...o, payment_reference: refs.get(o.id) ?? null }))
}

/** id → payment_reference from order list rows (blank references count as none). */
export function referenceMap(rows: readonly { id: number; payment_reference?: string | null }[]): Map<number, string | null> {
  return new Map(rows.map((r) => [r.id, r.payment_reference?.trim() ? r.payment_reference.trim() : null]))
}

// ---------------------------------------------------------------- errors

/** What a failed settlement call means for the UI. */
export type SettlementError =
  | { kind: "monthNotEnded"; year: number; month: number; ends: string }
  | { kind: "monthSettled"; year: number; month: number; settlementId: number | null }
  | { kind: "orderSettled"; orderId: number; settlementId: number }
  | { kind: "orderNotPaid"; orderId: number }
  | { kind: "nothingPending" }
  | { kind: "raced" }
  | { kind: "conflict" }
  | { kind: "futureDate" }
  | { kind: "beforeMonthEnd"; year: number; month: number }
  | { kind: "beforePaid"; date: string }
  | { kind: "badAmount" }
  | { kind: "wrongMethod"; orderId: number }
  | { kind: "badSelection" }
  | { kind: "wrongShape" }
  | { kind: "notMonthly" }
  | { kind: "notFound" }

type ErrorLike = { status: number; field?: string | null; message: string }

/**
 * Classifies a settlement API error. The backend sends no error codes, so
 * these are recognised by their (English) message text; keep the patterns in
 * step with db/settlements.py. null = not a settlement error (show the
 * generic message).
 */
export function classifySettlementError(e: ErrorLike): SettlementError | null {
  const msg = e.message
  if (e.status === 404) return { kind: "notFound" }
  if (e.status === 409) {
    let m = /Month (\d{4})\/(\d{1,2}) has not ended yet \(it ends (\d{4}-\d{2}-\d{2})\)/.exec(msg)
    if (m) return { kind: "monthNotEnded", year: Number(m[1]), month: Number(m[2]), ends: m[3] }
    m = /month (\d{4})\/(\d{1,2}) is already settled(?: \(settlement #(\d+)\))?/.exec(msg)
    if (m) return { kind: "monthSettled", year: Number(m[1]), month: Number(m[2]), settlementId: m[3] ? Number(m[3]) : null }
    m = /Order #(\d+) is already in settlement #(\d+)/.exec(msg)
    if (m) return { kind: "orderSettled", orderId: Number(m[1]), settlementId: Number(m[2]) }
    m = /Order #(\d+) is \w+, not paid/.exec(msg)
    if (m) return { kind: "orderNotPaid", orderId: Number(m[1]) }
    if (/^Nothing to settle\b/.test(msg)) return { kind: "nothingPending" }
    if (/settled meanwhile/.test(msg)) return { kind: "raced" }
    if (/conflicts with existing data/.test(msg)) return { kind: "conflict" }
    return null
  }
  if (e.status === 422) {
    if (e.field === "settled_date") {
      if (/in the future/.test(msg)) return { kind: "futureDate" }
      const m = /must be after the end of month (\d{4})\/(\d{1,2})/.exec(msg)
      if (m) return { kind: "beforeMonthEnd", year: Number(m[1]), month: Number(m[2]) }
      const p = /before the latest paid date of its orders \((\d{4}-\d{2}-\d{2})\)/.exec(msg)
      if (p) return { kind: "beforePaid", date: p[1] }
      return null
    }
    // db/'s ">= 0" / "must be an integer", or FastAPI's strict-int refusal.
    if (e.field === "amount_received") return { kind: "badAmount" }
    if (e.field === "order_ids") {
      if (/settles whole months only/.test(msg)) return { kind: "wrongShape" }
      const m = /Order #(\d+) was not paid with/.exec(msg)
      if (m) return { kind: "wrongMethod", orderId: Number(m[1]) }
      return { kind: "badSelection" }
    }
    if ((e.field === "jalali_year" || e.field === "jalali_month") && /applies only to a method that settles whole months/.test(msg))
      return { kind: "notMonthly" }
  }
  return null
}

/** The form field a classified error belongs under; null = an alert in the dialog. */
export function settlementErrorField(e: SettlementError): "settled_date" | "amount_received" | null {
  switch (e.kind) {
    case "futureDate":
    case "beforeMonthEnd":
    case "beforePaid":
      return "settled_date"
    case "badAmount":
      return "amount_received"
    default:
      return null
  }
}

/** Errors that mean the pending list is stale: refetch it and say so. */
export function settlementErrorRefreshes(e: SettlementError): boolean {
  return ["raced", "orderSettled", "orderNotPaid", "nothingPending", "monthSettled"].includes(e.kind)
}
