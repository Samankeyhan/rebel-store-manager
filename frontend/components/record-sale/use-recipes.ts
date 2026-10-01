"use client"

import * as React from "react"
import { ApiError, getRecipe } from "@/lib/api"
import type { RecipeState } from "./derive"

/**
 * Recipe checks for the made-to-order products currently on the form,
 * fetched lazily (first time a product is picked) and cached per product.
 * A product with no entry yet reads as "loading". The cache lives as long
 * as the form: «ثبت فروش جدید» remounts it, so costs are re-read.
 *
 * 404 or an empty recipe → "missing" (the API would refuse a non-draft sale
 * with field "made_to_order"). Any other failure → "failed": not a block,
 * since POST /orders makes the real decision.
 */
export function useRecipes(productIds: number[]) {
  const [cache, setCache] = React.useState<Record<number, RecipeState>>({})
  const inFlight = React.useRef(new Set<number>())

  const key = [...new Set(productIds)].sort((a, b) => a - b).join(",")

  React.useEffect(() => {
    for (const id of key ? key.split(",").map(Number) : []) {
      if (id in cache || inFlight.current.has(id)) continue
      inFlight.current.add(id)
      getRecipe(id).then(
        (recipe) => {
          inFlight.current.delete(id)
          setCache((c) => ({
            ...c,
            [id]:
              recipe.items.length === 0
                ? { status: "missing" }
                : { status: "ok", unitCost: recipe.unit_cost_at_qty_1 },
          }))
        },
        (error: unknown) => {
          inFlight.current.delete(id)
          const missing = error instanceof ApiError && error.status === 404
          setCache((c) => ({ ...c, [id]: { status: missing ? "missing" : "failed" } }))
        }
      )
    }
  }, [key, cache])

  return cache
}
