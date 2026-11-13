// Run with `npm test`. The light order edit: locks, the changed-fields body, the proposed paid day, refusals.
import { test } from "node:test"
import assert from "node:assert/strict"
import { canEdit, editBlockerRefusal, editBody, editFormFrom, editLocks, editRefusal, formBlocked, proposedPaidDate } from "./order-edit.ts"

const order = {
  status: "PAID",
  stock_committed: 1,
  settlement_id: null,
  payment_method_id: 3,
  payment_reference: null,
  paid_date: "2026-10-25",
  shipping_charge: 1_800_000,
  postage_cost: 1_250_000,
  customer_name: "مشتری الف",
  notes: null,
}

test("locks follow status, commit and settlement", () => {
  assert.deepEqual(editLocks(order), { none: false, money: true, postage: true, paidDate: true })
  assert.deepEqual(editLocks({ ...order, settlement_id: 4 }), { none: false, money: false, postage: true, paidDate: false })
  assert.deepEqual(editLocks({ ...order, status: "PENDING" }), { none: false, money: true, postage: true, paidDate: false })
  for (const status of ["DRAFT", "CANCELLED", "REFUNDED"]) {
    assert.deepEqual(editLocks({ ...order, status }), { none: false, money: false, postage: false, paidDate: false })
  }
  assert.equal(editLocks({ ...order, status: "VOIDED" }).none, true)
  assert.equal(canEdit({ status: "VOIDED" }), false)
  assert.equal(canEdit({ status: "CANCELLED" }), true)
})

test("an untouched form sends nothing", () => {
  const initial = editFormFrom(order, "2026-10-25")
  assert.deepEqual(editBody(initial, { ...initial }), {})
  assert.deepEqual(editBody(initial, { ...initial, customerName: "  مشتری الف " }), {})
})

test("only changed fields are sent, text trimmed and blank as null", () => {
  const initial = editFormFrom(order, "2026-10-25")
  const form = {
    ...initial, orderDate: "2026-10-26", paymentMethodId: 1, shipping: 0, postage: 1_250_005,
    customerName: "   ", notes: " یادداشت ", paidDate: "2026-10-26",
  }
  assert.deepEqual(editBody(initial, form), {
    order_date: "2026-10-26", payment_method_id: 1, paid_date: "2026-10-26", shipping_charge: 0,
    postage_cost: 1_250_005, customer_name: null, notes: "یادداشت",
  })
})

test("a money field with no exact amount is left out and blocks saving", () => {
  const initial = editFormFrom(order, "2026-10-25")
  const form = { ...initial, shipping: null }
  assert.deepEqual(editBody(initial, form), {})
  assert.equal(formBlocked(form), true)
  assert.equal(formBlocked(initial), false)
})

test("the paid day follows the order day only when it was the order's own day", () => {
  const same = editFormFrom(order, "2026-10-25")
  assert.equal(proposedPaidDate(same, same, "2026-10-27"), "2026-10-27")
  const later = editFormFrom({ ...order, paid_date: "2026-10-26" }, "2026-10-25")
  assert.equal(proposedPaidDate(later, later, "2026-10-27"), "2026-10-26")
  // The user moved the paid day by hand: it stays.
  assert.equal(proposedPaidDate(same, { ...same, paidDate: "2026-10-20" }, "2026-10-27"), "2026-10-20")
  const unpaid = editFormFrom({ ...order, paid_date: null }, "2026-10-25")
  assert.equal(proposedPaidDate(unpaid, unpaid, "2026-10-27"), "")
})

test("refusals are read from code and details", () => {
  const e = (code, details = {}) => editRefusal({ status: 409, code, details })
  assert.deepEqual(e("ORDER_ALREADY_VOIDED"), { kind: "voided" })
  assert.deepEqual(e("ORDER_EDIT_NOT_ALLOWED", { status: "DRAFT", fields: ["postage_cost"] }), { kind: "notAllowed", status: "DRAFT" })
  assert.deepEqual(e("ORDER_NOT_PAID"), { kind: "notPaid" })
  assert.deepEqual(e("ORDER_ALREADY_SETTLED", { settlement_id: 7 }), { kind: "settled", settlementId: 7 })
  assert.deepEqual(e("PERIOD_ALREADY_DISTRIBUTED", { period_end: "2026-10-15", date: "2026-10-05" }), {
    kind: "closed", periodEnd: "2026-10-15", date: "2026-10-05",
  })
  assert.equal(e("PERIOD_ALREADY_DISTRIBUTED", {}), null)
  assert.deepEqual(e("MONTH_ALREADY_SETTLED", { jalali_year: 1405, jalali_month: 7 }), { kind: "month", jalaliYear: 1405, jalaliMonth: 7 })
  assert.equal(e("SOMETHING_ELSE"), null)
  assert.equal(editRefusal({ status: 422, code: "ORDER_NOT_PAID", details: {} }), null)
  assert.deepEqual(editBlockerRefusal({ code: "ORDER_ALREADY_SETTLED", details: { order_id: 1, settlement_id: 2 } }), {
    kind: "settled", settlementId: 2,
  })
})
