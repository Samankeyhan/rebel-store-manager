/**
 * «ثبت بها» (accounting rules section 2): when the screens offer it and what its confirmation shows. Nothing here is
 * saved. Pure, so `npm test` runs it. The backend decides: the cost is accepted only while a material's is 0 and a
 * product's is NULL; the screens only offer it for stock that is already there (or a recipe a material blocks).
 */

import { lineCost } from "./costing.ts"

/** A material still at cost 0 / none ("not entered"); a SERVICE too, since it can make a recipe «ناقص». */
export function canSetMaterialCost(m: { unit_cost: number | null }): boolean {
  return !m.unit_cost
}

/** A product with no cost (NULL; 0 is a real cost) that holds stock: the units that cannot be sold yet. */
export function canSetProductCost(p: { unit_cost: number | null; current_stock: number }): boolean {
  return p.unit_cost == null && p.current_stock > 0
}

/**
 * The stock value the confirmation shows: stock × price (one rounding, half-even, `lineCost`). A SERVICE material has
 * no stock, so no value; nor does an item whose stock is unknown or 0 (nothing to value).
 */
export function setCostStockValue(item: { type?: string; current_stock: number | null }, cost: number): number | null {
  if (item.type === "SERVICE" || item.current_stock == null || item.current_stock <= 0) return null
  return lineCost(item.current_stock, cost)
}
