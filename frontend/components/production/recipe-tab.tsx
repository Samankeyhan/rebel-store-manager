"use client"

import * as React from "react"
import { Info, Loader2, Plus, Trash2 } from "lucide-react"
import { Collapsible } from "@/components/common/collapsible"
import { ItemPicker, type PickerItem } from "@/components/common/item-picker"
import { Segment } from "@/components/common/segment"
import { badgeBase } from "@/components/common/status"
import { Alert, Btn, InlineMessage, cardClass } from "@/components/record-sale/primitives"
import { unitLabel } from "@/components/products/figures"
import {
  ApiError,
  addRecipeItem,
  removeRecipeItem,
  updateRecipeItem,
  type Material,
  type Product,
  type Recipe,
} from "@/lib/api"
import { batchPreview, recipeSums } from "@/lib/costing"
import { formatQuantity, parseDecimal } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { cn } from "@/lib/utils"
import { R } from "./copy"
import type { RecipeEntry } from "./use-production-data"

type Basis = "PER_UNIT" | "PER_BATCH"

function without<V>(record: Record<number, V>, key: number): Record<number, V> {
  const next = { ...record }
  delete next[key]
  return next
}
type Item = Recipe["items"][number]

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 409) return R.duplicateLine
    if (e.status === 422 && (e.field === "quantity_needed" || /quantity/i.test(e.message))) return R.qtyInvalid
    return e.message
  }
  return String(e)
}

function listCaption(entry: RecipeEntry | undefined): React.ReactNode {
  if (!entry || entry.status === "loading") return <Loader2 className="size-3.5 animate-spin text-text-3" aria-hidden />
  if (entry.status === "ok") return <span className="text-xs text-text-3">{R.itemCount(entry.recipe.items.length)}</span>
  if (entry.status === "missing") return <span className={cn(badgeBase, "bg-surface-2 text-text-2")}>{R.noRecipeBadge}</span>
  return <span className="text-xs text-text-3">—</span>
}

/**
 * Recipe editor (design 06 «دستور تولید»). The API saves one line at a time
 * (POST / PATCH / DELETE /products/{id}/recipe/items), each returning the
 * whole recipe — so every change saves on its own and there is no
 * «ذخیره دستور» button.
 */
export function RecipeTab({
  products,
  materials,
  recipes,
  productId,
  onProductChange,
  setRecipe,
  mobile,
}: {
  products: Product[]
  materials: Material[]
  recipes: Record<number, RecipeEntry>
  productId: number | null
  onProductChange: (id: number) => void
  setRecipe: (productId: number, recipe: Recipe) => void
  mobile: boolean
}) {
  const active = products.filter((p) => p.is_active === 1)
  const product = active.find((p) => p.id === productId) ?? active[0] ?? null
  const entry = product ? recipes[product.id] : undefined
  const items: Item[] = entry?.status === "ok" ? entry.recipe.items : []

  const [drafts, setDrafts] = React.useState<Record<number, string>>({})
  const [busy, setBusy] = React.useState<Set<number | "add">>(new Set())
  const [rowErrors, setRowErrors] = React.useState<Record<number, string>>({})
  const [addError, setAddError] = React.useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = React.useState<number | null>(null)

  // Per-product edit state resets when the product changes.
  const [shownFor, setShownFor] = React.useState<number | null>(null)
  if ((product?.id ?? null) !== shownFor) {
    setShownFor(product?.id ?? null)
    setDrafts({})
    setRowErrors({})
    setAddError(null)
    setConfirmDelete(null)
  }

  const run = async (key: number | "add", call: () => Promise<Recipe>): Promise<boolean> => {
    if (!product) return false
    setBusy((b) => new Set(b).add(key))
    try {
      setRecipe(product.id, await call())
      if (key === "add") setAddError(null)
      else setRowErrors((r) => without(r, key))
      return true
    } catch (e) {
      if (key === "add") setAddError(errorText(e))
      else setRowErrors((r) => ({ ...r, [key]: errorText(e) }))
      return false
    } finally {
      setBusy((b) => {
        const next = new Set(b)
        next.delete(key)
        return next
      })
    }
  }

  const saveQty = async (item: Item) => {
    const text = drafts[item.material_id]
    if (text == null) return
    const q = parseDecimal(text)
    if (q == null || q <= 0) {
      setRowErrors((r) => ({ ...r, [item.material_id]: R.qtyInvalid }))
      return
    }
    if (q === item.quantity_needed) {
      setDrafts((d) => without(d, item.material_id))
      setRowErrors((r) => without(r, item.material_id))
      return
    }
    const ok = await run(item.material_id, () =>
      updateRecipeItem(product!.id, item.material_id, { quantity_needed: q })
    )
    if (ok) setDrafts((d) => without(d, item.material_id))
  }

  const setBasis = (item: Item, basis: Basis) => {
    if (basis === item.cost_basis) return
    run(item.material_id, () =>
      updateRecipeItem(product!.id, item.material_id, { quantity_needed: item.quantity_needed, cost_basis: basis })
    )
  }

  const remove = (item: Item) => {
    // Removing a made-to-order product's last line leaves it unsellable; the
    // backend allows it, so warn first rather than block.
    if (items.length === 1 && product?.made_to_order === 1 && confirmDelete !== item.material_id) {
      setConfirmDelete(item.material_id)
      return
    }
    setConfirmDelete(null)
    run(item.material_id, () => removeRecipeItem(product!.id, item.material_id))
  }

  const used = new Set(items.map((i) => i.material_id))
  const addable: PickerItem[] = materials
    .filter((m) => m.is_active === 1 && !used.has(m.id))
    .sort((a, b) => a.name.localeCompare(b.name, "fa"))
    .map((m) => ({
      id: m.id,
      name: m.name,
      // Stock only — never costs — in the picker.
      sub: m.type === "SERVICE" || m.current_stock == null ? R.service : R.materialStock(formatQuantity(m.current_stock), unitLabel(m.unit)),
    }))
  const materialById = new Map(materials.map((m) => [m.id, m]))

  const sums = recipeSums(items)
  const at30 = items.length ? batchPreview(items, 30, () => null).unitCost : 0
  const at100 = items.length ? batchPreview(items, 100, () => null).unitCost : 0

  if (!product) {
    return <p className={cn(cardClass, "px-5 py-10 text-center text-[13px] text-text-3")}>{R.noProducts}</p>
  }

  const productItems: PickerItem[] = active.map((p) => {
    const e = recipes[p.id]
    return {
      id: p.id,
      name: p.name,
      sub: e?.status === "ok" ? R.itemCount(e.recipe.items.length) : e?.status === "missing" ? R.noRecipeBadge : undefined,
    }
  })

  const list = (
    <nav aria-label={R.listLabel} className={cn(cardClass, "w-[280px] shrink-0 p-2")}>
      <div className="px-2.5 pt-1 pb-2 text-xs font-semibold text-text-3">{R.listLabel}</div>
      <ul className="flex flex-col">
        {active.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              aria-current={p.id === product.id ? "true" : undefined}
              onClick={() => onProductChange(p.id)}
              className={cn(
                "flex h-11 w-full cursor-pointer items-center justify-between gap-2 rounded-lg px-2.5 text-start text-[13.5px] outline-none hover:bg-surface-2 focus-visible:ring-3 focus-visible:ring-ring/30",
                p.id === product.id && "bg-red-soft font-bold hover:bg-red-soft"
              )}
            >
              <span className="min-w-0 truncate">{p.name}</span>
              {listCaption(recipes[p.id])}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )

  const rowGrid = "grid grid-cols-[minmax(0,1fr)_110px_290px_130px_36px] items-center gap-3"

  const editor = (
    <section className={cn(cardClass, "min-w-0 grow")} aria-labelledby="recipe-title">
      <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex flex-col">
          <h2 id="recipe-title" className="text-base font-bold text-heading">
            {R.editorTitle(product.name)}
          </h2>
          <span className="text-xs text-text-3">{R.editorCaption}</span>
        </div>
      </div>
      <Collapsible key={product.id} label={R.recipeDetails} className={mobile ? "px-3.5 py-2" : "px-5 py-3"}>
        <div className={cn("flex flex-col pt-2", mobile ? "gap-3" : "gap-3.5")}>
          <div role="note" className="flex items-start gap-3 rounded-[10px] bg-info-soft px-4 py-3 text-[13px] leading-[22px]">
            <Info className="mt-0.5 size-[18px] shrink-0 text-info" aria-hidden />
            <div>
              <div className="mb-0.5 font-bold">{R.explainTitle}</div>
              <b>{R.explainPerUnit}</b>
              {R.explainPerUnitBody}
              <b>{R.explainPerBatch}</b>
              {R.explainPerBatchBody}
            </div>
          </div>

          {entry?.status === "loading" && (
            <p className="flex items-center justify-center gap-2 py-6 text-[13px] text-text-3">
              <Loader2 className="size-4 animate-spin" aria-hidden />
              {R.recipeLoading}
            </p>
          )}
          {entry?.status === "failed" && <Alert tone="warn">{R.recipeFailed}</Alert>}
          {entry?.status === "missing" && <p className="py-2 text-[13px] text-text-3">{R.emptyRecipe}</p>}

          {items.length > 0 && !mobile && (
            <div className={cn(rowGrid, "text-xs font-semibold text-text-3")}>
              <span>{R.colLineMaterial}</span>
              <span>{R.colLineQty}</span>
              <span>{R.colLineBasis}</span>
              <span>{R.colLineCost}</span>
              <span />
            </div>
          )}

          {items.map((item) => {
            const service = item.material_type === "SERVICE"
            const unit = unitLabel(item.material_unit)
            const rowBusy = busy.has(item.material_id)
            const inactive = materialById.get(item.material_id)?.is_active === 0
            const qtyInput = (
              <div className="relative flex items-center">
                <input
                  inputMode="decimal"
                  aria-label={`${R.colLineQty} — ${item.material_name}`}
                  value={drafts[item.material_id] ?? formatQuantity(item.quantity_needed)}
                  disabled={rowBusy}
                  onChange={(e) => setDrafts((d) => ({ ...d, [item.material_id]: e.target.value }))}
                  onBlur={() => saveQty(item)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") e.currentTarget.blur()
                  }}
                  onFocus={(e) => e.currentTarget.select()}
                  className={cn(
                    "w-full min-w-0 rounded-lg border border-border-strong bg-card ps-3 pe-12 text-sm tabular-nums outline-none focus:border-heading focus:ring-3 focus:ring-ring/30",
                    mobile ? "h-11" : "h-10",
                    rowErrors[item.material_id] && "border-loss"
                  )}
                />
                <span className="pointer-events-none absolute end-3 text-xs text-text-3">{unit}</span>
              </div>
            )
            const basis = (
              <Segment<Basis>
                value={item.cost_basis as Basis}
                options={[
                  ["PER_UNIT", R.perUnit],
                  ["PER_BATCH", R.perBatch],
                ]}
                onChange={(b) => setBasis(item, b)}
                label={`${R.colLineBasis} — ${item.material_name}`}
                mobile={mobile}
                className="[&_button]:text-[12.5px]"
              />
            )
            const cost = (
              <span className="text-[13px] font-bold tabular-nums">
                {item.cost_basis === "PER_BATCH"
                  ? R.lineCostOnce(Math.round(item.quantity_needed * item.material_unit_cost))
                  : R.lineCostPerUnit(Math.round(item.quantity_needed * item.material_unit_cost))}
              </span>
            )
            const del = (
              <Btn
                variant="ghost"
                size="sm"
                className="size-8 px-0"
                aria-label={`${R.deleteLine} — ${item.material_name}`}
                disabled={rowBusy}
                onClick={() => remove(item)}
              >
                {rowBusy ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              </Btn>
            )
            const name = (
              <span className="flex min-w-0 flex-col">
                <span className="flex items-center gap-1.5 truncate text-[13.5px] font-bold">
                  {item.material_name}
                  {inactive && <span className={cn(badgeBase, "bg-surface-2 text-text-3")}>{R.inactiveMaterial}</span>}
                </span>
                <span className="truncate text-xs text-text-3">{R.lineSub(service, item.material_unit_cost, unit)}</span>
              </span>
            )
            return (
              <div key={item.material_id} className="flex flex-col gap-1.5">
                {mobile ? (
                  <div className="flex flex-col gap-2 rounded-[10px] border border-border p-3">
                    <div className="flex items-start justify-between gap-2">
                      {name}
                      {del}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {qtyInput}
                      <div className="flex items-center justify-end">{cost}</div>
                    </div>
                    {basis}
                  </div>
                ) : (
                  <div className={rowGrid}>
                    {name}
                    {qtyInput}
                    {basis}
                    {cost}
                    {del}
                  </div>
                )}
                {rowErrors[item.material_id] && (
                  <InlineMessage severity="error">{rowErrors[item.material_id]}</InlineMessage>
                )}
                {confirmDelete === item.material_id && (
                  <Alert
                    tone="warn"
                    title={R.lastLineWarnTitle}
                    action={
                      <span className="flex shrink-0 gap-2">
                        <Btn size="sm" className="border-loss-border text-loss" onClick={() => remove(item)}>
                          {R.lastLineConfirm}
                        </Btn>
                        <Btn variant="ghost" size="sm" onClick={() => setConfirmDelete(null)}>
                          {R.cancel}
                        </Btn>
                      </span>
                    }
                  >
                    {R.lastLineWarn}
                  </Alert>
                )}
              </div>
            )
          })}

          {entry?.status !== "loading" && (
            <div className="flex flex-col gap-1.5">
              <div className={mobile ? "w-full" : "w-[320px]"}>
                <AddLine
                  items={addable}
                  busy={busy.has("add")}
                  mobile={mobile}
                  onPick={(materialId) =>
                    run("add", () =>
                      addRecipeItem(product.id, { material_id: materialId, quantity_needed: 1, cost_basis: "PER_UNIT" })
                    )
                  }
                />
              </div>
              {addError && <InlineMessage severity="error">{addError}</InlineMessage>}
            </div>
          )}

          {items.length > 0 && (
            <>
              <div className="h-px bg-border" />
              <div className={cn("grid gap-3", mobile ? "grid-cols-1" : "grid-cols-3")}>
                <Tile caption={R.tilePerUnit} value={formatMoney(sums.perUnit)} />
                <Tile caption={R.tilePerBatch} value={formatMoney(sums.perBatch)} />
                <Tile caption={R.tileAt} value={`${formatMoney(at30)} / ${formatMoney(at100)}`} />
              </div>
            </>
          )}
        </div>
      </Collapsible>
    </section>
  )

  if (mobile) {
    return (
      <div className="flex flex-col gap-3">
        <ItemPicker
          items={productItems}
          value={product.id}
          onPick={onProductChange}
          placeholder={R.pickProduct}
          searchLabel={R.searchProduct}
          emptyText={R.noProducts}
          noMatchText={R.noProductMatch}
          mobile
        />
        {editor}
      </div>
    )
  }
  return (
    <div className="flex items-start gap-6">
      {list}
      {editor}
    </div>
  )
}

function Tile({ caption, value }: { caption: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-[10px] bg-surface-2 p-3">
      <span className="text-xs text-text-3">{caption}</span>
      <span className="font-bold tabular-nums">{value}</span>
    </div>
  )
}

/** «افزودن متریال یا خدمت»: a picker styled as a dashed add button; picking adds the line (qty 1, per unit). */
function AddLine({
  items,
  busy,
  mobile,
  onPick,
}: {
  items: PickerItem[]
  busy: boolean
  mobile: boolean
  onPick: (materialId: number) => void
}) {
  return (
    <div className="relative [&>button]:border-dashed">
      <ItemPicker
        items={items}
        value={null}
        onPick={onPick}
        placeholder={R.addLine}
        searchLabel={R.searchMaterial}
        emptyText={R.noMaterialsLeft}
        noMatchText={R.noMaterialMatch}
        mobile={mobile}
        disabled={busy}
      />
      <span className="pointer-events-none absolute end-9 top-1/2 -translate-y-1/2 text-text-3">
        {busy ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
      </span>
    </div>
  )
}
