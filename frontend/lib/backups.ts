/** Text for the backup card (Settings → «پشتیبان‌گیری»): sizes and the reason a backup failed, from the API's typed `reason`. */

import { formatNumber, formatQuantity } from "./persian-numbers.ts"

const REASONS: Record<string, string> = {
  disk_full: "فضای دیسک پر است.",
  locked: "پایگاه داده در آن لحظه در حال استفاده بود.",
  integrity: "نسخهٔ ساخته‌شده سالم نبود و حذف شد.",
  folder: "پوشهٔ پشتیبان ساخته یا نوشته نشد.",
  unknown: "خطای ناشناخته؛ جزئیات در فایل لاگ است.",
}

/** The plain-language reason for a failed backup (`BACKUP_FAILED` details.reason, or the status file's reason). */
export function backupReason(reason: string | null | undefined): string {
  return (reason && REASONS[reason]) || REASONS.unknown
}

/** «۸۰۰ بایت», «۵۲۰ کیلوبایت», «۱٫۲ مگابایت». */
export function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—"
  if (bytes < 1024) return `${formatNumber(Math.round(bytes))} بایت`
  if (bytes < 1024 * 1024) return `${formatNumber(Math.round(bytes / 1024))} کیلوبایت`
  return `${formatQuantity(Number((bytes / (1024 * 1024)).toFixed(1)))} مگابایت`
}

/** «۱۲ از ۶۰». */
export function keptText(count: number, keep: number): string {
  return `${formatNumber(count)} از ${formatNumber(keep)}`
}
