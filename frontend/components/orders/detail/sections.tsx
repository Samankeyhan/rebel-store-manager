"use client"

import * as React from "react"
import { Ban, CircleUserRound, Info, Lock, Printer, Undo2 } from "lucide-react"
import { ChannelBadge, StatusBadge, statusName } from "@/components/common/status"
import { Btn, btnClass, cardClass } from "@/components/record-sale/primitives"
import { categoryPath } from "@/lib/category-path"
import { invoicePdfUrl, type Catalog, type OrderDetail } from "@/lib/api"
import { formatJalaliDateTime } from "@/lib/jalali"
import { formatNumber } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { D } from "../copy"
import {
  CAN_CANCEL,
  CAN_REFUND,
  FORWARD,
  cancelLoss,
  cogs,
  itemsDiscount,
  itemsGross,
  marginPct,
  refundLoss,
  unitCount,
} from "../order-figures"
import { kitName } from "./dialogs"

const TERMINAL_NOTE: Record<string, string> = {
  COMPLETED: D.terminalCompleted,
  CANCELLED: D.terminalCancelled,
  REFUNDED: D.terminalRefunded,
}

function Row({ label, value, className }: { label: React.ReactNode; value: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-baseline justify-between gap-3 text-[13.5px] leading-[22px]", className)}>
      <span className="text-text-2">{label}</span>
      <span className="whitespace-nowrap tabular-nums">{value}</span>
    </div>
  )
}

const neg = (n: number) => (n ? formatNumber(-n) : formatNumber(0))
const sep = <div className="my-0.5 h-px w-full bg-border" />

export type Actions = {
  busy: boolean
  onForward: (status: string) => void
  onCancel: () => void
  onRefund: () => void
}

// ── [1] header card ─────────────────────────────────────────────────────

export function HeaderCard({
  detail,
  catalog,
  timeZone,
  actions,
  mobile,
}: {
  detail: OrderDetail
  catalog: Catalog | null
  timeZone: string
  actions: Actions
  mobile: boolean
}) {
  const { order } = detail
  const forward = FORWARD[order.status] ?? []
  const kit = kitName(detail, catalog)
  const when = formatJalaliDateTime(order.order_date, timeZone)
  const print = (
    <a
      href={invoicePdfUrl(order.id)}
      className={btnClass("outline", "md", mobile ? "size-12 px-0" : undefined)}
      aria-label={mobile ? D.print : undefined}
    >
      <Printer className="size-4" />
      {!mobile && D.print}
    </a>
  )

  if (mobile) {
    const last = forward[forward.length - 1]
    return (
      <section className={cn(cardClass, "flex flex-col gap-2.5 p-3.5")}>
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={order.status} />
          <ChannelBadge channel={order.channel} />
        </div>
        <div className="flex flex-col gap-0.5 text-[13px] text-text-3">
          <span>
            {D.customer}
            <b className="text-foreground">{order.customer_name || "—"}</b>
          </span>
          <span className="tabular-nums">{D.registered(when)}</span>
        </div>
        <div className="flex items-baseline justify-between text-[15px] font-bold">
          <span>{D.total}</span>
          <span className="text-xl tabular-nums">
            {formatNumber(detail.customer_total)} <span className="text-xs font-medium text-text-3">تومان</span>
          </span>
        </div>
        {forward.slice(0, -1).map((s) => (
          <Btn key={s} className="h-12 w-full" disabled={actions.busy} onClick={() => actions.onForward(s)}>
            {D.mobileTransition(statusName(s))}
          </Btn>
        ))}
        <div className={cn("grid gap-2", last ? "grid-cols-[1fr_48px]" : "grid-cols-1")}>
          {last ? (
            <Btn variant="primary" className="h-12" disabled={actions.busy} onClick={() => actions.onForward(last)}>
              {D.mobileTransition(statusName(last))}
            </Btn>
          ) : (
            <span className="flex items-center gap-1.5 text-[13px] text-text-3">
              <Info className="size-4 shrink-0" aria-hidden />
              {TERMINAL_NOTE[order.status]}
            </span>
          )}
          {last ? print : null}
        </div>
        {!last && <div className="flex justify-end">{print}</div>}
      </section>
    )
  }

  return (
    <section className={cn(cardClass, "flex flex-col gap-4 px-5 py-[18px]")}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2.5">
            <span dir="ltr" className="font-mono text-xl font-semibold text-heading">
              {order.invoice_number}
            </span>
            <StatusBadge status={order.status} />
            <ChannelBadge channel={order.channel} />
          </div>
          <div className="flex flex-wrap gap-x-3.5 gap-y-1 text-[13px] text-text-3">
            <span>
              {D.customer}
              <b className="text-foreground">{order.customer_name || "—"}</b>
            </span>
            <span className="tabular-nums">{D.registered(when)}</span>
            <span>{kit ? D.packaging(kit) : D.noPackaging}</span>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end">
          <span className="text-xs text-text-3">{D.total}</span>
          <span className="text-[22px] font-bold tabular-nums">
            {formatNumber(detail.customer_total)} <span className="text-xs font-medium text-text-3">تومان</span>
          </span>
        </div>
      </div>
      <div className="h-px w-full bg-border" />
      <div className="flex flex-wrap items-center gap-2">
        {forward.length > 0 ? (
          <>
            <span className="me-1 text-xs font-bold text-text-3">{D.transitionsLabel}</span>
            {forward.map((s, i) => (
              <Btn
                key={s}
                variant={i === forward.length - 1 ? "primary" : "outline"}
                disabled={actions.busy}
                onClick={() => actions.onForward(s)}
              >
                {statusName(s)}
              </Btn>
            ))}
          </>
        ) : (
          <span className="flex items-center gap-1.5 text-[13px] text-text-3">
            <Info className="size-4" aria-hidden />
            {TERMINAL_NOTE[order.status]}
          </span>
        )}
        {print}
        <span className="grow" />
        {CAN_CANCEL.has(order.status) && (
          <Btn
            className="border-loss-border text-loss hover:bg-loss-soft"
            disabled={actions.busy}
            onClick={actions.onCancel}
          >
            <Ban className="size-4" />
            {D.cancelOrder}
          </Btn>
        )}
        {CAN_REFUND.has(order.status) && (
          <Btn
            className="border-loss-border text-loss hover:bg-loss-soft"
            disabled={actions.busy}
            onClick={actions.onRefund}
          >
            <Undo2 className="size-4 -scale-x-100" />
            {D.refundOrder}
          </Btn>
        )}
      </div>
    </section>
  )
}

/** Mobile «عملیات حساس»: the destructive pair in its own section. */
export function SensitiveActions({ detail, actions }: { detail: OrderDetail; actions: Actions }) {
  const s = detail.order.status
  if (!CAN_CANCEL.has(s) && !CAN_REFUND.has(s)) return null
  return (
    <section className="flex flex-col gap-2 border-t border-dashed border-border-strong pt-3.5">
      <h2 className="text-xs font-bold text-text-3">{D.sensitive}</h2>
      {CAN_CANCEL.has(s) && (
        <Btn
          size="lg"
          className="w-full border-loss-border text-loss hover:bg-loss-soft"
          disabled={actions.busy}
          onClick={actions.onCancel}
        >
          <Ban className="size-4" />
          {D.cancelOrder}
        </Btn>
      )}
      {CAN_REFUND.has(s) && (
        <Btn
          size="lg"
          className="w-full border-loss-border text-loss hover:bg-loss-soft"
          disabled={actions.busy}
          onClick={actions.onRefund}
        >
          <Undo2 className="size-4 -scale-x-100" />
          {D.refundOrder}
        </Btn>
      )}
    </section>
  )
}

// ── [2] items + customer total ─────────────────────────────────────────

function CustomerBlock({ detail, mobile }: { detail: OrderDetail; mobile: boolean }) {
  const discount = itemsDiscount(detail)
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5 text-xs font-bold text-text-3">
        <CircleUserRound className="size-3.5" aria-hidden />
        {D.customerBlock}
      </div>
      <Row label={D.itemsGross} value={formatNumber(itemsGross(detail))} />
      <Row label={D.discount} value={discount ? formatNumber(-discount) : formatNumber(0)} />
      <Row label={D.shipping} value={formatNumber(detail.order.shipping_charge)} />
      {sep}
      <div className="flex items-baseline justify-between gap-3 text-[15px] font-bold">
        <span>{D.total}</span>
        <span className="text-xl tabular-nums">
          {formatNumber(detail.customer_total)}
          {!mobile && <span className="ms-1 text-xs font-medium text-text-3">تومان</span>}
        </span>
      </div>
    </div>
  )
}

export function ItemsCard({
  detail,
  catalog,
  mobile,
}: {
  detail: OrderDetail
  catalog: Catalog | null
  mobile: boolean
}) {
  const categories = new Map((catalog?.products ?? []).map((p) => [p.id, categoryPath(p)]))
  const caption = D.itemsCaption(detail.items.length, unitCount(detail))

  if (mobile) {
    return (
      <section className={cn(cardClass, "overflow-hidden")} aria-labelledby="it">
        <div className="flex justify-between px-3.5 pt-3.5 pb-2">
          <h2 id="it" className="text-sm font-bold text-heading">
            {D.itemsCard}
          </h2>
          <span className="text-xs text-text-3">{caption}</span>
        </div>
        {detail.items.map((i) => (
          <div key={i.id} className="flex items-start justify-between gap-3 border-t border-border px-3.5 py-2.5">
            <div className="flex min-w-0 flex-col">
              <span className="font-bold">{i.product_name}</span>
              <span className="text-xs text-text-3 tabular-nums">
                {D.mobileQty(i.quantity, i.unit_price)}
                {i.discount_amount > 0 && ` · ${D.mobileDiscount(i.discount_amount, i.discount_reason)}`}
              </span>
            </div>
            <b className="tabular-nums">{formatNumber(i.list_price - i.discount_amount)}</b>
          </div>
        ))}
        <div className="border-t border-border px-3.5 py-3">
          <CustomerBlock detail={detail} mobile />
        </div>
      </section>
    )
  }

  return (
    <section className={cn(cardClass, "overflow-hidden")} aria-labelledby="it">
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
        <h2 id="it" className="text-base font-bold text-heading">
          {D.itemsCard}
        </h2>
        <span className="text-xs text-text-3">{caption}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[13.5px]">
          <thead>
            <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
              <th scope="col" className="w-full">
                {D.colProduct}
              </th>
              <th scope="col">{D.colQty}</th>
              <th scope="col">{D.colUnitPrice}</th>
              <th scope="col">{D.colDiscount}</th>
              <th scope="col">{D.colLineTotal}</th>
            </tr>
          </thead>
          <tbody>
            {detail.items.map((i) => {
              const sub = [categories.get(i.product_id), i.discount_reason ? D.discountReason(i.discount_reason) : null]
                .filter(Boolean)
                .join(" · ")
              return (
                <tr
                  key={i.id}
                  className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap last:[&>td]:border-b-0"
                >
                  <td>
                    <div className="flex flex-col leading-[1.4]">
                      <span className="font-bold">{i.product_name}</span>
                      {sub && <span className="text-xs text-text-3">{sub}</span>}
                    </div>
                  </td>
                  <td className="tabular-nums">{formatNumber(i.quantity)}</td>
                  <td className="tabular-nums">{formatNumber(i.unit_price)}</td>
                  <td className={cn("tabular-nums", !i.discount_amount && "text-text-3")}>
                    {i.discount_amount ? formatNumber(-i.discount_amount) : "—"}
                  </td>
                  <td className="font-bold tabular-nums">{formatNumber(i.list_price - i.discount_amount)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="flex justify-end border-t border-border px-5 py-3.5">
        <div className="w-[340px] max-w-full">
          <CustomerBlock detail={detail} mobile={false} />
        </div>
      </div>
    </section>
  )
}

// ── [3] internal cost and profit (never on the invoice) ────────────────

function ProfitBand({ label, value, tone }: { label: string; value: string; tone: "pos" | "neg" | "nil" }) {
  return (
    <div
      className={cn(
        "-mx-2.5 flex items-baseline justify-between gap-3 rounded-lg px-2.5 py-2 text-[15px] font-bold",
        tone === "pos" && "bg-profit-soft text-profit",
        tone === "neg" && "bg-loss-soft text-loss",
        tone === "nil" && "bg-surface-3 text-text-3"
      )}
    >
      <span>{label}</span>
      <span className="text-xl whitespace-nowrap tabular-nums">
        {value}
        {tone !== "nil" && <span className="ms-1 text-xs font-medium">تومان</span>}
      </span>
    </div>
  )
}

export function InternalCard({
  detail,
  catalog,
  mobile,
}: {
  detail: OrderDetail
  catalog: Catalog | null
  mobile: boolean
}) {
  const { order } = detail
  const status = order.status
  const kit = kitName(detail, catalog) ?? D.noPackaging
  const window = catalog?.settings.postage_estimate_window ?? 3
  const draft = status === "DRAFT"
  const cancelled = status === "CANCELLED"
  const refunded = status === "REFUNDED"

  // A draft froze nothing; a cancelled order's packaging came back and it
  // was never posted — neither has real costs to show (only the fee).
  const noCosts = draft || cancelled
  const costRows = (
    <>
      {!mobile && <Row label={D.revenue} value={formatNumber(detail.customer_total)} />}
      <Row label={D.cogs} value={noCosts ? "—" : neg(cogs(detail))} />
      <Row label={D.packagingRow(kit)} value={noCosts ? "—" : neg(order.packaging_cost)} />
      <Row
        label={
          <span className="flex flex-col leading-[1.35]">
            <span>
              {mobile ? D.postageMobile : D.postage}
              {!mobile && (
                <span className="ms-1 inline-flex h-[18px] items-center rounded-md bg-surface-2 px-1.5 text-[10.5px]">
                  {D.estimatedChip}
                </span>
              )}
            </span>
            <span className="text-[11px] text-text-3">{mobile ? D.postageHintShort : D.postageHint(window)}</span>
          </span>
        }
        value={noCosts ? "—" : neg(order.postage_cost)}
      />
      <Row label={D.fee} value={neg(order.transaction_fee)} />
    </>
  )

  let bottom: React.ReactNode
  if (draft) {
    bottom = (
      <>
        <ProfitBand label={mobile ? D.profitMobile : D.profit} value="—" tone="nil" />
        <Note>{D.draftNote}</Note>
      </>
    )
  } else if (cancelled) {
    const loss = cancelLoss(order)
    bottom = (
      <>
        <ProfitBand label={mobile ? D.profitMobile : D.profit} value="—" tone="nil" />
        <Note>{D.cancelledNote}</Note>
        {loss > 0 && <Row label={D.cancelLoss} value={formatNumber(-loss)} className="font-bold text-loss" />}
      </>
    )
  } else if (refunded) {
    const loss = refundLoss(order)
    bottom = (
      <>
        <div className="flex flex-col">
          <Row
            label={D.refundOriginal}
            value={formatNumber(detail.profit)}
            className={cn("font-bold", detail.profit < 0 ? "text-loss" : "text-profit")}
          />
          <span className="text-[11px] text-text-3">{D.refundOriginalNote}</span>
        </div>
        <ProfitBand label={D.refundLoss} value={formatNumber(-loss)} tone="neg" />
        <span className="text-xs text-text-3 tabular-nums">
          {D.refundLossBreakdown(order.packaging_cost, order.postage_cost, order.transaction_fee)}
        </span>
      </>
    )
  } else {
    const profit = detail.profit
    const margin = marginPct(profit, detail.customer_total)
    const shipCost = order.packaging_cost + order.postage_cost
    const shipResult = order.shipping_charge - shipCost
    bottom = (
      <>
        <ProfitBand
          label={mobile ? D.profitMobile : profit < 0 ? D.loss : D.profit}
          value={formatNumber(profit)}
          tone={profit < 0 ? "neg" : "pos"}
        />
        {!mobile && (
          <Row
            label={<span className="text-xs text-text-3">{D.margin}</span>}
            value={<span className="text-xs text-text-3">{margin == null ? "—" : `${formatNumber(margin)}٪`}</span>}
          />
        )}
        {!mobile && (order.shipping_charge > 0 || order.postage_cost > 0) && (
          <div className="rounded-lg border border-border bg-card px-2.5 py-2 text-xs text-text-2 tabular-nums">
            {D.shipEcon(formatNumber(order.shipping_charge), formatNumber(shipCost))}{" "}
            <b className={shipResult < 0 ? "text-loss" : "text-profit"}>{formatNumber(shipResult)}</b>
          </div>
        )}
      </>
    )
  }

  return (
    <section className={cn(cardClass, "bg-surface-2")} aria-labelledby="ic">
      <div
        className={cn(
          "flex items-center justify-between gap-3 border-b border-dashed border-border",
          mobile ? "px-3.5 py-3" : "px-5 py-4"
        )}
      >
        <h2 id="ic" className={cn("flex items-center gap-2 font-bold text-heading", mobile ? "text-sm" : "text-base")}>
          <Lock className="size-4" aria-hidden />
          {D.internalCard}
        </h2>
        <span className="text-xs text-text-3">{D.internalCaption}</span>
      </div>
      <div className={cn("flex flex-col gap-2", mobile ? "p-3.5" : "p-5")}>
        {costRows}
        {sep}
        {bottom}
      </div>
    </section>
  )
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex gap-1.5 text-xs leading-[19px] text-text-3">
      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  )
}
