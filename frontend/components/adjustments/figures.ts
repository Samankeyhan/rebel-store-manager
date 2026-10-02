/**
 * Pure logic for the adjustments screen. The rules mirror
 * db/adjustments.py::record_stock_adjustment (docs/accounting-rules.md §2, §8):
 * reason is WASTE or ADJUSTMENT; WASTE is always negative; products move in
 * whole units; no movement may take stock below zero; unit_cost only on a
 * positive ADJUSTMENT, blended into the weighted average.
 */

import { unitLabel } from "@/components/products/figures"
import type { Adjustment, AdjustmentItemType, AdjustmentReason, Material, Product } from "@/lib/api"
import { blendUnitCost, roundHalfEven } from "@/lib/costing"
import { A } from "./copy"

export type Kind = "waste" | "correction"
export type Dir = "plus" | "minus"
export type ItemKind = "product" | "material"

/** The item as the form sees it: stock, cost and unit, product or material. */
export type AdjItem = {
  kind: ItemKind
  id: number
  name: string
  stock: number
  cost: number | null
  unit: string
}

export function fromProduct(p: Product): AdjItem {
  return { kind: "product", id: p.id, name: p.name, stock: p.current_stock, cost: p.unit_cost, unit: "عدد" }
}

export function fromMaterial(m: Material): AdjItem {
  return { kind: "material", id: m.id, name: m.name, stock: m.current_stock ?? 0, cost: m.unit_cost, unit: unitLabel(m.unit) }
}

export const reasonOf = (kind: Kind): AdjustmentReason => (kind === "waste" ? "WASTE" : "ADJUSTMENT")
export const itemTypeOf = (kind: ItemKind): AdjustmentItemType => (kind === "product" ? "PRODUCT" : "MATERIAL")

/** +1 only for a correction upward; waste and a correction downward both decrement. */
export function signOf(kind: Kind, dir: Dir): 1 | -1 {
  return kind === "correction" && dir === "plus" ? 1 : -1
}

// Guards the stock comparison against binary fractions (0.1 + 0.2 …).
const EPS = 1e-9

/**
 * The design's single validation chain (§4), in its precedence, plus the
 * zero-stock wording. Returns the one message to show, or null.
 */
export function validate(item: AdjItem, q: number | null, sign: 1 | -1): string | null {
  if (q == null || !(q > 0)) return A.qtyRequired
  if (item.kind === "product" && Math.floor(q) !== q) return A.qtyFraction
  if (sign < 0 && q > item.stock + EPS) {
    return item.stock <= 0 ? A.qtyZeroStock(item.name) : A.qtyOver(item.stock, item.unit, item.name)
  }
  return null
}

export type Preview = {
  after: number
  /** Signed change in inventory value; null when the cost is unknown. */
  value: number | null
  /** The new weighted average, only for a correction + with a cost entered. */
  newCost: number | null
}

/**
 * Before → after for a valid adjustment. Waste and a correction − are valued
 * at the current cost (which they don't change). A correction + is valued at
 * the entered cost, else the current one; with a cost entered the new average
 * is db/costing.py blend_unit_cost(stock, cost, q, unit_cost × q).
 */
export function previewOf(item: AdjItem, q: number, sign: 1 | -1, unitCost: number | null): Preview {
  const after = item.stock + sign * q
  if (sign > 0) {
    const basis = unitCost ?? item.cost
    return {
      after,
      value: basis == null ? null : roundHalfEven(q * basis),
      newCost: unitCost == null ? null : blendUnitCost(item.stock, item.cost, q, unitCost * q),
    }
  }
  return { after, value: item.cost == null ? null : -roundHalfEven(q * item.cost), newCost: null }
}

/**
 * A history row's value: quantity_change × unit_cost_at_time, signed — per
 * row, the same product the P&L sums for waste (db/reports.py _waste_cost).
 */
export function rowValue(row: Adjustment): number | null {
  if (row.unit_cost_at_time == null) return null
  const v = roundHalfEven(Math.abs(row.quantity_change) * row.unit_cost_at_time)
  return row.quantity_change < 0 ? -v : v
}

export type RowKind = "waste" | "plus" | "minus"

export function rowKind(row: Adjustment): RowKind {
  if (row.reason === "WASTE") return "waste"
  return row.quantity_change > 0 ? "plus" : "minus"
}
