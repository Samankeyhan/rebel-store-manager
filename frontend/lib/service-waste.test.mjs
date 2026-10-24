// `npm test` — waste of a service: the price to prefill, the amount preview, the price to send, the link to «ثبت بها».
import { test } from "node:test"
import assert from "node:assert/strict"
import { priceToSend, serviceWasteAmount, servicePrice, setCostHref } from "./service-waste.ts"

test("servicePrice: the current cost, none at 0 or null", () => {
  assert.equal(servicePrice({ unit_cost: 90000 }), 90000)
  assert.equal(servicePrice({ unit_cost: 1 }), 1)
  assert.equal(servicePrice({ unit_cost: 0 }), null)
  assert.equal(servicePrice({ unit_cost: null }), null)
})

test("serviceWasteAmount: units × price, exact, half-even once", () => {
  assert.equal(serviceWasteAmount(2, 90000), 180000)
  assert.equal(serviceWasteAmount(3, 333), 999)
  assert.equal(serviceWasteAmount(0.5, 333), 166) // 166.5 -> 166 (even)
  assert.equal(serviceWasteAmount(0.5, 335), 168) // 167.5 -> 168 (even)
  assert.equal(serviceWasteAmount(0.1, 30), 3) // 0.1 is the decimal 0.1, not a binary fraction
  assert.equal(serviceWasteAmount(1.5, 3), 4) // 4.5 -> 4
})

test("serviceWasteAmount stays exact past 2^53", () => {
  assert.equal(serviceWasteAmount(1, 9007199254740991), 9007199254740991)
})

test("priceToSend: the material's own cost is not sent, a typed price is", () => {
  const material = { unit_cost: 90000 }
  assert.equal(priceToSend(90000, material), null)
  assert.equal(priceToSend(85000, material), 85000)
})

test("setCostHref opens the material's drawer on the materials tab", () => {
  assert.equal(setCostHref(7), "/products?tab=materials&material=7")
})
