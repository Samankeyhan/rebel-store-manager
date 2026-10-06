// Run with `npm test`. "Today" is the store's day (settings.timezone), not the
// process's / browser's. Pin the process zone to one far from Tehran so a
// helper that used the local day would visibly fail.
process.env.TZ = "Pacific/Kiritimati" // UTC+14

import { test } from "node:test"
import assert from "node:assert/strict"
import { DEFAULT_TZ, storeToday } from "./store-day.ts"
import { initialState, paidDateForBody, reducer, buildOrderBody } from "../components/record-sale/state.ts"

// 2026-10-05 21:00 UTC = 2026-10-06 00:30 in Tehran = 2026-10-06 11:00 in Kiritimati
// = 2026-10-05 14:00 in Los Angeles.
const NOW = new Date(Date.UTC(2026, 9, 5, 21, 0, 0))

test("the process zone really is different here", () => {
  assert.equal(new Date(NOW).getDate(), 6) // local (Kiritimati) day
  assert.equal(NOW.getUTCDate(), 5)
})

test("storeToday uses the store zone, not the process zone", () => {
  assert.equal(storeToday(NOW, "Asia/Tehran"), "2026-10-06")
  assert.equal(storeToday(NOW, "America/Los_Angeles"), "2026-10-05")
  assert.equal(storeToday(NOW, "UTC"), "2026-10-05")
})

test("a missing or invalid zone falls back to Asia/Tehran", () => {
  assert.equal(DEFAULT_TZ, "Asia/Tehran")
  for (const tz of [null, undefined, "", "Not/AZone"]) assert.equal(storeToday(NOW, tz), "2026-10-06", String(tz))
})

test("a store in Los Angeles: the order dated today is paid today, so paid_date is omitted", () => {
  const product = { id: 7, retail_price: 1_000, wholesale_price: 800 }
  const s = reducer(initialState(1), { type: "pickProduct", key: 1, product })
  const today = storeToday(NOW, "America/Los_Angeles") // 2026-10-05, while the process says the 6th
  assert.equal(paidDateForBody(s, today), undefined)
  // Picking the 6th there is a future day for the store; it is sent as picked (the API refuses it, 422).
  const picked = reducer(s, { type: "paidDate", value: "2026-10-06" })
  assert.equal(buildOrderBody(picked, { kind: "none" }, today).paid_date, "2026-10-06")
  // In Tehran the 6th is today: omitted.
  assert.equal(paidDateForBody(picked, storeToday(NOW, "Asia/Tehran")), undefined)
})
