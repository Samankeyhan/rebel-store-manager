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
