/**
 * Reports helpers with no React and no API calls, so `npm test` can run them:
 * the «مطابقت» checks, the P&L statement layout and its line signs, the
 * empty-period test, display ratios and the product table's search and sort.
 *
 * Every figure comes from GET /reports/* (db/reports.py). The frontend only
 * sums returned integers to compare them with another returned integer; it
 * never computes a profit, a cost or any other money value of its own.
 */

import { toLatinDigits, toPersianDigits, MINUS } from "./persian-numbers.ts"

// ── reconciliation ─────────────────────────────────────────────────────────

export type Check =
  | { status: "ok"; expected: number; actual: number }
  | { status: "mismatch"; expected: number; actual: number; diff: number }
  /** A figure was not a safe integer Rial: nothing can be said. */
  | { status: "invalid" }

const isRial = (n: unknown): n is number => typeof n === "number" && Number.isSafeInteger(n)

/**
 * Compares `expected` (one backend figure) with the sum of `parts` (other
 * backend figures, already signed). Exact: integer Rial, no tolerance.
 * diff = actual − expected.
 */
export function reconcile(expected: number, parts: readonly number[]): Check {
  if (!isRial(expected) || !parts.every(isRial)) return { status: "invalid" }
  let actual = 0
  for (const p of parts) actual += p
  if (!Number.isSafeInteger(actual)) return { status: "invalid" }
  return actual === expected ? { status: "ok", expected, actual } : { status: "mismatch", expected, actual, diff: actual - expected }
}

// ── P&L statement ──────────────────────────────────────────────────────────

/** The keys of GET /reports/profit-and-loss (api/schemas/reports.py ProfitAndLossOut). */
export type PnlFigures = {
  items_revenue: number
  shipping_revenue: number
  total_revenue: number
  cogs: number
  packaging_cost: number
  postage_estimated: number
  transaction_fees: number
  gross_profit: number
  postage_actual: number
  postage_committed: number
  postage_variance: number
  refund_losses: number
  refund_fee_losses: number
  waste_cost: number
  operating_expenses: number
  net_profit: number
  order_count: number
}
export type PnlKey = keyof PnlFigures

/** add = adds to the subtotal, subtract = taken off it, total = the subtotal itself. */
export type LineRole = "add" | "subtract" | "total"
export type StatementLine = { key: PnlKey; role: LineRole }
export type StatementGroup = { id: "revenue" | "orderCosts" | "afterGross"; lines: StatementLine[] }

/** accounting-rules §9, in order: each group ends with the subtotal it builds. */
export const STATEMENT: readonly StatementGroup[] = [
  {
    id: "revenue",
    lines: [
      { key: "items_revenue", role: "add" },
      { key: "shipping_revenue", role: "add" },
      { key: "total_revenue", role: "total" },
    ],
  },
  {
    id: "orderCosts",
    lines: [
      { key: "cogs", role: "subtract" },
      { key: "packaging_cost", role: "subtract" },
      { key: "postage_estimated", role: "subtract" },
      { key: "transaction_fees", role: "subtract" },
      { key: "gross_profit", role: "total" },
    ],
  },
  {
    id: "afterGross",
    lines: [
      { key: "postage_variance", role: "subtract" },
      { key: "refund_losses", role: "subtract" },
      { key: "waste_cost", role: "subtract" },
      { key: "operating_expenses", role: "subtract" },
      { key: "net_profit", role: "total" },
    ],
  },
]

/**
 * Returned figures that are not part of the sum: shown under the statement.
 * postage_committed and refund_fee_losses are parts of postage_variance and
 * refund_losses, shown for explanation only (§9), never deducted again.
 */
export const STATEMENT_INFO: readonly PnlKey[] = ["postage_actual", "postage_committed", "refund_fee_losses", "order_count"]

export type LineSign = { glyph: "+" | "−" | "=" | ""; tone: "profit" | "loss" | "plain" }

/**
 * The sign cell and colour of a statement line, from the figure's real sign.
 * A subtracted line shows its absolute value: positive is a cost («−», loss
 * colour), negative is added back to profit («+», profit colour) — e.g. a
 * negative postage_variance (postage cost less than estimated). A subtotal
 * shows «=» and its own sign; an added line shows no glyph.
 */
export function lineSign(role: LineRole, value: number): LineSign {
  if (role === "total") return { glyph: "=", tone: value > 0 ? "profit" : value < 0 ? "loss" : "plain" }
  if (role === "add") return { glyph: "", tone: value < 0 ? "loss" : "plain" }
  if (value > 0) return { glyph: "−", tone: "loss" }
  if (value < 0) return { glyph: "+", tone: "profit" }
  return { glyph: "−", tone: "plain" }
}

/** The amount a statement line prints: subtracted lines carry their sign in the glyph. */
export function lineAmount(role: LineRole, value: number): number {
  return role === "subtract" ? Math.abs(value) : value
}

/**
 * The statement adds up: each subtotal equals its group's lines, signed as
 * the statement shows them (the previous subtotal carried into the next group).
 * The fourth: postage_variance = postage_actual − postage_committed (§9).
 */
export function statementChecks(p: PnlFigures): Check[] {
  return [
    reconcile(p.total_revenue, [p.items_revenue, p.shipping_revenue]),
    reconcile(p.gross_profit, [p.total_revenue, -p.cogs, -p.packaging_cost, -p.postage_estimated, -p.transaction_fees]),
    reconcile(p.net_profit, [
      p.gross_profit,
      -p.postage_variance,
      -p.refund_losses,
      -p.waste_cost,
      -p.operating_expenses,
    ]),
    reconcile(p.postage_variance, [p.postage_actual, -p.postage_committed]),
  ]
}

/** GET /reports/channels row. */
export type ChannelRow = { channel: string; order_count: number; total_revenue: number; total_profit: number }

/** Products vs P&L (accounting-rules §9: must reconcile exactly): revenue, cost. */
export function productChecks(rows: readonly ProductRow[], p: PnlFigures) {
  return {
    revenue: reconcile(p.items_revenue, rows.map((r) => r.total_revenue)),
    cost: reconcile(p.cogs, rows.map((r) => r.total_cost)),
  }
}

/** Channels vs P&L: same order set, and order profit summed is gross profit. */
export function channelChecks(rows: readonly ChannelRow[], p: PnlFigures) {
  return {
    orders: reconcile(p.order_count, rows.map((r) => r.order_count)),
    revenue: reconcile(p.total_revenue, rows.map((r) => r.total_revenue)),
    profit: reconcile(p.gross_profit, rows.map((r) => r.total_profit)),
  }
}

// ── part 2: shipping, payment methods, waste, expenses ─────────────────────

/** GET /reports/shipping (ShippingSummaryOut): the figures the checks read. */
export type ShippingFigures = {
  shipping_revenue: number
  packaging_cost: number
  postage_estimated: number
  postage_actual: number
  net_shipping_result: number
  net_shipping_result_estimated: number
  postage_gap: number
  order_count: number
  shipped_order_count: number
}
/** GET /reports/shipping-by-channel row. */
export type ShippingChannelRow = {
  channel: string
  shipped_order_count: number
  shipping_revenue: number
  packaging_cost: number
  postage_estimated: number
  net: number
  net_per_order: number
}

/**
 * Shipping summary vs its own per-channel rows (§9: these totals equal the
 * shipping-by-channel totals), and the summary's two results and postage_gap
 * against the summary figures they are defined from.
 */
export function shippingChecks(s: ShippingFigures, rows: readonly ShippingChannelRow[]) {
  return {
    shipped: reconcile(s.shipped_order_count, rows.map((r) => r.shipped_order_count)),
    revenue: reconcile(s.shipping_revenue, rows.map((r) => r.shipping_revenue)),
    packaging: reconcile(s.packaging_cost, rows.map((r) => r.packaging_cost)),
    estimated: reconcile(s.postage_estimated, rows.map((r) => r.postage_estimated)),
    net: reconcile(s.net_shipping_result_estimated, rows.map((r) => r.net)),
    actualResult: reconcile(s.net_shipping_result, [s.shipping_revenue, -s.packaging_cost, -s.postage_actual]),
    gap: reconcile(s.postage_gap, [s.postage_estimated, -s.postage_actual]),
  }
}

/** Shipping vs P&L: the same eligible order count and the same postage batches (§9). */
export function shippingPnlChecks(s: ShippingFigures, p: PnlFigures) {
  return {
    orders: reconcile(p.order_count, [s.order_count]),
    postageActual: reconcile(p.postage_actual, [s.postage_actual]),
  }
}

/** No shipped order and no postage batch paid in the period. */
export function shippingIsEmpty(s: ShippingFigures, rows: readonly ShippingChannelRow[]): boolean {
  return rows.length === 0 && s.shipped_order_count === 0 && s.postage_actual === 0
}

/** GET /reports/payment-methods row (PaymentMethodReportRowOut). */
export type PaymentRow = {
  payment_method_id: number | null
  order_count: number
  customer_total: number
  transaction_fees: number
  fees_lost_on_returns: number
  pending_expected: number
  settled_expected: number
  settled_received: number
  settlement_difference: number
}

const PAYMENT_FIGURES = [
  "order_count",
  "customer_total",
  "transaction_fees",
  "fees_lost_on_returns",
  "pending_expected",
  "settled_expected",
  "settled_received",
  "settlement_difference",
] as const

/** Payment methods vs P&L (§14): order set, customer totals, fees, and fees lost on returns. */
export function paymentChecks(rows: readonly PaymentRow[], p: PnlFigures) {
  return {
    orders: reconcile(p.order_count, rows.map((r) => r.order_count)),
    revenue: reconcile(p.total_revenue, rows.map((r) => r.customer_total)),
    fees: reconcile(p.transaction_fees, rows.map((r) => r.transaction_fees)),
    lostFees: reconcile(p.refund_fee_losses, rows.map((r) => r.fees_lost_on_returns)),
  }
}

/** Every figure on every row is 0 (rows are still listed for active methods). */
export function paymentsIsEmpty(rows: readonly PaymentRow[]): boolean {
  return rows.every((r) => PAYMENT_FIGURES.every((k) => r[k] === 0))
}

/** GET /reports/waste row; cost null = every movement's unit cost was unknown. */
export type WasteRow = { item_type: string; item_id: number; cost: number | null; unknown_cost_count: number }

/**
 * The waste table's foot: the sum of the known costs (what the P&L sums, §8),
 * rows with no cost at all, and rows whose cost leaves some movements out.
 * An unknown cost is never counted as 0.
 */
export function wasteTotals(rows: readonly WasteRow[]) {
  const known = rows.filter((r) => r.cost !== null)
  return {
    knownCost: known.reduce((s, r) => s + (r.cost as number), 0),
    unknownRows: rows.length - known.length,
    partialRows: known.filter((r) => r.unknown_cost_count > 0).length,
  }
}

/** Waste vs P&L (§8): the known per-item costs sum exactly to waste_cost. */
export function wasteChecks(rows: readonly WasteRow[], p: PnlFigures) {
  return {
    cost: reconcile(
      p.waste_cost,
      rows.filter((r) => r.cost !== null).map((r) => r.cost as number)
    ),
  }
}

/** GET /reports/expenses row. */
export type ExpenseRow = { category_id: number; total_amount: number; expense_count: number }

/** Expenses vs P&L: the categories sum to operating_expenses. */
export function expenseChecks(rows: readonly ExpenseRow[], p: PnlFigures) {
  return { total: reconcile(p.operating_expenses, rows.map((r) => r.total_amount)) }
}

export type SignedTone = { glyph: "+" | ""; tone: "profit" | "loss" | "plain" }

/**
 * A signed figure (a net result, a gap, a difference) from its real sign:
 * positive gets «+» (a negative already prints its minus); profit/loss
 * colour, or plain for a figure that is neither (`neutral`, e.g. postage_gap).
 */
export function signedTone(value: number, neutral = false): SignedTone {
  const glyph = value > 0 ? "+" : ""
  if (neutral) return { glyph, tone: "plain" }
  return { glyph, tone: value > 0 ? "profit" : value < 0 ? "loss" : "plain" }
}

/**
 * A link to another screen filtered to the report's period (?from=&to=).
 * Those screens have no all-time URL, so all time (range null) gives null:
 * no link rather than one that silently shows a different period.
 */
export function reportLink(
  path: string,
  params: Readonly<Record<string, string>>,
  range: { from: string; to: string } | null
): string | null {
  if (!range) return null
  const qs = new URLSearchParams(params)
  qs.set("from", range.from)
  qs.set("to", range.to)
  return `${path}?${qs.toString()}`
}

/** No activity at all in the period: every returned figure is 0. */
export function pnlIsEmpty(p: PnlFigures): boolean {
  return (Object.values(p) as number[]).every((v) => v === 0)
}

// ── display ratios ─────────────────────────────────────────────────────────

// Ratios (% of revenue, margin) are display ratios of two integers the API
// returned; nothing here derives a money value (no averages, no shares of money).

/** part ÷ whole as tenths of a percent (938 = 93.8%), rounded half away from zero; null when whole is 0. */
export function ratioTenths(part: number, whole: number): number | null {
  if (!whole) return null
  const t = (Math.abs(part) * 1000) / Math.abs(whole)
  const sign = Math.sign(part) * Math.sign(whole)
  const r = Math.round(t)
  return r === 0 ? 0 : sign * r
}

/** 938 → «۹۳٫۸٪», 1000 → «۱۰۰٪», −25 → «‎−۲٫۵٪». */
export function percentText(tenths: number): string {
  // Split the digits, not the number: tenths are a count, not money.
  const digits = String(Math.abs(tenths))
  const whole = digits.slice(0, -1) || "0"
  const frac = digits.slice(-1)
  const body = toPersianDigits(whole) + (frac !== "0" ? "٫" + toPersianDigits(frac) : "")
  return (tenths < 0 ? MINUS : "") + body + "٪"
}

/** Bar width (0–100) of a value against the period's largest; negatives and an empty scale draw no bar. */
export function barPercent(value: number, max: number): number {
  if (max <= 0 || value <= 0) return 0
  return Math.max(1, Math.round((value / max) * 100))
}

// ── product table ──────────────────────────────────────────────────────────

/** GET /reports/products row. */
export type ProductRow = {
  product_id: number
  product_name: string
  units_sold: number
  total_revenue: number
  total_cost: number
  total_profit: number
}

export const PRODUCT_SORT_KEYS = ["name", "units", "revenue", "cost", "profit", "margin"] as const
export type ProductSortKey = (typeof PRODUCT_SORT_KEYS)[number]
export type SortDir = "asc" | "desc"

/** Search text: Latin digits, Persian ی/ک for Arabic ي/ى/ك, no ZWNJ/tatweel, lower case, single spaces. */
export function normalizeSearch(text: string): string {
  return toLatinDigits(text)
    .replace(/[يى]/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/[‌‍ـ]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim()
}

export function filterProducts<T extends ProductRow>(rows: readonly T[], query: string): T[] {
  const q = normalizeSearch(query)
  if (!q) return [...rows]
  return rows.filter((r) => normalizeSearch(r.product_name).includes(q))
}

const marginSortValue = (r: ProductRow) => {
  const t = ratioTenths(r.total_profit, r.total_revenue)
  return t ?? Number.NEGATIVE_INFINITY
}

/** Stable sort; ties keep the backend's order (profit, highest first). */
export function sortProducts<T extends ProductRow>(rows: readonly T[], key: ProductSortKey, dir: SortDir): T[] {
  const sign = dir === "asc" ? 1 : -1
  const value = (r: ProductRow): number | string => {
    switch (key) {
      case "name":
        return r.product_name
      case "units":
        return r.units_sold
      case "revenue":
        return r.total_revenue
      case "cost":
        return r.total_cost
      case "profit":
        return r.total_profit
      case "margin":
        return marginSortValue(r)
    }
  }
  return rows
    .map((row, i) => ({ row, i }))
    .sort((a, b) => {
      const va = value(a.row)
      const vb = value(b.row)
      const c =
        typeof va === "string" && typeof vb === "string" ? va.localeCompare(vb, "fa") : va < vb ? -1 : va > vb ? 1 : 0
      return c !== 0 ? sign * c : a.i - b.i
    })
    .map((x) => x.row)
}
