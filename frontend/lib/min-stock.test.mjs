// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import { minStockChanged, parseMinStock } from "./min-stock.ts"
import { formatQuantity } from "./persian-numbers.ts"

test("empty text means no minimum", () => {
  for (const t of ["", "   "]) assert.deepEqual(parseMinStock(t), { ok: true, value: null }, JSON.stringify(t))
})

test("reads Persian and Latin digits, with either decimal separator", () => {
  assert.deepEqual(parseMinStock("۲٫۵"), { ok: true, value: 2.5 })
  assert.deepEqual(parseMinStock("2.5"), { ok: true, value: 2.5 })
  assert.deepEqual(parseMinStock("۱۲"), { ok: true, value: 12 })
  assert.deepEqual(parseMinStock("۱٬۲۰۰"), { ok: true, value: 1200 })
  assert.deepEqual(parseMinStock(" ۳ "), { ok: true, value: 3 })
  assert.deepEqual(parseMinStock(".5"), { ok: true, value: 0.5 })
})

test("zero is a valid minimum", () => {
  assert.deepEqual(parseMinStock("0"), { ok: true, value: 0 })
  assert.deepEqual(parseMinStock("۰"), { ok: true, value: 0 })
})

test("refuses negatives and junk instead of dropping characters", () => {
  for (const t of ["-3", "−3", "۳-", "abc", "1a2", "1.2.3", ".", "۲ عدد", "1e3", "Infinity"]) {
    assert.deepEqual(parseMinStock(t), { ok: false }, t)
  }
})

test("changed only when the parse is valid and differs from the saved minimum", () => {
  assert.equal(minStockChanged(null, parseMinStock("")), false)
  assert.equal(minStockChanged(undefined, parseMinStock("")), false)
  assert.equal(minStockChanged(5, parseMinStock("۵")), false)
  assert.equal(minStockChanged(5, parseMinStock("")), true)
  assert.equal(minStockChanged(null, parseMinStock("0")), true)
  assert.equal(minStockChanged(5, parseMinStock("-1")), false)
})

test("a minimum shown with formatQuantity reads back unchanged", () => {
  for (const n of [0, 0.5, 2.5, 12, 1200, 1234567.125]) {
    assert.deepEqual(parseMinStock(formatQuantity(n)), { ok: true, value: n }, String(n))
  }
})
