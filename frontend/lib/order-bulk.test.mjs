// `npm test` — the orders list's bulk «پرداخت‌شده» → «تکمیل‌شده»: the selection, what it allows, the body, a refusal.
import { test } from "node:test"
import assert from "node:assert/strict"
import { BULK_MAX, bulkBody, ineligibleCount, pageState, planBulk, setIds, toggleId } from "./order-bulk.ts"

const row = (id, status = "PAID") => ({ id, status, invoice_number: `INV-${String(id).padStart(6, "0")}` })

test("toggleId ticks and unticks one id and never mutates the selection it was given", () => {
  const empty = new Set()
  const one = toggleId(empty, 5)
  assert.deepEqual([...one], [5])
  assert.equal(empty.size, 0)
  assert.deepEqual([...toggleId(one, 5)], [])
  assert.deepEqual([...toggleId(one, 7)].sort(), [5, 7])
})

test("setIds ticks or unticks a whole page and leaves the other pages' ticks alone", () => {
  const before = new Set([1, 2, 99])
  assert.deepEqual([...setIds(before, [2, 3, 4], true)].sort((a, b) => a - b), [1, 2, 3, 4, 99])
  assert.deepEqual([...setIds(before, [1, 2, 3], false)], [99])
  assert.deepEqual([...before].sort((a, b) => a - b), [1, 2, 99])
})

test("pageState: none, some or all of the page's ids are ticked; an empty page is none", () => {
  assert.equal(pageState(new Set([1]), []), "none")
  assert.equal(pageState(new Set(), [1, 2, 3]), "none")
  assert.equal(pageState(new Set([2, 50]), [1, 2, 3]), "some")
  assert.equal(pageState(new Set([1, 2, 3, 50]), [1, 2, 3]), "all")
})

test("planBulk: only PAID orders can run; the chosen keep the list's order", () => {
  const rows = [row(3), row(2), row(1)]
  const plan = planBulk(rows, new Set([1, 3]))
  assert.deepEqual(plan.chosen.map((r) => r.id), [3, 1])
  assert.deepEqual(plan.ineligible, [])
  assert.equal(plan.canRun, true)
})

test("planBulk: one order that is not PAID disables the whole action and is counted", () => {
  const rows = [row(4), row(3, "PENDING"), row(2, "COMPLETED"), row(1)]
  const plan = planBulk(rows, new Set([1, 2, 3, 4]))
  assert.deepEqual(plan.ineligible.map((r) => r.id), [3, 2])
  assert.equal(plan.canRun, false)
  assert.equal(planBulk(rows, new Set([1, 4])).canRun, true)
})

test("planBulk: nothing chosen cannot run, and a tick on an order the list no longer holds is ignored", () => {
  const rows = [row(1)]
  assert.equal(planBulk(rows, new Set()).canRun, false)
  const stale = planBulk(rows, new Set([1, 404]))
  assert.deepEqual(stale.chosen.map((r) => r.id), [1])
  assert.equal(stale.canRun, true)
})

test("planBulk: more than the server's limit cannot run", () => {
  const rows = Array.from({ length: BULK_MAX + 1 }, (_, i) => row(i + 1))
  const all = new Set(rows.map((r) => r.id))
  assert.equal(planBulk(rows, all).tooMany, true)
  assert.equal(planBulk(rows, all).canRun, false)
  const limit = new Set(rows.slice(0, BULK_MAX).map((r) => r.id))
  assert.equal(planBulk(rows, limit).canRun, true)
})

test("bulkBody lists the chosen ids in order and always targets COMPLETED", () => {
  assert.deepEqual(bulkBody([row(3), row(1)]), { order_ids: [3, 1], status: "COMPLETED" })
})

test("ineligibleCount reads the 409 by its code and details, never by message text", () => {
  const refused = {
    status: 409,
    code: "ORDER_BULK_NOT_ELIGIBLE",
    details: { ineligible: [{ order_id: 3, invoice_number: "INV-000003", status: "PENDING" }, { order_id: 4, invoice_number: null, status: "DRAFT" }] },
  }
  assert.equal(ineligibleCount(refused), 2)
  assert.equal(ineligibleCount({ ...refused, details: {} }), null)
  assert.equal(ineligibleCount({ ...refused, status: 422 }), null)
  assert.equal(ineligibleCount({ status: 409, code: "CONFLICT", details: refused.details }), null)
  assert.equal(ineligibleCount({ status: 409, message: "3 of 5 orders are not PAID" }), null)
})
