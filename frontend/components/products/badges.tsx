import { badgeBase } from "@/components/common/status"
import { cn } from "@/lib/utils"
import { P } from "./copy"

export function ActiveBadge({ active }: { active: boolean }) {
  return (
    <span
      className={cn(
        badgeBase,
        active ? "bg-profit-soft text-profit" : "border border-dashed border-border-strong bg-card text-text-2"
      )}
    >
      {active ? P.active : P.inactive}
    </span>
  )
}

export function TypeBadge({ type }: { type: string }) {
  const service = type === "SERVICE"
  return (
    <span className={cn(badgeBase, service ? "bg-violet-soft text-violet" : "bg-info-soft text-info")}>
      {service ? P.typeService : P.typeStock}
    </span>
  )
}

export function Chip({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-md bg-surface-2 px-2 text-xs whitespace-nowrap text-text-2",
        className
      )}
    >
      {children}
    </span>
  )
}

export function NoCostBadge() {
  return <span className={cn(badgeBase, "bg-loss-soft text-loss")}>{P.noCost}</span>
}
