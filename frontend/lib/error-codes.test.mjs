// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import { detailNum, detailStr, hasCode, refusedProductId } from "./error-codes.ts"
import { categoryConflict } from "../components/categories/refusal.ts"

test("hasCode: any of the given codes; null/absent code never matches", () => {
  const e = { status: 409, code: "CATEGORY_IN_USE" }
  assert.equal(hasCode(e, "CATEGORY_IN_USE"), true)
  assert.equal(hasCode(e, "CONFLICT", "CATEGORY_IN_USE"), true)
  assert.equal(hasCode(e, "CONFLICT"), false)
  assert.equal(hasCode({ status: 422, code: null }, "VALIDATION_FAILED"), false)
  assert.equal(hasCode({ status: 0 }, "NOT_FOUND"), false)
})

test("detailNum / detailStr: typed reads, null otherwise", () => {
  const e = { status: 409, details: { n: 3, z: 0, s: "2026-10-22", bad: "4", nan: Number.NaN, nil: null } }
  assert.equal(detailNum(e, "n"), 3)
  assert.equal(detailNum(e, "z"), 0)
  assert.equal(detailNum(e, "bad"), null)
  assert.equal(detailNum(e, "nan"), null)
  assert.equal(detailNum(e, "nil"), null)
  assert.equal(detailNum(e, "missing"), null)
  assert.equal(detailStr(e, "s"), "2026-10-22")
  assert.equal(detailStr(e, "n"), null)
  assert.equal(detailNum({ status: 409 }, "n"), null)
})

test("refusedProductId: details.product_id of a no-recipe / no-cost refusal only", () => {
  const details = { product_id: 7, product_name: "Test LP" }
  assert.equal(refusedProductId({ status: 422, code: "PRODUCT_NO_RECIPE", field: "made_to_order", details }), 7)
  assert.equal(refusedProductId({ status: 422, code: "PRODUCT_NO_UNIT_COST", field: "unit_cost", details }), 7)
  assert.equal(refusedProductId({ status: 422, code: "VALIDATION_FAILED", field: "unit_cost", details }), null)
  assert.equal(refusedProductId({ status: 422, code: "PRODUCT_NO_RECIPE", details: {} }), null)
  // The product name inside the message is no longer read.
  assert.equal(refusedProductId({ status: 422, field: "unit_cost", message: "product 'Test LP' has no unit_cost" }), null)
})

test("categoryConflict: each 409 code; item_count from details", () => {
  assert.deepEqual(categoryConflict({ status: 409, code: "CATEGORY_IN_USE", details: { item_count: 3 } }), { kind: "inUse", count: 3 })
  assert.deepEqual(categoryConflict({ status: 409, code: "CATEGORY_IN_USE", details: {} }), { kind: "inUse", count: null })
  assert.deepEqual(categoryConflict({ status: 409, code: "CATEGORY_HAS_SUBCATEGORIES" }), { kind: "hasChildren" })
  assert.deepEqual(categoryConflict({ status: 409, code: "CATEGORY_PARENT_INACTIVE" }), { kind: "parentInactive" })
  assert.deepEqual(categoryConflict({ status: 409, code: "CATEGORY_DUPLICATE_NAME" }), { kind: "duplicate" })
})

test("categoryConflict: not a 409, another code, or message text only → null", () => {
  assert.equal(categoryConflict({ status: 422, code: "CATEGORY_PARENT_INACTIVE", field: "parent_id" }), null)
  assert.equal(categoryConflict({ status: 409, code: "CONFLICT" }), null)
  assert.equal(categoryConflict({ status: 409, message: "Category 'Posters' is used by 2 product(s)" }), null)
  assert.equal(categoryConflict({ status: 409, message: "A category named 'Posters' already exists at this level." }), null)
})
