"use client"

import * as React from "react"
import { Ban, ChartColumn, Package, ShoppingCart } from "lucide-react"
import { ConfirmShell, Effect } from "@/components/orders/detail/confirm-shell"
import type { Material, Product } from "@/lib/api"
import { formatQuantity } from "@/lib/persian-numbers"
import { P } from "./copy"
import { unitLabel } from "./figures"

export type DeactivateTarget = { kind: "product"; item: Product } | { kind: "material"; item: Material }

/** Deactivation is the app's substitute for deletion — and one-way for now. */
export function DeactivateDialog({
  target,
  mobile,
  busy,
  onCancel,
  onConfirm,
}: {
  target: DeactivateTarget | null
  mobile: boolean
  busy: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  // Keep the last target while the dialog animates closed.
  const [last, setLast] = React.useState(target)
  if (target && target !== last) setLast(target)
  const t = target ?? last
  if (!t) return null
  const material = t.kind === "material"

  return (
    <ConfirmShell
      open={target != null}
      onOpenChange={(o) => !o && onCancel()}
      mobile={mobile}
      busy={busy}
      icon={Ban}
      title={P.deactivateTitle(t.item.name)}
      subtitle={material ? P.matDeactivateSubtitle : P.deactivateSubtitle}
      confirmLabel={P.deactivate}
      confirmIcon={Ban}
      onConfirm={onConfirm}
      width={520}
    >
      <Effect tone="flat" icon={ShoppingCart}>
        {material ? P.matEffHidden : P.effHidden}
      </Effect>
      <Effect tone="flat" icon={ChartColumn}>
        {P.effHistory}
      </Effect>
      {t.kind === "product" && (
        <Effect tone="flat" icon={Package}>
          {P.effStock(t.item.current_stock)}
        </Effect>
      )}
      {t.kind === "material" && t.item.current_stock != null && (
        <Effect tone="flat" icon={Package}>
          {P.matEffStock(`${formatQuantity(t.item.current_stock)} ${unitLabel(t.item.unit)}`)}
        </Effect>
      )}
      <p className="text-xs text-text-3">{P.deactivateFinal}</p>
    </ConfirmShell>
  )
}
