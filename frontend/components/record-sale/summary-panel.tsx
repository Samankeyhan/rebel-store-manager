"use client"

import * as React from "react"
import { Check, ChevronUp, CircleUserRound, Lock, Truck, X } from "lucide-react"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import type { Catalog } from "@/lib/api"
import { cn } from "@/lib/utils"
import { formatNumber } from "@/lib/persian-numbers"
import { T, type Channel, type SaleStatus } from "./copy"
import type { Summary } from "./derive"
import { Alert, Btn, ChannelBadge, Kbd, cardClass, negAmount } from "./primitives"

function Row({
  label,
  value,
  className,
}: {
  label: React.ReactNode
  value: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex items-baseline justify-between gap-3 text-[13.5px] leading-[22px]", className)}>
      <span className="text-text-2">{label}</span>
      <span className="whitespace-nowrap tabular-nums">{value}</span>
    </div>
  )
}

const sep = <div className="my-1 h-px w-full bg-border" />

function profitTone(profit: number | null) {
  if (profit == null) return { text: "text-text-3", bg: "bg-surface-3", label: T.profit }
  if (profit < 0) return { text: "text-loss", bg: "bg-loss-soft", label: T.loss }
  return { text: "text-profit", bg: "bg-profit-soft", label: T.profit }
}

function CustomerRows({ s, mobile }: { s: Summary; mobile: boolean }) {
  return (
    <>
      <Row label={T.itemsGross(s.qtyTotal)} value={formatNumber(s.itemsGross)} />
      <Row label={T.discount} value={s.discount ? formatNumber(-s.discount) : formatNumber(0)} />
      <Row
        label={
          <>
            {T.shipping}
            {mobile && s.shippingOverridden && (
              <span className="ms-1 inline-flex h-[18px] items-center rounded-md bg-warn-soft px-1.5 text-[10.5px] text-warn">
                {T.manualChip}
              </span>
            )}
          </>
        }
        value={formatNumber(s.shipping)}
      />
      {!mobile && sep}
      <div className="flex items-baseline justify-between gap-3 text-[15px] font-bold">
        <span>{T.payable}</span>
        <span className="text-xl whitespace-nowrap tabular-nums">
          {formatNumber(s.total)}
          {!mobile && <span className="ms-1 text-xs font-medium text-text-3">{T.toman}</span>}
        </span>
      </div>
    </>
  )
}

function InternalRows({ s, window, mobile }: { s: Summary; window: number; mobile: boolean }) {
  const tone = profitTone(s.profit)
  return (
    <>
      <Row label={T.cogs} value={s.cost == null ? T.unknown : negAmount(s.cost)} />
      <Row label={T.packaging(s.kitName)} value={negAmount(s.kitCost)} />
      <Row
        label={
          <span className="flex flex-col leading-[1.35]">
            {T.postageRow}
            <span className="text-[11px] text-text-3">{mobile ? T.postageHintShort : T.postageHint(window)}</span>
          </span>
        }
        value={negAmount(s.postage)}
      />
      <Row label={T.fee} value={negAmount(s.fee)} />
      {!mobile && sep}
      <div
        className={cn(
          "-mx-2.5 flex items-baseline justify-between gap-3 rounded-lg px-2.5 py-2 text-[15px] font-bold",
          mobile && "mt-0.5 py-1.5",
          tone.bg
        )}
      >
        <span className={tone.text}>{tone.label}</span>
        <span className={cn("text-xl whitespace-nowrap tabular-nums", tone.text)}>
          {s.profit == null ? T.unknown : formatNumber(s.profit)}
          {s.profit != null && !mobile && <span className="ms-1 text-xs font-medium">{T.toman}</span>}
        </span>
      </div>
      {!mobile && (
        <div className="flex items-baseline justify-between gap-3 text-xs">
          <span className="text-text-3">{T.margin}</span>
          <span className="text-text-3 tabular-nums">
            {s.marginPct == null ? "—" : `${formatNumber(s.marginPct)}٪`}
          </span>
        </div>
      )}
      {s.showShipEcon && (
        <div
          className={cn(
            "flex items-start gap-1.5 text-xs leading-[19px] text-text-2",
            !mobile && "rounded-lg border border-border bg-card px-2.5 py-2"
          )}
        >
          {!mobile && <Truck className="mt-0.5 size-3.5 shrink-0 -scale-x-100" aria-hidden />}
          <span>
            {T.shipEcon} {formatNumber(s.shipping)} {T.shipEconCost} {formatNumber(s.shipCost)} ={" "}
            <b className={s.shipResult < 0 ? "text-loss" : "text-profit"}>{formatNumber(s.shipResult)}</b>
          </span>
        </div>
      )}
    </>
  )
}

export function ErrorList({ errors }: { errors: string[] }) {
  if (errors.length === 0) return null
  return (
    <Alert tone="err" title={T.errorCount(errors.length)} className="px-3.5 py-2.5">
      {errors.map((e, i) => (
        <div key={i}>• {e}</div>
      ))}
    </Alert>
  )
}

type SaveProps = {
  status: SaleStatus
  disabled: boolean
  saving: boolean
  onSave: () => void
}

function SaveButton({ status, disabled, saving, onSave, className }: SaveProps & { className?: string }) {
  return (
    <Btn
      variant="primary"
      size="lg"
      className={cn("w-full", className)}
      disabled={disabled || saving}
      aria-busy={saving || undefined}
      onClick={onSave}
    >
      {saving ? (
        <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />
      ) : (
        <Check className="size-[18px]" />
      )}
      {saving ? T.saving : status === "DRAFT" ? T.saveDraft : T.saveSale}
    </Btn>
  )
}

/** Desktop: the sticky 384px summary column. */
export function SummaryPanel({
  summary,
  channel,
  catalog,
  errors,
  serverAlert,
  onCancel,
  ...save
}: SaveProps & {
  summary: Summary
  channel: Channel
  catalog: Catalog
  errors: string[]
  serverAlert: React.ReactNode
  onCancel: () => void
}) {
  return (
    <aside aria-label={T.summaryAria} className="flex w-full flex-col gap-3 min-[1360px]:sticky min-[1360px]:top-20 min-[1360px]:w-[384px] min-[1360px]:shrink-0">
      <div className={cn(cardClass, "overflow-hidden")}>
        <div className="flex flex-col gap-2 px-5 py-4">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-bold text-heading">
              <CircleUserRound className="size-4" aria-hidden />
              {T.customerPart}
            </h2>
            <ChannelBadge channel={channel} />
          </div>
          <CustomerRows s={summary} mobile={false} />
        </div>
        <div className="flex flex-col gap-2 border-t-2 border-dashed border-border-strong bg-surface-2 px-5 py-4">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-bold text-heading">
              <Lock className="size-4" aria-hidden />
              {T.internalPart}
            </h2>
            <span className="text-xs text-text-3">{T.internalPartCaption}</span>
          </div>
          <InternalRows s={summary} window={catalog.settings.postage_estimate_window} mobile={false} />
        </div>
      </div>
      {serverAlert}
      <ErrorList errors={errors} />
      <SaveButton {...save} />
      <div className="flex items-center justify-between">
        <Btn variant="ghost" size="sm" onClick={onCancel}>
          {T.cancel}
        </Btn>
        <span className="text-xs text-text-3">
          <Kbd>Ctrl Enter</Kbd> {T.quickSave}
        </span>
      </div>
    </aside>
  )
}

/** Mobile: collapsed bar pinned to the bottom, expanding into a sheet. */
export function MobileSummarySheet({
  summary,
  catalog,
  errors,
  serverAlert,
  ...save
}: SaveProps & { summary: Summary; catalog: Catalog; errors: string[]; serverAlert: React.ReactNode }) {
  const [open, setOpen] = React.useState(false)
  const tone = profitTone(summary.profit)
  return (
    <>
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pb-5 shadow-[0_-8px_24px_rgba(18,22,38,.10)]">
        <div className="mx-auto mt-2 h-1 w-10 rounded bg-border-strong" aria-hidden />
        <button
          type="button"
          aria-expanded={open}
          aria-label={T.showSummary}
          onClick={() => setOpen(true)}
          className="flex w-full cursor-pointer items-center justify-between py-2.5 outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
        >
          <span className="flex flex-col items-start leading-[1.35]">
            <span className="text-xs text-text-3">{T.payable}</span>
            <span className="text-[19px] font-bold tabular-nums">
              {formatNumber(summary.total)} <span className="text-xs font-medium text-text-3">{T.toman}</span>
            </span>
          </span>
          <span className="flex flex-col items-end leading-[1.35]">
            <span className="flex items-center gap-1 text-xs text-text-3">
              <Lock className="size-3" aria-hidden />
              {T.profitShort}
            </span>
            <span className={cn("font-bold tabular-nums", tone.text)}>
              {summary.profit == null ? T.unknown : formatNumber(summary.profit)}
            </span>
          </span>
          <ChevronUp className="size-4 text-text-3" aria-hidden />
        </button>
        <SaveButton {...save} />
      </div>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side="bottom"
          showCloseButton={false}
          className="max-h-[90vh] gap-0 overflow-y-auto rounded-t-[18px] bg-card px-4 pb-5"
        >
          <div className="mx-auto mt-2 h-1 w-10 rounded bg-border-strong" aria-hidden />
          <div className="flex items-center justify-between pt-2.5 pb-1">
            <SheetTitle className="text-base font-bold text-heading">{T.summaryAria}</SheetTitle>
            <SheetDescription className="sr-only">{T.customerPart}</SheetDescription>
            <Btn variant="ghost" className="size-11 px-0" aria-label={T.close} onClick={() => setOpen(false)}>
              <X className="size-4" />
            </Btn>
          </div>
          <div className="flex flex-col gap-1.5 pb-3">
            <div className="flex items-center gap-1.5 text-xs font-bold text-text-3">
              <CircleUserRound className="size-3.5" aria-hidden />
              {T.customerPart}
            </div>
            <CustomerRows s={summary} mobile />
          </div>
          <div className="-mx-4 flex flex-col gap-1.5 border-t-2 border-dashed border-border-strong bg-surface-2 px-4 py-3">
            <div className="flex items-center gap-1.5 text-xs font-bold text-text-3">
              <Lock className="size-3.5" aria-hidden />
              {T.internalPartMobile}
            </div>
            <InternalRows s={summary} window={catalog.settings.postage_estimate_window} mobile />
          </div>
          {/* Errors from the last submit, visible without closing the sheet. */}
          <div className="mt-3 empty:hidden">{serverAlert}</div>
          {errors.length > 0 && (
            <div className="mt-3">
              <ErrorList errors={errors} />
            </div>
          )}
          <SaveButton {...save} className="mt-3.5" />
        </SheetContent>
      </Sheet>
    </>
  )
}
