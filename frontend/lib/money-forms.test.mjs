// Run with `npm test`. The scripted check that a Rial amount which isn't a
// multiple of 10 never reaches the API: it goes through the same parse step
// MoneyInput uses (parseMoneyInput) and then each form's own submit gate.
import { test } from "node:test"
import assert from "node:assert/strict"
import { parseMoneyInput, setCurrency } from "./money.ts"
import {
  buildOrderBody as buildWithMethod,
  initialState,
  moneyBlocked,
  priceField,
  reducer,
  resolveMethod,
} from "../components/record-sale/state.ts"
import { expenseSubmittable } from "../components/expenses/guard.ts"

/** Types `text` into a record-sale money field, as moneyProps() dispatches it. */
function typeInto(state, field, onExact, text, currency) {
  const { toman } = parseMoneyInput(text, currency)
  if (toman == null) return reducer(state, { type: "moneyInvalid", field, invalid: true })
  return reducer(reducer(state, onExact(toman)), { type: "moneyInvalid", field, invalid: false })
}

const product = { id: 7, retail_price: 1_000, wholesale_price: 800 }

const TODAY = "2026-10-06"
const NO_METHOD = { kind: "none" }
/** The body of an order with no payment method, built on TODAY. */
const buildOrderBody = (s) => buildWithMethod(s, NO_METHOD, TODAY)

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


// ---------------------------------------------------------------- payment method, fee, paid_date

const zarinpal = { id: 2, name: "Zarinpal", is_active: 1 }
const digipay = { id: 3, name: "Digipay", is_active: 1 }
const oldCard = { id: 4, name: "Old card", is_active: 0 }
const METHODS = [zarinpal, digipay, oldCard]
const asMethod = (m) => ({ kind: "method", method: m })

test("resolveMethod: explicit choice, channel default, none", () => {
  assert.deepEqual(resolveMethod({ kind: "method", id: 3 }, 2, METHODS), asMethod(digipay))
  assert.deepEqual(resolveMethod({ kind: "default" }, 2, METHODS), asMethod(zarinpal))
  assert.deepEqual(resolveMethod({ kind: "default" }, null, METHODS), { kind: "none" })
  assert.deepEqual(resolveMethod({ kind: "none" }, 2, METHODS), { kind: "none" })
})

test("resolveMethod: an inactive default or choice blocks; unloaded methods block when one is needed", () => {
  assert.deepEqual(resolveMethod({ kind: "default" }, 4, METHODS), { kind: "inactive", method: oldCard, isDefault: true })
  assert.deepEqual(resolveMethod({ kind: "method", id: 4 }, null, METHODS), { kind: "inactive", method: oldCard, isDefault: false })
  // The methods request failed and the channel has a default: never fall back to "no method".
  assert.deepEqual(resolveMethod({ kind: "default" }, 2, null), { kind: "unavailable", id: 2 })
  assert.deepEqual(resolveMethod({ kind: "default" }, 99, METHODS), { kind: "unavailable", id: 99 })
  // No default on the channel: the sale goes ahead without a method (manual fee, as before).
  assert.deepEqual(resolveMethod({ kind: "default" }, null, null), { kind: "none" })
})

test("buildOrderBody refuses an unresolved method", () => {
  const s = saleWithOneLine()
  assert.throws(() => buildWithMethod(s, { kind: "inactive", method: oldCard, isDefault: true }, TODAY))
  assert.throws(() => buildWithMethod(s, { kind: "unavailable", id: 2 }, TODAY))
})

test("fee: automatic with a method sends null; manual sends the integer, 0 included", () => {
  let s = saleWithOneLine()
  let body = buildWithMethod(s, asMethod(zarinpal), TODAY)
  assert.equal(body.payment_method_id, 2)
  assert.equal(body.transaction_fee, null)

  s = reducer(s, { type: "feeMode", mode: "manual", fee: 1500 })
  body = buildWithMethod(s, asMethod(zarinpal), TODAY)
  assert.equal(body.transaction_fee, 1500)

  s = reducer(s, { type: "fee", value: 0 })
  assert.equal(buildWithMethod(s, asMethod(zarinpal), TODAY).transaction_fee, 0)

  // Back to automatic.
  s = reducer(s, { type: "feeMode", mode: "auto" })
  assert.equal(buildWithMethod(s, asMethod(zarinpal), TODAY).transaction_fee, null)
})

test("fee: with no method the typed fee is sent exactly as before", () => {
  let s = saleWithOneLine()
  let body = buildOrderBody(s)
  assert.equal(body.payment_method_id, null)
  assert.equal(body.transaction_fee, 0)
  s = reducer(s, { type: "fee", value: 2500 })
  assert.equal(buildOrderBody(s).transaction_fee, 2500)
})

test("picking another method or another channel returns the fee to automatic", () => {
  let s = reducer(saleWithOneLine(), { type: "feeMode", mode: "manual", fee: 900 })
  assert.equal(reducer(s, { type: "payment", choice: { kind: "method", id: 3 } }).feeMode, "auto")
  const products = new Map([[product.id, product]])
  const moved = reducer(s, { type: "channel", channel: "INSTAGRAM", products })
  assert.equal(moved.feeMode, "auto")
  assert.deepEqual(moved.payment, { kind: "default" })
})

test("payment_reference is trimmed, empty is null", () => {
  let s = saleWithOneLine()
  assert.equal(buildOrderBody(s).payment_reference, null)
  s = reducer(s, { type: "reference", value: "  TRX-42 " })
  assert.equal(buildOrderBody(s).payment_reference, "TRX-42")
})

test("paid_date: omitted only when the order is dated today and paid today", () => {
  const s = saleWithOneLine() // COMPLETED, no order date, no picked payment day
  const body = buildOrderBody(s)
  assert.equal("paid_date" in body, false)
  assert.equal("order_date" in body, false)
})

test("paid_date: a picked day is sent explicitly", () => {
  const s = reducer(saleWithOneLine(), { type: "paidDate", value: "2026-10-01" })
  assert.equal(buildOrderBody(s).paid_date, "2026-10-01")
  // Picking today again: back to omitted.
  assert.equal("paid_date" in buildOrderBody(reducer(s, { type: "paidDate", value: TODAY })), false)
})

test("paid_date: a backdated order sends its own day (what the form shows and the server stores)", () => {
  const s = { ...saleWithOneLine(), orderDate: "2026-09-20" }
  const body = buildOrderBody(s)
  assert.equal(body.order_date, "2026-09-20")
  assert.equal(body.paid_date, "2026-09-20")
  // A backdated order paid on another day: that day.
  assert.equal(buildOrderBody(reducer(s, { type: "paidDate", value: "2026-09-25" })).paid_date, "2026-09-25")
  // A backdated order paid today: today must be sent, or the server would store the order's day.
  assert.equal(buildOrderBody(reducer(s, { type: "paidDate", value: TODAY })).paid_date, TODAY)
})

test("paid_date: never for DRAFT or PENDING; choosing them clears a picked day", () => {
  for (const status of ["DRAFT", "PENDING"]) {
    const picked = reducer(saleWithOneLine(), { type: "paidDate", value: "2026-10-01" })
    const s = reducer(picked, { type: "status", status })
    assert.equal(s.paidDate, null)
    assert.equal("paid_date" in buildOrderBody(s), false)
    // Even a backdated draft never carries a payment day.
    assert.equal("paid_date" in buildOrderBody({ ...s, orderDate: "2026-09-20" }), false)
  }
  const paid = reducer(reducer(saleWithOneLine(), { type: "paidDate", value: "2026-10-01" }), { type: "status", status: "PAID" })
  assert.equal(buildOrderBody(paid).paid_date, "2026-10-01")
})
