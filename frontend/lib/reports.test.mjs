// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  barPercent,
  channelChecks,
  expenseChecks,
  filterProducts,
  lineAmount,
  lineSign,
  normalizeSearch,
  paymentChecks,
  paymentsIsEmpty,
  percentText,
  pnlIsEmpty,
  productChecks,
  ratioTenths,
  reconcile,
  reportLink,
  shippingChecks,
  shippingIsEmpty,
  shippingPnlChecks,
  signedTone,
  sortProducts,
  statementChecks,
  STATEMENT,
  STATEMENT_INFO,
  wasteChecks,
  wasteTotals,
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
  postage_committed: 143_476_560,
  postage_variance: 4_123_440,
  refund_losses: 16_100_000,
  refund_fee_losses: 1_600_000,
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
  assert.deepEqual(statementChecks(PNL).map((c) => c.status), ["ok", "ok", "ok", "ok"])
  const drift = statementChecks({ ...PNL, net_profit: PNL.net_profit + 1 })
  assert.deepEqual(drift.map((c) => c.status), ["ok", "ok", "mismatch", "ok"])
  assert.equal(drift[2].diff, -1)
})

test("a negative postage variance is added back: «+», profit colour, still adds up", () => {
  // Postage paid 100,000 less than the estimates frozen on orders.
  const p = {
    ...PNL,
    postage_actual: PNL.postage_committed - 100_000,
    postage_variance: -100_000,
    net_profit: PNL.net_profit + 4_123_440 + 100_000,
  }
  assert.deepEqual(lineSign("subtract", p.postage_variance), { glyph: "+", tone: "profit" })
  assert.equal(lineAmount("subtract", p.postage_variance), 100_000)
  assert.deepEqual(statementChecks(p).map((c) => c.status), ["ok", "ok", "ok", "ok"])
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

test("postage variance check: actual − committed", () => {
  const bad = statementChecks({ ...PNL, postage_committed: PNL.postage_committed + 5 })
  assert.equal(bad[3].status, "mismatch")
  assert.equal(bad[3].diff, -5)
})

test("committed postage and fee losses are information rows, outside the sums", () => {
  assert.ok(STATEMENT_INFO.includes("postage_committed"))
  assert.ok(STATEMENT_INFO.includes("refund_fee_losses"))
  const inSums = STATEMENT.flatMap((g) => g.lines.map((l) => l.key))
  assert.ok(!inSums.includes("postage_committed") && !inSums.includes("refund_fee_losses"))
})

// Shipping: fictional, built the way db/reports.py does.
const SHIP_ROWS = [
  { channel: "WEBSITE", shipped_order_count: 30, shipping_revenue: 54_000_000, packaging_cost: 21_000_000, postage_estimated: 45_000_000, net: -12_000_000, net_per_order: -400_000 },
  { channel: "INSTAGRAM", shipped_order_count: 20, shipping_revenue: 36_000_000, packaging_cost: 14_000_000, postage_estimated: 30_000_000, net: -8_000_000, net_per_order: -400_000 },
]
const SHIP = {
  shipping_revenue: 90_000_000,
  packaging_cost: 35_000_000,
  postage_estimated: 75_000_000,
  postage_actual: 60_000_000,
  net_shipping_result: -5_000_000,
  net_shipping_result_estimated: -20_000_000,
  postage_gap: 15_000_000,
  order_count: 87,
  shipped_order_count: 50,
}

test("shipping summary equals its channel rows and its own definitions", () => {
  const c = shippingChecks(SHIP, SHIP_ROWS)
  assert.deepEqual(Object.values(c).map((x) => x.status), ["ok", "ok", "ok", "ok", "ok", "ok", "ok"])
  assert.equal(shippingChecks(SHIP, SHIP_ROWS.slice(1)).shipped.diff, -30)
  assert.equal(shippingChecks({ ...SHIP, postage_gap: -15_000_000 }, SHIP_ROWS).gap.status, "mismatch")
  assert.equal(shippingChecks({ ...SHIP, net_shipping_result: 1 }, SHIP_ROWS).actualResult.status, "mismatch")
})

test("shipping vs P&L: order count and postage paid", () => {
  const ok = shippingPnlChecks({ ...SHIP, postage_actual: PNL.postage_actual }, PNL)
  assert.deepEqual([ok.orders.status, ok.postageActual.status], ["ok", "ok"])
  assert.equal(shippingPnlChecks(SHIP, PNL).postageActual.status, "mismatch")
  assert.ok(shippingIsEmpty({ ...SHIP, shipped_order_count: 0, postage_actual: 0 }, []))
  assert.ok(!shippingIsEmpty({ ...SHIP, shipped_order_count: 0 }, []), "a paid batch alone is not empty")
})

const PAY = [
  { payment_method_id: 1, order_count: 60, customer_total: 1_500_000_000, transaction_fees: 10_000_000, fees_lost_on_returns: 1_600_000, pending_expected: 0, settled_expected: 0, settled_received: 0, settlement_difference: 0 },
  { payment_method_id: null, order_count: 27, customer_total: 364_200_000, transaction_fees: 2_600_000, fees_lost_on_returns: 0, pending_expected: 0, settled_expected: 0, settled_received: 0, settlement_difference: 0 },
]

test("payment methods vs P&L, including the exact fee-loss check", () => {
  const c = paymentChecks(PAY, PNL)
  assert.deepEqual([c.orders.status, c.revenue.status, c.fees.status, c.lostFees.status], ["ok", "ok", "ok", "ok"])
  const off = paymentChecks([{ ...PAY[0], fees_lost_on_returns: 1_599_999 }, PAY[1]], PNL)
  assert.equal(off.lostFees.status, "mismatch")
  assert.equal(off.lostFees.diff, -1)
  assert.ok(!paymentsIsEmpty(PAY))
  assert.ok(paymentsIsEmpty(PAY.map((r) => ({ ...r, ...Object.fromEntries(Object.keys(r).filter((k) => k !== "payment_method_id").map((k) => [k, 0])) }))))
  assert.ok(!paymentsIsEmpty([{ ...PAY[1], order_count: 0, customer_total: 0, transaction_fees: 0, settled_received: 5 }]))
})

test("waste: unknown costs are left out, never counted as 0", () => {
  const rows = [
    { item_type: "MATERIAL", item_id: 1, cost: 832, unknown_cost_count: 0 },
    { item_type: "MATERIAL", item_id: 2, cost: 12_000, unknown_cost_count: 2 },
    { item_type: "PRODUCT", item_id: 3, cost: null, unknown_cost_count: 1 },
  ]
  assert.deepEqual(wasteTotals(rows), { knownCost: 12_832, unknownRows: 1, partialRows: 1 })
  assert.equal(wasteChecks(rows, { ...PNL, waste_cost: 12_832 }).cost.status, "ok")
  assert.equal(wasteChecks(rows, { ...PNL, waste_cost: 12_833 }).cost.diff, -1)
  assert.deepEqual(wasteTotals([]), { knownCost: 0, unknownRows: 0, partialRows: 0 })
})

test("expenses vs P&L operating expenses", () => {
  const rows = [
    { category_id: 1, total_amount: 200_000_000, expense_count: 3 },
    { category_id: 2, total_amount: 70_000_000, expense_count: 1 },
  ]
  assert.equal(expenseChecks(rows, PNL).total.status, "ok")
  assert.equal(expenseChecks(rows.slice(1), PNL).total.diff, -200_000_000)
})

test("signed figures take glyph and colour from the real sign", () => {
  assert.deepEqual(signedTone(5), { glyph: "+", tone: "profit" })
  assert.deepEqual(signedTone(-5), { glyph: "", tone: "loss" })
  assert.deepEqual(signedTone(0), { glyph: "", tone: "plain" })
  assert.deepEqual(signedTone(5, true), { glyph: "+", tone: "plain" })
  assert.deepEqual(signedTone(-5, true), { glyph: "", tone: "plain" })
})

test("links carry the period; all time gives no link", () => {
  const r = { from: "2026-09-23", to: "2026-10-22" }
  assert.equal(reportLink("/expenses", { category: "4" }, r), "/expenses?category=4&from=2026-09-23&to=2026-10-22")
  assert.equal(reportLink("/adjustments", { kind: "waste", item: "MATERIAL:7" }, r), "/adjustments?kind=waste&item=MATERIAL%3A7&from=2026-09-23&to=2026-10-22")
  assert.equal(reportLink("/expenses", { category: "4" }, null), null)
})
