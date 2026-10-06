"use client"

import * as React from "react"
import { getFeePreview } from "@/lib/api"

export const FEE_PREVIEW_DEBOUNCE_MS = 300

export type FeePreview =
  /** Nothing to ask: no method, a manual fee, or an amount that isn't exact yet. */
  | { status: "idle" }
  /** Waiting for the debounce or the response for the CURRENT method and amount. */
  | { status: "loading" }
  | { status: "ready"; fee: number }
  | { status: "error"; retry: () => void }

type Result = { key: string; fee: number | null }

/**
 * The fee the backend would charge (GET /payment-methods/{id}/fee-preview) for
 * the order's customer total. The frontend never computes a fee.
 *
 * In sync with the form: each result is stored with the method id and amount
 * it was asked for, and is returned only while both still match the current
 * inputs — anything older reads as "loading", never as a stale fee. Requests
 * are debounced while the owner types and the previous one is aborted.
 *
 * `amount` null (or `methodId` null) = don't ask.
 */
export function useFeePreview(methodId: number | null, amount: number | null): FeePreview {
  const key = methodId == null || amount == null ? null : `${methodId}|${amount}`
  const [result, setResult] = React.useState<Result | null>(null)
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    if (methodId == null || amount == null) return
    const requestKey = `${methodId}|${amount}`
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      getFeePreview(methodId, amount, controller.signal).then(
        (preview) => {
          if (controller.signal.aborted) return
          // Defensive: the answer must be for exactly what was asked.
          const matches = preview.payment_method_id === methodId && preview.amount === amount
          setResult({ key: requestKey, fee: matches ? preview.transaction_fee : null })
        },
        () => {
          if (!controller.signal.aborted) setResult({ key: requestKey, fee: null })
        }
      )
    }, FEE_PREVIEW_DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [methodId, amount, attempt])

  const retry = React.useCallback(() => {
    setResult(null)
    setAttempt((a) => a + 1)
  }, [])

  if (key === null) return { status: "idle" }
  if (result?.key !== key) return { status: "loading" }
  return result.fee === null ? { status: "error", retry } : { status: "ready", fee: result.fee }
}
