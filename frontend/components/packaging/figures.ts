/**
 * Kit availability (formulas.md §5): how many kits current material stock
 * covers, and which material limits it. Display only — the kit's cost is the
 * API's kit_cost, never recomputed here.
 */

import type { KitDetail, Material } from "@/lib/api"

export type Availability =
  /** A kit with no materials never runs out. */
  | { kind: "unlimited" }
  | { kind: "count"; count: number; limiting: { name: string; stock: number; unit: string } }

/** Below this many kits the screen warns (design 08 §4; a literal, not a setting). */
export const LOW_KITS = 10

// Guards floor() against binary fractions: 1.5 / 0.5 must be 3, not 2.999….
const EPS = 1e-9

export function kitAvailability(kit: KitDetail, materials: Map<number, Material>): Availability {
  let best: Availability = { kind: "unlimited" }
  for (const item of kit.items) {
    const m = materials.get(item.material_id)
    const stock = m?.current_stock ?? 0
    const count = Math.floor(stock / item.quantity + EPS)
    // Strictly fewer: on a tie the earliest material in the kit is named.
    if (best.kind === "unlimited" || count < best.count) {
      best = { kind: "count", count: Math.max(0, count), limiting: { name: item.material_name, stock, unit: m?.unit ?? "" } }
    }
  }
  return best
}
