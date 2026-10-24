import { badgeBase } from "@/components/common/status"
import type { PaymentStatus } from "@/lib/payables"
import { cn } from "@/lib/utils"
import { PAY_STATUS_LABELS } from "./copy"

const TONES: Record<PaymentStatus, string> = {
  UNPAID: "bg-loss-soft text-loss",
  PARTIAL: "bg-warn-soft text-warn",
  PAID: "bg-profit-soft text-profit",
}

/** A purchase's payment status (db/supplier_payments.py, computed on read). */
export function PayStatusTag({ status }: { status: PaymentStatus }) {
  return <span className={cn(badgeBase, TONES[status])}>{PAY_STATUS_LABELS[status]}</span>
}
