// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  barPercent,
  channelChecks,
  filterProducts,
  lineAmount,
  lineSign,
  normalizeSearch,
  percentText,
  pnlIsEmpty,
  productChecks,
  ratioTenths,
  reconcile,
  sortProducts,
  statementChecks,
  STATEMENT,
  STATEMENT_INFO,
} from "./reports.ts"

// A consistent fictional P&L (Rial), built the way db/reports.py does.
const PNL = {
  items_revenue: 1_749_000_000,
  shipping_revenue: 115_200_000,
  total_revenue: 1_864_200_000,
  cogs: 913_360_000,
  packaging_cost: 71_200_000,
  postage_estimated: 143_476_560,
  transaction_fees: 12_600_000,
  gross_profit: 723_563_440,
  postage_actual: 147_600_000,
  postage_variance: 4_123_440,
  refund_losses: 16_100_000,
  waste_cost: 12_880_000,
  operating_expenses: 270_000_000,
  net_profit: 420_460_000,
  order_count: 87,
}
const ZERO = Object.fromEntries(Object.keys(PNL).map((k) => [k, 0]))

test("reconcile: exact match, signed difference, empty list", () => {
  assert.deepEqual(reconcile(10, [4, 6]), { status: "ok", expected: 10, actual: 10 })
  assert.deepEqual(reconcile(10, [4, 5]), { status: "mismatch", expected: 10, actual: 9, diff: -1 })
  assert.deepEqual(reconcile(10, [4, 7]), { status: "mismatch", expected: 10, actual: 11, diff: 1 })
  assert.deepEqual(reconcile(0, []), { status: "ok", expected: 0, actual: 0 })
  assert.deepEqual(reconcile(5, []), { status: "mismatch", expected: 5, actual: 0, diff: -5 })
})

test("reconcile: no tolerance, and non-integers are invalid, never rounded", () => {
  assert.equal(reconcile(1_000_000_001, [1_000_000_000]).status, "mismatch")
  assert.deepEqual(reconcile(10, [4.5, 5.5]), { status: "invalid" })
  assert.deepEqual(reconcile(10.5, [10]), { status: "invalid" })
  assert.deepEqual(reconcile(10, [null]), { status: "invalid" })
  assert.deepEqual(reconcile(0, [Number.MAX_SAFE_INTEGER, 1]), { status: "invalid" })
})

test("the statement covers every P&L key exactly once", () => {
  const keys = [...STATEMENT.flatMap((g) => g.lines.map((l) => l.key)), ...STATEMENT_INFO]
  assert.deepEqual([...keys].sort(), Object.keys(PNL).sort())
  assert.equal(new Set(keys).size, keys.length)
})

test("statement checks pass on a consistent P&L and catch a drift", () => {
  assert.deepEqual(statementChecks(PNL).map((c) => c.status), ["ok", "ok", "ok"])
  const drift = statementChecks({ ...PNL, net_profit: PNL.net_profit + 1 })
  assert.deepEqual(drift.map((c) => c.status), ["ok", "ok", "mismatch"])
  assert.equal(drift[2].diff, -1)
})

test("a negative postage variance is added back: «+», profit colour, still adds up", () => {
  // Postage paid 100,000 less than the estimates frozen on orders.
  const p = { ...PNL, postage_variance: -100_000, net_profit: PNL.net_profit + 4_123_440 + 100_000 }
  assert.deepEqual(lineSign("subtract", p.postage_variance), { glyph: "+", tone: "profit" })
  assert.equal(lineAmount("subtract", p.postage_variance), 100_000)
  assert.deepEqual(statementChecks(p).map((c) => c.status), ["ok", "ok", "ok"])
})

test("line signs follow the real sign", () => {
  assert.deepEqual(lineSign("subtract", 4_123_440), { glyph: "−", tone: "loss" })
  assert.deepEqual(lineSign("subtract", 0), { glyph: "−", tone: "plain" })
  assert.deepEqual(lineSign("add", 115_200_000), { glyph: "", tone: "plain" })
  assert.deepEqual(lineSign("total", 420_460_000), { glyph: "=", tone: "profit" })
  assert.deepEqual(lineSign("total", -5), { glyph: "=", tone: "loss" })
  assert.deepEqual(lineSign("total", 0), { glyph: "=", tone: "plain" })
  // Subtotals keep their sign; subtracted lines print the absolute value.
  assert.equal(lineAmount("total", -5), -5)
  assert.equal(lineAmount("subtract", 7), 7)
})

test("empty period: every figure is 0; expenses alone are not empty", () => {
  assert.equal(pnlIsEmpty(ZERO), true)
  assert.equal(pnlIsEmpty({ ...ZERO, operating_expenses: 1, net_profit: -1 }), false)
  assert.equal(pnlIsEmpty(PNL), false)
})

test("ratios: tenths of a percent, one decimal, null on a zero base", () => {
  assert.equal(ratioTenths(1_749_000_000, 1_864_200_000), 938)
  assert.equal(ratioTenths(1, 1), 1000)
  assert.equal(ratioTenths(-25, 1000), -25)
  assert.equal(ratioTenths(1, 3000), 0)
  assert.equal(ratioTenths(5, 0), null)
  assert.equal(percentText(938), "۹۳٫۸٪")
  assert.equal(percentText(1000), "۱۰۰٪")
  assert.equal(percentText(0), "۰٪")
  assert.equal(percentText(-25), "‎−۲٫۵٪")
})

test("bars scale to the period's largest value; negatives draw none", () => {
  assert.equal(barPercent(50, 100), 50)
  assert.equal(barPercent(100, 100), 100)
  assert.equal(barPercent(1, 10_000), 1)
  assert.equal(barPercent(-5, 100), 0)
  assert.equal(barPercent(5, 0), 0)
})

const ROWS = [
  { product_id: 1, product_name: "وینیل آلبوم اول", units_sold: 32, total_revenue: 724_000_000, total_cost: 441_600_000, total_profit: 282_400_000 },
  { product_id: 2, product_name: "تی‌شرت لوگو مشکی (L)", units_sold: 26, total_revenue: 221_400_000, total_cost: 106_600_000, total_profit: 114_800_000 },
  { product_id: 3, product_name: "پوستر تور ۱۴۰۴", units_sold: 64, total_revenue: 169_000_000, total_cost: 60_800_000, total_profit: 108_200_000 },
  { product_id: 4, product_name: "استیکر پک", units_sold: 92, total_revenue: 126_600_000, total_cost: 34_960_000, total_profit: 91_640_000 },
  { product_id: 5, product_name: "نمونه رایگان", units_sold: 3, total_revenue: 0, total_cost: 900_000, total_profit: -900_000 },
]

test("search normalises Arabic letters, ZWNJ and digits", () => {
  assert.equal(normalizeSearch("  تي‌شرت  ك "), "تیشرت ک")
  assert.deepEqual(filterProducts(ROWS, "تيشرت").map((r) => r.product_id), [2])
  assert.deepEqual(filterProducts(ROWS, "1404").map((r) => r.product_id), [3])
  assert.deepEqual(filterProducts(ROWS, "").map((r) => r.product_id), [1, 2, 3, 4, 5])
  assert.deepEqual(filterProducts(ROWS, "zzz"), [])
})

test("sort by each column, both directions; ties keep the backend order", () => {
  const ids = (rows) => rows.map((r) => r.product_id)
  assert.deepEqual(ids(sortProducts(ROWS, "profit", "desc")), [1, 2, 3, 4, 5])
  assert.deepEqual(ids(sortProducts(ROWS, "profit", "asc")), [5, 4, 3, 2, 1])
  assert.deepEqual(ids(sortProducts(ROWS, "units", "desc")), [4, 3, 1, 2, 5])
  assert.deepEqual(ids(sortProducts(ROWS, "cost", "asc")), [5, 4, 3, 2, 1])
  // A product with no revenue has no margin: last when descending.
  assert.deepEqual(ids(sortProducts(ROWS, "margin", "desc")), [4, 3, 2, 1, 5])
  const tied = [ROWS[0], { ...ROWS[1], total_revenue: ROWS[0].total_revenue }]
  assert.deepEqual(ids(sortProducts(tied, "revenue", "desc")), [1, 2])
  assert.deepEqual(ids(sortProducts(tied, "revenue", "asc")), [1, 2])
  assert.equal(sortProducts(ROWS, "name", "asc").length, 5)
})

test("product and channel checks compare with the P&L", () => {
  const p = { ...PNL, items_revenue: 1_241_000_000, cogs: 644_860_000 }
  assert.deepEqual(productChecks(ROWS, p).revenue.status, "ok")
  assert.deepEqual(productChecks(ROWS, p).cost.status, "ok")
  assert.deepEqual(productChecks(ROWS.slice(1), p).revenue.diff, -724_000_000)

  const channels = [
    { channel: "WEBSITE", order_count: 50, total_revenue: 1_000_000_000, total_profit: 400_000_000 },
    { channel: "IN_PERSON", order_count: 37, total_revenue: 864_200_000, total_profit: 323_563_440 },
  ]
  const c = channelChecks(channels, PNL)
  assert.deepEqual([c.orders.status, c.revenue.status, c.profit.status], ["ok", "ok", "ok"])
  assert.equal(channelChecks(channels.slice(0, 1), PNL).orders.diff, -37)
})
