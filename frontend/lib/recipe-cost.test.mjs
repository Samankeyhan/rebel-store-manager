// Run with `npm test`. Recipe cost previews mirror db/costing.py recipe_batch_total; the labels follow accounting §13.
import { test } from "node:test"
import assert from "node:assert/strict"
import { blendUnitCost, recipeBatchTotal, recipeMissing } from "./costing.ts"
import { costLines, costState, materialsWithoutCost, prefillCost } from "./product-cost.ts"

const unit = (quantity_needed, material_unit_cost) => ({ quantity_needed, cost_basis: "PER_UNIT", material_unit_cost })
const batch = (quantity_needed, material_unit_cost) => ({ quantity_needed, cost_basis: "PER_BATCH", material_unit_cost })
const recipe = [unit(1, 53_393), unit(0.3333, 10_000), unit(0.008, 1_200_000), batch(1, 3_333)]

test("recipeBatchTotal: PER_UNIT lines scale with the quantity, PER_BATCH lines count once", () => {
  assert.equal(recipeBatchTotal(recipe, 1), 69_659)
  assert.equal(recipeBatchTotal(recipe, 3), 202_311) // 3 x 66,326 + 3,333 once
  assert.notEqual(recipeBatchTotal(recipe, 3), 3 * recipeBatchTotal(recipe, 1)) // the old preview's overstatement
})

test("recipeBatchTotal rounds the sum once, half-even, and stays exact", () => {
  assert.equal(recipeBatchTotal([unit(0.5, 1)], 1), 0) // 0.5 -> 0
  assert.equal(recipeBatchTotal([unit(1.5, 1)], 1), 2)
  assert.equal(recipeBatchTotal([unit(2.5, 1)], 1), 2)
  assert.equal(recipeBatchTotal([unit(0.5, 1), unit(0.5, 1)], 1), 1) // one rounding, not two
  assert.equal(recipeBatchTotal([unit(0.005, 120_000_000)], 1), 600_000) // never 599,999.99…
  assert.equal(recipeBatchTotal([], 2), 0)
})

test("recipeMissing lists the materials with cost 0 or none", () => {
  const lines = [
    { material_id: 1, material_name: "A", material_unit_cost: 5 },
    { material_id: 2, material_name: "B", material_unit_cost: 0 },
    { material_id: 3, material_name: "C", material_unit_cost: null },
  ]
  assert.deepEqual(recipeMissing(lines), [{ id: 2, name: "B" }, { id: 3, name: "C" }])
})

test("blendUnitCost with zeroIsUnknown sets the cost from the incoming value (materials)", () => {
  assert.equal(blendUnitCost(20, 0, 10, 5_000), 167)
  assert.equal(blendUnitCost(20, 0, 10, 5_000, true), 500)
  assert.equal(blendUnitCost(20, 400, 10, 5_000, true), 433)
  assert.equal(blendUnitCost(3, 0, 2, 5, true), 2) // 2.5 -> 2
})

const product = (over = {}) => ({
  unit_cost: null,
  made_to_order: 0,
  current_stock: 0,
  recipe_cost: null,
  recipe_cost_status: "NONE",
  recipe_cost_missing: [],
  ...over,
})

test("costLines: stored average first, otherwise the recipe estimate, «ناقص», or unknown", () => {
  assert.deepEqual(costLines(product({ unit_cost: 700 })), [{ tag: "avg", cost: 700 }])
  assert.deepEqual(costLines(product({ made_to_order: 1, recipe_cost: 900, recipe_cost_status: "COMPLETE" })), [{ tag: "estimate", cost: 900 }])
  assert.deepEqual(
    costLines(product({ made_to_order: 1, recipe_cost_status: "INCOMPLETE", recipe_cost_missing: [{ id: 4, name: "Sticker" }] })),
    [{ tag: "incomplete", missing: ["Sticker"] }]
  )
  assert.deepEqual(costLines(product()), [{ tag: "unknown" }])
})

test("costLines: a made-to-order product with finished stock shows both", () => {
  const p = product({ unit_cost: 700, made_to_order: 1, current_stock: 3, recipe_cost: 900, recipe_cost_status: "COMPLETE" })
  assert.deepEqual(costLines(p), [{ tag: "avg", cost: 700 }, { tag: "estimate", cost: 900 }])
  // A normal product with a stored average shows only the average.
  assert.deepEqual(costLines({ ...p, made_to_order: 0 }), [{ tag: "avg", cost: 700 }])
})

test("costState keeps the sale rules: the estimate never makes a no-cost product sellable", () => {
  assert.equal(costState(product({ unit_cost: 1 })).kind, "known")
  assert.equal(costState(product({ made_to_order: 1, current_stock: 0 })).kind, "fromRecipe")
  assert.equal(costState(product({ made_to_order: 1, current_stock: 2, recipe_cost: 9, recipe_cost_status: "COMPLETE" })).kind, "missing")
  assert.equal(costState(product({ recipe_cost: 9, recipe_cost_status: "COMPLETE" })).kind, "missing")
})

test("prefillCost: only a COMPLETE recipe of a product with no stored cost", () => {
  assert.equal(prefillCost(product({ recipe_cost: 900, recipe_cost_status: "COMPLETE" })), 900)
  assert.equal(prefillCost(product({ recipe_cost_status: "INCOMPLETE" })), null)
  assert.equal(prefillCost(product({ recipe_cost_status: "NONE" })), null)
  assert.equal(prefillCost(product({ unit_cost: 5, recipe_cost: 900, recipe_cost_status: "COMPLETE" })), null)
})

test("materialsWithoutCost: active, cost 0, and holding stock or named in a recipe_cost_missing", () => {
  const m = (id, over = {}) => ({ id, type: "STOCK", is_active: 1, unit_cost: 0, current_stock: 0, ...over })
  const materials = [
    m(1, { current_stock: 5 }), // stock at cost 0
    m(2), // no stock, in no recipe
    m(3), // no stock but makes a recipe incomplete
    m(4, { type: "SERVICE", current_stock: null }), // a service in a recipe
    m(5, { current_stock: 5, unit_cost: 700 }), // costed
    m(6, { current_stock: 5, is_active: 0 }), // inactive
    m(7, { current_stock: 2, unit_cost: null }), // no cost recorded
  ]
  const products = [{ recipe_cost_missing: [{ id: 3 }, { id: 4 }] }, { recipe_cost_missing: [] }]
  assert.deepEqual(materialsWithoutCost(materials, products).map((x) => x.id), [1, 3, 4, 7])
})
