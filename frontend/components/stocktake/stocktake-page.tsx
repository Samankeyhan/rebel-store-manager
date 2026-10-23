"use client"

import * as React from "react"
import { useSearchParams } from "next/navigation"
import { ClipboardList, Loader2 } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { Segment } from "@/components/common/segment"
import { Switch } from "@/components/products/drawer-shell"
import { Alert, Btn, cardClass, inputClass } from "@/components/record-sale/primitives"
import { useIsMobile } from "@/hooks/use-mobile"
import { ApiError, applyStocktake, previewStocktake, type StocktakeItem, type StocktakeRequest, type StocktakeResult } from "@/lib/api"
import { itemErrorTarget, staleItems } from "@/lib/error-codes"
import { storeToday } from "@/lib/store-day"
import {
  clearDraft,
  emptyDraft,
  filterRows,
  isEmptyDraft,
  loadDraft,
  movedSince,
  rowState,
  saveDraft,
  type ItemKind,
  type RowState,
  type StorageLike,
} from "@/lib/stocktake"
import { useCurrency } from "@/lib/use-currency"
import { materialFromParams } from "@/lib/stocktake-link"
import { CountTable, type CostValue } from "./count-table"
import { S } from "./copy"
import { buildRows, type StockRow } from "./figures"
import { ResultCard } from "./result-card"
import { ReviewDialog } from "./review-dialog"
import { useStocktakeData } from "./use-stocktake-data"

function browserStorage(): StorageLike | null {
  try {
    return window.localStorage
  } catch {
    return null // blocked storage: the screen works, only without a draft
  }
}

type ApplyError = { message: string; code: string }

function describe(e: unknown): ApplyError {
  return e instanceof ApiError
    ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : e.code ?? `STOCKTAKE_${e.status}` }
    : { message: String(e), code: "UNKNOWN" }
}

/**
 * «شمارش موجودی»: enter what you physically counted, see the difference against the system stock, review every
 * correction, apply them all at once. Counts stay in a browser-only draft (localStorage) until applied.
 */
export function StocktakePage() {
  useCurrency() // re-render when the display currency switches (values in the review)
  const mobile = useIsMobile()
  const { catalog, timeZone, reload } = useStocktakeData()

  const [tab, setTab] = React.useState<ItemKind>("PRODUCT")
  const [counts, setCounts] = React.useState<Record<string, string>>({})
  const [costs, setCosts] = React.useState<Record<string, CostValue>>({})
  const [seen, setSeen] = React.useState<Record<string, number>>({})
  const [date, setDate] = React.useState<string | null>(null)
  const [note, setNote] = React.useState("")
  const [query, setQuery] = React.useState("")
  const [category, setCategory] = React.useState("")
  const [onlyDifferences, setOnlyDifferences] = React.useState(false)
  const [showInactive, setShowInactive] = React.useState(false)
  const [attempted, setAttempted] = React.useState(false)
  const [rowErrors, setRowErrors] = React.useState<Record<string, string>>({})
  const [banner, setBanner] = React.useState<{ tone: "err" | "warn"; title: string; body: string; code?: string } | null>(null)
  const [reviewing, setReviewing] = React.useState(false)
  const [plan, setPlan] = React.useState<StocktakeResult | null>(null)
  const [applying, setApplying] = React.useState(false)
  const [dialogError, setDialogError] = React.useState<ApplyError | null>(null)
  const [result, setResult] = React.useState<StocktakeResult | null>(null)
  const [restored, setRestored] = React.useState(0)
  const [confirmClear, setConfirmClear] = React.useState(false)
  // ?material=<id> (the materials tab links here): open on that material, found by name and highlighted. Only the view
  // changes: counts, costs and a stored draft are never read or written because of the link.
  const linkedMaterial = materialFromParams(useSearchParams())
  const [highlightKey, setHighlightKey] = React.useState<string | null>(null)
  const [linkApplied, setLinkApplied] = React.useState(false)

  const products = catalog.status === "ready" ? catalog.products : null
  const materials = catalog.status === "ready" ? catalog.materials : null
  const rows = React.useMemo(() => (products && materials ? buildRows(products, materials) : []), [products, materials])
  if (!linkApplied && linkedMaterial != null && rows.length > 0) {
    setLinkApplied(true)
    const target = rows.find((r) => r.kind === "MATERIAL" && r.id === linkedMaterial)
    if (target) {
      setTab("MATERIAL")
      setQuery(target.name)
      if (!target.isActive) setShowInactive(true)
      setHighlightKey(target.key)
    }
  }
  const systemOf = React.useMemo(() => Object.fromEntries(rows.map((r) => [r.key, r.systemQuantity])), [rows])

  // ---- the draft: read once, when the items are first loaded (state adjusted while rendering, as elsewhere in the app);
  // written (debounced) on every change afterwards
  const [draftChecked, setDraftChecked] = React.useState(false)
  if (!draftChecked && rows.length > 0) {
    setDraftChecked(true)
    const draft = loadDraft(browserStorage(), new Set(rows.map((r) => r.key)))
    if (draft && !isEmptyDraft(draft)) {
      setCounts(draft.counts)
      setCosts(draft.costs)
      setSeen(draft.seen)
      setDate(draft.date)
      setRestored(Object.keys(draft.counts).length)
    }
  }

  React.useEffect(() => {
    if (!draftChecked) return
    const timer = window.setTimeout(() => {
      const draft = emptyDraft(new Date().toISOString())
      draft.date = date
      draft.counts = counts
      draft.costs = Object.fromEntries(Object.entries(costs).filter((e): e is [string, number] => typeof e[1] === "number"))
      draft.seen = Object.fromEntries(Object.entries(seen).filter(([key]) => key in counts))
      saveDraft(browserStorage(), draft)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [draftChecked, counts, costs, seen, date])

  const today = storeToday(new Date(), timeZone)

  // ---- row states
  const states = React.useMemo(() => {
    const map = new Map<string, RowState>()
    for (const row of rows) {
      map.set(
        row.key,
        rowState({
          kind: row.kind,
          systemQuantity: row.systemQuantity,
          countText: counts[row.key] ?? "",
          costUnknown: row.costUnknown,
          hasCost: typeof costs[row.key] === "number",
        })
      )
    }
    return map
  }, [rows, counts, costs])

  const flagged = React.useMemo(() => new Set(movedSince(seen, systemOf).filter((key) => key in counts)), [seen, systemOf, counts])

  const onCount = (key: string, text: string) => {
    setRowErrors((e) => (key in e ? Object.fromEntries(Object.entries(e).filter(([k]) => k !== key)) : e))
    setCounts((c) => {
      if (text.trim() === "") return Object.fromEntries(Object.entries(c).filter(([k]) => k !== key))
      return { ...c, [key]: text }
    })
    setSeen((s) => ({ ...s, [key]: systemOf[key] }))
    if (text.trim() === "") setCosts((c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== key)))
    // A gain on a product with no stored cost: prefill the required cost with its complete recipe cost. Editable, and
    // still part of the review the owner confirms.
    const row = rows.find((r) => r.key === key)
    if (row?.prefillCost != null && text.trim() !== "") {
      const next = rowState({ kind: row.kind, systemQuantity: row.systemQuantity, countText: text, costUnknown: row.costUnknown, hasCost: false })
      const prefill = row.prefillCost
      if (next.status === "gain") setCosts((c) => (key in c ? c : { ...c, [key]: prefill }))
    }
  }
  const onCost = (key: string, value: CostValue) => setCosts((c) => ({ ...c, [key]: value }))
  const onRecheck = (key: string) => setSeen((s) => ({ ...s, [key]: systemOf[key] }))

  // ---- visible rows
  const tabRows = React.useMemo(() => rows.filter((r) => r.kind === tab), [rows, tab])
  const categories = React.useMemo(() => [...new Set(tabRows.map((r) => r.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, "fa")), [tabRows])
  const visible = React.useMemo(
    () => filterRows(tabRows, { query, category, onlyDifferences, showInactive }, (r: StockRow) => states.get(r.key)?.status ?? "blank"),
    [tabRows, query, category, onlyDifferences, showInactive, states]
  )
  const filtersActive = query !== "" || category !== "" || onlyDifferences

  const summary = React.useMemo(() => {
    let counted = 0
    let diffs = 0
    for (const state of states.values()) {
      if (state.status !== "blank") counted += 1
      if (state.status === "gain" || state.status === "loss") diffs += 1
    }
    return { counted, diffs, total: rows.length }
  }, [states, rows.length])

  // ---- review and apply
  const buildRequest = (): { body: StocktakeRequest; keys: string[] } | null => {
    setAttempted(true)
    setBanner(null)
    const items: StocktakeItem[] = []
    const keys: string[] = []
    let invalid = 0
    let needsCost = 0
    for (const row of rows) {
      const state = states.get(row.key) as RowState
      if (state.status === "blank") continue
      if (state.status === "invalid") {
        invalid += 1
        continue
      }
      const cost = costs[row.key]
      if (cost === null) invalid += 1
      if (state.needsCost) needsCost += 1
      items.push({
        item_type: row.kind,
        item_id: row.id,
        counted: state.counted as number,
        system_quantity: row.systemQuantity,
        ...(state.status === "gain" && typeof cost === "number" ? { unit_cost: cost } : {}),
      })
      keys.push(row.key)
    }
    if (invalid > 0) {
      setBanner({ tone: "err", title: S.invalidRows(invalid), body: "" })
      return null
    }
    if (flagged.size > 0) {
      setBanner({ tone: "warn", title: S.recheckNeeded, body: S.pauseBody })
      return null
    }
    if (needsCost > 0) {
      setBanner({ tone: "err", title: S.costRequired, body: "" })
      return null
    }
    if (items.length === 0) {
      setBanner({ tone: "warn", title: S.nothingCounted, body: "" })
      return null
    }
    return { body: { stocktake_date: date ?? undefined, note: note.trim() || undefined, items }, keys }
  }

  const fail = (e: unknown, keys: string[], inDialog: boolean) => {
    const stale = e instanceof ApiError ? staleItems(e) : []
    if (stale.length > 0) {
      setPlan(null)
      setReviewing(false)
      setBanner({ tone: "warn", title: S.staleTitle, body: S.staleBody(stale.length) })
      reload() // the fresh system quantities flag the rows that moved; the typed counts stay
      return
    }
    const target = e instanceof ApiError ? itemErrorTarget(e.field) : null
    const key = target ? keys[target.index] : undefined
    if (key) {
      setRowErrors((errors) => ({ ...errors, [key]: (e as ApiError).message }))
      const row = rows.find((r) => r.key === key)
      if (row) setTab(row.kind)
    }
    if (inDialog) setDialogError(describe(e))
    else {
      const info = describe(e)
      setBanner({ tone: "err", title: S.applyFailed, body: info.message, code: info.code })
    }
  }

  const pending = React.useRef<{ body: StocktakeRequest; keys: string[] } | null>(null)

  const onReview = async () => {
    const request = buildRequest()
    if (!request) return
    pending.current = request
    setReviewing(true)
    setDialogError(null)
    try {
      const plan = await previewStocktake(request.body)
      setPlan(plan)
    } catch (e) {
      fail(e, request.keys, false)
    } finally {
      setReviewing(false)
    }
  }

  const onApply = async () => {
    const request = pending.current
    if (!request) return
    setApplying(true)
    setDialogError(null)
    try {
      const done = await applyStocktake(request.body)
      clearDraft(browserStorage())
      setCounts({})
      setCosts({})
      setSeen({})
      setDate(null)
      setNote("")
      setRowErrors({})
      setAttempted(false)
      setPlan(null)
      setResult(done)
      reload()
    } catch (e) {
      fail(e, request.keys, true)
    } finally {
      setApplying(false)
    }
  }

  const clearAll = () => {
    clearDraft(browserStorage())
    setCounts({})
    setCosts({})
    setSeen({})
    setDate(null)
    setRowErrors({})
    setAttempted(false)
    setBanner(null)
    setRestored(0)
    setConfirmClear(false)
  }

  if (catalog.status === "error")
    return <ErrorBlock title={S.errorTitle} body={S.errorBody} retry={S.retry} onRetry={reload} mobile={mobile} />
  if (catalog.status === "loading") return <LoadingBlock mobile={mobile} label={S.loadingAria} />

  if (result)
    return (
      <div className="flex flex-col gap-4">
        <ResultCard result={result} onAgain={() => setResult(null)} />
      </div>
    )

  const toggle = (id: string, label: string, checked: boolean, onChange: (v: boolean) => void) => (
    <label htmlFor={id} className="flex cursor-pointer items-center gap-2 text-[13px] font-medium">
      <Switch id={id} checked={checked} onChange={onChange} />
      {label}
    </label>
  )

  return (
    <div className="flex flex-col gap-4 pb-6">
      <p className="text-sm text-text-2">{S.intro}</p>
      <Alert tone="warn" title={S.pauseTitle} icon="triangle">
        {S.pauseBody}
      </Alert>
      {restored > 0 && <p className="text-xs text-text-2">{S.draftRestored(restored)}</p>}
      {banner && (
        <Alert tone={banner.tone} title={banner.title}>
          {banner.body && <div dir="auto">{banner.body}</div>}
          {banner.code && (
            <div className="mt-1 text-xs text-text-3">
              {S.errorCode}{" "}
              <span dir="ltr" className="inline-block font-mono">
                {banner.code}
              </span>
            </div>
          )}
        </Alert>
      )}

      <section className={`${cardClass} flex flex-col gap-3 px-4 py-4`}>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex w-56 max-w-full flex-col gap-1.5">
            <label htmlFor="st-date" className="text-[13px] font-semibold">
              {S.fieldDate}
            </label>
            <DateField id="st-date" value={date ?? today} today={today} onChange={(iso) => setDate(iso === today ? null : iso)} todayLabel="امروز" mobile={mobile} />
          </div>
          <div className="flex min-w-48 grow flex-col gap-1.5">
            <label htmlFor="st-note" className="text-[13px] font-semibold">
              {S.fieldNote}
            </label>
            <input id="st-note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} placeholder={S.notePlaceholder} className={inputClass()} />
          </div>
        </div>
        <Segment
          value={tab}
          onChange={setTab}
          label={S.tabsLabel}
          mobile={mobile}
          options={[
            ["PRODUCT", S.tabProducts],
            ["MATERIAL", S.tabMaterials],
          ]}
        />
        <div className="flex flex-wrap items-center gap-3">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={S.search} aria-label={S.search} className={inputClass(null, "w-56")} />
          <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label={S.colCategory} className={inputClass(null, "w-52")}>
            <option value="">{S.allCategories}</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          {toggle("st-diff", S.onlyDifferences, onlyDifferences, setOnlyDifferences)}
          {toggle("st-inactive", S.showInactive, showInactive, setShowInactive)}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-text-2">
          <span aria-live="polite">{S.progress(summary.counted, summary.total, summary.diffs)}</span>
          {summary.counted > 0 &&
            (confirmClear ? (
              <span className="flex items-center gap-2">
                {S.clearDraftConfirm}
                <Btn size="sm" variant="primary" onClick={clearAll}>
                  {S.clearDraftYes}
                </Btn>
                <Btn size="sm" onClick={() => setConfirmClear(false)}>
                  {S.keep}
                </Btn>
              </span>
            ) : (
              <Btn size="sm" variant="ghost" onClick={() => setConfirmClear(true)}>
                {S.clearDraft}
              </Btn>
            ))}
        </div>
      </section>

      {visible.length === 0 ? (
        <StateShell
          icon={ClipboardList}
          mobile={mobile}
          title={filtersActive ? S.noMatch : S.noRows}
          action={
            filtersActive ? (
              <Btn
                onClick={() => {
                  setQuery("")
                  setCategory("")
                  setOnlyDifferences(false)
                }}
              >
                {S.clearFilters}
              </Btn>
            ) : undefined
          }
        />
      ) : (
        <CountTable
          rows={visible}
          states={states}
          counts={counts}
          costs={costs}
          flagged={flagged}
          rowErrors={rowErrors}
          attempted={attempted}
          mobile={mobile}
          onCount={onCount}
          onCost={onCost}
          onRecheck={onRecheck}
          highlightKey={highlightKey}
        />
      )}

      <div className="sticky bottom-3 z-30 rounded-xl border border-border bg-card px-4 py-3 shadow-[0_8px_24px_rgba(18,22,38,.12)]">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-text-2">{S.progress(summary.counted, summary.total, summary.diffs)}</span>
          <Btn variant="primary" size={mobile ? "lg" : "md"} disabled={reviewing || summary.counted === 0} aria-busy={reviewing || undefined} onClick={onReview}>
            {reviewing && <Loader2 className="size-4 animate-spin" />}
            {reviewing ? S.reviewing : S.reviewCount(summary.counted)}
          </Btn>
        </div>
      </div>

      <ReviewDialog
        open={plan != null}
        plan={plan}
        busy={applying}
        error={dialogError}
        onApply={onApply}
        onClose={() => {
          setPlan(null)
          setDialogError(null)
        }}
      />
    </div>
  )
}
