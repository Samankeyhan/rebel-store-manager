/**
 * Order status and sales channel badges, shared by every screen that shows
 * an order (design-system §5 Badge: `.badge.st-*` and `.ch.ch-*`).
 */

import { cn } from "@/lib/utils"
import { CHANNELS, type Channel } from "@/components/record-sale/copy"

export const ORDER_STATUS_IDS = [
  "DRAFT",
  "PENDING",
  "PAID",
  "COMPLETED",
  "CANCELLED",
  "REFUNDED",
] as const
export type OrderStatus = (typeof ORDER_STATUS_IDS)[number]

export const ORDER_STATUSES: Record<OrderStatus, { name: string; badge: string }> = {
  DRAFT: {
    name: "پیش‌نویس",
    badge: "border border-dashed border-border-strong bg-card text-text-2",
  },
  PENDING: { name: "در انتظار", badge: "bg-warn-soft text-warn" },
  PAID: { name: "پرداخت‌شده", badge: "bg-info-soft text-info" },
  COMPLETED: { name: "تکمیل‌شده", badge: "bg-profit-soft text-profit" },
  CANCELLED: { name: "لغوشده", badge: "bg-cancel-bg text-cancel-fg" },
  REFUNDED: { name: "مرجوعی", badge: "bg-violet-soft text-violet" },
}

export function statusName(status: string): string {
  return ORDER_STATUSES[status as OrderStatus]?.name ?? status
}

export const badgeBase =
  "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-xs font-semibold whitespace-nowrap before:size-1.5 before:shrink-0 before:rounded-full before:bg-current"

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const meta = ORDER_STATUSES[status as OrderStatus]
  if (!meta) return null
  return <span className={cn(badgeBase, meta.badge, className)}>{meta.name}</span>
}

export function ChannelBadge({ channel, className }: { channel: string; className?: string }) {
  const meta = CHANNELS[channel as Channel]
  if (!meta) return null
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-md border border-border bg-card px-2 text-xs font-medium whitespace-nowrap text-text-2",
        className
      )}
    >
      <span className={cn("size-2 shrink-0 rounded-[2px]", meta.square)} aria-hidden />
      {meta.name}
    </span>
  )
}
