"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { DrawerShell } from "@/components/products/drawer-shell"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { getMaterialPurchase, getProductPurchase, type MaterialPurchase, type ProductPurchase } from "@/lib/api"
import { formatJalaliDateTime } from "@/lib/jalali"
import { formatQuantity } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { U } from "./copy"
import { TypeTag } from "./type-tag"
import type { PurchaseRow } from "./use-purchases-data"

type Load = { status: "loading" } | { status: "error" } | { status: "ready"; p: MaterialPurchase | ProductPurchase }

/** One purchase (GET /purchases/{materials|products}/{id}), every field including the server's invoice number. */
export function PurchaseSheet({
  row,
  unitOf,
  timeZone,
  mobile,
  onClose,
}: {
  row: PurchaseRow | null
  unitOf: (row: PurchaseRow) => string
  timeZone: string
  mobile: boolean
  onClose: () => void
}) {
  const [load, setLoad] = React.useState<{ key: string; load: Load } | null>(null)
  const key = row?.key ?? null

  React.useEffect(() => {
    if (!row) return
    let cancelled = false
    const fetch = row.kind === "material" ? getMaterialPurchase(row.id) : getProductPurchase(row.id)
    fetch.then(
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
          <div className="flex items-center gap-2 text-[15px] font-bold">
            {row.itemName}
            <TypeTag kind={row.kind} />
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
                  [U.detailQty, `${formatQuantity(current.p.quantity_bought)} ${unitOf(row)}`],
                  [U.detailTotal, formatMoney(current.p.total_paid)],
                  [U.detailUnit, formatMoney(current.p.unit_cost)],
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
        </>
      )}
    </DrawerShell>
  )
}
