"use client"

import * as React from "react"
import Link from "next/link"
import { ChevronDown, ExternalLink, Info } from "lucide-react"
import { Money } from "@/components/common/money"
import { signedTone } from "@/lib/reports"
import { cn } from "@/lib/utils"
import { R } from "./copy"

const PLUS = "‎+"
const toneText = { profit: "text-profit", loss: "text-loss", plain: "" } as const

/**
 * A figure that can be negative (a net result, a gap, a difference): «+»
 * and the colour come from its real sign; a negative prints its own minus.
 * `neutral` keeps the colour plain for a figure that is neither profit nor loss.
 */
export function SignedMoney({
  value,
  neutral = false,
  className,
}: {
  value: number
  neutral?: boolean
  className?: string
}) {
  const s = signedTone(value, neutral)
  return (
    <span className={cn("whitespace-nowrap", toneText[s.tone], className)}>
      {s.glyph && (
        <span dir="ltr" className="tabular-nums">
          {PLUS}
        </span>
      )}
      <Money value={value} />
    </span>
  )
}

/** The info box under a report (same look as the P&L's scope note). */
export function ReportNote({ children }: { children: React.ReactNode }) {
  return (
    <div role="note" className="flex items-start gap-2.5 rounded-xl bg-info-soft px-3.5 py-3 text-[12.5px] leading-[21px] text-text-2">
      <Info className="mt-0.5 size-[18px] shrink-0 text-info" aria-hidden />
      <div className="flex flex-col gap-1.5">{children}</div>
    </div>
  )
}

/** A small link to another screen, already filtered; nothing when `href` is null. */
export function ScreenLink({ href, label, className }: { href: string | null; label: string; className?: string }) {
  if (!href) return null
  return (
    <Link
      href={href}
      title={label}
      aria-label={label}
      className={cn(
        "inline-flex size-7 shrink-0 items-center justify-center rounded-md text-text-3 outline-none hover:bg-surface-2 hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/30",
        className
      )}
    >
      <ExternalLink className="size-3.5" aria-hidden />
    </Link>
  )
}

/**
 * One expandable figure row, like the P&L statement's: label, value, an
 * optional second column (desktop), and what the figure means / how db/
 * computes it, written from docs/accounting-rules.md.
 */
export function ExplainRow({
  id,
  label,
  value,
  second,
  meaning,
  how,
  bold = false,
  mobile,
}: {
  id: string
  label: string
  value: React.ReactNode
  second?: React.ReactNode
  meaning: string
  how?: string
  bold?: boolean
  mobile: boolean
}) {
  const [open, setOpen] = React.useState(false)
  const panelId = `explain-${id}`
  return (
    <div className={cn("border-b border-border last:border-b-0", bold && "bg-surface-2")}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        title={R.explainAria(label)}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "grid w-full cursor-pointer items-center gap-x-3 text-start outline-none hover:bg-surface-2/70 focus-visible:ring-3 focus-visible:ring-ring/30 focus-visible:ring-inset",
          mobile
            ? "min-h-11 grid-cols-[minmax(0,1fr)_auto] px-3.5 py-2 text-[13px]"
            : "min-h-11 grid-cols-[minmax(0,1fr)_180px_160px] px-5 py-2 text-[13.5px]",
          bold && "font-bold"
        )}
      >
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="min-w-0">{label}</span>
          <ChevronDown className={cn("size-3.5 shrink-0 text-text-3 transition-transform", open && "rotate-180")} aria-hidden />
        </span>
        <span className="text-end whitespace-nowrap">{value}</span>
        {!mobile && <span className="text-end text-[12.5px] font-normal text-text-3">{second}</span>}
      </button>
      <div
        id={panelId}
        hidden={!open}
        className={cn("flex flex-col gap-1.5 text-[12.5px] leading-[21px] text-text-2", mobile ? "px-3.5 pb-3" : "px-5 pb-3.5")}
      >
        <p className="text-heading">{meaning}</p>
        {how && (
          <p>
            <b className="font-semibold text-text-3">{R.howTitle}: </b>
            {how}
          </p>
        )}
        {mobile && second && <p className="text-text-3">{second}</p>}
      </div>
    </div>
  )
}
