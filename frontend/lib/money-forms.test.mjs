// Run with `npm test`. The scripted check that a Rial amount which isn't a
// multiple of 10 never reaches the API: it goes through the same parse step
// MoneyInput uses (parseMoneyInput) and then each form's own submit gate.
import { test } from "node:test"
import assert from "node:assert/strict"
import { parseMoneyInput, setCurrency } from "./money.ts"
import { buildOrderBody, initialState, moneyBlocked, priceField, reducer } from "../components/record-sale/state.ts"
import { expenseSubmittable } from "../components/expenses/guard.ts"

/** Types `text` into a record-sale money field, as moneyProps() dispatches it. */
function typeInto(state, field, onExact, text, currency) {
  const { toman } = parseMoneyInput(text, currency)
  if (toman == null) return reducer(state, { type: "moneyInvalid", field, invalid: true })
  return reducer(reducer(state, onExact(toman)), { type: "moneyInvalid", field, invalid: false })
}

const product = { id: 7, retail_price: 1_000, wholesale_price: 800 }

function saleWithOneLine() {
  let s = initialState(1)
  s = reducer(s, { type: "pickProduct", key: 1, product })
  // The discount field is open, so a discount reaches the body.
  s = reducer(s, { type: "line", key: 1, patch: { discountOpen: true } })
  return s
}

test("MoneyInput parse: typing 15 in Rial is not exact; 150 is 15 Toman", () => {
  assert.equal(parseMoneyInput("15", "RIAL").toman, null)
  assert.equal(parseMoneyInput("۱۵", "RIAL").toman, null)
  assert.equal(parseMoneyInput("150", "RIAL").toman, 15)
  assert.equal(parseMoneyInput("۱٬۸۰۰٬۰۰۰", "RIAL").toman, 180_000)
  assert.equal(parseMoneyInput("15", "TOMAN").toman, 15)
  assert.equal(parseMoneyInput("", "RIAL").toman, 0)
  assert.equal(parseMoneyInput("", "RIAL", true).toman, undefined)
})

for (const [label, field, onExact] of [
  ["unit price", priceField(1), (n) => ({ type: "price", key: 1, value: n })],
  ["discount", `discount:1`, (n) => ({ type: "line", key: 1, patch: { discount: n } })],
  ["shipping", "shipping", (n) => ({ type: "shipping", value: n })],
  ["fee", "fee", (n) => ({ type: "fee", value: n })],
]) {
  test(`record sale: 15 Rial in ${label} blocks the order; nothing is built to submit`, () => {
    let s = saleWithOneLine()
    const before = buildOrderBody(s)
    s = typeInto(s, field, onExact, "15", "RIAL")
    assert.equal(moneyBlocked(s), true)
    assert.throws(() => buildOrderBody(s))
    // The last exact values are untouched — nothing was rounded into the form.
    assert.deepEqual({ ...s, invalidMoney: [], serverIssue: null }, { ...saleWithOneLine(), invalidMoney: [], serverIssue: null })
    // Fixing it (150 Rial = 15 Toman) unblocks it, and the body carries Toman.
    s = typeInto(s, field, onExact, "150", "RIAL")
    assert.equal(moneyBlocked(s), false)
    const body = buildOrderBody(s)
    assert.notDeepEqual(body, before)
  })
}

test("record sale: 150 Rial unit price is sent as 15 Toman", () => {
  let s = saleWithOneLine()
  s = typeInto(s, priceField(1), (n) => ({ type: "price", key: 1, value: n }), "150", "RIAL")
  assert.equal(buildOrderBody(s).items[0].unit_price, 15)
})

test("record sale: removing the line, re-picking or a channel change clears its flag", () => {
  let s = typeInto(saleWithOneLine(), priceField(1), (n) => ({ type: "price", key: 1, value: n }), "15", "RIAL")
  assert.equal(moneyBlocked(reducer(s, { type: "removeLine", key: 1 })), false)
  assert.equal(moneyBlocked(reducer(s, { type: "pickProduct", key: 1, product })), false)
  const products = new Map([[product.id, product]])
  assert.equal(moneyBlocked(reducer(s, { type: "channel", channel: "WHOLESALE", products })), false)
  const shipping = typeInto(saleWithOneLine(), "shipping", (n) => ({ type: "shipping", value: n }), "15", "RIAL")
  assert.equal(moneyBlocked(reducer(shipping, { type: "channel", channel: "WHOLESALE", products })), false)
})

test("expense: 15 Rial is never submittable; 150 Rial is (as 15 Toman)", () => {
  const amount15 = parseMoneyInput("15", "RIAL").toman
  assert.equal(expenseSubmittable({ categoryId: 3, amount: amount15 ?? null, busy: false }), false)
  const amount150 = parseMoneyInput("150", "RIAL").toman
  assert.equal(amount150, 15)
  assert.equal(expenseSubmittable({ categoryId: 3, amount: amount150 ?? null, busy: false }), true)
  assert.equal(expenseSubmittable({ categoryId: 3, amount: 0, busy: false }), false)
  assert.equal(expenseSubmittable({ categoryId: null, amount: 15, busy: false }), false)
})

test("the module default currency drives parseMoneyInput when none is passed", () => {
  setCurrency("RIAL")
  try {
    assert.equal(parseMoneyInput("15").toman, null)
  } finally {
    setCurrency("TOMAN")
  }
  assert.equal(parseMoneyInput("15").toman, 15)
})
