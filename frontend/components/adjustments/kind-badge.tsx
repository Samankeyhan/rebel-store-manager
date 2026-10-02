import { badgeBase } from "@/components/common/status"
import { cn } from "@/lib/utils"
import { A } from "./copy"
import type { RowKind } from "./figures"

/** Design §2: ضایعات = st-loss, اصلاح + = st-paid, اصلاح − = st-pending. */
const META: Record<RowKind, { text: string; cls: string }> = {
  waste: { text: A.badgeWaste, cls: "bg-loss-soft text-loss" },
  plus: { text: A.badgePlus, cls: "bg-info-soft text-info" },
  minus: { text: A.badgeMinus, cls: "bg-warn-soft text-warn" },
}

export function KindBadge({ kind, className }: { kind: RowKind; className?: string }) {
  const m = META[kind]
  return <span className={cn(badgeBase, m.cls, className)}>{m.text}</span>
}
