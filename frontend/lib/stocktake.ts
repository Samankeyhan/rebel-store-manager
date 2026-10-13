/**
 * The pure logic of the stocktake screen (no React, no API calls, so `npm test` can run it): reading a typed count,
 * the difference against the system stock, one row's state, the filters, keyboard moves and the browser draft.
 *
 * The difference mirrors db/stocktake.py `difference` exactly: counted − system as exact decimals, rounded half-even
 * to 1e-9, so binary-float noise in a REAL stock (0.1 + 0.2) is "no change". It is done with BigInt, never with
 * float subtraction. Money values are not computed here: the confirmation step shows what the API's preview returns.
 */

import { parseMinStock } from "./min-stock.ts"
import { toLatinDigits } from "./persian-numbers.ts"

export type ItemKind = "PRODUCT" | "MATERIAL"

export const MAX_QUANTITY = 1_000_000_000 // db/constants.py MAX_QUANTITY

/** The draft/row key of an item: "P:12" or "M:3". */
export function itemKey(kind: ItemKind, id: number): string {
  return `${kind === "PRODUCT" ? "P" : "M"}:${id}`
}

// ----------------------------------------------------------------- reading a typed count

export type CountParse = { ok: true; value: number | null } | { ok: false; reason: "format" | "ambiguous" }

/**
 * A typed count: blank = not counted (null). Persian and Latin digits, "٫" and "." are the decimal separators, the
 * Persian thousands mark "٬" (what formatQuantity prints) is ignored. Anything ambiguous is refused, not guessed:
 * "," and "/" (decimal or thousands?), negatives, letters, exponents. Same reader as the minimum-stock field
 * (lib/min-stock.ts parseMinStock) once those two characters are ruled out.
 */
export function parseCount(text: string): CountParse {
  if (/[,/]/.test(toLatinDigits(text))) return { ok: false, reason: "ambiguous" }
  const parsed = parseMinStock(text)
  if (!parsed.ok) return { ok: false, reason: "format" }
  return parsed
}

// ------------------------------------------------------------------- exact differences

const SCALE_DIGITS = 20
// BigInt() calls, not literals: the TypeScript target here predates ES2020 literals (lib/money.ts does the same).
const ZERO = BigInt(0)
const ONE = BigInt(1)
const TWO = BigInt(2)
const pow10 = (digits: number): bigint => BigInt("1" + "0".repeat(digits))
const SCALE = pow10(SCALE_DIGITS)
const BILLIONTH = pow10(SCALE_DIGITS - 9)

/** A number as the decimal it prints as (what Python's repr gives the backend), scaled by 1e20. */
function toScaled(n: number): bigint {
  const text = /e/i.test(String(n)) ? n.toFixed(SCALE_DIGITS) : String(n)
  const negative = text.startsWith("-")
  const [whole, fraction = ""] = text.replace("-", "").split(".")
  const scaled = BigInt(whole) * SCALE + BigInt((fraction + "0".repeat(SCALE_DIGITS)).slice(0, SCALE_DIGITS))
  return negative ? -scaled : scaled
}

/** Divide by BILLIONTH rounding half to even (the result is in units of 1e-9). */
function roundHalfEven(value: bigint): bigint {
  const negative = value < ZERO
  const abs = negative ? -value : value
  let quotient = abs / BILLIONTH
  const twice = (abs % BILLIONTH) * TWO
  if (twice > BILLIONTH || (twice === BILLIONTH && quotient % TWO === ONE)) quotient += ONE
  return negative ? -quotient : quotient
}

/** counted − system in units of 1e-9 (exact decimal arithmetic, rounded half-even). */
export function differenceNanos(counted: number, system: number): bigint {
  return roundHalfEven(toScaled(counted) - toScaled(system))
}

/** counted − system as a number (0 when it rounds to nothing). */
export function difference(counted: number, system: number): number {
  const nanos = differenceNanos(counted, system)
  if (nanos === ZERO) return 0
  const negative = nanos < ZERO
  const abs = (negative ? -nanos : nanos).toString().padStart(10, "0")
  const value = Number(`${abs.slice(0, -9)}.${abs.slice(-9)}`)
  return negative ? -value : value
}

// ----------------------------------------------------------------------- row state

export type RowStatus = "blank" | "invalid" | "same" | "gain" | "loss"
export type InvalidReason = "format" | "ambiguous" | "notWhole" | "tooLarge"

export type RowState = {
  status: RowStatus
  counted: number | null
  difference: number
  reason?: InvalidReason
  /** A gain on an item with no unit cost: the cost must be entered before applying. */
  needsCost: boolean
}

export function rowState(input: {
  kind: ItemKind
  systemQuantity: number
  countText: string
  /** The item's current unit cost is unknown (products start without one). */
  costUnknown: boolean
  /** A cost has been entered for this row (Rial). */
  hasCost: boolean
}): RowState {
  const parsed = parseCount(input.countText)
  if (!parsed.ok) return { status: "invalid", counted: null, difference: 0, reason: parsed.reason, needsCost: false }
  if (parsed.value === null) return { status: "blank", counted: null, difference: 0, needsCost: false }
  if (parsed.value > MAX_QUANTITY) return { status: "invalid", counted: null, difference: 0, reason: "tooLarge", needsCost: false }
  if (input.kind === "PRODUCT" && !Number.isInteger(parsed.value)) {
    return { status: "invalid", counted: null, difference: 0, reason: "notWhole", needsCost: false }
  }
  const diff = difference(parsed.value, input.systemQuantity)
  if (diff === 0) return { status: "same", counted: parsed.value, difference: 0, needsCost: false }
  if (diff < 0) return { status: "loss", counted: parsed.value, difference: diff, needsCost: false }
  return { status: "gain", counted: parsed.value, difference: diff, needsCost: input.costUnknown && !input.hasCost }
}

// ------------------------------------------------------------------------- filters

/** Search text folded the way names are compared: Arabic Yeh/Kaf → Persian, digits → Latin, no ZWNJ, lower case. */
export function foldSearch(text: string): string {
  return toLatinDigits(text)
    .replace(/ي/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/‌/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
}

export type FilterRow = { key: string; name: string; category: string; isActive: boolean }

export function filterRows<T extends FilterRow>(
  rows: T[],
  options: { query: string; category: string; onlyDifferences: boolean; showInactive: boolean },
  statusOf: (row: T) => RowStatus
): T[] {
  const query = foldSearch(options.query)
  return rows.filter((row) => {
    if (!options.showInactive && !row.isActive) return false
    if (options.category && row.category !== options.category) return false
    if (query && !foldSearch(row.name).includes(query)) return false
    if (options.onlyDifferences) {
      const status = statusOf(row)
      if (status !== "gain" && status !== "loss" && status !== "invalid") return false
    }
    return true
  })
}

// ---------------------------------------------------------------------- keyboard

/** The key of the row to focus when moving `delta` rows from `current` in the visible list; null at the ends. */
export function moveFocus(keys: string[], current: string, delta: 1 | -1): string | null {
  const index = keys.indexOf(current)
  if (index < 0) return null
  return keys[index + delta] ?? null
}

// ------------------------------------------------------------------------- draft

export const DRAFT_KEY = "rebel.stocktake.draft.v1"
const DRAFT_VERSION = 1

export type Draft = {
  version: 1
  savedAt: string
  /** The stocktake day, "YYYY-MM-DD", or null for "today". */
  date: string | null
  /** The count as typed, by item key. */
  counts: Record<string, string>
  /** Unit costs entered for gains, integer Rial, by item key. */
  costs: Record<string, number>
  /** The system quantity when the count was typed, by item key (to flag rows that moved since). */
  seen: Record<string, number>
}

export type StorageLike = { getItem(key: string): string | null; setItem(key: string, value: string): void; removeItem(key: string): void }

export function emptyDraft(savedAt: string): Draft {
  return { version: DRAFT_VERSION, savedAt, date: null, counts: {}, costs: {}, seen: {} }
}

export function isEmptyDraft(draft: Draft): boolean {
  return Object.values(draft.counts).every((text) => text.trim() === "")
}

/** A stored draft, or null when it is not one: corrupt JSON, another version, wrong shapes. Keys not in `validKeys` are dropped. */
export function parseDraft(text: string | null, validKeys: ReadonlySet<string>): Draft | null {
  if (!text) return null
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return null
  }
  if (!raw || typeof raw !== "object") return null
  const d = raw as Record<string, unknown>
  if (d.version !== DRAFT_VERSION || typeof d.savedAt !== "string") return null
  const record = (value: unknown): Record<string, unknown> => (value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {})
  const counts: Record<string, string> = {}
  const costs: Record<string, number> = {}
  const seen: Record<string, number> = {}
  for (const [key, value] of Object.entries(record(d.counts))) {
    if (validKeys.has(key) && typeof value === "string" && value.trim() !== "") counts[key] = value
  }
  for (const [key, value] of Object.entries(record(d.costs))) {
    if (validKeys.has(key) && typeof value === "number" && Number.isSafeInteger(value) && value >= 0) costs[key] = value
  }
  for (const [key, value] of Object.entries(record(d.seen))) {
    if (validKeys.has(key) && typeof value === "number" && Number.isFinite(value)) seen[key] = value
  }
  const date = typeof d.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d.date) ? d.date : null
  return { version: DRAFT_VERSION, savedAt: d.savedAt, date, counts, costs, seen }
}

export function loadDraft(storage: StorageLike | null | undefined, validKeys: ReadonlySet<string>): Draft | null {
  try {
    return parseDraft(storage?.getItem(DRAFT_KEY) ?? null, validKeys)
  } catch {
    return null // storage denied or unavailable
  }
}

/** Saves the draft, or removes the stored one when nothing is counted. Returns false when storage refused. */
export function saveDraft(storage: StorageLike | null | undefined, draft: Draft): boolean {
  try {
    if (!storage) return false
    if (isEmptyDraft(draft)) storage.removeItem(DRAFT_KEY)
    else storage.setItem(DRAFT_KEY, JSON.stringify(draft))
    return true
  } catch {
    return false // quota or privacy mode: the screen keeps working without a draft
  }
}

export function clearDraft(storage: StorageLike | null | undefined): void {
  try {
    storage?.removeItem(DRAFT_KEY)
  } catch {
    /* nothing to clear */
  }
}

/** The keys whose system quantity differs from what it was when the count was typed. */
export function movedSince(seen: Record<string, number>, current: Record<string, number>): string[] {
  return Object.keys(seen).filter((key) => key in current && differenceNanos(current[key], seen[key]) !== ZERO)
}
