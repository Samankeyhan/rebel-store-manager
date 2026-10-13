"use client"

import * as React from "react"
import { getSettings, listMaterials, listProducts, type Material, type Product } from "@/lib/api"
import { DEFAULT_TZ } from "@/lib/store-day"

type Catalog = { status: "loading" } | { status: "error" } | { status: "ready"; products: Product[]; materials: Material[] }

/** Every product and material (active or not: the screen filters), and the store time zone for «today». */
export function useStocktakeData() {
  const [catalog, setCatalog] = React.useState<Catalog>({ status: "loading" })
  const [timeZone, setTimeZone] = React.useState(DEFAULT_TZ)
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([listProducts(), listMaterials()]).then(
      ([products, materials]) => !cancelled && setCatalog({ status: "ready", products, materials }),
      () => !cancelled && setCatalog((c) => (c.status === "ready" ? c : { status: "error" }))
    )
    getSettings().then(
      (s) => !cancelled && setTimeZone(s.timezone || DEFAULT_TZ),
      () => {}
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const reload = React.useCallback(() => setAttempt((n) => n + 1), [])
  return { catalog, timeZone, reload }
}
