// Run with `npm test`. The stocktake page's ?material=<id> link.
import { test } from "node:test"
import assert from "node:assert/strict"
import { materialFromParams, stocktakeMaterialHref } from "./stocktake-link.ts"

const read = (qs) => materialFromParams(new URLSearchParams(qs))

test("the link and its reading agree", () => {
  assert.equal(stocktakeMaterialHref(17), "/stocktake?material=17")
  assert.equal(read(stocktakeMaterialHref(17).split("?")[1]), 17)
})

test("only a positive whole id is a link; everything else is ignored", () => {
  assert.equal(read(""), null)
  assert.equal(read("material="), null)
  assert.equal(read("material=0"), null)
  assert.equal(read("material=-3"), null)
  assert.equal(read("material=2.5"), null)
  assert.equal(read("material=abc"), null)
  assert.equal(read("material=7abc"), null)
  assert.equal(read("material=01"), null)
  assert.equal(read("material=%207"), null)
  assert.equal(read("material=99999999999999999"), null) // beyond a safe integer
  assert.equal(read("tab=materials&material=5"), 5)
})
