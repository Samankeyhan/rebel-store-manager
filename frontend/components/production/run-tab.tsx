"use client"

import * as React from "react"
import Link from "next/link"
import { Check, ChevronLeft, Loader2 } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { ItemPicker, type PickerItem } from "@/components/common/item-picker"
import { badgeBase } from "@/components/common/status"
import { Alert, Btn, Help, InlineMessage, Label, Stepper, btnClass, cardClass } from "@/components/record-sale/primitives"
import { SaveError } from "@/components/products/drawer-shell"
import { unitLabel } from "@/components/products/figures"
import { ApiError, runProduction, type Material, type Product } from "@/lib/api"
import { batchPreview, blendUnitCost, type BatchPreview } from "@/lib/costing"
import { formatMoney, formatNumber, formatQuantity } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { R } from "./copy"
import type { RecipeEntry } from "./use-production-data"

type ServerShort = { name: string; needed: number; available: number; unit: string }

export function RunTab({
  products,
  materials,
  recipes,
  productId,
  onProductChange,
  today,
  mobile,
  onGoRecipe,
  onRan,
  markMissing,
  refreshMaterials,
}: {
  products: Product[]
  materials: Material[]
  recipes: Record<number, RecipeEntry>
  productId: number | null
  onProductChange: (id: number) => void
  today: string
  mobile: boolean
  onGoRecipe: (productId: number | null) => void
  /** Called after a successful run with the toast text; refreshes the data. */
  onRan: (productId: number, toast: string) => Promise<void>
  markMissing: (productId: number) => void
  refreshMaterials: () => Promise<void>
}) {
  const [qty, setQty] = React.useState(1)
  const [date, setDate] = React.useState(today)
  const [note, setNote] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const [serverShort, setServerShort] = React.useState<ServerShort | null>(null)

  const active = products.filter((p) => p.is_active === 1)
  const withRecipe = active.filter((p) => recipes[p.id]?.status === "ok")
  const product = active.find((p) => p.id === productId) ?? null
  const entry = product ? recipes[product.id] : undefined

  // A product picked elsewhere (URL / recipe tab) without a recipe stays listed
  // so the "no recipe" block can explain why it can't be produced.
  const pickerItems: PickerItem[] = [...withRecipe, ...(product && !withRecipe.includes(product) ? [product] : [])].map(
    (p) => ({ id: p.id, name: p.name, pill: { text: R.stockPill(p.current_stock), tone: "neutral" } })
  )

  const stockById = React.useMemo(() => new Map(materials.map((m) => [m.id, m.current_stock])), [materials])
  const preview: BatchPreview | null =
    entry?.status === "ok" && qty >= 1 ? batchPreview(entry.recipe.items, qty, (id) => stockById.get(id) ?? null) : null
  const short = !!preview && preview.short.length > 0
  const canSubmit = !!product && entry?.status !== "missing" && entry?.status !== "loading" && qty >= 1 && !short && !busy

  const pickProduct = (id: number) => {
    onProductChange(id)
    setError(null)
    setServerShort(null)
  }

  const submit = async () => {
    if (!product || !canSubmit) return
    setBusy(true)
    setError(null)
    setServerShort(null)
    try {
      const res = await runProduction({
        product_id: product.id,
        quantity_produced: qty,
        // Today: let the server stamp the current time. Another day: that day.
        production_date: date === today ? null : date,
        notes: note.trim() || null,
      })
      await onRan(product.id, R.toastRun(qty, product.name, res.batch.unit_cost))
      setQty(1)
      setNote("")
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.type === "InsufficientStockError") {
        const name = String(e.details.item_name ?? "")
        const line = entry?.status === "ok" ? entry.recipe.items.find((i) => i.material_name === name) : undefined
        setServerShort({
          name,
          needed: Number(e.details.needed ?? 0),
          available: Number(e.details.available ?? 0),
          unit: unitLabel(line?.material_unit ?? ""),
        })
        refreshMaterials().catch(() => {})
      } else if (e instanceof ApiError && e.status === 422 && /no recipe/i.test(e.message)) {
        // The API is the final authority: the recipe went away since it loaded.
        markMissing(product.id)
      } else {
        setError(
          e instanceof ApiError
            ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `PRODUCTION_${e.status}` }
            : { message: String(e), code: "UNKNOWN" }
        )
      }
    } finally {
      setBusy(false)
    }
  }

  const form = (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-4")}>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="run-product">{R.fieldProduct}</Label>
        <ItemPicker
          id="run-product"
          items={pickerItems}
          value={productId}
          onPick={pickProduct}
          placeholder={R.pickProduct}
          searchLabel={R.searchProduct}
          emptyText={R.noProductsWithRecipe}
          noMatchText={R.noProductMatch}
          mobile={mobile}
        />
        {!mobile && <Help>{R.productHelp}</Help>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>{R.fieldQty}</Label>
        <div className={mobile ? "w-full" : "w-40"}>
          <Stepper value={qty} onValue={setQty} tone={short || qty < 1 ? "error" : null} size={mobile ? "mobile" : "md"} />
        </div>
        {qty < 1 ? (
          <InlineMessage severity="error">{R.qtyMin}</InlineMessage>
        ) : (
          preview && (
            <Help>
              {preview.maxBuildable == null ? (
                R.qtyHelpUnbounded
              ) : (
                <>
                  {R.qtyHelpMaxPrefix}
                  <b className="tabular-nums">{formatNumber(preview.maxBuildable)}</b>
                </>
              )}
            </Help>
          )
        )}
      </div>
      <div className={cn(mobile && "grid grid-cols-2 gap-2")}>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="run-date">{R.fieldDate}</Label>
          <DateField id="run-date" value={date} today={today} onChange={setDate} todayLabel={R.today} mobile={mobile} />
        </div>
        {mobile && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="run-note">{R.fieldNote}</Label>
            <input
              id="run-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={R.notePlaceholder}
              className="h-12 w-full min-w-0 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30"
            />
          </div>
        )}
      </div>
      {!mobile && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="run-note" optional>
            {R.fieldNote}
          </Label>
          <input
            id="run-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={R.notePlaceholder}
            className="h-10 w-full min-w-0 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30"
          />
        </div>
      )}
    </div>
  )

  const alerts = (
    <>
      {error && <SaveError {...error} />}
      {serverShort && (
        <Alert tone="err" title={R.serverShortTitle}>
          {R.serverShortLine(serverShort.name, serverShort.needed, serverShort.available, serverShort.unit)}
        </Alert>
      )}
      {preview && short && (
        <Alert
          tone="err"
          title={mobile ? R.shortTitleMobile : R.shortTitle}
          action={
            !mobile && (
              <span className="flex shrink-0 flex-col gap-1.5">
                <Link href="/purchases" className={btnClass("outline", "sm")}>
                  {R.buyMaterials}
                </Link>
                {preview.maxBuildable != null && preview.maxBuildable > 0 && (
                  <Btn variant="ghost" size="sm" onClick={() => setQty(preview.maxBuildable!)}>
                    {R.produceMax(preview.maxBuildable)}
                  </Btn>
                )}
              </span>
            )
          }
        >
          {mobile
            ? `${R.shortLine(preview.short[0].shortBy!, unitLabel(preview.short[0].material_unit), preview.short[0].material_name)}${
                preview.maxBuildable != null ? ` ${R.shortTailMobile(preview.maxBuildable)}` : ""
              }`
            : `${preview.short.map((l) => R.shortLine(l.shortBy!, unitLabel(l.material_unit), l.material_name)).join(" ")}${
                preview.maxBuildable != null ? ` ${R.shortTail(preview.maxBuildable)}` : ""
              }`}
          {mobile && preview.maxBuildable != null && preview.maxBuildable > 0 && (
            <div className="mt-2 flex gap-2">
              <Btn size="sm" onClick={() => setQty(preview.maxBuildable!)}>
                {R.produceMax(preview.maxBuildable)}
              </Btn>
              <Link href="/purchases" className={btnClass("ghost", "sm")}>
                {R.buyMaterials}
              </Link>
            </div>
          )}
        </Alert>
      )}
    </>
  )

  const body = !product ? (
    <p className="px-5 py-10 text-center text-[13px] text-text-3">{R.pickToPreview}</p>
  ) : entry?.status === "loading" || entry == null ? (
    <p className="flex items-center justify-center gap-2 px-5 py-10 text-[13px] text-text-3">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {R.recipeLoading}
    </p>
  ) : entry.status === "missing" ? (
    <div className="p-5">
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
    </div>
  ) : entry.status === "failed" ? (
    <div className="p-5">
      <Alert tone="warn">{R.recipeFailed}</Alert>
    </div>
  ) : preview ? (
    mobile ? (
      <MobilePreview preview={preview} product={product} qty={qty} />
    ) : (
      <DesktopPreview preview={preview} product={product} qty={qty} />
    )
  ) : null

  const submitLabel = R.submit(Math.max(qty, 0))

  if (mobile) {
    return (
      <div className="flex flex-col gap-3 pb-24">
        <section className={cn(cardClass, "p-3.5")}>{form}</section>
        {alerts}
        {product && <section className={cn(cardClass, "overflow-hidden")}>{body}</section>}
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
          <Btn variant="primary" size="lg" className="w-full" disabled={!canSubmit} aria-busy={busy || undefined} onClick={submit}>
            {busy ? <Loader2 className="size-[18px] animate-spin" /> : <Check className="size-[18px]" />}
            {submitLabel}
          </Btn>
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
        <div className="p-5">{form}</div>
      </section>
      <section className={cn(cardClass, "min-w-0 grow overflow-hidden")} aria-labelledby="run-preview-title">
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex flex-col">
            <h2 id="run-preview-title" className="text-base font-bold text-heading">
              {R.previewTitle}
            </h2>
            {product && entry?.status === "ok" && (
              <span className="text-xs text-text-3">{R.previewCaption(Math.max(qty, 0), product.name)}</span>
            )}
          </div>
          <Btn variant="link" className="text-[13px]" onClick={() => onGoRecipe(product?.id ?? null)}>
            {R.editRecipe}
          </Btn>
        </div>
        {(error || serverShort || short) && <div className="flex flex-col gap-3 px-5 pt-4">{alerts}</div>}
        {body}
        {product && entry?.status === "ok" && (
          <div className="flex items-center gap-3 px-5 pb-5">
            <Btn variant="primary" disabled={!canSubmit} aria-busy={busy || undefined} onClick={submit}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
              {submitLabel}
            </Btn>
            <span className="text-xs text-text-3">{R.submitNote(Math.max(qty, 0))}</span>
          </div>
        )}
      </section>
    </div>
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
      {formatNumber(delta)}
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
                  <td className="text-end font-bold tabular-nums">{formatNumber(Math.round(l.cost))}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="font-bold [&>td]:h-11 [&>td]:bg-surface-2 [&>td]:px-4">
              <td colSpan={5}>{R.totalLabel}</td>
              <td className="text-end tabular-nums">{formatNumber(preview.batchTotal)}</td>
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
            <span className="text-lg text-text-2 tabular-nums">{avg.old == null ? R.avgNoCost : formatNumber(avg.old)}</span>
            {/* Old → new in reading order: in RTL the chevron points left. */}
            <ChevronLeft className="size-[18px] text-text-3" aria-hidden />
            <span className="text-[22px] font-bold tabular-nums">{formatNumber(avg.after)}</span>
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
              <span className="shrink-0 text-sm tabular-nums">
                {formatNumber(Math.round(l.cost))}
                <span className="sr-only"> {unit}</span>
              </span>
            )}
          </div>
        )
      })}
      <div className="flex flex-col gap-1 border-t border-border px-3.5 py-3 text-[13px]">
        <span className="flex justify-between">
          <span className="text-text-2">{R.mobileTotal}</span>
          <b className="tabular-nums">{formatNumber(preview.batchTotal)}</b>
        </span>
        <span className="flex justify-between">
          <span className="text-text-2">{R.mobileUnit}</span>
          <b className="tabular-nums">{formatNumber(preview.unitCost)}</b>
        </span>
        <span className="flex justify-between">
          <span className="text-text-2">{R.mobileAvg}</span>
          <b className="tabular-nums">
            {avg.old == null ? R.avgNoCost : formatNumber(avg.old)} ← {formatNumber(avg.after)}
          </b>
        </span>
        <span className="pt-1 text-xs text-text-3">{R.previewNote}</span>
      </div>
    </>
  )
}
