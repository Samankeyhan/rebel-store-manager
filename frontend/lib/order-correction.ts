/**
 * Voiding and correcting a sale entered by mistake (docs/accounting-rules.md section 20): the record-sale
 * prefill from the old order, how to read a refusal (a void's 409/422, or a void-preview blocker), and which
 * orders the list shows. Dependency-free so `npm test` can run it. Money is integer Rial; days are Gregorian
 * "YYYY-MM-DD" store days (the caller turns the stored moment into a day with lib/jalali.ts `utcToLocal`).
 */

import { detailNum, detailStr, hasCode, type CodedError, type ErrorCode } from "./error-codes.ts"

/** The order the prefill reads (OrderDetailOut, only the fields used). */
export type CorrectedOrder = {
  order: {
    channel: string
    customer_name: string | null
    shipping_charge: number
    packaging_kit_id: number | null
    payment_method_id: number | null
    payment_reference: string | null
    status: string
    paid_date: string | null
    notes: string | null
  }
  items: { product_id: number; quantity: number; list_unit_price: number; discount_amount: number; discount_reason: string | null }[]
}

export type CorrectionStatus = "PENDING" | "PAID" | "COMPLETED"

export type CorrectionPrefill = {
  channel: string
  customerName: string
  /** unitPrice is the list unit price (what the customer saw); a discount stays a discount. */
  lines: { productId: number; qty: number; unitPrice: number; discount: number; discountReason: string }[]
  /** The old shipping charge, as an override (0 is a real zero). */
  shipping: number
  kit: { kind: "none" } | { kind: "kit"; id: number }
  payment: { kind: "none" } | { kind: "method"; id: number }
  reference: string
  status: CorrectionStatus
  /** The old order's own day: a correction usually keeps it. */
  orderDate: string
  /** The old payment day when it differs from the order's day; null = follow the order (the server default). */
  paidDate: string | null
  /** Carried into the new order unchanged (the form has no notes field). */
  notes: string | null
}

const CORRECTION_STATUSES: readonly string[] = ["PENDING", "PAID", "COMPLETED"]
const PAID = ["PAID", "COMPLETED"]

/** The record-sale form, filled from the order being corrected. `orderDay` is that order's store day. */
export function correctionPrefill(detail: CorrectedOrder, orderDay: string): CorrectionPrefill {
  const o = detail.order
  const status = (CORRECTION_STATUSES.includes(o.status) ? o.status : "COMPLETED") as CorrectionStatus
  const paidDate = PAID.includes(status) && o.paid_date && o.paid_date !== orderDay ? o.paid_date : null
  return {
    channel: o.channel,
    customerName: o.customer_name ?? "",
    lines: detail.items.map((i) => ({
      productId: i.product_id,
      qty: i.quantity,
      unitPrice: i.list_unit_price,
      discount: i.discount_amount,
      discountReason: i.discount_reason ?? "",
    })),
    shipping: o.shipping_charge,
    kit: o.packaging_kit_id == null ? { kind: "none" } : { kind: "kit", id: o.packaging_kit_id },
    payment: o.payment_method_id == null ? { kind: "none" } : { kind: "method", id: o.payment_method_id },
    reference: o.payment_reference ?? "",
    status,
    orderDate: orderDay,
    paidDate,
    notes: o.notes,
  }
}

/** Why a void (or a correction's void) is refused, read from its code and details. */
export type VoidRefusal =
  | { kind: "voided"; replacedBy: number | null }
  | { kind: "returned"; status: string }
  | { kind: "draft" }
  | { kind: "settled"; settlementId: number | null }
  | { kind: "closed"; periodEnd: string; date: string }
  | { kind: "stocktake"; itemName: string; stocktakeDate: string }
  | { kind: "reason" }

export function voidRefusal(e: CodedError): VoidRefusal | null {
  if (e.status === 422 && hasCode(e, "VOID_REASON_REQUIRED")) return { kind: "reason" }
  if (e.status !== 409) return null
  if (hasCode(e, "ORDER_ALREADY_VOIDED")) return { kind: "voided", replacedBy: detailNum(e, "replaced_by_order_id") }
  if (hasCode(e, "ORDER_HAS_RETURN")) return { kind: "returned", status: detailStr(e, "status") ?? "" }
  if (hasCode(e, "ORDER_NOT_COMMITTED")) return { kind: "draft" }
  if (hasCode(e, "ORDER_ALREADY_SETTLED")) return { kind: "settled", settlementId: detailNum(e, "settlement_id") }
  if (hasCode(e, "PERIOD_ALREADY_DISTRIBUTED")) {
    const periodEnd = detailStr(e, "period_end")
    if (periodEnd == null) return null
    return { kind: "closed", periodEnd, date: detailStr(e, "date") ?? periodEnd }
  }
  if (hasCode(e, "STOCKTAKE_AFTER_SALE")) {
    return { kind: "stocktake", itemName: detailStr(e, "item_name") ?? "", stocktakeDate: detailStr(e, "stocktake_date") ?? "" }
  }
  return null
}

/** A void-preview blocker ({code, details}) read like the 409 a void would answer with. */
export function blockerRefusal(blocker: { code: string; details: Record<string, unknown> }): VoidRefusal | null {
  return voidRefusal({ status: 409, code: blocker.code as ErrorCode, details: blocker.details })
}

/** The orders list: «همه» (filter "") leaves VOIDED orders out; the «باطل‌شده» tab shows only them. */
export function listedUnder(status: string, filter: string): boolean {
  return filter === "" ? status !== "VOIDED" : status === filter
}

/** The order may be voided or corrected from the detail screen (the server still decides; the preview names a refusal). */
export function canVoid(order: { status: string; stock_committed: number }): boolean {
  return CORRECTION_STATUSES.includes(order.status) && order.stock_committed === 1
}

/** The void-preview figures the form preview needs (VoidPreviewOut, only these fields). */
export type VoidReturns = {
  products: { item_id: number; quantity: number; unit_cost_after: number | null }[]
  materials: { item_id: number; quantity: number; unit_cost_after: number | null }[]
}

/**
 * The catalog as the corrected sale will meet it: the void runs first, in the same operation, so the
 * stock it returns is available and each item's cost is the one after the void (what the server reports
 * in the void-preview). Only the form's preview reads this; the server checks stock itself.
 */
export function catalogAfterVoid<
  P extends { id: number; current_stock: number | null; unit_cost: number | null },
  M extends { id: number; current_stock: number | null; unit_cost: number },
  C extends { products: P[]; materials: M[] },
>(catalog: C, returns: VoidReturns): C {
  const back = (rows: VoidReturns["products"]) => new Map(rows.map((r) => [r.item_id, r]))
  const products = back(returns.products)
  const materials = back(returns.materials)
  return {
    ...catalog,
    products: catalog.products.map((p) => {
      const r = products.get(p.id)
      return r ? { ...p, current_stock: (p.current_stock ?? 0) + r.quantity, unit_cost: r.unit_cost_after ?? p.unit_cost } : p
    }),
    materials: catalog.materials.map((m) => {
      const r = materials.get(m.id)
      return r ? { ...m, current_stock: (m.current_stock ?? 0) + r.quantity, unit_cost: r.unit_cost_after ?? m.unit_cost } : m
    }),
  }
}
