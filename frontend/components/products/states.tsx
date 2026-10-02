import { CloudOff, Layers, Package, Plus, RotateCw, SearchX } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import { cn } from "@/lib/utils"
import { P } from "./copy"

const sk = "rounded-[10px] bg-surface-2"

export function LoadingState({ mobile }: { mobile: boolean }) {
  return (
    <section aria-busy="true" aria-label={P.loadingAria} className="flex flex-col gap-3">
      <Skeleton className={cn(sk, "h-5 w-[180px] rounded-md")} />
      {Array.from({ length: mobile ? 5 : 8 }, (_, i) => (
        <Skeleton key={i} className={cn(sk, mobile ? "h-[84px] rounded-xl" : "h-10")} />
      ))}
    </section>
  )
}

function Shell({
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
        {body && <div className="max-w-[380px] text-[13px] text-text-3">{body}</div>}
        {action}
      </div>
    </section>
  )
}

export function ErrorState({ onRetry, mobile }: { onRetry: () => void; mobile: boolean }) {
  return (
    <Shell
      icon={CloudOff}
      tone="loss"
      mobile={mobile}
      title={mobile ? P.errorTitleMobile : P.errorTitle}
      body={P.errorBody}
      action={
        <Btn size={mobile ? "lg" : "md"} className="mt-1" onClick={onRetry}>
          <RotateCw className="size-4" />
          {P.retry}
        </Btn>
      }
    />
  )
}

export function EmptyState({ kind, onAdd, mobile }: { kind: "products" | "materials"; onAdd: () => void; mobile: boolean }) {
  const products = kind === "products"
  return (
    <Shell
      icon={products ? Package : Layers}
      mobile={mobile}
      title={products ? P.emptyTitle : P.emptyMatTitle}
      body={products ? (mobile ? P.emptyBodyMobile : P.emptyBody) : P.emptyMatBody}
      action={
        <Btn variant="primary" size={mobile ? "lg" : "md"} className="mt-1.5" onClick={onAdd}>
          <Plus className="size-4" />
          {products ? (mobile ? P.emptyCtaMobile : P.emptyCta) : P.emptyMatCta}
        </Btn>
      }
    />
  )
}

export function NoMatch({ text, onClear, mobile }: { text: string; onClear: () => void; mobile: boolean }) {
  return (
    <Shell
      icon={SearchX}
      mobile={mobile}
      title={text}
      action={
        <Btn size="sm" className="mt-1" onClick={onClear}>
          {P.clearFilters}
        </Btn>
      }
    />
  )
}
