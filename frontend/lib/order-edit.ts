/**
 * «ویرایش سفارش»: the light edit of an order in place (docs/accounting-rules.md section 20, "Light edit";
 * PATCH /orders/{id}). Which fields the order can take, the body of only the changed fields, the paid day
 * proposed when the order day moves, and how to read a refusal. Dependency-free so `npm test` can run it.
 * Money is integer Rial; days are Gregorian "YYYY-MM-DD" store days (the caller turns the stored moment into a
 * day with lib/jalali.ts `utcToLocal`). The server decides; these rules only keep the form honest.
 */

import { detailNum, detailStr, hasCode, type CodedError, type ErrorCode } from "./error-codes.ts"

/** The order fields the edit reads (OrderDetailOut.order, only these). */
export type EditableOrder = {
  status: string
  stock_committed: number
  settlement_id: number | null
  payment_method_id: number | null
  payment_reference: string | null
  paid_date: string | null
  shipping_charge: number
  postage_cost: number
  customer_name: string | null
  notes: string | null
}

export type EditForm = {
  orderDate: string
  /** null only on an order from before a method was required; the form then has none chosen. */
  paymentMethodId: number | null
  paymentReference: string
  /** "" when the order is not paid. */
  paidDate: string
  /** Integer Rial; null = the MoneyInput holds no exact amount (blocks saving). */
  shipping: number | null
  postage: number | null
  customerName: string
  notes: string
}

/** The body of PATCH /orders/{id} and POST /orders/{id}/edit-preview. */
export type EditBody = {
  order_date?: string
  payment_method_id?: number
  payment_reference?: string | null
  paid_date?: string
  shipping_charge?: number
  postage_cost?: number
  customer_name?: string | null
  notes?: string | null
}

/** Which fields the order can take now (before the server's closed-day and month checks). */
export type EditLocks = {
  /** Nothing at all: a VOIDED order. */
  none: boolean
  /** order_date, payment method, shipping: a committed PENDING / PAID / COMPLETED order, not settled. */
  money: boolean
  /** postage_cost: as money, but a settled order still takes it. */
  postage: boolean
  /** paid_date: a paid order, not settled. */
  paidDate: boolean
}

const ELIGIBLE = ["PENDING", "PAID", "COMPLETED"]
const PAID = ["PAID", "COMPLETED"]

export function editLocks(order: Pick<EditableOrder, "status" | "stock_committed" | "settlement_id">): EditLocks {
  if (order.status === "VOIDED") return { none: true, money: false, postage: false, paidDate: false }
  const committed = ELIGIBLE.includes(order.status) && order.stock_committed === 1
  const settled = order.settlement_id != null
  return {
    none: false,
    money: committed && !settled,
    postage: committed,
    paidDate: PAID.includes(order.status) && !settled,
  }
}

/** The order may be edited at all (the button shows). */
export const canEdit = (order: { status: string }) => order.status !== "VOIDED"

/** The form as the order stands. `orderDay` is the order's store day. */
export function editFormFrom(order: EditableOrder, orderDay: string): EditForm {
  return {
    orderDate: orderDay,
    paymentMethodId: order.payment_method_id,
    paymentReference: order.payment_reference ?? "",
    paidDate: order.paid_date ?? "",
    shipping: order.shipping_charge,
    postage: order.postage_cost,
    customerName: order.customer_name ?? "",
    notes: order.notes ?? "",
  }
}

const text = (s: string): string | null => (s.trim() === "" ? null : s.trim())

/**
 * Only the fields that differ from `initial`: what PATCH sends (omitted = unchanged). Text is compared trimmed,
 * blank = none. A money field holding no exact amount (null) is left out; `formBlocked` says so.
 */
export function editBody(initial: EditForm, form: EditForm): EditBody {
  const body: EditBody = {}
  if (form.orderDate !== initial.orderDate) body.order_date = form.orderDate
  if (form.paymentMethodId != null && form.paymentMethodId !== initial.paymentMethodId) {
    body.payment_method_id = form.paymentMethodId
  }
  if (form.paidDate !== "" && form.paidDate !== initial.paidDate) body.paid_date = form.paidDate
  if (form.shipping != null && form.shipping !== initial.shipping) body.shipping_charge = form.shipping
  if (form.postage != null && form.postage !== initial.postage) body.postage_cost = form.postage
  for (const [key, field] of [
    ["payment_reference", "paymentReference"],
    ["customer_name", "customerName"],
    ["notes", "notes"],
  ] as const) {
    if (text(form[field]) !== text(initial[field])) body[key] = text(form[field])
  }
  return body
}

/** Saving is blocked: a money field holds no exact amount. */
export const formBlocked = (form: EditForm) => form.shipping === null || form.postage === null

/**
 * When the order day moves, the paid day follows if it was the order's own day and the user has not moved it:
 * a wrong order date is usually a wrong payment day too. Returns the paid day to show.
 */
export function proposedPaidDate(initial: EditForm, form: EditForm, nextOrderDate: string): string {
  const followed = initial.paidDate !== "" && initial.paidDate === initial.orderDate && form.paidDate === form.orderDate
  return followed ? nextOrderDate : form.paidDate
}

/** Why an edit (or its preview blocker) is refused, read from its code and details. */
export type EditRefusal =
  | { kind: "voided" }
  | { kind: "notAllowed"; status: string }
  | { kind: "notPaid" }
  | { kind: "settled"; settlementId: number | null }
  | { kind: "closed"; periodEnd: string; date: string }
  | { kind: "month"; jalaliYear: number | null; jalaliMonth: number | null }

export function editRefusal(e: CodedError): EditRefusal | null {
  if (e.status !== 409) return null
  if (hasCode(e, "ORDER_ALREADY_VOIDED")) return { kind: "voided" }
  if (hasCode(e, "ORDER_EDIT_NOT_ALLOWED")) return { kind: "notAllowed", status: detailStr(e, "status") ?? "" }
  if (hasCode(e, "ORDER_NOT_PAID")) return { kind: "notPaid" }
  if (hasCode(e, "ORDER_ALREADY_SETTLED")) return { kind: "settled", settlementId: detailNum(e, "settlement_id") }
  if (hasCode(e, "PERIOD_ALREADY_DISTRIBUTED")) {
    const periodEnd = detailStr(e, "period_end")
    if (periodEnd == null) return null
    return { kind: "closed", periodEnd, date: detailStr(e, "date") ?? periodEnd }
  }
  if (hasCode(e, "MONTH_ALREADY_SETTLED")) {
    return { kind: "month", jalaliYear: detailNum(e, "jalali_year"), jalaliMonth: detailNum(e, "jalali_month") }
  }
  return null
}

/** An edit-preview blocker ({code, details}) read like the 409 the edit would answer with. */
export function editBlockerRefusal(blocker: { code: string; details: Record<string, unknown> }): EditRefusal | null {
  return editRefusal({ status: 409, code: blocker.code as ErrorCode, details: blocker.details })
}

/** The fields shown in the before → after table, in the order the server lists them. */
export const EDIT_FIELDS = [
  "order_date",
  "payment_method_id",
  "transaction_fee",
  "payment_reference",
  "paid_date",
  "shipping_charge",
  "postage_cost",
  "customer_name",
  "notes",
] as const
export type EditField = (typeof EDIT_FIELDS)[number]
export const MONEY_FIELDS: readonly string[] = ["transaction_fee", "shipping_charge", "postage_cost"]
export const DAY_FIELDS: readonly string[] = ["order_date", "paid_date"]
