"use client"

import * as React from "react"
import { ChevronLeft } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { badgeBase } from "@/components/common/status"
import { SaveError } from "@/components/products/drawer-shell"
import { InlineMessage, IntInput, Label, MoneyInput } from "@/components/record-sale/primitives"
import { Money } from "@/components/common/money"
import { ApiError, createPostageBatch, type PostageBatch } from "@/lib/api"
import { dateToISO, formatJalali, utcToLocal } from "@/lib/jalali"
import { formatNumber } from "@/lib/persian-numbers"
import { formatMoney, formatMoneyNumber } from "@/lib/money"
import { cn } from "@/lib/utils"
import { T } from "./copy"
import { project, rateOf } from "./figures"

const currentDay = () => dateToISO(new Date())

export type PaymentFormHandle = { submit: () => void; focus: () => void }

/**
 * «ثبت پرداخت به پست»: date, amount, orders, note, with this payment's rate
 * and the estimate it would produce. The projection uses the API's ordering
 * (figures.project); the saved estimate is re-read from the server.
 */
export const PaymentForm = React.forwardRef<
  PaymentFormHandle,
  {
    batches: PostageBatch[]
    windowSize: number
    currentEstimate: number
    timeZone: string
    mobile: boolean
    onBusyChange: (busy: boolean) => void
    onSaved: () => Promise<void>
  }
>(function PaymentForm({ batches, windowSize, currentEstimate, timeZone, mobile, onBusyChange, onSaved }, ref) {
  /** Integer Rial; null while MoneyInput holds text that gives no exact amount — blocks submit. */
  const [total, setTotal] = React.useState<number | null>(0)
  const [orders, setOrders] = React.useState(0)
  const [note, setNote] = React.useState("")
  // null = today, resolved at submission (a session can cross midnight).
  const [pickedDate, setPickedDate] = React.useState<string | null>(null)
  const [today, setToday] = React.useState(currentDay)
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const totalRef = React.useRef<HTMLInputElement>(null)

  // Keep "today" (the date field's default and its future-day limit) current.
  React.useEffect(() => {
    const t = window.setInterval(() => setToday(currentDay()), 60_000)
    return () => window.clearInterval(t)
  }, [])

  const ordersOk = orders >= 1
  const ordersError = (touched || orders !== 0) && !ordersOk
  const rate = ordersOk && total !== null ? rateOf(total, orders) : null
  const proj = ordersOk && total !== null ? project(batches, windowSize, { total, orders, day: pickedDate }, timeZone) : null
  const delta = proj ? proj.estimate - currentEstimate : 0

  const submit = async () => {
    setTouched(true)
    if (!ordersOk || total === null || busy) return
    setBusy(true)
    onBusyChange(true)
    setError(null)
    try {
      const day = currentDay()
      await createPostageBatch({
        total_paid: total,
        order_count: orders,
        paid_date: pickedDate == null || pickedDate === day ? null : pickedDate,
        notes: note.trim() || null,
      })
      await onSaved()
      setTotal(0)
      setOrders(0)
      setNote("")
      setPickedDate(null)
      setTouched(false)
    } catch (e) {
      setError(
        e instanceof ApiError
          ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `POSTAGE_${e.status}` }
          : { message: String(e), code: "UNKNOWN" }
      )
    } finally {
      setBusy(false)
      onBusyChange(false)
    }
  }

  React.useImperativeHandle(ref, () => ({ submit, focus: () => totalRef.current?.focus() }))

  const shortDay = (utc: string) => {
    const local = utcToLocal(utc, timeZone)
    return local ? formatJalali(local.iso, "yyyy/MM/dd") : utc
  }
  const arithmetic = proj
    ? `(${proj.window.map((b) => formatMoneyNumber(b.total_paid)).join(" + ")}) ÷ (${proj.window
        .map((b) => formatNumber(b.order_count))
        .join(" + ")})${proj.dropped ? T.projDropped(shortDay(proj.dropped.paid_date)) : ""}`
    : null

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-3.5")}>
      {error && <SaveError {...error} />}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pp-date">{mobile ? T.fieldDateMobile : T.fieldDate}</Label>
        <DateField
          id="pp-date"
          value={pickedDate ?? today}
          today={today}
          onChange={(d) => setPickedDate(d === today ? null : d)}
          todayLabel={T.today}
          mobile={mobile}
        />
      </div>
      <div className={cn("grid gap-3", mobile ? "grid-cols-1" : "grid-cols-2")}>
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="pp-total">{T.fieldTotal}</Label>
          <MoneyInput
            ref={totalRef}
            id="pp-total"
            value={total}
            onValue={(v) => setTotal(v ?? null)}
            tone={touched && total === 0 ? "warn" : null}
            className={mobile ? "h-12" : undefined}
          />
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="pp-orders">{T.fieldOrders}</Label>
          <IntInput
            id="pp-orders"
            value={orders}
            onValue={setOrders}
            suffix={T.orderSuffix}
            tone={ordersError ? "error" : null}
            className={mobile ? "h-12" : undefined}
            aria-invalid={ordersError || undefined}
          />
        </div>
      </div>
      {ordersError && <InlineMessage severity="error">{T.ordersError}</InlineMessage>}
      {touched && ordersOk && total === 0 && <InlineMessage severity="warn">{T.totalZero}</InlineMessage>}

      <div className="flex items-center justify-between gap-3 rounded-[10px] bg-surface-2 p-3 text-[13px]">
        <span className="text-text-2">{T.rateLabel}</span>
        <b className="text-lg tabular-nums">{rate == null ? "—" : formatMoney(rate)}</b>
      </div>

      <div className="flex flex-col gap-2 rounded-[10px] border border-border p-3">
        <span className="text-xs font-bold text-text-3">{mobile ? T.projLabelMobile : T.projLabel}</span>
        <span className="flex flex-wrap items-center gap-2">
          <Money value={currentEstimate} className="text-[17px] text-text-2" />
          {/* current → after in reading order: in RTL the chevron points left. */}
          <ChevronLeft className="size-[18px] text-text-3" aria-hidden />
          <b className="text-[22px]">
            <Money value={proj ? proj.estimate : currentEstimate} />
          </b>
          <span className={cn(badgeBase, "tabular-nums", delta > 0 ? "bg-warn-soft text-warn" : "bg-profit-soft text-profit")}>
            {delta >= 0 ? "+" : ""}
            {formatMoney(delta)}
          </span>
        </span>
        {proj?.outside ? (
          <span className="text-xs text-text-3">{T.projOutside}</span>
        ) : (
          arithmetic && <span className="text-xs leading-[1.8] text-text-3 tabular-nums">{arithmetic}</span>
        )}
        <span className="text-xs text-text-3">{T.projNote}</span>
      </div>

      {!mobile && (
        <>
          <p className="text-xs leading-[1.8] text-text-3">{T.help}</p>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pp-note" optional>
              {T.fieldNote}
            </Label>
            <input
              id="pp-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={T.notePlaceholder}
              className="h-10 w-full min-w-0 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30"
            />
          </div>
        </>
      )}
    </div>
  )
})
