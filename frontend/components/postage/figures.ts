/**
 * The postage estimate, explained and previewed (docs/accounting-rules.md §6,
 * formulas.md §2): round(Σ total_paid ÷ Σ order_count) over the newest N
 * payments by paid_date — a sum over a sum, not an average of each payment's
 * own rate. The headline figure is always the API's; these only rebuild its
 * arithmetic and preview a new payment.
 */

import type { PostageBatch } from "@/lib/api"
// Relative .ts imports so `npm test` (node --test) can load this module.
import { roundHalfEven } from "../../lib/costing.ts"
import { utcToLocal } from "../../lib/jalali.ts"

export type Sums = { total: number; orders: number }

export function sums(batches: { total_paid: number; order_count: number }[]): Sums {
  return batches.reduce((s, b) => ({ total: s.total + b.total_paid, orders: s.orders + b.order_count }), { total: 0, orders: 0 })
}

/** One payment's own per-order figure (display only). */
export const rateOf = (total: number, orders: number) => roundHalfEven(total / orders)

/**
 * The payments the current estimate uses: the API lists them newest first
 * (paid_date DESC, id DESC), exactly the estimate's order, so it's the first N.
 */
export const windowOf = (batches: PostageBatch[], n: number) => batches.slice(0, n)

export type Projection = {
  estimate: number
  /** Payments in the new window, the new one marked. */
  window: { total_paid: number; order_count: number; isNew: boolean; paid_date: string | null }[]
  /** The old-window payment pushed out, if any. */
  dropped: PostageBatch | null
  /** The new payment falls outside the newest N (backdated). */
  outside: boolean
}

/**
 * Where a new payment would land and what the estimate would become. Dated
 * today → it's the newest (the server stamps now). Backdated → stored as that
 * local day's midnight, so it sorts after that day's payments recorded at a
 * time, and before (higher id) any other midnight of the same day.
 */
export function project(
  batches: PostageBatch[],
  n: number,
  payment: { total: number; orders: number; day: string | null },
  timeZone: string
): Projection {
  let index = 0
  if (payment.day != null) {
    index = batches.findIndex((b) => {
      const local = utcToLocal(b.paid_date, timeZone)
      if (!local) return false
      return local.iso < payment.day! || (local.iso === payment.day && local.time === "00:00")
    })
    if (index === -1) index = batches.length
  }
  const entry = { total_paid: payment.total, order_count: payment.orders, isNew: true, paid_date: null }
  const ordered = [
    ...batches.slice(0, index).map((b) => ({ ...b, isNew: false })),
    entry,
    ...batches.slice(index).map((b) => ({ ...b, isNew: false })),
  ]
  const window = ordered.slice(0, n)
  const s = sums(window)
  const outside = index >= n
  return {
    estimate: roundHalfEven(s.total / s.orders),
    window,
    dropped: !outside && batches.length >= n ? batches[n - 1] : null,
    outside,
  }
}
