"use client"

import { cn } from "@/lib/utils"

/** `.seg`: a radiogroup of equal-width options. */
export function Segment<T extends string>({
  value,
  options,
  onChange,
  label,
  mobile,
  className,
}: {
  value: T
  options: readonly (readonly [T, string])[]
  onChange: (v: T) => void
  label: string
  mobile?: boolean
  className?: string
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn("flex gap-0.5 rounded-[10px] border border-border bg-surface-2 p-[3px]", className)}
    >
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={value === v}
          onClick={() => onChange(v)}
          className={cn(
            "grow cursor-pointer rounded-[7px] px-3 text-[13px] font-semibold whitespace-nowrap text-text-2 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
            mobile ? "h-10" : "h-[32px]",
            value === v && "bg-card text-heading shadow-[0_4px_14px_rgba(18,22,38,.08)]"
          )}
        >
          {text}
        </button>
      ))}
    </div>
  )
}
