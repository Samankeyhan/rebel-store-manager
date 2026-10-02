"use client"

import * as React from "react"
import { X } from "lucide-react"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { cn } from "@/lib/utils"
import { P } from "./copy"

/**
 * Edit/add panel (design 05 drawers): 460px, full height, pinned to the
 * physical left edge — a screen-edge choice — on desktop; a bottom sheet on
 * mobile. Header + scrolling body + footer.
 */
export function DrawerShell({
  open,
  onOpenChange,
  mobile,
  title,
  busy,
  children,
  footer,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  mobile: boolean
  title: string
  busy?: boolean
  children: React.ReactNode
  footer: React.ReactNode
}) {
  const guard = (next: boolean) => {
    if (busy && !next) return
    onOpenChange(next)
  }
  return (
    <Sheet open={open} onOpenChange={guard}>
      <SheetContent
        side={mobile ? "bottom" : "left"}
        showCloseButton={false}
        className={cn(
          "gap-0 bg-card p-0",
          mobile ? "max-h-[92vh] rounded-t-[18px]" : "rounded-s-[14px] data-[side=left]:w-[460px] data-[side=left]:max-w-[calc(100vw-2rem)] data-[side=left]:sm:max-w-[460px]"
        )}
      >
        {mobile && <div className="mx-auto mt-2 h-1 w-10 shrink-0 rounded bg-border-strong" aria-hidden />}
        <div className="flex shrink-0 items-center justify-between border-b border-border px-6 py-5">
          <SheetTitle className="text-base font-bold text-heading">{title}</SheetTitle>
          <SheetDescription className="sr-only">{title}</SheetDescription>
          <Btn variant="ghost" size="sm" className="size-8 px-0" aria-label={P.close} disabled={busy} onClick={() => guard(false)}>
            <X className="size-4" />
          </Btn>
        </div>
        <div className="flex min-h-0 grow flex-col gap-4 overflow-y-auto px-6 py-5">{children}</div>
        <div className="flex shrink-0 items-center gap-2 border-t border-border bg-surface-2 px-6 py-4">{footer}</div>
      </SheetContent>
    </Sheet>
  )
}

/** `.switch` (role=switch). */
export function Switch({
  checked,
  onChange,
  disabled,
  id,
  labelledBy,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
  id?: string
  labelledBy?: string
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-labelledby={labelledBy}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-5 w-9 shrink-0 cursor-pointer rounded-full bg-surface-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50",
        checked && "bg-heading"
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 size-4 rounded-full bg-white shadow transition-[inset-inline-start]",
          checked ? "start-[18px]" : "start-0.5"
        )}
        aria-hidden
      />
    </button>
  )
}

/** Inline failure banner inside a drawer: the backend's message + code. */
export function SaveError({ message, code }: { message: string; code: string }) {
  return (
    <Alert tone="err" title={P.saveFailed}>
      <div dir="auto">{message}</div>
      <div className="mt-1 text-xs text-text-3">
        {P.errorCode}{" "}
        <span dir="ltr" className="inline-block font-mono">
          {code}
        </span>
      </div>
    </Alert>
  )
}

export function FieldError({ children }: { children: React.ReactNode }) {
  return (
    <span role="alert" className="text-xs font-medium text-loss">
      {children}
    </span>
  )
}

export const textInputClass = (mobile: boolean, error?: boolean) =>
  cn(
    "w-full rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
    mobile ? "h-11" : "h-10",
    error && "border-loss ring-3 ring-loss-soft"
  )
