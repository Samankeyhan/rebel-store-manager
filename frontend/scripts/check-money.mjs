// `npm run check:money` — fails if a screen bypasses lib/money.ts:
//  1. a hard-coded «تومان» or «ریال» (only lib/money.ts may spell the units;
//     «ریال» is matched only when not part of «متریال»),
//  2. formatNumber(...) (or its `fa` alias in copy files) on what looks like money (use formatMoney / <Money>;
//     a true quantity that trips the name heuristic gets a `// qty` (or `{/* qty */}`) comment),
//  3. a money field still built on IntInput (suffix={X.toman}; use MoneyInput),
//  4. money multiplied or divided by 10, or RIAL_PER_TOMAN, anywhere but
//     lib/money.ts: amounts are integer Rial end to end and only lib/money.ts
//     converts for display. Scans app/, components/ and lib/ (the lib tests
//     are exempt: they check the conversion). String literals are skipped (a
//     Tailwind `bg-black/10` is not arithmetic); a ×10 that really isn't money
//     gets a `// not-money` comment.
import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(fileURLToPath(import.meta.url), "..", "..")
const DIRS = ["app", "components"]
const UNIT = /تومان|(?<!ت)ریال/
const MONEY_WORDS =
  /\b\w*(price|cost|total|amount|fee|paid|profit|revenue|charge|estimate|net|gross|discount|loss|delta|value|rate|avg|sum|kit_cost|shipping|postage|packaging)\w*\b/i
const FORMAT_NUMBER = /(?:formatNumber|\bfa)\(([^()]*(?:\([^()]*\))?[^()]*)\)/g
const INT_MONEY = /suffix=\{\s*\w+\.toman\s*\}/
// `* 10`, `/ 10`, `*= 10`, `/= 10`, `/ (10)`, `10 *` — not 100, 1.5, 10.5 or `**`.
const BY_TEN = /(?<![*/])[*/]=?\s*\(?\s*10(?![\d.])|(?<![\w.])10\s*\*(?![*=])/
const SCALE_DIRS = ["app", "components", "lib"]
const SCALE_EXEMPT = (rel) => rel === "lib/money.ts" || rel.endsWith(".test.mjs")

/** The line's code without string literals; a template literal keeps its ${…} expressions. */
function withoutStrings(code) {
  return code
    .replace(/`([^`]*)`/g, (_, body) => " " + [...body.matchAll(/\$\{([^}]*)\}/g)].map((m) => m[1]).join(" ") + " ")
    .replace(/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, '""')
}

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
        if (/(\/\/|\/\*)\s*qty\b/.test(line)) return
        for (const m of code.matchAll(FORMAT_NUMBER)) {
          if (MONEY_WORDS.test(m[1])) problems.push(`${at}  formatNumber on money? ${m[0]}`)
        }
      })
  }
}

for (const d of SCALE_DIRS) {
  for (const file of files(join(root, d))) {
    const rel = relative(root, file).replaceAll("\\", "/")
    if (SCALE_EXEMPT(rel)) continue
    readFileSync(file, "utf8")
      .split(/\r?\n/)
      .forEach((line, i) => {
        if (/(\/\/|\/\*)\s*not-money\b/.test(line)) return
        const code = withoutStrings(line.replace(/^\s*(\/\/|\*|\/\*).*$/, "").replace(/\/\/.*$/, ""))
        if (/\bRIAL_PER_TOMAN\b/.test(code)) problems.push(`${rel}:${i + 1}  RIAL_PER_TOMAN outside lib/money.ts: ${line.trim()}`)
        else if (BY_TEN.test(code)) problems.push(`${rel}:${i + 1}  money ×10 / ÷10 outside lib/money.ts? ${line.trim()}`)
      })
  }
}

if (problems.length) {
  console.error(problems.join("\n"))
  console.error(`\ncheck:money — ${problems.length} problem(s). See lib/money.ts.`)
  process.exit(1)
}
console.log("check:money — no hard-coded units, no formatNumber on money, no money IntInput, no ×10 / ÷10 outside lib/money.ts.")
