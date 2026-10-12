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

test("isNameDuplicate accepts the three duplicate-name codes on a 409 only", async () => {
  const { isNameDuplicate } = await import("./error-codes.ts")
  for (const code of ["NAME_DUPLICATE", "CATEGORY_DUPLICATE_NAME", "PAYMENT_METHOD_DUPLICATE_NAME"]) {
    assert.equal(isNameDuplicate({ status: 409, code }), true, code)
    assert.equal(isNameDuplicate({ status: 422, code }), false, code)
  }
  assert.equal(isNameDuplicate({ status: 409, code: "CONFLICT" }), false)
  assert.equal(isNameDuplicate({ status: 409, code: "CATEGORY_IN_USE" }), false)
  assert.equal(isNameDuplicate({ status: 409 }), false)
})

test("duplicateEntity and duplicateExistingId read the details of a duplicate refusal", async () => {
  const { duplicateEntity, duplicateExistingId } = await import("./error-codes.ts")
  const dup = { status: 409, code: "NAME_DUPLICATE", details: { entity: "supplier", existing_id: 7 } }
  assert.equal(duplicateEntity(dup), "supplier")
  assert.equal(duplicateExistingId(dup), 7)
  assert.equal(duplicateEntity({ ...dup, details: {} }), null)
  assert.equal(duplicateExistingId({ ...dup, details: { existing_id: "7" } }), null)
  assert.equal(duplicateEntity({ status: 409, code: "CONFLICT", details: { entity: "supplier" } }), null)
})

test("nameDuplicateMessage names the kind of record, falls back for an unknown one, and never says «ماده»", async () => {
  const { nameDuplicateMessage } = await import("../components/common/copy.ts")
  assert.match(nameDuplicateMessage("material"), /^متریالی /)
  assert.match(nameDuplicateMessage("supplier"), /^تأمین‌کننده‌ای /)
  assert.match(nameDuplicateMessage(null), /^موردی /)
  assert.match(nameDuplicateMessage("something_new"), /^موردی /)
  for (const entity of ["product", "material", "supplier", "partner", "category", "payment_method", "packaging_kit", "expense_category"]) {
    assert.doesNotMatch(nameDuplicateMessage(entity), /ماده|مواد/)
  }
})
