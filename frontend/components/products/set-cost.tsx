"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { Money } from "@/components/common/money"
import { Btn, InlineMessage, MoneyInput } from "@/components/record-sale/primitives"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { ApiError } from "@/lib/api"
import { isAmountTooLarge, isCostAlreadySet } from "@/lib/error-codes"
import { currencyLabel, formatMoneyNumber } from "@/lib/money"
import { formatQuantity } from "@/lib/persian-numbers"
import { setCostStockValue } from "@/lib/set-cost"
import { useCurrency } from "@/lib/use-currency"
import { cn } from "@/lib/utils"
import { P } from "./copy"

/** What «ثبت بها» is for: a material (STOCK or SERVICE) or a product, with the stock the confirmation values. */
export type SetCostItem = {
  kind: "material" | "product"
  id: number
  name: string
  /** The material's type; a SERVICE has no stock, so its confirmation shows the unit price only. */
  type?: string
  /** Shown unit («عدد», «گرم», …). */
  unit: string
  current_stock: number | null
}

function Row({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2 text-sm last:border-b-0">
      <dt className="text-text-2">{label}</dt>
      <dd className="font-semibold tabular-nums">{children}</dd>
    </div>
  )
}

/**
 * The guard against a Toman/Rial typo: a cost cannot be edited afterwards, so nothing is saved until «تأیید». It shows
 * the unit price in the display currency, the stored Rial amount (when the display is Toman) and the stock value the
 * price gives (STOCK materials and products; a SERVICE has none).
 */
function CostConfirm({
  item,
  cost,
  busy,
  onConfirm,
  onCancel,
}: {
  item: SetCostItem
  cost: number
  busy: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const currency = useCurrency()
  const id = React.useId()
  const service = item.type === "SERVICE"
  const value = setCostStockValue(item, cost)
  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onCancel()}>
      <DialogContent
        showCloseButton={false}
        aria-labelledby={id}
        style={{ maxWidth: "min(440px, calc(100% - 1rem))" }}
        className="w-full gap-0 overflow-hidden rounded-[14px] border border-border bg-card p-0 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)] ring-0 sm:max-w-none"
      >
        <div className="border-b border-border px-5 py-4">
          <DialogTitle id={id} className="text-base font-bold text-heading">
            {P.costConfirmTitle}
          </DialogTitle>
          <DialogDescription className="sr-only">{P.costConfirmTitle}</DialogDescription>
        </div>
        <div className="flex flex-col gap-3 px-5 py-4">
          <dl>
            <Row label={item.kind === "material" ? P.costConfirmMaterial : P.costConfirmProduct}>{item.name}</Row>
            <Row label={P.costConfirmUnitPrice(item.unit)}>
              <Money value={cost} plainUnit />
            </Row>
            {currency === "TOMAN" && (
              <Row label={P.costConfirmStored}>
                <span className="whitespace-nowrap">
                  <span dir="ltr">{formatMoneyNumber(cost, "RIAL")}</span> {currencyLabel("RIAL")}
                </span>
              </Row>
            )}
            {value != null && item.current_stock != null && (
              <Row label={P.costConfirmStockValue(`${formatQuantity(item.current_stock)} ${item.unit}`)}>
                <Money value={value} plainUnit />
              </Row>
            )}
          </dl>
          {service && <p className="text-xs text-text-2">{P.costConfirmService}</p>}
          <p className="text-xs font-medium text-warn">{P.costConfirmWarn}</p>
        </div>
        <div className="flex items-center gap-2 border-t border-border bg-surface-2 px-5 py-3">
          <Btn variant="primary" disabled={busy} aria-busy={busy || undefined} onClick={onConfirm}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
            {P.costConfirmOk}
          </Btn>
          <Btn disabled={busy} onClick={onCancel}>
            {P.costConfirmCancel}
          </Btn>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/**
 * «ثبت بها»: a price field and a button. The button opens the confirmation; only «تأیید» calls `onSave` (integer Rial,
 * at least 1). After a save the caller's data changes and the item no longer qualifies, so the field goes away.
 * A refusal because the cost is already set calls `onAlreadySet` (the caller refetches); any other failure is shown here.
 */
export function SetCostField({
  item,
  prefill = null,
  compact = false,
  mobile = false,
  onSave,
  onAlreadySet,
}: {
  item: SetCostItem
  /** A suggestion (the recipe estimate): editable, labelled, never saved without the click and the confirmation. */
  prefill?: number | null
  compact?: boolean
  mobile?: boolean
  onSave: (cost: number) => Promise<void>
  onAlreadySet?: () => void
}) {
  const [cost, setCost] = React.useState<number | null | undefined>(prefill ?? 0)
  const [confirming, setConfirming] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const amount = typeof cost === "number" && cost > 0 ? cost : null

  const save = async () => {
    if (amount == null) return
    setBusy(true)
    setError(null)
    try {
      await onSave(amount)
    } catch (e) {
      setConfirming(false)
      if (e instanceof ApiError && isCostAlreadySet(e)) {
        setError(P.costAlreadySet)
        onAlreadySet?.()
      } else if (e instanceof ApiError && isAmountTooLarge(e)) setError(P.costTooLarge)
      else setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-w-0 flex-col gap-1">
      <div className="flex flex-wrap items-start gap-2">
        <div className={cn("min-w-0", compact ? "w-44" : "w-56", "max-w-full")}>
          <MoneyInput
            value={cost}
            onValue={(v) => {
              setCost(v)
              setError(null)
            }}
            aria-label={P.setCostInputAria(item.name)}
            className={mobile ? "h-11" : compact ? "h-8 text-[13px]" : undefined}
          />
        </div>
        <Btn
          variant="primary"
          size={compact && !mobile ? "sm" : "md"}
          className={mobile ? "h-11" : undefined}
          disabled={amount == null || busy}
          onClick={() => setConfirming(true)}
        >
          {P.setCost}
        </Btn>
      </div>
      <span className="text-xs text-text-3">{P.setCostPer(item.unit)}</span>
      {prefill != null && cost === prefill && <span className="text-xs text-text-3">{P.setCostPrefilled}</span>}
      {error && <InlineMessage severity="error">{error}</InlineMessage>}
      {confirming && amount != null && (
        <CostConfirm item={item} cost={amount} busy={busy} onConfirm={save} onCancel={() => setConfirming(false)} />
      )}
    </div>
  )
}
