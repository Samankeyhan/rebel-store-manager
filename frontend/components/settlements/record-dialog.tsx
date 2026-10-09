"use client"

import * as React from "react"
import { Loader2, X } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { Money } from "@/components/common/money"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { DrawerShell, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Alert, Btn, Help, InlineMessage, Label, MoneyInput } from "@/components/record-sale/primitives"
import { ApiError, createSettlement, type PendingMethod, type PendingMonthGroup, type Settlement, type SettlementCreate } from "@/lib/api"
import {
  classifySettlementError,
  differenceKind,
  groupTitle,
  previewDifference,
  settlementErrorField,
  settlementErrorRefreshes,
} from "@/lib/settlements"
import { cn } from "@/lib/utils"
import { S, differenceText, settlementErrorText } from "./copy"

/** What «ثبت تسویه» settles: chosen orders (IMMEDIATE / DAYS_AFTER) or one whole Jalali month. */
export type RecordTarget =
  | { kind: "orders"; method: PendingMethod; orderIds: number[]; /** preview: Σ expected_amount, null if unsafe */ expected: number | null }
  | { kind: "month"; method: PendingMethod; group: PendingMonthGroup }

type Field = "settled_date" | "amount_received"

export const differenceTone = (difference: number) => {
  const kind = differenceKind(difference)
  return kind === "over" ? "text-profit" : kind === "under" ? "text-loss" : "text-text-2"
}

/**
 * «ثبت تسویه» (no design; the expense-dialog precedent): desktop a 500px
 * dialog, mobile a bottom sheet. The amount received starts empty so the
 * owner types what the bank shows. The expected amount and the difference
 * shown here are previews; the saved values come back from POST /settlements.
 * Never closes on an error.
 */
export function RecordDialog({
  target,
  today,
  mobile,
  onClose,
  onSaved,
  onStale,
}: {
  target: RecordTarget | null
  today: string
  mobile: boolean
  onClose: () => void
  onSaved: (settlement: Settlement) => void
  /** The pending list is stale (settled or changed meanwhile): refetch it. */
  onStale: () => void
}) {
  /** Integer Rial; undefined = empty; null = text that gives no exact amount (MoneyInput says why). */
  const [amount, setAmount] = React.useState<number | null | undefined>(undefined)
  const [date, setDate] = React.useState(today)
  const [note, setNote] = React.useState("")
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [fieldErrors, setFieldErrors] = React.useState<Partial<Record<Field, string>>>({})
  const [alert, setAlert] = React.useState<{ text: string; refreshed: boolean } | null>(null)
  const [saveError, setSaveError] = React.useState<{ message: string; code: string } | null>(null)

  // Keep the last target while the dialog animates closed.
  const [shown, setShown] = React.useState<RecordTarget | null>(null)
  if (target && target !== shown) {
    setShown(target)
    setAmount(undefined)
    setDate(today)
    setNote("")
    setTouched(false)
    setFieldErrors({})
    setAlert(null)
    setSaveError(null)
  }
  const t = target ?? shown
  if (!t) return null

  const open = target != null
  const expected = t.kind === "month" ? t.group.expected_amount : t.expected
  const difference = previewDifference(amount, expected)
  const amountError = fieldErrors.amount_received || (touched && amount === undefined ? S.receivedRequired : null)

  const close = () => {
    if (!busy) onClose()
  }

  const submit = async () => {
    setTouched(true)
    setFieldErrors({})
    setAlert(null)
    setSaveError(null)
    if (busy || amount == null) return
    const trimmed = note.trim()
    const body: SettlementCreate = {
      payment_method_id: t.method.payment_method_id,
      settled_date: date,
      amount_received: amount,
      ...(trimmed ? { note: trimmed } : {}),
      ...(t.kind === "orders"
        ? { order_ids: t.orderIds }
        : { jalali_year: t.group.jalali_year, jalali_month: t.group.jalali_month }),
    }
    setBusy(true)
    try {
      onSaved(await createSettlement(body))
    } catch (e) {
      const c = e instanceof ApiError ? classifySettlementError(e) : null
      if (c) {
        const field = settlementErrorField(c)
        if (field) setFieldErrors({ [field]: settlementErrorText(c) })
        else {
          const refreshes = settlementErrorRefreshes(c)
          if (refreshes) onStale()
          // «raced» already says the list was refreshed.
          setAlert({ text: settlementErrorText(c), refreshed: refreshes && c.kind !== "raced" })
        }
      } else if (e instanceof ApiError && e.status === 0) {
        setSaveError({ message: S.errorBody, code: "NET_TIMEOUT" })
      } else {
        setSaveError(
          e instanceof ApiError
            ? { message: e.message, code: `SETTLEMENTS_${e.status}` }
            : { message: String(e), code: "UNKNOWN" }
        )
      }
    } finally {
      setBusy(false)
    }
  }

  const summary = (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-[10px] bg-surface-2 px-4 py-3 text-[13px]">
      <dt className="text-text-3">{S.method}</dt>
      <dd className="font-semibold">{t.method.name}</dd>
      <dt className="text-text-3">{S.period}</dt>
      <dd className="font-semibold">{t.kind === "month" ? groupTitle(t.group) : S.orders(t.orderIds.length)}</dd>
      <dt className="text-text-3">{S.expected}</dt>
      <dd className="flex flex-wrap items-center gap-2">
        {expected === null ? (
          <span className="text-loss">{S.totalTooLarge}</span>
        ) : (
          <Money value={expected} className="font-bold" />
        )}
        {t.kind === "orders" && (
          <span className="rounded-md bg-card px-1.5 py-0.5 text-[11px] text-text-3">{S.preview}</span>
        )}
      </dd>
    </dl>
  )

  const fields = (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-3.5")}>
      {saveError && <SaveError {...saveError} />}
      {alert && (
        <Alert tone="err">
          <div>{alert.text}</div>
          {alert.refreshed && <div className="mt-1 text-xs text-text-3">{S.listRefreshed}</div>}
        </Alert>
      )}
      {summary}
      {t.kind === "month" && <Help>{S.monthlyHelp}</Help>}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="sr-amount">{S.received}</Label>
        <MoneyInput
          id="sr-amount"
          allowEmpty
          value={amount}
          onValue={(n) => {
            setAmount(n)
            setFieldErrors((f) => ({ ...f, amount_received: undefined }))
          }}
          tone={amountError ? "error" : null}
          aria-invalid={!!amountError || undefined}
          className={mobile ? "h-12" : undefined}
        />
        {amount === null ? null : amountError ? (
          <InlineMessage severity="error">{amountError}</InlineMessage>
        ) : (
          <Help>{S.receivedHelp}</Help>
        )}
      </div>
      {difference !== null && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-border px-4 py-2.5 text-[13px]">
          <span className="text-text-3">{S.differencePreview}</span>
          <b className={differenceTone(difference)}>{differenceText(difference)}</b>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="sr-date">{S.settledDate}</Label>
        <DateField
          id="sr-date"
          value={date}
          today={today}
          onChange={(d) => {
            setDate(d)
            setFieldErrors((f) => ({ ...f, settled_date: undefined }))
          }}
          todayLabel={S.today}
          mobile={mobile}
        />
        {fieldErrors.settled_date && <InlineMessage severity="error">{fieldErrors.settled_date}</InlineMessage>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="sr-note" optional>
          {S.note}
        </Label>
        <input id="sr-note" value={note} onChange={(e) => setNote(e.target.value)} className={textInputClass(mobile)} />
      </div>
    </div>
  )

  const submitBtn = (
    <Btn
      variant="primary"
      size={mobile ? "lg" : "md"}
      className={mobile ? "grow" : undefined}
      disabled={busy}
      aria-busy={busy || undefined}
      onClick={submit}
    >
      {busy && <Loader2 className="size-4 animate-spin" />}
      {S.settle}
    </Btn>
  )
  const cancelBtn = (
    <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={close}>
      {S.cancel}
    </Btn>
  )

  if (mobile) {
    return (
      <DrawerShell
        open={open}
        onOpenChange={(o) => !o && close()}
        mobile
        title={S.recordTitle}
        busy={busy}
        footer={
          <>
            {submitBtn}
            {cancelBtn}
          </>
        }
      >
        {fields}
      </DrawerShell>
    )
  }

  return (
    <SettlementDialogFrame open={open} title={S.recordTitle} description={S.receivedHelp} busy={busy} onClose={close} footer={<>{submitBtn}{cancelBtn}</>}>
      {fields}
    </SettlementDialogFrame>
  )
}

/** The desktop 500px dialog frame shared by the record and edit dialogs (expense-dialog look). */
export function SettlementDialogFrame({
  open,
  title,
  description,
  busy,
  onClose,
  footer,
  children,
}: {
  open: boolean
  title: string
  description: string
  busy: boolean
  onClose: () => void
  footer: React.ReactNode
  children: React.ReactNode
}) {
  const id = React.useId()
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        showCloseButton={false}
        aria-labelledby={id}
        style={{ maxWidth: "min(500px, calc(100% - 2rem))" }}
        className="w-full gap-0 overflow-hidden rounded-[14px] border border-border bg-card p-0 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)] ring-0 sm:max-w-none"
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <DialogTitle id={id} className="text-base font-bold text-heading">
            {title}
          </DialogTitle>
          <DialogDescription className="sr-only">{description}</DialogDescription>
          <Btn variant="ghost" size="sm" className="size-8 px-0" aria-label={S.close} disabled={busy} onClick={onClose}>
            <X className="size-4" />
          </Btn>
        </div>
        <div className="flex max-h-[70vh] flex-col overflow-y-auto px-6 py-5">{children}</div>
        <div className="flex justify-start gap-2 border-t border-border bg-surface-2 px-6 py-4">{footer}</div>
      </DialogContent>
    </Dialog>
  )
}
