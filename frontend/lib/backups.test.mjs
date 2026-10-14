// Run with `npm test`.
import { test } from "node:test"
import assert from "node:assert/strict"
import { backupReason, formatSize, keptText } from "./backups.ts"

test("sizes are shown in bytes, kilobytes or megabytes with Persian digits", () => {
  assert.equal(formatSize(800), "۸۰۰ بایت")
  assert.equal(formatSize(1024), "۱ کیلوبایت")
  assert.equal(formatSize(532480), "۵۲۰ کیلوبایت")
  assert.equal(formatSize(1024 * 1024), "۱ مگابایت")
  assert.equal(formatSize(1_258_291), "۱٫۲ مگابایت")
  assert.equal(formatSize(-1), "—")
  assert.equal(formatSize(Number.NaN), "—")
})

test("every backup failure reason has its own text and anything else falls back to the unknown one", () => {
  const texts = ["disk_full", "locked", "integrity", "folder", "unknown"].map(backupReason)
  assert.equal(new Set(texts).size, 5)
  assert.equal(backupReason("something_new"), backupReason("unknown"))
  assert.equal(backupReason(null), backupReason("unknown"))
  assert.equal(backupReason(undefined), backupReason("unknown"))
  for (const text of texts) assert.doesNotMatch(text, /ماده|مواد/)
})

test("the kept count reads «n از 60»", () => {
  assert.equal(keptText(12, 60), "۱۲ از ۶۰")
  assert.equal(keptText(0, 60), "۰ از ۶۰")
})
