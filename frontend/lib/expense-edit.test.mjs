// Run with `npm test`. Editing/deleting an expense or a postage payment: the PATCH body and the refusals.
import { test } from "node:test"
import assert from "node:assert/strict"
import { closedDay, expensePatch, isFutureDateError, postagePatch } from "./expense-edit.ts"

const saved = { categoryId: 3, amount: 1_000_000, description: "اجاره", day: "2026-09-10" }

test("expensePatch: nothing changed is null", () => {
  assert.equal(expensePatch(saved, { ...saved }), null)
  assert.equal(expensePatch(saved, { ...saved, description: "  اجاره " }), null)
})

test("expensePatch: only the changed fields are sent", () => {
  assert.deepEqual(expensePatch(saved, { ...saved, amount: 2_000_000 }), { amount: 2_000_000 })
  assert.deepEqual(expensePatch(saved, { ...saved, categoryId: 4, day: "2026-09-11" }), {
    expense_category_id: 4,
    expense_date: "2026-09-11",
  })
})

test("expensePatch: a blank description clears it with null", () => {
  assert.deepEqual(expensePatch(saved, { ...saved, description: "   " }), { description: null })
  assert.equal(expensePatch({ ...saved, description: "" }, { ...saved, description: "" }), null)
})

test("postagePatch: only the changed fields, blank note clears", () => {
  const p = { total: 900, orders: 3, note: "n", day: "2026-09-10" }
  assert.equal(postagePatch(p, { ...p }), null)
  assert.deepEqual(postagePatch(p, { ...p, total: 0, orders: 4 }), { total_paid: 0, order_count: 4 })
  assert.deepEqual(postagePatch(p, { ...p, note: "", day: "2026-09-09" }), { notes: null, paid_date: "2026-09-09" })
})

test("closedDay: reads PERIOD_ALREADY_DISTRIBUTED details", () => {
  const e = {
    status: 409,
    code: "PERIOD_ALREADY_DISTRIBUTED",
    details: { distribution_id: 5, period_end: "2026-09-30", date: "2026-09-10" },
  }
  assert.deepEqual(closedDay(e), { periodEnd: "2026-09-30", date: "2026-09-10", distributionId: 5 })
})

test("closedDay: another 409, another status or missing details is not it", () => {
  assert.equal(closedDay({ status: 409, code: "CONFLICT", details: {} }), null)
  assert.equal(closedDay({ status: 422, code: "PERIOD_ALREADY_DISTRIBUTED", details: { period_end: "2026-09-30" } }), null)
  assert.equal(closedDay({ status: 409, code: "PERIOD_ALREADY_DISTRIBUTED", details: {} }), null)
})

test("isFutureDateError: DATE_IN_FUTURE on the named field only", () => {
  const e = { status: 422, code: "DATE_IN_FUTURE", field: "expense_date", details: { today: "2026-10-23" } }
  assert.equal(isFutureDateError(e, "expense_date"), true)
  assert.equal(isFutureDateError(e, "paid_date"), false)
  assert.equal(isFutureDateError({ ...e, code: "VALIDATION_FAILED" }, "expense_date"), false)
})
