"use client"

import * as React from "react"
import Link from "next/link"
import { Check, CircleCheck, CloudOff, ExternalLink, PackagePlus, Plus, Printer, RotateCw, X } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { invoicePdfUrl, type Catalog, type OrderDetail } from "@/lib/api"
import { cn } from "@/lib/utils"
import { formatNumber, formatQuantity } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { T } from "./copy"
import type { Banner } from "./derive"
import { Alert, Btn, ChannelBadge, StatusBadge, btnClass, cardClass } from "./primitives"
import type { ServerIssue } from "./state"

// ── Blocking / soft banners at the top of the form ──────────────────────

export function Banners({ banners, onDraft }: { banners: Banner[]; onDraft: () => void }) {
  // One banner per product and kind, as in the design.
  const seen = new Set<string>()
  const unique = banners.filter((b) => {
    const k = `${b.kind}:${b.severity}:${b.name}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
  const setCost = (
    <Link href="/products" className={btnClass("outline", "sm")}>
      {T.v3SetCost}
      <ExternalLink className="size-3.5" />
    </Link>
  )
  const draftBtn = (
    <Btn variant="ghost" size="sm" onClick={onDraft}>
      {T.saveAsDraft}
    </Btn>
  )
  return (
    <>
      {unique.map((b) => {
        const key = `${b.kind}:${b.severity}:${b.name}`
        if (b.kind === "noCost") {
          return b.severity === "error" ? (
            <Alert
              key={key}
              tone="err"
              icon="lock"
              title={T.v3BannerTitle(b.name)}
              action={
                <div className="flex shrink-0 flex-col gap-1.5">
                  {setCost}
                  {draftBtn}
                </div>
              }
            >
              {T.v3BannerBody}
            </Alert>
          ) : (
            <Alert key={key} tone="warn" icon="triangle" title={T.v3DraftTitle(b.name)} action={setCost}>
              {T.v3DraftBody}
            </Alert>
          )
        }
        return b.severity === "error" ? (
          <Alert key={key} tone="err" icon="lock" title={T.noRecipe(b.name)} action={draftBtn} />
        ) : (
          <Alert key={key} tone="warn" icon="triangle" title={T.noRecipeDraft(b.name)} />
        )
      })}
    </>
  )
}

/**
 * What POST /orders rejected that isn't already shown on a line: a short
 * material (made-to-order or packaging), or any other error.
 */
export function ServerAlert({
  issue,
  onDraft,
  compact,
}: {
  issue: ServerIssue | null
  onDraft: () => void
  /** Also summarise issues shown on a line (for the mobile sheet, which covers the lines). */
  compact?: boolean
}) {
  if (!issue) return null
  if (compact && issue.kind === "stock" && issue.productId != null) {
    return <Alert tone="err">{T.v2Summary(issue.itemName)}</Alert>
  }
  if (compact && issue.kind === "noCost") return <Alert tone="err">{T.v3Summary(issue.name)}</Alert>
  if (compact && issue.kind === "noRecipe") return <Alert tone="err">{T.noRecipeSummary(issue.name)}</Alert>
  if (issue.kind === "stock" && issue.productId == null) {
    const text =
      issue.available <= 0
        ? T.v2BlockingZero(issue.itemName)
        : T.v2Blocking(`${formatQuantity(issue.available)} ${issue.unit ?? ""}`.trim(), issue.itemName)
    return (
      <Alert tone="err">
        <div>{text}</div>
        <button
          type="button"
          className="mt-1 cursor-pointer text-xs font-bold text-heading hover:text-primary"
          onClick={onDraft}
        >
          {T.saveAsDraft}
        </button>
      </Alert>
    )
  }
  if (issue.kind === "generic") {
    return (
      <Alert tone="err" title={T.saveFailedTitle}>
        <div dir="auto">{issue.message}</div>
        <div className="mt-1 text-xs text-text-3">
          {T.errorCode}{" "}
          <span dir="ltr" className="inline-block font-mono">
            {issue.code}
          </span>
        </div>
      </Alert>
    )
  }
  return null
}

// ── Success ──────────────────────────────────────────────────────────────

export function SuccessView({
  result,
  catalog,
  onNewSale,
  mobile,
}: {
  result: OrderDetail
  catalog: Catalog
  onNewSale: () => void
  mobile: boolean
}) {
  const { order, items } = result
  const qty = items.reduce((n, i) => n + i.quantity, 0)
  const draft = order.status === "DRAFT"
  const kit = order.packaging_kit_id == null ? null : catalog.kits.find((k) => k.id === order.packaging_kit_id)
  const note = draft ? T.stockNoteDraft : T.stockNote(qty, kit?.name ?? null)
  // A draft's profit isn't real yet (no costs frozen): «—», as in the design.
  const profit = draft ? null : result.profit
  const profitCls = profit == null ? "text-text-3" : profit < 0 ? "text-loss" : "text-profit"
  const profitText = profit == null ? "—" : formatNumber(profit)

  const disc = (
    <div className="flex size-16 items-center justify-center rounded-full bg-profit-soft text-profit">
      <Check className="size-8" aria-hidden />
    </div>
  )
  const inv = (
    <span dir="ltr" className="font-mono text-lg font-semibold text-heading">
      {order.invoice_number}
    </span>
  )
  const print = (cls: string) => (
    <a href={invoicePdfUrl(order.id)} className={cls}>
      <Printer className="size-4" />
      {T.printInvoice}
    </a>
  )
  const view = (cls: string) => (
    <Link href={`/orders/view/?id=${order.id}`} className={cls}>
      <ExternalLink className="size-4" />
      {T.viewOrder}
    </Link>
  )

  if (mobile) {
    return (
      <section aria-live="polite" className="flex flex-col items-center gap-3 px-1 py-6 text-center">
        {disc}
        <h2 className="text-xl font-bold text-heading">{T.successTitle}</h2>
        {inv}
        <div className="flex gap-2">
          <StatusBadge status={order.status} />
          <ChannelBadge channel={order.channel} />
        </div>
        <div className={cn(cardClass, "mt-2 flex w-full flex-col gap-1.5 px-3.5 py-3")}>
          <div className="flex justify-between text-[13.5px]">
            <span className="text-text-2">{T.tileTotal}</span>
            <b className="tabular-nums">{formatMoney(result.customer_total)}</b>
          </div>
          <div className="flex justify-between text-[13.5px]">
            <span className="text-text-2">{T.tileProfit}</span>
            <b className={cn("tabular-nums", profitCls)}>{profit == null ? "—" : formatMoney(profit)}</b>
          </div>
          <div className="text-start text-xs text-text-3">{note}</div>
        </div>
        <div className="mt-3 flex w-full flex-col gap-2">
          <Btn variant="primary" size="lg" className="w-full" onClick={onNewSale}>
            <Plus className="size-4" />
            {T.newSale}
          </Btn>
          {print(btnClass("outline", "lg", "w-full"))}
          {view(btnClass("ghost", "lg", "w-full"))}
        </div>
      </section>
    )
  }

  return (
    <div className="flex justify-center py-10">
      <section
        aria-live="polite"
        className={cn(cardClass, "flex w-[600px] max-w-full flex-col items-center gap-3.5 px-10 py-9 text-center")}
      >
        {disc}
        <h2 className="text-xl font-bold text-heading">{T.successTitle}</h2>
        <div className="flex items-center gap-2.5">
          {inv}
          <StatusBadge status={order.status} />
          <ChannelBadge channel={order.channel} />
        </div>
        <div className="my-2 grid w-full grid-cols-3 gap-2.5">
          <div className="rounded-[10px] bg-surface-2 p-2.5">
            <div className="text-xs text-text-3">{T.tileTotal}</div>
            <div className="font-bold tabular-nums">{formatNumber(result.customer_total)}</div>
          </div>
          <div className="rounded-[10px] bg-surface-2 p-2.5">
            <div className="text-xs text-text-3">{T.tileProfit}</div>
            <div className={cn("font-bold tabular-nums", profitCls)}>{profitText}</div>
          </div>
          <div className="rounded-[10px] bg-surface-2 p-2.5">
            <div className="text-xs text-text-3">{T.tileItems}</div>
            <div className="font-bold tabular-nums">{T.units(qty)}</div>
          </div>
        </div>
        <p className="text-[13px] text-text-3">{note}</p>
        <div className="mt-1.5 flex flex-wrap justify-center gap-2">
          {print(btnClass("outline"))}
          {view(btnClass("outline"))}
          <Btn variant="primary" onClick={onNewSale}>
            <Plus className="size-4" />
            {T.newSale}
          </Btn>
        </div>
      </section>
    </div>
  )
}

export function Toast({ invoice, onClose }: { invoice: string; onClose: () => void }) {
  React.useEffect(() => {
    const t = window.setTimeout(onClose, 4000)
    return () => window.clearTimeout(t)
  }, [onClose])
  return (
    // Bottom-left is a screen-edge choice (design: toasts sit bottom inline-end).
    <div
      role="status"
      className="fixed bottom-6 left-6 z-50 flex w-[360px] max-w-[calc(100vw-32px)] items-start gap-3 rounded-xl border border-border bg-card px-4 py-3.5 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)]"
    >
      <CircleCheck className="mt-0.5 size-5 shrink-0 text-profit" aria-hidden />
      <div className="min-w-0 grow">
        <div className="text-[13.5px] font-bold">{T.toastTitle(invoice)}</div>
        <div className="text-[12.5px] text-text-3">{T.toastBody}</div>
      </div>
      <Btn variant="ghost" size="sm" className="w-8 px-0" aria-label={T.close} onClick={onClose}>
        <X className="size-4" />
      </Btn>
    </div>
  )
}

// ── Loading / error / empty ──────────────────────────────────────────────

const sk = "rounded-md bg-surface-2"

export function LoadingView({ mobile }: { mobile: boolean }) {
  if (mobile) {
    return (
      <div aria-busy="true" className="flex flex-col gap-3.5">
        <Skeleton className={cn(sk, "h-[200px] rounded-xl")} />
        <Skeleton className={cn(sk, "h-[260px] rounded-xl")} />
        <Skeleton className={cn(sk, "h-[160px] rounded-xl")} />
      </div>
    )
  }
  return (
    <div aria-busy="true" className="flex flex-col items-stretch gap-6 min-[1360px]:flex-row min-[1360px]:items-start">
      <div className="flex min-w-0 grow flex-col gap-5">
        <div className={cn(cardClass, "flex flex-col gap-3.5 p-5")}>
          <Skeleton className={cn(sk, "h-[18px] w-40")} />
          <div className="grid grid-cols-5 gap-2.5">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className={cn(sk, "h-[76px]")} />
            ))}
          </div>
          <Skeleton className={cn(sk, "h-10 w-[360px] max-w-full")} />
        </div>
        <div className={cn(cardClass, "flex flex-col gap-3.5 p-5")}>
          <Skeleton className={cn(sk, "h-[18px] w-36")} />
          <Skeleton className={cn(sk, "h-10")} />
          <Skeleton className={cn(sk, "h-10")} />
          <Skeleton className={cn(sk, "h-8 w-30")} />
        </div>
        <div className={cn(cardClass, "flex flex-col gap-3.5 p-5")}>
          <Skeleton className={cn(sk, "h-[18px] w-36")} />
          <Skeleton className={cn(sk, "h-10 w-80 max-w-full")} />
          <div className="grid grid-cols-4 gap-2.5">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className={cn(sk, "h-[70px]")} />
            ))}
          </div>
        </div>
      </div>
      <div className={cn(cardClass, "flex w-full flex-col gap-3 p-5 min-[1360px]:w-[384px] min-[1360px]:shrink-0")}>
        <Skeleton className={cn(sk, "h-[18px] w-30")} />
        <Skeleton className={cn(sk, "h-4")} />
        <Skeleton className={cn(sk, "h-4")} />
        <Skeleton className={cn(sk, "h-7")} />
        <Skeleton className={cn(sk, "mt-2 h-[120px]")} />
        <Skeleton className={cn(sk, "mt-2 h-12")} />
      </div>
    </div>
  )
}

export function LoadErrorView({ code, onRetry, mobile }: { code: string; onRetry: () => void; mobile: boolean }) {
  const retry = (
    <Btn size={mobile ? "md" : "sm"} className={mobile ? "h-11" : undefined} onClick={onRetry}>
      <RotateCw className="size-3.5" />
      {T.retry}
    </Btn>
  )
  if (mobile) {
    return (
      <div
        role="alert"
        className="flex flex-col gap-2 rounded-[10px] border border-loss-border bg-loss-soft px-4 py-3 text-[13px] leading-[21px]"
      >
        <div className="flex items-center gap-2.5 text-loss">
          <CloudOff className="size-5" aria-hidden />
          <span className="text-[13.5px] font-bold text-foreground">{T.loadErrorTitleMobile}</span>
        </div>
        <span>{T.loadErrorBodyMobile}</span>
        {retry}
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-5">
      <Alert tone="err" icon={<CloudOff className="size-5" />} title={T.loadErrorTitle} action={retry}>
        {T.loadErrorBody}
        <div className="mt-1 text-xs text-text-3">
          {T.errorCode}{" "}
          <span dir="ltr" className="inline-block font-mono">
            {code}
          </span>
        </div>
      </Alert>
      <section role="group" className={cn(cardClass, "opacity-55")} aria-disabled="true">
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-base font-bold text-heading">{T.channelCard}</h2>
        </div>
        <div className="grid grid-cols-5 gap-2.5 p-5">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="h-[76px] rounded-[10px] border border-border-strong bg-card" />
          ))}
        </div>
      </section>
      <section role="group" className={cn(cardClass, "opacity-55")} aria-disabled="true">
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-base font-bold text-heading">{T.itemsCard}</h2>
        </div>
        <div className="flex flex-col items-center gap-2.5 px-6 py-10 text-center">
          <div className="mb-1 flex size-14 items-center justify-center rounded-2xl bg-loss-soft text-loss">
            <CloudOff className="size-6" aria-hidden />
          </div>
          <div className="text-[15px] font-bold text-heading">{T.productsUnavailable}</div>
        </div>
      </section>
    </div>
  )
}

export function EmptyView({ mobile }: { mobile: boolean }) {
  return (
    <section className={cn(cardClass, "w-full")}>
      <div className={cn("flex flex-col items-center gap-2.5 px-6 text-center", mobile ? "py-12" : "py-[88px]")}>
        <div className="mb-1 flex size-14 items-center justify-center rounded-2xl bg-surface-2 text-text-3">
          <PackagePlus className="size-6" aria-hidden />
        </div>
        <div className="text-[15px] font-bold text-heading">{mobile ? T.emptyTitleMobile : T.emptyTitle}</div>
        <div className="max-w-[380px] text-[13px] text-text-3">{mobile ? T.emptyBodyMobile : T.emptyBody}</div>
        <div className="mt-2 flex gap-2">
          <Link href="/products" className={btnClass("primary", mobile ? "lg" : "md")}>
            <Plus className="size-4" />
            {T.addProduct}
          </Link>
          {!mobile && (
            <Link href="/packaging" className={btnClass("outline")}>
              {T.defineKit}
            </Link>
          )}
        </div>
      </div>
    </section>
  )
}
