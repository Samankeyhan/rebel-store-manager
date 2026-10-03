/**
 * A date range kept in a page's URL as ?from=YYYY-MM-DD&to=YYYY-MM-DD
 * (Gregorian, whole local days, both ends inclusive). Dependency-free so it
 * can be unit-tested with `node --test` (see url-range.test.mjs).
 */

export type UrlRange = { from: string; to: string }

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/

/** The URL's range, or `fallback` when either end is missing, malformed or reversed. */
export function readUrlRange(params: URLSearchParams, fallback: UrlRange): UrlRange {
  const from = params.get("from")
  const to = params.get("to")
  if (from && to && ISO_DAY.test(from) && ISO_DAY.test(to) && from <= to) return { from, to }
  return fallback
}

/**
 * `params` with the range written in; the default range is written as no
 * parameters at all, so a plain link keeps meaning "the default".
 */
export function writeUrlRange(params: URLSearchParams, range: UrlRange, fallback: UrlRange): URLSearchParams {
  const next = new URLSearchParams(params)
  if (range.from === fallback.from && range.to === fallback.to) {
    next.delete("from")
    next.delete("to")
  } else {
    next.set("from", range.from)
    next.set("to", range.to)
  }
  return next
}
