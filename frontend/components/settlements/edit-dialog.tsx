"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { Money } from "@/components/common/money"
import { DrawerShell, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Alert, Btn, Help, InlineMessage, Label, MoneyInput } from "@/components/record-sale/primitives"
import { ApiError, updateSettlement, type Settlement, type SettlementListItem } from "@/lib/api"
import { classifySettlementError, jalaliMonthTitle, previewDifference, settlementErrorField, settlementPatch } from "@/lib/settlements"
import { cn } from "@/lib/utils"
import { S, differenceText, settlementErrorText } from "./copy"
import { SettlementDialogFrame, differenceTone } from "./record-dialog"

type Field = "settled_date" | "amount_received"

/**
 * «ویرایش تسویه»: amount received, settled date and note only (which orders
 * a settlement holds, and its expected amount, never change). Sends only the
 * changed fields; the row is replaced from the response.
 */
export function EditDialog({
  settlement,
  today,
  mobile,
  onClose,
  onSaved,
}: {
  settlement: SettlementListItem | null
  today: string
  mobile: boolean
  onClose: () => void
  onSaved: (saved: Settlement) => void
}) {
  const [amount, setAmount] = React.useState<number | null | undefined>(0)
  const [date, setDate] = React.useState(today)
  const [note, setNote] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [fieldErrors, setFieldErrors] = React.useState<Partial<Record<Field, string>>>({})
  const [alert, setAlert] = React.useState<string | null>(null)
  const [saveError, setSaveError] = React.useState<{ message: string; code: string } | null>(null)

  const [shown, setShown] = React.useState<SettlementListItem | null>(null)
  if (settlement && settlement !== shown) {
    setShown(settlement)
    setAmount(settlement.amount_received)
    setDate(settlement.settled_date)
    setNote(settlement.note ?? "")
    setFieldErrors({})
    setAlert(null)
    setSaveError(null)
  }
  const s = settlement ?? shown
  if (!s) return null

  const open = settlement != null
  const difference = previewDifference(amount, s.expected_amount)

  const close = () => {
    if (!busy) onClose()
  }

  const submit = async () => {
    setFieldErrors({})
    setAlert(null)
    setSaveError(null)
    if (busy || amount == null) return
    const patch = settlementPatch(s, { amount, date, note })
    if (Object.keys(patch).length === 0) {
      onClose()
      return
    }
    setBusy(true)
    try {
      onSaved(await updateSettlement(s.id, patch))
    } catch (e) {
      const c = e instanceof ApiError ? classifySettlementError(e) : null
      if (c) {
        const field = settlementErrorField(c)
        if (field) setFieldErrors({ [field]: settlementErrorText(c) })
        else setAlert(settlementErrorText(c))
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

  const fields = (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-3.5")}>
      {saveError && <SaveError {...saveError} />}
      {alert && <Alert tone="err">{alert}</Alert>}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-[10px] bg-surface-2 px-4 py-3 text-[13px]">
        <dt className="text-text-3">{S.method}</dt>
        <dd className="font-semibold">{s.payment_method_name}</dd>
        <dt className="text-text-3">{S.period}</dt>
        <dd className="font-semibold">
          {s.jalali_year != null && s.jalali_month != null ? jalaliMonthTitle(s.jalali_year, s.jalali_month) : S.orders(s.order_count)}
        </dd>
        <dt className="text-text-3">{S.expected}</dt>
        <dd>
          <Money value={s.expected_amount} className="font-bold" />
        </dd>
      </dl>
      <Help>{S.editHelp}</Help>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="se-amount">{S.received}</Label>
        <MoneyInput
          id="se-amount"
          value={amount}
          onValue={(n) => {
            setAmount(n)
            setFieldErrors((f) => ({ ...f, amount_received: undefined }))
          }}
          tone={fieldErrors.amount_received ? "error" : null}
          aria-invalid={!!fieldErrors.amount_received || undefined}
          className={mobile ? "h-12" : undefined}
        />
        {fieldErrors.amount_received && <InlineMessage severity="error">{fieldErrors.amount_received}</InlineMessage>}
      </div>
      {difference !== null && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-border px-4 py-2.5 text-[13px]">
          <span className="text-text-3">{S.differencePreview}</span>
          <b className={differenceTone(difference)}>{differenceText(difference)}</b>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="se-date">{S.settledDate}</Label>
        <DateField
          id="se-date"
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
        <Label htmlFor="se-note" optional>
          {S.note}
        </Label>
        <input id="se-note" value={note} onChange={(e) => setNote(e.target.value)} className={textInputClass(mobile)} />
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
      {S.save}
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
        title={S.editTitle}
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
    <SettlementDialogFrame
      open={open}
      title={S.editTitle}
      description={S.editHelp}
      busy={busy}
      onClose={close}
      footer={
        <>
          {submitBtn}
          {cancelBtn}
        </>
      }
    >
      {fields}
    </SettlementDialogFrame>
  )
}
