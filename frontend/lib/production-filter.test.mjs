// `npm test` — search and category filter of the production recipe and history tabs.
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  NO_FILTER,
  categoryOptions,
  filterBatches,
  filterProducts,
  inCategory,
  isFiltering,
} from "./production-filter.ts"

// Categories: «وینیل» (1, top-level), «پوستر» (2, top-level) with «پوستر بزرگ» (3) and «پوستر کوچک» (4).
const product = (id, name, category_id, category_name, parent_category_id = null, parent_category_name = null) => ({
  id, name, category_id, category_name, parent_category_id, parent_category_name,
})
const PRODUCTS = [
  product(10, "Rebel LP", 1, "وینیل"),
  product(11, "آلبوم كتاب", 1, "وینیل"),
  product(12, "Tour Poster A2", 3, "پوستر بزرگ", 2, "پوستر"),
  product(13, "Tour Poster A5", 4, "پوستر کوچک", 2, "پوستر"),
  product(14, "Sticker Sheet", 2, "پوستر"),
]
const byId = new Map(PRODUCTS.map((p) => [p.id, p]))
const ids = (list) => list.map((p) => p.id)

test("no filter keeps everything; isFiltering sees a typed query or a category, not blanks", () => {
  assert.deepEqual(ids(filterProducts(PRODUCTS, NO_FILTER)), [10, 11, 12, 13, 14])
  assert.equal(isFiltering(NO_FILTER), false)
  assert.equal(isFiltering({ q: "   ", categoryId: null }), false)
  assert.equal(isFiltering({ q: "lp", categoryId: null }), true)
  assert.equal(isFiltering({ q: "", categoryId: 1 }), true)
})

test("search by name: English any case, Persian with spelling variants", () => {
  assert.deepEqual(ids(filterProducts(PRODUCTS, { q: "rebel", categoryId: null })), [10])
  assert.deepEqual(ids(filterProducts(PRODUCTS, { q: "POSTER", categoryId: null })), [12, 13])
  assert.deepEqual(ids(filterProducts(PRODUCTS, { q: "کتاب", categoryId: null })), [11]) // Persian ک finds Arabic ك
  assert.deepEqual(ids(filterProducts(PRODUCTS, { q: "nothing here", categoryId: null })), [])
})

test("a top-level category includes its subcategories; a subcategory is exact", () => {
  assert.deepEqual(ids(filterProducts(PRODUCTS, { q: "", categoryId: 2 })), [12, 13, 14])
  assert.deepEqual(ids(filterProducts(PRODUCTS, { q: "", categoryId: 3 })), [12])
  assert.deepEqual(ids(filterProducts(PRODUCTS, { q: "", categoryId: 1 })), [10, 11])
  assert.equal(inCategory(PRODUCTS[2], 2), true)
  assert.equal(inCategory(PRODUCTS[2], 4), false)
})

test("search and category combine (both must hold)", () => {
  assert.deepEqual(ids(filterProducts(PRODUCTS, { q: "a5", categoryId: 2 })), [13])
  assert.deepEqual(ids(filterProducts(PRODUCTS, { q: "a5", categoryId: 1 })), [])
})

test("category options: each category on screen, a parent for its subcategories, Persian order", () => {
  const options = categoryOptions(PRODUCTS)
  assert.deepEqual(
    options.map((o) => [o.id, o.label]),
    [
      [2, "پوستر"],
      [3, "پوستر › پوستر بزرگ"],
      [4, "پوستر › پوستر کوچک"],
      [1, "وینیل"],
    ]
  )
})

test("category options offer a parent that only has products in a subcategory, and none for an empty list", () => {
  const onlyChild = categoryOptions([PRODUCTS[2]])
  assert.deepEqual(onlyChild.map((o) => o.id).sort(), [2, 3])
  assert.deepEqual(categoryOptions([]), [])
})

// ------------------------------------------------------------------ history

const batch = (id, product_id, product_name, production_date = "2026-10-01 10:00:00") => ({ id, product_id, product_name, production_date })
const BATCHES = [batch(1, 10, "Rebel LP"), batch(2, 12, "Tour Poster A2"), batch(3, 13, "Tour Poster A5"), batch(4, 10, "Rebel LP")]

test("history: a batch is found through its product's name and category", () => {
  assert.deepEqual(filterBatches(BATCHES, byId, NO_FILTER).map((b) => b.id), [1, 2, 3, 4])
  assert.deepEqual(filterBatches(BATCHES, byId, { q: "lp", categoryId: null }).map((b) => b.id), [1, 4])
  assert.deepEqual(filterBatches(BATCHES, byId, { q: "", categoryId: 2 }).map((b) => b.id), [2, 3])
  assert.deepEqual(filterBatches(BATCHES, byId, { q: "a2", categoryId: 2 }).map((b) => b.id), [2])
})

test("history: filtering never changes the rows it keeps, so the date rule and sittings still see the same batches", () => {
  const kept = filterBatches(BATCHES, byId, { q: "lp", categoryId: null })
  assert.equal(kept[0], BATCHES[0]) // the same objects, in the same (newest first) order
  assert.deepEqual(kept.map((b) => b.production_date), ["2026-10-01 10:00:00", "2026-10-01 10:00:00"])
})

test("history: a batch whose product the list no longer holds is found by its own name, never by category", () => {
  const orphan = batch(9, 999, "Old Cassette")
  assert.deepEqual(filterBatches([orphan], byId, { q: "cassette", categoryId: null }).map((b) => b.id), [9])
  assert.deepEqual(filterBatches([orphan], byId, { q: "", categoryId: 1 }), [])
})
