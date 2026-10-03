"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { Collapsible } from "@/components/common/collapsible"
import { DrawerShell } from "@/components/products/drawer-shell"
import { TypeBadge } from "@/components/products/badges"
import { unitLabel } from "@/components/products/figures"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { getProductionBatch, type Material, type ProductionBatchDetail, type ProductionBatchListItem } from "@/lib/api"
import { roundHalfEven } from "@/lib/costing"
import { formatJalaliDateTime } from "@/lib/jalali"
import { formatQuantity } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { Money } from "@/components/common/money"
import { R } from "./copy"

type Load = { status: "loading" } | { status: "error" } | { status: "ready"; detail: ProductionBatchDetail }

/** One batch (GET /production/{id}): its facts and the materials it consumed at their frozen costs. */
export function BatchSheet({
  batch,
  materials,
  timeZone,
  mobile,
  onClose,
}: {
  batch: ProductionBatchListItem | null
  materials: Material[]
  timeZone: string
  mobile: boolean
  onClose: () => void
}) {
  const [load, setLoad] = React.useState<{ id: number; load: Load } | null>(null)
  // The detail (materials and costs) is fetched only once «جزئیات و بها» is first opened for this batch.
  const [requested, setRequested] = React.useState<number | null>(null)
  const id = batch != null && requested === batch.id ? batch.id : null

  React.useEffect(() => {
    if (id == null) return
    let cancelled = false
    getProductionBatch(id).then(
      (detail) => !cancelled && setLoad({ id, load: { status: "ready", detail } }),
      () => !cancelled && setLoad({ id, load: { status: "error" } })
    )
    return () => {
      cancelled = true
    }
  }, [id])

  const current: Load = load && load.id === id ? load.load : { status: "loading" }
  const unitOf = (materialId: number) => unitLabel(materials.find((m) => m.id === materialId)?.unit ?? "")

  return (
    <DrawerShell
      open={batch != null}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={R.batchTitle}
      footer={<Btn onClick={onClose}>{R.close}</Btn>}
    >
      {batch && (
        <>
          <div className="flex flex-col gap-1 rounded-[10px] bg-surface-2 px-3 py-2.5 text-[13px]">
            <span className="font-bold">{batch.product_name}</span>
            <span className="text-text-3 tabular-nums">
              {formatJalaliDateTime(batch.production_date, timeZone)} · {R.batchFacts(batch.quantity_produced)}
            </span>
            {batch.notes && <span className="text-text-3">{batch.notes}</span>}
          </div>
          <Collapsible key={batch.id} label={R.costDetails} onFirstOpen={() => setRequested(batch.id)}>
            <div className="flex flex-col gap-2 pt-1">
              <span className="px-1 text-[13px] text-text-3">
                {R.batchUnitCost}: <b className="text-foreground tabular-nums">{formatMoney(batch.unit_cost)}</b>
              </span>
              <h3 className="text-sm font-bold text-heading">{R.batchMaterials}</h3>
              {current.status === "loading" && (
                <p className="flex items-center justify-center gap-2 py-6 text-[13px] text-text-3">
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                </p>
              )}
              {current.status === "error" && <Alert tone="err">{R.batchLoadFailed}</Alert>}
              {current.status === "ready" && <BatchMaterials detail={current.detail} unitOf={unitOf} />}
            </div>
          </Collapsible>
        </>
      )}
    </DrawerShell>
  )
}

function BatchMaterials({ detail, unitOf }: { detail: ProductionBatchDetail; unitOf: (id: number) => string }) {
  // The batch total the backend stored the unit cost from: round(Σ used × cost).
  const total = roundHalfEven(detail.materials.reduce((s, m) => s + m.quantity_used * m.unit_cost_at_time, 0))
  return (
    <div className="flex flex-col">
      {detail.materials.map((m) => (
        <div key={m.id} className="flex items-start justify-between gap-3 border-b border-border py-2.5 text-[13px]">
          <span className="flex min-w-0 flex-col gap-1">
            <span className="flex items-center gap-1.5 font-bold">
              {m.material_name}
              <TypeBadge type={m.material_type} />
            </span>
            <span className="text-xs text-text-3 tabular-nums">
              {R.colUsed}: {formatQuantity(m.quantity_used)} {unitOf(m.material_id)} · {R.colUnitCostAt}:{" "}
              {formatMoney(m.unit_cost_at_time)}
            </span>
          </span>
          <Money value={Math.round(m.quantity_used * m.unit_cost_at_time)} className="shrink-0 font-bold" />
        </div>
      ))}
      <div className="flex items-center justify-between py-3 text-[13.5px] font-bold">
        <span>{R.totalLabel}</span>
        <span className="tabular-nums">{formatMoney(total)}</span>
      </div>
    </div>
  )
}
