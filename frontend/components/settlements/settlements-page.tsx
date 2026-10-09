"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Clock, Hourglass } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { Segment } from "@/components/common/segment"
import { Toast } from "@/components/common/toast"
import { useStoreTimeZone } from "@/components/dashboard/use-dashboard-data"
import { storeToday } from "@/lib/store-day"
import { useCurrency } from "@/lib/use-currency"
import { cn } from "@/lib/utils"
import { S } from "./copy"
import { PendingTab } from "./pending-tab"

const TABS = ["pending", "history"] as const
type Tab = (typeof TABS)[number]
const isTab = (v: string | null): v is Tab => TABS.includes(v as Tab)

/**
 * تسویه‌ها: the owner matches what each payment method paid out against its
 * pending orders and records the settlement (nothing settles by itself).
 * «در انتظار» lists pending orders per method; «سابقه» lists recorded
 * settlements. The tab and the history's method filter live in the URL
 * (?tab=history&method=). "Today" is the store's day (settings.timezone).
 */
export function SettlementsPage() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()

  const tabParam = params.get("tab")
  const tab: Tab = isTab(tabParam) ? tabParam : "pending"

  const timeZone = useStoreTimeZone()
  const [now] = React.useState(() => new Date())
  // null until settings.timezone is known: the date field waits for it.
  const today = timeZone ? storeToday(now, timeZone) : null

  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const setParams = React.useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(window.location.search)
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      if (next.get("tab") === "pending") next.delete("tab")
      const qs = next.toString()
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
    },
    [router, pathname]
  )

  const tabs = mobile ? (
    <Segment<Tab>
      value={tab}
      options={[
        ["pending", S.tabPending],
        ["history", S.tabHistory],
      ]}
      onChange={(t) => setParams({ tab: t })}
      label={S.tabsLabel}
      mobile
      className="grid grid-cols-2"
    />
  ) : (
    <div role="tablist" aria-label={S.tabsLabel} className="flex gap-1 border-b border-border">
      {(
        [
          ["pending", S.tabPending, Hourglass],
          ["history", S.tabHistory, Clock],
        ] as const
      ).map(([id, label, Icon]) => {
        const on = tab === id
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => setParams({ tab: id })}
            className={cn(
              "-mb-px inline-flex h-10 cursor-pointer items-center gap-1.5 border-b-2 border-transparent px-3 text-[13.5px] font-semibold whitespace-nowrap text-text-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
              on && "border-primary text-heading"
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </button>
        )
      })}
    </div>
  )

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-5")}>
      {tabs}
      {tab === "pending" ? <PendingTab today={today} mobile={mobile} onToast={setToast} /> : null}
      {toast && <Toast title={toast} onClose={closeToast} closeLabel={S.close} />}
    </div>
  )
}
