// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  activeTotal,
  backendAcceptsTotal,
  classifyDistributionError,
  defaultPeriod,
  isNameTaken,
  jalaliYearStart,
  overCapBy,
  parsePercent,
  percentChanges,
  percentOf,
  percentText,
  splitState,
  totalHundredths,
} from "./partners.ts"
import { distributionErrorText, hundredthsText, percentErrorText } from "../components/partners/copy.ts"

const LATIN = /[0-9]/

test("parsePercent: digits, decimal marks, at most 2 decimals, 0 < p ≤ 100", () => {
  assert.deepEqual(parsePercent("33.33"), { hundredths: 3333, error: null })
  assert.deepEqual(parsePercent("۳۳٫۳۴"), { hundredths: 3334, error: null })
  assert.deepEqual(parsePercent("٥٠"), { hundredths: 5000, error: null })
  assert.deepEqual(parsePercent("12/5"), { hundredths: 1250, error: null })
  assert.deepEqual(parsePercent(" 100 "), { hundredths: 10000, error: null })
  assert.deepEqual(parsePercent("0.01"), { hundredths: 1, error: null })
  assert.deepEqual(parsePercent(".5"), { hundredths: 50, error: null })
  assert.deepEqual(parsePercent("7."), { hundredths: 700, error: null })
  assert.equal(parsePercent("").error, "empty")
  assert.equal(parsePercent("abc").error, "format")
  assert.equal(parsePercent(".").error, "format")
  assert.equal(parsePercent("-5").error, "format")
  assert.equal(parsePercent("1.2.3").error, "format")
  assert.equal(parsePercent("33.333").error, "decimals")
  assert.equal(parsePercent("0").error, "range")
  assert.equal(parsePercent("0.00").error, "range")
  assert.equal(parsePercent("100.01").error, "range")
  assert.equal(parsePercent("99999999999999999999").error, "range")
})

test("percentOf sends the same double the owner typed", () => {
  assert.equal(percentOf(3333), 33.33)
  assert.equal(percentOf(3334), 33.34)
  assert.equal(percentOf(1), 0.01)
  assert.equal(percentOf(10000), 100)
  assert.equal(JSON.stringify(percentOf(3333)), "33.33")
})

test("percentText round-trips through parsePercent", () => {
  assert.equal(percentText(33.33), "۳۳٫۳۳")
  assert.equal(percentText(50), "۵۰")
  for (const h of [1, 50, 999, 3333, 3334, 10000]) {
    assert.equal(parsePercent(percentText(percentOf(h))).hundredths, h)
  }
})

test("totals are exact in hundredths: 33.33 + 33.33 + 33.34 is 100", () => {
  assert.equal(totalHundredths([3333, 3333, 3334]), 10000)
  assert.equal(splitState(totalHundredths([3333, 3333, 3334])), "ok")
  assert.equal(splitState(totalHundredths([3333, 3333, 3333])), "under")
  assert.equal(splitState(totalHundredths([5000, 5001])), "over")
  assert.equal(splitState(totalHundredths([5000, null])), "invalid")
  assert.equal(splitState(totalHundredths([])), "under")
})

test("backendAcceptsTotal mirrors db/'s |Σ − 100| ≤ 0.01 over active partners", () => {
  const p = (id, pct, is_active = 1) => ({ id, name: `P${id}`, current_percentage: pct, is_active })
  assert.equal(backendAcceptsTotal([p(1, 33.33), p(2, 33.33), p(3, 33.34)]), true)
  assert.equal(backendAcceptsTotal([p(1, 60), p(2, 40), p(3, 25, 0)]), true)
  assert.equal(backendAcceptsTotal([p(1, 60), p(2, 30)]), false)
  // Python gives 60 + 39.99 = 99.99000000000001, within 0.01: db/ accepts it, so the banner stays off.
  assert.equal(backendAcceptsTotal([p(1, 60), p(2, 39.99)]), true)
  assert.equal(backendAcceptsTotal([p(1, 60), p(2, 39.98)]), false)
  assert.equal(backendAcceptsTotal([]), false)
  assert.equal(activeTotal([p(1, 60), p(2, 30), p(3, 10, 0)]), 90)
})

test("percentChanges: only rows whose value changes", () => {
  const partners = [
    { id: 1, current_percentage: 50 },
    { id: 2, current_percentage: 30 },
    { id: 3, current_percentage: 20 },
  ]
  const edited = new Map([
    [1, 5000],
    [2, 2500],
    [3, 2500],
  ])
  assert.deepEqual(percentChanges(partners, edited), [
    { partnerId: 2, percentage: 25 },
    { partnerId: 3, percentage: 25 },
  ])
  assert.deepEqual(percentChanges(partners, new Map()), [])
})

test("isNameTaken: case-insensitive, trimmed, includes inactive partners", () => {
  const partners = [{ name: "Alice" }, { name: "  Bob " }, { name: "رضا" }]
  assert.equal(isNameTaken("alice", partners), true)
  assert.equal(isNameTaken(" BOB", partners), true)
  assert.equal(isNameTaken("رضا ", partners), true)
  assert.equal(isNameTaken("Carol", partners), false)
  assert.equal(isNameTaken("   ", partners), false)
})

test("defaultPeriod: Jalali year start for the first payout, else the day after the latest period", () => {
  // 2026-10-09 is 17 Mehr 1405; 1 Farvardin 1405 is 2026-03-21.
  assert.equal(jalaliYearStart("2026-10-09"), "2026-03-21")
  assert.equal(jalaliYearStart("2026-03-20"), "2025-03-21")
  assert.deepEqual(defaultPeriod("2026-10-09", []), { from: "2026-03-21", to: "2026-10-09" })
  assert.deepEqual(
    defaultPeriod("2026-10-09", [{ period_end: "2026-06-30" }, { period_end: "2026-08-31" }]),
    { from: "2026-09-01", to: "2026-10-09" }
  )
  // The latest period already ends today: the range still isn't empty.
  assert.deepEqual(defaultPeriod("2026-10-09", [{ period_end: "2026-10-09" }]), { from: "2026-10-10", to: "2026-10-10" })
})

test("overCapBy: exact difference, negative undistributed, unsafe", () => {
  assert.equal(overCapBy(1_000_000, 400_000), 600_000)
  assert.equal(overCapBy(1_000, -200), 1_200)
  assert.equal(overCapBy(Number.MAX_SAFE_INTEGER, -1), null)
})

test("classifyDistributionError: the backend's codes and details", () => {
  const e = (status, code, details = {}, field = null) => ({ status, code, details, field, message: "documentation only" })
  assert.deepEqual(
    classifyDistributionError(
      e(409, "DISTRIBUTION_PERIOD_OVERLAP", { distribution_id: 4, period_start: "2026-03-01", period_end: "2026-03-31" })
    ),
    { kind: "overlap", id: 4, from: "2026-03-01", to: "2026-03-31" }
  )
  assert.deepEqual(classifyDistributionError(e(422, "DISTRIBUTION_NO_ACTIVE_PARTNERS")), { kind: "noPartners" })
  assert.deepEqual(classifyDistributionError(e(422, "DISTRIBUTION_PERCENT_SUM")), { kind: "percentSum" })
  assert.deepEqual(
    classifyDistributionError(e(422, "DISTRIBUTION_EXCEEDS_UNDISTRIBUTED", {}, "total_amount_distributed")),
    { kind: "overCap" }
  )
  // FastAPI's strict-int refusal (no code) and db/'s ">= 0" both mean a bad amount.
  assert.deepEqual(classifyDistributionError(e(422, null, {}, "total_amount_distributed")), { kind: "badAmount" })
  assert.deepEqual(classifyDistributionError(e(422, "VALIDATION_FAILED", {}, "total_amount_distributed")), { kind: "badAmount" })
  assert.deepEqual(classifyDistributionError(e(422, "DISTRIBUTION_PERIOD_ORDER", {}, "period_end")), { kind: "periodOrder" })
  assert.deepEqual(classifyDistributionError(e(422, "VALIDATION_FAILED", {}, "date")), { kind: "badDate" })
  assert.equal(classifyDistributionError(e(500, null)), null)
  assert.equal(classifyDistributionError(e(409, "CONFLICT")), null)
  assert.equal(classifyDistributionError(e(409, "DISTRIBUTION_PERIOD_OVERLAP", {})), null)
})

test("classifyDistributionError ignores message text", () => {
  const msg = (status, message, field = null) => ({ status, message, field })
  assert.equal(
    classifyDistributionError(msg(409, "Period 2026-03-15..2026-04-15 overlaps distribution #4 (2026-03-01..2026-03-31)")),
    null
  )
  assert.equal(classifyDistributionError(msg(422, "No active partners found — add partners before distributing")), null)
  assert.deepEqual(
    classifyDistributionError(msg(422, "total_amount_distributed (1000) exceeds undistributed profit", "total_amount_distributed")),
    { kind: "badAmount" }
  )
})

test("copy: Persian digits only", () => {
  assert.equal(hundredthsText(3333), "۳۳٫۳۳")
  assert.equal(hundredthsText(10000), "۱۰۰")
  assert.equal(hundredthsText(-50), "۰٫۵")
  for (const err of ["empty", "format", "decimals", "range"]) assert.doesNotMatch(percentErrorText(err), LATIN)
  for (const kind of ["noPartners", "percentSum", "overCap", "badAmount", "periodOrder", "badDate"])
    assert.doesNotMatch(distributionErrorText({ kind }), LATIN)
  assert.doesNotMatch(distributionErrorText({ kind: "overlap", id: 12, from: "2026-03-01", to: "2026-03-31" }), LATIN)
})
