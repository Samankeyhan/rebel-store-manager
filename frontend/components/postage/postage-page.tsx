"use client"

import * as React from "react"
import Link from "next/link"
import { Check, Loader2, Plus, Truck } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { badgeBase } from "@/components/common/status"
import { Toast } from "@/components/common/toast"
import { DateRangePopover } from "@/components/orders/list/date-range-popover"
import { CHANNEL_IDS, CHANNELS } from "@/components/record-sale/copy"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import type { PostageBatch, Settings } from "@/lib/api"
import { formatJalali, presetRange, utcToLocal, wholeMonthLabel, type IsoRange } from "@/lib/jalali"
import { formatNumber } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { T } from "./copy"
import { rateOf, sums, windowOf } from "./figures"
import { PaymentForm, type PaymentFormHandle } from "./payment-form"
import { usePostageData } from "./use-postage-data"

/** «وب‌سایت، اینستاگرام و عمده‌فروشی»: the channels the estimate applies to. */
function postageChannels(settings: Settings): string {
  const names = CHANNEL_IDS.filter((c) => settings.channels[c]?.applies_postage === 1).map((c) => CHANNELS[c].name)
  if (names.length <= 1) return names.join("")
  return `${names.slice(0, -1).join(T.listSep)}${T.and}${names[names.length - 1]}`
}

/**
 * هزینه‌های ارسال (design 09): the store-wide postage estimate — always the
 * API's number, with its arithmetic rebuilt from the payments it uses — the
 * form to record a bulk payment, and the payments ledger.
 */
export function PostagePage() {
  const mobile = useIsMobile()
  const { state, reload, refresh } = usePostageData()
  const [now] = React.useState(() => new Date())
  const defaultRange = React.useMemo(() => presetRange("thisYear", now), [now])
  const [range, setRange] = React.useState<IsoRange>(defaultRange)
  const [busy, setBusy] = React.useState(false)
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])
  const formRef = React.useRef<PaymentFormHandle>(null)

  if (state.status === "loading") return <LoadingBlock mobile={mobile} label={T.loadingAria} />
  if (state.status === "error")
    return (
      <ErrorBlock
        title={mobile ? T.errorTitleMobile : T.errorTitle}
        body={T.errorBody}
        retry={T.retry}
        onRetry={reload}
        mobile={mobile}
      />
    )

  const { batches, estimate, settings } = state
  const tz = settings.timezone || "Asia/Tehran"
  const inWindow = windowOf(batches, estimate.window)
  const inWindowIds = new Set(inWindow.map((b) => b.id))
  const windowSums = sums(inWindow)
  const day = (utc: string) => {
    const local = utcToLocal(utc, tz)
    return local ? formatJalali(local.iso, "yyyy/MM/dd") : utc
  }

  // ---------------------------------------------------------------- hero
  const hero = (
    <section
      aria-labelledby="est"
      className={cn(cardClass, "flex flex-wrap items-center gap-7 border-transparent bg-navy-soft", mobile ? "p-4" : "px-6 py-5")}
    >
      <div className="flex min-w-[280px] flex-col gap-1">
        <span id="est" className={cn("font-bold text-heading", mobile ? "text-xs" : "text-[13px]")}>
          {mobile ? T.heroLabelMobile : T.heroLabel}
        </span>
        <span className="flex items-baseline gap-2">
          <b className={cn("tabular-nums", mobile ? "text-[30px] leading-[42px]" : "text-4xl leading-[48px]")}>
            {formatNumber(estimate.estimate)}
          </b>
          <span className={cn("font-medium", mobile ? "text-[13px]" : "text-sm")}>{mobile ? T.toman : T.perOrder}</span>
        </span>
        {inWindow.length === 0 ? (
          <span className="text-[13px] text-text-3">{T.heroDefault}</span>
        ) : mobile ? (
          <span className="text-xs text-text-3 tabular-nums">
            {T.heroCaptionMobile(windowSums.total, windowSums.orders, inWindow.length)}
          </span>
        ) : (
          <>
            <span className="text-[13px] text-text-3">{T.heroCaption(inWindow.length, postageChannels(settings))}</span>
            <span className="mt-1 self-start rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs tabular-nums">
              {`(${inWindow.map((b) => formatNumber(b.total_paid)).join(" + ")}) ÷ (${inWindow
                .map((b) => formatNumber(b.order_count))
                .join(" + ")}) = ${formatNumber(windowSums.total)} ÷ ${formatNumber(windowSums.orders)}`}
            </span>
            <span className="text-xs text-text-3">{T.heroNotAverage}</span>
          </>
        )}
      </div>
      {!mobile && inWindow.length > 0 && (
        <div className="flex grow gap-2.5">
          {inWindow.map((b) => (
            <div key={b.id} className={cn(cardClass, "flex flex-1 flex-col px-3 py-2.5")}>
              <span className="text-xs text-text-3 tabular-nums">{day(b.paid_date)}</span>
              <b className="tabular-nums">{formatNumber(rateOf(b.total_paid, b.order_count))}</b>
              <span className="text-xs text-text-3 tabular-nums">
                {formatNumber(b.total_paid)} ÷ {formatNumber(b.order_count)}
              </span>
            </div>
          ))}
        </div>
      )}
      {!mobile && (
        <Link href="/settings" className="text-xs font-bold whitespace-nowrap text-heading hover:text-primary">
          {T.windowLink(estimate.window)}
        </Link>
      )}
    </section>
  )

  // ---------------------------------------------------------------- form
  const form = (
    <PaymentForm
      ref={formRef}
      batches={batches}
      windowSize={estimate.window}
      currentEstimate={estimate.estimate}
      timeZone={tz}
      mobile={mobile}
      onBusyChange={setBusy}
      onSaved={async () => {
        const next = await refresh().catch(() => {
          reload()
          return null
        })
        if (next) setToast(T.toastSaved(next.estimate))
      }}
    />
  )

  // ---------------------------------------------------------------- ledger
  const rows = batches.filter((b) => {
    const local = utcToLocal(b.paid_date, tz)?.iso
    return !local || (local >= range.from && local <= range.to)
  })
  const empty = batches.length === 0

  const ledgerEmpty = (
    <StateShell
      icon={Truck}
      mobile={mobile}
      title={mobile ? T.emptyTitleMobile : T.emptyTitle}
      body={mobile ? T.emptyBodyMobile : T.emptyBody}
      action={
        !mobile && (
          <Btn variant="primary" className="mt-1.5" onClick={() => formRef.current?.focus()}>
            <Plus className="size-4" />
            {T.emptyCta}
          </Btn>
        )
      }
    />
  )

  if (mobile) {
    return (
      <div className="flex flex-col gap-3 pb-24">
        {hero}
        <section className={cn(cardClass, "flex flex-col gap-3 p-3.5")}>
          <h3 className="text-sm font-bold text-heading">{T.formTitle}</h3>
          {form}
        </section>
        {empty ? (
          ledgerEmpty
        ) : (
          <>
            <h3 className="text-sm font-bold text-heading">{T.recent}</h3>
            {batches.slice(0, 5).map((b) => (
              <div key={b.id} className={cn(cardClass, "flex items-center justify-between gap-3 px-3.5 py-3")}>
                <span className="flex flex-col">
                  <b className="tabular-nums">{formatNumber(b.total_paid)}</b>
                  <span className="text-xs text-text-3 tabular-nums">{T.recentMeta(day(b.paid_date), b.order_count)}</span>
                </span>
                <span className="text-sm tabular-nums">{T.recentRate(rateOf(b.total_paid, b.order_count))}</span>
              </div>
            ))}
          </>
        )}
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
          <Btn variant="primary" size="lg" className="w-full" disabled={busy} onClick={() => formRef.current?.submit()}>
            {busy ? <Loader2 className="size-[18px] animate-spin" /> : <Check className="size-[18px]" />}
            {T.submit}
          </Btn>
        </div>
        {toast && <Toast title={toast} onClose={closeToast} closeLabel={T.close} />}
      </div>
    )
  }

  const month = wholeMonthLabel(range)
  const footer = sums(rows)
  const ledger = (
    <section className={cn(cardClass, "min-w-0 grow overflow-hidden")} aria-labelledby="pl">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <h2 id="pl" className="text-base font-bold text-heading">
          {T.ledgerTitle}
        </h2>
        <DateRangePopover value={range} onApply={setRange} />
      </div>
      {rows.length === 0 ? (
        <p className="px-5 py-10 text-center text-[13px] text-text-3">{T.noMatch}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col">{T.colDate}</th>
                <th scope="col" className="text-end!">
                  {T.colTotal}
                </th>
                <th scope="col" className="text-end!">
                  {T.colOrders}
                </th>
                <th scope="col" className="text-end!">
                  {T.colRate}
                </th>
                <th scope="col" className="w-full">
                  <span className="sr-only">{T.inWindow}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((b: PostageBatch) => {
                const current = inWindowIds.has(b.id)
                return (
                  <tr
                    key={b.id}
                    title={b.notes ?? undefined}
                    className="[&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
                  >
                    <td className={cn("tabular-nums", !current && "text-text-3")}>{day(b.paid_date)}</td>
                    <td className="text-end font-bold tabular-nums">{formatNumber(b.total_paid)}</td>
                    <td className="text-end tabular-nums">{formatNumber(b.order_count)}</td>
                    <td className="text-end tabular-nums">{formatNumber(rateOf(b.total_paid, b.order_count))}</td>
                    <td>
                      <span className="flex items-center gap-2">
                        {current && <span className={cn(badgeBase, "bg-info-soft text-info")}>{T.inWindow}</span>}
                        {b.notes && <span className="truncate text-xs text-text-3">{b.notes}</span>}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr className="font-bold [&>td]:h-[52px] [&>td]:bg-surface-2 [&>td]:px-4">
                <td>{month ? T.footerMonth(month) : T.footerRange}</td>
                <td className="text-end tabular-nums">{formatNumber(footer.total)}</td>
                <td className="text-end tabular-nums">{formatNumber(footer.orders)}</td>
                <td className="text-end tabular-nums">{formatNumber(rateOf(footer.total, footer.orders))}</td>
                <td className="text-xs font-normal text-text-3">{T.footerNote}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </section>
  )

  return (
    <div className="flex flex-col gap-5">
      {hero}
      <div className="flex items-start gap-6">
        <section className={cn(cardClass, "w-[420px] shrink-0")} aria-labelledby="nf">
          <div className="border-b border-border px-5 py-4">
            <h2 id="nf" className="text-base font-bold text-heading">
              {T.formTitle}
            </h2>
          </div>
          <div className="flex flex-col gap-3.5 p-5">
            {form}
            <Btn variant="primary" className="self-start" disabled={busy} aria-busy={busy || undefined} onClick={() => formRef.current?.submit()}>
              {busy && <Loader2 className="size-4 animate-spin" />}
              {T.submit}
            </Btn>
          </div>
        </section>
        {empty ? <div className="min-w-0 grow">{ledgerEmpty}</div> : ledger}
      </div>
      {toast && <Toast title={toast} onClose={closeToast} closeLabel={T.close} />}
    </div>
  )
}
