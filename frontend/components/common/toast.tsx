"use client"

import * as React from "react"
import { CircleCheck, X } from "lucide-react"
import { Btn } from "@/components/record-sale/primitives"

/** design-system §5 Toast: bottom-left (a screen-edge choice), closes after 5s. */
export function Toast({ title, onClose, closeLabel }: { title: string; onClose: () => void; closeLabel: string }) {
  React.useEffect(() => {
    const t = window.setTimeout(onClose, 5000)
    return () => window.clearTimeout(t)
  }, [onClose, title])
  return (
    <div
      role="status"
      className="fixed bottom-6 left-6 z-50 flex w-[380px] max-w-[calc(100vw-32px)] items-center gap-3 rounded-xl border border-border bg-card px-4 py-3.5 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)]"
    >
      <CircleCheck className="size-5 shrink-0 text-profit" aria-hidden />
      <div className="min-w-0 grow text-[13.5px] font-bold">{title}</div>
      <Btn variant="ghost" size="sm" className="w-8 px-0" aria-label={closeLabel} onClick={onClose}>
        <X className="size-4" />
      </Btn>
    </div>
  )
}
