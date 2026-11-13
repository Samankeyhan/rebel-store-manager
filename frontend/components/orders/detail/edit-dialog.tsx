"use client"

import * as React from "react"
import { ArrowLeft, ChevronDown, PencilLine } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { DateField } from "@/components/common/date-field"
import { Help, InlineMessage, Label, MoneyInput, inputClass } from "@/components/record-sale/primitives"
import { PM, feeText } from "@/components/payment-methods/copy"
import { getEditPreview, listPaymentMethods, type OrderDetail, type OrderEditPreview, type PaymentMethod } from "@/lib/api"
import { formatJalali, utcToLocal } from "@/lib/jalali"
import { formatMoney } from "@/lib/money"
import {
  DAY_FIELDS,
  MONEY_FIELDS,
  editBlockerRefusal,
  editBody,
  editFormFrom,
  editLocks,
  formBlocked,
  proposedPaidDate,
  type EditBody,
  type EditForm,
} from "@/lib/order-edit"
import { cn } from "@/lib/utils"
import { D } from "../copy"
import { ConfirmShell } from "./confirm-shell"

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  detail: OrderDetail
  timeZone: string
  today: string
  mobile: boolean
  busy: boolean
  onSave: (body: EditBody) => void
}

type PreviewState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; preview: OrderEditPreview }

function TextField({
  id,
  label,
  value,
  onChange,
  disabled,
  mobile,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  mobile: boolean
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <input
        id={id}
        value={value}
        disabled={disabled}
        maxLength={500}
        onChange={(e) => onChange(e.target.value)}
        className={cn(inputClass(), mobile && "h-11", disabled && "opacity-60")}
      />
    </div>
  )
}

/** One value of the before → after list, shown in its unit. */
function shown(field: string, value: unknown, methods: PaymentMethod[] | null): string {
  if (value == null || value === "") return D.editNone
  if (MONEY_FIELDS.includes(field) || field === "customer_total" || field === "profit" || field === "settlement_amount") {
    return typeof value === "number" ? formatMoney(value) : String(value)
  }
  if (DAY_FIELDS.includes(field) || field === "order_day" || field === "expected_settlement_date") {
    return formatJalali(String(value))
  }
  if (field === "payment_method_id") {
    return methods?.find((m) => m.id === value)?.name ?? String(value)
  }
  return String(value)
}

function BeforeAfter({ label, before, after }: { label: string; before: string; after: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg bg-surface-2 px-3 py-2 text-[13px] leading-[21px]">
      <span className="font-semibold text-text-2">{label}</span>
      <span className="flex flex-wrap items-center gap-x-2 tabular-nums">
        <span className="text-text-3 line-through decoration-text-3/50">{before}</span>
        <ArrowLeft className="size-3.5 shrink-0 text-text-3" aria-hidden />
        <b>{after}</b>
      </span>
    </div>
  )
}

/**
 * «ویرایش سفارش»: the light edit (accounting-rules section 20). Step 1 is the form, only the fields the order can
 * take; step 2 shows the server's preview, each changed field and figure before → after, and every refusal.
 * Saving sends only the changed fields.
 */
export function EditOrderDialog({ open, onOpenChange, detail, timeZone, today, mobile, busy, onSave }: Props) {
  const order = detail.order
  const orderDay = utcToLocal(order.order_date, timeZone)?.iso ?? order.order_date.slice(0, 10)
  const initial = React.useMemo(() => editFormFrom(order, orderDay), [order, orderDay])
  const locks = editLocks(order)
  const [form, setForm] = React.useState<EditForm>(initial)
  const [step, setStep] = React.useState<"form" | "review">("form")
  const [preview, setPreview] = React.useState<PreviewState>({ status: "idle" })
  const [paidFollowed, setPaidFollowed] = React.useState(false)
  const [methods, setMethods] = React.useState<PaymentMethod[] | null>(null)

  // A fresh form every time the dialog opens (and after the order changed): reset while rendering, not in an effect.
  const [shownFor, setShownFor] = React.useState<EditForm | null>(null)
  if (open && shownFor !== initial) {
    setShownFor(initial)
    setForm(initial)
    setStep("form")
    setPreview({ status: "idle" })
    setPaidFollowed(false)
  } else if (!open && shownFor !== null) {
    setShownFor(null)
  }
  React.useEffect(() => {
    if (!open) return
    let cancelled = false
    listPaymentMethods(true).then(
      (m) => !cancelled && setMethods(m),
      () => !cancelled && setMethods(null)
    )
    return () => {
      cancelled = true
    }
  }, [open])

  const body = editBody(initial, form)
  const changed = Object.keys(body).length > 0
  const set = (patch: Partial<EditForm>) => setForm((f) => ({ ...f, ...patch }))

  const review = () => {
    setStep("review")
    setPreview({ status: "loading" })
    getEditPreview(order.id, body).then(
      (p) => setPreview({ status: "ready", preview: p }),
      () => setPreview({ status: "error" })
    )
  }

  const blockers =
    preview.status === "ready"
      ? preview.preview.blockers.map((b) => {
          const r = editBlockerRefusal(b)
          return r ? D.editRefusal(r) : b.code
        })
      : []

  const active = (methods ?? []).filter((m) => m.is_active === 1)
  const currentMethod = methods?.find((m) => m.id === form.paymentMethodId)
  const methodName = currentMethod
    ? currentMethod.is_active === 1
      ? currentMethod.name
      : PM.inactive(currentMethod.name)
    : form.paymentMethodId == null
      ? D.editMethodNone
      : order.payment_method_name ?? D.editNone

  const formStep = (
    <>
      {locks.money ? null : (
        <InlineMessage severity="warn">{order.settlement_id != null ? D.editLockedSettled : D.editLockedStatus}</InlineMessage>
      )}
      {locks.money && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="edit-order-date">{D.editOrderDateLabel}</Label>
          <DateField
            id="edit-order-date"
            value={form.orderDate}
            today={today}
            todayLabel={D.today}
            mobile={mobile}
            onChange={(iso) => {
              const paidDate = locks.paidDate ? proposedPaidDate(initial, form, iso) : form.paidDate
              setPaidFollowed(paidDate !== form.paidDate)
              set({ orderDate: iso, paidDate })
            }}
          />
        </div>
      )}
      {locks.paidDate && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="edit-paid-date">{D.paidDateLabel}</Label>
          <DateField
            id="edit-paid-date"
            value={form.paidDate}
            today={today}
            todayLabel={D.today}
            mobile={mobile}
            onChange={(iso) => {
              setPaidFollowed(false)
              set({ paidDate: iso })
            }}
          />
          {paidFollowed ? <Help>{D.editPaidFollows}</Help> : <Help>{D.paidDateHelp}</Help>}
        </div>
      )}
      {locks.money && (
        <div className="flex flex-col gap-1.5">
          <Label>{D.editMethodLabel}</Label>
          <DropdownMenu dir="rtl">
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label={D.editMethodLabel}
                className={cn(inputClass(), "flex cursor-pointer items-center justify-between gap-2", mobile && "h-11")}
              >
                <span className="truncate">{methodName}</span>
                <ChevronDown className="size-3.5 shrink-0 text-text-3" aria-hidden />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[240px]">
              <DropdownMenuRadioGroup
                value={form.paymentMethodId == null ? "" : String(form.paymentMethodId)}
                onValueChange={(v) => set({ paymentMethodId: Number(v) })}
              >
                {active.map((m) => (
                  <DropdownMenuRadioItem key={m.id} value={String(m.id)}>
                    <span className="flex min-w-0 grow flex-col gap-0.5 py-0.5">
                      <span className="truncate font-semibold">{m.name}</span>
                      <span className="text-xs leading-5 text-text-3">{feeText(m.fee_bps, m.fee_fixed, m.fee_cap)}</span>
                    </span>
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
          <Help>{D.editMethodHelp}</Help>
        </div>
      )}
      {locks.money && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="edit-shipping">{D.editShippingLabel}</Label>
          <MoneyInput id="edit-shipping" value={form.shipping} onValue={(rial) => set({ shipping: rial ?? null })} />
          <Help>{D.editShippingHelp}</Help>
        </div>
      )}
      {locks.postage && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="edit-postage">{D.editPostageLabel}</Label>
          <MoneyInput id="edit-postage" value={form.postage} onValue={(rial) => set({ postage: rial ?? null })} />
          <Help>{D.editPostageHelp}</Help>
        </div>
      )}
      <TextField
        id="edit-reference"
        label={D.editReferenceLabel}
        value={form.paymentReference}
        onChange={(v) => set({ paymentReference: v })}
        mobile={mobile}
      />
      <TextField
        id="edit-customer"
        label={D.editCustomerLabel}
        value={form.customerName}
        onChange={(v) => set({ customerName: v })}
        mobile={mobile}
      />
      <TextField id="edit-notes" label={D.editNotesLabel} value={form.notes} onChange={(v) => set({ notes: v })} mobile={mobile} />
      <p className="text-xs text-text-3">{D.editItemsNote}</p>
    </>
  )

  const figures = preview.status === "ready" ? preview.preview.figures : null
  const movedFigures = figures
    ? (Object.entries(figures) as [string, { before: unknown; after: unknown }][]).filter(([, f]) => f.before !== f.after)
    : []

  const reviewStep = (
    <>
      {preview.status === "loading" && <p className="text-[13px] text-text-3">{D.editLoading}</p>}
      {preview.status === "error" && <InlineMessage severity="error">{D.editPreviewFailed}</InlineMessage>}
      {preview.status === "ready" && (
        <>
          {blockers.map((text) => (
            <InlineMessage key={text} severity="error">
              {text}
            </InlineMessage>
          ))}
          {preview.preview.changes.length === 0 ? (
            <p className="text-[13px] text-text-3">{D.editNoChange}</p>
          ) : (
            <>
              <p className="text-[13px] font-semibold">{D.editReviewLead}</p>
              {preview.preview.changes.map((c) => (
                <BeforeAfter
                  key={c.field}
                  label={D.editFieldName(c.field)}
                  before={shown(c.field, c.before, methods)}
                  after={shown(c.field, c.after, methods)}
                />
              ))}
            </>
          )}
          {movedFigures.length > 0 && (
            <>
              <p className="text-[13px] font-semibold">{D.editFiguresLead}</p>
              {movedFigures.map(([name, f]) => (
                <BeforeAfter
                  key={name}
                  label={D.editFigureName(name)}
                  before={shown(name, f.before, methods)}
                  after={shown(name, f.after, methods)}
                />
              ))}
            </>
          )}
          <button
            type="button"
            className="cursor-pointer self-start text-[13px] font-bold text-heading hover:text-primary"
            disabled={busy}
            onClick={() => setStep("form")}
          >
            {D.editBack}
          </button>
        </>
      )}
      {preview.status === "error" && (
        <button
          type="button"
          className="cursor-pointer self-start text-[13px] font-bold text-heading hover:text-primary"
          onClick={() => setStep("form")}
        >
          {D.editBack}
        </button>
      )}
    </>
  )

  const ready =
    preview.status === "ready" && preview.preview.blockers.length === 0 && preview.preview.changes.length > 0
  return (
    <ConfirmShell
      open={open}
      onOpenChange={onOpenChange}
      mobile={mobile}
      busy={busy}
      danger={false}
      icon={PencilLine}
      title={D.editTitle(order.invoice_number ?? "")}
      subtitle={D.editSubtitle}
      confirmLabel={step === "form" ? D.editReview : D.editSave}
      confirmDisabled={step === "form" ? !changed || formBlocked(form) : !ready}
      onConfirm={() => (step === "form" ? review() : onSave(body))}
      width={560}
    >
      {step === "form" ? formStep : reviewStep}
    </ConfirmShell>
  )
}
