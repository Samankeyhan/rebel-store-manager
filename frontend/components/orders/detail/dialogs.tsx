"use client"

import * as React from "react"
import {
  Ban,
  Box,
  ChartColumn,
  Package,
  PackageCheck,
  Percent,
  Truck,
  Undo2,
  Wallet,
} from "lucide-react"
import { statusName } from "@/components/common/status"
import { cn } from "@/lib/utils"
import type { Catalog, OrderDetail } from "@/lib/api"
import { formatJalali, utcToLocal } from "@/lib/jalali"
import { formatNumber } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { D } from "../copy"
import { refundLoss } from "../order-figures"
import { ConfirmShell, Effect, Irreversible } from "./confirm-shell"

const MirroredTruck = ({ className }: { className?: string }) => (
  <Truck className={cn(className, "-scale-x-100")} />
)
const MirroredUndo = ({ className }: { className?: string }) => (
  <Undo2 className={cn(className, "-scale-x-100")} />
)

/** «۱ «A»، ۲ «B» و ۳ «C»» */
function joinLines(parts: string[]): string {
  if (parts.length <= 1) return parts.join("")
  return `${parts.slice(0, -1).join("، ")} و ${parts[parts.length - 1]}`
}

function lineList(items: OrderDetail["items"]): string {
  return joinLines(items.map((i) => `${formatNumber(i.quantity)} «${i.product_name}»`))
}

export function kitName(detail: OrderDetail, catalog: Catalog | null): string | null {
  const id = detail.order.packaging_kit_id
  if (id == null) return null
  return catalog?.kits.find((k) => k.id === id)?.name ?? D.unknownKit
}

function madeToOrderIds(catalog: Catalog | null): Set<number> {
  return new Set((catalog?.products ?? []).filter((p) => p.made_to_order).map((p) => p.id))
}

function ReasonField({
  id,
  label,
  placeholder,
  optional,
  value,
  onChange,
  mobile,
}: {
  id: string
  label: string
  placeholder: string
  optional?: boolean
  value: string
  onChange: (v: string) => void
  mobile: boolean
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-semibold">
        {label} {optional && <span className="font-normal text-text-3">{D.optional}</span>}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          "w-full rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
          mobile ? "h-11" : "h-10"
        )}
      />
      <span className="text-xs text-text-3">{D.reasonHelp}</span>
    </div>
  )
}

type DialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  detail: OrderDetail
  catalog: Catalog | null
  timeZone: string
  mobile: boolean
  busy: boolean
}

/**
 * Cancel: only from DRAFT/PENDING/PAID (never shipped). Restores products
 * and packaging if stock was committed; postage is not a cost; the fee is
 * the only loss. A DRAFT committed nothing, so nothing returns and nothing
 * is lost.
 */
export function CancelDialog({
  onConfirm,
  ...p
}: DialogProps & { onConfirm: (reason: string | null) => void }) {
  const { order, items } = p.detail
  const committed = !!order.stock_committed
  const [reason, setReason] = React.useState("")
  const mto = madeToOrderIds(p.catalog)
  const normalLines = items.filter((i) => !mto.has(i.product_id))
  const mtoLines = items.filter((i) => mto.has(i.product_id))
  const kit = kitName(p.detail, p.catalog)
  const localDay = utcToLocal(order.order_date, p.timeZone)
  const month = localDay ? formatJalali(localDay.iso, "MMMM") : ""
  const inv = order.invoice_number ?? ""

  return (
    <ConfirmShell
      open={p.open}
      onOpenChange={(o) => {
        if (!o) setReason("")
        p.onOpenChange(o)
      }}
      mobile={p.mobile}
      busy={p.busy}
      icon={Ban}
      title={D.cancelTitle(inv)}
      subtitle={committed ? D.cancelSubtitle(statusName(order.status)) : D.cancelSubtitleDraft(statusName(order.status))}
      confirmLabel={D.cancelOrder}
      confirmIcon={Ban}
      onConfirm={() => onConfirm(committed && reason.trim() ? reason.trim() : null)}
    >
      {committed ? (
        <>
          {normalLines.length > 0 && (
            <Effect tone="up" icon={Package} lead={D.effProductsLead}>
              {lineList(normalLines)}.
            </Effect>
          )}
          {mtoLines.map((i) => (
            <Effect key={i.id} tone="up" icon={Package}>
              {D.effMadeToOrder(i.product_name)}
            </Effect>
          ))}
          {kit && (
            <Effect tone="up" icon={Box} lead={D.effPackagingLead}>
              {formatNumber(1)} «{kit}».
            </Effect>
          )}
          <Effect tone="flat" icon={MirroredTruck} lead={D.effNoPostageLead}>
            {D.effNoPostageBody}
          </Effect>
          {order.transaction_fee > 0 ? (
            <Effect tone="down" icon={Percent} lead={D.effFeeLead}>
              <span className="tabular-nums">{formatMoney(order.transaction_fee)}</span> {D.effFeeBody}
            </Effect>
          ) : (
            <Effect tone="flat" icon={Percent} lead={D.effNoLossLead}>
              {D.effNoLossBody}
            </Effect>
          )}
        </>
      ) : (
        <Effect tone="flat" icon={Package}>
          {D.effDraftNothing}
        </Effect>
      )}
      {order.status === "PAID" && (
        <Effect tone="flat" icon={Wallet} lead={D.effMoneyLead}>
          <span className="tabular-nums">{formatMoney(p.detail.customer_total)}</span> {D.effMoneyBody}
        </Effect>
      )}
      <Effect tone="flat" icon={ChartColumn} lead={D.effReportsLead}>
        {committed ? D.effReportsBody(month) : D.effReportsDraft}
      </Effect>
      {/* The reason is stored only alongside restored stock: a draft has none,
          so the field would silently go nowhere. */}
      {committed && (
        <ReasonField
          id="cancel-reason"
          label={D.cancelReasonLabel}
          placeholder={D.cancelReasonPlaceholder}
          value={reason}
          onChange={setReason}
          mobile={p.mobile}
        />
      )}
      <Irreversible />
    </ConfirmShell>
  )
}

/**
 * Refund: only from PAID/COMPLETED (always committed). Products come back
 * (made-to-order units as finished stock); packaging was used up; packaging
 * + postage + fee become the loss. No amount is captured.
 */
export function RefundDialog({
  onConfirm,
  ...p
}: DialogProps & { onConfirm: (reason: string | null) => void }) {
  const { order, items } = p.detail
  const [reason, setReason] = React.useState("")
  const loss = refundLoss(order)
  const inv = order.invoice_number ?? ""

  return (
    <ConfirmShell
      open={p.open}
      onOpenChange={(o) => {
        if (!o) setReason("")
        p.onOpenChange(o)
      }}
      mobile={p.mobile}
      busy={p.busy}
      icon={MirroredUndo}
      title={D.refundTitle(inv)}
      subtitle={D.refundSubtitle}
      confirmLabel={D.refundOrder}
      confirmIcon={MirroredUndo}
      onConfirm={() => onConfirm(reason.trim() || null)}
      width={580}
    >
      <Effect tone="up" icon={PackageCheck} lead={D.effOnlyProductsLead}>
        {lineList(items)}.
      </Effect>
      <Effect tone="down" icon={Box} lead={D.effLossLead}>
        <span className="tabular-nums">
          {D.effLossBody(order.packaging_cost, order.postage_cost, order.transaction_fee, loss)}
        </span>
        {order.packaging_kit_id != null && <> {D.effBoxNotReturned}</>}
      </Effect>
      <Effect tone="flat" icon={Wallet} lead={D.effRefundMoneyLead}>
        {D.effRefundMoneyBody}
      </Effect>
      {/* Both figures, kept apart as the P&L keeps gross profit and refund losses. */}
      <div className="grid grid-cols-2 gap-2.5 rounded-[10px] bg-surface-2 p-3">
        <div className="flex flex-col">
          <span className="text-xs text-text-3">{D.refundOriginal}</span>
          <span
            className={cn(
              "font-bold tabular-nums",
              p.detail.profit < 0 ? "text-loss" : "text-profit"
            )}
          >
            {formatMoney(p.detail.profit)}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-xs text-text-3">{D.refundLoss}</span>
          <span className="font-bold text-loss tabular-nums">{formatMoney(-loss)}</span>
        </div>
      </div>
      <ReasonField
        id="refund-reason"
        label={D.refundReasonLabel}
        placeholder={D.refundReasonPlaceholder}
        optional
        value={reason}
        onChange={setReason}
        mobile={p.mobile}
      />
      <Irreversible />
    </ConfirmShell>
  )
}

/** Leaving DRAFT commits stock for the first time: say so before doing it. */
export function CommitConfirm({
  target,
  onConfirm,
  ...p
}: Omit<DialogProps, "catalog" | "timeZone"> & { target: string; onConfirm: () => void }) {
  const name = statusName(target)
  return (
    <ConfirmShell
      open={p.open}
      onOpenChange={p.onOpenChange}
      mobile={p.mobile}
      busy={p.busy}
      danger={false}
      icon={PackageCheck}
      title={D.commitTitle(name)}
      confirmLabel={D.commitConfirm(name)}
      onConfirm={onConfirm}
      width={480}
    >
      <p className="text-[13px] leading-[22px] text-text-2">{D.commitBody}</p>
    </ConfirmShell>
  )
}
