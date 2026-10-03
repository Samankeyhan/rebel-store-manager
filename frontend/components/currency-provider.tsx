"use client"

import * as React from "react"
import { getSettings } from "@/lib/api"
import { readCachedCurrency, setCurrency } from "@/lib/money"

/**
 * Loads the display currency once at app start: this browser's cached choice
 * first (no Toman flash for a Rial user), then GET /settings, which is the
 * source of truth. A failed load keeps the cache (or Toman) and never blocks
 * a screen. Settings → «واحد پول» calls setCurrency directly after saving.
 */
export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  React.useEffect(() => {
    const cached = readCachedCurrency()
    if (cached) setCurrency(cached)
    let cancelled = false
    getSettings().then(
      (s) => !cancelled && setCurrency(s.display_currency),
      (e) => console.warn("Display currency not loaded; keeping", cached ?? "TOMAN", e)
    )
    return () => {
      cancelled = true
    }
  }, [])
  return <>{children}</>
}
