// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  DRAFT_KEY,
  clearDraft,
  difference,
  differenceNanos,
  emptyDraft,
  filterRows,
  itemKey,
  loadDraft,
  movedSince,
  moveFocus,
  parseCount,
  parseDraft,
  rowState,
  saveDraft,
} from "./stocktake.ts"

// ---------------------------------------------------------------------- reading a typed count

test("blank text is not counted", () => {
  for (const t of ["", "   "]) assert.deepEqual(parseCount(t), { ok: true, value: null })
})

test("Persian and Latin digits, with ٫ or . as the decimal separator", () => {
  assert.deepEqual(parseCount("۱۲"), { ok: true, value: 12 })
  assert.deepEqual(parseCount("۲٫۵"), { ok: true, value: 2.5 })
  assert.deepEqual(parseCount("2.5"), { ok: true, value: 2.5 })
  assert.deepEqual(parseCount(" 0 "), { ok: true, value: 0 })
  assert.deepEqual(parseCount("۱٬۲۰۰"), { ok: true, value: 1200 }) // the thousands mark formatQuantity prints
})

test('ambiguous input is refused, not guessed: "," and "/" alone, negatives, junk', () => {
  for (const t of [",", "۱,۵", "1,5", "۲/۵", "1,200"]) assert.deepEqual(parseCount(t), { ok: false, reason: "ambiguous" }, t)
  for (const t of ["-3", "−3", "abc", "1.2.3", ".", "1e3", "۲ عدد", "Infinity"]) {
    assert.equal(parseCount(t).ok, false, t)
  }
})

// ---------------------------------------------------------------- exact differences

test("difference is exact decimal arithmetic rounded half-even to 1e-9", () => {
  assert.equal(difference(0.3, 0.1 + 0.2), 0) // 0.30000000000000004 is float noise
  assert.equal(difference(5, 2), 3)
  assert.equal(difference(2.5, 5), -2.5)
  assert.equal(difference(0.1, 0), 0.1)
  assert.equal(difference(1.0000000004, 1), 0)
  assert.equal(difference(1.000000001, 1), 1e-9)
  assert.equal(difference(0.7040000000000001, 0.704), 0)
  assert.equal(difference(0, 0.30000000000000004), -0.3)
})

test("differences of large values stay exact where float subtraction would not", () => {
  assert.equal(differenceNanos(999_999_999.5, 0.5), 999_999_999_000_000_000n)
  assert.equal(difference(1_000_000_000, 999_999_999), 1)
  assert.equal(differenceNanos(1e-7, 0), 100n) // numbers that print with an exponent
  assert.equal(differenceNanos(0, 1.1102230246251565e-16), 0n)
})

test("an exact half of a billionth goes to the even neighbour, both signs", () => {
  assert.equal(differenceNanos(0.0000000005, 0), 0n) // 0.5 -> 0
  assert.equal(differenceNanos(0.0000000015, 0), 2n) // 1.5 -> 2
  assert.equal(differenceNanos(0, 0.0000000005), 0n)
  assert.equal(differenceNanos(0, 0.0000000015), -2n)
})

// ----------------------------------------------------------------------- row state

const base = { kind: "MATERIAL", systemQuantity: 10, costUnknown: false, hasCost: false }

test("row states: blank, same, gain, loss", () => {
  assert.equal(rowState({ ...base, countText: "" }).status, "blank")
  assert.equal(rowState({ ...base, countText: "۱۰" }).status, "same")
  assert.deepEqual(rowState({ ...base, countText: "12.5" }), { status: "gain", counted: 12.5, difference: 2.5, needsCost: false })
  assert.deepEqual(rowState({ ...base, countText: "0" }), { status: "loss", counted: 0, difference: -10, needsCost: false })
})

test("a material with float noise in its stock counted at the same decimal is the same", () => {
  assert.equal(rowState({ ...base, systemQuantity: 0.1 + 0.2, countText: "0.3" }).status, "same")
})

test("products must be whole numbers; materials may be fractional", () => {
  const product = { ...base, kind: "PRODUCT", systemQuantity: 1 }
  assert.deepEqual(rowState({ ...product, countText: "2.5" }), { status: "invalid", counted: null, difference: 0, reason: "notWhole", needsCost: false })
  assert.equal(rowState({ ...product, countText: "3" }).status, "gain")
  assert.equal(rowState({ ...base, countText: "2.5" }).status, "loss")
})

test("invalid text and numbers beyond the limit are invalid with a reason", () => {
  assert.equal(rowState({ ...base, countText: "abc" }).reason, "format")
  assert.equal(rowState({ ...base, countText: "1,5" }).reason, "ambiguous")
  assert.equal(rowState({ ...base, countText: "-1" }).reason, "format")
  assert.equal(rowState({ ...base, countText: "1000000001" }).reason, "tooLarge")
  assert.equal(rowState({ ...base, countText: "1000000000" }).status, "gain")
})

test("a gain on an item without a cost needs one until a cost is entered; a loss never does", () => {
  const product = { kind: "PRODUCT", systemQuantity: 0, costUnknown: true, hasCost: false }
  assert.equal(rowState({ ...product, countText: "12" }).needsCost, true)
  assert.equal(rowState({ ...product, countText: "12", hasCost: true }).needsCost, false)
  assert.equal(rowState({ ...product, systemQuantity: 5, countText: "1" }).needsCost, false)
  assert.equal(rowState({ ...product, countText: "0" }).needsCost, false)
})

// -------------------------------------------------------------------------- filters

const rows = [
  { key: "P:1", name: "آلبوم یک", category: "آلبوم", isActive: true },
  { key: "P:2", name: "تی‌شرت", category: "تی‌شرت", isActive: true },
  { key: "P:3", name: "كاست قدیمی", category: "کاست", isActive: false },
  { key: "M:1", name: "جعبه ۲", category: "بسته‌بندی", isActive: true },
]
const none = { query: "", category: "", onlyDifferences: false, showInactive: false }
const keys = (list) => list.map((r) => r.key)

test("inactive items are hidden unless the toggle is on", () => {
  assert.deepEqual(keys(filterRows(rows, none, () => "blank")), ["P:1", "P:2", "M:1"])
  assert.deepEqual(keys(filterRows(rows, { ...none, showInactive: true }, () => "blank")), ["P:1", "P:2", "P:3", "M:1"])
})

test("category filter and name search (digits, Arabic letters and ZWNJ fold)", () => {
  assert.deepEqual(keys(filterRows(rows, { ...none, category: "آلبوم" }, () => "blank")), ["P:1"])
  assert.deepEqual(keys(filterRows(rows, { ...none, query: "جعبه 2" }, () => "blank")), ["M:1"])
  assert.deepEqual(keys(filterRows(rows, { ...none, query: "تیشرت" }, () => "blank")), ["P:2"])
  assert.deepEqual(keys(filterRows(rows, { ...none, query: "کاست", showInactive: true }, () => "blank")), ["P:3"])
})

test("only differences keeps gains, losses and invalid counts (so they are not hidden)", () => {
  const status = { "P:1": "gain", "P:2": "same", "M:1": "invalid" }
  assert.deepEqual(keys(filterRows(rows, { ...none, onlyDifferences: true }, (r) => status[r.key] ?? "blank")), ["P:1", "M:1"])
})

// --------------------------------------------------------------------------- keyboard

test("Enter / arrows move to the next or previous visible row and stop at the ends", () => {
  const visible = ["P:1", "P:5", "M:2"]
  assert.equal(moveFocus(visible, "P:1", 1), "P:5")
  assert.equal(moveFocus(visible, "M:2", 1), null)
  assert.equal(moveFocus(visible, "P:5", -1), "P:1")
  assert.equal(moveFocus(visible, "P:1", -1), null)
  assert.equal(moveFocus(visible, "P:9", 1), null) // a row that is no longer visible
})

// ----------------------------------------------------------------------------- draft

function memory() {
  const data = new Map()
  return { data, getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: (k) => void data.delete(k) }
}
const valid = new Set(["P:1", "P:2", "M:3"])

test("itemKey", () => {
  assert.equal(itemKey("PRODUCT", 12), "P:12")
  assert.equal(itemKey("MATERIAL", 3), "M:3")
})

test("a draft round-trips through storage", () => {
  const storage = memory()
  const draft = { ...emptyDraft("2026-10-13T10:00:00Z"), date: "2026-10-12", counts: { "P:1": "۱۲", "M:3": "2٫5" }, costs: { "P:1": 1500000 }, seen: { "P:1": 0, "M:3": 10 } }
  assert.equal(saveDraft(storage, draft), true)
  assert.ok(storage.data.has(DRAFT_KEY))
  assert.deepEqual(loadDraft(storage, valid), draft)
})

test("unknown ids, blank counts and bad values are dropped on load", () => {
  const text = JSON.stringify({
    version: 1, savedAt: "x", date: "13/10/2026",
    counts: { "P:1": "5", "P:99": "7", "P:2": "  ", "M:3": 4 },
    costs: { "P:1": 12.5, "P:2": -1, "M:3": 900 },
    seen: { "P:1": "a", "M:3": 2 },
  })
  assert.deepEqual(parseDraft(text, valid), { version: 1, savedAt: "x", date: null, counts: { "P:1": "5" }, costs: { "M:3": 900 }, seen: { "M:3": 2 } })
})

test("corrupt JSON, another version and wrong shapes are ignored", () => {
  for (const text of [null, "", "{", "[]", "null", "42", JSON.stringify({ version: 2, savedAt: "x", counts: {} }), JSON.stringify({ version: 1, counts: {} })]) {
    assert.equal(parseDraft(text, valid), null, String(text))
  }
  assert.deepEqual(parseDraft(JSON.stringify({ version: 1, savedAt: "x", counts: "no", costs: [], seen: null }), valid), emptyDraft("x"))
})

test("storage that throws never breaks the screen", () => {
  const broken = { getItem() { throw new Error("denied") }, setItem() { throw new Error("quota") }, removeItem() { throw new Error("denied") } }
  assert.equal(loadDraft(broken, valid), null)
  assert.equal(saveDraft(broken, { ...emptyDraft("x"), counts: { "P:1": "1" } }), false)
  assert.doesNotThrow(() => clearDraft(broken))
  assert.equal(loadDraft(null, valid), null)
  assert.equal(saveDraft(undefined, emptyDraft("x")), false)
})

test("saving a draft with nothing counted removes the stored one; clear removes it too", () => {
  const storage = memory()
  saveDraft(storage, { ...emptyDraft("x"), counts: { "P:1": "1" } })
  assert.ok(storage.data.has(DRAFT_KEY))
  assert.equal(saveDraft(storage, { ...emptyDraft("y"), counts: { "P:1": "" } }), true)
  assert.equal(storage.data.has(DRAFT_KEY), false)
  saveDraft(storage, { ...emptyDraft("x"), counts: { "P:1": "1" } })
  clearDraft(storage)
  assert.equal(storage.data.has(DRAFT_KEY), false)
})

test("rows whose system quantity moved since the count was typed are flagged", () => {
  assert.deepEqual(movedSince({ "P:1": 5, "M:3": 2.5, "P:2": 1 }, { "P:1": 4, "M:3": 0.1 + 2.4, "P:9": 1 }), ["P:1"])
  assert.deepEqual(movedSince({}, { "P:1": 4 }), [])
})
