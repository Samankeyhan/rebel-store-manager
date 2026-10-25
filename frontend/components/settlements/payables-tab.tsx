"use client"

import * as React from "react"
import Link from "next/link"
import { HandCoins, ReceiptText } from "lucide-react"
import { ConfirmDeleteDialog } from "@/components/common/confirm-delete-dialog"
import { Money } from "@/components/common/money"
import { RowMenu } from "@/components/common/row-menu"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { METHOD_LABELS } from "@/components/purchases/copy"
import { PayStatusTag } from "@/components/purchases/pay-status-tag"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import {
  ApiError,
  deleteSupplierPayment,
  getPayables,
  listSupplierPayments,
  type Payables,
  type PayablesSupplier,
  type SupplierPayment,
} from "@/lib/api"
import { utcToLocal } from "@/lib/jalali"
import { formatMoney } from "@/lib/money"
import { itemsSummary } from "@/lib/purchase-lines"
import { cn } from "@/lib/utils"
import { P, S } from "./copy"
import { dayOf, SupplierPaymentDialog, SupplierPaymentEditDialog } from "./supplier-payment-dialog"

type Load = { status: "loading" } | { status: "error" } | { status: "ready"; payables: Payables; payments: SupplierPayment[] }

/**
 * «بدهی به تأمین‌کنندگان»: what the shop owes each supplier (GET /payables: outstanding, oldest unpaid day, open
 * purchases), «ثبت پرداخت» per supplier, and the history of supplier payments with edit and delete. Every figure comes
 * from the API (db/supplier_payments.py); payments are cash and debt, never profit.
 */
export function PayablesTab({
  today,
  timeZone,
  mobile,
  onToast,
}: {
  today: string | null
  timeZone: string | null
  mobile: boolean
  onToast: (text: string) => void
}) {
  const [load, setLoad] = React.useState<Load>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)
  const [paying, setPaying] = React.useState<PayablesSupplier | null>(null)
  const [editing, setEditing] = React.useState<SupplierPayment | null>(null)
  const [deleting, setDeleting] = React.useState<SupplierPayment | null>(null)
  const [deleteBusy, setDeleteBusy] = React.useState(false)
  const [deleteError, setDeleteError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([getPayables(), listSupplierPayments()]).then(
      ([payables, payments]) => !cancelled && setLoad({ status: "ready", payables, payments }),
      () => !cancelled && setLoad({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [attempt])
  const refresh = () => setAttempt((a) => a + 1)

  if (load.status === "error")
    return <ErrorBlock title={P.loadFailed} body={S.errorBody} retry={S.retry} onRetry={() => { setLoad({ status: "loading" }); refresh() }} mobile={mobile} />
  if (load.status === "loading" || !today || !timeZone) return <LoadingBlock mobile={mobile} label={S.loadingAria} />

  const { payables, payments } = load
  const confirmDelete = async () => {
    if (!deleting) return
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await deleteSupplierPayment(deleting.id)
      setDeleting(null)
      onToast(P.toastDeleted)
      refresh()
    } catch (e) {
      setDeleteError(e instanceof ApiError && e.status === 404 ? P.notFound : e instanceof Error ? e.message : String(e))
    } finally {
      setDeleteBusy(false)
    }
  }

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-5")}>
      <p className="text-[13px] leading-[1.9] text-text-3">{P.intro}</p>
      {payables.suppliers.length === 0 ? (
        <StateShell icon={HandCoins} mobile={mobile} title={P.none} />
      ) : (
        <>
          <div className={cn(cardClass, "flex items-center justify-between gap-3 px-4 py-3")}>
            <span className="text-sm font-semibold text-text-2">{P.owedTotal}</span>
            <Money value={payables.outstanding_total} className="text-lg font-bold text-loss" />
          </div>
          <div className={cn("grid gap-3", !mobile && "grid-cols-2")}>
            {payables.suppliers.map((s) => (
              <SupplierCard
                key={s.supplier_id ?? "none"}
                supplier={s}
                today={today}
                timeZone={timeZone}
                onPay={() => setPaying(s)}
              />
            ))}
          </div>
        </>
      )}

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-bold text-heading">{P.history}</h3>
        {payments.length === 0 ? (
          <p className="text-[13px] text-text-3">{P.noHistory}</p>
        ) : (
          <ul className={cn(cardClass, "flex flex-col divide-y divide-border")}>
            {payments.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-[13.5px]">
                <span className="flex min-w-0 flex-col">
                  <span className="truncate font-semibold">{p.supplier_name ?? P.noSupplier}</span>
                  <span className="truncate text-xs text-text-3">
                    {dayOf(p.payment_date, timeZone)} · {METHOD_LABELS[p.method]}
                    {p.reference && (
                      <>
                        {" · "}
                        <span dir="ltr">{p.reference}</span>
                      </>
                    )}
                    {" · "}
                    {P.forPurchases(p.allocations.length)}
                  </span>
                  {p.note && <span className="truncate text-xs text-text-3">{p.note}</span>}
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  <Money value={p.amount} className="font-bold" />
                  <RowMenu
                    onEdit={() => setEditing(p)}
                    onDelete={() => {
                      setDeleteError(null)
                      setDeleting(p)
                    }}
                  />
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <SupplierPaymentDialog
        supplier={paying}
        today={today}
        timeZone={timeZone}
        mobile={mobile}
        onClose={() => setPaying(null)}
        onSaved={() => {
          onToast(P.toastSaved(paying?.supplier_name ?? P.noSupplier))
          setPaying(null)
          refresh()
        }}
      />
      <SupplierPaymentEditDialog
        payment={editing}
        today={today}
        timeZone={timeZone}
        mobile={mobile}
        onClose={() => setEditing(null)}
        onSaved={() => {
          onToast(P.toastEdited)
          setEditing(null)
          refresh()
        }}
      />
      <ConfirmDeleteDialog
        open={deleting != null}
        title={P.deleteTitle}
        lines={
          deleting
            ? [
                P.deleteLine(deleting.supplier_name ?? P.noSupplier, dayOf(deleting.payment_date, timeZone), formatMoney(deleting.amount)),
                P.deleteEffect,
              ]
            : []
        }
        confirmLabel={P.deleteConfirm}
        busy={deleteBusy}
        error={deleteError}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  )
}

function SupplierCard({
  supplier,
  today,
  timeZone,
  onPay,
}: {
  supplier: PayablesSupplier
  today: string
  timeZone: string
  onPay: () => void
}) {
  // the purchases screen reads ?supplier= and ?from=&to= (components/purchases/purchases-page.tsx: supplierParam, from, to)
  const from = utcToLocal(supplier.oldest_unpaid_date, timeZone)?.iso
  const href =
    supplier.supplier_id != null && from && from <= today
      ? `/purchases?supplier=${supplier.supplier_id}&from=${from}&to=${today}`
      : null
  return (
    <article className={cn(cardClass, "flex flex-col gap-3 p-4")}>
      <header className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <h4 className="truncate text-[15px] font-bold text-heading">{supplier.supplier_name ?? P.noSupplier}</h4>
          <span className="text-xs text-text-3">{P.oldestUnpaid(dayOf(supplier.oldest_unpaid_date, timeZone))}</span>
        </div>
        <span className="flex shrink-0 flex-col items-end">
          <span className="text-xs text-text-3">{P.owed}</span>
          <Money value={supplier.outstanding} className="font-bold text-loss" />
        </span>
      </header>
      <ul className="flex flex-col divide-y divide-border rounded-[10px] border border-border text-[13px]">
        {supplier.open_purchases.map((p) => (
          <li key={p.purchase_id} className="flex items-center justify-between gap-2 px-3 py-2">
            <span className="flex min-w-0 flex-col">
              <span className="truncate font-semibold">{itemsSummary(p.item_names, P.moreItems)}</span>
              <span className="truncate text-xs text-text-3">
                <span dir="ltr">{p.invoice_number}</span> · {dayOf(p.purchase_date, timeZone)}
              </span>
            </span>
            <span className="flex shrink-0 flex-col items-end gap-1">
              <Money value={p.outstanding} className="font-semibold" />
              <PayStatusTag status={p.payment_status} />
            </span>
          </li>
        ))}
      </ul>
      <footer className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-text-3">{P.openCount(supplier.open_purchases.length)}</span>
        <span className="flex items-center gap-2">
          {href && (
            <Link href={href} className="inline-flex items-center gap-1 text-xs font-semibold text-info hover:underline">
              <ReceiptText className="size-3.5" aria-hidden />
              {P.purchasesLink}
            </Link>
          )}
          <Btn size="sm" variant="primary" onClick={onPay}>
            {P.record}
          </Btn>
        </span>
      </footer>
    </article>
  )
}
