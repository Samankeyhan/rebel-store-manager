/**
 * Which product cost the screens show (accounting rules §13). Nothing here is saved: `unit_cost` is the stored weighted
 * average, `recipe_cost*` is the display-only estimate from the recipe at today's material costs.
 * Pure, no imports: `npm test` runs it.
 */

export type CostInput = {
  unit_cost: number | null
  made_to_order: number
  current_stock: number
  recipe_cost: number | null
  recipe_cost_status: "NONE" | "INCOMPLETE" | "COMPLETE"
  recipe_cost_missing: { id: number; name: string }[]
}

export type Estimate = { kind: "complete"; cost: number } | { kind: "incomplete"; missing: string[] }

export type CostState =
  /** A stored weighted average exists. */
  | { kind: "known"; cost: number; estimate: Estimate | null }
  /** Made-to-order with no finished stock: each sale is costed from the recipe at sale time. */
  | { kind: "fromRecipe"; estimate: Estimate | null }
  /** Can't be sold until a cost exists (accounting §7 / §13). */
  | { kind: "missing"; estimate: Estimate | null }

/** One line of cost text. «میانگین موجودی» = avg, «برآورد از دستور تولید» = estimate, «ناقص: …» = incomplete, «نامشخص» = unknown. */
export type CostLine =
  | { tag: "avg"; cost: number }
  | { tag: "estimate"; cost: number }
  | { tag: "incomplete"; missing: string[] }
  | { tag: "unknown" }

export function estimateOf(p: CostInput): Estimate | null {
  if (p.recipe_cost_status === "COMPLETE" && p.recipe_cost != null) return { kind: "complete", cost: p.recipe_cost }
  if (p.recipe_cost_status === "INCOMPLETE") return { kind: "incomplete", missing: p.recipe_cost_missing.map((m) => m.name) }
  return null
}

/**
 * A normal product with no cost can't be sold. A made-to-order product with no cost is fine while it has no finished
 * stock — each sale is costed from its recipe — but its finished units can't be sold without a cost, which is what the
 * backend refuses too. The estimate never changes that: it is shown, never stored.
 */
export function costState(p: CostInput): CostState {
  const estimate = estimateOf(p)
  if (p.unit_cost != null) return { kind: "known", cost: p.unit_cost, estimate }
  if (p.made_to_order && p.current_stock === 0) return { kind: "fromRecipe", estimate }
  return { kind: "missing", estimate }
}

/**
 * The cost text lines for a product: the stored average when there is one, otherwise the recipe estimate, an
 * «ناقص» note when a recipe material has no cost, or «نامشخص». A made-to-order product with finished stock and a
 * stored average shows both.
 */
export function costLines(p: CostInput): CostLine[] {
  const state = costState(p)
  const estimateLine = (e: Estimate | null): CostLine =>
    e == null ? { tag: "unknown" } : e.kind === "complete" ? { tag: "estimate", cost: e.cost } : { tag: "incomplete", missing: e.missing }
  if (state.kind !== "known") return [estimateLine(state.estimate)]
  const lines: CostLine[] = [{ tag: "avg", cost: state.cost }]
  if (p.made_to_order && p.current_stock > 0 && state.estimate != null) lines.push(estimateLine(state.estimate))
  return lines
}

/** Record-sale / stocktake: the recipe cost to prefill a required cost with — only a COMPLETE recipe offers one. */
export function prefillCost(p: Pick<CostInput, "unit_cost" | "recipe_cost" | "recipe_cost_status">): number | null {
  if (p.unit_cost != null) return null
  return p.recipe_cost_status === "COMPLETE" ? p.recipe_cost : null
}

/**
 * «متریال‌های بدون بها»: every ACTIVE material with cost 0 ("not entered") that holds stock, or that makes some
 * product's recipe «ناقص» (`recipe_cost_missing` of the product rows already loaded).
 */
export function materialsWithoutCost<
  M extends { id: number; type: string; is_active: number; unit_cost: number | null; current_stock: number | null },
>(materials: M[], products: { recipe_cost_missing: { id: number }[] }[]): M[] {
  const inRecipes = new Set(products.flatMap((p) => p.recipe_cost_missing.map((m) => m.id)))
  return materials.filter(
    (m) =>
      m.is_active === 1 &&
      !m.unit_cost &&
      ((m.type === "STOCK" && (m.current_stock ?? 0) > 0) || inRecipes.has(m.id))
  )
}
