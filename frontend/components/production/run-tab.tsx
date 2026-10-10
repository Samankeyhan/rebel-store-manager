"use client"

import * as React from "react"
import Link from "next/link"
import { Check, ChevronLeft, CircleCheck, Loader2, Plus, RotateCw, Trash2 } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { Collapsible } from "@/components/common/collapsible"
import { ItemPicker, type PickerItem } from "@/components/common/item-picker"
import { badgeBase } from "@/components/common/status"
import { Alert, Btn, Help, InlineMessage, Label, Stepper, btnClass, cardClass } from "@/components/record-sale/primitives"
import { SaveError } from "@/components/products/drawer-shell"
import { unitLabel } from "@/components/products/figures"
import { ApiError, runProduction, type Material, type Product } from "@/lib/api"
import { blendUnitCost, chainedPreviews, type BatchPreview, type ChainedPreview } from "@/lib/costing"
import { dateToISO } from "@/lib/jalali"
import { formatQuantity } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { Money } from "@/components/common/money"
import { cn } from "@/lib/utils"
import { R } from "./copy"
import type { RecipeEntry } from "./use-production-data"

// ---------------------------------------------------------------- line model

type LineError =
  | { type: "short"; name: string; needed: number; available: number; unit: string }
  | { type: "noRecipe" }
  | { type: "other"; message: string; code: string }

/**
 * draft → queued (submit) → submitting → success | failed;
 * failed → queued («تلاش دوباره…»); failed → draft (any edit).
 */
type LineStatus =
  | { kind: "draft" }
  | { kind: "queued" }
  | { kind: "submitting" }
  | { kind: "success"; unitCost: number }
  | { kind: "failed"; error: LineError }

type Line = { key: string; productId: number | null; qty: number; note: string; status: LineStatus }

let lineSeq = 0
const newLine = (productId: number | null = null): Line => ({
  key: `l${++lineSeq}`,
  productId,
  qty: 1,
  note: "",
  status: { kind: "draft" },
})

/** The browser's local calendar day, read when called (not when the form opened). */
const currentDay = () => dateToISO(new Date())

const editable = (l: Line) => l.status.kind === "draft" || l.status.kind === "failed"

function toLineError(e: unknown, unitOf: (name: string) => string): LineError {
  if (e instanceof ApiError && e.status === 409 && e.type === "InsufficientStockError") {
    const name = String(e.details.item_name ?? "")
    return {
      type: "short",
      name,
      needed: Number(e.details.needed ?? 0),
      available: Number(e.details.available ?? 0),
      unit: unitOf(name),
    }
  }
  if (e instanceof ApiError && e.status === 422 && e.code === "PRODUCT_NO_RECIPE") return { type: "noRecipe" }
  return e instanceof ApiError
    ? { type: "other", message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `PRODUCTION_${e.status}` }
    : { type: "other", message: String(e), code: "UNKNOWN" }
}

/**
 * اجرای تولید as a list: each line is its own production run (the backend
 * stays one product per batch). Lines are previewed against the material
 * stock left by the lines above them, and submitted one POST at a time, top
 * to bottom; a failed line never stops the rest.
 */
export function RunTab({
  products,
  materials,
  recipes,
  productId,
  mobile,
  onGoRecipe,
  onRunsDone,
  markMissing,
}: {
  products: Product[]
  materials: Material[]
  recipes: Record<number, RecipeEntry>
  /** ?product= — pre-fills a line (e.g. coming back from the recipe tab). */
  productId: number | null
  mobile: boolean
  onGoRecipe: (productId: number | null) => void
  /** After a run of lines: refresh products, materials and history; show the toast. */
  onRunsDone: (succeeded: number) => Promise<void>
  markMissing: (productId: number) => void
}) {
  const [lines, setLines] = React.useState<Line[]>(() => [newLine(productId)])
  // The line last added or edited: «ویرایش دستور» opens its product's recipe.
  const [expanded, setExpanded] = React.useState<string | null>(() => lines[0]?.key ?? null)
  // null = "today", resolved when submitting so a session crossing midnight
  // never sends yesterday; a day the user picks is sent as picked.
  const [pickedDate, setPickedDate] = React.useState<string | null>(null)
  const [today, setToday] = React.useState(currentDay)
  const [running, setRunning] = React.useState<{ done: number; total: number } | null>(null)
  const [summary, setSummary] = React.useState<{ ok: number; total: number } | null>(null)

  // Keep "today" (the date field's default and its future-day limit) current.
  React.useEffect(() => {
    const t = window.setInterval(() => setToday(currentDay()), 60_000)
    return () => window.clearInterval(t)
  }, [])

  // A product arriving via the URL lands on an empty line, or a new one.
  const [seenUrlProduct, setSeenUrlProduct] = React.useState(productId)
  if (productId !== seenUrlProduct) {
    setSeenUrlProduct(productId)
    if (productId != null && !lines.some((l) => l.productId === productId)) {
      const empty = lines.find((l) => l.productId == null && editable(l))
      if (empty) {
        setLines(lines.map((l) => (l.key === empty.key ? { ...l, productId } : l)))
        setExpanded(empty.key)
      } else {
        const line = newLine(productId)
        setLines([...lines, line])
        setExpanded(line.key)
      }
    }
  }

  const active = products.filter((p) => p.is_active === 1)
  const productById = new Map(active.map((p) => [p.id, p]))
  const stockById = React.useMemo(() => new Map(materials.map((m) => [m.id, m.current_stock])), [materials])
  const recipeItems = (id: number | null) => {
    const e = id == null ? undefined : recipes[id]
    return e?.status === "ok" ? e.recipe.items : null
  }
  const previews = chainedPreviews(
    lines.map((l) => ({ key: l.key, items: recipeItems(l.productId), qty: l.qty })),
    (id) => stockById.get(id) ?? null
  )

  /** Ready to send: a product whose recipe isn't known-missing, qty ≥ 1, not short. */
  const sendable = (l: Line) => {
    if (l.productId == null || l.qty < 1 || !productById.has(l.productId)) return false
    const status = recipes[l.productId]?.status
    if (status === "missing" || status === "loading" || status == null) return false
    const p = previews.get(l.key)
    return !p || p.short.length === 0
  }
  const eligible = lines.filter((l) => editable(l) && sendable(l))
  const failed = lines.filter((l) => l.status.kind === "failed")
  const runsTotal = eligible.reduce((s, l) => s + (previews.get(l.key)?.batchTotal ?? 0), 0)

  const update = (key: string, patch: Partial<Line>) =>
    setLines((ls) =>
      ls.map((l) =>
        l.key !== key
          ? l
          : // Editing a failed line returns it to draft and clears its error.
            { ...l, ...patch, status: l.status.kind === "failed" ? { kind: "draft" } : l.status }
      )
    )
  const addLine = () => {
    const line = newLine()
    setLines((ls) => [...ls, line])
    setExpanded(line.key)
  }
  const removeLine = (key: string) => setLines((ls) => (ls.length > 1 ? ls.filter((l) => l.key !== key) : [newLine()]))
  const setStatus = (key: string, status: LineStatus) =>
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, status } : l)))

  /** POST one line at a time, top to bottom; a failure is recorded and the loop goes on. */
  const run = async (batch: Line[]) => {
    if (batch.length === 0 || running) return
    setSummary(null)
    const keys = new Set(batch.map((l) => l.key))
    setLines((ls) => ls.map((l) => (keys.has(l.key) ? { ...l, status: { kind: "queued" } } : l)))
    setRunning({ done: 0, total: batch.length })

    let ok = 0
    for (const [i, line] of batch.entries()) {
      setStatus(line.key, { kind: "submitting" })
      const day = currentDay()
      try {
        const res = await runProduction({
          product_id: line.productId!,
          quantity_produced: line.qty,
          // Today (resolved now): the server stamps the current time.
          production_date: pickedDate == null || pickedDate === day ? null : pickedDate,
          notes: line.note.trim() || null,
        })
        ok += 1
        setStatus(line.key, { kind: "success", unitCost: res.batch.unit_cost })
      } catch (e) {
        const items = recipeItems(line.productId) ?? []
        const error = toLineError(e, (name) => unitLabel(items.find((it) => it.material_name === name)?.material_unit ?? ""))
        if (error.type === "noRecipe") markMissing(line.productId!)
        setStatus(line.key, { kind: "failed", error })
      }
      setRunning({ done: i + 1, total: batch.length })
    }

    // Let the user see the ✓ rows briefly, then refresh and drop them in one
    // step (so a finished line's stock is never counted twice).
    await new Promise((r) => window.setTimeout(r, 1500))
    await onRunsDone(ok)
    setLines((ls) => {
      const rest = ls.filter((l) => l.status.kind !== "success")
      return rest.length ? rest : [newLine()]
    })
    setRunning(null)
    if (ok < batch.length) setSummary({ ok, total: batch.length })
  }

  const busy = running != null
  const usedIds = new Set(lines.map((l) => l.productId).filter((id): id is number => id != null))
  const withRecipe = active.filter((p) => recipes[p.id]?.status === "ok")
  const expandedLine = lines.find((l) => l.key === expanded) ?? null

  const dateField = (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="run-date">{R.fieldDate}</Label>
      <DateField
        id="run-date"
        value={pickedDate ?? today}
        today={today}
        onChange={(d) => setPickedDate(d === today ? null : d)}
        todayLabel={R.today}
        mobile={mobile}
      />
    </div>
  )

  const summaryAlert = summary && failed.length > 0 && (
    <Alert
      tone="err"
      title={R.summaryTitle(summary.ok, summary.total)}
      action={
        !mobile && (
          <Btn size="sm" disabled={busy} onClick={() => run(failed)}>
            <RotateCw className="size-3.5" />
            {R.retryFailed}
          </Btn>
        )
      }
    >
      {R.summaryBody}
    </Alert>
  )

  const progress = running && (
    <div role="status" className="flex flex-col gap-1.5 rounded-[10px] bg-surface-2 px-4 py-3 text-[13px] font-semibold">
      <span className="flex items-center gap-2">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        {R.progress(running.done, running.total)}
      </span>
      <span className="h-1.5 overflow-hidden rounded-full bg-border">
        <span
          className="block h-full rounded-full bg-primary transition-[width]"
          style={{ width: `${(running.done / running.total) * 100}%` }}
        />
      </span>
    </div>
  )

  const lineBlocks = lines.map((line, index) => {
    const product = line.productId == null ? null : (productById.get(line.productId) ?? null)
    const pickerItems: PickerItem[] = [
      ...withRecipe.filter((p) => p.id === line.productId || !usedIds.has(p.id)),
      ...(product && !withRecipe.includes(product) ? [product] : []),
    ].map((p) => ({ id: p.id, name: p.name, pill: { text: R.stockPill(p.current_stock), tone: "neutral" } }))
    return (
      <LineBlock
        key={line.key}
        index={index + 1}
        line={line}
        product={product}
        entry={line.productId == null ? undefined : recipes[line.productId]}
        preview={previews.get(line.key) ?? null}
        pickerItems={pickerItems}
        locked={busy || !editable(line)}
        mobile={mobile}
        onChange={(patch) => {
          update(line.key, patch)
          setExpanded(line.key)
        }}
        onRemove={() => removeLine(line.key)}
        onGoRecipe={onGoRecipe}
      />
    )
  })

  const addButton = (
    <Btn variant="outline" className="self-start border-dashed" disabled={busy} onClick={addLine}>
      <Plus className="size-4" />
      {R.addProductLine}
    </Btn>
  )

  const footer = (
    <div className={cn("flex flex-col gap-2", !mobile && "border-t border-border px-5 py-4")}>
      {eligible.length > 0 && (
        <Collapsible label={R.runsTotal}>
          <div className="flex items-baseline justify-between gap-3 px-1 pt-1 text-[13.5px]">
            <span className="text-xs text-text-3">{R.runsTotalCaption}</span>
            <b className="tabular-nums">{formatMoney(runsTotal)}</b>
          </div>
        </Collapsible>
      )}
      {!mobile && (
        <div className="flex flex-wrap items-center gap-3">
          <Btn variant="primary" disabled={busy || eligible.length === 0} aria-busy={busy || undefined} onClick={() => run(eligible)}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
            {R.submitMany(eligible.length)}
          </Btn>
          <span className="text-xs text-text-3">{R.submitManyNote}</span>
        </div>
      )}
    </div>
  )

  if (mobile) {
    const retryMode = failed.length > 0 && eligible.every((l) => l.status.kind === "failed")
    return (
      <div className="flex flex-col gap-3 pb-24">
        <section className={cn(cardClass, "p-3.5")}>{dateField}</section>
        {progress}
        {summaryAlert}
        {lineBlocks}
        {addButton}
        {footer}
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
          {retryMode ? (
            <Btn variant="primary" size="lg" className="w-full" disabled={busy} onClick={() => run(failed)}>
              <RotateCw className="size-[18px]" />
              {R.retryFailed}
            </Btn>
          ) : (
            <Btn
              variant="primary"
              size="lg"
              className="w-full"
              disabled={busy || eligible.length === 0}
              aria-busy={busy || undefined}
              onClick={() => run(eligible)}
            >
              {busy ? <Loader2 className="size-[18px] animate-spin" /> : <Check className="size-[18px]" />}
              {busy && running ? R.progress(running.done, running.total) : R.submitMany(eligible.length)}
            </Btn>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-6">
      <section className={cn(cardClass, "w-[360px] shrink-0")} aria-labelledby="run-form-title">
        <div className="border-b border-border px-5 py-4">
          <h2 id="run-form-title" className="text-base font-bold text-heading">
            {R.formTitle}
          </h2>
        </div>
        <div className="flex flex-col gap-4 p-5">
          {dateField}
          <Help>{R.productHelp}</Help>
          <Help>{R.duplicateHint}</Help>
        </div>
      </section>
      <section className={cn(cardClass, "min-w-0 grow")} aria-labelledby="run-lines-title">
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex flex-col">
            <h2 id="run-lines-title" className="text-base font-bold text-heading">
              {R.linesTitle}
            </h2>
            <span className="text-xs text-text-3">{R.linesCaption}</span>
          </div>
          <Btn variant="link" className="text-[13px]" onClick={() => onGoRecipe(expandedLine?.productId ?? null)}>
            {R.editRecipe}
          </Btn>
        </div>
        <div className="flex flex-col gap-3 p-5">
          {progress}
          {summaryAlert}
          {lineBlocks}
          {addButton}
        </div>
        {footer}
      </section>
    </div>
  )
}

// ---------------------------------------------------------------- one line

function StatusPill({ status }: { status: LineStatus }) {
  switch (status.kind) {
    case "queued":
      return <span className={cn(badgeBase, "bg-surface-2 text-text-2")}>{R.statusQueued}</span>
    case "submitting":
      return (
        <span className={cn(badgeBase, "bg-info-soft text-info before:hidden")}>
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
          {R.statusSubmitting}
        </span>
      )
    case "success":
      return (
        <span className={cn(badgeBase, "bg-profit-soft text-profit before:hidden")}>
          <CircleCheck className="size-3.5" aria-hidden />
          {R.statusSuccessPlain}
        </span>
      )
    case "failed":
      return <span className={cn(badgeBase, "bg-loss-soft text-loss")}>{R.statusFailed}</span>
    default:
      return null
  }
}

function LineErrorView({ error, onGoRecipe, productId }: { error: LineError; onGoRecipe: (id: number) => void; productId: number }) {
  if (error.type === "short")
    return (
      <Alert tone="err" title={R.serverShortTitle}>
        {R.serverShortLine(error.name, error.needed, error.available, error.unit)}
      </Alert>
    )
  if (error.type === "noRecipe")
    return (
      <Alert
        tone="warn"
        title={R.noRecipeTitle}
        action={
          <Btn size="sm" onClick={() => onGoRecipe(productId)}>
            {R.makeRecipe}
          </Btn>
        }
      >
        {R.noRecipeBody}
      </Alert>
    )
  return <SaveError message={error.message} code={error.code} />
}

function LineBlock({
  index,
  line,
  product,
  entry,
  preview,
  pickerItems,
  locked,
  mobile,
  onChange,
  onRemove,
  onGoRecipe,
}: {
  index: number
  line: Line
  product: Product | null
  entry: RecipeEntry | undefined
  preview: ChainedPreview | null
  pickerItems: PickerItem[]
  locked: boolean
  mobile: boolean
  onChange: (patch: Partial<Line>) => void
  onRemove: () => void
  onGoRecipe: (productId: number | null) => void
}) {
  const short = !!preview && preview.short.length > 0
  const status = line.status
  const failed = status.kind === "failed"
  const avg = product && preview ? averageOf(product, line.qty, preview) : null

  const header = (
    <div className={cn("grid items-start gap-2", mobile ? "grid-cols-1" : "grid-cols-[minmax(0,1fr)_150px_minmax(0,0.8fr)_auto]")}>
      <div className="flex min-w-0 flex-col gap-1">
        <span className="sr-only">{R.lineLabel(index)}</span>
        <ItemPicker
          items={pickerItems}
          value={line.productId}
          onPick={(id) => onChange({ productId: id })}
          placeholder={R.pickProduct}
          searchLabel={R.searchProduct}
          emptyText={R.noProductsWithRecipe}
          noMatchText={R.noProductMatch}
          mobile={mobile}
          disabled={locked}
        />
      </div>
      <div className={cn(mobile && "grid grid-cols-[1fr_auto] items-center gap-2")}>
        <fieldset disabled={locked} className="min-w-0">
          <Stepper
            value={line.qty}
            onValue={(qty) => onChange({ qty })}
            tone={short || line.qty < 1 ? "error" : null}
            size={mobile ? "mobile" : "md"}
          />
        </fieldset>
        {mobile && (
          <Btn variant="ghost" size="sm" className="size-11 px-0" aria-label={R.removeLine} disabled={locked} onClick={onRemove}>
            <Trash2 className="size-4" />
          </Btn>
        )}
      </div>
      <input
        aria-label={R.noteShort}
        value={line.note}
        disabled={locked}
        onChange={(e) => onChange({ note: e.target.value })}
        placeholder={R.noteShort}
        className={cn(
          "w-full min-w-0 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30 disabled:opacity-60",
          mobile ? "h-11" : "h-10"
        )}
      />
      {!mobile && (
        <Btn variant="ghost" size="sm" className="size-10 px-0" aria-label={R.removeLine} disabled={locked} onClick={onRemove}>
          <Trash2 className="size-4" />
        </Btn>
      )}
    </div>
  )

  let body: React.ReactNode = null
  if (product && (entry == null || entry.status === "loading")) {
    body = (
      <p className="flex items-center gap-2 text-[13px] text-text-3">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        {R.recipeLoading}
      </p>
    )
  } else if (product && entry?.status === "missing") {
    body = (
      <Alert
        tone="warn"
        title={R.noRecipeTitle}
        action={
          <Btn size="sm" onClick={() => onGoRecipe(product.id)}>
            {R.makeRecipe}
          </Btn>
        }
      >
        {R.noRecipeBody}
      </Alert>
    )
  } else if (product && entry?.status === "failed") {
    body = <Alert tone="warn">{R.recipeFailed}</Alert>
  } else if (line.qty < 1) {
    body = <InlineMessage severity="error">{R.qtyMin}</InlineMessage>
  } else if (product && preview && avg) {
    const shortAlert = short && (
      <Alert
        tone="err"
        title={mobile ? R.shortTitleMobile : R.shortTitle}
        action={
          !mobile &&
          !locked && (
            <span className="flex shrink-0 flex-col gap-1.5">
              <Link href="/purchases" className={btnClass("outline", "sm")}>
                {R.buyMaterials}
              </Link>
              {preview.maxBuildable != null && preview.maxBuildable > 0 && (
                <Btn variant="ghost" size="sm" onClick={() => onChange({ qty: preview.maxBuildable! })}>
                  {R.produceMax(preview.maxBuildable)}
                </Btn>
              )}
            </span>
          )
        }
      >
        {`${preview.short.map((l) => R.shortLine(l.shortBy!, unitLabel(l.material_unit), l.material_name)).join(" ")}${
          preview.maxBuildable != null ? ` ${R.shortTail(preview.maxBuildable)}` : ""
        }`}
        {preview.shortByEarlier && <div className="mt-1 text-xs font-semibold">{R.shortByEarlier}</div>}
        {mobile && !locked && preview.maxBuildable != null && preview.maxBuildable > 0 && (
          <div className="mt-2 flex gap-2">
            <Btn size="sm" onClick={() => onChange({ qty: preview.maxBuildable! })}>
              {R.produceMax(preview.maxBuildable)}
            </Btn>
            <Link href="/purchases" className={btnClass("ghost", "sm")}>
              {R.buyMaterials}
            </Link>
          </div>
        )}
      </Alert>
    )
    body = (
      <>
        {shortAlert}
        {/* Blocking messages (the shortage above) stay outside; costs open on click. */}
        <Collapsible label={R.costDetails}>
          <p className="px-1 pb-1 text-[13px] tabular-nums">
            {R.collapsedSummary(preview.batchTotal, preview.unitCost)}
            {" · "}
            {R.collapsedAvg(avg.old == null ? R.avgNoCost : formatMoney(avg.old), avg.after)}
          </p>
          <div className="-mx-4 overflow-hidden border-t border-border">
            {mobile ? (
              <MobilePreview preview={preview} product={product} qty={line.qty} />
            ) : (
              <DesktopPreview preview={preview} product={product} qty={line.qty} />
            )}
          </div>
        </Collapsible>
      </>
    )
  }

  return (
    <section
      aria-label={product ? `${R.lineLabel(index)}: ${product.name}` : R.lineLabel(index)}
      className={cn(
        "flex flex-col gap-2.5 rounded-xl border border-border p-4",
        (failed || (short && status.kind === "draft")) && "border-loss-border bg-loss-soft/40",
        status.kind === "success" && "border-profit/40 bg-profit-soft/40"
      )}
    >
      {status.kind !== "draft" && (
        <div className="flex justify-end">
          <StatusPill status={status} />
        </div>
      )}
      {header}
      {failed && product && <LineErrorView error={status.error} onGoRecipe={onGoRecipe} productId={product.id} />}
      {/* A no-recipe failure already shows the no-recipe block as its error. */}
      {status.kind !== "success" && !(failed && status.error.type === "noRecipe") && body}
      {status.kind === "success" && (
        <Collapsible label={R.costDetails}>
          <p className="px-1 text-[13px] tabular-nums">{R.successUnitCost(status.unitCost)}</p>
        </Collapsible>
      )}
    </section>
  )
}

/** The product's weighted average before → after (formulas.md §3 via blendUnitCost). */
function averageOf(product: Product, qty: number, preview: BatchPreview) {
  const after = blendUnitCost(product.current_stock, product.unit_cost, qty, preview.batchTotal)
  const old = product.unit_cost
  const blended = old != null && product.current_stock > 0
  return {
    old,
    after,
    delta: old != null ? after - old : null,
    derivation: blended
      ? R.avgFormula(product.current_stock, old, preview.batchTotal, product.current_stock + qty)
      : old == null
        ? R.avgFirstCost
        : R.avgNoStock,
  }
}

function DeltaBadge({ delta }: { delta: number }) {
  return (
    <span className={cn(badgeBase, "tabular-nums", delta < 0 ? "bg-profit-soft text-profit" : "bg-warn-soft text-warn")}>
      {delta >= 0 ? "+" : ""}
      {formatMoney(delta)}
    </span>
  )
}

function DesktopPreview({ preview, product, qty }: { preview: BatchPreview; product: Product; qty: number }) {
  const avg = averageOf(product, qty, preview)
  return (
    <>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[13.5px]">
          <thead>
            <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
              <th scope="col" className="w-full">
                {R.colMaterial}
              </th>
              <th scope="col">{R.colBasis}</th>
              <th scope="col" className="text-end!">
                {R.colNeed}
              </th>
              <th scope="col" className="text-end!">
                {R.colStock}
              </th>
              <th scope="col" className="text-end!">
                {R.colAfter}
              </th>
              <th scope="col" className="text-end!">
                {R.colCost}
              </th>
            </tr>
          </thead>
          <tbody>
            {preview.lines.map((l) => {
              const unit = unitLabel(l.material_unit)
              const isShort = l.shortBy != null
              return (
                <tr
                  key={l.material_id}
                  className={cn(
                    "[&>td]:h-[48px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap",
                    isShort && "[&>td]:bg-loss-soft"
                  )}
                >
                  <td className="font-bold">{l.material_name}</td>
                  <td>
                    <BasisMark perBatch={l.perBatch} />
                  </td>
                  <td className="text-end tabular-nums">
                    {formatQuantity(l.need)} {unit}
                  </td>
                  <td className="text-end text-text-3 tabular-nums">{l.stock == null ? R.service : formatQuantity(l.stock)}</td>
                  <td className={cn("text-end tabular-nums", isShort && "font-bold text-loss")}>
                    {l.stock == null ? "—" : isShort ? R.shortCell(l.shortBy!) : formatQuantity(l.after!)}
                  </td>
                  <td className="text-end font-bold">
                    <Money value={Math.round(l.cost)} />
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="font-bold [&>td]:h-11 [&>td]:bg-surface-2 [&>td]:px-4">
              <td colSpan={5}>{R.totalLabel}</td>
              <td className="text-end">
                <Money value={preview.batchTotal} />
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div className="grid grid-cols-3 gap-3 border-t border-border px-5 py-4">
        <div className="flex flex-col gap-1 rounded-[10px] bg-surface-2 p-3">
          <span className="text-xs text-text-3">{R.unitTile}</span>
          <span className="text-xl font-bold tabular-nums">{formatMoney(preview.unitCost)}</span>
          <span className="text-xs text-text-3">{R.unitTileDerivation(qty)}</span>
        </div>
        <div className="col-span-2 flex flex-col gap-1 rounded-[10px] bg-surface-2 p-3">
          <span className="text-xs text-text-3">{R.avgTile(product.name)}</span>
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-lg text-text-2 tabular-nums">{avg.old == null ? R.avgNoCost : formatMoney(avg.old)}</span>
            {/* Old → new in reading order: in RTL the chevron points left. */}
            <ChevronLeft className="size-[18px] text-text-3" aria-hidden />
            <Money value={avg.after} className="text-[22px] font-bold" />
            {avg.delta != null && <DeltaBadge delta={avg.delta} />}
          </span>
          <span className="text-xs text-text-3 tabular-nums">{avg.derivation}</span>
        </div>
      </div>
      <p className="px-5 pb-3 text-xs text-text-3">{R.previewNote}</p>
    </>
  )
}

function BasisMark({ perBatch }: { perBatch: boolean }) {
  return perBatch ? (
    <span className={cn(badgeBase, "bg-violet-soft text-violet")}>{R.perBatch}</span>
  ) : (
    <span className="inline-flex h-6 items-center rounded-md bg-surface-2 px-2 text-xs text-text-2">{R.perUnit}</span>
  )
}

function MobilePreview({ preview, product, qty }: { preview: BatchPreview; product: Product; qty: number }) {
  const avg = averageOf(product, qty, preview)
  return (
    <>
      <h3 className="px-3.5 pt-3.5 pb-2 text-sm font-bold text-heading">{R.mobileSection}</h3>
      {preview.lines.map((l) => {
        const unit = unitLabel(l.material_unit)
        const isShort = l.shortBy != null
        return (
          <div
            key={l.material_id}
            className={cn("flex items-center justify-between gap-3 border-t border-border px-3.5 py-2.5", isShort && "bg-loss-soft")}
          >
            <span className="flex min-w-0 flex-col">
              <span className="text-[13px] font-bold">{l.material_name}</span>
              <span className="text-xs text-text-3">
                {l.perBatch
                  ? R.perBatch
                  : R.mobileLineNeed(R.perUnit, `${formatQuantity(l.need)}`, l.stock == null ? null : formatQuantity(l.stock))}
              </span>
            </span>
            {isShort ? (
              <span className="shrink-0 text-xs font-bold text-loss">{R.shortCell(l.shortBy!)}</span>
            ) : (
              <span className="shrink-0 text-sm">
                <Money value={Math.round(l.cost)} />
                <span className="sr-only"> {unit}</span>
              </span>
            )}
          </div>
        )
      })}
      <div className="flex flex-col gap-1 border-t border-border px-3.5 py-3 text-[13px]">
        <span className="flex justify-between">
          <span className="text-text-2">{R.mobileTotal}</span>
          <b>
            <Money value={preview.batchTotal} />
          </b>
        </span>
        <span className="flex justify-between">
          <span className="text-text-2">{R.mobileUnit}</span>
          <b>
            <Money value={preview.unitCost} />
          </b>
        </span>
        <span className="flex justify-between">
          <span className="text-text-2">{R.mobileAvg}</span>
          <b className="tabular-nums">
            {avg.old == null ? R.avgNoCost : formatMoney(avg.old)} ← {formatMoney(avg.after)}
          </b>
        </span>
        <span className="pt-1 text-xs text-text-3">{R.previewNote}</span>
      </div>
    </>
  )
}
