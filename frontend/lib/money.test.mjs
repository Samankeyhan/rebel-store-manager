// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  RIAL_PER_TOMAN,
  currencyLabel,
  formatMoney,
  formatMoneyNumber,
  fromDisplayAmount,
  getCurrency,
  setCurrency,
  subscribeCurrency,
  toDisplayAmount,
} from "./money.ts"
import { parseInteger } from "./persian-numbers.ts"

const NBSP = " "
const MINUS = "‎−"

test("Rial is exactly Toman × 10", () => {
  assert.equal(RIAL_PER_TOMAN, 10)
  for (const t of [0, 1, 7, 180_000, 1_234_567, -2_500]) {
    assert.equal(toDisplayAmount(t, "RIAL"), t * 10)
    assert.equal(toDisplayAmount(t, "TOMAN"), t)
  }
})

test("round trips Toman → display → Toman in both currencies", () => {
  const big = Math.floor(Number.MAX_SAFE_INTEGER / 10)
  for (const t of [0, 1, 9, 10, 180_000, 99_999_999, big, -1, -180_000, -big]) {
    for (const c of ["TOMAN", "RIAL"]) {
      assert.equal(fromDisplayAmount(toDisplayAmount(t, c), c), t, `${t} ${c}`)
    }
  }
})

test("Rial input must be a multiple of 10; it is never rounded", () => {
  for (const n of [1, 5, 15, 19, 99, 180_005, -5, -15]) assert.equal(fromDisplayAmount(n, "RIAL"), null, String(n))
  assert.equal(fromDisplayAmount(20, "RIAL"), 2)
  assert.equal(fromDisplayAmount(-20, "RIAL"), -2)
  assert.equal(fromDisplayAmount(1_800_000, "RIAL"), 180_000)
  // Toman: every integer is exact.
  assert.equal(fromDisplayAmount(15, "TOMAN"), 15)
  // Typed in Persian digits, as MoneyInput reads them.
  assert.equal(fromDisplayAmount(parseInteger("۱۵"), "RIAL"), null)
  assert.equal(fromDisplayAmount(parseInteger("۱٬۸۰۰٬۰۰۰"), "RIAL"), 180_000)
})

test("non-integer or unsafe input is never exact", () => {
  for (const n of [1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(fromDisplayAmount(n, "RIAL"), null)
    assert.equal(fromDisplayAmount(n, "TOMAN"), null)
  }
})

test("large amounts: the Rial figure stays exact up to the safe-integer limit", () => {
  const big = Math.floor(Number.MAX_SAFE_INTEGER / 10)
  assert.equal(toDisplayAmount(big, "RIAL"), big * 10)
  assert.ok(Number.isSafeInteger(toDisplayAmount(big, "RIAL")))
  // Beyond it, display keeps the Toman figure instead of an inexact one (and warns).
  const warn = console.warn
  console.warn = () => {}
  try {
    assert.equal(toDisplayAmount(big + 1, "RIAL"), big + 1)
  } finally {
    console.warn = warn
  }
})

test("formatMoney: number, NBSP, active unit", () => {
  assert.equal(formatMoney(180_000, "TOMAN"), `۱۸۰٬۰۰۰${NBSP}تومان`)
  assert.equal(formatMoney(180_000, "RIAL"), `۱٬۸۰۰٬۰۰۰${NBSP}ریال`)
  assert.equal(formatMoney(0, "RIAL"), `۰${NBSP}ریال`)
  assert.equal(formatMoney(-2_500, "TOMAN"), `${MINUS}۲٬۵۰۰${NBSP}تومان`)
  assert.equal(formatMoney(-2_500, "RIAL"), `${MINUS}۲۵٬۰۰۰${NBSP}ریال`)
  assert.equal(formatMoneyNumber(180_000, "RIAL"), "۱٬۸۰۰٬۰۰۰")
})

test("the store: setCurrency switches every default-argument caller and notifies", () => {
  assert.equal(getCurrency(), "TOMAN")
  let calls = 0
  const off = subscribeCurrency(() => calls++)
  try {
    setCurrency("RIAL")
    assert.equal(getCurrency(), "RIAL")
    assert.equal(currencyLabel(), "ریال")
    assert.equal(formatMoney(5), `۵۰${NBSP}ریال`)
    assert.equal(fromDisplayAmount(15), null)
    setCurrency("RIAL") // no change, no notification
    setCurrency("TOMAN")
    assert.equal(currencyLabel(), "تومان")
    assert.equal(formatMoney(5), `۵${NBSP}تومان`)
    assert.equal(calls, 2)
  } finally {
    off()
    setCurrency("TOMAN")
  }
})
