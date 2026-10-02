"use client"

import * as React from "react"

/**
 * Lets a page turn the top bar into its breadcrumb form
 * (design 04: «سفارش‌ها ‹ INV-000038»). Pages without a crumb keep the
 * plain nav-item title.
 */
export type Crumb = { parentHref: string; parentLabel: string; title: string }

type CrumbState = { crumb: Crumb | null; setCrumb: (crumb: Crumb | null) => void }

const CrumbContext = React.createContext<CrumbState>({ crumb: null, setCrumb: () => {} })

export function TopBarCrumbProvider({ children }: { children: React.ReactNode }) {
  const [crumb, setCrumb] = React.useState<Crumb | null>(null)
  const value = React.useMemo(() => ({ crumb, setCrumb }), [crumb])
  return <CrumbContext.Provider value={value}>{children}</CrumbContext.Provider>
}

export function useTopBarCrumb(): Crumb | null {
  return React.useContext(CrumbContext).crumb
}

/** Shows `crumb` in the top bar while the calling page is mounted. */
export function usePageCrumb(crumb: Crumb | null) {
  const { setCrumb } = React.useContext(CrumbContext)
  const key = crumb ? `${crumb.parentHref}|${crumb.parentLabel}|${crumb.title}` : ""
  React.useEffect(() => {
    if (!key) return
    const [parentHref, parentLabel, title] = key.split("|")
    setCrumb({ parentHref, parentLabel, title })
    return () => setCrumb(null)
  }, [key, setCrumb])
}
