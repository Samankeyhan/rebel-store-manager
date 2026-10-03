"use client"

import { Lock } from "lucide-react"
import { Segment } from "@/components/common/segment"
import { Help, InlineMessage, cardClass } from "@/components/record-sale/primitives"
import type { Currency } from "@/lib/money"
import { cn } from "@/lib/utils"
import { S } from "./copy"

/**
 * [3] عمومی: «واحد پول» (display currency; saved immediately by the page, not
 * through the draft — see settings-page.tsx) and the store timezone, display-only. The backend accepts a change,
 * but db/timeutil.py reads it on every conversion: changing it would move
 * every stored moment into different local days in every filter and report,
 * and shift what profit_distributions' local-day periods mean. So this screen
 * never sends PUT /settings/timezone.
 */
export function GeneralCard({
  timezone,
  currency,
  onCurrency,
  currencyBusy,
  currencyError,
  mobile,
}: {
  timezone: string
  currency: Currency
  onCurrency: (c: Currency) => void
  currencyBusy: boolean
  currencyError: string | null
  mobile: boolean
}) {
  return (
    <section id="general" className={cn(cardClass, "scroll-mt-6")} aria-labelledby="st3">
      <div className={cn(mobile ? "px-3.5 pt-3.5" : "border-b border-border px-5 py-4")}>
        <h2 id="st3" className={cn("font-bold text-heading", mobile ? "text-sm" : "text-base leading-[26px]")}>
          {S.generalTitle}
        </h2>
      </div>
      <div className={cn("flex flex-col gap-1.5", mobile ? "px-3.5 pt-3.5" : "max-w-[480px] px-5 pt-5")}>
        <span id="st-currency-label" className="text-[13px] font-semibold">
          {S.currencyLabel}
        </span>
        <Segment
          value={currency}
          options={S.currencyOptions}
          onChange={onCurrency}
          label={S.currencyAria}
          mobile={mobile}
          className={cn(!mobile && "max-w-[240px]", currencyBusy && "pointer-events-none opacity-60")}
        />
        {currencyError ? <InlineMessage severity="error">{currencyError}</InlineMessage> : <Help>{S.currencyNote}</Help>}
      </div>
      <div className={cn("flex flex-col gap-1.5", mobile ? "p-3.5" : "max-w-[480px] p-5")}>
        <span id="st-tz-label" className="text-[13px] font-semibold">
          {S.tzLabel}
        </span>
        <div
          role="textbox"
          aria-labelledby="st-tz-label"
          aria-readonly="true"
          tabIndex={0}
          className="flex h-10 outline-none focus-visible:ring-3 focus-visible:ring-ring/30 items-center justify-between gap-2 rounded-lg border border-border bg-surface-2 px-3 text-sm text-text-2"
        >
          <span dir="ltr">{timezone}</span>
          <Lock className="size-3.5 text-text-3" aria-hidden />
        </div>
        <Help>{S.tzHelp}</Help>
      </div>
    </section>
  )
}
