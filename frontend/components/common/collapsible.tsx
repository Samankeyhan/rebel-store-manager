"use client"

import * as React from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * A disclosure: a button with a chevron that shows or hides its content.
 * Closed on every mount; the open state is local and never persisted. The
 * content isn't rendered while closed, so hidden values aren't in the DOM.
 * `onFirstOpen` lets a caller defer loading until the user asks.
 */
export function Collapsible({
  label,
  children,
  className,
  buttonClassName,
  onFirstOpen,
}: {
  label: React.ReactNode
  children: React.ReactNode
  className?: string
  buttonClassName?: string
  onFirstOpen?: () => void
}) {
  const [open, setOpen] = React.useState(false)
  const [opened, setOpened] = React.useState(false)
  const id = React.useId()
  const toggle = () => {
    if (!open && !opened) {
      setOpened(true)
      onFirstOpen?.()
    }
    setOpen(!open)
  }
  return (
    <div className={cn("flex flex-col", className)}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={toggle}
        className={cn(
          "flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg px-1 py-1 text-start text-[13px] font-semibold text-text-2 outline-none hover:bg-surface-2 focus-visible:ring-3 focus-visible:ring-ring/30",
          buttonClassName
        )}
      >
        <span className="min-w-0">{label}</span>
        <ChevronDown className={cn("size-4 shrink-0 text-text-3 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      <div id={id} hidden={!open}>
        {open && children}
      </div>
    </div>
  )
}
