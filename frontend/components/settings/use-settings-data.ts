"use client"

import * as React from "react"
import {
  getKit,
  getPostageEstimate,
  getSettings,
  listKits,
  listPaymentMethods,
  listPostageBatches,
  type KitDetail,
  type PaymentMethod,
  type PostageBatch,
  type PostageEstimate,
  type Settings,
} from "@/lib/api"

type Ready = {
  status: "ready"
  settings: Settings
  kits: KitDetail[]
  batches: PostageBatch[]
  estimate: PostageEstimate
  /** Every payment method, inactive ones included (the card lists them; a channel default may point at one). */
  methods: PaymentMethod[]
}
type State = { status: "loading" } | { status: "error" } | Ready

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name, "fa")

/** Every kit with its cost (the list endpoint has none, so each detail is fetched), inactive ones included. */
async function loadKits(): Promise<KitDetail[]> {
  const list = await listKits()
  const kits = await Promise.all(list.map((k) => getKit(k.id)))
  return kits.sort(byName)
}

/**
 * Settings (the saved baseline), kits (picker options and their costs; an
 * inactive kit is kept only to name a channel default that points at one),
 * the postage payments and API estimate the estimate preview needs, and the
 * payment methods (their card and the channel default pickers).
 */
export function useSettingsData() {
  const [state, setState] = React.useState<State>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([getSettings(), loadKits(), listPostageBatches(), getPostageEstimate(), listPaymentMethods(true)]).then(
      ([settings, kits, batches, estimate, methods]) =>
        !cancelled && setState({ status: "ready", settings, kits, batches, estimate, methods }),
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

  const patch = React.useCallback((p: Partial<Omit<Ready, "status">>) => {
    setState((s) => (s.status === "ready" ? { ...s, ...p } : s))
  }, [])

  const setSettings = React.useCallback((settings: Settings) => patch({ settings }), [patch])
  const refreshKits = React.useCallback(async () => patch({ kits: await loadKits() }), [patch])
  const refreshEstimate = React.useCallback(async () => patch({ estimate: await getPostageEstimate() }), [patch])
  const refreshMethods = React.useCallback(async () => patch({ methods: await listPaymentMethods(true) }), [patch])
  /** Replace (or add) one method after a save, keeping the list sorted by name like the API. */
  const putMethod = React.useCallback((m: PaymentMethod) => {
    setState((s) =>
      s.status === "ready"
        ? { ...s, methods: [...s.methods.filter((x) => x.id !== m.id), m].sort(byName) }
        : s
    )
  }, [])

  return { state, reload, setSettings, refreshKits, refreshEstimate, refreshMethods, putMethod }
}
