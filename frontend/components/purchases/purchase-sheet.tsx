"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { DrawerShell } from "@/components/products/drawer-shell"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { getPurchase, type PurchaseDetail } from "@/lib/api"
import { formatJalaliDateTime } from "@/lib/jalali"
import { formatQuantity } from "@/lib/persian-numbers"
import { unitLabel } from "@/components/products/figures"
import { formatMoney } from "@/lib/money"
import { METHOD_LABELS, U } from "./copy"
import { PayStatusTag } from "./pay-status-tag"
import { TypeTag } from "./type-tag"
import type { PurchaseRow } from "./use-purchases-data"

type Load = { status: "loading" } | { status: "error" } | { status: "ready"; p: PurchaseDetail }

/**
 * One purchase invoice (GET /purchases/{id}): the server's invoice number, every line (item, quantity, line total, unit
 * cost), the invoice total, its payment status, what is paid and still owed, and the payments that paid it (all from the API).
 */
export function PurchaseSheet({
  row,
  timeZone,
  mobile,
  onClose,
}: {
  row: PurchaseRow | null
  timeZone: string
  mobile: boolean
  onClose: () => void
}) {
  const [load, setLoad] = React.useState<{ key: string; load: Load } | null>(null)
  const key = row?.key ?? null

  React.useEffect(() => {
    if (!row) return
    let cancelled = false
    getPurchase(row.id).then(
      (p) => !cancelled && setLoad({ key: row.key, load: { status: "ready", p } }),
      () => !cancelled && setLoad({ key: row.key, load: { status: "error" } })
    )
    return () => {
      cancelled = true
    }
  }, [row])

  const current: Load = load && load.key === key ? load.load : { status: "loading" }

  return (
    <DrawerShell
      open={row != null}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={U.detailTitle}
      footer={<Btn onClick={onClose}>{U.close}</Btn>}
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
          </div>
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
                  [U.detailPaymentStatus, <PayStatusTag key="s" status={current.p.payment_status} />],
                  [U.detailPaid, formatMoney(current.p.paid)],
                  [U.detailOutstanding, formatMoney(current.p.outstanding)],
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
    </DrawerShell>
  )
}
