// Run with `npm test`. The record-sale «تاریخ فروش» field: reducer action,
// paid-day reset, request body, error classification, the 31-day rule.
import { test } from "node:test"
import assert from "node:assert/strict"
import { buildOrderBody, initialState, reducer } from "../components/record-sale/state.ts"
import { daysBetween, isFutureOrderDateError, isStaleSaleDay } from "./sale-date.ts"

const TODAY = "2026-10-06"
const NONE = { kind: "none" }
const product = { id: 7, retail_price: 10_000, wholesale_price: 8_000 }
const sale = () => reducer(initialState(1), { type: "pickProduct", key: 1, product })
const pick = (s, value) => reducer(s, { type: "orderDate", value, today: TODAY })

test("orderDate action: a past day is kept, today goes back to null", () => {
  const past = pick(sale(), "2026-09-20")
  assert.equal(past.orderDate, "2026-09-20")
  assert.equal(pick(past, TODAY).orderDate, null)
})

test("orderDate action: moving the sale past a picked payment day resets it to follow the order", () => {
  const paid = reducer(pick(sale(), "2026-09-20"), { type: "paidDate", value: "2026-09-25" })
  assert.equal(pick(paid, "2026-09-28").paidDate, null)
  assert.equal(pick(paid, TODAY).paidDate, null)
})

test("orderDate action: a sale day on or before the picked payment day keeps it", () => {
  const paid = reducer(pick(sale(), "2026-09-20"), { type: "paidDate", value: "2026-09-25" })
  assert.equal(pick(paid, "2026-09-22").paidDate, "2026-09-25")
  assert.equal(pick(paid, "2026-09-25").paidDate, "2026-09-25")
  assert.equal(reducer(sale(), { type: "paidDate", value: null }).paidDate, null)
})

test("body: a backdated sale sends order_date and its own paid_date", () => {
  const body = buildOrderBody(pick(sale(), "2026-09-20"), NONE, TODAY)
  assert.equal(body.order_date, "2026-09-20")
  assert.equal(body.paid_date, "2026-09-20")
})

test("body: a sale dated today sends neither order_date nor paid_date", () => {
  const body = buildOrderBody(pick(pick(sale(), "2026-09-20"), TODAY), NONE, TODAY)
  assert.equal("order_date" in body, false)
  assert.equal("paid_date" in body, false)
})

test("errors: DATE_IN_FUTURE on order_date is the sale-day error", () => {
  assert.equal(isFutureOrderDateError({ code: "DATE_IN_FUTURE", field: "order_date" }), true)
})

test("errors: DATE_IN_FUTURE on paid_date or another code is not", () => {
  assert.equal(isFutureOrderDateError({ code: "DATE_IN_FUTURE", field: "paid_date" }), false)
  assert.equal(isFutureOrderDateError({ code: "MONTH_ALREADY_SETTLED", field: "order_date" }), false)
})

test("31-day rule: exactly 31 days back asks nothing", () => {
  assert.equal(daysBetween("2026-09-05", TODAY), 31)
  assert.equal(isStaleSaleDay("2026-09-05", TODAY), false)
  assert.equal(isStaleSaleDay(TODAY, TODAY), false)
})

test("31-day rule: 32 days back asks for a confirmation (also across a year end)", () => {
  assert.equal(isStaleSaleDay("2026-09-04", TODAY), true)
  assert.equal(isStaleSaleDay("2025-12-31", "2026-01-31"), false)
  assert.equal(isStaleSaleDay("2025-12-30", "2026-01-31"), true)
})
