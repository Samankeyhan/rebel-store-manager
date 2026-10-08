"use client"

import { Help, InlineMessage, Label, MoneyInput, Stepper, cardClass } from "@/components/record-sale/primitives"
import type { MoneyInputError } from "@/lib/money"
import { sums, windowOf } from "@/components/postage/figures"
import type { PostageBatch, PostageEstimate, Settings } from "@/lib/api"
import { roundHalfEven } from "@/lib/costing"
import { Money } from "@/components/common/money"
import { cn } from "@/lib/utils"
import { S } from "./copy"
import { WINDOW_MAX, type Draft } from "./draft"

export type HeroFigure = {
  estimate: number
  /** True when it's a local preview of unsaved values, not the API's number. */
  preview: boolean
  /** Payments the estimate uses (≤ N), and their sums. */
  used: number
  paid: number
  orders: number
}

/**
 * The estimate for the draft's N and default (docs/accounting-rules.md §6):
 * round(Σ total_paid ÷ Σ order_count) over the newest N payments, or the
 * default estimate when there are none. While the draft matches what's saved
 * it's the API's own number; otherwise the same formula is rebuilt for
 * display only (as Postage's projection does) and never sent.
 */
export function heroFigure(batches: PostageBatch[], api: PostageEstimate, saved: Settings, draft: Draft): HeroFigure {
  const n = Math.max(1, draft.postage_estimate_window)
  const window = windowOf(batches, n)
  const s = sums(window)
  const unchanged =
    draft.postage_estimate_window === saved.postage_estimate_window &&
    draft.default_postage_estimate === saved.default_postage_estimate &&
    api.window === saved.postage_estimate_window
  // A not-yet-exact default (null) previews as the saved one.
  const local = window.length === 0 ? (draft.default_postage_estimate ?? saved.default_postage_estimate) : roundHalfEven(s.total / s.orders)
  return {
    estimate: unchanged ? api.estimate : local,
    preview: !unchanged,
    used: window.length,
    paid: s.total,
    orders: s.orders,
  }
}

type Props = {
  draft: Draft
  hero: HeroFigure
  windowError: string | null
  defaultError: string | null
  onWindow: (n: number) => void
  onDefault: (n: number | null, error: MoneyInputError | null) => void
  mobile: boolean
}

/** [2] تخمین هزینه پست: N (the stepper), the pre-payments default, and the estimate they give. */
export function PostageCard({ draft, hero, windowError, defaultError, onWindow, onDefault, mobile }: Props) {
  const n = draft.postage_estimate_window
  const setN = (v: number) => onWindow(Math.min(WINDOW_MAX, v))

  const caption = hero.preview ? S.heroPreview(Math.max(1, n)) : mobile ? S.heroCaptionMobile : S.heroCaption
  const detail =
    hero.used === 0
      ? S.noPayments
      : [
          mobile ? S.divisorMobile(hero.paid, hero.orders) : S.divisor(hero.used, hero.paid, hero.orders),
          hero.used < n ? S.fewerThanN(hero.used) : "",
        ]
          .filter(Boolean)
          .join(" ")

  const heroBox = (
    <div className={cn("flex flex-col gap-1 rounded-xl bg-navy-soft px-4 py-3.5", !mobile && "grow")} aria-live="polite">
      <span className={cn("text-[13px]", hero.preview ? "font-bold text-warn" : "text-text-2")}>{caption}</span>
      <span className="flex items-baseline gap-1.5">
        <b className={cn("leading-tight font-bold text-heading tabular-nums", mobile ? "text-[22px]" : "text-[26px]")}>
          <Money value={hero.estimate} unit={false} />
        </b>
        <span className="text-[13px] font-medium">{S.perOrder}</span>
      </span>
      <span className="text-xs text-text-3 tabular-nums">{detail}</span>
    </div>
  )

  const defaultField = (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="st-default-post">{S.defaultPostLabel}</Label>
      <MoneyInput
        id="st-default-post"
        value={draft.default_postage_estimate}
        onValue={(v, error) => onDefault(v ?? null, error)}
        tone={defaultError ? "error" : null}
        className={mobile ? "h-12 text-base" : undefined}
        aria-invalid={defaultError ? true : undefined}
      />
      {draft.default_postage_estimate === null ? null : defaultError ? (
        <InlineMessage severity="error">{defaultError}</InlineMessage>
      ) : (
        <Help>{S.defaultPostHelp}</Help>
      )}
    </div>
  )

  const windowError_ = windowError && <InlineMessage severity="error">{windowError}</InlineMessage>

  if (mobile) {
    return (
      <section id="post" className={cn(cardClass, "flex flex-col gap-3 p-3.5")} aria-labelledby="st2">
        <h2 id="st2" className="text-sm font-bold text-heading">
          {S.postTitle}
        </h2>
        <div className="flex items-center justify-between gap-3">
          <Label>{S.windowLabelMobile}</Label>
          <div className="w-[132px]">
            <Stepper value={n} onValue={setN} size="mobile" inputLabel={S.windowInputAria} tone={windowError ? "error" : null} />
          </div>
        </div>
        {windowError_}
        {heroBox}
        <Help>{S.windowForward}</Help>
        {defaultField}
      </section>
    )
  }

  return (
    <section id="post" className={cn(cardClass, "scroll-mt-6")} aria-labelledby="st2">
      <div className="border-b border-border px-5 py-4">
        <h2 id="st2" className="text-base leading-[26px] font-bold text-heading">
          {S.postTitle}
        </h2>
      </div>
      <div className="flex flex-col gap-5 p-5">
        <div className="flex items-start gap-6">
          <div className="flex w-[260px] shrink-0 flex-col gap-1.5">
            <Label>{S.windowLabel}</Label>
            <div className="w-[140px]">
              <Stepper value={n} onValue={setN} inputLabel={S.windowInputAria} tone={windowError ? "error" : null} />
            </div>
            {windowError_}
            <Help>{S.windowHelp}</Help>
            <Help>{S.windowForward}</Help>
          </div>
          {heroBox}
        </div>
        <div className="max-w-[320px]">{defaultField}</div>
      </div>
    </section>
  )
}
