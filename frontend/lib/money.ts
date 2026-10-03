/**
 * Money display. Money is an integer count of TOMAN everywhere: in the
 * database, in every API request and response, in component state and in
 * every client-side preview. The owner can choose to SEE it in Rial
 * (Settings → «واحد پول»); Rial = Toman × 10, always exact. This module is
 * the frontend's ONLY place that knows that (db/currency.py is the backend's).
 *
 * - Display: formatMoney(toman) → "۱۸۰٬۰۰۰ تومان" / "۱٬۸۰۰٬۰۰۰ ریال", or the
 *   <Money> component (components/common/money.tsx).
 * - Input: MoneyInput (components/record-sale/primitives.tsx), which uses
 *   fromDisplayAmount and never rounds.
 * - A unit in copy: currencyLabel(). Never hard-code «تومان» or «ریال».
 *
 * The active currency is a module-level store, so plain functions (copy.ts
 * helpers, toasts, aria-labels) read it when called. React re-renders come
 * from useCurrency() (lib/use-currency.ts), which each page root and <Money>
 * call. Dependency-free apart from persian-numbers, for `node --test`.
 */

import { formatNumber } from "./persian-numbers.ts"

export type Currency = "TOMAN" | "RIAL"

export const RIAL_PER_TOMAN = 10

const LABELS: Record<Currency, string> = { TOMAN: "تومان", RIAL: "ریال" }
const STORAGE_KEY = "rebel.displayCurrency"
/** U+00A0: keeps a number and its unit on one line. */
const NBSP = " "

let current: Currency = "TOMAN"
const listeners = new Set<() => void>()

export const isCurrency = (v: unknown): v is Currency => v === "TOMAN" || v === "RIAL"

export function getCurrency(): Currency {
  return current
}

/** Switches the display currency for the whole app (no reload) and remembers it in this browser. */
export function setCurrency(c: Currency): void {
  if (!isCurrency(c) || c === current) return
  current = c
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, c)
  } catch {
    // Private mode / blocked storage: the setting still comes from /settings.
  }
  for (const fn of [...listeners]) fn()
}

/** The currency this browser last used, so a Rial user doesn't see Toman flash before /settings loads. */
export function readCachedCurrency(): Currency | null {
  try {
    const v = globalThis.localStorage?.getItem(STORAGE_KEY)
    return isCurrency(v) ? v : null
  } catch {
    return null
  }
}

export function subscribeCurrency(fn: () => void): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

/** «تومان» or «ریال». */
export function currencyLabel(c: Currency = current): string {
  return LABELS[c]
}

function asToman(n: number, fn: string): number {
  if (!Number.isFinite(n)) {
    console.warn(`${fn}: expected a finite number, got ${n}; showing 0`)
    return 0
  }
  if (!Number.isInteger(n)) {
    console.warn(`${fn}: expected an integer Toman amount, got ${n}; rounding`)
    return Math.round(n)
  }
  return n
}

/** A Toman amount in the display currency (exact). Never throws: an out-of-range result keeps the Toman figure and warns. */
export function toDisplayAmount(toman: number, c: Currency = current): number {
  const t = asToman(toman, "toDisplayAmount")
  if (c !== "RIAL") return t
  const rial = t * RIAL_PER_TOMAN
  if (!Number.isSafeInteger(rial)) {
    console.warn(`toDisplayAmount: ${t} Toman is too large to show in Rial`)
    return t
  }
  return rial
}

/**
 * An amount typed in the display currency, as Toman. null when it can't be
 * exact: in Rial, anything that isn't a multiple of 10. Never rounds.
 */
export function fromDisplayAmount(n: number, c: Currency = current): number | null {
  if (!Number.isSafeInteger(n)) return null
  if (c !== "RIAL") return n
  if (n % RIAL_PER_TOMAN !== 0) return null
  return n / RIAL_PER_TOMAN
}

/** The converted number without its unit, for operands inside a formula whose result carries the unit. */
export function formatMoneyNumber(toman: number, c: Currency = current): string {
  return formatNumber(toDisplayAmount(toman, c))
}

/** Integer Toman → "<number> <unit>" in the display currency: 180000 → "۱۸۰٬۰۰۰ تومان" (or "۱٬۸۰۰٬۰۰۰ ریال"). */
export function formatMoney(toman: number, c: Currency = current): string {
  return `${formatMoneyNumber(toman, c)}${NBSP}${currencyLabel(c)}`
}
