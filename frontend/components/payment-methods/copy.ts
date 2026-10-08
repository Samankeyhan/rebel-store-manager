/**
 * Payment-method copy shared by Settings, Record Sale and Orders. // NEW file
 * Relative imports only, so lib/payment-methods.test.mjs can load it.
 */

import { formatMoney } from "../../lib/money.ts"
import { formatPercent, type PaymentError, type SettlementRule } from "../../lib/payment-methods.ts"
import { formatNumber, toPersianDigits } from "../../lib/persian-numbers.ts"

const fa = formatNumber

/** The rule in words, never a computed date: «همان روز», «۱ روز بعد از پرداخت», «روز ۷ ماه بعد (شمسی)». */
export function ruleText(rule: SettlementRule | string, days: number | null): string {
  if (rule === "DAYS_AFTER") return `${fa(days ?? 0)} روز بعد از پرداخت` // NEW
  if (rule === "DAY_OF_NEXT_MONTH") return `روز ${fa(days ?? 0)} ماه بعد (شمسی)` // NEW
  return "همان روز" // NEW
}

/**
 * «۱٫۵٪ + ۵۰۰ تومان», «۱٫۵٪», «۵۰۰ تومان», or «بدون کارمزد»; with a cap on the
 * percentage part, «۰٫۵٪ تا سقف ۱۶٬۰۰۰ تومان + ۵۰۰ تومان». feeCap null = no cap.
 */
export function feeText(feeBps: number, feeFixed: number, feeCap: number | null): string {
  const parts: string[] = []
  if (feeBps > 0) {
    const cap = feeCap != null ? ` تا سقف ${formatMoney(feeCap)}` : "" // NEW
    parts.push(`${formatPercent(feeBps)}٪${cap}`)
  }
  if (feeFixed > 0) parts.push(formatMoney(feeFixed))
  return parts.length ? parts.join(" + ") : PM.noFee
}

const monthLabel = (year: number, month: number) => toPersianDigits(`${year}/${String(month).padStart(2, "0")}`)

export const PM = {
  noFee: "بدون کارمزد", // NEW
  noMethod: "بدون روش", // NEW
  noMethodLong: "بدون روش پرداخت", // NEW
  inactive: (name: string) => `${name} (غیرفعال)`, // NEW
  ruleNames: {
    IMMEDIATE: "همان روز", // NEW
    DAYS_AFTER: "چند روز بعد", // NEW
    DAY_OF_NEXT_MONTH: "روز مشخص ماه بعد", // NEW
  } as Record<SettlementRule, string>,
  ruleHelp: {
    IMMEDIATE: "پول همان روز پرداخت به حساب می‌رسد؛ مثل کارت‌به‌کارت.", // NEW
    DAYS_AFTER: "پول چند روز بعد از پرداخت مشتری می‌رسد؛ مثلاً درگاهی که فردا تسویه می‌کند.", // NEW
    DAY_OF_NEXT_MONTH:
      "همه پرداخت‌های یک ماه شمسی یک‌جا، در روز مشخصی از ماه بعد و پس از کسر کارمزد می‌رسد؛ اگر آن ماه کوتاه‌تر باشد، روز آخر ماه.", // NEW
  } as Record<SettlementRule, string>,
  settleLine: (rule: string, days: number | null) => `تسویه: ${ruleText(rule, days)}`, // NEW
  pending: (n: number) => `${fa(n)} سفارش در انتظار تسویه`, // NEW

  // errors (backend messages are English; these are what the owner reads)
  closedMonth: (year: number, month: number) =>
    `ماه ${monthLabel(year, month)} این روش پرداخت قبلاً تسویه شده؛ تاریخ پرداخت را در ماهی باز انتخاب کنید.`, // NEW
  settled: (id: number | null) =>
    id == null
      ? "این سفارش تسویه شده و تاریخ پرداختش دیگر قابل تغییر نیست." // NEW
      : `این سفارش در تسویه شماره ${fa(id)} است و تاریخ پرداختش دیگر قابل تغییر نیست.`, // NEW
  unpaid: "این سفارش هنوز پرداخت نشده؛ تاریخ پرداختی برای تغییر ندارد.", // NEW
  rulePending: (n: number) =>
    `${fa(n)} سفارش این روش هنوز تسویه نشده؛ قاعده تسویه قابل تغییر نیست. برای قاعده جدید، این روش را غیرفعال کنید و روش تازه‌ای بسازید.`, // NEW
  duplicateName: "روش پرداختی با این نام وجود دارد.", // NEW
  futurePaidDate: "تاریخ پرداخت نمی‌تواند بعد از امروز باشد.", // NEW
  paidDateNotAllowed: "تاریخ پرداخت فقط برای سفارشی که پرداخت می‌شود ثبت می‌شود.", // NEW
  inactiveMethod: (name: string | null) =>
    name
      ? `روش پرداخت «${name}» غیرفعال است؛ روش دیگری یا «بدون روش» انتخاب کنید.` // NEW
      : "این روش پرداخت غیرفعال است؛ روش دیگری یا «بدون روش» انتخاب کنید.", // NEW
  inactiveDefault: "این روش پرداخت غیرفعال است و نمی‌تواند پیش‌فرض کانال باشد.", // NEW
  methodGone: "این روش پرداخت دیگر وجود ندارد.", // NEW
  methodsReloaded: "فهرست روش‌های پرداخت دوباره خوانده شد.", // NEW
}

/** The Persian sentence for a classified payment error. */
export function paymentErrorText(e: PaymentError, methodName: string | null = null): string {
  switch (e.kind) {
    case "closedMonth":
      return PM.closedMonth(e.year, e.month)
    case "settled":
      return PM.settled(e.settlementId)
    case "unpaid":
      return PM.unpaid
    case "rulePending":
      return PM.rulePending(e.count)
    case "duplicateName":
      return PM.duplicateName
    case "futurePaidDate":
      return PM.futurePaidDate
    case "paidDateNotAllowed":
      return PM.paidDateNotAllowed
    case "inactiveMethod":
      return PM.inactiveMethod(methodName)
    case "inactiveDefault":
      return PM.inactiveDefault
  }
}
