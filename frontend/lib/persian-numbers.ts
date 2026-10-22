/**
 * Persian number formatting. EVERY number shown in the UI goes through this
 * module (toPersianDigits / formatNumber / formatQuantity) — never render a
 * raw number or call toLocaleString directly, so digits and separators stay
 * consistent across screens.
 *
 * MONEY does not use formatNumber directly: it goes through lib/money.ts
 * (formatMoney / <Money> / MoneyInput), which adds the unit and applies the
 * display currency. These functions never throw: a non-integer means a
 * rounding slip upstream, which must not crash a screen — it is rounded and
 * warned about.
 */

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
/** U+066C ARABIC THOUSANDS SEPARATOR */
const THOUSANDS_SEPARATOR = "٬"
/** U+2212 MINUS SIGN; U+200E LRM keeps it on the visual left in RTL text. */
export const MINUS = "‎−"

/** Replaces ASCII digits 0-9 in the input with Persian digits ۰-۹. */
export function toPersianDigits(value: number | string): string {
  return String(value).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[Number(d)])
}

/** Converts Persian (۰-۹) and Arabic-Indic (٠-٩) digits back to ASCII. */
export function toLatinDigits(value: string): string {
  return value
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660))
}

function toInteger(n: number, fn: string): number {
  if (!Number.isFinite(n)) {
    console.warn(`${fn}: expected a finite number, got ${n}; showing 0`)
    return 0
  }
  if (!Number.isInteger(n)) {
    console.warn(`${fn}: expected an integer, got ${n}; rounding`)
    return Math.round(n)
  }
  return n
}

/**
 * A string of Latin digits (no sign) grouped with ٬ in Persian digits:
 * "180000" → "۱۸۰٬۰۰۰". Works on the text itself, so it never loses a digit
 * however long the string is.
 */
export function formatDigitString(digits: string): string {
  return toPersianDigits(digits.replace(/\B(?=(\d{3})+(?!\d))/g, THOUSANDS_SEPARATOR))
}

/** Integer with Persian digits and ٬ thousands separators: 180000 → "۱۸۰٬۰۰۰". */
export function formatNumber(n: number): string {
  const int = toInteger(n, "formatNumber")
  return (int < 0 ? MINUS : "") + formatDigitString(String(Math.abs(int)))
}

/** U+066B ARABIC DECIMAL SEPARATOR */
const DECIMAL_SEPARATOR = "٫"

/**
 * A quantity that may be fractional (materials): 1.5 → "۱٫۵", 0.06 → "۰٫۰۶",
 * 14 → "۱۴". Up to six decimals (a recipe may need 0.005 L of ink, and
 * millilitres come next); trailing zeros dropped. Not for money. For text
 * that goes back into an input use `quantityText`.
 */
export function formatQuantity(n: number): string {
  if (!Number.isFinite(n)) {
    console.warn(`formatQuantity: expected a finite number, got ${n}; showing 0`)
    return "۰"
  }
  const millionths = Math.round(Math.abs(n) * 1_000_000)
  const intPart = Math.floor(millionths / 1_000_000)
  const frac = String(millionths % 1_000_000).padStart(6, "0").replace(/0+$/, "")
  const sign = n < 0 && millionths > 0 ? MINUS : ""
  return (
    sign +
    formatNumber(intPart) +
    (frac ? DECIMAL_SEPARATOR + toPersianDigits(frac) : "")
  )
}

/** A finite number as plain decimal digits, never in exponent form (1e-7 → "0.0000001"). */
function plainDecimal(n: number): string {
  const s = String(Math.abs(n))
  const m = /^(\d+)(?:\.(\d+))?e([+-]\d+)$/.exec(s)
  if (!m) return s
  const digits = m[1] + (m[2] ?? "")
  const point = m[1].length + Number(m[3])
  if (point <= 0) return "0." + "0".repeat(-point) + digits
  if (point >= digits.length) return digits + "0".repeat(point - digits.length)
  return digits.slice(0, point) + "." + digits.slice(point)
}

/**
 * The text a quantity input shows for `n` — and what it is rewritten to on
 * blur. Like `formatQuantity`, but only when that reads back (`parseDecimal`)
 * as exactly `n`; otherwise the full decimal, so a rewrite never changes the
 * value that was typed or saved (0.0000004 must not become «۰»).
 */
export function quantityText(n: number): string {
  const text = formatQuantity(n)
  if (parseDecimal(text) === Math.abs(n) && (n >= 0 || text.startsWith(MINUS))) return text
  return (n < 0 ? MINUS : "") + toPersianDigits(plainDecimal(n).replace(".", DECIMAL_SEPARATOR))
}

/**
 * Parses a whole number typed in any digits (Persian, Arabic-Indic, Latin),
 * ignoring separators and anything else that isn't a digit. Empty → 0.
 * For integer-only fields: money and product quantities.
 */
export function parseInteger(value: string): number {
  const digits = toLatinDigits(value).replace(/[^0-9]/g, "")
  return digits === "" ? 0 : Number.parseInt(digits, 10)
}

/**
 * Parses a possibly fractional quantity typed in any digits. `٫` (U+066B),
 * `/` and `.` all mean the decimal point (design-system §5); everything else
 * that isn't a digit is ignored. Returns null for an empty or invalid value.
 * For material quantities only — never money.
 */
export function parseDecimal(value: string): number | null {
  const s = toLatinDigits(value)
    .replace(/[٫/]/g, ".")
    .replace(/[^0-9.]/g, "")
  if (s === "" || s === ".") return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}
