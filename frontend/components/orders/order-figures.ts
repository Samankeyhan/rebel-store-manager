/**
 * Pure display rules for orders. The status maps mirror the backend exactly
 * (db/orders.py _ALLOWED_TRANSITIONS, db/returns.py *_ALLOWED_FROM) — the UI
 * only offers what the API will accept. The figures here only re-state what
 * the API returned; none of them is saved anywhere.
 */

import type { OrderDetail, OrderListItem } from "@/lib/api"

/** sessionStorage key: the list's last query, so the detail crumb returns to the same filters. */
export const LIST_QUERY_KEY = "orders:lastQuery"

/** POST /orders/{id}/status: forward moves only. */
export const FORWARD: Record<string, readonly string[]> = {
  DRAFT: ["PENDING", "PAID", "COMPLETED"],
  PENDING: ["PAID", "COMPLETED"],
  PAID: ["COMPLETED"],
}

/** POST /orders/{id}/return with status CANCELLED: never shipped. */
export const CAN_CANCEL = new Set(["DRAFT", "PENDING", "PAID"])
/** POST /orders/{id}/return with status REFUNDED: paid or shipped. */
export const CAN_REFUND = new Set(["PAID", "COMPLETED"])

/** accounting-rules §9: the statuses that count as revenue. */
export const REVENUE_ELIGIBLE = new Set(["PENDING", "PAID", "COMPLETED"])

type CostFields = Pick<
  OrderListItem,
  "packaging_cost" | "postage_cost" | "transaction_fee" | "stock_committed"
>

/**
 * accounting-rules §7/§9: a refund's loss is packaging + postage + fee.
 * The API doesn't return it (backend follow-up: a net_result field).
 */
export function refundLoss(order: CostFields): number {
  return order.packaging_cost + order.postage_cost + order.transaction_fee
}

/** §9: a cancellation loses only its fee, and only if stock was committed. */
export function cancelLoss(order: CostFields): number {
  return order.stock_committed ? order.transaction_fee : 0
}

export type ProfitView =
  | { kind: "none" }
  | { kind: "known"; profit: number }
  /** Both figures shown side by side, as the P&L keeps them apart. */
  | { kind: "refund"; original: number; loss: number }

/**
 * DRAFT has frozen nothing and CANCELLED left the reports, so neither has a
 * profit (the detail endpoint returns a number for both; it isn't one).
 */
export function profitView(status: string, profit: number | null, order: CostFields): ProfitView {
  if (status === "DRAFT" || status === "CANCELLED") return { kind: "none" }
  if (status === "REFUNDED") {
    return { kind: "refund", original: profit ?? 0, loss: refundLoss(order) }
  }
  return profit == null ? { kind: "none" } : { kind: "known", profit }
}

/** Frozen cost of goods: Σ qty × unit_cost_at_time (the API's own profit uses the same). */
export function cogs(detail: OrderDetail): number {
  return detail.items.reduce((sum, i) => sum + i.quantity * i.unit_cost_at_time, 0)
}

export function itemsGross(detail: OrderDetail): number {
  return detail.items.reduce((sum, i) => sum + i.list_price, 0)
}

export function itemsDiscount(detail: OrderDetail): number {
  return detail.items.reduce((sum, i) => sum + i.discount_amount, 0)
}

export function unitCount(detail: OrderDetail): number {
  return detail.items.reduce((sum, i) => sum + i.quantity, 0)
}

/** Whole-percent margin, or null when there is no revenue. */
export function marginPct(profit: number, total: number): number | null {
  return total ? Math.round((profit / total) * 100) : null
}

/** Strips Persian/Arabic digits and the INV- prefix for invoice search. */
export function matchesSearch(row: OrderListItem, query: string, toLatin: (s: string) => string): boolean {
  const q = toLatin(query).trim().toLowerCase()
  if (!q) return true
  const customer = (row.customer_name ?? "").toLowerCase()
  if (customer.includes(q) || customer.includes(query.trim())) return true
  const inv = (row.invoice_number ?? "").toLowerCase()
  if (inv.includes(q)) return true
  const digits = q.replace(/\D/g, "")
  if (!digits) return false
  const invDigits = inv.replace(/\D/g, "")
  return invDigits.includes(digits) || String(Number(invDigits)) === String(Number(digits))
}
