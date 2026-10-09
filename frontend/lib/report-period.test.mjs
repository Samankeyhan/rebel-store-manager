// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
// Expected Jalali month boundaries match db/jalali.py month_range().
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  apiRange,
  periodKey,
  periodPresets,
  presetPeriod,
  readReportPeriod,
  readReportTab,
  writeReportPeriod,
  writeReportTab,
} from "./report-period.ts"

const TODAY = "2026-10-09" // 17 Mehr 1405
const qs = (s) => new URLSearchParams(s)

test("presets relative to 17 Mehr 1405", () => {
  assert.deepEqual(periodPresets(TODAY), {
    thisMonth: { from: "2026-09-23", to: "2026-10-22" }, // 1 Mehr – 30 Mehr
    lastMonth: { from: "2026-08-23", to: "2026-09-22" }, // Shahrivar, 31 days
    thisYear: { from: "2026-03-21", to: "2027-03-20" }, // 1 Farvardin 1405 – 30 Esfand 1405
    last30: { from: "2026-09-10", to: "2026-10-09" }, // today and the 29 days before
  })
})

test("last month from Farvardin is Esfand of the previous Jalali year", () => {
  const p = periodPresets("2026-03-21") // 1 Farvardin 1405
  assert.deepEqual(p.thisMonth, { from: "2026-03-21", to: "2026-04-20" })
  assert.deepEqual(p.lastMonth, { from: "2026-02-20", to: "2026-03-20" }) // Esfand 1404: 29 days
  assert.deepEqual(p.thisYear, { from: "2026-03-21", to: "2027-03-20" })
})

test("Esfand has 30 days in a leap year (1403) and 29 otherwise (1404, 1402)", () => {
  assert.deepEqual(periodPresets("2025-03-20").thisMonth, { from: "2025-02-19", to: "2025-03-20" }) // 30 Esfand 1403
  assert.deepEqual(periodPresets("2026-03-20").thisMonth, { from: "2026-02-20", to: "2026-03-20" }) // 29 Esfand 1404
  assert.deepEqual(periodPresets("2024-03-19").thisMonth, { from: "2024-02-20", to: "2024-03-19" }) // 29 Esfand 1402
  // The last day of the year still belongs to that year.
  assert.deepEqual(periodPresets("2025-03-20").thisYear, { from: "2024-03-20", to: "2025-03-20" })
})

test("no parameters = this Jalali month", () => {
  assert.deepEqual(readReportPeriod(qs(""), TODAY), { kind: "thisMonth", range: { from: "2026-09-23", to: "2026-10-22" } })
})

test("a range equal to a preset selects it; anything else is custom", () => {
  assert.equal(readReportPeriod(qs("from=2026-08-23&to=2026-09-22"), TODAY).kind, "lastMonth")
  assert.equal(readReportPeriod(qs("from=2026-03-21&to=2027-03-20"), TODAY).kind, "thisYear")
  assert.equal(readReportPeriod(qs("from=2026-09-10&to=2026-10-09"), TODAY).kind, "last30")
  assert.deepEqual(readReportPeriod(qs("from=2026-09-01&to=2026-09-01"), TODAY), {
    kind: "custom",
    range: { from: "2026-09-01", to: "2026-09-01" },
  })
})

test("malformed or reversed ranges fall back to this month", () => {
  for (const s of ["from=2026-10-01", "from=2026-10-05&to=2026-10-01", "from=2026-02-31&to=2026-03-01", "from=2026-09-01&to=2026-13-01", "from=x&to=y"]) {
    assert.equal(readReportPeriod(qs(s), TODAY).kind, "thisMonth", s)
  }
})

test("period=all is all time and wins over from/to", () => {
  assert.deepEqual(readReportPeriod(qs("period=all"), TODAY), { kind: "all", range: null })
  assert.deepEqual(readReportPeriod(qs("period=all&from=2026-09-01&to=2026-09-02"), TODAY), { kind: "all", range: null })
})

test("write: the default writes nothing, others round-trip, other params are kept", () => {
  assert.equal(writeReportPeriod(qs("tab=products"), presetPeriod("thisMonth", TODAY), TODAY).toString(), "tab=products")
  assert.equal(writeReportPeriod(qs("from=2026-09-01&to=2026-09-02"), presetPeriod("all", TODAY), TODAY).toString(), "period=all")
  for (const period of [
    presetPeriod("lastMonth", TODAY),
    presetPeriod("thisYear", TODAY),
    presetPeriod("last30", TODAY),
    presetPeriod("all", TODAY),
    { kind: "custom", range: { from: "2025-01-01", to: "2026-10-09" } },
  ]) {
    assert.deepEqual(readReportPeriod(writeReportPeriod(qs("period=all"), period, TODAY), TODAY), period)
  }
})

test("API bounds: a range sends both inclusive days, all time sends none", () => {
  assert.deepEqual(apiRange(presetPeriod("thisMonth", TODAY)), { from: "2026-09-23", to: "2026-10-22" })
  assert.deepEqual(apiRange(presetPeriod("all", TODAY)), {})
  assert.equal(periodKey(presetPeriod("all", TODAY)), "all")
  assert.equal(periodKey(presetPeriod("thisMonth", TODAY)), "2026-09-23|2026-10-22")
})

test("tab: default pnl, unknown values fall back, default writes nothing", () => {
  assert.equal(readReportTab(qs("")), "pnl")
  assert.equal(readReportTab(qs("tab=channels")), "channels")
  assert.equal(readReportTab(qs("tab=nope")), "pnl")
  assert.equal(writeReportTab(qs("tab=products&from=2026-09-01&to=2026-09-02"), "pnl").toString(), "from=2026-09-01&to=2026-09-02")
  assert.equal(writeReportTab(qs(""), "products").toString(), "tab=products")
})
