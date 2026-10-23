/**
 * Display rules for products and materials. Nothing here is saved; the
 * numbers only re-state what the API returned.
 */

import type { Material, Product } from "@/lib/api"
import { lineCost } from "@/lib/costing"

/**
 * The unit picker's list, stored as Persian text (the API takes any string).
 * Units already saved on a material that are not here stay as they are.
 */
export const UNITS = [
  "میلی‌لیتر",
  "لیتر",
  "گرم",
  "کیلوگرم",
  "سانتی‌متر",
  "متر",
  "عدد",
  "برگ",
  "رول",
  "بسته",
  "نوبت",
] as const

/** What a new material starts with (the list's first entry is not the default). */
export const DEFAULT_UNIT = "عدد"

/** The API's default unit is the English "piece". */
export function unitLabel(unit: string): string {
  return unit === "piece" ? "عدد" : unit
}

// Which cost a product shows (stored average, recipe estimate, «ناقص», «نامشخص») lives in lib/product-cost.ts, where
// `npm test` covers it. Same rule as record-sale's V3-MTO-stock for what can't be sold.
export { costLines, costState } from "@/lib/product-cost"
export type { CostLine, CostState } from "@/lib/product-cost"

/** Inventory value for display (design 05 «ارزش موجودی»); services have none. */
export function inventoryValue(m: Material): number | null {
  if (m.type === "SERVICE" || m.current_stock == null) return null
  return lineCost(m.current_stock, m.unit_cost)
}

/** Folds Arabic ي/ك into Persian ی/ک and lowercases, for search. */
export function norm(s: string): string {
  return s.replace(/ي/g, "ی").replace(/ك/g, "ک").toLowerCase().trim()
}
