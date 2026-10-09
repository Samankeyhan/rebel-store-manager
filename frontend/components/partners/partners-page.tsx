"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { HandCoins, Pencil, UserPlus, Users } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { ErrorBlock, LoadingBlock } from "@/components/common/screen-states"
import { Segment } from "@/components/common/segment"
import { Toast } from "@/components/common/toast"
import { useStoreTimeZone } from "@/components/dashboard/use-dashboard-data"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { listDistributions, listPartners, type DistributionListItem, type Partner } from "@/lib/api"
import { activeTotal, backendAcceptsTotal, percentText } from "@/lib/partners"
import { DEFAULT_TZ, storeToday } from "@/lib/store-day"
import { useCurrency } from "@/lib/use-currency"
import { cn } from "@/lib/utils"
import { S } from "./copy"
import { PartnersTab } from "./partners-tab"
import { PayoutDialog } from "./payout-dialog"
import { PayoutsTab } from "./payouts-tab"
import { SplitDialog, type SplitMode } from "./split-dialog"

const TABS = ["partners", "payouts"] as const
type Tab = (typeof TABS)[number]
const isTab = (v: string | null): v is Tab => TABS.includes(v as Tab)

type Data =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; partners: Partner[]; distributions: DistributionListItem[] }

/**
 * شرکا: partners and their percentage of the profit («شرکا»), and payouts
 * of profit to them («پرداخت‌ها», ?tab=payouts). A payout is split by
 * db/distributions.py: the screen shows its preview and saved shares and
 * never computes a share. «ثبت پرداخت» stays disabled while the active
 * partners' percentages fail the backend's sum check.
 */
export function PartnersPage() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()

  const tabParam = params.get("tab")
  const tab: Tab = isTab(tabParam) ? tabParam : "partners"

  const timeZone = useStoreTimeZone()
  const [now] = React.useState(() => new Date())
  // null until settings.timezone is known: «ثبت پرداخت» waits for it.
  const today = timeZone ? storeToday(now, timeZone) : null

  const [data, setData] = React.useState<Data>({ status: "loading" })
  const [reloadKey, setReloadKey] = React.useState(0)
  const [split, setSplit] = React.useState<SplitMode | null>(null)
  const [payoutOpen, setPayoutOpen] = React.useState(false)
  const [partial, setPartial] = React.useState<{ saved: string[]; error: string } | null>(null)
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const [loadedKey, setLoadedKey] = React.useState(reloadKey)
  if (loadedKey !== reloadKey) {
    setLoadedKey(reloadKey)
    // Keep showing the current data while it refreshes after a save.
    if (data.status === "error") setData({ status: "loading" })
  }
  React.useEffect(() => {
    let cancelled = false
    Promise.all([listPartners(false), listDistributions()]).then(
      ([partners, distributions]) => !cancelled && setData({ status: "ready", partners, distributions }),
      () => !cancelled && setData({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [reloadKey])
  const reload = () => setReloadKey((k) => k + 1)

  const setTab = (t: Tab) => {
    const next = new URLSearchParams(window.location.search)
    if (t === "partners") next.delete("tab")
    else next.set("tab", t)
    const qs = next.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
  }

  const tabs = mobile ? (
    <Segment<Tab>
      value={tab}
      options={[
        ["partners", S.tabPartners],
        ["payouts", S.tabPayouts],
      ]}
      onChange={setTab}
      label={S.tabsLabel}
      mobile
      className="grid grid-cols-2"
    />
  ) : (
    <div role="tablist" aria-label={S.tabsLabel} className="flex gap-1 border-b border-border">
      {(
        [
          ["partners", S.tabPartners, Users],
          ["payouts", S.tabPayouts, HandCoins],
        ] as const
      ).map(([id, label, Icon]) => {
        const on = tab === id
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => setTab(id)}
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

  let content: React.ReactNode
  if (data.status === "loading") content = <LoadingBlock mobile={mobile} label={S.loadingAria} />
  else if (data.status === "error")
    content = <ErrorBlock title={S.partnersErrorTitle} body={S.errorBody} retry={S.retry} onRetry={reload} mobile={mobile} />
  else {
    const { partners, distributions } = data
    const active = partners.filter((p) => p.is_active === 1)
    const totalOk = backendAcceptsTotal(partners)
    const size = mobile ? "lg" : "md"
    content = (
      <>
        <div className={cn("flex gap-2", mobile ? "flex-col" : "flex-wrap items-center")}>
          <Btn variant="primary" size={size} disabled={!today || active.length === 0 || !totalOk} onClick={() => setPayoutOpen(true)}>
            <HandCoins className="size-4" aria-hidden />
            {S.recordPayout}
          </Btn>
          <Btn size={size} onClick={() => setSplit({ kind: "add" })}>
            <UserPlus className="size-4" aria-hidden />
            {S.addPartner}
          </Btn>
          {active.length > 0 && (
            <Btn size={size} onClick={() => setSplit({ kind: "edit" })}>
              <Pencil className="size-4" aria-hidden />
              {S.editSplit}
            </Btn>
          )}
        </div>
        {partial && (
          <Alert
            tone="err"
            title={S.partialTitle}
            action={
              <Btn variant="ghost" size="sm" onClick={() => setPartial(null)}>
                {S.close}
              </Btn>
            }
          >
            <div dir="auto">{S.failedAt(partial.error)}</div>
            <div className="mt-1">{S.partialSaved}</div>
            <ul className="list-disc ps-5">
              {partial.saved.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            <div className="mt-1 font-semibold">{S.partialBlocked}</div>
          </Alert>
        )}
        {active.length > 0 && !totalOk && (
          <Alert tone="warn" icon="triangle" title={S.totalBadTitle}>
            {S.totalBadBody(percentText(activeTotal(partners)))}
          </Alert>
        )}
        {tab === "partners" ? (
          <PartnersTab
            partners={partners}
            reloadKey={reloadKey}
            mobile={mobile}
            onAdd={() => setSplit({ kind: "add" })}
            onDeactivate={(p) => setSplit({ kind: "deactivate", partner: p })}
          />
        ) : (
          <PayoutsTab rows={distributions} partners={partners} timeZone={timeZone ?? DEFAULT_TZ} mobile={mobile} />
        )}
        <SplitDialog
          mode={split}
          partners={partners}
          mobile={mobile}
          onClose={() => setSplit(null)}
          onDone={(text) => {
            setSplit(null)
            setPartial(null)
            setToast(text)
            reload()
          }}
          onPartial={(saved, error) => {
            setSplit(null)
            setPartial({ saved, error })
            reload()
          }}
        />
        {today && (
          <PayoutDialog
            open={payoutOpen}
            today={today}
            distributions={distributions}
            mobile={mobile}
            onClose={() => setPayoutOpen(false)}
            onSaved={() => {
              setPayoutOpen(false)
              setToast(S.toastPayout)
              setTab("payouts")
              reload()
            }}
          />
        )}
      </>
    )
  }

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-5")}>
      {tabs}
      {tab === "partners" && <p className="text-[13px] text-text-3">{S.intro}</p>}
      {content}
      {toast && <Toast title={toast} onClose={closeToast} closeLabel={S.close} />}
    </div>
  )
}
