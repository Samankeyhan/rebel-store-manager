"use client"

import * as React from "react"
import Link from "next/link"
import { PencilLine, TriangleAlert } from "lucide-react"
import { VoidEffects } from "@/components/orders/detail/dialogs"
import type { VoidPreview } from "@/lib/api"
import { cn } from "@/lib/utils"
import { T } from "./copy"
import { Alert, btnClass, cardClass } from "./primitives"
import type { Action, FormState } from "./state"

/**
 * «اصلاح سفارش»: on top of the record-sale form, what saving does (the old order is voided, the effects
 * the void-preview lists) and the required reason. Accounting rules section 20.
 */
export function CorrectionCard({
  invoice,
  preview,
  state,
  dispatch,
  mobile,
}: {
  invoice: string
  preview: VoidPreview
  state: FormState
  dispatch: React.Dispatch<Action>
  mobile: boolean
}) {
  return (
    <section
      aria-labelledby="correction-title"
      className={cn(cardClass, "flex flex-col gap-3 border-heading/30", mobile ? "p-3.5" : "px-5 py-4")}
    >
      <h2 id="correction-title" className="flex items-center gap-2 text-[15px] font-bold text-heading">
        <PencilLine className="size-4" aria-hidden />
        <span>
          {T.correctTitle}{" "}
          <span dir="ltr" className="font-mono">
            {invoice}
          </span>
        </span>
      </h2>
      <p className="text-[13px] leading-[22px] text-text-2">{T.correctBody}</p>
      <div className="flex flex-col gap-2">
        <div className="text-xs font-bold text-text-3">{T.correctEffectsLead}</div>
        <VoidEffects preview={preview} />
        {(preview.products.length > 0 || preview.materials.length > 0) && (
          <p className="text-xs text-text-3">{T.correctStockNote}</p>
        )}
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="correction-reason" className="text-[13px] font-semibold">
          {T.correctReasonLabel}
        </label>
        <input
          id="correction-reason"
          value={state.correctionReason}
          onChange={(e) => dispatch({ type: "correctionReason", value: e.target.value })}
          placeholder={T.correctReasonPlaceholder}
          className={cn(
            "w-full rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
            mobile ? "h-11" : "h-10"
          )}
        />
        <span className="text-xs text-text-3">{T.correctReasonHelp}</span>
      </div>
    </section>
  )
}

/** The order can't be corrected now: why (from the void-preview), and the way back to it. */
export function CorrectionBlocked({ orderId, reasons, mobile }: { orderId: number; reasons: string[]; mobile: boolean }) {
  return (
    <section role="alert" className={cn(cardClass, "flex flex-col gap-3", mobile ? "p-3.5" : "px-6 py-5")}>
      <h2 className="flex items-center gap-2 text-[15px] font-bold text-heading">
        <TriangleAlert className="size-5 text-loss" aria-hidden />
        {T.correctBlockedTitle}
      </h2>
      {reasons.map((r) => (
        <Alert key={r} tone="err">
          {r}
        </Alert>
      ))}
      <div>
        <Link href={`/orders/view/?id=${orderId}`} className={btnClass("outline", mobile ? "lg" : "md")}>
          {T.correctBackToOrder}
        </Link>
      </div>
    </section>
  )
}
