"use client"

/**
 * «نمایش جزئیات و بها» on the Production screen: OFF by default, remembered
 * on this device. Shared by the three tabs through one localStorage key, so
 * every reader re-renders when it flips.
 */

import * as React from "react"

const KEY = "production:showDetails"
const EVENT = "production:showDetails"

function read(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1"
  } catch {
    return false
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange)
  window.addEventListener("storage", onChange)
  return () => {
    window.removeEventListener(EVENT, onChange)
    window.removeEventListener("storage", onChange)
  }
}

export function setShowDetails(on: boolean) {
  try {
    window.localStorage.setItem(KEY, on ? "1" : "0")
  } catch {
    // Storage unavailable (private mode): the choice lasts until reload.
    memory = on
  }
  window.dispatchEvent(new Event(EVENT))
}

let memory: boolean | null = null

/** false on the server and until the browser says otherwise. */
export function useShowDetails(): boolean {
  return React.useSyncExternalStore(
    subscribe,
    () => memory ?? read(),
    () => false,
  )
}
