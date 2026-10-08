/**
 * The optional «حداقل موجودی» field of a material (a quantity in the
 * material's unit; db/materials.py owns the low-stock rule).
 *
 * Unlike `parseDecimal`, which drops every character it doesn't know (so
 * "-3" would read as 3), this refuses anything that isn't a plain
 * non-negative decimal: empty text means "no minimum" (null).
 */

import { toLatinDigits } from "./persian-numbers.ts"

export type MinStockParse = { ok: true; value: number | null } | { ok: false }

export function parseMinStock(text: string): MinStockParse {
  const s = toLatinDigits(text)
    .trim()
    .replace(/[٫/]/g, ".")
    .replace(/[٬,]/g, "")
  if (s === "") return { ok: true, value: null }
  if (!/^(\d+\.?\d*|\.\d+)$/.test(s)) return { ok: false }
  const n = Number(s)
  return Number.isFinite(n) ? { ok: true, value: n } : { ok: false }
}

/** The minimum as the API sends it, for comparing with the field's parse. */
export function minStockChanged(saved: number | null | undefined, parsed: MinStockParse): boolean {
  return parsed.ok && parsed.value !== (saved ?? null)
}
