"use client"

import * as React from "react"
import {
  ApiError,
  getProduct,
  getRecipe,
  getSettings,
  listMaterials,
  listProducts,
  listProduction,
  type Material,
  type Product,
  type ProductionBatchListItem,
  type Recipe,
} from "@/lib/api"

export type RecipeEntry =
  | { status: "loading" }
  | { status: "ok"; recipe: Recipe }
  /** 404 or no lines: production is refused (422) until a recipe exists. */
  | { status: "missing" }
  /** Any other failure: not a block — POST /production decides. */
  | { status: "failed" }

type Base =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; products: Product[]; materials: Material[]; batches: ProductionBatchListItem[] }

const DEFAULT_TZ = "Asia/Tehran"
const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name, "fa")

/**
 * Everything the three production tabs share: products (all, for names;
 * pickers use the active ones), materials (all — a recipe may reference an
 * inactive one), the batch history, and a recipe index. No endpoint says which
 * products have a recipe, so each active product's recipe is fetched once, in
 * parallel; every recipe write returns the whole recipe, which replaces the
 * entry (setRecipe).
 */
export function useProductionData() {
  const [base, setBase] = React.useState<Base>({ status: "loading" })
  const [recipes, setRecipes] = React.useState<Record<number, RecipeEntry>>({})
  const [timeZone, setTimeZone] = React.useState(DEFAULT_TZ)
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([listProducts(), listMaterials(), listProduction()]).then(
      ([products, materials, batches]) => {
        if (cancelled) return
        setBase({ status: "ready", products: products.sort(byName), materials, batches })
        const active = products.filter((p) => p.is_active === 1)
        setRecipes(Object.fromEntries(active.map((p) => [p.id, { status: "loading" } as RecipeEntry])))
        for (const p of active) {
          getRecipe(p.id).then(
            (recipe) =>
              !cancelled &&
              setRecipes((r) => ({
                ...r,
                [p.id]: recipe.items.length === 0 ? { status: "missing" } : { status: "ok", recipe },
              })),
            (error: unknown) =>
              !cancelled &&
              setRecipes((r) => ({
                ...r,
                [p.id]: { status: error instanceof ApiError && error.status === 404 ? "missing" : "failed" },
              }))
          )
        }
      },
      () => !cancelled && setBase({ status: "error" })
    )
    getSettings().then(
      (s) => !cancelled && setTimeZone(s.timezone || DEFAULT_TZ),
      () => {}
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const reload = React.useCallback(() => {
    setBase({ status: "loading" })
    setAttempt((a) => a + 1)
  }, [])

  const setRecipe = React.useCallback((productId: number, recipe: Recipe) => {
    setRecipes((r) => ({
      ...r,
      [productId]: recipe.items.length === 0 ? { status: "missing" } : { status: "ok", recipe },
    }))
  }, [])

  const markMissing = React.useCallback((productId: number) => {
    setRecipes((r) => ({ ...r, [productId]: { status: "missing" } }))
  }, [])

  /** After a run: the product's new stock and average, fresh material stock, the new batch. */
  const refreshAfterRun = React.useCallback(async (productId: number) => {
    const [product, materials, batches] = await Promise.all([getProduct(productId), listMaterials(), listProduction()])
    setBase((b) =>
      b.status !== "ready"
        ? b
        : { ...b, products: b.products.map((p) => (p.id === product.id ? product : p)), materials, batches }
    )
  }, [])

  const refreshMaterials = React.useCallback(async () => {
    const materials = await listMaterials()
    setBase((b) => (b.status !== "ready" ? b : { ...b, materials }))
  }, [])

  return { base, recipes, timeZone, reload, setRecipe, markMissing, refreshAfterRun, refreshMaterials }
}
