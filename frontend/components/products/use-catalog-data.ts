"use client"

import * as React from "react"
import { listMaterials, listProducts, type Material, type Product } from "@/lib/api"

type State =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; products: Product[]; materials: Material[] }

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name, "fa")

/**
 * Products and materials for both tabs, loaded once (including inactive
 * rows — /catalog only returns active ones). Every write endpoint returns the
 * updated row, which replaces or inserts it here, so no full refetch.
 */
export function useCatalogData() {
  const [state, setState] = React.useState<State>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([listProducts(), listMaterials()]).then(
      ([products, materials]) =>
        !cancelled && setState({ status: "ready", products, materials }),
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

  return { state, reload, upsertProduct, upsertMaterial }
}
