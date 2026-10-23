/**
 * The stocktake page's one URL parameter: /stocktake?material=<id> opens the page on the materials tab, searching for
 * that material and highlighting its row. Dependency-free so `npm test` covers it.
 * It only filters the view: counts, costs and a stored draft are never touched by arriving through a link.
 */

/** The link to the stocktake page for one material. */
export function stocktakeMaterialHref(materialId: number): string {
  return `/stocktake?material=${materialId}`
}

/** The material id a link names: digits only, a positive safe integer; anything else is no link at all. */
export function materialFromParams(params: URLSearchParams): number | null {
  const raw = params.get("material")
  if (raw == null || !/^[1-9]\d{0,15}$/.test(raw)) return null
  const id = Number(raw)
  return Number.isSafeInteger(id) ? id : null
}
