/**
 * Money display and input. Money is an integer count of RIAL everywhere: in
 * the database, in every API request and response, in component state and in
 * every client-side preview. The owner chooses whether to SEE it in Rial (the
 * stored integer) or in Toman (Settings → «واحد پول»): Toman = Rial ÷ 10, with
 * one decimal digit only when the Rial amount isn't a multiple of 10. This
 * module is the frontend's ONLY place that knows that (db/currency.py is the
 * backend's twin); `npm run check:money` fails on ×10 / ÷10 anywhere else.
 *
 * - Display: formatMoney(rial) → "۱۸۰٬۰۰۰٫۵ تومان" / "۱٬۸۰۰٬۰۰۵ ریال", or the
 *   <Money> component (components/common/money.tsx).
 * - Input: MoneyInput (components/record-sale/primitives.tsx), which uses
 *   parseMoneyInput and never rounds.
 * - A unit in copy: currencyLabel(). Never hard-code «تومان» or «ریال».
 *
 * Every conversion is integer arithmetic on safe integers (or on the typed
 * digit string itself); a float never touches money here.
 *
 * The active currency is a module-level store, so plain functions (copy.ts
 * helpers, toasts, aria-labels) read it when called. React re-renders come
 * from useCurrency() (lib/use-currency.ts), which each page root and <Money>
 * call. Dependency-free apart from persian-numbers, for `node --test`.
 */

import { MINUS, formatDigitString, toLatinDigits, toPersianDigits } from "./persian-numbers.ts"

export type Currency = "TOMAN" | "RIAL"

/** Only for this module and its tests; check:money refuses it in app/ and components/. */
export const RIAL_PER_TOMAN = 10

/** 9,007,199,254,740,991 Rial: the largest amount a JS number holds exactly. */
export const MAX_RIAL = Number.MAX_SAFE_INTEGER

const LABELS: Record<Currency, string> = { TOMAN: "تومان", RIAL: "ریال" }
const STORAGE_KEY = "rebel.displayCurrency"
/** U+00A0: keeps a number and its unit on one line. */
const NBSP = " "
/** U+066B ARABIC DECIMAL SEPARATOR, the Persian decimal mark. */
const DECIMAL_MARK = "٫"

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

// ---------------------------------------------------------------- display

export type DisplayParts = {
  negative: boolean
  /** The whole display units: |rial| in Rial, |rial| ÷ 10 (integer) in Toman. */
  whole: number
  /** Toman only: the last Rial digit, 1–9; null when it is 0 (a whole Toman) and always in Rial. */
  tenth: number | null
}

/** Never throws: a slip upstream must not crash a screen. It is warned about and shown as 0 or rounded. */
function asRial(n: number, fn: string): number {
  if (!Number.isFinite(n)) {
    console.warn(`${fn}: expected a finite number, got ${n}; showing 0`)
    return 0
  }
  if (!Number.isInteger(n)) {
    console.warn(`${fn}: expected an integer Rial amount, got ${n}; rounding`)
    return asRial(Math.round(n), fn)
  }
  if (!Number.isSafeInteger(n)) {
    console.warn(`${fn}: ${n} is beyond the exact range (±${MAX_RIAL} Rial); showing 0`)
    return 0
  }
  return n
}

/**
 * An integer Rial amount in the display currency, as db/currency.py's
 * to_display_parts: Rial → (|rial|, no tenth); Toman → (|rial| ÷ 10, the last
 * Rial digit or null). Integer arithmetic only: `% 10` is exact on a safe
 * integer, and (m − digit) ÷ 10 divides an exact multiple of 10.
 */
export function toDisplayParts(rial: number, c: Currency = current): DisplayParts {
  const r = asRial(rial, "toDisplayParts")
  const negative = r < 0
  const magnitude = negative ? -r : r
  if (c === "RIAL") return { negative, whole: magnitude, tenth: null }
  const digit = magnitude % RIAL_PER_TOMAN
  return { negative, whole: (magnitude - digit) / RIAL_PER_TOMAN, tenth: digit === 0 ? null : digit }
}

/**
 * The number without its unit, for operands inside a formula whose result
 * carries the unit: Persian digits, «٬» grouping, «٫» + one digit only when
 * needed, the shared minus (LRM + U+2212). (1800005, Toman) → "۱۸۰٬۰۰۰٫۵".
 */
export function formatMoneyNumber(rial: number, c: Currency = current): string {
  const { negative, whole, tenth } = toDisplayParts(rial, c)
  const sign = negative ? MINUS : ""
  return sign + formatDigitString(String(whole)) + (tenth == null ? "" : DECIMAL_MARK + toPersianDigits(tenth))
}

/** Integer Rial → "<number> <unit>" in the display currency: 1800000 → "۱۸۰٬۰۰۰ تومان" (or "۱٬۸۰۰٬۰۰۰ ریال"). */
export function formatMoney(rial: number, c: Currency = current): string {
  return `${formatMoneyNumber(rial, c)}${NBSP}${currencyLabel(c)}`
}

// ---------------------------------------------------------------- input

/** Why a typed amount gives no Rial value; the Persian text is in components/common/copy.ts. */
export type MoneyInputError = "negative" | "tomanDecimals" | "rialDecimal" | "tooLarge"

export type ParsedMoney = {
  /**
   * What the field keeps: Latin digits with at most one "." (and a leading
   * "-" if one was typed, so the user sees what the error is about).
   * moneyInputText() turns it into Persian for display.
   */
  text: string
  /** Integer Rial; null when the text can't be an exact amount (see error); undefined when empty and allowEmpty. */
  rial: number | null | undefined
  error: MoneyInputError | null
}

const MINUS_SIGNS = /[-−‒–—﹣－]/
/** «٫» (U+066B), "." and "/" all mean the decimal point (design-system §5). */
const DECIMAL_MARKS = /[٫./]/
const MAX_RIAL_DIGITS = String(MAX_RIAL)

/** A digit string (no leading zeros) as a number, or null beyond MAX_RIAL. Compared as text, so nothing is rounded first. */
function safeFromDigits(digits: string): number | null {
  const d = digits.replace(/^0+(?=\d)/, "")
  if (d.length > MAX_RIAL_DIGITS.length) return null
  if (d.length === MAX_RIAL_DIGITS.length && d > MAX_RIAL_DIGITS) return null
  return Number(d)
}

/**
 * What MoneyInput reports for the text in the field. Digits in Persian,
 * Arabic-Indic or Latin script; «٬», "," and spaces (anything that isn't a
 * digit, minus or decimal mark) are ignored; «٫», "." or "/" is the decimal
 * mark (only the first one counts).
 *
 * - Toman: at most ONE decimal digit; the Rial value is the whole digits
 *   followed by that digit (or 0), built from the digit string: "180000.5" →
 *   1800005. Two or more decimal digits → null ("tomanDecimals").
 * - Rial: an integer; any decimal mark → null ("rialDecimal").
 * - Both: a minus sign → null ("negative"); beyond MAX_RIAL → null ("tooLarge").
 * - Empty (no digits): undefined when `allowEmpty`, else 0.
 * Never rounds.
 */
export function parseMoneyInput(raw: string, c: Currency = current, allowEmpty = false): ParsedMoney {
  const latin = toLatinDigits(raw)
  const negative = MINUS_SIGNS.test(latin)
  const markAt = latin.search(DECIMAL_MARKS)
  const hasMark = markAt !== -1
  const onlyDigits = (s: string) => s.replace(/[^0-9]/g, "")
  const whole = onlyDigits(hasMark ? latin.slice(0, markAt) : latin).replace(/^0+(?=\d)/, "")
  const fraction = hasMark ? onlyDigits(latin.slice(markAt + 1)) : ""
  const text = (negative ? "-" : "") + whole + (hasMark ? "." + fraction : "")
  const result = (rial: number | null | undefined, error: MoneyInputError | null = null): ParsedMoney => ({ text, rial, error })

  if (negative) return result(null, "negative")
  if (hasMark && c === "RIAL") return result(null, "rialDecimal")
  if (fraction.length > 1) return result(null, "tomanDecimals")
  if (whole === "" && fraction === "") return result(allowEmpty ? undefined : 0)

  const digits = c === "RIAL" ? whole : (whole || "0") + (fraction || "0")
  const rial = safeFromDigits(digits)
  return rial === null ? result(null, "tooLarge") : result(rial)
}

/** The field text for an amount set from outside (load, reset, revert): Latin digits, "." before a Toman tenth. */
export function moneyInputTextOf(rial: number | null | undefined, c: Currency = current): string {
  if (rial == null) return ""
  const { negative, whole, tenth } = toDisplayParts(rial, c)
  return (negative ? "-" : "") + String(whole) + (tenth == null ? "" : "." + String(tenth))
}

/** The field text as shown: Persian digits, «٬» grouping on the whole part, «٫» for the mark. */
export function moneyInputDisplay(text: string): string {
  const negative = text.startsWith("-")
  const body = negative ? text.slice(1) : text
  const markAt = body.indexOf(".")
  const whole = markAt === -1 ? body : body.slice(0, markAt)
  const fraction = markAt === -1 ? null : body.slice(markAt + 1)
  return (
    (negative ? MINUS : "") +
    formatDigitString(whole) +
    (fraction === null ? "" : DECIMAL_MARK + toPersianDigits(fraction))
  )
}
