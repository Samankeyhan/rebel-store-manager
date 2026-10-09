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
  postage_variance: number
  refund_losses: number
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

/** Returned figures that are not part of the sum: shown under the statement. */
export const STATEMENT_INFO: readonly PnlKey[] = ["postage_actual", "order_count"]

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
