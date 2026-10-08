// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  MAX_RIAL,
  RIAL_PER_TOMAN,
  currencyLabel,
  formatMoney,
  formatMoneyNumber,
  getCurrency,
  moneyInputDisplay,
  moneyInputTextOf,
  parseMoneyInput,
  setCurrency,
  subscribeCurrency,
  toDisplayParts,
} from "./money.ts"
import { M, moneyInputMessage } from "../components/common/copy.ts"

const NBSP = " "
const MINUS = "‎−"

const parts = (negative, whole, tenth) => ({ negative, whole, tenth })

// ---------------------------------------------------------------- display

test("toDisplayParts mirrors db/currency.py to_display_parts", () => {
  assert.equal(RIAL_PER_TOMAN, 10)
  assert.deepEqual(toDisplayParts(1_800_005, "TOMAN"), parts(false, 180_000, 5))
  assert.deepEqual(toDisplayParts(1_800_000, "TOMAN"), parts(false, 180_000, null))
  assert.deepEqual(toDisplayParts(1_800_005, "RIAL"), parts(false, 1_800_005, null))
  assert.deepEqual(toDisplayParts(7, "TOMAN"), parts(false, 0, 7))
  assert.deepEqual(toDisplayParts(0, "TOMAN"), parts(false, 0, null))
  assert.deepEqual(toDisplayParts(-25_005, "TOMAN"), parts(true, 2_500, 5))
  assert.deepEqual(toDisplayParts(-5, "TOMAN"), parts(true, 0, 5))
  assert.deepEqual(toDisplayParts(-5, "RIAL"), parts(true, 5, null))
})

test("toDisplayParts is exact up to the largest safe integer", () => {
  assert.equal(MAX_RIAL, 9_007_199_254_740_991)
  assert.deepEqual(toDisplayParts(MAX_RIAL, "TOMAN"), parts(false, 900_719_925_474_099, 1))
  assert.deepEqual(toDisplayParts(MAX_RIAL, "RIAL"), parts(false, MAX_RIAL, null))
  assert.deepEqual(toDisplayParts(-MAX_RIAL, "TOMAN"), parts(true, 900_719_925_474_099, 1))
  assert.deepEqual(toDisplayParts(MAX_RIAL - 1, "TOMAN"), parts(false, 900_719_925_474_099, null))
  // Every last digit round-trips through the parts.
  for (let r = MAX_RIAL - 30; r <= MAX_RIAL; r++) {
    const { whole, tenth } = toDisplayParts(r, "TOMAN")
    assert.equal(String(whole) + String(tenth ?? 0), String(r))
  }
})

test("toDisplayParts never throws on a slip upstream (warns)", () => {
  const warn = console.warn
  const warnings = []
  console.warn = (m) => warnings.push(m)
  try {
    assert.deepEqual(toDisplayParts(Number.NaN, "TOMAN"), parts(false, 0, null))
    assert.deepEqual(toDisplayParts(MAX_RIAL + 2, "RIAL"), parts(false, 0, null))
    assert.deepEqual(toDisplayParts(15.4, "TOMAN"), parts(false, 1, 5))
    assert.equal(warnings.length, 3)
  } finally {
    console.warn = warn
  }
})

test("formatMoney: Persian digits, «٬» grouping, «٫» + one digit only when needed, NBSP, unit", () => {
  assert.equal(formatMoney(1_800_000, "TOMAN"), `۱۸۰٬۰۰۰${NBSP}تومان`)
  assert.equal(formatMoney(1_800_005, "TOMAN"), `۱۸۰٬۰۰۰٫۵${NBSP}تومان`)
  assert.equal(formatMoney(1_800_005, "RIAL"), `۱٬۸۰۰٬۰۰۵${NBSP}ریال`)
  assert.equal(formatMoney(1_800_000, "RIAL"), `۱٬۸۰۰٬۰۰۰${NBSP}ریال`)
  assert.equal(formatMoney(0, "TOMAN"), `۰${NBSP}تومان`)
  assert.equal(formatMoney(7, "TOMAN"), `۰٫۷${NBSP}تومان`)
  assert.equal(formatMoney(999_999_995, "TOMAN"), `۹۹٬۹۹۹٬۹۹۹٫۵${NBSP}تومان`)
  assert.equal(formatMoney(999_999_995, "RIAL"), `۹۹۹٬۹۹۹٬۹۹۵${NBSP}ریال`)
  assert.equal(formatMoney(MAX_RIAL, "RIAL"), `۹٬۰۰۷٬۱۹۹٬۲۵۴٬۷۴۰٬۹۹۱${NBSP}ریال`)
  assert.equal(formatMoney(MAX_RIAL, "TOMAN"), `۹۰۰٬۷۱۹٬۹۲۵٬۴۷۴٬۰۹۹٫۱${NBSP}تومان`)
})

test("formatMoney: the shared minus, also on amounts under one Toman", () => {
  assert.equal(formatMoney(-25_000, "TOMAN"), `${MINUS}۲٬۵۰۰${NBSP}تومان`)
  assert.equal(formatMoney(-25_005, "TOMAN"), `${MINUS}۲٬۵۰۰٫۵${NBSP}تومان`)
  assert.equal(formatMoney(-25_005, "RIAL"), `${MINUS}۲۵٬۰۰۵${NBSP}ریال`)
  assert.equal(formatMoney(-5, "TOMAN"), `${MINUS}۰٫۵${NBSP}تومان`)
  assert.equal(formatMoneyNumber(1_800_005, "TOMAN"), "۱۸۰٬۰۰۰٫۵")
  assert.equal(formatMoneyNumber(1_800_005, "RIAL"), "۱٬۸۰۰٬۰۰۵")
})

// ---------------------------------------------------------------- input

const rialOf = (text, c, allowEmpty) => parseMoneyInput(text, c, allowEmpty).rial
const errorOf = (text, c) => parseMoneyInput(text, c).error

test("Toman input: the Rial value is built from the digit string", () => {
  assert.equal(rialOf("180000", "TOMAN"), 1_800_000)
  assert.equal(rialOf("180000.5", "TOMAN"), 1_800_005)
  assert.equal(rialOf("۱۸۰٬۰۰۰٫۵", "TOMAN"), 1_800_005)
  assert.equal(rialOf("١٨٠٬٠٠٠٫٥", "TOMAN"), 1_800_005) // Arabic-Indic
  assert.equal(rialOf("180,000/5", "TOMAN"), 1_800_005)
  assert.equal(rialOf("180 000.5", "TOMAN"), 1_800_005)
  assert.equal(rialOf("0.7", "TOMAN"), 7)
  assert.equal(rialOf(".7", "TOMAN"), 7)
  assert.equal(rialOf("12.", "TOMAN"), 120)
  assert.equal(rialOf("12.0", "TOMAN"), 120)
  assert.equal(rialOf("007", "TOMAN"), 70)
  // 0.1 + 0.2 style floats never enter: these are digit strings.
  assert.equal(rialOf("99999999.5", "TOMAN"), 999_999_995)
  assert.equal(rialOf("900719925474099.1", "TOMAN"), MAX_RIAL)
})

test("Toman input: at most one decimal digit", () => {
  for (const t of ["1.25", "۱٫۲۵", "180000.50", "0.05"]) {
    assert.equal(rialOf(t, "TOMAN"), null, t)
    assert.equal(errorOf(t, "TOMAN"), "tomanDecimals", t)
  }
  assert.equal(moneyInputMessage("tomanDecimals"), "در تومان حداکثر یک رقم اعشار مجاز است")
})

test("Rial input: any integer; a decimal mark is refused", () => {
  assert.equal(rialOf("15", "RIAL"), 15) // no multiple-of-10 rule any more
  assert.equal(rialOf("۱٬۸۰۰٬۰۰۵", "RIAL"), 1_800_005)
  assert.equal(rialOf("1,800,005", "RIAL"), 1_800_005)
  assert.equal(rialOf(String(MAX_RIAL), "RIAL"), MAX_RIAL)
  for (const t of ["15.5", "۱۵٫۵", "15/5", "15.", "15.0"]) {
    assert.equal(rialOf(t, "RIAL"), null, t)
    assert.equal(errorOf(t, "RIAL"), "rialDecimal", t)
  }
  assert.equal(moneyInputMessage("rialDecimal"), "ریال عدد صحیح است و اعشار ندارد")
})

test("a minus sign is refused, not dropped", () => {
  for (const c of ["TOMAN", "RIAL"]) {
    for (const t of ["-5", "−5", "۵-", "-۱۸۰٬۰۰۰"]) {
      assert.equal(rialOf(t, c), null, `${t} ${c}`)
      assert.equal(errorOf(t, c), "negative", `${t} ${c}`)
    }
  }
  assert.equal(moneyInputMessage("negative"), "مبلغ منفی مجاز نیست")
  // The field keeps the minus, so the user sees what the message is about.
  assert.equal(parseMoneyInput("-5", "RIAL").text, "-5")
})

test("beyond the largest safe amount gives null, never a rounded number", () => {
  assert.equal(rialOf(String(MAX_RIAL + 1), "RIAL"), null) // "9007199254740992"
  assert.equal(errorOf("9007199254740992", "RIAL"), "tooLarge")
  assert.equal(rialOf("99999999999999999", "RIAL"), null)
  assert.equal(rialOf("900719925474099.2", "TOMAN"), null)
  assert.equal(rialOf("900719925474100", "TOMAN"), null)
  assert.equal(errorOf("900719925474100", "TOMAN"), "tooLarge")
  assert.equal(moneyInputMessage("tooLarge"), M.tooLarge)
  // Leading zeros don't count towards the length.
  assert.equal(rialOf("000" + String(MAX_RIAL), "RIAL"), MAX_RIAL)
})

test("empty input: 0, or undefined with allowEmpty; a lone mark is empty in Toman", () => {
  for (const c of ["TOMAN", "RIAL"]) {
    assert.equal(rialOf("", c), 0)
    assert.equal(rialOf("", c, true), undefined)
    assert.equal(rialOf("٬ ,", c, true), undefined)
  }
  assert.equal(rialOf("٫", "TOMAN", true), undefined)
  assert.equal(rialOf("٫", "RIAL", true), null)
})

test("the field text: digits plus one decimal mark, shown in Persian", () => {
  assert.equal(parseMoneyInput("۱۸۰٬۰۰۰٫۵", "TOMAN").text, "180000.5")
  assert.equal(parseMoneyInput("1.2.3", "TOMAN").text, "1.23") // only the first mark counts
  assert.equal(parseMoneyInput("0012", "RIAL").text, "12")
  assert.equal(moneyInputDisplay("180000.5"), "۱۸۰٬۰۰۰٫۵")
  assert.equal(moneyInputDisplay("180000."), "۱۸۰٬۰۰۰٫")
  assert.equal(moneyInputDisplay("-5"), `${MINUS}۵`)
  assert.equal(moneyInputDisplay("99999999999999999999"), "۹۹٬۹۹۹٬۹۹۹٬۹۹۹٬۹۹۹٬۹۹۹٬۹۹۹") // no digit lost
  // An amount set from outside.
  assert.equal(moneyInputTextOf(1_800_005, "TOMAN"), "180000.5")
  assert.equal(moneyInputTextOf(1_800_000, "TOMAN"), "180000")
  assert.equal(moneyInputTextOf(1_800_005, "RIAL"), "1800005")
  assert.equal(moneyInputTextOf(null, "TOMAN"), "")
  assert.equal(moneyInputTextOf(undefined, "RIAL"), "")
})

test("round trip: Rial → field text → Rial in both currencies", () => {
  for (const r of [0, 1, 7, 9, 10, 15, 1_800_005, 999_999_995, MAX_RIAL - 1, MAX_RIAL]) {
    for (const c of ["TOMAN", "RIAL"]) {
      assert.equal(rialOf(moneyInputTextOf(r, c), c), r, `${r} ${c}`)
      assert.equal(rialOf(moneyInputDisplay(moneyInputTextOf(r, c)), c), r, `${r} ${c} shown`)
    }
  }
})

test("parseMoneyInput coverage: scripts, marks, separators, leading zeros, empty, minus, limits", () => {
  // Digits in Persian, Arabic-Indic and Latin script, in both currencies.
  for (const [t, r] of [["۱۲۳۴", 1_234], ["١٢٣٤", 1_234], ["1234", 1_234], ["۱2٣4", 1_234]]) {
    assert.equal(rialOf(t, "RIAL"), r, t)
    assert.equal(rialOf(t, "TOMAN"), r * 10, t) // a whole Toman amount: the test's own expectation
  }
  // Each decimal mark: «٫» U+066B, "." and "/".
  for (const mark of ["٫", ".", "/"]) {
    assert.equal(rialOf(`12${mark}5`, "TOMAN"), 125, mark)
    assert.equal(errorOf(`12${mark}5`, "RIAL"), "rialDecimal", mark)
  }
  // Separators «٬» U+066C, "," and spaces are ignored.
  for (const t of ["۱٬۲۳۴٬۵۶۷", "1,234,567", "1 234 567", " ۱٬۲۳۴,567 "]) {
    assert.equal(rialOf(t, "RIAL"), 1_234_567, t)
    assert.equal(rialOf(t, "TOMAN"), 12_345_670, t)
  }
  // Leading zeros.
  assert.equal(rialOf("۰۰۵", "TOMAN"), 50)
  assert.equal(rialOf("۰۰۵", "RIAL"), 5)
  assert.equal(rialOf("0.5", "TOMAN"), 5)
  assert.equal(rialOf("۰٫۵", "TOMAN"), 5)
  assert.equal(rialOf("00.5", "TOMAN"), 5)
  assert.equal(parseMoneyInput("۰۰۵", "RIAL").text, "5")
  // Empty, with and without allowEmpty.
  for (const c of ["TOMAN", "RIAL"]) {
    assert.deepEqual(parseMoneyInput("", c), { text: "", rial: 0, error: null })
    assert.deepEqual(parseMoneyInput("", c, true), { text: "", rial: undefined, error: null })
  }
  // Every minus character the parser knows: - U+2212 U+2012 U+2013 U+2014 U+FE63 U+FF0D.
  for (const m of ["-", "−", "‒", "–", "—", "﹣", "－"]) {
    for (const c of ["TOMAN", "RIAL"]) {
      assert.equal(rialOf(`${m}5`, c), null, `${m} ${c}`)
      assert.equal(errorOf(`${m}5`, c), "negative", `${m} ${c}`)
    }
  }
  // Both sides of the maximum in each currency.
  assert.equal(rialOf("9007199254740991", "RIAL"), 9_007_199_254_740_991)
  assert.equal(rialOf("۹٬۰۰۷٬۱۹۹٬۲۵۴٬۷۴۰٬۹۹۱", "RIAL"), 9_007_199_254_740_991)
  assert.equal(rialOf("9007199254740992", "RIAL"), null)
  assert.equal(errorOf("9007199254740992", "RIAL"), "tooLarge")
  assert.equal(rialOf("900719925474099.1", "TOMAN"), 9_007_199_254_740_991)
  assert.equal(rialOf("۹۰۰٬۷۱۹٬۹۲۵٬۴۷۴٬۰۹۹٫۱", "TOMAN"), 9_007_199_254_740_991)
  assert.equal(rialOf("900719925474099.2", "TOMAN"), null)
  assert.equal(errorOf("900719925474099.2", "TOMAN"), "tooLarge")
})

// ---------------------------------------------------------------- the store

test("the store: setCurrency switches every default-argument caller and notifies", () => {
  assert.equal(getCurrency(), "TOMAN")
  let calls = 0
  const off = subscribeCurrency(() => calls++)
  try {
    setCurrency("RIAL")
    assert.equal(getCurrency(), "RIAL")
    assert.equal(currencyLabel(), "ریال")
    assert.equal(formatMoney(5), `۵${NBSP}ریال`)
    assert.equal(parseMoneyInput("1.5").error, "rialDecimal")
    setCurrency("RIAL") // no change, no notification
    setCurrency("TOMAN")
    assert.equal(currencyLabel(), "تومان")
    assert.equal(formatMoney(5), `۰٫۵${NBSP}تومان`)
    assert.equal(parseMoneyInput("1.5").rial, 15)
    assert.equal(calls, 2)
  } finally {
    off()
    setCurrency("TOMAN")
  }
})
