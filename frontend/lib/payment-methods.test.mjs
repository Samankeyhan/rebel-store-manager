// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import { BPS_MAX, capError, capForSave, classifyPaymentError, formatPercent, parsePercent } from "./payment-methods.ts"
import { feeText, paymentErrorText, ruleText } from "../components/payment-methods/copy.ts"
import { formatMoney, parseMoneyInput, setCurrency } from "./money.ts"

const ok = (bps) => ({ ok: true, bps })

test("parsePercent: Latin, Persian and Arabic-Indic digits, . or ٫", () => {
  assert.deepEqual(parsePercent("1.5"), ok(150))
  assert.deepEqual(parsePercent("۱٫۵"), ok(150))
  assert.deepEqual(parsePercent("١٫٥"), ok(150))
  assert.deepEqual(parsePercent("۱.۵"), ok(150))
  assert.deepEqual(parsePercent("1٫25"), ok(125))
  assert.deepEqual(parsePercent("12"), ok(1200))
  assert.deepEqual(parsePercent("0.05"), ok(5))
  assert.deepEqual(parsePercent(".5"), ok(50))
  assert.deepEqual(parsePercent("3."), ok(300))
  assert.deepEqual(parsePercent(" 2.5 ٪"), ok(250))
  assert.deepEqual(parsePercent("2.5%"), ok(250))
  assert.deepEqual(parsePercent("007.10"), ok(710))
})

test("parsePercent: empty is 0, bounds 0..100%", () => {
  assert.deepEqual(parsePercent(""), ok(0))
  assert.deepEqual(parsePercent("0"), ok(0))
  assert.deepEqual(parsePercent("100"), ok(BPS_MAX))
  assert.deepEqual(parsePercent("100.00"), ok(BPS_MAX))
  assert.deepEqual(parsePercent("100.01"), { ok: false, error: "range" })
  assert.deepEqual(parsePercent("1000"), { ok: false, error: "range" })
})

test("parsePercent: a third decimal blocks, junk is a format error", () => {
  assert.deepEqual(parsePercent("12.345"), { ok: false, error: "decimals" })
  assert.deepEqual(parsePercent("۰٫۰۰۵"), { ok: false, error: "decimals" })
  for (const bad of [".", "-1", "1.2.3", "abc", "1,5", "1 5"]) {
    assert.deepEqual(parsePercent(bad), { ok: false, error: "format" }, bad)
  }
})

test("parsePercent never goes through a float: 0.07 and 1.15 are exact", () => {
  assert.deepEqual(parsePercent("0.07"), ok(7))
  assert.deepEqual(parsePercent("1.15"), ok(115))
  assert.deepEqual(parsePercent("2.29"), ok(229))
  assert.deepEqual(parsePercent("4.35"), ok(435))
})

test("formatPercent", () => {
  assert.equal(formatPercent(150), "۱٫۵")
  assert.equal(formatPercent(5), "۰٫۰۵")
  assert.equal(formatPercent(1200), "۱۲")
  assert.equal(formatPercent(0), "۰")
  assert.equal(formatPercent(10000), "۱۰۰")
  assert.equal(formatPercent(125), "۱٫۲۵")
})

test("formatPercent → parsePercent round-trips every basis point", () => {
  for (let bps = 0; bps <= BPS_MAX; bps++) {
    assert.deepEqual(parsePercent(formatPercent(bps)), ok(bps), String(bps))
  }
})

test("ruleText", () => {
  assert.equal(ruleText("IMMEDIATE", null), "همان روز")
  assert.equal(ruleText("DAYS_AFTER", 1), "۱ روز بعد از پرداخت")
  assert.equal(ruleText("DAY_OF_NEXT_MONTH", 7), "روز ۷ ماه بعد (شمسی)")
})

test("feeText", () => {
  // fee_fixed is integer Rial.
  setCurrency("TOMAN")
  assert.equal(feeText(150, 5_000, null), `۱٫۵٪ + ${formatMoney(5_000)}`)
  assert.match(formatMoney(5_000), /^۵۰۰\s+تومان$/u)
  assert.match(feeText(0, 5_005, null), /^۵۰۰٫۵\s+تومان$/u)
  assert.equal(feeText(150, 0, null), "۱٫۵٪")
  assert.equal(feeText(0, 5_000, null), formatMoney(5_000))
  assert.equal(feeText(0, 0, null), "بدون کارمزد")
  setCurrency("RIAL")
  assert.equal(feeText(0, 5_000, null), formatMoney(5_000))
  assert.match(feeText(0, 5_000, null), /^۵٬۰۰۰\s+ریال$/u)
  assert.match(feeText(0, 5_005, null), /^۵٬۰۰۵\s+ریال$/u)
  setCurrency("TOMAN")
})

test("feeText with a cap on the percentage part", () => {
  setCurrency("TOMAN")
  // Zarinpal: 0.5% up to 16,000 Toman (160,000 Rial) + 500 Toman (5,000 Rial).
  assert.match(feeText(50, 5_000, 160_000), /^۰٫۵٪ تا سقف ۱۶٬۰۰۰\s+تومان \+ ۵۰۰\s+تومان$/u)
  assert.match(feeText(50, 0, 160_000), /^۰٫۵٪ تا سقف ۱۶٬۰۰۰\s+تومان$/u)
  assert.match(feeText(50, 0, 160_005), /^۰٫۵٪ تا سقف ۱۶٬۰۰۰٫۵\s+تومان$/u)
  assert.equal(feeText(50, 5_000, null), `۰٫۵٪ + ${formatMoney(5_000)}`)
  // A cap never shows without a percentage (the backend refuses one anyway).
  assert.equal(feeText(0, 5_000, 160_000), formatMoney(5_000))
  assert.equal(feeText(0, 0, 160_000), "بدون کارمزد")
  setCurrency("RIAL")
  assert.match(feeText(50, 5_000, 160_000), /^۰٫۵٪ تا سقف ۱۶۰٬۰۰۰\s+ریال \+ ۵٬۰۰۰\s+ریال$/u)
  assert.match(feeText(50, 0, 1), /^۰٫۵٪ تا سقف ۱\s+ریال$/u)
  setCurrency("TOMAN")
})

test("capError: empty = no cap, inexact blocks, 0 is refused; ignored without a percentage", () => {
  assert.equal(capError(50, undefined), null)
  assert.equal(capError(50, 160_000), null)
  assert.equal(capError(50, 1), null)
  assert.equal(capError(50, 9_007_199_254_740_991), null)
  assert.equal(capError(50, null), "inexact")
  assert.equal(capError(50, 0), "min")
  assert.equal(capError(50, -1), "min")
  assert.equal(capError(50, 1.5), "min")
  assert.equal(capError(50, 9_007_199_254_740_992), "min")
  // The field is off while the percentage is 0, empty or invalid.
  for (const bps of [0, null]) {
    for (const cap of [undefined, null, 0, 160_000]) assert.equal(capError(bps, cap), null, `${bps} ${cap}`)
  }
})

test("capForSave: the fee_cap the drawer sends", () => {
  assert.equal(capForSave(50, 160_000), 160_000)
  assert.equal(capForSave(50, undefined), null) // empty = no cap
  assert.equal(capForSave(0, 160_000), null) // percentage emptied: the cap is cleared with it
  assert.equal(capForSave(null, 160_000), null)
  assert.equal(capForSave(10_000, 9_007_199_254_740_991), 9_007_199_254_740_991)
})

test("the cap field's typed text → Rial (MoneyInput with allowEmpty)", () => {
  const cap = (text, c) => parseMoneyInput(text, c, true).rial
  assert.equal(cap("16000", "TOMAN"), 160_000)
  assert.equal(cap("۱۶٬۰۰۰", "TOMAN"), 160_000)
  assert.equal(cap("16000.5", "TOMAN"), 160_005)
  assert.equal(cap("16000.55", "TOMAN"), null) // two Toman decimals: not exact
  assert.equal(cap("160000", "RIAL"), 160_000)
  assert.equal(cap("1.5", "RIAL"), null)
  assert.equal(cap("", "TOMAN"), undefined) // empty = no cap
  assert.equal(cap("", "RIAL"), undefined)
  assert.equal(capError(50, cap("0", "TOMAN")), "min")
  assert.equal(capError(50, cap("16000.55", "TOMAN")), "inexact")
  assert.equal(capForSave(50, cap("", "TOMAN")), null)
})

// The exact texts db/ raises (db/orders.py, db/payment_methods.py).
const CASES = [
  [{ status: 409, message: "Digipay's month 1405/06 is already settled (settlement #2); choose a paid date in an open month." },
    { kind: "closedMonth", year: 1405, month: 6 }],
  [{ status: 409, message: "Order #4 is part of settlement #3; its paid date can no longer change." },
    { kind: "settled", settlementId: 3 }],
  [{ status: 409, message: "Order #5 is PENDING, not paid; it has no paid date to change." }, { kind: "unpaid" }],
  [{ status: 409, message: "Cannot change the settlement rule of 'Zarinpal': 1 paid order is still pending settlement. Deactivate this method and create a new one with the new rule." },
    { kind: "rulePending", count: 1 }],
  [{ status: 409, message: "Cannot change the settlement rule of 'Zarinpal': 12 paid orders are still pending settlement. Deactivate this method and create a new one with the new rule." },
    { kind: "rulePending", count: 12 }],
  [{ status: 409, message: "A payment method named 'Digipay' already exists" }, { kind: "duplicateName" }],
  [{ status: 422, field: "paid_date", message: "paid_date 2026-10-07 is in the future (today is 2026-10-06)" }, { kind: "futurePaidDate" }],
  [{ status: 422, field: "paid_date", message: "paid_date can only be given for a PAID or COMPLETED order, not PENDING" }, { kind: "paidDateNotAllowed" }],
  [{ status: 422, field: "payment_method_id", message: "Payment method 'Digipay' is not active. Choose another method or update the channel's default payment method." },
    { kind: "inactiveMethod" }],
  [{ status: 422, field: "default_payment_method_id", message: "Payment method 'Card' is not active and cannot be a channel's default payment method" },
    { kind: "inactiveDefault" }],
  [{ status: 409, message: "Cannot transition order #1 from COMPLETED to PAID" }, null],
  [{ status: 422, field: "unit_cost", message: "no cost" }, null],
]

test("classifyPaymentError recognises every payment error the backend raises", () => {
  for (const [error, expected] of CASES) assert.deepEqual(classifyPaymentError(error), expected, error.message)
})

test("paymentErrorText", () => {
  assert.equal(
    paymentErrorText({ kind: "closedMonth", year: 1405, month: 6 }),
    "ماه ۱۴۰۵/۰۶ این روش پرداخت قبلاً تسویه شده؛ تاریخ پرداخت را در ماهی باز انتخاب کنید."
  )
  assert.match(paymentErrorText({ kind: "rulePending", count: 3 }), /^۳ سفارش/)
  assert.match(paymentErrorText({ kind: "inactiveMethod" }, "Digipay"), /«Digipay»/)
})
