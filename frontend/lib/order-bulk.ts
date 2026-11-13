/**
 * The orders list's bulk action: «پرداخت‌شده» → «تکمیل‌شده» for the rows ticked in the list. Pure helpers with no
 * React and no API calls, so `npm test` can run them: the selection set, what a selection allows, the request
 * body and how a refusal is read. The rule itself lives in db/orders.py `bulk_update_order_status`, which stays the
 * judge (the screen only avoids sending what it will refuse): all or nothing, only PAID orders, at most 200.
 */

import { type CodedError, hasCode } from "./error-codes.ts"

/** db/orders.py BULK_STATUS_MAX. */
export const BULK_MAX = 200
/** The one status a bulk change moves from (to COMPLETED). */
export const BULK_FROM_STATUS = "PAID"

/** The order fields the bulk action reads (OrderListItem fits). */
export type BulkRow = { id: number; status: string; invoice_number: string | null }

export type Selection = ReadonlySet<number>

/** The selection with `id` ticked, or unticked if it was ticked. Never mutates. */
export function toggleId(ids: Selection, id: number): Set<number> {
  const next = new Set(ids)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  return next
}

/** The selection with every id of `targets` ticked (`on`) or unticked. Never mutates. */
export function setIds(ids: Selection, targets: readonly number[], on: boolean): Set<number> {
  const next = new Set(ids)
  for (const id of targets) {
    if (on) next.add(id)
    else next.delete(id)
  }
  return next
}

/** How many of `pageIds` are ticked: the header checkbox is checked ("all"), mixed ("some") or empty ("none"). */
export type PageState = "none" | "some" | "all"

export function pageState(ids: Selection, pageIds: readonly number[]): PageState {
  if (pageIds.length === 0) return "none"
  const ticked = pageIds.filter((id) => ids.has(id)).length
  return ticked === 0 ? "none" : ticked === pageIds.length ? "all" : "some"
}

export type BulkPlan = {
  /** The ticked orders the list still has, in the list's order. */
  chosen: BulkRow[]
  /** The chosen ones that are not PAID: any of them disables the action. */
  ineligible: BulkRow[]
  tooMany: boolean
  /** Something is chosen, all of it PAID, and not more than BULK_MAX. */
  canRun: boolean
}

/**
 * What the selection allows. `rows` is every order the list holds (not only the page on screen: a selection
 * keeps across pages), `ids` the ticked ones. A ticked id the list no longer holds is ignored.
 */
export function planBulk(rows: readonly BulkRow[], ids: Selection): BulkPlan {
  const chosen = rows.filter((r) => ids.has(r.id))
  const ineligible = chosen.filter((r) => r.status !== BULK_FROM_STATUS)
  const tooMany = chosen.length > BULK_MAX
  return { chosen, ineligible, tooMany, canRun: chosen.length > 0 && ineligible.length === 0 && !tooMany }
}

/** The POST /orders/bulk-status body for the chosen orders. */
export function bulkBody(chosen: readonly BulkRow[]): { order_ids: number[]; status: "COMPLETED" } {
  return { order_ids: chosen.map((r) => r.id), status: "COMPLETED" }
}

/**
 * How many orders a refused bulk call found that are not PAID (409 ORDER_BULK_NOT_ELIGIBLE, details
 * `ineligible`); null for any other error. The list changed under the screen: it is read again.
 */
export function ineligibleCount(e: CodedError): number | null {
  if (e.status !== 409 || !hasCode(e, "ORDER_BULK_NOT_ELIGIBLE")) return null
  const list = e.details?.ineligible
  return Array.isArray(list) ? list.length : null
}
