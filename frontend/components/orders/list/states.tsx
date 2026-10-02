import Link from "next/link"
import { CloudOff, Plus, ReceiptText, RotateCw } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Btn, btnClass, cardClass } from "@/components/record-sale/primitives"
import { cn } from "@/lib/utils"
import { L } from "../copy"

const sk = "rounded-md bg-surface-2"

export function LoadingState({ mobile }: { mobile: boolean }) {
  if (mobile) {
    return (
      <div aria-busy="true" className="flex flex-col gap-3">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className={cn(sk, "h-[92px] rounded-xl")} />
        ))}
      </div>
    )
  }
  return (
    <div aria-busy="true" className="flex flex-col gap-4">
      <Skeleton className={cn(sk, "h-10 w-[640px] max-w-full")} />
      <div className={cn(cardClass, "px-4")}>
        {Array.from({ length: 10 }, (_, i) => (
          <div
            key={i}
            className="grid h-[52px] grid-cols-[110px_130px_90px_minmax(0,1fr)_100px_130px_120px] items-center gap-6 border-b border-border last:border-b-0"
          >
            <Skeleton className={cn(sk, "h-3.5")} />
            <Skeleton className={cn(sk, "h-3.5")} />
            <Skeleton className={cn(sk, "h-[22px]")} />
            <Skeleton className={cn(sk, "h-3.5 w-3/5")} />
            <Skeleton className={cn(sk, "h-[22px] rounded-full")} />
            <Skeleton className={cn(sk, "h-3.5")} />
            <Skeleton className={cn(sk, "h-3.5")} />
          </div>
        ))}
      </div>
    </div>
  )
}

export function ErrorState({ code, onRetry, mobile }: { code: string; onRetry: () => void; mobile: boolean }) {
  return (
    <section role="alert" className={cardClass}>
      <div className={cn("flex flex-col items-center gap-2.5 px-6 text-center", mobile ? "py-12" : "py-24")}>
        <div className="mb-1 flex size-14 items-center justify-center rounded-2xl bg-loss-soft text-loss">
          <CloudOff className={mobile ? "size-[26px]" : "size-7"} aria-hidden />
        </div>
        <div className="text-[15px] font-bold text-heading">{mobile ? L.errorTitleMobile : L.errorTitle}</div>
        <div className="max-w-[380px] text-[13px] text-text-3">{mobile ? L.errorBodyMobile : L.errorBody}</div>
        <Btn size={mobile ? "lg" : "md"} className="mt-1" onClick={onRetry}>
          <RotateCw className="size-4" />
          {L.retry}
        </Btn>
        {!mobile && (
          <div className="text-xs text-text-3">
            {L.errorCode}{" "}
            <span dir="ltr" className="inline-block font-mono">
              {code}
            </span>
          </div>
        )}
      </div>
    </section>
  )
}

export function EmptyState({ mobile }: { mobile: boolean }) {
  return (
    <section className={cardClass}>
      <div className={cn("flex flex-col items-center gap-2.5 px-6 text-center", mobile ? "py-12" : "py-24")}>
        <div className="mb-1 flex size-14 items-center justify-center rounded-2xl bg-surface-2 text-text-3">
          <ReceiptText className={mobile ? "size-[26px]" : "size-7"} aria-hidden />
        </div>
        <div className="text-[15px] font-bold text-heading">{L.emptyTitle}</div>
        <div className="max-w-[380px] text-[13px] text-text-3">{mobile ? L.emptyBodyMobile : L.emptyBody}</div>
        <Link href="/sales/new" className={btnClass("primary", mobile ? "lg" : "md", "mt-1.5")}>
          <Plus className="size-4" />
          {L.emptyCta}
        </Link>
      </div>
    </section>
  )
}
