// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  blockerRefusal,
  canChange,
  cancelGate,
  cancelRefusal,
  catalogAfterCancel,
  correctionPrefill,
  parseShowCancelled,
  remainderAfterPaid,
} from "./purchase-correction.ts"

const err = (status, code, details = {}) => ({ status, code, details, message: "ignored" })

test("correctionPrefill fills the form from the invoice: supplier (0 = none), day, note and every line", () => {
  const prefill = correctionPrefill(
    {
      supplier_id: null,
      notes: null,
      payment_status: "PAID",
      lines: [
        { kind: "MATERIAL", item_id: 4, quantity_bought: 2.5, total_paid: 1000 },
        { kind: "PRODUCT", item_id: 9, quantity_bought: 3, total_paid: 900 },
      ],
    },
    "2026-10-10"
  )
  assert.deepEqual(prefill, {
    supplierId: 0,
    date: "2026-10-10",
    note: "",
    payMode: "FULL",
    lines: [{ pick: 4, qty: 2.5, total: 1000 }, { pick: -9, qty: 3, total: 900 }],
  })
  const credit = correctionPrefill({ supplier_id: 7, notes: "n", payment_status: "PARTIAL", lines: [] }, "2026-10-01")
  assert.deepEqual([credit.supplierId, credit.note, credit.payMode], [7, "n", "NONE"])
})

test("cancelRefusal reads every refusal by code and details, never the message", () => {
  assert.deepEqual(cancelRefusal(err(422, "VOID_REASON_REQUIRED")), { kind: "reason" })
  assert.deepEqual(cancelRefusal(err(422, "PURCHASE_CORRECTION_BELOW_PAID", { paid: 4000, new_total: 3000 })), {
    kind: "below_paid", paid: 4000, newTotal: 3000,
  })
  assert.deepEqual(cancelRefusal(err(409, "PURCHASE_ALREADY_CANCELLED", { replaced_by_purchase_id: 5 })), { kind: "cancelled", replacedBy: 5 })
  assert.deepEqual(cancelRefusal(err(409, "PURCHASE_HAS_PAYMENTS", { paid: 100, shared: 1, payment_ids: [3, "x", 4] })), {
    kind: "payments", paid: 100, shared: true, paymentIds: [3, 4],
  })
  assert.deepEqual(cancelRefusal(err(409, "PERIOD_ALREADY_DISTRIBUTED", { period_end: "2026-10-05", date: "2026-10-04" })), {
    kind: "closed", periodEnd: "2026-10-05", date: "2026-10-04",
  })
  assert.deepEqual(cancelRefusal(err(409, "PURCHASE_STOCK_USED", { item_name: "کاغذ", current_stock: 9, quantity_bought: 10 })), {
    kind: "stock_used", itemName: "کاغذ", currentStock: 9, quantity: 10,
  })
  assert.deepEqual(cancelRefusal(err(409, "STOCKTAKE_AFTER_PURCHASE", { item_name: "کاغذ", stocktake_date: "2026-10-12" })), {
    kind: "stocktake", itemName: "کاغذ", stocktakeDate: "2026-10-12",
  })
  assert.deepEqual(cancelRefusal(err(409, "PURCHASE_COST_HISTORY_UNKNOWN", { item_name: "کاغذ" })), { kind: "history", itemName: "کاغذ" })
  assert.equal(cancelRefusal(err(409, "ORDER_ALREADY_VOIDED")), null)
  assert.equal(cancelRefusal(err(500, "PURCHASE_STOCK_USED")), null)
})

test("a later cost event names the later purchases; a cost set without a movement says so", () => {
  const r = blockerRefusal({
    code: "PURCHASE_COST_CHANGED_SINCE",
    details: {
      item_name: "کاغذ",
      later: [{ reason: "PURCHASE", movement_id: 9, date: "2026-10-11 08:00:00", purchase_id: 4, invoice_number: "PUR-000004" }, "junk"],
      cost_changed_without_movement: 0,
    },
  })
  assert.deepEqual(r, {
    kind: "cost_changed",
    itemName: "کاغذ",
    later: [{ reason: "PURCHASE", date: "2026-10-11 08:00:00", purchaseId: 4, invoiceNumber: "PUR-000004" }],
    withoutMovement: false,
  })
  assert.equal(blockerRefusal({ code: "PURCHASE_COST_CHANGED_SINCE", details: { cost_changed_without_movement: 1 } }).withoutMovement, true)
})

test("cancelGate: payments wholly on the purchase need the tick; a shared one or another blocker never", () => {
  const payments = { code: "PURCHASE_HAS_PAYMENTS", details: {} }
  const clean = { blockers: [], payments: [] }
  assert.deepEqual(cancelGate(clean, false), { needsTick: false, shared: false, canConfirm: true })
  const sole = { blockers: [payments], payments: [{ shared: 0 }, { shared: 0 }] }
  assert.deepEqual(cancelGate(sole, false), { needsTick: true, shared: false, canConfirm: false })
  assert.deepEqual(cancelGate(sole, true), { needsTick: true, shared: false, canConfirm: true })
  const shared = { blockers: [payments], payments: [{ shared: 0 }, { shared: 1 }] }
  assert.deepEqual(cancelGate(shared, true), { needsTick: false, shared: true, canConfirm: false })
  const blocked = { blockers: [payments, { code: "PURCHASE_STOCK_USED", details: {} }], payments: [{ shared: 0 }] }
  assert.equal(cancelGate(blocked, true).canConfirm, false)
})

test("the cancelled toggle, which purchases can change, and the correction remainder", () => {
  assert.equal(parseShowCancelled("1"), true)
  assert.equal(parseShowCancelled("true"), false)
  assert.equal(parseShowCancelled(null), false)
  assert.equal(canChange({ status: "ACTIVE" }), true)
  assert.equal(canChange({ status: "CANCELLED" }), false)
  assert.equal(remainderAfterPaid(5000, 1500), 3500)
  assert.equal(remainderAfterPaid(1000, 1500), 0)
  assert.equal(remainderAfterPaid(null, 0), null)
})

test("catalogAfterCancel: the old invoice's items get the stock and cost the cancel leaves; others are untouched", () => {
  const materials = [
    { id: 1, current_stock: 10, unit_cost: 400 },
    { id: 2, current_stock: null, unit_cost: 200 },
    { id: 3, current_stock: 5, unit_cost: 90 },
  ]
  const products = [{ id: 1, current_stock: 3, unit_cost: 300 }]
  const after = catalogAfterCancel(materials, products, [
    { kind: "MATERIAL", item_id: 1, stock_after: 0, cost_after: 0 },
    { kind: "MATERIAL", item_id: 2, stock_after: null, cost_after: 70 },
    { kind: "PRODUCT", item_id: 1, stock_after: 0, cost_after: null },
  ])
  assert.deepEqual(after.materials, [
    { id: 1, current_stock: 0, unit_cost: 0 },
    { id: 2, current_stock: null, unit_cost: 70 },
    { id: 3, current_stock: 5, unit_cost: 90 },
  ])
  assert.deepEqual(after.products, [{ id: 1, current_stock: 0, unit_cost: null }])
  assert.equal(after.materials[2], materials[2])
})
