/**
 * Category display and tree helpers. Products and materials carry their
 * category's name and its parent's (for a subcategory) from the API, so no
 * lookup is needed to show one.
 */

import type { CategoryTree } from "@/lib/api"

type Categorised = {
  category_name: string | null
  parent_category_name: string | null
}

/** «فندک › فندک بزرگ» for a subcategory, «وینیل» for a top-level, "" for none. */
export function categoryPath(item: Categorised): string {
  if (!item.category_name) return ""
  return item.parent_category_name ? `${item.parent_category_name} › ${item.category_name}` : item.category_name
}

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name, "fa")

/**
 * The tree sorted in Persian order (the API orders by raw bytes, which puts
 * پ چ ژ گ out of place), optionally without inactive nodes.
 */
export function sortTree(tree: CategoryTree[], activeOnly = false): CategoryTree[] {
  return tree
    .filter((t) => !activeOnly || t.is_active === 1)
    .map((t) => ({
      ...t,
      children: t.children.filter((c) => !activeOnly || c.is_active === 1).sort(byName),
    }))
    .sort(byName)
}

/** The category plus, for a top-level one, all its subcategories. */
export function descendantIds(tree: CategoryTree[], id: number): Set<number> {
  const ids = new Set([id])
  for (const c of tree.find((t) => t.id === id)?.children ?? []) ids.add(c.id)
  return ids
}

/** Whether any node in the tree has this id. */
export function treeHas(tree: CategoryTree[], id: number): boolean {
  return tree.some((t) => t.id === id || t.children.some((c) => c.id === id))
}
