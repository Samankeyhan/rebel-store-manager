// `npm test` — «ثبت بها»: when it is offered and the stock value its confirmation shows.
import { test } from "node:test"
import assert from "node:assert/strict"
import { canSetMaterialCost, canSetProductCost, setCostStockValue } from "./set-cost.ts"
import { materialsWithoutCost } from "./product-cost.ts"

test("canSetMaterialCost: only a material at cost 0 or none, a SERVICE included", () => {
  assert.equal(canSetMaterialCost({ unit_cost: 0 }), true)
  assert.equal(canSetMaterialCost({ unit_cost: null }), true)
  assert.equal(canSetMaterialCost({ unit_cost: 700 }), false)
})

test("canSetProductCost: only a product with NO cost that holds stock; a cost of 0 is a real cost", () => {
  assert.equal(canSetProductCost({ unit_cost: null, current_stock: 4 }), true)
  assert.equal(canSetProductCost({ unit_cost: null, current_stock: 0 }), false)
  assert.equal(canSetProductCost({ unit_cost: 0, current_stock: 4 }), false)
  assert.equal(canSetProductCost({ unit_cost: 250000, current_stock: 4 }), false)
})

test("setCostStockValue: stock × price for a STOCK material and a product, rounded once half-even", () => {
  assert.equal(setCostStockValue({ type: "STOCK", current_stock: 20 }, 500), 10000)
  assert.equal(setCostStockValue({ type: "STOCK", current_stock: 2.5 }, 333), 832) // 832.5 → 832
  assert.equal(setCostStockValue({ current_stock: 4 }, 250000), 1000000)
})

test("setCostStockValue: a SERVICE has none, nor has an item without stock", () => {
  assert.equal(setCostStockValue({ type: "SERVICE", current_stock: null }, 7000), null)
  assert.equal(setCostStockValue({ type: "STOCK", current_stock: 0 }, 500), null)
  assert.equal(setCostStockValue({ type: "STOCK", current_stock: null }, 500), null)
})

test("materialsWithoutCost: a material leaves the list once it is priced, even while its stock stays", () => {
  const m = { id: 1, type: "STOCK", is_active: 1, unit_cost: 0, current_stock: 5 }
  assert.deepEqual(materialsWithoutCost([m], []).map((x) => x.id), [1])
  assert.deepEqual(materialsWithoutCost([{ ...m, unit_cost: 500 }], []).map((x) => x.id), [])
})
