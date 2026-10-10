/**
 * Reading the backend's machine-readable errors, with no React and no API
 * calls, so `npm test` can run it. Every app error carries `code` (an
 * ErrorCode from db/errors.py, typed via lib/api-types.ts) and `details`;
 * screens decide what to show from those, never from the English message.
 * The details each code carries are listed on db/errors.py ErrorCode.
 */

import type { components } from "./api-types.ts"

export type ErrorCode = components["schemas"]["ErrorCode"]

/** The ApiError fields the classifiers read (lib/api.ts ApiError fits). */
export type CodedError = {
  status: number
  code?: ErrorCode | null
  field?: string | null
  details?: Record<string, unknown>
}

export function hasCode(e: CodedError, ...codes: ErrorCode[]): boolean {
  return e.code != null && codes.includes(e.code)
}

/** A numeric detail; null when missing or not a finite number. */
export function detailNum(e: CodedError, key: string): number | null {
  const v = e.details?.[key]
  return typeof v === "number" && Number.isFinite(v) ? v : null
}

/** A string detail; null when missing or not a string. */
export function detailStr(e: CodedError, key: string): string | null {
  const v = e.details?.[key]
  return typeof v === "string" ? v : null
}

/** The product a PRODUCT_NO_RECIPE / PRODUCT_NO_UNIT_COST refusal is about. */
export function refusedProductId(e: CodedError): number | null {
  return hasCode(e, "PRODUCT_NO_RECIPE", "PRODUCT_NO_UNIT_COST") ? detailNum(e, "product_id") : null
}
