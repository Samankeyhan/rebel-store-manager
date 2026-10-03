// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import { readUrlRange, writeUrlRange } from "./url-range.ts"

const fallback = { from: "2026-03-21", to: "2027-03-20" }

test("reads ?from=&to= from the URL", () => {
  const p = new URLSearchParams("from=2026-09-23&to=2026-10-22")
  assert.deepEqual(readUrlRange(p, fallback), { from: "2026-09-23", to: "2026-10-22" })
})

test("falls back when a bound is missing, malformed or reversed", () => {
  for (const qs of ["", "from=2026-09-23", "from=2026-9-23&to=2026-10-22", "from=2026-10-22&to=2026-09-23"]) {
    assert.deepEqual(readUrlRange(new URLSearchParams(qs), fallback), fallback, qs)
  }
})

test("writes the range back and keeps other parameters", () => {
  const next = writeUrlRange(new URLSearchParams("type=material"), { from: "2026-10-01", to: "2026-10-03" }, fallback)
  assert.equal(next.toString(), "type=material&from=2026-10-01&to=2026-10-03")
})

test("the default range is written as no parameters", () => {
  const next = writeUrlRange(new URLSearchParams("from=2026-10-01&to=2026-10-03"), fallback, fallback)
  assert.equal(next.toString(), "")
})

test("a written range reads back unchanged", () => {
  const range = { from: "2026-08-23", to: "2026-09-22" }
  assert.deepEqual(readUrlRange(writeUrlRange(new URLSearchParams(), range, fallback), fallback), range)
})
