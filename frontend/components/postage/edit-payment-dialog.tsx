"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { closedDayMessage } from "@/components/common/copy"
import { DrawerShell, SaveError } from "@/components/products/drawer-shell"
import { Btn, Help, InlineMessage, IntInput, Label, MoneyInput } from "@/components/record-sale/primitives"
import { ApiError, updatePostageBatch, type PostageBatch } from "@/lib/api"
import { closedDay, isFutureDateError, postagePatch } from "@/lib/expense-edit"
import { formatJalali, utcToLocal } from "@/lib/jalali"
import { T } from "./copy"

/**
 * «ویرایش پرداخت به پست»: date, amount, orders, note of a saved payment; only the changed fields are sent.
 * A refusal for a closed day (a profit payout covers it) is shown in full; the screen re-reads the estimate after saving.
 */
export function EditPaymentDialog({
  batch,
  today,
  timeZone,
  mobile,
  onClose,
  onSaved,
}: {
  /** The payment being edited; null = closed. */
  batch: PostageBatch | null
  today: string
  timeZone: string
  mobile: boolean
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const open = batch != null
  const savedDay = batch ? (utcToLocal(batch.paid_date, timeZone)?.iso ?? today) : today
  const [day, setDay] = React.useState(today)
  /** Integer Rial; null while MoneyInput holds text that gives no exact amount — blocks saving. */
  const [total, setTotal] = React.useState<number | null>(0)
  const [orders, setOrders] = React.useState(0)
  const [note, setNote] = React.useState("")
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const [dateError, setDateError] = React.useState<string | null>(null)

  const [shownId, setShownId] = React.useState<number | null>(null)
  if (batch && shownId !== batch.id) {
    setShownId(batch.id)
    setDay(savedDay)
    setTotal(batch.total_paid)
    setOrders(batch.order_count)
    setNote(batch.notes ?? "")
    setTouched(false)
    setError(null)
    setDateError(null)
  } else if (!batch && shownId !== null) {
    setShownId(null)
  }

  const ordersOk = orders >= 1
  const ordersError = touched && !ordersOk

  const close = () => {
    if (!busy) onClose()
  }

  const submit = async () => {
    setTouched(true)
    setError(null)
    setDateError(null)
    if (!batch || busy || !ordersOk || total === null) return
    const patch = postagePatch(
      { total: batch.total_paid, orders: batch.order_count, note: batch.notes ?? "", day: savedDay },
      { total, orders, note, day }
    )
    if (!patch) {
      setError({ message: T.nothingChanged, code: "NO_CHANGE" })
      return
    }
    setBusy(true)
    try {
      await updatePostageBatch(batch.id, patch)
      await onSaved()
    } catch (e) {
      const closed = e instanceof ApiError ? closedDay(e) : null
      if (closed) {
        setError({ message: closedDayMessage(formatJalali(closed.periodEnd, "yyyy/MM/dd")), code: "PERIOD_ALREADY_DISTRIBUTED" })
      } else if (e instanceof ApiError && isFutureDateError(e, "paid_date")) {
        setDateError(T.futureDate)
      } else if (e instanceof ApiError && e.status === 404) {
        setError({ message: T.gone, code: "POSTAGE_404" })
      } else {
        setError(
          e instanceof ApiError
            ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `POSTAGE_${e.status}` }
            : { message: String(e), code: "UNKNOWN" }
        )
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <DrawerShell
      open={open}
      onOpenChange={(o) => !o && close()}
      mobile={mobile}
      title={T.editTitle}
      busy={busy}
      footer={
        <>
          <Btn variant="primary" size={mobile ? "lg" : "md"} className={mobile ? "grow" : undefined} disabled={busy} aria-busy={busy || undefined} onClick={submit}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {T.save}
          </Btn>
          <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={close}>
            {T.cancel}
          </Btn>
        </>
      }
    >
      {error && <SaveError {...error} />}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ep-date">{T.fieldDate}</Label>
        <DateField id="ep-date" value={day} today={today} onChange={setDay} todayLabel={T.today} mobile={mobile} />
        {dateError && <InlineMessage severity="error">{dateError}</InlineMessage>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ep-total">{T.fieldTotal}</Label>
        <MoneyInput id="ep-total" value={total} onValue={(v) => setTotal(v ?? null)} className={mobile ? "h-12" : undefined} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ep-orders">{T.fieldOrders}</Label>
        <IntInput
          id="ep-orders"
          value={orders}
          onValue={setOrders}
          suffix={T.orderSuffix}
          tone={ordersError ? "error" : null}
          className={mobile ? "h-12" : undefined}
          aria-invalid={ordersError || undefined}
        />
        {ordersError && <InlineMessage severity="error">{T.ordersError}</InlineMessage>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ep-note" optional>
          {T.fieldNote}
        </Label>
        <input
          id="ep-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={T.notePlaceholder}
          className="h-10 w-full min-w-0 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30"
        />
      </div>
      <Help>{T.editNote}</Help>
    </DrawerShell>
  )
}
