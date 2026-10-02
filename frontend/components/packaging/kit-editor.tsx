"use client"

import * as React from "react"
import Link from "next/link"
import { Ban, Loader2, Plus, RotateCcw, Trash2 } from "lucide-react"
import { ItemPicker, type PickerItem } from "@/components/common/item-picker"
import { ChannelBadge } from "@/components/common/status"
import { unitLabel } from "@/components/products/figures"
import { Btn, InlineMessage, cardClass } from "@/components/record-sale/primitives"
import {
  ApiError,
  addKitItem,
  reactivateKit,
  removeKitItem,
  updateKitItem,
  type KitDetail,
  type Material,
} from "@/lib/api"
import { formatNumber, formatQuantity, parseDecimal } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { K } from "./copy"
import { LOW_KITS, kitAvailability } from "./figures"

type Item = KitDetail["items"][number]

function without<V>(record: Record<number, V>, key: number): Record<number, V> {
  const next = { ...record }
  delete next[key]
  return next
}

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 409) return K.duplicate
    if (e.status === 422 && e.field === "quantity") return K.qtyInvalid
    return e.message
  }
  return String(e)
}

/**
 * One kit: its lines (each change saves on its own — the API writes a line at
 * a time and returns the whole kit), and the three tiles. kit_cost is the
 * API's; the per-line cost is shown for that line only.
 */
export function KitEditor({
  kit,
  materials,
  defaultChannels,
  mobile,
  onSaved,
  onDeactivate,
  onReactivated,
}: {
  kit: KitDetail
  materials: Material[]
  defaultChannels: string[]
  mobile: boolean
  onSaved: (kit: KitDetail) => void
  onDeactivate: () => void
  /** After «فعال کردن دوباره» succeeded (the kit is already saved via onSaved). */
  onReactivated: (kit: KitDetail) => void
}) {
  const [drafts, setDrafts] = React.useState<Record<number, string>>({})
  const [busy, setBusy] = React.useState<Set<number | "add">>(new Set())
  const [rowErrors, setRowErrors] = React.useState<Record<number, string>>({})
  const [addError, setAddError] = React.useState<string | null>(null)
  const [reactivating, setReactivating] = React.useState(false)
  const [reactivateError, setReactivateError] = React.useState<string | null>(null)

  const [shownFor, setShownFor] = React.useState(kit.id)
  if (kit.id !== shownFor) {
    setShownFor(kit.id)
    setDrafts({})
    setRowErrors({})
    setAddError(null)
    setReactivateError(null)
  }

  /** Not destructive, so no confirmation: flips is_active back to 1. */
  const reactivate = async () => {
    setReactivating(true)
    setReactivateError(null)
    try {
      const updated = await reactivateKit(kit.id)
      onSaved(updated)
      onReactivated(updated)
    } catch (e) {
      setReactivateError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setReactivating(false)
    }
  }

  const active = kit.is_active === 1
  const materialById = React.useMemo(() => new Map(materials.map((m) => [m.id, m])), [materials])
  const avail = kitAvailability(kit, materialById)

  const run = async (key: number | "add", call: () => Promise<KitDetail>): Promise<boolean> => {
    setBusy((b) => new Set(b).add(key))
    try {
      onSaved(await call())
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
      setRowErrors((r) => ({ ...r, [item.material_id]: K.qtyInvalid }))
      return
    }
    if (q === item.quantity) {
      setDrafts((d) => without(d, item.material_id))
      setRowErrors((r) => without(r, item.material_id))
      return
    }
    if (await run(item.material_id, () => updateKitItem(kit.id, item.material_id, q))) {
      setDrafts((d) => without(d, item.material_id))
    }
  }

  const used = new Set(kit.items.map((i) => i.material_id))
  const addable: PickerItem[] = materials
    .filter((m) => m.is_active === 1 && m.type === "STOCK" && !used.has(m.id))
    .sort((a, b) => a.name.localeCompare(b.name, "fa"))
    .map((m) => ({
      id: m.id,
      name: m.name,
      sub: K.stockCaption(m.current_stock ?? 0, unitLabel(m.unit)),
    }))

  const grid = "grid grid-cols-[minmax(0,1fr)_120px_150px_130px_36px] items-center gap-3"

  const rows = kit.items.map((item) => {
    const m = materialById.get(item.material_id)
    const unit = unitLabel(m?.unit ?? "")
    const rowBusy = busy.has(item.material_id)
    const name = (
      <span className="flex min-w-0 flex-col leading-[1.3]">
        <span className="truncate text-[13.5px] font-bold">{item.material_name}</span>
        <span className="truncate text-xs text-text-3">{K.stockCaption(m?.current_stock ?? 0, unit)}</span>
      </span>
    )
    const qty = (
      <div className="relative flex items-center">
        <input
          inputMode="decimal"
          aria-label={`${K.colQty} — ${item.material_name}`}
          value={drafts[item.material_id] ?? formatQuantity(item.quantity)}
          disabled={!active || rowBusy}
          onChange={(e) => setDrafts((d) => ({ ...d, [item.material_id]: e.target.value }))}
          onBlur={() => saveQty(item)}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur()
          }}
          onFocus={(e) => e.currentTarget.select()}
          className={cn(
            "w-full min-w-0 rounded-lg border border-border-strong bg-card ps-3 pe-14 text-sm tabular-nums outline-none focus:border-heading focus:ring-3 focus:ring-ring/30 disabled:opacity-60",
            mobile ? "h-11" : "h-10",
            rowErrors[item.material_id] && "border-loss"
          )}
        />
        <span className="pointer-events-none absolute end-3 text-xs text-text-3">{unit}</span>
      </div>
    )
    const unitCost = <span className="text-[13px] text-text-3 tabular-nums">{K.unitCost(item.material_unit_cost, unit)}</span>
    // This line's share only; kit_cost (rounded once over all lines) comes from the API.
    const lineCost = <span className="font-bold tabular-nums">{formatNumber(Math.round(item.quantity * item.material_unit_cost))}</span>
    const del = active && (
      <Btn
        variant="ghost"
        size="sm"
        className="size-8 px-0"
        aria-label={`${K.delete} — ${item.material_name}`}
        disabled={rowBusy}
        onClick={() => run(item.material_id, () => removeKitItem(kit.id, item.material_id))}
      >
        {rowBusy ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
      </Btn>
    )
    return (
      <div key={item.material_id} className="flex flex-col gap-1.5">
        {mobile ? (
          <div className="flex flex-col gap-2 rounded-[10px] border border-border p-3">
            <div className="flex items-start justify-between gap-2">
              {name}
              {del}
            </div>
            <div className="grid grid-cols-2 items-center gap-2">
              {qty}
              <span className="flex flex-col items-end">
                {lineCost}
                {unitCost}
              </span>
            </div>
          </div>
        ) : (
          <div className={grid}>
            {name}
            {qty}
            {unitCost}
            {lineCost}
            <span>{del}</span>
          </div>
        )}
        {rowErrors[item.material_id] && <InlineMessage severity="error">{rowErrors[item.material_id]}</InlineMessage>}
      </div>
    )
  })

  const low = avail.kind === "count" && avail.count < LOW_KITS

  return (
    <section className={cn(cardClass, "min-w-0 grow overflow-hidden")} aria-labelledby="kit-title">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex flex-col">
          <h2 id="kit-title" className="text-base font-bold text-heading">
            {kit.name}
          </h2>
          <span className="text-xs text-text-3">{active ? `${K.savesNote} ${K.nameReadOnly}` : K.inactiveNote}</span>
        </div>
        {active ? (
          <Btn size="sm" className="border-loss-border text-loss hover:bg-loss-soft" onClick={onDeactivate}>
            <Ban className="size-3.5" />
            {K.deactivate}
          </Btn>
        ) : (
          <Btn size="sm" disabled={reactivating} aria-busy={reactivating || undefined} onClick={reactivate}>
            {reactivating ? <Loader2 className="size-3.5 animate-spin" /> : <RotateCcw className="size-3.5" />}
            {K.reactivate}
          </Btn>
        )}
        {reactivateError && (
          <div className="w-full">
            <InlineMessage severity="error">{reactivateError}</InlineMessage>
          </div>
        )}
      </div>
      <div className={cn("flex flex-col", mobile ? "gap-3 p-3.5" : "gap-3.5 p-5")}>
        {kit.items.length > 0 && !mobile && (
          <div className={cn(grid, "border-b border-border pb-1.5 text-xs font-bold text-text-3")}>
            <span>{K.colMaterial}</span>
            <span>{K.colQty}</span>
            <span>{K.colUnitCost}</span>
            <span>{K.colLineCost}</span>
            <span />
          </div>
        )}
        {rows}
        {kit.items.length === 0 && <p className="py-3 text-[13px] text-text-3">{K.emptyKit}</p>}
        {active && (
          <div className="flex flex-col gap-1.5">
            <div className={cn("relative [&>button]:border-dashed", mobile ? "w-full" : "w-[300px]")}>
              <ItemPicker
                items={addable}
                value={null}
                onPick={(materialId) => run("add", () => addKitItem(kit.id, materialId, 1))}
                placeholder={K.addMaterial}
                searchLabel={K.searchMaterial}
                emptyText={K.noMaterialsLeft}
                noMatchText={K.noMaterialMatch}
                mobile={mobile}
                disabled={busy.has("add")}
              />
              <span className="pointer-events-none absolute end-9 top-1/2 -translate-y-1/2 text-text-3">
                {busy.has("add") ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
              </span>
            </div>
            {addError && <InlineMessage severity="error">{addError}</InlineMessage>}
          </div>
        )}
        <div className={cn("mt-1 grid gap-3", mobile ? "grid-cols-1" : "grid-cols-3")}>
          <div className="flex flex-col gap-1 rounded-[10px] bg-surface-2 p-3">
            <span className="text-xs font-bold text-text-3">{K.tileCost}</span>
            <span className="tabular-nums">
              <b className="text-[22px]">{formatNumber(kit.kit_cost)}</b> <span className="text-xs">{K.toman}</span>
            </span>
            <span className="text-xs text-text-3">{K.tileCostNote}</span>
          </div>
          <div className="flex flex-col gap-1 rounded-[10px] bg-surface-2 p-3">
            <span className="text-xs font-bold text-text-3">{K.tileChannels}</span>
            <span className="mt-1 flex flex-wrap gap-1.5">
              {defaultChannels.length ? (
                defaultChannels.map((c) => <ChannelBadge key={c} channel={c} />)
              ) : (
                <span className="text-xs text-text-3">{K.noDefaultTile}</span>
              )}
            </span>
            <Link href="/settings" className="mt-auto text-xs font-bold text-heading hover:text-primary">
              {K.tileChannelsLink}
            </Link>
          </div>
          <div className={cn("flex flex-col gap-1 rounded-[10px] p-3", low ? "bg-warn-soft" : "bg-surface-2")}>
            <span className="text-xs font-bold text-text-3">{K.tileAvail}</span>
            <b className="text-[22px] tabular-nums">{avail.kind === "unlimited" ? "∞" : formatNumber(avail.count)}</b>
            <span className={cn("text-xs", low ? "font-bold" : "text-text-3")}>
              {avail.kind === "unlimited"
                ? K.noLimit
                : K.limiting(avail.limiting.name, avail.limiting.stock, unitLabel(avail.limiting.unit))}
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}
