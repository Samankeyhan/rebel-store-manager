/**
 * The backend's category refusals (db/categories.py codes), with no React and
 * no API calls, so `npm test` can run it. refusalOf (logic.ts) wraps it.
 */

import { type CodedError, detailNum, hasCode } from "../../lib/error-codes.ts"

export type CategoryConflict =
  | { kind: "inUse"; count: number | null }
  | { kind: "hasChildren" }
  | { kind: "parentInactive" }
  | { kind: "duplicate" }

/** A 409 from deactivate / reactivate / create / rename; null = not one of these. */
export function categoryConflict(e: CodedError): CategoryConflict | null {
  if (e.status !== 409) return null
  if (hasCode(e, "CATEGORY_IN_USE")) return { kind: "inUse", count: detailNum(e, "item_count") }
  if (hasCode(e, "CATEGORY_HAS_SUBCATEGORIES")) return { kind: "hasChildren" }
  if (hasCode(e, "CATEGORY_PARENT_INACTIVE")) return { kind: "parentInactive" }
  if (hasCode(e, "CATEGORY_DUPLICATE_NAME")) return { kind: "duplicate" }
  return null
}
