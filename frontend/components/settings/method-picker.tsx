"use client"

import { ChevronDown } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { PM, feeText } from "@/components/payment-methods/copy"
import type { PaymentMethod } from "@/lib/api"
import { cn } from "@/lib/utils"
import { NONE } from "./draft"

/** The method a choice names, or null for «بدون روش» (or an id no longer listed). */
export function methodFor(choice: string, methods: PaymentMethod[]): PaymentMethod | null {
  return choice === NONE ? null : (methods.find((m) => String(m.id) === choice) ?? null)
}

/** A choice pointing at a method that exists but is inactive: orders using the default would be refused. */
export const isInactiveMethodChoice = (choice: string, methods: PaymentMethod[]) => methodFor(choice, methods)?.is_active === 0

/**
 * A channel's default payment method: active methods plus «بدون روش». A
 * current default that has since been deactivated is shown (in warn tone)
 * but can't be re-chosen — the same rules as KitPicker.
 */
export function MethodPicker({
  value,
  methods,
  onChange,
  label,
  mobile,
}: {
  value: string
  methods: PaymentMethod[]
  onChange: (choice: string) => void
  label: string
  mobile: boolean
}) {
  const method = methodFor(value, methods)
  const inactive = method?.is_active === 0
  const name = value === NONE ? PM.noMethod : method ? (inactive ? PM.inactive(method.name) : method.name) : "—"
  const active = methods.filter((m) => m.is_active === 1)

  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={label}
          className={cn(
            "flex cursor-pointer items-center justify-between gap-2 rounded-lg border border-border-strong bg-card px-3 text-[13px] outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
            mobile ? "h-10 w-full" : "h-9 w-[200px]",
            inactive && "border-warn text-warn"
          )}
        >
          <span className="truncate">{name}</span>
          <ChevronDown className="size-3.5 shrink-0 text-text-3" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className={mobile ? "w-[var(--radix-dropdown-menu-trigger-width)]" : "w-[260px]"}>
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {active.map((m) => (
            <DropdownMenuRadioItem key={m.id} value={String(m.id)}>
              <span className="flex min-w-0 grow items-center justify-between gap-3">
                <span className="truncate">{m.name}</span>
                <span className="shrink-0 text-xs text-text-3">{feeText(m.fee_bps, m.fee_fixed)}</span>
              </span>
            </DropdownMenuRadioItem>
          ))}
          <DropdownMenuRadioItem value={NONE}>{PM.noMethod}</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
