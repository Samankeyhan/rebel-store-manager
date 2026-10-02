"use client"

import * as React from "react"
import { CircleAlert } from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { Btn } from "@/components/record-sale/primitives"
import { cn } from "@/lib/utils"
import { D, L } from "../copy"

export type EffectTone = "up" | "down" | "flat"

/** `.effect` row: tinted icon chip (↑ returns / ↓ lost / = neutral) + bold lead-in + body. */
export function Effect({
  tone,
  icon: Icon,
  lead,
  children,
}: {
  tone: EffectTone
  icon: React.ComponentType<{ className?: string }>
  lead?: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg bg-surface-2 px-3 py-2.5 text-[13px] leading-[21px]">
      <span
        className={cn(
          "flex size-6 shrink-0 items-center justify-center rounded-md",
          tone === "up" && "bg-profit-soft text-profit",
          tone === "down" && "bg-loss-soft text-loss",
          tone === "flat" && "bg-surface-3 text-text-2"
        )}
        aria-hidden
      >
        <Icon className="size-3.5" />
      </span>
      <div>
        {lead && <b>{lead}</b>} {children}
      </div>
    </div>
  )
}

export function Irreversible() {
  return (
    <p className="flex items-center gap-1.5 text-xs font-bold text-loss">
      <CircleAlert className="size-3.5" aria-hidden />
      {D.irreversible}
    </p>
  )
}

/**
 * A destructive or stock-affecting confirmation. Desktop: a centred
 * alertdialog (centred on the viewport, not on a 1440 board as drawn).
 * Mobile: a bottom sheet. Focus starts on «انصراف»; while the request is in
 * flight the dialog can't be dismissed.
 */
export function ConfirmShell({
  open,
  onOpenChange,
  mobile,
  busy,
  icon: Icon,
  danger = true,
  title,
  subtitle,
  confirmLabel,
  confirmIcon: ConfirmIcon,
  confirmDisabled = false,
  onConfirm,
  width = 560,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  mobile: boolean
  busy: boolean
  icon: React.ComponentType<{ className?: string }>
  danger?: boolean
  title: string
  subtitle?: string
  confirmLabel: string
  confirmIcon?: React.ComponentType<{ className?: string }>
  /** Keeps the confirm button disabled (e.g. until a required choice is made). */
  confirmDisabled?: boolean
  onConfirm: () => void
  width?: number
  children: React.ReactNode
}) {
  const cancelRef = React.useRef<HTMLButtonElement>(null)
  const guard = (next: boolean) => {
    if (busy && !next) return
    onOpenChange(next)
  }
  const focusCancel = (e: Event) => {
    e.preventDefault()
    cancelRef.current?.focus()
  }

  const iconDisc = (
    <span
      className={cn(
        "flex size-10 shrink-0 items-center justify-center rounded-full",
        danger ? "bg-loss-soft text-loss" : "bg-navy-soft text-heading"
      )}
      aria-hidden
    >
      <Icon className="size-5" />
    </span>
  )

  const confirm = (
    <Btn
      variant="primary"
      className={cn(
        danger && "bg-loss hover:bg-loss/90",
        mobile && "h-12 w-full"
      )}
      disabled={busy || confirmDisabled}
      aria-busy={busy || undefined}
      onClick={onConfirm}
    >
      {busy ? (
        <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />
      ) : (
        ConfirmIcon && <ConfirmIcon className="size-4" />
      )}
      {confirmLabel}
    </Btn>
  )
  const cancel = (
    <Btn ref={cancelRef} className={mobile ? "h-12 w-full" : undefined} disabled={busy} onClick={() => guard(false)}>
      {L.cancel}
    </Btn>
  )

  if (mobile) {
    return (
      <Sheet open={open} onOpenChange={guard}>
        <SheetContent
          side="bottom"
          showCloseButton={false}
          role="alertdialog"
          onOpenAutoFocus={focusCancel}
          className="max-h-[92vh] gap-3 overflow-y-auto rounded-t-[18px] bg-card px-4 pb-5"
        >
          <div className="mx-auto mt-2 h-1 w-10 rounded bg-border-strong" aria-hidden />
          <div className="flex items-start gap-3">
            {iconDisc}
            <div className="flex flex-col gap-0.5">
              <SheetTitle className="text-base font-bold text-heading">{title}</SheetTitle>
              {subtitle ? (
                <SheetDescription className="text-[13px] text-text-3">{subtitle}</SheetDescription>
              ) : (
                <SheetDescription className="sr-only">{title}</SheetDescription>
              )}
            </div>
          </div>
          {children}
          <div className="mt-1 flex flex-col gap-2">
            {confirm}
            {cancel}
          </div>
        </SheetContent>
      </Sheet>
    )
  }

  return (
    <Dialog open={open} onOpenChange={guard}>
      <DialogContent
        showCloseButton={false}
        role="alertdialog"
        onOpenAutoFocus={focusCancel}
        style={{ maxWidth: `min(${width}px, calc(100% - 2rem))` }}
        className="w-full gap-0 overflow-hidden rounded-[14px] border border-border bg-card p-0 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)] ring-0 sm:max-w-none"
      >
        <div className="flex items-start gap-3.5 px-6 pt-5">
          {iconDisc}
          <div className="flex flex-col gap-0.5">
            <DialogTitle className="text-base font-bold text-heading">{title}</DialogTitle>
            {subtitle ? (
              <DialogDescription className="text-[13px] text-text-3">{subtitle}</DialogDescription>
            ) : (
              <DialogDescription className="sr-only">{title}</DialogDescription>
            )}
          </div>
        </div>
        <div className="flex max-h-[60vh] flex-col gap-3.5 overflow-y-auto px-6 py-4">{children}</div>
        <div className="flex justify-start gap-2 border-t border-border bg-surface-2 px-6 py-4">
          {confirm}
          {cancel}
        </div>
      </DialogContent>
    </Dialog>
  )
}
