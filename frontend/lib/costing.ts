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

/**
 * quantity × unit cost in whole Rial, exact and rounded half-even once, like
 * db/costing.py (a REAL quantity counts as the decimal it was entered as:
 * 0.005 × 120,000,000 = 600,000, never 599,999.99…). For one line's cost;
 * a recipe or batch total sums its lines before rounding (recipeSums,
 * batchPreview).
 */
export function lineCost(quantity: number, unitCost: number): number {
  const s = String(Math.abs(quantity))
  const m = /^(\d+)(?:\.(\d+))?(?:e([+-]\d+))?$/.exec(s)
  if (!m || !Number.isInteger(unitCost)) return roundHalfEven(quantity * unitCost)
  const fraction = m[2] ?? ""
  // value = digits × 10^-scale; a negative scale (1e21) multiplies instead.
  const scale = fraction.length - Number(m[3] ?? 0)
  const one = BigInt(1)
  const two = BigInt(2)
  const power = (k: number) => BigInt("1" + "0".repeat(k)) // a power of ten, without ×10
  let numerator = BigInt(m[1] + fraction) * BigInt(unitCost)
  let denominator = one
  if (scale > 0) denominator = power(scale)
  else numerator *= power(-scale)
  let whole = numerator / denominator
  const twice = (numerator % denominator) * two
  if (twice > denominator || (twice === denominator && whole % two === one)) whole += one
  return Number(whole)
}

/** db/costing.py blend_unit_cost: the weighted average when stock comes in. */
export function blendUnitCost(
  stockBefore: number | null,
  costBefore: number | null,
  qtyIn: number,
  valueIn: number,
  /** Materials only (accounting rules §2): a cost of 0 means "not entered", like null. */
  zeroIsUnknown = false
): number {
  if (zeroIsUnknown && costBefore === 0) costBefore = null
  if (costBefore == null || stockBefore == null || stockBefore <= 0) {
    return roundHalfEven(valueIn / qtyIn)
  }
  return roundHalfEven((stockBefore * costBefore + valueIn) / (stockBefore + qtyIn))
}

/** A number as the decimal it was entered as: digits × 10^-scale (scale >= 0), like db/costing.py exact_quantity. */
function decimalOf(x: number): { digits: bigint; scale: number } {
  const m = /^(\d+)(?:\.(\d+))?(?:e([+-]\d+))?$/.exec(String(Math.abs(x)))
  if (!m) throw new Error(`not a plain number: ${x}`)
  const fraction = m[2] ?? ""
  const scale = fraction.length - Number(m[3] ?? 0)
  const digits = BigInt(m[1] + fraction)
  if (scale >= 0) return { digits, scale }
  return { digits: digits * BigInt("1" + "0".repeat(-scale)), scale: 0 }
}

/**
 * db/costing.py recipe_batch_total: Σ needed × unit cost, exact, rounded half-even once. A PER_UNIT line needs
 * quantity_needed × batchQty, a PER_BATCH line quantity_needed once — so a sale of n units counts PER_BATCH lines
 * once, never n times. Preview only; the saved cost comes from the API.
 */
export function recipeBatchTotal(
  lines: { quantity_needed: number; cost_basis: string; material_unit_cost: number }[],
  batchQty: number
): number {
  const batch = decimalOf(batchQty)
  const terms = lines.map((line) => {
    const needed = decimalOf(line.quantity_needed)
    let digits = needed.digits * BigInt(line.material_unit_cost)
    let scale = needed.scale
    if (line.cost_basis !== "PER_BATCH") {
      digits *= batch.digits
      scale += batch.scale
    }
    return { digits, scale }
  })
  const scale = terms.reduce((s, t) => Math.max(s, t.scale), 0)
  const one = BigInt(1)
  const two = BigInt(2)
  const denominator = BigInt("1" + "0".repeat(scale))
  const numerator = terms.reduce((sum, t) => sum + t.digits * BigInt("1" + "0".repeat(scale - t.scale)), BigInt(0))
  let whole = numerator / denominator
  const twice = (numerator % denominator) * two
  if (twice > denominator || (twice === denominator && whole % two === one)) whole += one
  return Number(whole)
}

/** The recipe's materials whose cost is 0 or missing ("not entered"): the recipe cost is then incomplete. */
export function recipeMissing(
  lines: { material_id: number; material_name: string; material_unit_cost: number | null }[]
): { id: number; name: string }[] {
  return lines.filter((l) => !l.material_unit_cost).map((l) => ({ id: l.material_id, name: l.material_name }))
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

export type ChainLine = { key: string; items: RecipeLine[] | null; qty: number }
export type ChainedPreview = BatchPreview & {
  /** Short only because lines above it use the same materials first. */
  shortByEarlier: boolean
}

/**
 * Previews for several separate runs submitted one after another (top to
 * bottom). They share material stock: each line sees what is left after the
 * lines above it. A line predicted to fail (short) consumes nothing — the
 * server refuses it whole — so it never takes stock from the lines after it.
 */
export function chainedPreviews(
  lines: ChainLine[],
  stockOf: (materialId: number) => number | null
): Map<string, ChainedPreview> {
  const used = new Map<number, number>()
  const remaining = (id: number) => {
    const s = stockOf(id)
    return s == null ? null : s - (used.get(id) ?? 0)
  }
  const out = new Map<string, ChainedPreview>()
  for (const line of lines) {
    if (!line.items || line.qty < 1) continue
    const preview = batchPreview(line.items, line.qty, remaining)
    const short = preview.short.length > 0
    const shortByEarlier = short && batchPreview(line.items, line.qty, stockOf).short.length === 0
    if (!short) {
      for (const l of preview.lines) if (l.stock != null) used.set(l.material_id, (used.get(l.material_id) ?? 0) + l.need)
    }
    out.set(line.key, { ...preview, shortByEarlier })
  }
  return out
}
