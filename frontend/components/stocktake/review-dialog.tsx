"use client"

import * as React from "react"
import { Loader2, X } from "lucide-react"
import { Money } from "@/components/common/money"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { Alert, Btn } from "@/components/record-sale/primitives"
import type { StocktakeResult } from "@/lib/api"
import { formatQuantity } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { S } from "./copy"

/**
 * The confirmation step: every correction (item, old, new, difference, cost, value) exactly as the API's preview
 * computed it, the note that will be written, and the one button that applies them all.
 */
export function ReviewDialog({
  open,
  plan,
  busy,
  error,
  onApply,
  onClose,
}: {
  open: boolean
  plan: StocktakeResult | null
  busy: boolean
  error: { message: string; code: string } | null
  onApply: () => void
  onClose: () => void
}) {
  const id = React.useId()
  const nothing = plan != null && plan.corrections.length === 0
  return (
    <Dialog open={open} onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent
        showCloseButton={false}
        aria-labelledby={id}
        style={{ maxWidth: "min(860px, calc(100% - 1rem))" }}
        className="w-full gap-0 overflow-hidden rounded-[14px] border border-border bg-card p-0 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)] ring-0 sm:max-w-none"
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <DialogTitle id={id} className="text-base font-bold text-heading">
            {S.dialogTitle}
          </DialogTitle>
          <DialogDescription className="sr-only">{S.dialogTitle}</DialogDescription>
          <Btn variant="ghost" size="sm" className="size-8 px-0" aria-label={S.close} disabled={busy} onClick={onClose}>
            <X className="size-4" />
          </Btn>
        </div>
        <div className="flex max-h-[68vh] flex-col gap-3 overflow-y-auto px-5 py-4">
          {plan && (
            <>
              <p className="text-sm font-semibold">{nothing ? S.dialogNothing : S.dialogLead(plan.corrections.length, plan.unchanged_count)}</p>
              <p className="text-xs text-text-2">{S.dialogNote(plan.note)}</p>
              <Alert tone="warn" title={S.pauseTitle} icon="triangle" />
              {!nothing && (
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="border-b border-border bg-surface-2 text-xs text-text-3">
                        <th className="px-3 py-2 text-start font-semibold">{S.colName}</th>
                        <th className="px-3 py-2 text-end font-semibold">{S.colOld}</th>
                        <th className="px-3 py-2 text-end font-semibold">{S.colNew}</th>
                        <th className="px-3 py-2 text-end font-semibold">{S.colDiff}</th>
                        <th className="px-3 py-2 text-end font-semibold">{S.colCost}</th>
                        <th className="px-3 py-2 text-end font-semibold">{S.colValue}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plan.corrections.map((c) => (
                        <tr key={`${c.item_type}:${c.item_id}`} className="border-b border-border/70 last:border-b-0">
                          <td className="px-3 py-2 font-semibold">
                            {c.item_name} <span className="text-xs font-normal text-text-3">{c.unit === "piece" ? S.unitPiece : c.unit}</span>
                          </td>
                          <td className="px-3 py-2 text-end tabular-nums">{formatQuantity(c.old_quantity)}</td>
                          <td className="px-3 py-2 text-end tabular-nums">{formatQuantity(c.new_quantity)}</td>
                          <td className={cn("px-3 py-2 text-end font-bold tabular-nums", c.difference > 0 ? "text-profit" : "text-loss")}>
                            <span dir="ltr">{S.signed(c.difference)}</span>
                          </td>
                          <td className="px-3 py-2 text-end">{c.unit_cost == null ? <span className="text-text-3">{S.noCost}</span> : <Money value={c.unit_cost} />}</td>
                          <td className="px-3 py-2 text-end">{c.value == null ? <span className="text-text-3">—</span> : <Money value={c.value} />}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!nothing && (
                <p className="text-sm">
                  <b>{S.total}:</b> <Money value={plan.total_value} />
                  {plan.unvalued_count > 0 && <span className="ms-2 text-xs text-text-3">({S.unvalued(plan.unvalued_count)})</span>}
                </p>
              )}
            </>
          )}
          {error && (
            <Alert tone="err" title={S.applyFailed}>
              <div dir="auto">{error.message}</div>
              <div className="mt-1 text-xs text-text-3">
                {S.errorCode}{" "}
                <span dir="ltr" className="inline-block font-mono">
                  {error.code}
                </span>
              </div>
            </Alert>
          )}
        </div>
        <div className="flex justify-start gap-2 border-t border-border bg-surface-2 px-5 py-4">
          <Btn variant="primary" disabled={busy || nothing || !plan} aria-busy={busy || undefined} onClick={onApply}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {busy ? S.applying : S.apply}
          </Btn>
          <Btn disabled={busy} onClick={onClose}>
            {S.back}
          </Btn>
        </div>
      </DialogContent>
    </Dialog>
  )
}
