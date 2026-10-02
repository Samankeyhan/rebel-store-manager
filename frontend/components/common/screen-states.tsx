"use client"

import * as React from "react"
import { CloudOff, RotateCw } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import { cn } from "@/lib/utils"

const sk = "rounded-[10px] bg-surface-2"

/** `[[STATES:]]` loading: a title bar and 8 rows (5 tall cards on mobile). */
export function LoadingBlock({ mobile, label }: { mobile: boolean; label: string }) {
  return (
    <section aria-busy="true" aria-label={label} className="flex flex-col gap-3">
      <Skeleton className={cn(sk, "h-5 w-[180px] rounded-md")} />
      {Array.from({ length: mobile ? 5 : 8 }, (_, i) => (
        <Skeleton key={i} className={cn(sk, mobile ? "h-[84px] rounded-xl" : "h-10")} />
      ))}
    </section>
  )
}

/** `.empty` card: icon disc, title, body, one action. */
export function StateShell({
  icon: Icon,
  tone = "neutral",
  title,
  body,
  action,
  mobile,
}: {
  icon: React.ComponentType<{ className?: string }>
  tone?: "neutral" | "loss"
  title: string
  body?: string
  action?: React.ReactNode
  mobile: boolean
}) {
  return (
    <section className={cardClass} role={tone === "loss" ? "alert" : undefined}>
      <div className={cn("flex flex-col items-center gap-2.5 px-6 text-center", mobile ? "py-12" : "py-24")}>
        <div
          className={cn(
            "mb-1 flex size-14 items-center justify-center rounded-2xl",
            tone === "loss" ? "bg-loss-soft text-loss" : "bg-surface-2 text-text-3"
          )}
        >
          <Icon className={mobile ? "size-[26px]" : "size-7"} />
        </div>
        <div className="text-[15px] font-bold text-heading">{title}</div>
        {body && <div className="max-w-[420px] text-[13px] text-text-3">{body}</div>}
        {action}
      </div>
    </section>
  )
}

export function ErrorBlock({
  title,
  body,
  retry,
  onRetry,
  mobile,
}: {
  title: string
  body: string
  retry: string
  onRetry: () => void
  mobile: boolean
}) {
  return (
    <StateShell
      icon={CloudOff}
      tone="loss"
      mobile={mobile}
      title={title}
      body={body}
      action={
        <Btn size={mobile ? "lg" : "md"} className="mt-1" onClick={onRetry}>
          <RotateCw className="size-4" />
          {retry}
        </Btn>
      }
    />
  )
}
