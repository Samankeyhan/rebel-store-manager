"use client"

import * as React from "react"
import { getCurrency, subscribeCurrency, type Currency } from "./money"

/**
 * The active display currency; re-renders the caller when it changes. Each
 * page root calls it once so every money string on the page (including the
 * plain-function ones in copy.ts) is rebuilt on a switch; <Money> calls it too.
 * The server snapshot is TOMAN (static export); the cached/real value arrives
 * after hydration via CurrencyProvider.
 */
export function useCurrency(): Currency {
  return React.useSyncExternalStore(subscribeCurrency, getCurrency, () => "TOMAN")
}
