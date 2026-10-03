"use client"

import * as React from "react"
import { CloudOff, RotateCw } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import { formatNumber } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { D } from "./copy"

export const sk = "rounded-md bg-surface-2"

/** A dashboard card: `.card-h` (title, caption, aside) + body. */
export function DashCard({
  id,
  title,
  caption,
  aside,
  children,
  className,
  headerRule = true,
}: {
  id: string
  title: string
  caption?: React.ReactNode
  aside?: React.ReactNode
  children: React.ReactNode
  className?: string
  headerRule?: boolean
}) {
  return (
    <section aria-labelledby={id} className={cn(cardClass, "flex min-w-0 flex-col", className)}>
      <div
        className={cn(
          "flex items-start justify-between gap-3 px-4 py-3.5 md:px-5 md:py-4",
          headerRule && "border-b border-border"
        )}
      >
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 id={id} className="text-base leading-[26px] font-bold text-heading">
            {title}
          </h2>
          {caption && <div className="text-xs text-text-3">{caption}</div>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  )
}

/** A card body that failed: cause, error code, retry. The rest of the page keeps working. */
export function CardError({
  title,
  code,
  onRetry,
  mobile,
}: {
  title: string
  code: string
  onRetry: () => void
  mobile: boolean
}) {
  return (
    <div role="alert" className="flex flex-col items-center gap-2 px-5 py-8 text-center">
      <div className="mb-1 flex size-12 items-center justify-center rounded-2xl bg-loss-soft text-loss">
        <CloudOff className="size-6" aria-hidden />
      </div>
      <div className="text-[14px] font-bold text-heading">{title}</div>
      <div className="max-w-[360px] text-[13px] text-text-3">{D.errorBody}</div>
      <div className="text-xs text-text-3">
        {D.errorCode("")}
        <span dir="ltr" className="font-mono">
          {code}
        </span>
      </div>
      <Btn size={mobile ? "lg" : "sm"} className="mt-1" onClick={onRetry}>
        <RotateCw className="size-3.5" aria-hidden />
        {D.retry}
      </Btn>
    </div>
  )
}

export function CardLoading({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label={D.loadingAria} className="flex flex-col gap-3 px-5 py-5">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={cn(sk, "h-9")} />
      ))}
    </div>
  )
}

/** `.empty` inside a card. */
export function CardEmpty({
  icon: Icon,
  tone = "neutral",
  title,
  body,
  action,
  className,
}: {
  icon: React.ComponentType<{ className?: string }>
  tone?: "neutral" | "profit"
  title: string
  body?: string
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-col items-center gap-2 px-6 py-10 text-center", className)}>
      <div
        className={cn(
          "mb-1 flex size-12 items-center justify-center rounded-2xl",
          tone === "profit" ? "bg-profit-soft text-profit" : "bg-surface-2 text-text-3"
        )}
      >
        <Icon className="size-6" />
      </div>
      <div className="text-[14px] font-bold text-heading">{title}</div>
      {body && <div className="max-w-[420px] text-[13px] text-text-3">{body}</div>}
      {action}
    </div>
  )
}

/**
 * An amount followed by «تومان», kept on one line. The number is
 * bidi-isolated so its minus (formatNumber's LRM + U+2212) always stays on
 * the digits' left, whatever text surrounds it.
 */
export function Amount({ n, unit = true, className }: { n: number; unit?: boolean; className?: string }) {
  return (
    <span className={cn("whitespace-nowrap", className)}>
      <span dir="ltr" className="tabular-nums">
        {formatNumber(n)}
      </span>
      {unit && ` ${D.toman}`}
    </span>
  )
}
