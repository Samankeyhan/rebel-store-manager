/**
 * Editing and deleting an expense or a postage payment: what to send and how to read a refusal.
 * Dependency-free so `npm test` can run it. Days are Gregorian "YYYY-MM-DD" in the store's time zone
 * (the caller turns the stored moment into a day with lib/jalali.ts `utcToLocal`); money is integer Rial.
 */

import { detailNum, detailStr, hasCode, type CodedError } from "./error-codes.ts"

/** A change of amount or date on a day on or before the latest profit payout's period_end, or a delete there. */
export type ClosedDay = { periodEnd: string; date: string; distributionId: number | null }

export function closedDay(e: CodedError): ClosedDay | null {
  if (e.status !== 409 || !hasCode(e, "PERIOD_ALREADY_DISTRIBUTED")) return null
  const periodEnd = detailStr(e, "period_end")
  if (periodEnd == null) return null
  return { periodEnd, date: detailStr(e, "date") ?? periodEnd, distributionId: detailNum(e, "distribution_id") }
}

/** The new record date was after today (DATE_IN_FUTURE on that field). */
export function isFutureDateError(e: CodedError, field: "expense_date" | "paid_date"): boolean {
  return e.status === 422 && hasCode(e, "DATE_IN_FUTURE") && e.field === field
}

export type ExpenseFields = { categoryId: number; amount: number; description: string; day: string }
export type ExpenseBody = { expense_category_id?: number; amount?: number; description?: string | null; expense_date?: string }

/** Only what differs from the saved expense (PATCH semantics); null when nothing changed. A blank description clears it. */
export function expensePatch(saved: ExpenseFields, form: ExpenseFields): ExpenseBody | null {
  const body: ExpenseBody = {}
  if (form.categoryId !== saved.categoryId) body.expense_category_id = form.categoryId
  if (form.amount !== saved.amount) body.amount = form.amount
  if (form.day !== saved.day) body.expense_date = form.day
  const description = form.description.trim()
  if (description !== saved.description.trim()) body.description = description || null
  return Object.keys(body).length > 0 ? body : null
}

export type PostageFields = { total: number; orders: number; note: string; day: string }
export type PostageBody = { total_paid?: number; order_count?: number; notes?: string | null; paid_date?: string }

export function postagePatch(saved: PostageFields, form: PostageFields): PostageBody | null {
  const body: PostageBody = {}
  if (form.total !== saved.total) body.total_paid = form.total
  if (form.orders !== saved.orders) body.order_count = form.orders
  if (form.day !== saved.day) body.paid_date = form.day
  const note = form.note.trim()
  if (note !== saved.note.trim()) body.notes = note || null
  return Object.keys(body).length > 0 ? body : null
}
