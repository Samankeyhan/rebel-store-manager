/**
 * Editing, cancelling and correcting a purchase entered by mistake (docs/accounting-rules.md section 23): the
 * correction form's prefill from the old invoice, how to read a refusal (a cancel's 409/422, or a cancel-preview
 * blocker), the payment tick of the cancel dialog, and which purchases the list shows. Dependency-free so `npm test`
 * can run it. Money is integer Rial; days are Gregorian "YYYY-MM-DD" store days (the caller turns the stored moment
 * into a day with lib/jalali.ts `utcToLocal`).
 */

import { detailNum, detailStr, hasCode, type CodedError, type ErrorCode } from "./error-codes.ts"
import { pickId, type ItemKind } from "./purchase-lines.ts"

/** The invoice the prefill reads (PurchaseDetailOut, only the fields used). */
export type CorrectedPurchase = {
  supplier_id: number | null
  notes: string | null
  payment_status: "UNPAID" | "PARTIAL" | "PAID"
  lines: { kind: ItemKind; item_id: number; quantity_bought: number; total_paid: number }[]
}

export type PurchasePrefill = {
  /** 0 = no supplier (the form's "none" option). */
  supplierId: number
  date: string
  note: string
  /** A paid purchase stays paid (FULL pays what a larger total adds); otherwise nothing more is paid now (NONE). */
  payMode: "FULL" | "NONE"
  lines: { pick: number; qty: number; total: number }[]
}

/** The purchase form, filled from the invoice being corrected. `purchaseDay` is its store day (a correction usually keeps it). */
export function correctionPrefill(detail: CorrectedPurchase, purchaseDay: string): PurchasePrefill {
  return {
    supplierId: detail.supplier_id ?? 0,
    date: purchaseDay,
    note: detail.notes ?? "",
    payMode: detail.payment_status === "PAID" ? "FULL" : "NONE",
    lines: detail.lines.map((l) => ({ pick: pickId(l.kind, l.item_id), qty: l.quantity_bought, total: l.total_paid })),
  }
}

/** Why a cancel (or a correction) is refused, read from its code and details. */
export type CancelRefusal =
  | { kind: "cancelled"; replacedBy: number | null }
  | { kind: "payments"; paid: number | null; shared: boolean; paymentIds: number[] }
  | { kind: "closed"; periodEnd: string; date: string }
  | { kind: "stock_used"; itemName: string; currentStock: number | null; quantity: number | null }
  | { kind: "stocktake"; itemName: string; stocktakeDate: string }
  | { kind: "cost_changed"; itemName: string; later: LaterEvent[]; withoutMovement: boolean }
  | { kind: "history"; itemName: string }
  | { kind: "below_paid"; paid: number | null; newTotal: number | null }
  | { kind: "reason" }

export type LaterEvent = { reason: string; date: string; purchaseId: number | null; invoiceNumber: string | null }

function laterEvents(value: unknown): LaterEvent[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((v) => {
    if (typeof v !== "object" || v == null) return []
    const e = v as Record<string, unknown>
    return [{
      reason: typeof e.reason === "string" ? e.reason : "",
      date: typeof e.date === "string" ? e.date : "",
      purchaseId: typeof e.purchase_id === "number" ? e.purchase_id : null,
      invoiceNumber: typeof e.invoice_number === "string" ? e.invoice_number : null,
    }]
  })
}

export function cancelRefusal(e: CodedError): CancelRefusal | null {
  if (e.status === 422 && hasCode(e, "VOID_REASON_REQUIRED")) return { kind: "reason" }
  if (e.status === 422 && hasCode(e, "PURCHASE_CORRECTION_BELOW_PAID"))
    return { kind: "below_paid", paid: detailNum(e, "paid"), newTotal: detailNum(e, "new_total") }
  if (e.status !== 409) return null
  const itemName = detailStr(e, "item_name") ?? ""
  if (hasCode(e, "PURCHASE_ALREADY_CANCELLED")) return { kind: "cancelled", replacedBy: detailNum(e, "replaced_by_purchase_id") }
  if (hasCode(e, "PURCHASE_HAS_PAYMENTS")) {
    const ids = e.details?.payment_ids
    return {
      kind: "payments",
      paid: detailNum(e, "paid"),
      shared: detailNum(e, "shared") === 1,
      paymentIds: Array.isArray(ids) ? ids.filter((i): i is number => typeof i === "number") : [],
    }
  }
  if (hasCode(e, "PERIOD_ALREADY_DISTRIBUTED")) {
    const periodEnd = detailStr(e, "period_end")
    if (periodEnd == null) return null
    return { kind: "closed", periodEnd, date: detailStr(e, "date") ?? periodEnd }
  }
  if (hasCode(e, "PURCHASE_STOCK_USED"))
    return { kind: "stock_used", itemName, currentStock: detailNum(e, "current_stock"), quantity: detailNum(e, "quantity_bought") }
  if (hasCode(e, "STOCKTAKE_AFTER_PURCHASE")) return { kind: "stocktake", itemName, stocktakeDate: detailStr(e, "stocktake_date") ?? "" }
  if (hasCode(e, "PURCHASE_COST_CHANGED_SINCE"))
    return { kind: "cost_changed", itemName, later: laterEvents(e.details?.later), withoutMovement: detailNum(e, "cost_changed_without_movement") === 1 }
  if (hasCode(e, "PURCHASE_COST_HISTORY_UNKNOWN")) return { kind: "history", itemName }
  return null
}

/** A cancel-preview blocker ({code, details}) read like the 409 a cancel would answer with. */
export function blockerRefusal(blocker: { code: string; details: Record<string, unknown> }): CancelRefusal | null {
  return cancelRefusal({ status: 409, code: blocker.code as ErrorCode, details: blocker.details })
}

/**
 * Whether the cancel button may be pressed (owner edit E3): no blocker other than the payments; payments that are
 * all wholly on this purchase go only after the tick «پرداخت‌های این خرید هم حذف شوند»; a shared payment never.
 * `needsTick`: the dialog shows the payments and the checkbox.
 */
export function cancelGate(
  preview: { blockers: { code: string; details: Record<string, unknown> }[]; payments: { shared: number }[] },
  ticked: boolean
): { needsTick: boolean; shared: boolean; canConfirm: boolean } {
  const others = preview.blockers.filter((b) => b.code !== "PURCHASE_HAS_PAYMENTS")
  const shared = preview.payments.some((p) => p.shared === 1)
  const needsTick = preview.payments.length > 0 && !shared
  return { needsTick, shared, canConfirm: others.length === 0 && !shared && (!needsTick || ticked) }
}

/** The purchases list shows cancelled purchases only with the toggle «نمایش خریدهای باطل‌شده» (`?cancelled=1`). */
export function parseShowCancelled(value: string | null): boolean {
  return value === "1"
}

/** A purchase can be edited, cancelled or corrected from its sheet only while ACTIVE (the server still decides). */
export function canChange(purchase: { status: string }): boolean {
  return purchase.status === "ACTIVE"
}

/** The part of a correction's new total the form's payment is about: what is not yet paid (never below 0). */
export function remainderAfterPaid(total: number | null, paid: number): number | null {
  if (total === null) return null
  return Math.max(total - paid, 0)
}

/** The cancel-preview lines `catalogAfterCancel` reads. */
export type CancelLines = { kind: ItemKind; item_id: number; stock_after: number | null; cost_after: number | null }[]

/**
 * The catalog as the corrected purchase will meet it: the cancel runs first, in the same operation, so each item of
 * the old invoice has the stock and the unit cost the cancel-preview reports after it (a product's cost may go back
 * to none). Only the form's cost preview reads this; the server computes the real figures.
 */
export function catalogAfterCancel<
  P extends { id: number; current_stock: number | null; unit_cost: number | null },
  M extends { id: number; current_stock: number | null; unit_cost: number },
>(materials: M[], products: P[], lines: CancelLines): { materials: M[]; products: P[] } {
  const of = (kind: ItemKind) => new Map(lines.filter((l) => l.kind === kind).map((l) => [l.item_id, l]))
  const material = of("MATERIAL")
  const product = of("PRODUCT")
  return {
    materials: materials.map((m) => {
      const l = material.get(m.id)
      return l ? { ...m, current_stock: l.stock_after ?? m.current_stock, unit_cost: l.cost_after ?? m.unit_cost } : m
    }),
    products: products.map((p) => {
      const l = product.get(p.id)
      return l ? { ...p, current_stock: l.stock_after ?? p.current_stock, unit_cost: l.cost_after } : p
    }),
  }
}
