"use client"

import * as React from "react"
import { CheckCheck } from "lucide-react"
import { Btn, InlineMessage } from "@/components/record-sale/primitives"
import { BULK_MAX, type BulkPlan } from "@/lib/order-bulk"
import { cn } from "@/lib/utils"
import { ConfirmShell } from "../detail/confirm-shell"
import { L } from "../copy"

/**
 * The action bar shown while orders are ticked in the list: how many, the one action («تغییر به تکمیل‌شده»)
 * and «لغو انتخاب». The action is off, with the reason said on the bar, while any ticked order is not PAID
 * (all or nothing: the server refuses the whole call too) or too many are ticked. The selection's count is the
 * total across pages.
 */
export function BulkBar({
  count,
  plan,
  onRun,
  onClear,
  mobile,
}: {
  count: number
  plan: BulkPlan
  onRun: () => void
  onClear: () => void
  mobile: boolean
}) {
  const reason = plan.ineligible.length > 0 ? L.bulkIneligible(plan.ineligible.length) : plan.tooMany ? L.bulkTooMany(BULK_MAX) : null
  return (
    <div
      role="region"
      aria-label={L.bulkSelected(count)}
      className={cn(
        "flex flex-col gap-2 border-border bg-card",
        mobile
          ? "fixed inset-x-0 bottom-0 z-30 border-t px-4 pt-3 pb-5"
          : "rounded-xl border px-4 py-3 shadow-[0_1px_2px_rgba(18,22,38,.06)]"
      )}
    >
      <div className={cn("flex items-center gap-3", mobile ? "flex-col items-stretch" : "flex-wrap justify-between")}>
        <b className="text-[13.5px] text-heading tabular-nums">{L.bulkSelected(count)}</b>
        <div className={cn("flex items-center gap-2", mobile && "w-full")}>
          <Btn
            variant="primary"
            className={mobile ? "h-11 grow" : undefined}
            disabled={!plan.canRun}
            aria-describedby={reason ? "bulk-reason" : undefined}
            onClick={onRun}
          >
            <CheckCheck className="size-4" aria-hidden />
            {L.bulkAction}
          </Btn>
          <Btn variant="ghost" className={mobile ? "h-11" : undefined} onClick={onClear}>
            {L.bulkClear}
          </Btn>
        </div>
      </div>
      {reason && (
        <div id="bulk-reason">
          <InlineMessage severity="error">{reason}</InlineMessage>
        </div>
      )}
    </div>
  )
}

/** The confirmation: the count and every invoice number about to change; nothing else changes. */
export function BulkConfirm({
  open,
  onOpenChange,
  plan,
  busy,
  error,
  onConfirm,
  mobile,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  plan: BulkPlan
  busy: boolean
  error: string | null
  onConfirm: () => void
  mobile: boolean
}) {
  return (
    <ConfirmShell
      open={open}
      onOpenChange={onOpenChange}
      mobile={mobile}
      busy={busy}
      danger={false}
      icon={CheckCheck}
      title={L.bulkConfirmTitle(plan.chosen.length)}
      subtitle={L.bulkConfirmSubtitle}
      confirmLabel={L.bulkConfirm}
      confirmDisabled={!plan.canRun}
      onConfirm={onConfirm}
    >
      <p className="text-[13px] text-text-2">{L.bulkConfirmNote}</p>
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold text-text-3">{L.bulkInvoices}</span>
        <ul
          dir="ltr"
          className="grid max-h-48 grid-cols-2 gap-x-4 gap-y-1 overflow-y-auto rounded-lg bg-surface-2 px-3 py-2.5 font-mono text-[12.5px] sm:grid-cols-3"
        >
          {plan.chosen.map((o) => (
            <li key={o.id}>{o.invoice_number ?? `#${o.id}`}</li>
          ))}
        </ul>
      </div>
      {error && <InlineMessage severity="error">{error}</InlineMessage>}
    </ConfirmShell>
  )
}
