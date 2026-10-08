// Run with `npm test`. The client previews keep their formulas (they mirror
// db/ line for line) and now run on integer Rial. Where a formula rounds, the
// Rial result can differ from the old Toman result × 10: these cases pin the
// Rial figure, which is what the backend now stores (Python round(), half-even).
import { test } from "node:test"
import assert from "node:assert/strict"
import { batchPreview, blendUnitCost, purchaseUnitCost, recipeSums, roundHalfEven } from "./costing.ts"
import { project, rateOf, sums } from "../components/postage/figures.ts"
import { initialState, orderTotal, reducer } from "../components/record-sale/state.ts"

const line = (cost_basis, quantity_needed, material_unit_cost) => ({
  material_id: 1,
  material_name: "Card",
  material_type: "SERVICE",
  material_unit: "pc",
  quantity_needed,
  cost_basis,
  material_unit_cost,
})
const noStock = () => null

test("weighted average: 3 units at 1,001 Toman + 1 at 1,000 Toman = 10,008 Rial (half-even of 10,007.5)", () => {
  assert.equal(blendUnitCost(3, 10_010, 1, 10_000), 10_008)
  // The old Toman preview: round(4003 / 4 = 1000.75) = 1001 Toman, i.e. 10,010 Rial.
  assert.equal(blendUnitCost(3, 1_001, 1, 1_000) * 10, 10_010)
  // No stock before: this delivery's own unit cost.
  assert.equal(blendUnitCost(0, 10_010, 2, 10_005), 5_002) // 5,002.5 → even
  assert.equal(blendUnitCost(null, null, 2, 10_015), 5_008) // 5,007.5 → even
})

test("purchase unit cost: half-even on the Rial", () => {
  assert.equal(purchaseUnitCost(10_010, 2), 5_005)
  assert.equal(purchaseUnitCost(1_001, 2) * 10, 5_000) // old: 500.5 → 500 Toman
  assert.equal(purchaseUnitCost(10_005, 2), 5_002)
  assert.equal(purchaseUnitCost(10_015, 2), 5_008)
})

test("production batch: total and unit cost round on the Rial", () => {
  // 0.5 × 1,001 Toman per unit.
  const rial = batchPreview([line("PER_UNIT", 0.5, 10_010)], 1, noStock)
  assert.equal(rial.batchTotal, 5_005)
  assert.equal(rial.unitCost, 5_005)
  assert.equal(batchPreview([line("PER_UNIT", 0.5, 1_001)], 1, noStock).batchTotal * 10, 5_000)

  // A once-per-batch 1,001 Toman spread over 4 units.
  const perBatch = batchPreview([line("PER_BATCH", 1, 10_010)], 4, noStock)
  assert.equal(perBatch.batchTotal, 10_010)
  assert.equal(perBatch.unitCost, 2_502) // 2,502.5 → even
  assert.equal(batchPreview([line("PER_BATCH", 1, 1_001)], 4, noStock).unitCost * 10, 2_500)
})

test("recipe sums round on the Rial", () => {
  const sumsRial = recipeSums([line("PER_UNIT", 0.5, 10_010), line("PER_BATCH", 0.5, 10_030)])
  assert.deepEqual(sumsRial, { perUnit: 5_005, perBatch: 5_015 })
  const sumsToman = recipeSums([line("PER_UNIT", 0.5, 1_001), line("PER_BATCH", 0.5, 1_003)])
  assert.deepEqual({ perUnit: sumsToman.perUnit * 10, perBatch: sumsToman.perBatch * 10 }, { perUnit: 5_000, perBatch: 5_020 })
})

test("roundHalfEven matches Python round() on .5 ties", () => {
  for (const [x, r] of [[10_007.5, 10_008], [2_502.5, 2_502], [5_015.5, 5_016], [0.5, 0], [1.5, 2]]) assert.equal(roundHalfEven(x), r)
})

test("postage: a payment's rate and the estimate round on the Rial", () => {
  // 1,001 Toman for 2 orders.
  assert.equal(rateOf(10_010, 2), 5_005)
  assert.equal(rateOf(1_001, 2) * 10, 5_000)
  assert.deepEqual(sums([{ total_paid: 10_010, order_count: 2 }, { total_paid: 30_005, order_count: 4 }]), { total: 40_015, orders: 6 })

  const batches = [{ id: 1, total_paid: 30_005, order_count: 4, paid_date: "2026-10-01T08:00:00Z" }]
  const p = project(batches, 5, { total: 10_010, orders: 2, day: null }, "Asia/Tehran")
  assert.equal(p.estimate, 6_669) // 40,015 / 6 = 6,669.17
  const old = project([{ ...batches[0], total_paid: 3_000 }], 5, { total: 1_001, orders: 2, day: null }, "Asia/Tehran")
  assert.equal(old.estimate * 10, 6_670) // 4,001 / 6 = 666.8 → 667 Toman
})

test("record sale: the customer total is exact on odd Rial amounts (no rounding)", () => {
  const product = { id: 7, retail_price: 12_345, wholesale_price: 10_001 }
  let s = initialState(1)
  s = reducer(s, { type: "pickProduct", key: 1, product })
  s = reducer(s, { type: "line", key: 1, patch: { qty: 3, discountOpen: true, discount: 7 } })
  s = reducer(s, { type: "shipping", value: 1_800_005 })
  const catalog = { settings: { default_shipping_charge: 0, channels: {} } }
  assert.equal(orderTotal(s, catalog), 37_035 - 7 + 1_800_005) // 1,837,033 — db/orders.py customer_total
})
