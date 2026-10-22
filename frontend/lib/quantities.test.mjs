import assert from "node:assert/strict"
import test from "node:test"
import { lineCost, recipeSums } from "./costing.ts"
import { formatQuantity, parseDecimal, quantityText } from "./persian-numbers.ts"

test("formatQuantity keeps up to six decimals", () => {
  assert.equal(formatQuantity(0.005), "۰٫۰۰۵")
  assert.equal(formatQuantity(0.0004), "۰٫۰۰۰۴")
  assert.equal(formatQuantity(0.000001), "۰٫۰۰۰۰۰۱")
  assert.equal(formatQuantity(1.5), "۱٫۵")
  assert.equal(formatQuantity(14), "۱۴")
})

test("formatQuantity still rounds past six decimals", () => {
  assert.equal(formatQuantity(0.00000049), "۰")
  assert.equal(formatQuantity(0.0000005), "۰٫۰۰۰۰۰۱")
})

test("quantityText reads back as exactly the same number", () => {
  for (const n of [0.005, 0.0004, 0.000001, 1.5, 14, 1200.25, 0.1, 1e-7, 1.234567891, 123456789.5]) {
    assert.equal(parseDecimal(quantityText(n)), n, String(n))
  }
})

test("quantityText never turns a small quantity into zero", () => {
  assert.equal(quantityText(0.0000004), "۰٫۰۰۰۰۰۰۴")
  assert.equal(quantityText(1e-7), "۰٫۰۰۰۰۰۰۱")
  assert.notEqual(quantityText(0.00000049), "۰")
})

test("quantityText is the plain formatQuantity text when that is exact", () => {
  assert.equal(quantityText(0.005), formatQuantity(0.005))
  assert.equal(quantityText(1200), formatQuantity(1200))
  assert.equal(quantityText(0), "۰")
})

test("lineCost is exact: a quantity counts as the decimal it was typed as", () => {
  assert.equal(lineCost(0.005, 120_000_000), 600_000)
  assert.equal(lineCost(0.1, 3), 0) // 0.3 → 0
  assert.equal(lineCost(1.1, 3), 3) // 3.3 → 3
  assert.equal(lineCost(0.07, 100), 7)
})

test("lineCost rounds half to even, once", () => {
  assert.equal(lineCost(0.5, 1), 0)
  assert.equal(lineCost(1.5, 1), 2)
  assert.equal(lineCost(2.5, 1), 2)
  assert.equal(lineCost(3.5, 1), 4)
  assert.equal(lineCost(2.5, 333), 832) // 832.5 → 832 (accounting-rules §8)
})

test("lineCost handles exponent-form quantities", () => {
  assert.equal(lineCost(1e-7, 10_000_000), 1)
  assert.equal(lineCost(5e-7, 1_000_000), 0) // 0.5 → 0
  assert.equal(lineCost(1e21, 1), 1e21)
})

test("recipeSums agrees with lineCost for a single line", () => {
  const line = { quantity_needed: 0.005, cost_basis: "PER_UNIT", material_unit_cost: 120_000_000 }
  assert.equal(recipeSums([line]).perUnit, lineCost(0.005, 120_000_000))
})
