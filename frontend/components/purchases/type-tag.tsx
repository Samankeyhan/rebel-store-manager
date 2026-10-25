import { badgeBase } from "@/components/common/status"
import type { ItemType } from "@/lib/purchase-lines"
import { cn } from "@/lib/utils"
import { U } from "./copy"

const TONES: Record<ItemType, string> = {
  STOCK: "bg-info-soft text-info",
  SERVICE: "bg-warn-soft text-warn",
  PRODUCT: "bg-profit-soft text-profit",
}
const LABELS: Record<ItemType, string> = { STOCK: U.badgeMaterial, SERVICE: U.badgeService, PRODUCT: U.badgeProduct }

/** نوع badge of a purchase line: متریال (blue), خدمت (amber), محصول (green). */
export function TypeTag({ type }: { type: ItemType }) {
  return <span className={cn(badgeBase, TONES[type])}>{LABELS[type]}</span>
}
