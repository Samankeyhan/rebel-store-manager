"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Clock, Factory, PencilLine, Plus } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { Segment } from "@/components/common/segment"
import { Toast } from "@/components/common/toast"
import { Btn } from "@/components/record-sale/primitives"
import { presetRange, type IsoRange } from "@/lib/jalali"
import { cn } from "@/lib/utils"
import { R } from "./copy"
import { HistoryTab } from "./history-tab"
import { RecipeTab } from "./recipe-tab"
import { RunTab } from "./run-tab"
import { setShowDetails, useShowDetails } from "./show-details"
import { useProductionData } from "./use-production-data"

const TABS = ["run", "recipe", "history"] as const
type Tab = (typeof TABS)[number]
const isTab = (v: string | null): v is Tab => TABS.includes(v as Tab)

/**
 * تولید (design 06): run a batch, edit recipes, browse past runs. The tab and
 * the selected product live in the URL (?tab=, ?product=), shared by the run
 * and recipe tabs so «ویرایش دستور» / «ساخت دستور تولید» land on the same product.
 */
export function ProductionPage() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()
  const tabParam = params.get("tab")
  const tab: Tab = isTab(tabParam) ? tabParam : "run"
  const productParam = Number(params.get("product"))
  const productId = Number.isInteger(productParam) && productParam > 0 ? productParam : null

  const setParams = React.useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(window.location.search)
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      if (next.get("tab") === "run") next.delete("tab")
      const qs = next.toString()
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
    },
    [router, pathname]
  )

  // Read on the client (static export): the history's default range.
  const [now] = React.useState(() => new Date())
  const defaultRange = React.useMemo(() => presetRange("thisYear", now), [now])
  const [range, setRange] = React.useState<IsoRange>(defaultRange)

  const showDetails = useShowDetails()
  const data = useProductionData()
  const { base, recipes } = data
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const goRecipe = (id: number | null) => setParams({ tab: "recipe", product: id ? String(id) : null })
  const pickProduct = (id: number) => setParams({ product: String(id) })

  let body: React.ReactNode
  if (base.status === "loading") body = <LoadingBlock mobile={mobile} label={R.loadingAria} />
  else if (base.status === "error")
    body = <ErrorBlock title={R.errorTitle} body={R.errorBody} retry={R.retry} onRetry={data.reload} mobile={mobile} />
  else {
    const active = base.products.filter((p) => p.is_active === 1)
    const entries = active.map((p) => recipes[p.id])
    const indexDone = entries.every((e) => e && e.status !== "loading")
    const noneProducible = indexDone && !entries.some((e) => e?.status === "ok")

    if (tab === "run" && noneProducible && productId == null) {
      body = (
        <StateShell
          icon={Factory}
          mobile={mobile}
          title={R.emptyTitle}
          body={mobile ? R.emptyBodyMobile : R.emptyBody}
          action={
            <Btn variant="primary" size={mobile ? "lg" : "md"} className="mt-1.5" onClick={() => goRecipe(null)}>
              <Plus className="size-4" />
              {R.makeRecipe}
            </Btn>
          }
        />
      )
    } else if (tab === "run") {
      body = (
        <RunTab
          products={base.products}
          materials={base.materials}
          recipes={recipes}
          productId={productId}
          mobile={mobile}
          showDetails={showDetails}
          onGoRecipe={goRecipe}
          onRunsDone={async (succeeded) => {
            await data.refreshAfterRuns().catch(() => data.reload())
            if (succeeded > 0) setToast(R.toastRuns(succeeded))
          }}
          markMissing={data.markMissing}
        />
      )
    } else if (tab === "recipe") {
      body = (
        <RecipeTab
          products={base.products}
          materials={base.materials}
          recipes={recipes}
          productId={productId}
          onProductChange={pickProduct}
          setRecipe={data.setRecipe}
          mobile={mobile}
        />
      )
    } else {
      body = (
        <HistoryTab
          batches={base.batches}
          materials={base.materials}
          timeZone={data.timeZone}
          range={range}
          onRangeChange={setRange}
          defaultRange={defaultRange}
          mobile={mobile}
        />
      )
    }
  }

  const tabs = mobile ? (
    <Segment<Tab>
      value={tab}
      options={[
        ["run", R.segRun],
        ["recipe", R.segRecipe],
        ["history", R.segHistory],
      ]}
      onChange={(t) => setParams({ tab: t })}
      label={R.tabsLabel}
      mobile
      className="grid grid-cols-3"
    />
  ) : (
    <div role="tablist" aria-label={R.tabsLabel} className="flex gap-1 border-b border-border">
      {(
        [
          ["run", R.tabRun, Factory],
          ["recipe", R.tabRecipe, PencilLine],
          ["history", R.tabHistory, Clock],
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
      {base.status === "ready" && (
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-end">
            <label className="inline-flex cursor-pointer items-center gap-2.5 text-[13px] font-semibold text-text-2">
              {R.detailsToggle}
              <button
                type="button"
                role="switch"
                aria-checked={showDetails}
                onClick={() => setShowDetails(!showDetails)}
                className={cn(
                  "relative inline-flex h-6 w-10 shrink-0 cursor-pointer items-center rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                  showDetails ? "bg-primary" : "bg-border-strong"
                )}
              >
                <span
                  className={cn(
                    "absolute top-0.5 size-5 rounded-full bg-white shadow transition-[inset-inline-start]",
                    showDetails ? "start-[18px]" : "start-0.5"
                  )}
                />
              </button>
            </label>
          </div>
          {!showDetails && <p className="text-end text-xs text-text-3">{R.detailsHidden}</p>}
        </div>
      )}
      {base.status === "ready" && tabs}
      {body}
      {toast && <Toast title={toast} onClose={closeToast} closeLabel={R.close} />}
    </div>
  )
}
