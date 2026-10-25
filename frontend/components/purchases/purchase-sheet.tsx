"use client"

import * as React from "react"
import { Eraser, FilePenLine, Loader2, Pencil } from "lucide-react"
import { DrawerShell } from "@/components/products/drawer-shell"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { getPurchase, type Material, type Product, type PurchaseDetail, type Supplier } from "@/lib/api"
import { formatJalaliDateTime } from "@/lib/jalali"
import { formatQuantity } from "@/lib/persian-numbers"
import { unitLabel } from "@/components/products/figures"
import { formatMoney } from "@/lib/money"
import { canChange } from "@/lib/purchase-correction"
import { C, METHOD_LABELS, U } from "./copy"
import { PayStatusTag } from "./pay-status-tag"
import { PurchaseCancelDialog } from "./purchase-cancel-dialog"
import { PurchaseCorrectDialog } from "./purchase-correct-dialog"
import { PurchaseEditDialog } from "./purchase-edit-dialog"
import { TypeTag } from "./type-tag"
import type { PurchaseRow, RefreshedItem } from "./use-purchases-data"

/** The invoices linked by a correction: the one this replaces and the one that replaced it. */
type Linked = { replaces: PurchaseDetail | null; replacedBy: PurchaseDetail | null }
type Load = { status: "loading" } | { status: "error" } | { status: "ready"; p: PurchaseDetail; linked: Linked }

async function fetchLinked(p: PurchaseDetail): Promise<Linked> {
  const one = (id: number | null) => (id == null ? Promise.resolve(null) : getPurchase(id).catch(() => null))
  const [replaces, replacedBy] = await Promise.all([one(p.replaces_invoice_id), one(p.replaced_by_invoice_id)])
  return { replaces, replacedBy }
}

/**
 * One purchase invoice (GET /purchases/{id}): the server's invoice number, every line (item, quantity, line total, unit
 * cost), the invoice total, its payment status, what is paid and still owed, and the payments that paid it (all from the API).
 * An ACTIVE invoice can be edited (supplier, day, note), cancelled or corrected (accounting-rules section 23); a
 * CANCELLED one shows its reason and links to the invoice that replaced it.
 */
export function PurchaseSheet({
  row,
  timeZone,
  mobile,
  onClose,
  catalog,
  today,
  refreshSuppliers,
  onChanged,
  onShow,
}: {
  row: PurchaseRow | null
  timeZone: string
  mobile: boolean
  onClose: () => void
  /** null while the items and suppliers load (the change buttons wait for them). */
  catalog: { materials: Material[]; products: Product[]; suppliers: Supplier[] } | null
  today: string
  refreshSuppliers: () => Promise<void>
  /** After an edit, cancel or correction: the invoice to show now, the items re-read, and the toast. */
  onChanged: (show: PurchaseDetail, items: RefreshedItem[], message: string) => void
  /** Open a linked invoice in the sheet. */
  onShow: (purchase: PurchaseDetail) => void
}) {
  const [load, setLoad] = React.useState<{ key: string; row: PurchaseRow; load: Load } | null>(null)
  const [dialog, setDialog] = React.useState<"edit" | "cancel" | "correct" | null>(null)
  const key = row?.key ?? null

  React.useEffect(() => {
    if (!row) return
    let cancelled = false
    getPurchase(row.id)
      .then(async (p) => ({ p, linked: await fetchLinked(p) }))
      .then(
        ({ p, linked }) => !cancelled && setLoad({ key: row.key, row, load: { status: "ready", p, linked } }),
        () => !cancelled && setLoad({ key: row.key, row, load: { status: "error" } })
      )
    return () => {
      cancelled = true
    }
  }, [row])

  // A new row object (the same invoice after a change, or another one) shows loading until its fetch lands.
  const current: Load = load && load.key === key && load.row === row ? load.load : { status: "loading" }
  const ready = current.status === "ready" ? current.p : null
  const changeable = ready != null && canChange(ready) && catalog != null

  const linkBtn = (label: string, p: PurchaseDetail) => (
    <Btn variant="link" onClick={() => onShow(p)}>
      {label}{" "}
      <span dir="ltr" className="font-mono">
        {p.invoice_number ?? "—"}
      </span>
    </Btn>
  )

  return (
    <DrawerShell
      open={row != null}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={U.detailTitle}
      footer={
        <div className="flex flex-wrap gap-2">
          {changeable && (
            <>
              <Btn onClick={() => setDialog("edit")}>
                <Pencil className="size-4" aria-hidden />
                {C.edit}
              </Btn>
              <Btn onClick={() => setDialog("correct")}>
                <FilePenLine className="size-4" aria-hidden />
                {C.correctPurchase}
              </Btn>
              <Btn className="text-loss" onClick={() => setDialog("cancel")}>
                <Eraser className="size-4" aria-hidden />
                {C.cancelPurchase}
              </Btn>
            </>
          )}
          <Btn onClick={onClose}>{U.close}</Btn>
        </div>
      }
    >
      {row && (
        <>
          <div className="flex flex-wrap items-center gap-2 text-[15px] font-bold">
            <span dir="ltr" className="font-mono">
              {row.invoiceNumber ?? "—"}
            </span>
            {row.types.map((t) => (
              <TypeTag key={t} type={t} />
            ))}
            {ready?.status === "CANCELLED" && <CancelledTag />}
          </div>
          {current.status === "ready" && current.p.status === "CANCELLED" && (
            <Alert tone="err">
              <span className="flex flex-col gap-1">
                <span>{C.cancelledBanner(current.p.cancel_reason ?? "—")}</span>
                {current.p.cancelled_at && (
                  <span className="text-xs">
                    {C.cancelledAt}: {formatJalaliDateTime(current.p.cancelled_at, timeZone)}
                  </span>
                )}
              </span>
            </Alert>
          )}
          {current.status === "ready" && (current.linked.replacedBy || current.linked.replaces) && (
            <div className="flex flex-wrap items-center gap-3 text-[13px]">
              {current.linked.replacedBy && linkBtn(C.replacedBy, current.linked.replacedBy)}
              {current.linked.replaces && linkBtn(C.corrects, current.linked.replaces)}
            </div>
          )}
          {current.status === "loading" && (
            <p className="flex justify-center py-6 text-text-3">
              <Loader2 className="size-4 animate-spin" aria-hidden />
            </p>
          )}
          {current.status === "error" && <Alert tone="err">{U.detailLoadFailed}</Alert>}
          {current.status === "ready" && (
            <dl className="flex flex-col text-[13.5px]">
              {(
                [
                  [U.detailInvoice, <span key="i" dir="ltr" className="font-mono">{current.p.invoice_number ?? "—"}</span>],
                  [U.detailDate, formatJalaliDateTime(current.p.purchase_date, timeZone)],
                  [U.detailSupplier, current.p.supplier_name ?? U.noSupplierOption],
                  [U.detailTotal, formatMoney(current.p.total)],
                  // A cancelled invoice is owed nothing (payables leave it out), so no payment status or remainder.
                  [U.detailPaymentStatus, current.p.status === "CANCELLED" ? "—" : <PayStatusTag key="s" status={current.p.payment_status} />],
                  [U.detailPaid, formatMoney(current.p.paid)],
                  [U.detailOutstanding, current.p.status === "CANCELLED" ? "—" : formatMoney(current.p.outstanding)],
                  [U.detailNote, current.p.notes || "—"],
                ] as const
              ).map(([label, value]) => (
                <div key={label} className="flex items-start justify-between gap-4 border-b border-border py-2.5 last:border-b-0">
                  <dt className="text-text-3">{label}</dt>
                  <dd className="text-end font-semibold tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
          )}
          {current.status === "ready" && (
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-bold text-heading">{U.detailLines}</h3>
              <ul className="flex flex-col text-[13.5px]">
                {current.p.lines.map((line) => (
                  <li key={`${line.kind}-${line.id}`} className="flex items-start justify-between gap-4 border-b border-border py-2 last:border-b-0">
                    <span className="flex min-w-0 flex-col">
                      <span className="flex flex-wrap items-center gap-1.5 font-semibold">
                        {line.item_name}
                        <TypeTag type={line.item_type} />
                      </span>
                      <span className="text-xs text-text-3 tabular-nums">
                        {formatQuantity(line.quantity_bought)} {line.unit ? unitLabel(line.unit) : "عدد"} · {U.detailUnit}: {formatMoney(line.unit_cost)}
                      </span>
                    </span>
                    <span className="shrink-0 font-semibold tabular-nums">{formatMoney(line.total_paid)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {current.status === "ready" && (
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-bold text-heading">{U.detailPayments}</h3>
              {current.p.payments.length === 0 ? (
                <p className="text-[13px] text-text-3">{U.noPayments}</p>
              ) : (
                <ul className="flex flex-col text-[13.5px]">
                  {current.p.payments.map((pay) => (
                    <li key={pay.payment_id} className="flex items-start justify-between gap-4 border-b border-border py-2 last:border-b-0">
                      <span className="flex min-w-0 flex-col">
                        <span>{formatJalaliDateTime(pay.payment_date, timeZone)}</span>
                        <span className="truncate text-xs text-text-3">
                          {METHOD_LABELS[pay.method]}
                          {pay.reference && (
                            <>
                              {" · "}
                              <span dir="ltr">{pay.reference}</span>
                            </>
                          )}
                        </span>
                      </span>
                      <span className="flex shrink-0 flex-col items-end">
                        <span className="font-semibold tabular-nums">{formatMoney(pay.amount)}</span>
                        {pay.payment_amount !== pay.amount && (
                          <span className="text-xs text-text-3">{U.paymentOfWhole(formatMoney(pay.payment_amount))}</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}
      {ready && catalog && dialog === "edit" && (
        <PurchaseEditDialog
          open
          onOpenChange={(o) => !o && setDialog(null)}
          detail={ready}
          suppliers={catalog.suppliers}
          today={today}
          timeZone={timeZone}
          mobile={mobile}
          onDone={(p, message) => onChanged(p, [], message)}
        />
      )}
      {ready && dialog === "cancel" && (
        <PurchaseCancelDialog
          open
          onOpenChange={(o) => !o && setDialog(null)}
          detail={ready}
          timeZone={timeZone}
          mobile={mobile}
          onDone={(p, message) => onChanged(p, [], message)}
        />
      )}
      {ready && catalog && dialog === "correct" && (
        <PurchaseCorrectDialog
          onClose={() => setDialog(null)}
          detail={ready}
          materials={catalog.materials}
          products={catalog.products}
          suppliers={catalog.suppliers}
          today={today}
          timeZone={timeZone}
          mobile={mobile}
          refreshSuppliers={refreshSuppliers}
          onDone={(p, items, message) => {
            setDialog(null)
            onChanged(p, items, message)
          }}
        />
      )}
    </DrawerShell>
  )
}

/** «باطل‌شده» on a cancelled purchase (the list row and the sheet). */
export function CancelledTag() {
  return (
    <span className="inline-flex h-5 items-center rounded-full bg-loss-soft px-2 text-[11px] font-bold text-loss">{C.cancelledTag}</span>
  )
}
