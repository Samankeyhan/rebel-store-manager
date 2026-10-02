"use client"

import { ChevronDown } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { KitDetail } from "@/lib/api"
import { formatNumber } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { S } from "./copy"
import { NONE } from "./draft"

/** The kit a choice names, or null for «بدون بسته‌بندی» (or an id no longer listed). */
export function kitFor(choice: string, kits: KitDetail[]): KitDetail | null {
  return choice === NONE ? null : (kits.find((k) => String(k.id) === choice) ?? null)
}

/** A choice pointing at a kit that exists but is inactive: orders using the default would be refused. */
export const isInactiveChoice = (choice: string, kits: KitDetail[]) => kitFor(choice, kits)?.is_active === 0

/**
 * A channel's default kit: active kits plus «بدون بسته‌بندی», the same options
 * and NONE sentinel as Packaging's deactivate dialog. A current default that
 * has since been deactivated is shown (in warn tone) but can't be re-chosen.
 */
export function KitPicker({
  value,
  kits,
  onChange,
  label,
  mobile,
}: {
  value: string
  kits: KitDetail[]
  onChange: (choice: string) => void
  label: string
  mobile: boolean
}) {
  const kit = kitFor(value, kits)
  const inactive = kit?.is_active === 0
  const name = value === NONE ? S.noPackaging : kit ? (inactive ? S.kitInactive(kit.name) : kit.name) : "—"
  const active = kits.filter((k) => k.is_active === 1)

  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={label}
          className={cn(
            "flex cursor-pointer items-center justify-between gap-2 rounded-lg border border-border-strong bg-card px-3 text-[13px] outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
            mobile ? "h-10 w-full" : "h-9 w-[220px]",
            inactive && "border-warn text-warn"
          )}
        >
          <span className="truncate">{name}</span>
          <span className="flex shrink-0 items-center gap-2">
            <span className="text-text-3 tabular-nums">{formatNumber(kit?.kit_cost ?? 0)}</span>
            <ChevronDown className="size-3.5 text-text-3" aria-hidden />
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className={mobile ? "w-[var(--radix-dropdown-menu-trigger-width)]" : "w-[240px]"}>
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {active.map((k) => (
            <DropdownMenuRadioItem key={k.id} value={String(k.id)}>
              <span className="flex grow items-center justify-between gap-3">
                {k.name}
                <span className="text-text-3 tabular-nums">{formatNumber(k.kit_cost)}</span>
              </span>
            </DropdownMenuRadioItem>
          ))}
          <DropdownMenuRadioItem value={NONE}>
            <span className="flex grow items-center justify-between gap-3">
              {S.noPackaging}
              <span className="text-text-3 tabular-nums">{formatNumber(0)}</span>
            </span>
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
