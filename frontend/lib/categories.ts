/**
 * Display labels for product categories. The backend stores category codes
 * (db/constants.py VALID_CATEGORIES); the UI never shows a code. An unknown
 * value (e.g. a category added later, or one already stored in Persian) is
 * shown as is.
 */
const CATEGORY_LABELS: Record<string, string> = {
  ALBUM: "آلبوم",
  CASSETTE: "کاست",
  VINYL: "وینیل",
  MIRROR: "آینه",
  POSTER: "پوستر",
  STICKER: "استیکر",
  TSHIRT: "تی‌شرت",
  OTHER: "سایر",
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category
}
