"use client"

import * as React from "react"
import { Box, Eraser, History, Wallet } from "lucide-react"
import { ConfirmShell, Effect, Irreversible } from "@/components/orders/detail/confirm-shell"
import { unitLabel } from "@/components/products/figures"
import { Help, InlineMessage, Label } from "@/components/record-sale/primitives"
import { ApiError, cancelPurchase, getCancelPreview, type PurchaseCancelPreview, type PurchaseDetail } from "@/lib/api"
import { formatJalaliDateTime } from "@/lib/jalali"
import { formatMoney } from "@/lib/money"
import { formatQuantity } from "@/lib/persian-numbers"
import { blockerRefusal, cancelGate, cancelRefusal } from "@/lib/purchase-correction"
import { C, METHOD_LABELS, refusalText } from "./copy"

type Load = { status: "loading" } | { status: "error" } | { status: "ready"; preview: PurchaseCancelPreview }

/** The blockers of a cancel-preview in Persian. The payments blocker is left to the tick unless a payment is shared. */
export function blockerTexts(preview: PurchaseCancelPreview, timeZone: string, keepPayments: boolean): string[] {
  return preview.blockers
    .filter((b) => keepPayments || b.code !== "PURCHASE_HAS_PAYMENTS")
    .map((b) => {
      const refusal = blockerRefusal(b)
      return refusal ? refusalText(refusal, timeZone) : b.code
    })
}

/** One line of the preview: the stock and the unit cost the cancel gives back (all from the server). */
function lineText(line: PurchaseCancelPreview["lines"][number]): string {
  const cost = (v: number | null) => (v == null ? C.noCost : formatMoney(v))
  if (line.item_type === "SERVICE") return C.serviceBack(line.item_name, cost(line.cost_before), cost(line.cost_after))
  return C.lineBack(
    line.item_name,
    line.unit ? unitLabel(line.unit) : "عدد",
    formatQuantity(line.stock_before ?? 0),
    formatQuantity(line.stock_after ?? 0),
    cost(line.cost_before),
    cost(line.cost_after)
  )
}

/**
 * «ابطال خرید» (accounting-rules section 23): for a purchase entered by mistake. The cancel-preview first (each line's
 * stock and cost going back, every refusal), a required reason, and the payments that go with it only after the tick
 * «پرداخت‌های این خرید هم حذف شوند» (owner edit E3); a payment shared with another purchase refuses. Mounted only
 * while open.
 */
export function PurchaseCancelDialog({
  open,
  onOpenChange,
  detail,
  timeZone,
  mobile,
  onDone,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  detail: PurchaseDetail
  timeZone: string
  mobile: boolean
  onDone: (cancelled: PurchaseDetail, message: string) => void
}) {
  const [load, setLoad] = React.useState<Load>({ status: "loading" })
  const [reason, setReason] = React.useState("")
  const [ticked, setTicked] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const inv = detail.invoice_number ?? ""

  React.useEffect(() => {
    if (!open) return
    let cancelled = false
    getCancelPreview(detail.id).then(
      (preview) => !cancelled && setLoad({ status: "ready", preview }),
      () => !cancelled && setLoad({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [open, detail.id])

  const gate = load.status === "ready" ? cancelGate(load.preview, ticked) : null
  const blockers = load.status === "ready" && gate ? blockerTexts(load.preview, timeZone, gate.shared) : []

  const close = (o: boolean) => {
    if (!o) {
      setReason("")
      setTicked(false)
      setError(null)
    }
    onOpenChange(o)
  }

  const confirm = async () => {
    if (!gate?.canConfirm || !reason.trim()) return
    setBusy(true)
    setError(null)
    try {
      const cancelled = await cancelPurchase(detail.id, reason.trim(), gate.needsTick && ticked)
      setBusy(false)
      close(false)
      onDone(cancelled, C.cancelled(inv))
    } catch (e) {
      const refusal = e instanceof ApiError ? cancelRefusal(e) : null
      setError(refusal ? refusalText(refusal, timeZone) : e instanceof ApiError ? e.message : String(e))
      setBusy(false)
    }
  }

  return (
    <ConfirmShell
      open={open}
      onOpenChange={close}
      mobile={mobile}
      busy={busy}
      icon={Eraser}
      title={C.cancelTitle(inv)}
      subtitle={C.cancelSubtitle}
      confirmLabel={C.cancelPurchase}
      confirmIcon={Eraser}
      confirmDisabled={!gate?.canConfirm || !reason.trim()}
      onConfirm={confirm}
      width={600}
    >
      {load.status === "loading" && <p className="text-[13px] text-text-3">{C.cancelLoading}</p>}
      {load.status === "error" && <InlineMessage severity="error">{C.cancelPreviewFailed}</InlineMessage>}
      {error && <InlineMessage severity="error">{error}</InlineMessage>}
      {load.status === "ready" &&
        (blockers.length > 0 ? (
          blockers.map((text) => (
            <InlineMessage key={text} severity="error">
              {text}
            </InlineMessage>
          ))
        ) : (
          <>
            {load.preview.lines.map((line) => (
              <Effect key={line.line_index} tone="flat" icon={line.item_type === "SERVICE" ? History : Box}>
                <span className="tabular-nums">{lineText(line)}</span>
              </Effect>
            ))}
            {gate?.needsTick && (
              <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
                <span className="flex items-center gap-1.5 text-[13px] font-semibold">
                  <Wallet className="size-3.5 text-text-3" aria-hidden />
                  {C.paymentsGo}
                </span>
                <ul className="flex flex-col text-[13px]">
                  {load.preview.payments.map((pay) => (
                    <li key={pay.payment_id} className="flex items-start justify-between gap-4 border-b border-border py-1.5 last:border-b-0">
                      <span className="flex min-w-0 flex-col">
                        <span>{formatJalaliDateTime(pay.payment_date, timeZone)}</span>
                        <span className="truncate text-xs text-text-3">
                          {METHOD_LABELS[pay.method]}
                          {pay.reference && (
                            <>
                              {" · "}
                              <span dir="ltr">{pay.reference}</span>
                            </>
                          )}
                        </span>
                      </span>
                      <span className="shrink-0 font-semibold tabular-nums">{formatMoney(pay.amount)}</span>
                    </li>
                  ))}
                </ul>
                <label className="flex cursor-pointer items-center gap-2 text-[13px] font-semibold">
                  <input
                    type="checkbox"
                    className="size-4 cursor-pointer accent-primary"
                    checked={ticked}
                    onChange={(e) => setTicked(e.target.checked)}
                  />
                  {C.paymentsTick}
                </label>
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="purchase-cancel-reason">{C.reasonLabel}</Label>
              <input
                id="purchase-cancel-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={C.reasonPlaceholder}
                className={
                  "w-full rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30 " +
                  (mobile ? "h-11" : "h-10")
                }
              />
              <Help>{C.reasonHelp}</Help>
            </div>
            <p className="text-xs text-text-3">{C.kept}</p>
          </>
        ))}
      <Irreversible />
    </ConfirmShell>
  )
}
