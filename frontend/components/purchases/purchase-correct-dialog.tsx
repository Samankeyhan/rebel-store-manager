"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { DrawerShell } from "@/components/products/drawer-shell"
import { Alert, Btn, InlineMessage } from "@/components/record-sale/primitives"
import { getCancelPreview, type Material, type Product, type PurchaseCancelPreview, type PurchaseDetail, type Supplier } from "@/lib/api"
import { utcToLocal } from "@/lib/jalali"
import { catalogAfterCancel, correctionPrefill } from "@/lib/purchase-correction"
import { C, U } from "./copy"
import { blockerTexts } from "./purchase-cancel-dialog"
import { PurchaseForm, type PurchaseFormHandle } from "./purchase-form"
import type { RefreshedItem } from "./use-purchases-data"

type Load = { status: "loading" } | { status: "error" } | { status: "ready"; preview: PurchaseCancelPreview }

/**
 * «اصلاح خرید» (accounting-rules section 23): the purchase form filled with the invoice (every line, supplier, day,
 * note) plus a required reason. The save cancels the old invoice and records this one in its place in one operation;
 * the payments move to it, so the form shows what is already paid and the payment choice is on the rest. The form's
 * cost preview starts from each item's stock and cost after the cancel (the cancel-preview). Mounted only while open.
 */
export function PurchaseCorrectDialog({
  onClose,
  detail,
  materials,
  products,
  suppliers,
  today,
  timeZone,
  mobile,
  refreshSuppliers,
  onDone,
}: {
  onClose: () => void
  detail: PurchaseDetail
  materials: Material[]
  products: Product[]
  suppliers: Supplier[]
  today: string
  timeZone: string
  mobile: boolean
  refreshSuppliers: () => Promise<void>
  onDone: (corrected: PurchaseDetail, items: RefreshedItem[], message: string) => void
}) {
  const [load, setLoad] = React.useState<Load>({ status: "loading" })
  const [busy, setBusy] = React.useState(false)
  const formRef = React.useRef<PurchaseFormHandle>(null)
  const inv = detail.invoice_number ?? ""

  React.useEffect(() => {
    let cancelled = false
    getCancelPreview(detail.id).then(
      (preview) => !cancelled && setLoad({ status: "ready", preview }),
      () => !cancelled && setLoad({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [detail.id])

  // A correction moves the payments, so the payments blocker never applies to it (a shared one is refused by the
  // server only when the supplier changes).
  const blockers = load.status === "ready" ? blockerTexts(load.preview, timeZone, false) : []
  const ready = load.status === "ready" && blockers.length === 0
  const after = load.status === "ready" ? catalogAfterCancel(materials, products, load.preview.lines) : null
  const day = utcToLocal(detail.purchase_date, timeZone)?.iso ?? today

  return (
    <DrawerShell
      open
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={C.correctTitle(inv)}
      busy={busy}
      footer={
        <>
          <Btn variant="primary" disabled={!ready || busy} aria-busy={busy || undefined} onClick={() => formRef.current?.submit()}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {C.correctSubmit}
          </Btn>
          <Btn disabled={busy} onClick={onClose}>
            {U.cancel}
          </Btn>
        </>
      }
    >
      <p className="text-[13px] text-text-3">{C.correctSubtitle}</p>
      {load.status === "loading" && (
        <p className="flex justify-center py-6 text-text-3">
          <Loader2 className="size-4 animate-spin" aria-hidden />
        </p>
      )}
      {load.status === "error" && <Alert tone="err">{C.cancelPreviewFailed}</Alert>}
      {blockers.map((text) => (
        <InlineMessage key={text} severity="error">
          {text}
        </InlineMessage>
      ))}
      {ready && after && (
        <PurchaseForm
          ref={formRef}
          materials={after.materials}
          products={after.products}
          suppliers={suppliers}
          today={today}
          mobile={mobile}
          onBusyChange={setBusy}
          onSaved={(items, message, saved) => onDone(saved, items, message)}
          refreshSuppliers={refreshSuppliers}
          prefill={correctionPrefill(detail, day)}
          correction={{ purchaseId: detail.id, invoiceNumber: inv, paid: detail.paid, timeZone }}
        />
      )}
    </DrawerShell>
  )
}
