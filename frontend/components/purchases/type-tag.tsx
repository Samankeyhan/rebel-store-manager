import { badgeBase } from "@/components/common/status"
import { cn } from "@/lib/utils"
import { U } from "./copy"
import type { PurchaseKind } from "./use-purchases-data"

/** نوع badge: متریال = st-paid (blue), محصول = st-done (green). */
export function TypeTag({ kind }: { kind: PurchaseKind }) {
  return (
    <span className={cn(badgeBase, kind === "material" ? "bg-info-soft text-info" : "bg-profit-soft text-profit")}>
      {kind === "material" ? U.badgeMaterial : U.badgeProduct}
    </span>
  )
}
