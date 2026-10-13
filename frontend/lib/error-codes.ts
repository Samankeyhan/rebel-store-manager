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

const NAME_DUPLICATE_CODES: ErrorCode[] = ["NAME_DUPLICATE", "CATEGORY_DUPLICATE_NAME", "PAYMENT_METHOD_DUPLICATE_NAME"]

/**
 * A create or rename refused because the name (or a spelling variant of it) is taken: 409 with
 * NAME_DUPLICATE, or the older category / payment-method code. details: `entity`, `existing_id`.
 */
export function isNameDuplicate(e: CodedError): boolean {
  return e.status === 409 && hasCode(e, ...NAME_DUPLICATE_CODES)
}

/** Which kind of record a name-duplicate refusal is about (`details.entity`); null if missing. */
export function duplicateEntity(e: CodedError): string | null {
  return isNameDuplicate(e) ? detailStr(e, "entity") : null
}

/** The id of the record that already has the name; null if unknown. */
export function duplicateExistingId(e: CodedError): number | null {
  return isNameDuplicate(e) ? detailNum(e, "existing_id") : null
}

/** An amount over the limit (db/constants.py MAX_MONEY; details `max`, `field` says which amount). MoneyInput stops at the same number, so only a stale client or a script gets here. */
export function isAmountTooLarge(e: CodedError): boolean {
  return e.status === 422 && hasCode(e, "AMOUNT_TOO_LARGE")
}

/** A quantity that is not a whole number, or outside its range (details `min`, `max`: the bound crossed). */
export function isQuantityRefusal(e: CodedError): boolean {
  return e.status === 422 && hasCode(e, "QUANTITY_NOT_WHOLE", "QUANTITY_OUT_OF_RANGE")
}

export type StaleItem = { itemType: string; itemId: number; itemName: string; expected: number; actual: number }

/** The items of a STOCKTAKE_STALE refusal (409): their live stock is not what the count was made against. */
export function staleItems(e: CodedError): StaleItem[] {
  if (e.status !== 409 || !hasCode(e, "STOCKTAKE_STALE")) return []
  const items = e.details?.items
  if (!Array.isArray(items)) return []
  return items.flatMap((raw): StaleItem[] => {
    const i = raw as Record<string, unknown>
    return typeof i.item_type === "string" && typeof i.item_id === "number" && typeof i.item_name === "string" &&
      typeof i.expected === "number" && typeof i.actual === "number"
      ? [{ itemType: i.item_type, itemId: i.item_id, itemName: i.item_name, expected: i.expected, actual: i.actual }]
      : []
  })
}

/** The row index an `items.<index>.<field>` error field points at, and which field; null for any other field. */
export function itemErrorTarget(field: string | null | undefined): { index: number; field: string } | null {
  const match = /^items\.(\d+)\.(\w+)$/.exec(field ?? "")
  return match ? { index: Number(match[1]), field: match[2] } : null
}
