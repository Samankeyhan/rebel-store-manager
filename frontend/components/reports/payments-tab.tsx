"use client"

import * as React from "react"
import { CreditCard } from "lucide-react"
import { Money } from "@/components/common/money"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { useLoad, type Loader } from "@/components/dashboard/use-dashboard-data"
import { PM } from "@/components/payment-methods/copy"
import { cardClass } from "@/components/record-sale/primitives"
import { getPaymentMethodReport, type PaymentMethodReportRow, type ProfitAndLoss } from "@/lib/api"
import type { SettlementRule } from "@/lib/payment-methods"
import { formatNumber } from "@/lib/persian-numbers"
import { apiRange, periodKey, type ReportPeriod } from "@/lib/report-period"
import { paymentChecks, paymentsIsEmpty } from "@/lib/reports"
import { cn } from "@/lib/utils"
import { CheckLines, pnlChecks } from "./check-line"
import { PAYMENTS_EXPLAIN, R } from "./copy"
import { ReportNote, ScreenLink, SignedMoney } from "./report-bits"

type Row = PaymentMethodReportRow

const methodName = (r: Row) =>
  r.payment_method_id == null ? PM.noMethodLong : r.is_active === 0 ? PM.inactive(r.name ?? "") : (r.name ?? "")
const ruleName = (r: Row) => (r.settlement_rule ? (PM.ruleNames[r.settlement_rule as SettlementRule] ?? R.nil) : R.nil)
/** settlements-page.tsx reads ?method= for its history tab (?tab=history). No date range there. */
const settlementsHref = (r: Row) =>
  r.payment_method_id == null ? null : `/settlements?tab=history&method=${r.payment_method_id}`

const th = "text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:whitespace-nowrap"
const tr = "hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
const foot = "font-bold [&>td]:h-12 [&>td]:bg-surface-2 [&>td]:px-4 [&>td]:whitespace-nowrap"

/**
 * «روش‌های پرداخت»: GET /reports/payment-methods for the period (rules §14
 * «Payment-method report»), one row per method plus «بدون روش پرداخت».
 * Order count, customer total, fees and fees lost on returns are checked
 * against the P&L; the settlement columns go by settled_date and have no
 * P&L counterpart.
 */
export function PaymentsTab({
  period,
  pnl,
  mobile,
}: {
  period: ReportPeriod
  pnl: Loader<ProfitAndLoss>
  mobile: boolean
}) {
  const load = useLoad<Row[]>("REPORTS", periodKey(period), () => getPaymentMethodReport(apiRange(period)))

  if (load.status === "loading") return <LoadingBlock mobile={mobile} label={R.loadingAria} />
  if (load.status === "error")
    return <ErrorBlock title={R.errorTitle} body={R.errorBody} retry={R.retry} onRetry={load.retry} mobile={mobile} />

  const rows = load.data
  const checks = pnlChecks(pnl, (p) => {
    const c = paymentChecks(rows, p)
    return [
      { label: R.checkPayOrders, check: c.orders },
      { label: R.checkPayRevenue, check: c.revenue },
      { label: R.checkPayFees, check: c.fees },
      { label: R.checkPayLostFees, check: c.lostFees },
    ]
  })

  if (paymentsIsEmpty(rows))
    return (
      <div className="flex flex-col gap-3">
        <StateShell icon={CreditCard} mobile={mobile} title={R.paymentsEmptyTitle} body={R.paymentsEmptyBody} />
        <CheckLines checks={checks} />
      </div>
    )

  const sum = (pick: (r: Row) => number) => rows.reduce((t, r) => t + pick(r), 0)
  const key = (r: Row) => String(r.payment_method_id ?? "none")

  const note = (
    <ReportNote>
      <span>{PAYMENTS_EXPLAIN.orders}</span>
      <span>{PAYMENTS_EXPLAIN.feesLost}</span>
      <span>{PAYMENTS_EXPLAIN.pending}</span>
      <span>{PAYMENTS_EXPLAIN.settled}</span>
    </ReportNote>
  )

  if (mobile)
    return (
      <div className="flex flex-col gap-3">
        <ul aria-label={R.tabPayments} className="flex flex-col gap-2">
          {rows.map((r) => (
            <li key={key(r)} className={cn(cardClass, "flex flex-col gap-2 px-3.5 py-3 text-[13px]")}>
              <span className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 flex-col">
                  <b className="truncate text-heading">{methodName(r)}</b>
                  <span className="text-xs text-text-3">{ruleName(r)}</span>
                </span>
                <ScreenLink href={settlementsHref(r)} label={R.openSettlements(methodName(r))} />
              </span>
              <Pairs
                items={[
                  [R.colOrders, <span key="o" className="tabular-nums">{formatNumber(r.order_count)}</span>],
                  [R.customerTotalShort, <Money key="c" value={r.customer_total} />],
                  [R.feesShort, <Money key="f" value={r.transaction_fees} />],
                  [R.feesLostShort, <Money key="l" value={r.fees_lost_on_returns} />],
                ]}
              />
              <Pairs
                items={[
                  [R.pendingShort, <Money key="p" value={r.pending_expected} />],
                  [R.settledExpectedShort, <Money key="e" value={r.settled_expected} />],
                  [R.settledReceivedShort, <Money key="r" value={r.settled_received} />],
                  [R.settleDiffShort, <SignedMoney key="d" value={r.settlement_difference} />],
                ]}
              />
            </li>
          ))}
          <li className={cn(cardClass, "flex flex-col gap-2 bg-surface-2 px-3.5 py-3 text-[13px]")}>
            <b>{R.total}</b>
            <Pairs
              items={[
                [R.colOrders, <span key="o" className="tabular-nums">{formatNumber(sum((r) => r.order_count))}</span>],
                [R.customerTotalShort, <Money key="c" value={sum((r) => r.customer_total)} />],
                [R.feesShort, <Money key="f" value={sum((r) => r.transaction_fees)} />],
                [R.feesLostShort, <Money key="l" value={sum((r) => r.fees_lost_on_returns)} />],
              ]}
            />
          </li>
        </ul>
        <CheckLines checks={checks} />
        {note}
      </div>
    )

  return (
    <div className="flex flex-col gap-4">
      <section aria-labelledby="pay-orders" className={cn(cardClass, "overflow-hidden")}>
        <div className="border-b border-border px-5 py-4">
          <h2 id="pay-orders" className="text-[15px] font-bold text-heading">
            {R.paymentsOrdersTitle}
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className={th}>
                <th scope="col" className="w-full text-start">
                  {R.colMethod}
                </th>
                <th scope="col" className="text-start">
                  {R.colRule}
                </th>
                <th scope="col" className="text-end">
                  {R.colOrders}
                </th>
                <th scope="col" className="text-end">
                  {R.colCustomerTotal}
                </th>
                <th scope="col" className="text-end">
                  {R.colFees}
                </th>
                <th scope="col" className="text-end">
                  {R.colFeesLost}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={key(r)} className={tr}>
                  <td>
                    <span className="flex items-center gap-1">
                      <span className={cn("font-semibold", r.payment_method_id == null && "text-text-2")}>{methodName(r)}</span>
                      <ScreenLink href={settlementsHref(r)} label={R.openSettlements(methodName(r))} />
                    </span>
                  </td>
                  <td className="text-text-2">{ruleName(r)}</td>
                  <td className="text-end tabular-nums">{formatNumber(r.order_count)}</td>
                  <td className="text-end">
                    <Money value={r.customer_total} />
                  </td>
                  <td className="text-end">
                    <Money value={r.transaction_fees} />
                  </td>
                  <td className="text-end">
                    <Money value={r.fees_lost_on_returns} />
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className={foot}>
                <td>{R.total}</td>
                <td />
                <td className="text-end tabular-nums">{formatNumber(sum((r) => r.order_count))}</td>
                <td className="text-end">
                  <Money value={sum((r) => r.customer_total)} />
                </td>
                <td className="text-end">
                  <Money value={sum((r) => r.transaction_fees)} />
                </td>
                <td className="text-end">
                  <Money value={sum((r) => r.fees_lost_on_returns)} />
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
        <CheckLines className="border-t border-border px-5 py-3" checks={checks} />
      </section>

      <section aria-labelledby="pay-settle" className={cn(cardClass, "overflow-hidden")}>
        <div className="border-b border-border px-5 py-4">
          <h2 id="pay-settle" className="text-[15px] font-bold text-heading">
            {R.paymentsSettleTitle}
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className={th}>
                <th scope="col" className="w-full text-start">
                  {R.colMethod}
                </th>
                <th scope="col" className="text-end">
                  {R.colPending}
                </th>
                <th scope="col" className="text-end">
                  {R.colSettledExpected}
                </th>
                <th scope="col" className="text-end">
                  {R.colSettledReceived}
                </th>
                <th scope="col" className="text-end">
                  {R.colSettleDiff}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={key(r)} className={tr}>
                  <td className={cn("font-semibold", r.payment_method_id == null && "text-text-2")}>{methodName(r)}</td>
                  <td className="text-end">
                    <Money value={r.pending_expected} />
                  </td>
                  <td className="text-end">
                    <Money value={r.settled_expected} />
                  </td>
                  <td className="text-end">
                    <Money value={r.settled_received} />
                  </td>
                  <td className="text-end">
                    <SignedMoney value={r.settlement_difference} />
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className={foot}>
                <td>{R.total}</td>
                <td className="text-end">
                  <Money value={sum((r) => r.pending_expected)} />
                </td>
                <td className="text-end">
                  <Money value={sum((r) => r.settled_expected)} />
                </td>
                <td className="text-end">
                  <Money value={sum((r) => r.settled_received)} />
                </td>
                <td className="text-end">
                  <SignedMoney value={sum((r) => r.settlement_difference)} />
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
      {note}
    </div>
  )
}


function Pairs({ items }: { items: [string, React.ReactNode][] }) {
  return (
    <span className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-text-3">
      {items.map(([label, value]) => (
        <span key={label} className="flex flex-col">
          {label}
          <span className="text-[13px] text-text-2">{value}</span>
        </span>
      ))}
    </span>
  )
}
