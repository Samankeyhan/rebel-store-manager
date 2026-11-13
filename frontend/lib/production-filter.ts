/**
 * The search box and category filter of the production screen's recipe and history tabs. Pure helpers (no React,
 * no API calls) so `npm test` can run them. Products already carry their category and its parent
 * (`category_id`, `category_name`, `parent_category_id`, `parent_category_name`), so the options come from the
 * products on screen and nothing is fetched. A production batch row has no category: it is joined to its product
 * by `product_id` (a backend gap, reported). Names are matched with `searchKey` (the port of the database's
 * name key), so Persian and English, any case, any spelling variant.
 */

import { categoryPath } from "./category-path.ts"
import { nameMatches } from "./search-key.ts"

/** The product fields the filter reads (Product from lib/api.ts fits). */
export type FilterProduct = {
  id: number
  name: string
  category_id: number
  category_name: string
  parent_category_id: number | null
  parent_category_name: string | null
}

export type ProductFilter = {
  /** The typed search, as typed. Empty = every name. */
  q: string
  /** A category id (a top-level one includes its subcategories), or null = every category. */
  categoryId: number | null
}

export const NO_FILTER: ProductFilter = { q: "", categoryId: null }

/** Whether anything is being filtered (what «پاک کردن فیلترها» would undo). */
export function isFiltering(filter: ProductFilter): boolean {
  return filter.q.trim() !== "" || filter.categoryId != null
}

/** In the category itself or, for a top-level category, in one of its subcategories. */
export function inCategory(product: FilterProduct, categoryId: number): boolean {
  return product.category_id === categoryId || product.parent_category_id === categoryId
}

/** One choice of the category dropdown: «والد» (all of it) or «والد › فرزند». */
export type CategoryOption = { id: number; label: string }

/** The categories the given products are in, each top-level one that has a product in it or in a subcategory, in Persian order. */
export function categoryOptions(products: readonly FilterProduct[]): CategoryOption[] {
  const byId = new Map<number, string>()
  for (const p of products) {
    byId.set(p.category_id, categoryPath(p))
    if (p.parent_category_id != null && p.parent_category_name) byId.set(p.parent_category_id, p.parent_category_name)
  }
  return [...byId].map(([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label, "fa"))
}

export function productMatches(product: FilterProduct, filter: ProductFilter): boolean {
  if (filter.categoryId != null && !inCategory(product, filter.categoryId)) return false
  return nameMatches(product.name, filter.q)
}

export function filterProducts<P extends FilterProduct>(products: readonly P[], filter: ProductFilter): P[] {
  return products.filter((p) => productMatches(p, filter))
}

/**
 * The batches whose product matches. A batch is matched through its product (category and name as the products
 * list has them now); a batch whose product the list doesn't hold is found by its own `product_name` and never
 * by category.
 */
export function filterBatches<B extends { product_id: number; product_name: string }>(
  batches: readonly B[],
  products: ReadonlyMap<number, FilterProduct>,
  filter: ProductFilter
): B[] {
  return batches.filter((b) => {
    const product = products.get(b.product_id)
    if (product) return productMatches(product, filter)
    return filter.categoryId == null && nameMatches(b.product_name, filter.q)
  })
}
