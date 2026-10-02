/**
 * Client-side cost previews. Each function mirrors one backend formula line
 * for line (docs/accounting-rules.md; formulas.md §3–4), so a preview equals
 * what the server will store unless costs or stock change in between. They
 * are previews only: the saved figures always come from the API response.
 */

/**
 * Python's round(): to the nearest integer, ties to even (banker's
 * rounding). JS Math.round sends .5 up, which would differ on exact ties.
 */
export function roundHalfEven(x: number): number {
  const floor = Math.floor(x)
  const diff = x - floor
  if (diff > 0.5) return floor + 1
  if (diff < 0.5) return floor
  return floor % 2 === 0 ? floor : floor + 1
}

/** db/costing.py blend_unit_cost: the weighted average when stock comes in. */
export function blendUnitCost(
  stockBefore: number | null,
  costBefore: number | null,
  qtyIn: number,
  valueIn: number
): number {
  if (costBefore == null || stockBefore == null || stockBefore <= 0) {
    return roundHalfEven(valueIn / qtyIn)
  }
  return roundHalfEven((stockBefore * costBefore + valueIn) / (stockBefore + qtyIn))
}

/** db/purchases.py _compute_unit_cost: this purchase's own unit cost. */
export function purchaseUnitCost(totalPaid: number, quantity: number): number {
  return roundHalfEven(totalPaid / quantity)
}

export type RecipeLine = {
  material_id: number
  material_name: string
  material_type: string
  material_unit: string
  quantity_needed: number
  cost_basis: string
  material_unit_cost: number
}

export type BatchLine = RecipeLine & {
  perBatch: boolean
  /** Quantity consumed by this batch. */
  need: number
  /** need × unit cost, unrounded (the backend rounds only the sum). */
  cost: number
  /** STOCK lines only; null for services (never checked, never short). */
  stock: number | null
  after: number | null
  shortBy: number | null
}

export type BatchPreview = {
  lines: BatchLine[]
  /** round(Σ line cost) — db/production.py batch_total_cost. */
  batchTotal: number
  /** round(batchTotal ÷ n) — the batch's unit cost. */
  unitCost: number
  short: BatchLine[]
  /** Largest n the current stock allows; null when nothing limits it. */
  maxBuildable: number | null
}

// Guards floor() against binary fractions: 1.5 / 0.5 must be 3, not 2.999….
const EPS = 1e-9

/**
 * db/production.py run_production_batch, before it writes anything: what a
 * batch of `n` consumes and costs, and which STOCK materials run short.
 * `stockOf` gives a material's current stock (null for a service).
 */
export function batchPreview(
  items: RecipeLine[],
  n: number,
  stockOf: (materialId: number) => number | null
): BatchPreview {
  let sum = 0
  let maxBuildable: number | null = null
  const limit = (m: number) => {
    maxBuildable = maxBuildable == null ? m : Math.min(maxBuildable, m)
  }
  const lines = items.map((item): BatchLine => {
    const perBatch = item.cost_basis === "PER_BATCH"
    const need = perBatch ? item.quantity_needed : item.quantity_needed * n
    const cost = need * item.material_unit_cost
    sum += cost
    const stock = item.material_type === "STOCK" ? (stockOf(item.material_id) ?? 0) : null
    let after: number | null = null
    let shortBy: number | null = null
    if (stock != null) {
      // need > stock is short; using exactly the last unit is allowed.
      if (need > stock) shortBy = need - stock
      else after = stock - need
      if (perBatch) {
        if (stock < item.quantity_needed) limit(0)
      } else {
        limit(Math.floor(stock / item.quantity_needed + EPS))
      }
    }
    return { ...item, perBatch, need, cost, stock, after, shortBy }
  })
  const batchTotal = roundHalfEven(sum)
  return {
    lines,
    batchTotal,
    unitCost: n > 0 ? roundHalfEven(batchTotal / n) : 0,
    short: lines.filter((l) => l.shortBy != null),
    maxBuildable,
  }
}

/** Recipe summary (design 06 recipe tiles): per-unit and once-per-batch sums. */
export function recipeSums(items: RecipeLine[]): { perUnit: number; perBatch: number } {
  let perUnit = 0
  let perBatch = 0
  for (const i of items) {
    if (i.cost_basis === "PER_BATCH") perBatch += i.quantity_needed * i.material_unit_cost
    else perUnit += i.quantity_needed * i.material_unit_cost
  }
  return { perUnit: roundHalfEven(perUnit), perBatch: roundHalfEven(perBatch) }
}
