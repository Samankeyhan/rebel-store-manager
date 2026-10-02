"use client"

/**
 * Design-system primitives used by the record-sale screen (design/tokens.css
 * .btn / .input / .stepper / .opt / .alert / .badge / .ch), as Tailwind on
 * the theme tokens. Kept local: the shell's shadcn Button/Input are 32px
 * tall, while this form's controls are 40/48 (44+ on mobile).
 */

import * as React from "react"
import { CircleAlert, Info, Lock, Minus, Plus, TriangleAlert } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatNumber, parseInteger } from "@/lib/persian-numbers"
import { T } from "./copy"

const focusRing = "outline-none focus-visible:ring-3 focus-visible:ring-ring/30"

const btnVariants = {
  primary: "bg-primary text-white hover:bg-red-hover",
  outline: "border-border-strong bg-card text-foreground hover:bg-surface-2",
  ghost: "text-text-2 hover:bg-surface-2",
  link: "h-auto! border-0 px-0! text-heading font-semibold hover:text-primary",
} as const
const btnSizes = {
  sm: "h-8 rounded-[7px] px-3 text-[13px]",
  md: "h-10 rounded-lg px-4 text-sm",
  lg: "h-12 rounded-[10px] px-5 text-[15px]",
} as const

export function btnClass(
  variant: keyof typeof btnVariants = "outline",
  size: keyof typeof btnSizes = "md",
  className?: string
) {
  return cn(
    "inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 border border-transparent font-semibold whitespace-nowrap select-none disabled:cursor-not-allowed disabled:opacity-45 [&_svg]:shrink-0",
    focusRing,
    btnSizes[size],
    btnVariants[variant],
    className
  )
}

export function Btn({
  variant = "outline",
  size = "md",
  className,
  type = "button",
  ...props
}: React.ComponentProps<"button"> & {
  variant?: keyof typeof btnVariants
  size?: keyof typeof btnSizes
}) {
  return <button type={type} className={btnClass(variant, size, className)} {...props} />
}

export const cardClass =
  "rounded-xl border border-border bg-card text-card-foreground shadow-[0_1px_2px_rgba(18,22,38,.06)]"

export function SectionCard({
  title,
  caption,
  icon,
  id,
  children,
  className,
  bodyClassName,
  ...rest
}: {
  title: string
  caption?: string
  icon?: React.ReactNode
  id: string
  children: React.ReactNode
  className?: string
  bodyClassName?: string
} & Omit<React.ComponentProps<"section">, "title" | "children">) {
  return (
    <section className={cn(cardClass, className)} aria-labelledby={id} {...rest}>
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
        <h2 id={id} className="flex items-center gap-2 text-base leading-[26px] font-bold text-heading">
          {icon}
          {title}
        </h2>
        {caption && <span className="text-xs leading-[19px] text-text-3">{caption}</span>}
      </div>
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </section>
  )
}

export const inputClass = (tone?: "error" | "warn" | null, className?: string) =>
  cn(
    "h-10 w-full min-w-0 rounded-lg border border-border-strong bg-card px-3 text-sm text-foreground outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
    tone === "error" && "border-loss ring-3 ring-loss-soft focus:border-loss",
    tone === "warn" && "border-warn focus:border-warn",
    className
  )

/** Integer input (money or product quantity): shows Persian digits, accepts any. */
export function IntInput({
  value,
  onValue,
  tone,
  suffix,
  className,
  ...props
}: Omit<React.ComponentProps<"input">, "value" | "onChange"> & {
  value: number
  onValue: (n: number) => void
  tone?: "error" | "warn" | null
  suffix?: string
}) {
  const input = (
    <input
      inputMode="numeric"
      autoComplete="off"
      value={formatNumber(value)}
      onChange={(e) => onValue(parseInteger(e.target.value))}
      onFocus={(e) => e.currentTarget.select()}
      className={inputClass(tone, cn("tabular-nums", suffix && "pe-14", className))}
      {...props}
    />
  )
  if (!suffix) return input
  return (
    <div className="relative flex w-full items-center">
      {input}
      <span className="pointer-events-none absolute end-3 text-xs text-text-3">{suffix}</span>
    </div>
  )
}

export function Stepper({
  value,
  onValue,
  tone,
  size = "md",
}: {
  value: number
  onValue: (n: number) => void
  tone?: "error" | "warn" | null
  size?: "md" | "mobile"
}) {
  const btn = cn(
    "flex h-full cursor-pointer items-center justify-center bg-surface-2 text-text-2 hover:text-foreground",
    focusRing,
    size === "mobile" ? "w-10" : "w-8"
  )
  return (
    <div
      className={cn(
        "flex items-center overflow-hidden rounded-lg border border-border-strong bg-card",
        size === "mobile" ? "h-11" : "h-10",
        tone === "error" && "border-loss ring-3 ring-loss-soft",
        tone === "warn" && "border-warn"
      )}
    >
      <button type="button" className={btn} aria-label={T.increase} onClick={() => onValue(value + 1)}>
        <Plus className="size-3.5" />
      </button>
      <input
        inputMode="numeric"
        aria-label={T.colQty}
        value={formatNumber(value)}
        // Typing clamps at 0 (V6 then flags it); the − button clamps at 1.
        onChange={(e) => onValue(Math.max(0, parseInteger(e.target.value)))}
        onFocus={(e) => e.currentTarget.select()}
        className="h-full w-full min-w-0 bg-transparent text-center tabular-nums outline-none"
      />
      <button
        type="button"
        className={btn}
        aria-label={T.decrease}
        onClick={() => onValue(Math.max(1, value - 1))}
      >
        <Minus className="size-3.5" />
      </button>
    </div>
  )
}

export function Label({
  htmlFor,
  children,
  optional,
  className,
}: {
  htmlFor?: string
  children: React.ReactNode
  optional?: boolean
  className?: string
}) {
  const content = (
    <>
      {children}
      {optional && <span className="font-normal text-text-3"> {T.optional}</span>}
    </>
  )
  const cls = cn("text-[13px] font-semibold text-foreground", className)
  return htmlFor ? (
    <label htmlFor={htmlFor} className={cls}>
      {content}
    </label>
  ) : (
    <span className={cls}>{content}</span>
  )
}

export function Help({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("text-xs leading-[19px] text-text-3", className)}>{children}</span>
}

const messageIcons = {
  alert: CircleAlert,
  info: Info,
  lock: Lock,
}

/** `.err` (blocking, role=alert) / `.warn-t` (soft, role=status). */
export function InlineMessage({
  severity,
  icon = severity === "error" ? "alert" : "info",
  children,
}: {
  severity: "error" | "warn"
  icon?: keyof typeof messageIcons
  children: React.ReactNode
}) {
  const Icon = messageIcons[icon]
  return (
    <div
      role={severity === "error" ? "alert" : "status"}
      className={cn(
        "flex flex-wrap items-start gap-x-1.5 gap-y-1 text-xs leading-[19px] font-medium",
        severity === "error" ? "text-loss" : "text-warn"
      )}
    >
      <Icon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      {children}
    </div>
  )
}

export function Alert({
  tone,
  title,
  icon,
  children,
  action,
  className,
}: {
  tone: "err" | "warn" | "ok"
  title?: React.ReactNode
  icon?: "alert" | "lock" | "triangle" | React.ReactNode
  children?: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  const iconNode =
    icon === "lock" ? (
      <Lock className="size-5" />
    ) : icon === "triangle" ? (
      <TriangleAlert className="size-5" />
    ) : icon === "alert" || icon === undefined ? (
      <CircleAlert className="size-5" />
    ) : (
      icon
    )
  return (
    <div
      role={tone === "err" ? "alert" : "status"}
      className={cn(
        "flex items-start gap-3 rounded-[10px] border px-4 py-3 text-[13px] leading-[21px] text-foreground",
        tone === "err" && "border-loss-border bg-loss-soft",
        tone === "warn" && "border-transparent bg-warn-soft",
        tone === "ok" && "border-transparent bg-profit-soft",
        className
      )}
    >
      <span
        className={cn(
          "mt-px flex shrink-0",
          tone === "err" && "text-loss",
          tone === "warn" && "text-warn",
          tone === "ok" && "text-profit"
        )}
        aria-hidden
      >
        {iconNode}
      </span>
      <div className="min-w-0 grow">
        {title && <div className="mb-0.5 text-[13.5px] font-bold">{title}</div>}
        {children}
      </div>
      {action}
    </div>
  )
}

/** `.opt` option card (radio). */
export function OptionTile({
  selected,
  onSelect,
  children,
  tag,
  className,
  ...props
}: Omit<React.ComponentProps<"button">, "onSelect"> & {
  selected: boolean
  onSelect: () => void
  tag?: string
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        "relative flex min-w-0 cursor-pointer flex-col items-start gap-0.5 rounded-[10px] border border-border-strong bg-card px-3 py-2.5 text-start hover:border-heading",
        focusRing,
        selected && "border-primary bg-red-soft shadow-[0_0_0_1px_var(--primary)] hover:border-primary",
        className
      )}
      {...props}
    >
      {children}
      {tag && (
        <span className="absolute end-2 top-2 rounded-[4px] bg-surface-2 px-1.5 text-[10.5px] font-bold text-text-3">
          {tag}
        </span>
      )}
    </button>
  )
}

export function PostageBadge({ on }: { on: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-xs font-semibold whitespace-nowrap before:size-1.5 before:rounded-full before:bg-current",
        on ? "bg-info-soft text-info" : "border border-dashed border-border-strong bg-card text-text-2"
      )}
    >
      {on ? T.postageOn : T.postageOff}
    </span>
  )
}

export { ChannelBadge, StatusBadge } from "@/components/common/status"

export function StockPill({ text, tone }: { text: string; tone: "neutral" | "out" }) {
  return (
    <span
      className={cn(
        "inline-flex h-[22px] items-center rounded-md px-2 text-[11.5px] font-semibold whitespace-nowrap",
        tone === "out" ? "bg-loss-soft text-loss" : "bg-surface-2 text-text-2"
      )}
    >
      {text}
    </span>
  )
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <span
      dir="ltr"
      className="inline-flex h-5 items-center rounded-[5px] border border-border bg-surface-2 px-1.5 font-mono text-[11px] text-text-3"
    >
      {children}
    </span>
  )
}

/** Signed amount for the internal summary: «−۱۹۹٬۲۷۳», or «۰». */
export function negAmount(n: number): string {
  return n ? formatNumber(-n) : formatNumber(0)
}
