// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  attachReferences,
  classifySettlementError,
  differenceKind,
  groupTitle,
  isMonthGroup,
  jalaliMonthTitle,
  overdueOrderCount,
  previewDifference,
  referenceMap,
  selectedExpected,
  selectionTotal,
  settlementErrorField,
  settlementErrorRefreshes,
  settlementPatch,
} from "./settlements.ts"
import { differenceText, settlementErrorText, signedMoney } from "../components/settlements/copy.ts"
import { formatMoney, setCurrency } from "./money.ts"

const LATIN = /[0-9]/

test("selectionTotal: exact integer Rial, negatives, empty, unsafe", () => {
  assert.equal(selectionTotal([12345, 7]), 12352)
  assert.equal(selectionTotal([-1500, 1000]), -500)
  assert.equal(selectionTotal([]), 0)
  assert.equal(selectionTotal([Number.MAX_SAFE_INTEGER, 1]), null)
  assert.equal(selectionTotal([1.5, 1]), null)
  assert.equal(selectionTotal([Number.MAX_SAFE_INTEGER - 1, 1]), Number.MAX_SAFE_INTEGER)
})

test("selectedExpected: only the chosen orders", () => {
  const orders = [
    { id: 1, expected_amount: 12345 },
    { id: 2, expected_amount: 7 },
    { id: 3, expected_amount: 1000 },
  ]
  assert.equal(selectedExpected(orders, new Set([1, 2])), 12352)
  assert.equal(selectedExpected(orders, new Set()), 0)
})

test("previewDifference: received − expected, as db/settlements.py", () => {
  assert.equal(previewDifference(13000, 12352), 648)
  assert.equal(previewDifference(12000, 12352), -352)
  assert.equal(previewDifference(12352, 12352), 0)
  // A negative expected amount (fees above the customer total).
  assert.equal(previewDifference(0, -1500), 1500)
  assert.equal(previewDifference(1000, -1500), 2500)
  assert.equal(previewDifference(undefined, 100), null)
  assert.equal(previewDifference(null, 100), null)
  assert.equal(previewDifference(100, null), null)
  assert.equal(previewDifference(Number.MAX_SAFE_INTEGER, -1), null)
})

test("differenceKind and differenceText: positive, negative, zero, both currencies", () => {
  assert.equal(differenceKind(5), "over")
  assert.equal(differenceKind(-5), "under")
  assert.equal(differenceKind(0), "equal")
  try {
    setCurrency("TOMAN")
    assert.ok(formatMoney(6485).startsWith("۶۴۸٫۵") && formatMoney(-3520).includes("−۳۵۲"))
    assert.equal(differenceText(6485), `بیشتر از انتظار دریافت شد ‎+${formatMoney(6485)}`)
    assert.equal(differenceText(-3520), `کمتر از انتظار دریافت شد ${formatMoney(-3520)}`)
    assert.equal(differenceText(0), "برابر با مبلغ مورد انتظار")
    setCurrency("RIAL")
    assert.equal(differenceText(6485), `بیشتر از انتظار دریافت شد ‎+${formatMoney(6485)}`)
    assert.equal(differenceText(-3520), `کمتر از انتظار دریافت شد ${formatMoney(-3520)}`)
    assert.equal(signedMoney(0), formatMoney(0))
    assert.ok(formatMoney(6485).startsWith("۶٬۴۸۵") && formatMoney(-3520).includes("−۳٬۵۲۰"))
    for (const d of [6485, -3520, 0]) assert.ok(!LATIN.test(differenceText(d)), differenceText(d))
  } finally {
    setCurrency("TOMAN")
  }
})

test("overdueOrderCount: overdue date and month groups only", () => {
  const date = (overdue, due, n) => ({ expected_date: "2026-10-01", overdue, due, order_count: n })
  const month = (overdue, n) => ({
    ...date(overdue, overdue, n),
    jalali_year: 1405,
    jalali_month: 6,
    month_first_day: "2026-08-23",
    month_last_day: "2026-09-22",
    can_settle: true,
  })
  assert.equal(overdueOrderCount([date(true, true, 3)]), 3)
  assert.equal(overdueOrderCount([date(false, true, 4)]), 0) // due today, not overdue
  assert.equal(overdueOrderCount([month(true, 2), date(false, false, 5)]), 2)
  assert.equal(overdueOrderCount([date(true, true, 1), month(true, 2), date(false, true, 9)]), 3)
  assert.equal(overdueOrderCount([]), 0)
})

test("groupTitle: month name for a month group, Jalali date for a date group", () => {
  const dateGroup = { expected_date: "2026-10-07", overdue: false, due: false, order_count: 1 }
  const monthGroup = {
    ...dateGroup,
    jalali_year: 1405,
    jalali_month: 7,
    month_first_day: "2026-09-23",
    month_last_day: "2026-10-22",
    can_settle: false,
  }
  assert.equal(isMonthGroup(monthGroup), true)
  assert.equal(isMonthGroup(dateGroup), false)
  assert.equal(groupTitle(monthGroup), "مهر ۱۴۰۵")
  assert.equal(groupTitle(dateGroup), "۱۵ مهر ۱۴۰۵")
})

test("attachReferences: join by id, missing or blank → null", () => {
  const refs = referenceMap([
    { id: 1, payment_reference: " TRX-77 " },
    { id: 2, payment_reference: "" },
    { id: 4, payment_reference: null },
  ])
  const out = attachReferences([{ id: 1, x: "a" }, { id: 2 }, { id: 3 }], refs)
  assert.deepEqual(out, [
    { id: 1, x: "a", payment_reference: "TRX-77" },
    { id: 2, payment_reference: null },
    { id: 3, payment_reference: null },
  ])
  assert.deepEqual(attachReferences([{ id: 9 }], new Map()), [{ id: 9, payment_reference: null }])
})

// The codes and details of db/settlements.py (and FastAPI's strict int refusal); messages are only documentation.
const CASES = [
  [
    { status: 409, code: "SETTLEMENT_MONTH_NOT_ENDED", details: { jalali_year: 1405, jalali_month: 7, month_end: "2026-10-22" }, message: "Month 1405/07 has not ended yet (it ends 2026-10-22); 'Gateway M' settles whole months only." },
    { kind: "monthNotEnded", year: 1405, month: 7, ends: "2026-10-22" },
    "ماه ۱۴۰۵/۰۷ هنوز تمام نشده؛ بعد از ۳۰ مهر ۱۴۰۵ قابل تسویه است.",
  ],
  [
    { status: 409, code: "MONTH_ALREADY_SETTLED", details: { jalali_year: 1405, jalali_month: 6, settlement_id: 12 }, message: "Gateway M's month 1405/06 is already settled (settlement #12)." },
    { kind: "monthSettled", year: 1405, month: 6, settlementId: 12 },
    "ماه ۱۴۰۵/۰۶ این روش قبلاً تسویه شده (تسویه شماره ۱۲).",
  ],
  [
    { status: 409, code: "MONTH_ALREADY_SETTLED", details: { jalali_year: 1405, jalali_month: 6, settlement_id: null }, message: "Gateway M's month 1405/06 is already settled." },
    { kind: "monthSettled", year: 1405, month: 6, settlementId: null },
    "ماه ۱۴۰۵/۰۶ این روش قبلاً تسویه شده.",
  ],
  [
    { status: 409, code: "ORDER_ALREADY_SETTLED", details: { order_id: 31, settlement_id: 4 }, message: "Order #31 is already in settlement #4." },
    { kind: "orderSettled", orderId: 31, settlementId: 4 },
    "سفارش ۳۱ قبلاً در تسویه شماره ۴ ثبت شده.",
  ],
  [
    { status: 409, code: "ORDER_NOT_PAID", details: { order_id: 31, status: "REFUNDED" }, message: "Order #31 is REFUNDED, not paid; it cannot be settled." },
    { kind: "orderNotPaid", orderId: 31 },
    "سفارش ۳۱ دیگر پرداخت‌شده نیست (لغو یا مرجوع شده) و قابل تسویه نیست.",
  ],
  [
    { status: 409, code: "SETTLEMENT_NOTHING_PENDING", details: { jalali_year: 1405, jalali_month: 5 }, message: "Nothing to settle: 'Gateway M' has no pending paid orders in 1405/05." },
    { kind: "nothingPending" },
    "این ماه سفارش در انتظار تسویه‌ای ندارد.",
  ],
  [
    { status: 409, code: "SETTLEMENT_RACED", message: "Some of these orders were settled meanwhile; reload and try again." },
    { kind: "raced" },
    "بعضی از این سفارش‌ها همین حالا تسویه شدند؛ فهرست به‌روز شد، دوباره انتخاب کنید.",
  ],
  [
    { status: 409, code: "SETTLEMENT_CONFLICT", message: "Could not record the settlement: it conflicts with existing data" },
    { kind: "conflict" },
    "ثبت تسویه با داده‌های موجود تداخل دارد؛ صفحه را تازه کنید.",
  ],
  [
    { status: 422, code: "DATE_IN_FUTURE", details: { today: "2026-10-09" }, field: "settled_date", message: "settled_date 2026-10-10 is in the future (today is 2026-10-09)" },
    { kind: "futureDate" },
    "تاریخ تسویه نمی‌تواند بعد از امروز باشد.",
  ],
  [
    {
      status: 422, code: "SETTLEMENT_DATE_BEFORE_MONTH_END", details: { jalali_year: 1405, jalali_month: 6, month_end: "2026-09-22" },
      field: "settled_date",
      message: "settled_date 2026-09-01 must be after the end of month 1405/06 (2026-09-22)",
    },
    { kind: "beforeMonthEnd", year: 1405, month: 6 },
    "تاریخ تسویه باید بعد از پایان ماه ۱۴۰۵/۰۶ باشد.",
  ],
  [
    {
      status: 422, code: "SETTLEMENT_DATE_BEFORE_PAID", details: { latest_paid_date: "2026-10-05" },
      field: "settled_date",
      message: "settled_date 2026-10-01 is before the latest paid date of its orders (2026-10-05)",
    },
    { kind: "beforePaid", date: "2026-10-05" },
    "تاریخ تسویه نمی‌تواند قبل از آخرین تاریخ پرداخت این سفارش‌ها (۱۳ مهر ۱۴۰۵) باشد.",
  ],
  [
    { status: 422, code: "VALIDATION_FAILED", field: "amount_received", message: "amount_received must be >= 0, got -5" },
    { kind: "badAmount" },
    "مبلغ دریافتی باید عددی صحیح و نامنفی باشد.",
  ],
  [
    { status: 422, field: "amount_received", message: "Input should be a valid integer" },
    { kind: "badAmount" },
    "مبلغ دریافتی باید عددی صحیح و نامنفی باشد.",
  ],
  [
    { status: 422, code: "SETTLEMENT_ORDER_WRONG_METHOD", details: { order_id: 8 }, field: "order_ids", message: "Order #8 was not paid with 'Card'" },
    { kind: "wrongMethod", orderId: 8 },
    "سفارش ۸ با این روش پرداخت نشده.",
  ],
  [
    { status: 422, code: "VALIDATION_FAILED", field: "order_ids", message: "Order #999 does not exist" },
    { kind: "badSelection" },
    "انتخاب سفارش‌ها معتبر نیست؛ صفحه را تازه کنید.",
  ],
  [{ status: 422, code: "VALIDATION_FAILED", field: "order_ids", message: "order_ids contains duplicates" }, { kind: "badSelection" }, null],
  [
    { status: 422, code: "VALIDATION_FAILED", field: "order_ids", message: "order_ids is required: choose at least one pending order to settle" },
    { kind: "badSelection" },
    null,
  ],
  [
    {
      status: 422, code: "SETTLEMENT_WHOLE_MONTHS_ONLY",
      field: "order_ids",
      message: "'Gateway M' settles whole months only; give jalali_year and jalali_month, not order_ids",
    },
    { kind: "wrongShape" },
    "این روش فقط ماه کامل تسویه می‌کند.",
  ],
  [
    {
      status: 422, code: "SETTLEMENT_NOT_MONTHLY",
      field: "jalali_year",
      message: "jalali_year applies only to a method that settles whole months; 'Card' settles chosen orders",
    },
    { kind: "notMonthly" },
    "این روش ماهانه تسویه نمی‌کند.",
  ],
  [
    { status: 404, code: "NOT_FOUND", message: "Settlement with id 77 does not exist" },
    { kind: "notFound" },
    "این روش پرداخت یا تسویه دیگر وجود ندارد.",
  ],
]

test("classifySettlementError: every backend message, and its Persian text", () => {
  for (const [error, kind, text] of CASES) {
    const c = classifySettlementError(error)
    assert.deepEqual(c, kind, error.message)
    if (text) assert.equal(settlementErrorText(c), text)
    assert.ok(!LATIN.test(settlementErrorText(c)), settlementErrorText(c))
  }
})

test("classifySettlementError: unknown → null", () => {
  assert.equal(classifySettlementError({ status: 0, message: "Backend not reachable at http://x" }), null)
  assert.equal(classifySettlementError({ status: 500, message: "HTTP 500" }), null)
  assert.equal(classifySettlementError({ status: 409, message: "Something else" }), null)
  assert.equal(classifySettlementError({ status: 422, field: "settled_date", message: "bad format" }), null)
  assert.equal(classifySettlementError({ status: 422, field: "note", message: "x" }), null)
  // The old message text alone no longer classifies; a code without its details doesn't either.
  assert.equal(classifySettlementError({ status: 409, message: "Order #31 is already in settlement #4." }), null)
  assert.equal(classifySettlementError({ status: 409, code: "ORDER_ALREADY_SETTLED", details: {}, message: "x" }), null)
  assert.equal(
    classifySettlementError({ status: 422, field: "settled_date", message: "settled_date 2026-10-10 is in the future (today is 2026-10-09)" }),
    null
  )
})

test("settlementErrorField and settlementErrorRefreshes", () => {
  assert.equal(settlementErrorField({ kind: "futureDate" }), "settled_date")
  assert.equal(settlementErrorField({ kind: "beforePaid", date: "2026-01-01" }), "settled_date")
  assert.equal(settlementErrorField({ kind: "beforeMonthEnd", year: 1405, month: 1 }), "settled_date")
  assert.equal(settlementErrorField({ kind: "badAmount" }), "amount_received")
  assert.equal(settlementErrorField({ kind: "raced" }), null)
  for (const kind of ["raced", "orderSettled", "orderNotPaid", "nothingPending", "monthSettled"])
    assert.equal(settlementErrorRefreshes({ kind }), true, kind)
  for (const kind of ["conflict", "futureDate", "badAmount", "monthNotEnded", "notFound"])
    assert.equal(settlementErrorRefreshes({ kind }), false, kind)
})

test("jalaliMonthTitle: a stored Jalali month by name", () => {
  assert.equal(jalaliMonthTitle(1405, 7), "مهر ۱۴۰۵")
  assert.equal(jalaliMonthTitle(1405, 12), "اسفند ۱۴۰۵")
  assert.equal(jalaliMonthTitle(1404, 1), "فروردین ۱۴۰۴")
})

test("settlementPatch: only changed fields; an emptied note clears", () => {
  const original = { amount_received: 12345, settled_date: "2026-10-01", note: "bank" }
  assert.deepEqual(settlementPatch(original, { amount: 12345, date: "2026-10-01", note: " bank " }), {})
  assert.deepEqual(settlementPatch(original, { amount: 12000, date: "2026-10-01", note: "bank" }), { amount_received: 12000 })
  assert.deepEqual(settlementPatch(original, { amount: 12345, date: "2026-10-02", note: "bank" }), { settled_date: "2026-10-02" })
  assert.deepEqual(settlementPatch(original, { amount: 12345, date: "2026-10-01", note: "  " }), { note: null })
  assert.deepEqual(settlementPatch({ ...original, note: null }, { amount: 0, date: "2026-10-01", note: "x" }), {
    amount_received: 0,
    note: "x",
  })
  assert.deepEqual(settlementPatch({ ...original, note: null }, { amount: 12345, date: "2026-10-01", note: "" }), {})
})
