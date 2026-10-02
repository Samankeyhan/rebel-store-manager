"use client"

import * as React from "react"
import { getKit, getSettings, listKits, listMaterials, type KitDetail, type Material, type Settings } from "@/lib/api"

type State =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; kits: KitDetail[]; materials: Material[]; settings: Settings }

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name, "fa")

/**
 * Kits (with their items and cost: the list endpoint has neither, so each
 * kit's detail is fetched), materials (units, stock, the add picker) and
 * settings (channel defaults). Every kit write returns the whole kit, which
 * replaces it here.
 */
export function usePackagingData() {
  const [state, setState] = React.useState<State>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    ;(async () => {
      const [list, materials, settings] = await Promise.all([listKits(), listMaterials(), getSettings()])
      const kits = await Promise.all(list.map((k) => getKit(k.id)))
      return { kits: kits.sort(byName), materials, settings }
    })().then(
      (data) => !cancelled && setState({ status: "ready", ...data }),
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

  const upsertKit = React.useCallback((kit: KitDetail) => {
    setState((s) =>
      s.status !== "ready"
        ? s
        : {
            ...s,
            kits: s.kits.some((k) => k.id === kit.id)
              ? s.kits.map((k) => (k.id === kit.id ? kit : k))
              : [...s.kits, kit].sort(byName),
          }
    )
  }, [])

  const refreshSettings = React.useCallback(async () => {
    const settings = await getSettings()
    setState((s) => (s.status === "ready" ? { ...s, settings } : s))
  }, [])

  return { state, reload, upsertKit, refreshSettings }
}
