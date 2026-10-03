"use client"

import { ChevronLeft } from "lucide-react"
import { badgeBase } from "@/components/common/status"
import { blendUnitCost, purchaseUnitCost } from "@/lib/costing"
import { formatNumber, formatQuantity } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { cn } from "@/lib/utils"
import { U } from "./copy"

export type PreviewItem = { name: string; stock: number; cost: number | null; unit: string; kind: "material" | "product" }

/**
 * «پیش‌نمایش بهای تمام‌شده» (design 07 §1.7, formulas.md §3): this purchase's
 * unit cost and the item's weighted average before → after, via the same
 * functions as db/purchases.py (purchaseUnitCost, blendUnitCost). A preview:
 * the saved average is re-read from the server after the purchase.
 */
export function PurchasePreview({
  item,
  qty,
  total,
  mobile,
}: {
  item: PreviewItem | null
  qty: number | null
  total: number
  mobile: boolean
}) {
  const valid = item != null && qty != null && qty > 0
  const unit = valid ? purchaseUnitCost(total, qty) : null
  const after = valid ? blendUnitCost(item.stock, item.cost, qty, total) : null
  const afterStock = valid ? item.stock + qty : null
  const blended = item != null && item.cost != null && item.stock > 0
  const delta = after != null && item?.cost != null && blended ? after - item.cost : null
  const derivation =
    !valid || item == null
      ? null
      : blended
        ? (mobile ? U.formulaMobile : U.formula)(item.stock, item.cost!, total, afterStock!)
        : item.cost == null
          ? U.firstPurchase
          : U.noStockNow

  const q = (n: number) => formatQuantity(n)

  if (mobile) {
    return (
      <section aria-label={U.previewTitle} className="flex flex-col gap-2 rounded-xl bg-surface-2 p-3.5 text-[13px]">
        <h3 className="text-sm font-bold text-heading">{U.previewTitle}</h3>
        {item == null ? (
          <p className="text-xs text-text-3">{U.pickToPreview}</p>
        ) : (
          <>
            <Line label={U.unitThis} value={unit == null ? "—" : formatNumber(unit)} />
            <Line
              label={U.avgNowMobile(`${q(item.stock)} ${item.unit}`)}
              value={item.cost == null ? U.noCost : formatNumber(item.cost)}
            />
            <Line
              label={U.avgAfterMobile(afterStock == null ? "—" : `${q(afterStock)} ${item.unit}`)}
              value={after == null ? "—" : formatNumber(after)}
              total
            />
            {derivation && <span className="text-xs text-text-3 tabular-nums">{derivation}</span>}
          </>
        )}
      </section>
    )
  }

  return (
    <section aria-label={U.previewTitle} className="flex flex-col gap-2.5 rounded-xl bg-surface-2 p-3.5">
      <h3 className="text-sm font-bold text-heading">{U.previewTitle}</h3>
      {item == null ? (
        <p className="text-xs text-text-3">{U.pickToPreview}</p>
      ) : (
        <>
          <Line label={U.unitThis} value={unit == null ? "—" : formatMoney(unit)} />
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 rounded-[10px] border border-border bg-card px-3 py-2.5">
            <div className="flex flex-col">
              <span className="text-xs text-text-3">{U.avgNow}</span>
              <span className="text-[17px] tabular-nums">{item.cost == null ? U.noCost : formatNumber(item.cost)}</span>
              <span className="text-xs text-text-3 tabular-nums">{U.inStock(q(item.stock), item.unit)}</span>
            </div>
            {/* current → after in reading order: in RTL the chevron points left. */}
            <ChevronLeft className="size-5 text-text-3" aria-hidden />
            <div className="flex flex-col">
              <span className="text-xs text-text-3">{U.avgAfter}</span>
              <span className="text-[19px] font-bold tabular-nums">{after == null ? "—" : formatNumber(after)}</span>
              <span className="text-xs text-text-3 tabular-nums">
                {afterStock == null ? "—" : U.inStock(q(afterStock), item.unit)}
              </span>
            </div>
          </div>
          {derivation && (
            <span className="text-xs leading-[1.8] text-text-3 tabular-nums">
              {derivation}
              {delta != null && (
                <span
                  className={cn(
                    badgeBase,
                    "ms-1.5 tabular-nums",
                    delta > 0 ? "bg-warn-soft text-warn" : "bg-profit-soft text-profit"
                  )}
                >
                  {delta > 0 ? "+" : ""}
                  {formatNumber(delta)}
                </span>
              )}
            </span>
          )}
          <span className="text-xs text-text-3">
            {item.kind === "material" ? U.noteMaterial(item.name) : U.noteProduct(item.name)} {U.previewNote}
          </span>
        </>
      )}
    </section>
  )
}

function Line({ label, value, total }: { label: string; value: string; total?: boolean }) {
  return (
    <span className={cn("flex items-center justify-between gap-3", total && "border-t border-border pt-2 font-bold")}>
      <span className="text-text-2">{label}</span>
      <span className="font-bold tabular-nums">{value}</span>
    </span>
  )
}
