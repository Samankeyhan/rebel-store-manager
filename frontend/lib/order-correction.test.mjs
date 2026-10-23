// Run with `npm test`. Voiding / correcting a sale: the record-sale prefill, the refusals, the list filter.
import { test } from "node:test"
import assert from "node:assert/strict"
import { blockerRefusal, canVoid, correctionPrefill, listedUnder, voidRefusal } from "./order-correction.ts"

const detail = {
  order: {
    channel: "INSTAGRAM",
    customer_name: "مشتری الف",
    shipping_charge: 1_800_000,
    packaging_kit_id: 4,
    payment_method_id: 2,
    payment_reference: "ZP-1",
    status: "PAID",
    paid_date: "2026-10-10",
    notes: "یادداشت",
  },
  items: [
    { product_id: 7, quantity: 2, list_unit_price: 300_000, discount_amount: 50_000, discount_reason: "دوستانه" },
    { product_id: 9, quantity: 1, list_unit_price: 120_005, discount_amount: 0, discount_reason: null },
  ],
}

test("correctionPrefill: every field of the old order, the list unit price, the shipping as an override", () => {
  const p = correctionPrefill(detail, "2026-10-10")
  assert.deepEqual(p, {
    channel: "INSTAGRAM",
    customerName: "مشتری الف",
    lines: [
      { productId: 7, qty: 2, unitPrice: 300_000, discount: 50_000, discountReason: "دوستانه" },
      { productId: 9, qty: 1, unitPrice: 120_005, discount: 0, discountReason: "" },
    ],
    shipping: 1_800_000,
    kit: { kind: "kit", id: 4 },
    payment: { kind: "method", id: 2 },
    reference: "ZP-1",
    status: "PAID",
    orderDate: "2026-10-10",
    paidDate: null,
    notes: "یادداشت",
  })
})

test("correctionPrefill: no kit, no method, no customer become explicit «none» / empty", () => {
  const o = { ...detail.order, packaging_kit_id: null, payment_method_id: null, customer_name: null, payment_reference: null }
  const p = correctionPrefill({ ...detail, order: o }, "2026-10-10")
  assert.deepEqual([p.kit, p.payment, p.customerName, p.reference], [{ kind: "none" }, { kind: "none" }, "", ""])
})

test("correctionPrefill: a payment day other than the order day is kept; an unpaid order has none", () => {
  assert.equal(correctionPrefill(detail, "2026-10-08").paidDate, "2026-10-10")
  const pending = { ...detail.order, status: "PENDING", paid_date: null }
  assert.equal(correctionPrefill({ ...detail, order: pending }, "2026-10-08").paidDate, null)
  assert.equal(correctionPrefill({ ...detail, order: pending }, "2026-10-08").status, "PENDING")
})

test("correctionPrefill: a status a correction cannot have becomes COMPLETED", () => {
  assert.equal(correctionPrefill({ ...detail, order: { ...detail.order, status: "DRAFT" } }, "2026-10-10").status, "COMPLETED")
})

test("voidRefusal: each code with its details", () => {
  const e = (code, details = {}, status = 409) => voidRefusal({ status, code, details })
  assert.deepEqual(e("ORDER_ALREADY_VOIDED", { order_id: 1, voided_at: "x", replaced_by_order_id: 5 }), { kind: "voided", replacedBy: 5 })
  assert.deepEqual(e("ORDER_HAS_RETURN", { status: "REFUNDED" }), { kind: "returned", status: "REFUNDED" })
  assert.deepEqual(e("ORDER_NOT_COMMITTED", { status: "DRAFT" }), { kind: "draft" })
  assert.deepEqual(e("ORDER_ALREADY_SETTLED", { settlement_id: 3 }), { kind: "settled", settlementId: 3 })
  assert.deepEqual(e("PERIOD_ALREADY_DISTRIBUTED", { period_end: "2026-09-30", date: "2026-09-12" }), {
    kind: "closed", periodEnd: "2026-09-30", date: "2026-09-12",
  })
  assert.deepEqual(e("STOCKTAKE_AFTER_SALE", { item_name: "کاغذ", stocktake_date: "2026-10-15" }), {
    kind: "stocktake", itemName: "کاغذ", stocktakeDate: "2026-10-15",
  })
  assert.deepEqual(e("VOID_REASON_REQUIRED", {}, 422), { kind: "reason" })
})

test("voidRefusal: anything else is not a void refusal", () => {
  assert.equal(voidRefusal({ status: 409, code: "CONFLICT", details: {} }), null)
  assert.equal(voidRefusal({ status: 422, code: "ORDER_HAS_RETURN", details: {} }), null)
  assert.equal(voidRefusal({ status: 409, code: "PERIOD_ALREADY_DISTRIBUTED", details: {} }), null)
})

test("blockerRefusal reads a void-preview blocker like the 409", () => {
  assert.deepEqual(blockerRefusal({ code: "ORDER_ALREADY_SETTLED", details: { order_id: 1, settlement_id: 9 } }), {
    kind: "settled", settlementId: 9,
  })
})

test("listedUnder: «همه» hides VOIDED, its own tab shows only VOIDED", () => {
  assert.equal(listedUnder("COMPLETED", ""), true)
  assert.equal(listedUnder("VOIDED", ""), false)
  assert.equal(listedUnder("VOIDED", "VOIDED"), true)
  assert.equal(listedUnder("COMPLETED", "VOIDED"), false)
  assert.equal(listedUnder("CANCELLED", "CANCELLED"), true)
})

test("canVoid: committed PENDING / PAID / COMPLETED orders only", () => {
  assert.equal(canVoid({ status: "COMPLETED", stock_committed: 1 }), true)
  assert.equal(canVoid({ status: "PENDING", stock_committed: 1 }), true)
  for (const status of ["DRAFT", "CANCELLED", "REFUNDED", "VOIDED"]) assert.equal(canVoid({ status, stock_committed: 1 }), false)
  assert.equal(canVoid({ status: "PAID", stock_committed: 0 }), false)
})
