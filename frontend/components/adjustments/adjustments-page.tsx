"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Check, Loader2 } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { ErrorBlock, LoadingBlock } from "@/components/common/screen-states"
import { Toast } from "@/components/common/toast"
import { unitLabel } from "@/components/products/figures"
import { Btn } from "@/components/record-sale/primitives"
import type { Adjustment, AdjustmentItemType, AdjustmentReason, Material, Product } from "@/lib/api"
import { jalaliMonthRange, type IsoRange } from "@/lib/jalali"
import { AdjustmentForm, type AdjustmentFormHandle } from "./adjustment-form"
import { A } from "./copy"
import type { ItemKind } from "./figures"
import { HistoryCard, RecentList, type ItemFilter, type KindFilter } from "./history"
import { useAdjustmentsData } from "./use-adjustments-data"
import { useCurrency } from "@/lib/use-currency"

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/
const KINDS = ["all", "waste", "correction"] as const
const ITEM_RE = /^(type:(PRODUCT|MATERIAL)|(PRODUCT|MATERIAL):\d+)$/

/**
 * تعدیل موجودی (design 10). Desktop: the form and its live preview side by
 * side, the history below. Mobile: the form, a compact preview, «اخیر», and
 * a sticky save button. History filters live in the URL (?kind=, ?item=,
 * ?from=&to=).
 */
export function AdjustmentsPage() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()

  const [now] = React.useState(() => new Date())
  const defaultRange = React.useMemo(() => jalaliMonthRange(now), [now])

  const kindParam = params.get("kind")
  const kind: KindFilter = KINDS.includes(kindParam as KindFilter) ? (kindParam as KindFilter) : "all"
  const itemParam = params.get("item") ?? ""
  const item: ItemFilter = ITEM_RE.test(itemParam) ? itemParam : ""
  const from = params.get("from")
  const to = params.get("to")
  const range: IsoRange = from && to && ISO_DAY.test(from) && ISO_DAY.test(to) && from <= to ? { from, to } : defaultRange

  const itemType: AdjustmentItemType | null = item ? (item.replace(/^type:/, "").split(":")[0] as AdjustmentItemType) : null
  const itemId = item && !item.startsWith("type:") ? Number(item.split(":")[1]) : null
  const reason: AdjustmentReason | null = kind === "waste" ? "WASTE" : kind === "correction" ? "ADJUSTMENT" : null

  const setParams = React.useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(window.location.search)
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      const qs = next.toString()
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
    },
    [router, pathname]
  )

  // Mobile shows the newest adjustments overall, so no filters there.
  const data = useAdjustmentsData(
    mobile ? {} : { itemType, reason, from: range.from, to: range.to }
  )
  const { catalog, list } = data

  const [formBusy, setFormBusy] = React.useState(false)
  const formRef = React.useRef<AdjustmentFormHandle>(null)
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const products = React.useMemo(() => (catalog.status === "ready" ? catalog.products : []), [catalog])
  const materials = React.useMemo(() => (catalog.status === "ready" ? catalog.materials : []), [catalog])
  const unitOf = React.useMemo(() => {
    const units = new Map(materials.map((m) => [m.id, unitLabel(m.unit)]))
    return (row: Adjustment) => (row.item_type === "MATERIAL" ? (units.get(row.item_id) ?? "") : "عدد")
  }, [materials])

  const onSaved = (k: ItemKind, fresh: Product | Material | null, message: string) => {
    if (fresh) data.replaceItem(k, fresh)
    data.refreshList()
    setToast(message)
  }

  const rows = list.status === "ready" ? list.rows.filter((r) => itemId == null || r.item_id === itemId) : []

  // Items seen in the loaded history (plus the selected one), for the «کالا» filter.
  const itemOptions = React.useMemo(() => {
    const p = new Map<number, string>()
    const m = new Map<number, string>()
    for (const r of list.status === "ready" ? list.rows : []) {
      ;(r.item_type === "PRODUCT" ? p : m).set(r.item_id, r.item_name ?? String(r.item_id))
    }
    if (itemId != null && itemType === "PRODUCT" && !p.has(itemId)) {
      const found = products.find((x) => x.id === itemId)
      if (found) p.set(itemId, found.name)
    }
    if (itemId != null && itemType === "MATERIAL" && !m.has(itemId)) {
      const found = materials.find((x) => x.id === itemId)
      if (found) m.set(itemId, found.name)
    }
    const sorted = (map: Map<number, string>) => [...map].sort((a, b) => a[1].localeCompare(b[1], "fa"))
    return { products: sorted(p), materials: sorted(m) }
  }, [list, itemId, itemType, products, materials])

  const filtersActive = kind !== "all" || item !== "" || range.from !== defaultRange.from || range.to !== defaultRange.to
  const clearFilters = () => router.replace(pathname, { scroll: false })

  const toastNode = toast && <Toast title={toast} onClose={closeToast} closeLabel={A.close} />

  if (catalog.status === "error")
    return (
      <ErrorBlock
        title={mobile ? A.errorTitleMobile : A.errorTitle}
        body={A.errorBody}
        retry={A.retry}
        onRetry={data.reload}
        mobile={mobile}
      />
    )
  if (catalog.status === "loading") return <LoadingBlock mobile={mobile} label={A.loadingAria} />

  const form = (
    <AdjustmentForm
      ref={formRef}
      products={products}
      materials={materials}
      mobile={mobile}
      onBusyChange={setFormBusy}
      onSaved={onSaved}
      onItemRefreshed={data.replaceItem}
      onItemsStale={() => data.refreshCatalog().catch(() => {})}
    />
  )

  if (mobile) {
    return (
      <div className="flex flex-col gap-3 pb-24">
        {form}
        <RecentList list={list} unitOf={unitOf} timeZone={data.timeZone} onRetry={data.reload} />
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
          <Btn
            variant="primary"
            size="lg"
            className="w-full"
            disabled={formBusy}
            aria-busy={formBusy || undefined}
            onClick={() => formRef.current?.submit()}
          >
            {formBusy ? <Loader2 className="size-[18px] animate-spin" /> : <Check className="size-[18px]" />}
            {A.submit}
          </Btn>
        </div>
        {toastNode}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {form}
      <HistoryCard
        list={list}
        rows={rows}
        unitOf={unitOf}
        timeZone={data.timeZone}
        kind={kind}
        onKind={(k) => setParams({ kind: k === "all" ? null : k })}
        item={item}
        onItem={(v) => setParams({ item: v || null })}
        itemOptions={itemOptions}
        range={range}
        onRange={(r) =>
          setParams(r.from === defaultRange.from && r.to === defaultRange.to ? { from: null, to: null } : { from: r.from, to: r.to })
        }
        filtersActive={filtersActive}
        onClear={clearFilters}
        onRetry={data.reload}
        onEmptyCta={() => formRef.current?.focus()}
      />
      {toastNode}
    </div>
  )
}
