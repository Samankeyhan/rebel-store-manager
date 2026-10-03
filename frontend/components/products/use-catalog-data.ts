"use client"

import * as React from "react"
import {
  listCategoryTree,
  listMaterials,
  listProducts,
  type CategoryKind,
  type CategoryTree,
  type Material,
  type Product,
} from "@/lib/api"
import { sortTree } from "@/lib/category-path"

type State =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready"
      products: Product[]
      materials: Material[]
      /** Both category trees, inactive nodes included (filters still need them). */
      productTree: CategoryTree[]
      materialTree: CategoryTree[]
    }

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name, "fa")

/**
 * Products, materials and both category trees, loaded once (including inactive
 * rows — /catalog only returns active ones). Every write endpoint returns the
 * updated row, which replaces or inserts it here, so no full refetch.
 */
export function useCatalogData() {
  const [state, setState] = React.useState<State>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([listProducts(), listMaterials(), listCategoryTree("PRODUCT"), listCategoryTree("MATERIAL")]).then(
      ([products, materials, productTree, materialTree]) =>
        !cancelled &&
        setState({
          status: "ready",
          products,
          materials,
          productTree: sortTree(productTree),
          materialTree: sortTree(materialTree),
        }),
      () => !cancelled && setState({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const reload = React.useCallback(() => {
    setState({ status: "loading" })
    setAttempt((a) => a + 1)
  }, [])

  const upsertProduct = React.useCallback((p: Product) => {
    setState((s) =>
      s.status !== "ready"
        ? s
        : {
            ...s,
            products: s.products.some((x) => x.id === p.id)
              ? s.products.map((x) => (x.id === p.id ? p : x))
              : [...s.products, p].sort(byName),
          }
    )
  }, [])

  const upsertMaterial = React.useCallback((m: Material) => {
    setState((s) =>
      s.status !== "ready"
        ? s
        : {
            ...s,
            materials: s.materials.some((x) => x.id === m.id)
              ? s.materials.map((x) => (x.id === m.id ? m : x))
              : [...s.materials, m].sort(byName),
          }
    )
  }, [])

  /**
   * Refetch one category tree after a category write. A rename changes the
   * children's parent_name too, so this is simpler than patching nodes.
   * Products/materials carry their category's name, so a rename also needs
   * those lists; `withItems` refetches them in the same round.
   */
  const reloadTree = React.useCallback(async (kind: CategoryKind, withItems = false) => {
    const [tree, items] = await Promise.all([
      listCategoryTree(kind),
      withItems ? (kind === "PRODUCT" ? listProducts() : listMaterials()) : Promise.resolve(null),
    ])
    setState((s) => {
      if (s.status !== "ready") return s
      const next = { ...s }
      if (kind === "PRODUCT") {
        next.productTree = sortTree(tree)
        if (items) next.products = items as Product[]
      } else {
        next.materialTree = sortTree(tree)
        if (items) next.materials = items as Material[]
      }
      return next
    })
  }, [])

  return { state, reload, reloadTree, upsertProduct, upsertMaterial }
}
