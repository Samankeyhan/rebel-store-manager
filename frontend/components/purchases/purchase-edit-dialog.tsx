"use client"

import * as React from "react"
import { Pencil } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { ItemPicker, type PickerItem } from "@/components/common/item-picker"
import { ConfirmShell } from "@/components/orders/detail/confirm-shell"
import { Help, InlineMessage, Label } from "@/components/record-sale/primitives"
import { ApiError, type PurchaseDetail, type PurchaseUpdate, type Supplier, updatePurchase } from "@/lib/api"
import { hasCode } from "@/lib/error-codes"
import { utcToLocal } from "@/lib/jalali"
import { cancelRefusal } from "@/lib/purchase-correction"
import { cn } from "@/lib/utils"
import { C, refusalText, U } from "./copy"

const NO_SUPPLIER = 0

/** The Persian text of an edit refusal, by code (never the message). */
function editError(e: unknown, timeZone: string): { field: "supplier" | "date" | null; text: string } {
  if (!(e instanceof ApiError)) return { field: null, text: String(e) }
  if (hasCode(e, "PURCHASE_HAS_PAYMENTS")) return { field: "supplier", text: C.sharedSupplier }
  if (hasCode(e, "SUPPLIER_REQUIRED_FOR_CREDIT")) return { field: "supplier", text: C.creditNeedsSupplier }
  if (hasCode(e, "SUPPLIER_NOT_FOUND")) return { field: "supplier", text: U.supplierGone }
  if (hasCode(e, "SUPPLIER_PAYMENT_BEFORE_PURCHASE")) return { field: "date", text: C.paymentBeforeDay }
  if (hasCode(e, "DATE_IN_FUTURE")) return { field: "date", text: C.dateInFuture }
  const refusal = cancelRefusal(e)
  return { field: null, text: refusal ? refusalText(refusal, timeZone) : e.message }
}

/**
 * «ویرایش» of a purchase: only its supplier, day and note (PATCH /purchases/{id}; only the changed fields are sent).
 * Lines and amounts change through «اصلاح خرید». The server moves the payments that follow (section 23). Mounted
 * only while open, so it starts from the invoice as it is.
 */
export function PurchaseEditDialog({
  open,
  onOpenChange,
  detail,
  suppliers,
  today,
  timeZone,
  mobile,
  onDone,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  detail: PurchaseDetail
  suppliers: Supplier[]
  today: string
  timeZone: string
  mobile: boolean
  onDone: (updated: PurchaseDetail, message: string) => void
}) {
  const day = utcToLocal(detail.purchase_date, timeZone)?.iso ?? today
  const [supplierId, setSupplierId] = React.useState(detail.supplier_id ?? NO_SUPPLIER)
  const [date, setDate] = React.useState(day)
  const [note, setNote] = React.useState(detail.notes ?? "")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ field: "supplier" | "date" | null; text: string } | null>(null)

  const patch: PurchaseUpdate = {}
  if (supplierId !== (detail.supplier_id ?? NO_SUPPLIER)) patch.supplier_id = supplierId === NO_SUPPLIER ? null : supplierId
  if (date !== day) patch.purchase_date = date
  if (note.trim() !== (detail.notes ?? "")) patch.notes = note.trim() || null
  const changed = Object.keys(patch).length > 0

  const supplierItems: PickerItem[] = [
    { id: NO_SUPPLIER, name: U.noSupplierOption },
    ...[...suppliers].sort((a, b) => a.name.localeCompare(b.name, "fa")).map((s) => ({ id: s.id, name: s.name })),
  ]

  const confirm = async () => {
    if (!changed) return
    setBusy(true)
    setError(null)
    try {
      const updated = await updatePurchase(detail.id, patch)
      setBusy(false)
      onOpenChange(false)
      onDone(updated, C.editSaved(detail.invoice_number ?? ""))
    } catch (e) {
      setError(editError(e, timeZone))
      setBusy(false)
    }
  }

  const inputCls = cn(
    "w-full min-w-0 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
    mobile ? "h-11" : "h-10"
  )

  return (
    <ConfirmShell
      open={open}
      onOpenChange={onOpenChange}
      mobile={mobile}
      busy={busy}
      icon={Pencil}
      danger={false}
      title={C.editTitle(detail.invoice_number ?? "")}
      subtitle={C.editSubtitle}
      confirmLabel={C.editSave}
      confirmIcon={Pencil}
      confirmDisabled={!changed}
      onConfirm={confirm}
      width={520}
    >
      {error && error.field === null && <InlineMessage severity="error">{error.text}</InlineMessage>}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pe-supplier">{U.fieldSupplier}</Label>
        <ItemPicker
          id="pe-supplier"
          items={supplierItems}
          value={supplierId}
          onPick={(id) => {
            setSupplierId(id)
            setError(null)
          }}
          placeholder={U.noSupplierOption}
          searchLabel={U.searchSupplier}
          emptyText={U.noSupplierOption}
          noMatchText={U.noSupplierMatch}
          mobile={mobile}
          error={error?.field === "supplier"}
        />
        {error?.field === "supplier" && <InlineMessage severity="error">{error.text}</InlineMessage>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pe-date">{U.fieldDate}</Label>
        <DateField
          id="pe-date"
          value={date}
          today={today}
          onChange={(d) => {
            setDate(d)
            setError(null)
          }}
          todayLabel={U.today}
          mobile={mobile}
        />
        {error?.field === "date" && <InlineMessage severity="error">{error.text}</InlineMessage>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pe-note" optional>
          {U.fieldNote}
        </Label>
        <input id="pe-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder={U.notePlaceholder} className={inputCls} />
      </div>
      {detail.payments.length > 0 && <Help>{C.editPaymentsFollow}</Help>}
    </ConfirmShell>
  )
}
