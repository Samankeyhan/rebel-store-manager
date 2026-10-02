/**
 * Display rules for products and materials. Nothing here is saved; the
 * numbers only re-state what the API returned.
 */

import type { Material, Product } from "@/lib/api"

/** db/constants.py VALID_CATEGORIES, in the backend's order. */
export const CATEGORY_CODES = [
  "ALBUM",
  "CASSETTE",
  "VINYL",
  "MIRROR",
  "POSTER",
  "STICKER",
  "TSHIRT",
  "OTHER",
  "فندک",
] as const

/** The design's unit list (05 §2), stored as Persian text. */
export const UNITS = ["عدد", "متر", "کیلوگرم", "رول", "لیتر", "نوبت"] as const

/** The API's default unit is the English "piece". */
export function unitLabel(unit: string): string {
  return unit === "piece" ? "عدد" : unit
}

export type CostState =
  | { kind: "known"; cost: number }
  /** Made-to-order with no finished stock: cost comes from the recipe at sale time. */
  | { kind: "fromRecipe" }
  /** Can't be sold until a cost exists (accounting §7 / §13). */
  | { kind: "missing" }

/**
 * A normal product with no cost can't be sold. A made-to-order product with
 * no cost is fine while it has no finished stock — each sale is costed from
 * its recipe — but its finished units can't be sold without a cost, which is
 * what the backend refuses too (same rule as record-sale's V3-MTO-stock).
 */
export function costState(p: Product): CostState {
  if (p.unit_cost != null) return { kind: "known", cost: p.unit_cost }
  if (p.made_to_order && p.current_stock === 0) return { kind: "fromRecipe" }
  return { kind: "missing" }
}

/** Inventory value for display (design 05 «ارزش موجودی»); services have none. */
export function inventoryValue(m: Material): number | null {
  if (m.type === "SERVICE" || m.current_stock == null) return null
  return Math.round(m.current_stock * m.unit_cost)
}

/** Folds Arabic ي/ك into Persian ی/ک and lowercases, for search. */
export function norm(s: string): string {
  return s.replace(/ي/g, "ی").replace(/ك/g, "ک").toLowerCase().trim()
}
