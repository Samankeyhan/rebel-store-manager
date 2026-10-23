import { unitLabel } from "@/components/products/figures"
import type { Material, Product } from "@/lib/api"
import { categoryPath } from "@/lib/category-path"
import { prefillCost } from "@/lib/product-cost"
import { itemKey, type ItemKind } from "@/lib/stocktake"

/** An item as the stocktake table sees it. */
export type StockRow = {
  key: string
  kind: ItemKind
  id: number
  name: string
  category: string
  unit: string
  /** The system stock as the API sent it. */
  systemQuantity: number
  isActive: boolean
  /** The item has no unit cost yet (a product that was never bought, made or costed). */
  costUnknown: boolean
  unitCost: number | null
  /** A product with no stored cost and a COMPLETE recipe: the recipe cost to prefill the required cost with (editable). */
  prefillCost: number | null
  /** A material whose cost is 0 ("not entered"): a gain counted without a cost keeps it at 0. */
  costZero: boolean
}

/** Products, and the materials that hold stock (services have none and are left out). */
export function buildRows(products: Product[], materials: Material[]): StockRow[] {
  const rows: StockRow[] = products.map((p) => ({
    key: itemKey("PRODUCT", p.id),
    kind: "PRODUCT",
    id: p.id,
    name: p.name,
    category: categoryPath(p),
    unit: unitLabel("piece"),
    systemQuantity: p.current_stock,
    isActive: p.is_active === 1,
    costUnknown: p.unit_cost == null,
    unitCost: p.unit_cost,
    prefillCost: prefillCost(p),
    costZero: false,
  }))
  for (const m of materials) {
    if (m.type !== "STOCK" || m.current_stock == null) continue
    rows.push({
      key: itemKey("MATERIAL", m.id),
      kind: "MATERIAL",
      id: m.id,
      name: m.name,
      category: categoryPath(m),
      unit: unitLabel(m.unit),
      systemQuantity: m.current_stock,
      isActive: m.is_active === 1,
      costUnknown: false,
      unitCost: m.unit_cost,
      prefillCost: null,
      costZero: m.unit_cost === 0,
    })
  }
  return rows.sort((a, b) => a.name.localeCompare(b.name, "fa"))
}
