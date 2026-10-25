/**
 * Purchase-invoice form helpers with no React and no API calls, so `npm test` can run them: one supplier invoice with
 * several lines (STOCK materials, services, products), as db/purchases.py `record_purchase` takes it.
 *
 * Every saved figure (the invoice total, each line's unit cost, the payment status) comes from the API. The checks
 * here only mirror the backend's refusals so the form can say what is wrong before sending; the backend decides.
 * Amounts are integer Rial. The invoice total shown while typing is the exact sum of the line totals.
 */

export type ItemKind = "MATERIAL" | "PRODUCT"
/** What a line's item is: a stock material, a service (no stock), a finished product. */
export type ItemType = "STOCK" | "SERVICE" | "PRODUCT"
/** The purchases list's type filter (`?type=`), and the API's `item_type` for it. */
export type TypeFilter = "all" | "material" | "service" | "product"

export const TYPE_FILTERS: readonly TypeFilter[] = ["all", "material", "service", "product"]

export function parseTypeFilter(value: string | null): TypeFilter {
  return TYPE_FILTERS.includes(value as TypeFilter) ? (value as TypeFilter) : "all"
}

/** The API's `item_type` query value for a filter (MATERIAL = STOCK materials); null = no filter. */
export function apiItemType(filter: TypeFilter): "MATERIAL" | "SERVICE" | "PRODUCT" | null {
  return filter === "all" ? null : (filter.toUpperCase() as "MATERIAL" | "SERVICE" | "PRODUCT")
}

/** The picker lists materials and products together: a material keeps its id, a product is -id. */
export function pickId(kind: ItemKind, id: number): number {
  return kind === "MATERIAL" ? id : -id
}

export function unpick(pick: number): { kind: ItemKind; id: number } {
  return pick < 0 ? { kind: "PRODUCT", id: -pick } : { kind: "MATERIAL", id: pick }
}

export type LineProblem = "item" | "duplicate" | "qty" | "qty_whole" | "total" | "service_total"

/** One line as typed: `qty` and `total` are null while their text gives no exact number (blocks submit). */
export type LineInput = { pick: number | null; itemType: ItemType | null; qty: number | null; total: number | null }

/**
 * What each line refuses, as record_purchase does: an item; not the same item as an earlier line (PURCHASE_DUPLICATE_ITEM);
 * a quantity above 0, whole for a product; an exact total; a service total above 0 (SERVICE_PURCHASE_NEEDS_TOTAL).
 * One entry per line, null = fine; the first problem of a line is the one given.
 */
export function lineProblems(lines: readonly LineInput[]): (LineProblem | null)[] {
  const seen = new Set<number>()
  return lines.map((l) => {
    if (l.pick == null || l.itemType == null) return "item"
    if (seen.has(l.pick)) return "duplicate"
    seen.add(l.pick)
    if (l.qty === null || !(l.qty > 0)) return "qty"
    if (l.itemType === "PRODUCT" && !Number.isInteger(l.qty)) return "qty_whole"
    if (l.total === null) return "total"
    if (l.itemType === "SERVICE" && l.total === 0) return "service_total"
    return null
  })
}

/** The invoice total: the exact sum of the line totals, null when a line has no exact total or the sum is not a safe integer. */
export function invoiceTotal(totals: readonly (number | null)[]): number | null {
  let sum = 0
  for (const t of totals) {
    if (t === null || !Number.isSafeInteger(t)) return null
    sum += t
    if (!Number.isSafeInteger(sum)) return null
  }
  return sum
}

export type LineBody = { kind: ItemKind; item_id: number; quantity_bought: number; total_paid: number }

/** The body's `lines` for lines that passed `lineProblems`. */
export function linesBody(lines: readonly { pick: number; qty: number; total: number }[]): LineBody[] {
  return lines.map((l) => {
    const { kind, id } = unpick(l.pick)
    return { kind, item_id: id, quantity_bought: l.qty, total_paid: l.total }
  })
}

/** A backend refusal's `field` (`lines.2.total_paid`) as the line index and the field; null for any other field. */
export function lineField(field: string | null | undefined): { index: number; field: string } | null {
  const m = /^lines\.(\d+)\.(.+)$/.exec(field ?? "")
  return m ? { index: Number(m[1]), field: m[2] } : null
}

/** «کاغذ» for one item, «کاغذ و ۲ قلم دیگر» for more (`more` writes the second part). */
export function itemsSummary(names: readonly string[], more: (others: number) => string): string {
  if (names.length === 0) return ""
  return names.length === 1 ? names[0] : `${names[0]} ${more(names.length - 1)}`
}

/** The distinct item types of a purchase's lines, in the order they first appear. */
export function lineTypes(lines: readonly { item_type: ItemType }[]): ItemType[] {
  return [...new Set(lines.map((l) => l.item_type))]
}
