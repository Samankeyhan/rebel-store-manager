// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  apiItemType,
  invoiceTotal,
  itemsSummary,
  lineField,
  lineProblems,
  lineTypes,
  linesBody,
  parseTypeFilter,
  pickId,
  unpick,
} from "./purchase-lines.ts"

const line = (pick, itemType, qty, total) => ({ pick, itemType, qty, total })

test("a picker id is the material id, or minus the product id, and back", () => {
  assert.equal(pickId("MATERIAL", 7), 7)
  assert.equal(pickId("PRODUCT", 7), -7)
  assert.deepEqual(unpick(7), { kind: "MATERIAL", id: 7 })
  assert.deepEqual(unpick(-7), { kind: "PRODUCT", id: 7 })
})

test("the type filter: only the four values, and the API item_type of each", () => {
  assert.equal(parseTypeFilter("service"), "service")
  assert.equal(parseTypeFilter("SERVICE"), "all")
  assert.equal(parseTypeFilter(null), "all")
  assert.equal(apiItemType("all"), null)
  assert.equal(apiItemType("material"), "MATERIAL")
  assert.equal(apiItemType("service"), "SERVICE")
  assert.equal(apiItemType("product"), "PRODUCT")
})

test("lineProblems: item, duplicate, quantity, whole product, total, service total, in that order", () => {
  const problems = lineProblems([
    line(null, null, 1, 100),
    line(1, "STOCK", 2.5, 100),
    line(1, "STOCK", 1, 100),
    line(2, "SERVICE", 0, 100),
    line(-3, "PRODUCT", 1.5, 100),
    line(4, "STOCK", 1, null),
    line(5, "SERVICE", 2, 0),
    line(-6, "PRODUCT", 3, 0),
    line(7, "STOCK", null, 100),
    line(-1, "PRODUCT", 1, 100),
  ])
  assert.deepEqual(problems, [
    "item",
    null,
    "duplicate",
    "qty",
    "qty_whole",
    "total",
    "service_total",
    null, // a product, like a stock material, may be bought at total 0
    "qty",
    null, // product 1 and material 1 are different items (picker ids 1 and -1)
  ])
})

test("invoiceTotal: the exact sum, null when a line has no exact total or the sum leaves the safe range", () => {
  assert.equal(invoiceTotal([]), 0)
  assert.equal(invoiceTotal([4000, 1000, 900]), 5900)
  assert.equal(invoiceTotal([4000, null]), null)
  assert.equal(invoiceTotal([Number.MAX_SAFE_INTEGER, 1]), null)
  assert.equal(invoiceTotal([Number.MAX_SAFE_INTEGER, 0]), Number.MAX_SAFE_INTEGER)
})

test("linesBody names the kind and the item of each picked line", () => {
  assert.deepEqual(linesBody([{ pick: 4, qty: 2.5, total: 1000 }, { pick: -9, qty: 3, total: 900 }]), [
    { kind: "MATERIAL", item_id: 4, quantity_bought: 2.5, total_paid: 1000 },
    { kind: "PRODUCT", item_id: 9, quantity_bought: 3, total_paid: 900 },
  ])
})

test("lineField reads the line index and field of a backend refusal", () => {
  assert.deepEqual(lineField("lines.2.total_paid"), { index: 2, field: "total_paid" })
  assert.deepEqual(lineField("lines.0.item_id"), { index: 0, field: "item_id" })
  assert.equal(lineField("lines"), null)
  assert.equal(lineField("payment.amount"), null)
  assert.equal(lineField(null), null)
})

test("itemsSummary: one name, or the first and how many more", () => {
  const more = (n) => `+${n}`
  assert.equal(itemsSummary([], more), "")
  assert.equal(itemsSummary(["کاغذ"], more), "کاغذ")
  assert.equal(itemsSummary(["کاغذ", "چاپ", "تی‌شرت"], more), "کاغذ +2")
})

test("lineTypes: the distinct item types, first seen first", () => {
  assert.deepEqual(lineTypes([{ item_type: "STOCK" }, { item_type: "SERVICE" }, { item_type: "STOCK" }]), ["STOCK", "SERVICE"])
  assert.deepEqual(lineTypes([]), [])
})
