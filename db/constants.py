"""Fixed code lists shared by db/: `VALID_CHANNELS`, `VALID_STATUSES`, and `LEGACY_PRODUCT_CATEGORIES` (the pre-005 category codes; documentation and tests only, nothing validates against it)."""

# The fixed product category codes used before migration 005, mapped to the
# name each was seeded under in the categories table. Nothing validates
# against this any more (categories are user-editable rows); it documents the
# migration's backfill map and lets tests resolve a legacy code to its row.
LEGACY_PRODUCT_CATEGORIES = {
    "ALBUM": "آلبوم",
    "CASSETTE": "کاست",
    "VINYL": "وینیل",
    "MIRROR": "آینه",
    "POSTER": "پوستر",
    "STICKER": "استیکر",
    "TSHIRT": "تی‌شرت",
    "OTHER": "سایر",
    "فندک": "فندک",
}
VALID_CHANNELS = ("INSTAGRAM", "WEBSITE", "WHOLESALE", "IN_PERSON", "OTHER")
VALID_STATUSES = (
    "DRAFT",
    "PENDING",
    "PAID",
    "COMPLETED",
    "CANCELLED",
    "REFUNDED",
)
