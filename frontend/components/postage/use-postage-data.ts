"use client"

import * as React from "react"
import { getPostageEstimate, getSettings, listPostageBatches, type PostageBatch, type PostageEstimate, type Settings } from "@/lib/api"

type State =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; batches: PostageBatch[]; estimate: PostageEstimate; settings: Settings }

/** Payments (newest first), the API's current estimate, and settings (default estimate, channels, timezone). */
export function usePostageData() {
  const [state, setState] = React.useState<State>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([listPostageBatches(), getPostageEstimate(), getSettings()]).then(
      ([batches, estimate, settings]) => !cancelled && setState({ status: "ready", batches, estimate, settings }),
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

  /** After a payment: re-read the list and the estimate, so the headline is the server's. */
  const refresh = React.useCallback(async (): Promise<PostageEstimate> => {
    const [batches, estimate] = await Promise.all([listPostageBatches(), getPostageEstimate()])
    setState((s) => (s.status === "ready" ? { ...s, batches, estimate } : s))
    return estimate
  }, [])

  return { state, reload, refresh }
}
