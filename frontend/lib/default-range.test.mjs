// Run with `npm test`. The orders list and the dashboard default to the last 30 days.
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  DASHBOARD_PRESET_KINDS,
  dashboardPresets,
  defaultedRangeQuery,
  last30Range,
  readDefaultedRange,
} from "./default-range.ts"
import { rangeDays } from "./jalali.ts"

const TODAY = "2026-10-06"

test("last 30 days: today and the 29 days before it", () => {
  assert.deepEqual(last30Range(TODAY), { from: "2026-09-07", to: TODAY })
  assert.equal(rangeDays(last30Range(TODAY)), 30)
})

test("no URL parameters means the last 30 days, and the default writes none", () => {
  const read = readDefaultedRange(new URLSearchParams(), TODAY)
  assert.deepEqual(read, { kind: "last30", range: last30Range(TODAY) })
  assert.equal(defaultedRangeQuery(read.range, TODAY), "")
})

test("URL round trip: another preset or a custom range is kept, a malformed one falls back", () => {
  const month = dashboardPresets(TODAY).thisMonth
  const qs = defaultedRangeQuery(month, TODAY)
  assert.equal(qs, `from=${month.from}&to=${month.to}`)
  assert.deepEqual(readDefaultedRange(new URLSearchParams(qs), TODAY), { kind: "thisMonth", range: month })
  const custom = { from: "2026-08-01", to: "2026-08-03" }
  assert.equal(readDefaultedRange(new URLSearchParams(defaultedRangeQuery(custom, TODAY)), TODAY).kind, "custom")
  assert.equal(readDefaultedRange(new URLSearchParams("from=x&to=y"), TODAY).kind, "last30")
})

test("dashboard presets: last30 is first-class between 7 days and this month", () => {
  assert.deepEqual([...DASHBOARD_PRESET_KINDS], ["today", "last7", "last30", "thisMonth", "lastMonth"])
  const p = dashboardPresets(TODAY)
  assert.deepEqual(p.last30, last30Range(TODAY))
  assert.deepEqual(p.last7, { from: "2026-09-30", to: TODAY })
  assert.deepEqual(readDefaultedRange(new URLSearchParams(`from=${p.last7.from}&to=${p.last7.to}`), TODAY).kind, "last7")
})
