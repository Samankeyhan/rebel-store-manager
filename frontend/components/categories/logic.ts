/**
 * Pure helpers for «دسته‌ها». They mirror db/categories.py's rules so the
 * screen can explain a refusal before sending the request; the backend stays
 * the authority, and its refusal is mapped through refusalOf when the local
 * data was stale.
 */

import { ApiError, type CategoryTree } from "@/lib/api"

export type Count = { total: number; inactive: number }

/** Items per category id, inactive items included (they block deactivation too). */
export function itemCounts(items: { category_id: number | null; is_active: number }[]): Map<number, Count> {
  const counts = new Map<number, Count>()
  for (const it of items) {
    if (it.category_id == null) continue
    const c = counts.get(it.category_id) ?? { total: 0, inactive: 0 }
    c.total += 1
    if (it.is_active !== 1) c.inactive += 1
    counts.set(it.category_id, c)
  }
  return counts
}

export type CategoryNode = CategoryTree | CategoryTree["children"][number]

/** Why deactivate_category would refuse: items using it, and its active subcategories. */
export function blockers(
  node: CategoryNode,
  counts: Map<number, Count>
): { items: number; activeChildren: string[] } {
  const children = "children" in node ? node.children : []
  return {
    items: counts.get(node.id)?.total ?? 0,
    activeChildren: children.filter((c) => c.is_active === 1).map((c) => c.name),
  }
}

/** Whether a node exists in the tree, and its parent (null for a top-level one). */
export function findNode(
  tree: CategoryTree[],
  id: number
): { node: CategoryNode; parent: CategoryTree | null } | null {
  for (const t of tree) {
    if (t.id === id) return { node: t, parent: null }
    const child = t.children.find((c) => c.id === id)
    if (child) return { node: child, parent: t }
  }
  return null
}

/**
 * _check_sibling_name: an exact match on the trimmed name among the same
 * kind's top-level categories, or the same parent's children — inactive
 * siblings included. No other normalisation, like the backend.
 */
export function siblingClash(
  tree: CategoryTree[],
  parentId: number | null,
  name: string,
  excludeId: number | null = null
): "active" | "inactive" | null {
  const siblings: CategoryNode[] =
    parentId == null ? tree : (tree.find((t) => t.id === parentId)?.children ?? [])
  const hit = siblings.find((s) => s.name === name && s.id !== excludeId)
  return hit ? (hit.is_active === 1 ? "active" : "inactive") : null
}

export type Refusal =
  | { kind: "inUse"; count: number | null }
  | { kind: "hasChildren" }
  | { kind: "parentInactive" }
  | { kind: "duplicate" }
  | { kind: "field"; field: string; message: string }
  | { kind: "other"; message: string; code: string }

/**
 * The backend's category refusals. ConflictError carries no details, so the
 * 409s are told apart by their (English) message; the count of items using a
 * category exists only inside that message.
 */
export function refusalOf(e: unknown): Refusal {
  if (e instanceof ApiError && e.status === 409) {
    const used = /is used by (\d+)/.exec(e.message)
    if (used || /is used by/.test(e.message)) return { kind: "inUse", count: used ? Number(used[1]) : null }
    if (/active subcategories/.test(e.message)) return { kind: "hasChildren" }
    if (/^Parent category .* is inactive/.test(e.message)) return { kind: "parentInactive" }
    if (/already exists at this level/.test(e.message)) return { kind: "duplicate" }
  }
  if (e instanceof ApiError && e.status === 422 && e.field) return { kind: "field", field: e.field, message: e.message }
  return errorInfo(e)
}

export function errorInfo(e: unknown): { kind: "other"; message: string; code: string } {
  return e instanceof ApiError
    ? { kind: "other", message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `CATEGORIES_${e.status}` }
    : { kind: "other", message: String(e), code: "UNKNOWN" }
}
