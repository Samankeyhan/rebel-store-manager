// `npm test` — the search key (a port of db/names.py name_key) and the name match built on it.
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { nameMatches, searchKey, storedForm } from "./search-key.ts"

const VECTORS = JSON.parse(readFileSync(new URL("../../tests/fixtures/name_key_vectors.json", import.meta.url), "utf8")).vectors
const ZWNJ = "‌"

test("the port gives db.names.name_key's answer for every shared vector", () => {
  assert.ok(VECTORS.length >= 20)
  for (const { input, key } of VECTORS) {
    assert.equal(searchKey(input), key, `searchKey(${JSON.stringify(input)})`)
  }
})

test("a key is idempotent: searching with a key finds what the key came from", () => {
  for (const { input } of VECTORS) assert.equal(searchKey(searchKey(input)), searchKey(input), JSON.stringify(input))
})

test("English is case-insensitive and ignores extra spaces", () => {
  assert.equal(nameMatches("Rebel LP Vinyl", "vinyl"), true)
  assert.equal(nameMatches("Rebel LP Vinyl", "  LP   VINYL "), true)
  assert.equal(nameMatches("Rebel LP Vinyl", "tape"), false)
})

test("Persian: Arabic ي/ك find Persian ی/ک and the other way round", () => {
  assert.equal(nameMatches("کتاب علی", "كتاب علي"), true)
  assert.equal(nameMatches("كتاب علي", "کتاب علی"), true)
})

test("Persian, Arabic-Indic and Latin digits are the same digit", () => {
  assert.equal(nameMatches("پوستر ۲۰۲۴", "2024"), true)
  assert.equal(nameMatches("پوستر ۲۰۲۴", "٢٠٢٤"), true)
  assert.equal(nameMatches("Poster 2024", "۲۰۲۴"), true)
  assert.equal(nameMatches("پوستر ۲۰۲۴", "2025"), false)
})

test("a ZWNJ does not matter in either the name or the query", () => {
  assert.equal(nameMatches(`تی${ZWNJ}شرت`, "تیشرت"), true)
  assert.equal(nameMatches("تیشرت", `تی${ZWNJ}شرت`), true)
})

test("mixed Persian and English names are found by either part", () => {
  const name = `Rebel تی${ZWNJ}شرت XL`
  assert.equal(nameMatches(name, "rebel"), true)
  assert.equal(nameMatches(name, "تیشرت xl"), true)
  assert.equal(nameMatches(name, "hoodie"), false)
})

test("an empty or blank query matches every name", () => {
  assert.equal(nameMatches("anything", ""), true)
  assert.equal(nameMatches("anything", "   "), true)
  assert.equal(nameMatches("", ""), true)
})

test("storedForm keeps a ZWNJ only between two Arabic-script letters", () => {
  assert.equal(storedForm(`می${ZWNJ}خواهم`), `می${ZWNJ}خواهم`)
  assert.equal(storedForm(`a${ZWNJ}b`), "ab")
  assert.equal(storedForm(`می${ZWNJ} A`), "می A")
})
