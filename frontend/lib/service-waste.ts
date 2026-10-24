/**
 * Waste of a service (accounting rules section 8): a SERVICE material has a cost but no stock, so its waste is a
 * count of units at a price per unit, and no stock change. Pure, so `npm test` runs it. The backend decides: it
 * refuses a material at cost 0 (MATERIAL_NO_UNIT_COST) and stores the price per unit; the amount shown here is a
 * preview of units × price (`lineCost`, one half-even rounding), the same product the P&L sums.
 */

import { lineCost } from "./costing.ts"

/** The price per unit to prefill: the material's current cost, or null when it has none (0 = "not entered"). */
export function servicePrice(material: { unit_cost: number | null }): number | null {
  return material.unit_cost != null && material.unit_cost >= 1 ? material.unit_cost : null
}

/** The amount of a service waste: units × price per unit, exact, half-even to the Rial. */
export function serviceWasteAmount(quantity: number, price: number): number {
  return lineCost(quantity, price)
}

/**
 * The price to send: null when it is the material's own current cost (the server then uses its cost), else the
 * typed price. A price that is not a whole Rial of at least 1 is never sent (the form blocks it).
 */
export function priceToSend(typed: number, material: { unit_cost: number | null }): number | null {
  return typed === servicePrice(material) ? null : typed
}

/** The link to a material's drawer, where «ثبت بها» is (/products?tab=materials&material=<id>, as the dashboard's rows). */
export function setCostHref(materialId: number): string {
  return `/products?tab=materials&material=${materialId}`
}
