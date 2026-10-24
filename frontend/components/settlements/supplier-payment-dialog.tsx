"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { ItemPicker, type PickerItem } from "@/components/common/item-picker"
import { Money } from "@/components/common/money"
import { DrawerShell, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { METHOD_LABELS, METHOD_ORDER } from "@/components/purchases/copy"
import { Alert, Btn, Help, InlineMessage, Label, MoneyInput } from "@/components/record-sale/primitives"
import {
  ApiError,
  createSupplierPayment,
  getAllocationPreview,
  updateSupplierPayment,
  type PayablesSupplier,
  type SupplierPayment,
  type SupplierPaymentMethod,
} from "@/lib/api"
import { formatJalali, utcToLocal } from "@/lib/jalali"
import { formatMoney } from "@/lib/money"
import { allocatedTotal, allocationProblem, allocationsBody, classifyPayablesError } from "@/lib/payables"
import { cn } from "@/lib/utils"
import { P, S } from "./copy"
import { SettlementDialogFrame } from "./record-dialog"

type Line = {
  key: string
  purchase_kind: "MATERIAL" | "PRODUCT"
  purchase_id: number
  label: string
  outstanding: number
  amount: number | null
}

const methodItems: PickerItem[] = METHOD_ORDER.map((m, i) => ({ id: i + 1, name: METHOD_LABELS[m] }))

function MethodPicker({ id, value, onChange, mobile }: { id: string; value: SupplierPaymentMethod; onChange: (m: SupplierPaymentMethod) => void; mobile: boolean }) {
  return (
    <ItemPicker
      id={id}
      items={methodItems}
      value={METHOD_ORDER.indexOf(value as (typeof METHOD_ORDER)[number]) + 1}
      onPick={(i) => onChange(METHOD_ORDER[i - 1] ?? "OTHER")}
      placeholder={P.method}
      searchLabel={P.searchMethod}
      emptyText={P.method}
      noMatchText={() => P.method}
      mobile={mobile}
    />
  )
}

/** The Persian text of a payables refusal, and whether it belongs under the date field. */
function refusalText(e: ApiError): { text: string; field: "date" | "amount" | null } {
  const c = classifyPayablesError(e)
  switch (c.kind) {
    case "exceeds_due":
      return { text: P.exceedsDue, field: null }
    case "exceeds_balance":
      return { text: P.exceedsBalance(c.outstanding != null ? formatMoney(c.outstanding) : null), field: "amount" }
    case "supplier_mismatch":
      return { text: P.supplierMismatch, field: null }
    case "allocation_mismatch":
      return { text: P.mismatch, field: null }
    case "before_purchase":
      return { text: P.beforePurchase(c.purchaseDate), field: "date" }
    case "date_in_future":
      return { text: P.dateFuture, field: "date" }
    case "not_found":
      return { text: P.notFound, field: null }
    case "amount_too_large":
      return { text: P.tooLarge, field: "amount" }
    default:
      return { text: e.message, field: null }
  }
}

function Shell({
  open,
  mobile,
  title,
  description,
  busy,
  onClose,
  footer,
  children,
}: {
  open: boolean
  mobile: boolean
  title: string
  description: string
  busy: boolean
  onClose: () => void
  footer: React.ReactNode
  children: React.ReactNode
}) {
  if (mobile)
    return (
      <DrawerShell open={open} onOpenChange={(o) => !o && onClose()} mobile title={title} busy={busy} footer={footer}>
        {children}
      </DrawerShell>
    )
  return (
    <SettlementDialogFrame open={open} title={title} description={description} busy={busy} onClose={onClose} footer={footer}>
      {children}
    </SettlementDialogFrame>
  )
}

/**
 * «ثبت پرداخت» to one supplier: amount (default = everything owed), day, method, reference, note, and the split over
 * its unpaid purchases. The split starts oldest first from the server (GET /payables/allocation-preview) and every
 * line can be changed; the lines must add up to the amount. Nothing here computes what is owed: the figures come from
 * /payables, and the server decides (db/supplier_payments.py).
 */
export function SupplierPaymentDialog({
  supplier,
  today,
  timeZone,
  mobile,
  onClose,
  onSaved,
}: {
  supplier: PayablesSupplier | null
  today: string
  timeZone: string
  mobile: boolean
  onClose: () => void
  onSaved: (payment: SupplierPayment) => void
}) {
  const [amount, setAmount] = React.useState<number | null>(0)
  const [date, setDate] = React.useState(today)
  const [method, setMethod] = React.useState<SupplierPaymentMethod>("CARD")
  const [reference, setReference] = React.useState("")
  const [note, setNote] = React.useState("")
  const [lines, setLines] = React.useState<Line[]>([])
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [fieldError, setFieldError] = React.useState<{ field: "date" | "amount"; text: string } | null>(null)
  const [alert, setAlert] = React.useState<string | null>(null)
  const [saveError, setSaveError] = React.useState<{ message: string; code: string } | null>(null)

  const fillOldestFirst = React.useCallback(
    async (s: PayablesSupplier, value: number | null) => {
      if (value === null || value <= 0) return
      try {
        const plan = await getAllocationPreview(s.supplier_id, value)
        setLines((ls) => ls.map((l) => ({ ...l, amount: plan.find((p) => p.purchase_kind === l.purchase_kind && p.purchase_id === l.purchase_id)?.amount ?? 0 })))
      } catch (e) {
        if (e instanceof ApiError) setFieldError({ field: "amount", text: refusalText(e).text })
      }
    },
    []
  )

  const [shown, setShown] = React.useState<PayablesSupplier | null>(null)
  if (supplier && supplier !== shown) {
    setShown(supplier)
    setAmount(supplier.outstanding)
    setDate(today)
    setMethod("CARD")
    setReference("")
    setNote("")
    // everything owed, oldest first: each purchase gets what it still owes
    setLines(
      supplier.open_purchases.map((p) => ({
        key: `${p.purchase_kind}-${p.purchase_id}`,
        purchase_kind: p.purchase_kind,
        purchase_id: p.purchase_id,
        label: `${p.item_name} · ${p.invoice_number ?? ""} · ${dayOf(p.purchase_date, timeZone)}`,
        outstanding: p.outstanding,
        amount: p.outstanding,
      }))
    )
    setTouched(false)
    setFieldError(null)
    setAlert(null)
    setSaveError(null)
  }
  const s = supplier ?? shown
  if (!s) return null
  const open = supplier != null
  const problem = allocationProblem(amount, lines)
  const allocated = allocatedTotal(lines)

  const close = () => {
    if (!busy) onClose()
  }

  const submit = async () => {
    setTouched(true)
    setFieldError(null)
    setAlert(null)
    setSaveError(null)
    if (busy || problem !== null || amount === null) return
    setBusy(true)
    try {
      onSaved(
        await createSupplierPayment({
          supplier_id: s.supplier_id,
          payment_date: date,
          amount,
          method,
          reference: reference.trim() || null,
          note: note.trim() || null,
          allocations: allocationsBody(lines),
        })
      )
    } catch (e) {
      if (e instanceof ApiError && e.status !== 0 && e.code) {
        const r = refusalText(e)
        if (r.field) setFieldError({ field: r.field, text: r.text })
        else setAlert(r.text)
      } else {
        setSaveError(
          e instanceof ApiError ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `PAYABLES_${e.status}` } : { message: String(e), code: "UNKNOWN" }
        )
      }
    } finally {
      setBusy(false)
    }
  }

  const amountError =
    fieldError?.field === "amount" ? fieldError.text : touched && problem?.kind === "amount" ? P.amountRequired : null
  const splitError =
    !touched || !problem || problem.kind === "amount"
      ? null
      : problem.kind === "over"
        ? P.over
        : problem.kind === "empty"
          ? P.empty
          : P.mismatch

  const fields = (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-3.5")}>
      {saveError && <SaveError {...saveError} />}
      {alert && <Alert tone="err">{alert}</Alert>}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-[10px] bg-surface-2 px-4 py-3 text-[13px]">
        <dt className="text-text-3">{P.owed}</dt>
        <dd>
          <Money value={s.outstanding} className="font-bold" />
        </dd>
      </dl>
      <div className="grid grid-cols-2 gap-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="sp-amount">{P.amount}</Label>
          <MoneyInput
            id="sp-amount"
            value={amount}
            onValue={(v) => {
              setAmount(v ?? null)
              setFieldError(null)
            }}
            tone={amountError ? "error" : null}
            className={mobile ? "h-12" : undefined}
          />
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="sp-date">{P.date}</Label>
          <DateField id="sp-date" value={date} today={today} onChange={(d) => { setDate(d); setFieldError(null) }} todayLabel={S.today} mobile={mobile} />
        </div>
      </div>
      {amountError && <InlineMessage severity="error">{amountError}</InlineMessage>}
      {fieldError?.field === "date" && <InlineMessage severity="error">{fieldError.text}</InlineMessage>}
      <div className="grid grid-cols-2 gap-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="sp-method">{P.method}</Label>
          <MethodPicker id="sp-method" value={method} onChange={setMethod} mobile={mobile} />
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="sp-ref" optional>
            {P.reference}
          </Label>
          <input id="sp-ref" dir="ltr" value={reference} onChange={(e) => setReference(e.target.value)} className={textInputClass(mobile)} />
        </div>
      </div>
      <section className="flex flex-col gap-2 rounded-[10px] border border-border p-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-[13.5px] font-bold text-heading">{P.split}</h3>
          <Btn size="sm" disabled={busy || amount === null || amount <= 0} onClick={() => fillOldestFirst(s, amount)}>
            {P.oldestFirst}
          </Btn>
        </div>
        <Help>{P.splitHelp}</Help>
        {lines.map((line) => (
          <div key={line.key} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between gap-2 text-[12.5px]">
              <span className="min-w-0 truncate font-semibold">{line.label}</span>
              <span className="shrink-0 text-text-3">{P.lineOwes(formatMoney(line.outstanding))}</span>
            </div>
            <MoneyInput
              id={`sp-line-${line.key}`}
              value={line.amount}
              onValue={(v) => setLines((ls) => ls.map((l) => (l.key === line.key ? { ...l, amount: v ?? null } : l)))}
              tone={touched && problem?.kind === "over" && problem.key === line.key ? "error" : null}
              className={mobile ? "h-11" : "h-9"}
            />
          </div>
        ))}
        <div className="flex items-center justify-between gap-2 border-t border-border pt-2 text-[13px]">
          <span className="text-text-3">{P.allocated}</span>
          {allocated === null ? <span className="text-text-3">—</span> : <Money value={allocated} className="font-bold" />}
        </div>
        {splitError && <InlineMessage severity="error">{splitError}</InlineMessage>}
      </section>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="sp-note" optional>
          {P.note}
        </Label>
        <input id="sp-note" value={note} onChange={(e) => setNote(e.target.value)} className={textInputClass(mobile)} />
      </div>
    </div>
  )

  const footer = (
    <>
      <Btn variant="primary" size={mobile ? "lg" : "md"} className={mobile ? "grow" : undefined} disabled={busy} aria-busy={busy || undefined} onClick={submit}>
        {busy && <Loader2 className="size-4 animate-spin" />}
        {P.save}
      </Btn>
      <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={close}>
        {P.cancel}
      </Btn>
    </>
  )
  return (
    <Shell open={open} mobile={mobile} title={P.dialogTitle(s.supplier_name ?? P.noSupplier)} description={P.splitHelp} busy={busy} onClose={close} footer={footer}>
      {fields}
    </Shell>
  )
}

/** «ویرایش پرداخت»: day, method, reference and note only (the amount and the split never change). Sends only what changed. */
export function SupplierPaymentEditDialog({
  payment,
  today,
  timeZone,
  mobile,
  onClose,
  onSaved,
}: {
  payment: SupplierPayment | null
  today: string
  timeZone: string
  mobile: boolean
  onClose: () => void
  onSaved: (payment: SupplierPayment) => void
}) {
  const [date, setDate] = React.useState(today)
  const [method, setMethod] = React.useState<SupplierPaymentMethod>("OTHER")
  const [reference, setReference] = React.useState("")
  const [note, setNote] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [dateError, setDateError] = React.useState<string | null>(null)
  const [alert, setAlert] = React.useState<string | null>(null)
  const [saveError, setSaveError] = React.useState<{ message: string; code: string } | null>(null)

  const [shown, setShown] = React.useState<SupplierPayment | null>(null)
  if (payment && payment !== shown) {
    setShown(payment)
    setDate(utcToLocal(payment.payment_date, timeZone)?.iso ?? today)
    setMethod(payment.method)
    setReference(payment.reference ?? "")
    setNote(payment.note ?? "")
    setDateError(null)
    setAlert(null)
    setSaveError(null)
  }
  const p = payment ?? shown
  if (!p) return null
  const open = payment != null

  const close = () => {
    if (!busy) onClose()
  }

  const submit = async () => {
    setDateError(null)
    setAlert(null)
    setSaveError(null)
    if (busy) return
    const patch: Record<string, string | null> = {}
    if (date !== (utcToLocal(p.payment_date, timeZone)?.iso ?? date)) patch.payment_date = date
    if (method !== p.method) patch.method = method
    if ((reference.trim() || null) !== p.reference) patch.reference = reference.trim() || null
    if ((note.trim() || null) !== p.note) patch.note = note.trim() || null
    if (Object.keys(patch).length === 0) {
      onClose()
      return
    }
    setBusy(true)
    try {
      onSaved(await updateSupplierPayment(p.id, patch))
    } catch (e) {
      if (e instanceof ApiError && e.status !== 0 && e.code) {
        const r = refusalText(e)
        if (r.field === "date") setDateError(r.text)
        else setAlert(r.text)
      } else {
        setSaveError(
          e instanceof ApiError ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `PAYABLES_${e.status}` } : { message: String(e), code: "UNKNOWN" }
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
        <dt className="text-text-3">{P.colSupplier}</dt>
        <dd className="font-semibold">{p.supplier_name ?? P.noSupplier}</dd>
        <dt className="text-text-3">{P.amount}</dt>
        <dd>
          <Money value={p.amount} className="font-bold" />
        </dd>
      </dl>
      <Help>{P.editHelp}</Help>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="spe-date">{P.date}</Label>
        <DateField id="spe-date" value={date} today={today} onChange={(d) => { setDate(d); setDateError(null) }} todayLabel={S.today} mobile={mobile} />
        {dateError && <InlineMessage severity="error">{dateError}</InlineMessage>}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="spe-method">{P.method}</Label>
          <MethodPicker id="spe-method" value={method} onChange={setMethod} mobile={mobile} />
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="spe-ref" optional>
            {P.reference}
          </Label>
          <input id="spe-ref" dir="ltr" value={reference} onChange={(e) => setReference(e.target.value)} className={textInputClass(mobile)} />
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="spe-note" optional>
          {P.note}
        </Label>
        <input id="spe-note" value={note} onChange={(e) => setNote(e.target.value)} className={textInputClass(mobile)} />
      </div>
    </div>
  )
  const footer = (
    <>
      <Btn variant="primary" size={mobile ? "lg" : "md"} className={mobile ? "grow" : undefined} disabled={busy} aria-busy={busy || undefined} onClick={submit}>
        {busy && <Loader2 className="size-4 animate-spin" />}
        {P.saveEdit}
      </Btn>
      <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={close}>
        {P.cancel}
      </Btn>
    </>
  )
  return (
    <Shell open={open} mobile={mobile} title={P.editTitle} description={P.editHelp} busy={busy} onClose={close} footer={footer}>
      {fields}
    </Shell>
  )
}

/** The store-local day of a stored UTC moment, as a short Jalali date. */
export function dayOf(utc: string, timeZone: string): string {
  const local = utcToLocal(utc, timeZone)
  return local ? formatJalali(local.iso, "yyyy/MM/dd") : utc
}
