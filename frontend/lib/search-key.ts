/**
 * The search key of a name: a TypeScript port of `db/names.py` `name_key` (the key the database compares names
 * by), so a search finds a name whatever its spelling variant: Arabic ي/ك against Persian ی/ک, Persian,
 * Arabic-Indic or Latin digits, a ZWNJ or none, invisible direction marks, upper or lower case.
 *
 * It is a port because the Python function cannot run in the browser, and there is no endpoint to ask. Both
 * are checked against the same vectors (tests/fixtures/name_key_vectors.json: `tests/test_names.py` for Python,
 * `lib/search-key.test.mjs` for this file), so they cannot drift apart unnoticed: change both together.
 * Dependency-free, so `npm test` runs it.
 */

const ZWNJ = "‌"

// Zero-width space, LRM, RLM, U+202A-202E, U+2066-2069, BOM, soft hyphen, word joiner (db/names.py _INVISIBLE).
const INVISIBLE = new Set<number>([0x200b, 0x200e, 0x200f, 0xfeff, 0x00ad, 0x2060])
for (let cp = 0x202a; cp <= 0x202e; cp++) INVISIBLE.add(cp)
for (let cp = 0x2066; cp <= 0x2069; cp++) INVISIBLE.add(cp)

const ARABIC_RANGES: readonly (readonly [number, number])[] = [
  [0x0600, 0x06ff],
  [0x0750, 0x077f],
  [0x08a0, 0x08ff],
  [0xfb50, 0xfdff],
  [0xfe70, 0xfeff],
]

function isArabicLetter(ch: string): boolean {
  const cp = ch.codePointAt(0)!
  return /^\p{L}$/u.test(ch) && ARABIC_RANGES.some(([low, high]) => low <= cp && cp <= high)
}

/** Arabic Yeh/Kaf → Persian Yeh/Kaf. */
function fixLetters(text: string): string {
  return text.replace(/ي/g, "ی").replace(/ك/g, "ک")
}

function mapDigits(text: string, base: number, to: number): string {
  return text.replace(new RegExp(`[${String.fromCharCode(base)}-${String.fromCharCode(base + 9)}]`, "g"), (d) =>
    String.fromCharCode(d.charCodeAt(0) - base + to)
  )
}

/** ZWNJ stays only between two Arabic-script letters, and a run of them is one. */
function keepZwnjBetweenLetters(text: string): string {
  const chars = Array.from(text)
  const out: string[] = []
  let i = 0
  while (i < chars.length) {
    if (chars[i] !== ZWNJ) {
      out.push(chars[i])
      i++
      continue
    }
    while (i < chars.length && chars[i] === ZWNJ) i++
    if (out.length > 0 && i < chars.length && isArabicLetter(out[out.length - 1]) && isArabicLetter(chars[i])) {
      out.push(ZWNJ)
    }
  }
  return out.join("")
}

/** db/names.py `stored_form`: what a name is saved as. */
export function storedForm(name: string): string {
  let text = fixLetters(name.normalize("NFC"))
  text = mapDigits(text, 0x660, 0x6f0)
  text = Array.from(text)
    .filter((ch) => !INVISIBLE.has(ch.codePointAt(0)!))
    .join("")
  text = text.split(/\s+/).filter(Boolean).join(" ")
  return keepZwnjBetweenLetters(text).normalize("NFC")
}

/** Python's `str.casefold` for the letters it treats differently from `toLowerCase`: ß → ss, final ς → σ. */
function casefold(text: string): string {
  return text.toLowerCase().replace(/ß/g, "ss").replace(/ς/g, "σ")
}

/** db/names.py `name_key`: the comparison key (stored form, NFKC, no ZWNJ, ASCII digits, case-folded). */
export function searchKey(name: string): string {
  let text = storedForm(name).normalize("NFKC")
  text = fixLetters(text).split(ZWNJ).join("")
  text = mapDigits(mapDigits(text, 0x6f0, 0x30), 0x660, 0x30)
  return casefold(text)
}

/** True when `name` contains `query` under `searchKey`; an empty query matches everything. */
export function nameMatches(name: string, query: string): boolean {
  const q = searchKey(query)
  return q === "" || searchKey(name).includes(q)
}
