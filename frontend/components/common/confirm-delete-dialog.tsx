"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { RowActions } from "./copy"

/**
 * The confirmation before a hard delete: what is being deleted (the `lines`), the permanence note, and the
 * refusal if the server says no (`error`). Centred on desktop and phone alike (a short dialog).
 */
export function ConfirmDeleteDialog({
  open,
  title,
  lines,
  confirmLabel,
  busy,
  error,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  lines: React.ReactNode[]
  confirmLabel: string
  busy: boolean
  error: string | null
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent
        showCloseButton={false}
        style={{ maxWidth: "min(440px, calc(100% - 2rem))" }}
        className="w-full gap-0 overflow-hidden rounded-[14px] border border-border bg-card p-0 ring-0 sm:max-w-none"
      >
        <div className="border-b border-border px-6 py-4">
          <DialogTitle className="text-base font-bold text-heading">{title}</DialogTitle>
          <DialogDescription className="sr-only">{RowActions.deleteNote}</DialogDescription>
        </div>
        <div className="flex flex-col gap-3 px-6 py-5 text-sm">
          {error && (
            <Alert tone="err" title={RowActions.remove}>
              <div dir="auto">{error}</div>
            </Alert>
          )}
          <ul className="flex flex-col gap-1.5">
            {lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
          <p className="text-xs leading-[1.8] text-text-3">{RowActions.deleteNote}</p>
        </div>
        <div className="flex justify-start gap-2 border-t border-border bg-surface-2 px-6 py-4">
          <Btn variant="primary" disabled={busy} aria-busy={busy || undefined} onClick={onConfirm}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {confirmLabel}
          </Btn>
          <Btn disabled={busy} onClick={onClose}>
            {RowActions.cancel}
          </Btn>
        </div>
      </DialogContent>
    </Dialog>
  )
}
