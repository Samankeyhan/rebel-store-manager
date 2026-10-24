// Run with `npm test` (node --test; Node 22 strips the .ts types itself).
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  allocatedTotal,
  allocationProblem,
  allocationsBody,
  classifyPayablesError,
  matchesPayFilter,
  parsePayFilter,
  purchasePaymentBody,
  purchasePaymentProblem,
} from "./payables.ts"

test("parsePayFilter / matchesPayFilter: only the three statuses, none = all", () => {
  assert.equal(parsePayFilter("unpaid"), "unpaid")
  assert.equal(parsePayFilter("PAID"), null)
  assert.equal(parsePayFilter(null), null)
  assert.equal(matchesPayFilter("PARTIAL", "partial"), true)
  assert.equal(matchesPayFilter("PAID", "unpaid"), false)
  assert.equal(matchesPayFilter("UNPAID", null), true)
})

test("purchasePaymentProblem mirrors check_purchase_payment", () => {
  assert.equal(purchasePaymentProblem("FULL", false, 1000, null), null)
  assert.equal(purchasePaymentProblem("NONE", false, 1000, null), "supplier")
  assert.equal(purchasePaymentProblem("PARTIAL", false, 1000, 10), "supplier")
  assert.equal(purchasePaymentProblem("NONE", true, 1000, null), null)
  assert.equal(purchasePaymentProblem("PARTIAL", true, 1000, 999), null)
  assert.equal(purchasePaymentProblem("PARTIAL", true, 1000, 1000), "partial_amount") // the whole total is FULL
  assert.equal(purchasePaymentProblem("PARTIAL", true, 1000, 0), "partial_amount")
  assert.equal(purchasePaymentProblem("PARTIAL", true, 1000, null), "partial_amount") // inexact money text
})

test("purchasePaymentBody: amount only for PARTIAL, no reference on credit", () => {
  assert.deepEqual(purchasePaymentBody("FULL", 500, "CARD", " R-1 "), { mode: "FULL", amount: null, method: "CARD", reference: "R-1" })
  assert.deepEqual(purchasePaymentBody("PARTIAL", 500, "CASH", ""), { mode: "PARTIAL", amount: 500, method: "CASH", reference: null })
  assert.deepEqual(purchasePaymentBody("NONE", 500, "CASH", "x"), { mode: "NONE", amount: null, method: "CASH", reference: null })
})

test("allocatedTotal: exact integer Rial; an inexact line or an unsafe sum is null", () => {
  assert.equal(allocatedTotal([]), 0)
  assert.equal(allocatedTotal([{ key: "a", outstanding: 9, amount: 4 }, { key: "b", outstanding: 9, amount: 5 }]), 9)
  assert.equal(allocatedTotal([{ key: "a", outstanding: 9, amount: null }]), null)
  assert.equal(
    allocatedTotal([
      { key: "a", outstanding: Number.MAX_SAFE_INTEGER, amount: Number.MAX_SAFE_INTEGER },
      { key: "b", outstanding: 9, amount: 1 },
    ]),
    null
  )
})

test("allocationProblem: amount, over a line, nothing paid, sum mismatch, fine", () => {
  const line = (key, outstanding, amount) => ({ key, outstanding, amount })
  assert.deepEqual(allocationProblem(null, [line("a", 5, 5)]), { kind: "amount" })
  assert.deepEqual(allocationProblem(0, [line("a", 5, 0)]), { kind: "amount" })
  assert.deepEqual(allocationProblem(6, [line("a", 5, 6)]), { kind: "over", key: "a" })
  assert.deepEqual(allocationProblem(6, [line("a", 5, 0), line("b", 5, 0)]), { kind: "empty" })
  assert.deepEqual(allocationProblem(6, [line("a", 5, 5)]), { kind: "mismatch", allocated: 5 })
  assert.equal(allocationProblem(6, [line("a", 5, 5), line("b", 5, 1)]), null)
  assert.deepEqual(
    allocationsBody([
      { key: "a", outstanding: 5, amount: 5, purchase_kind: "MATERIAL", purchase_id: 1 },
      { key: "b", outstanding: 5, amount: 0, purchase_kind: "PRODUCT", purchase_id: 2 },
    ]),
    [{ purchase_kind: "MATERIAL", purchase_id: 1, amount: 5 }]
  )
})

test("classifyPayablesError reads code and details, never the message", () => {
  const e = (code, details = {}) => ({ status: 409, code, details, message: "ignored" })
  assert.deepEqual(classifyPayablesError(e("SUPPLIER_REQUIRED_FOR_CREDIT")), { kind: "supplier_required" })
  assert.deepEqual(classifyPayablesError(e("SUPPLIER_PAYMENT_EXCEEDS_DUE", { purchase_kind: "MATERIAL", purchase_id: 3, outstanding: 70 })), {
    kind: "exceeds_due",
    purchaseKind: "MATERIAL",
    purchaseId: 3,
    outstanding: 70,
  })
  assert.deepEqual(classifyPayablesError(e("SUPPLIER_PAYMENT_EXCEEDS_BALANCE", { supplier_id: 1, outstanding: 9 })), {
    kind: "exceeds_balance",
    outstanding: 9,
  })
  assert.deepEqual(classifyPayablesError(e("SUPPLIER_PAYMENT_BEFORE_PURCHASE", { purchase_date: "2026-05-01" })), {
    kind: "before_purchase",
    purchaseDate: "2026-05-01",
  })
  assert.deepEqual(classifyPayablesError(e("SUPPLIER_PAYMENT_ALLOCATION_MISMATCH", { amount: 5, allocated: 4 })), {
    kind: "allocation_mismatch",
    allocated: 4,
  })
  assert.deepEqual(classifyPayablesError(e("CONFLICT")), { kind: "other" })
})
