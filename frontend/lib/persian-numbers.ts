/**
 * Persian number formatting. EVERY number shown in the UI goes through this
 * module (toPersianDigits / formatNumber / formatMoney) — never render a raw
 * number or call toLocaleString directly, so digits and separators stay
 * consistent across screens.
 *
 * Money is always an integer count of Toman (see the backend's money rule).
 * These functions never throw: a non-integer amount means a rounding slip
 * upstream, which must not crash a screen — it is rounded and warned about.
 */

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
/** U+066C ARABIC THOUSANDS SEPARATOR */
const THOUSANDS_SEPARATOR = "٬"
/** U+2212 MINUS SIGN; U+200E LRM keeps it on the visual left in RTL text. */
const MINUS = "‎−"

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

/** Integer with Persian digits and ٬ thousands separators: 180000 → "۱۸۰٬۰۰۰". */
export function formatNumber(n: number): string {
  const int = toInteger(n, "formatNumber")
  const grouped = String(Math.abs(int)).replace(
    /\B(?=(\d{3})+(?!\d))/g,
    THOUSANDS_SEPARATOR
  )
  return (int < 0 ? MINUS : "") + toPersianDigits(grouped)
}

/** Integer Toman amount: 180000 → "۱۸۰٬۰۰۰ تومان". */
export function formatMoney(n: number): string {
  return `${formatNumber(toInteger(n, "formatMoney"))} تومان`
}

/** U+066B ARABIC DECIMAL SEPARATOR */
const DECIMAL_SEPARATOR = "٫"

/**
 * A quantity that may be fractional (materials): 1.5 → "۱٫۵", 0.06 → "۰٫۰۶",
 * 14 → "۱۴". Up to three decimals; trailing zeros dropped. Not for money.
 */
export function formatQuantity(n: number): string {
  if (!Number.isFinite(n)) {
    console.warn(`formatQuantity: expected a finite number, got ${n}; showing 0`)
    return "۰"
  }
  const thousandths = Math.round(Math.abs(n) * 1000)
  const intPart = Math.floor(thousandths / 1000)
  const frac = String(thousandths % 1000).padStart(3, "0").replace(/0+$/, "")
  const sign = n < 0 && thousandths > 0 ? MINUS : ""
  return (
    sign +
    formatNumber(intPart) +
    (frac ? DECIMAL_SEPARATOR + toPersianDigits(frac) : "")
  )
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
