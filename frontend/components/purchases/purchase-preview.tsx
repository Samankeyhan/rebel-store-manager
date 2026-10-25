"use client"

import { ChevronLeft } from "lucide-react"
import { blendUnitCost, purchaseUnitCost } from "@/lib/costing"
import { formatQuantity } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { U } from "./copy"

/** What a line's preview needs of its item: a service has no stock (`stock` null). */
export type PreviewItem = {
  name: string
  kind: "material" | "product" | "service"
  stock: number | null
  cost: number | null
  unit: string
}

/**
 * «پیش‌نمایش بهای تمام‌شده» of ONE purchase line (design 07 §1.7, formulas.md §3): this line's unit cost and the item's
 * weighted average before → after, via the same functions as db/purchases.py (purchaseUnitCost, blendUnitCost). A
 * service has no stock: its new price is the line's unit cost (the last purchase sets it). A preview: the saved
 * figures are re-read from the server after the purchase.
 */
export function LinePreview({ item, qty, total }: { item: PreviewItem | null; qty: number | null; total: number | null }) {
  const valid = item != null && qty != null && qty > 0 && total != null
  if (item == null || !valid || total == null || qty == null) return <p className="text-xs text-text-3">{U.pickToPreview}</p>
  const unit = purchaseUnitCost(total, qty)
  const stock = item.stock ?? 0
  const service = item.kind === "service"
  const after = service ? unit : blendUnitCost(stock, item.cost, qty, total, item.kind === "material")
  const now = item.cost == null || (item.kind !== "product" && item.cost === 0) ? U.noCost : formatMoney(item.cost)

  if (service) {
    return (
      <section aria-label={U.previewTitle} className="flex flex-col gap-1 rounded-[10px] bg-surface-2 px-3 py-2.5 text-[13px]">
        <span className="flex items-center justify-between gap-3">
          <span className="text-text-2">{U.previewUnit}</span>
          <span className="font-bold tabular-nums">{formatMoney(unit)}</span>
        </span>
        <span className="text-xs leading-[1.8] text-text-3 tabular-nums">
          {U.previewServiceFrom(item.name, item.cost ? formatMoney(item.cost) : U.servicePriceNotEntered, formatMoney(after))}
        </span>
        <span className="text-xs text-text-3">{U.previewServiceNote(item.name)}</span>
      </section>
    )
  }
  return (
    <section aria-label={U.previewTitle} className="flex flex-col gap-1 rounded-[10px] bg-surface-2 px-3 py-2.5 text-[13px]">
      <span className="flex items-center justify-between gap-3">
        <span className="text-text-2">{U.previewUnit}</span>
        <span className="font-bold tabular-nums">{formatMoney(unit)}</span>
      </span>
      <span className="flex items-center justify-between gap-3 tabular-nums">
        <span className="text-text-2">{U.avgNow}</span>
        <span className="flex items-center gap-1.5">
          <span>{now}</span>
          {/* current → after in reading order: in RTL the chevron points left. */}
          <ChevronLeft className="size-4 text-text-3" aria-hidden />
          <b>{formatMoney(after)}</b>
        </span>
      </span>
      <span className="text-xs text-text-3 tabular-nums">
        {U.inStock(formatQuantity(stock + qty), item.unit)}
        {" · "}
        {U.previewNote}
      </span>
    </section>
  )
}
