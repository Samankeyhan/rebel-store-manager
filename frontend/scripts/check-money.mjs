// `npm run check:money` — fails if a screen bypasses lib/money.ts:
//  1. a hard-coded «تومان» or «ریال» (only lib/money.ts may spell the units;
//     «ریال» is matched only when not part of «متریال»),
//  2. formatNumber(...) on what looks like money (use formatMoney / <Money>;
//     a true quantity that trips the name heuristic gets a `// qty` comment),
//  3. a money field still built on IntInput (suffix={X.toman}; use MoneyInput).
import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(fileURLToPath(import.meta.url), "..", "..")
const DIRS = ["app", "components"]
const UNIT = /تومان|(?<!ت)ریال/
const MONEY_WORDS =
  /\b\w*(price|cost|total|amount|fee|paid|profit|revenue|charge|estimate|net|gross|discount|loss|delta|value|rate|avg|sum|kit_cost|shipping|postage|packaging)\w*\b/i
const FORMAT_NUMBER = /formatNumber\(([^()]*(?:\([^()]*\))?[^()]*)\)/g
const INT_MONEY = /suffix=\{\s*\w+\.toman\s*\}/

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) yield* files(p)
    else if (/\.(tsx?|mjs)$/.test(name)) yield p
  }
}

const problems = []
for (const d of DIRS) {
  for (const file of files(join(root, d))) {
    const rel = relative(root, file).replaceAll("\\", "/")
    readFileSync(file, "utf8")
      .split(/\r?\n/)
      .forEach((line, i) => {
        const at = `${rel}:${i + 1}`
        const code = line.replace(/^\s*(\/\/|\*|\/\*).*$/, "") // skip comment lines
        if (UNIT.test(code)) problems.push(`${at}  hard-coded unit: ${line.trim()}`)
        if (INT_MONEY.test(code)) problems.push(`${at}  money IntInput (use MoneyInput): ${line.trim()}`)
        if (/\/\/\s*qty\b/.test(line)) return
        for (const m of code.matchAll(FORMAT_NUMBER)) {
          if (MONEY_WORDS.test(m[1])) problems.push(`${at}  formatNumber on money? ${m[0]}`)
        }
      })
  }
}

if (problems.length) {
  console.error(problems.join("\n"))
  console.error(`\ncheck:money — ${problems.length} problem(s). See lib/money.ts.`)
  process.exit(1)
}
console.log("check:money — no hard-coded units, no formatNumber on money, no money IntInput.")
