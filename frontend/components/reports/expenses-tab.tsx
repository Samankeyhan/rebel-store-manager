"use client"

import * as React from "react"
import { Wallet } from "lucide-react"
import { Money } from "@/components/common/money"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { useLoad, type Loader } from "@/components/dashboard/use-dashboard-data"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import {
  getExpenseBreakdown,
  getPurchasesSummary,
  type ExpenseBreakdown,
  type ProfitAndLoss,
  type PurchasesSummary,
} from "@/lib/api"
import { formatNumber } from "@/lib/persian-numbers"
import { apiRange, periodKey, type ReportPeriod } from "@/lib/report-period"
import { barPercent, expenseChecks, percentText, ratioTenths, reportLink } from "@/lib/reports"
import { cn } from "@/lib/utils"
import { CheckLines, pnlChecks } from "./check-line"
import { PNL_EXPLAIN, R } from "./copy"
import { ReportNote, ScreenLink } from "./report-bits"

/**
 * «هزینه‌ها و خرید»: GET /reports/expenses (per category; checked against
 * the P&L operating_expenses) and GET /reports/purchases, which is inventory,
 * not an expense (rules §9, §2): shown apart, never added to anything.
 * Links: expenses-page.tsx reads ?category= and ?from=&to=;
 * purchases-page.tsx reads ?type=material|product and ?from=&to=.
 * Neither screen has an all-time URL, so all time shows no links.
 */
export function ExpensesTab({
  period,
  pnl,
  mobile,
}: {
  period: ReportPeriod
  pnl: Loader<ProfitAndLoss>
  mobile: boolean
}) {
  const expenses = useLoad<ExpenseBreakdown[]>("REPORTS", periodKey(period), () => getExpenseBreakdown(apiRange(period)))
  const purchases = useLoad<PurchasesSummary>("REPORTS", periodKey(period), () => getPurchasesSummary(apiRange(period)))

  if (expenses.status === "loading" || purchases.status === "loading")
    return <LoadingBlock mobile={mobile} label={R.loadingAria} />
  if (expenses.status === "error" && purchases.status === "error")
    return (
      <ErrorBlock
        title={R.errorTitle}
        body={R.errorBody}
        retry={R.retry}
        onRetry={() => {
          expenses.retry()
          purchases.retry()
        }}
        mobile={mobile}
      />
    )

  const nothing =
    expenses.status === "ready" &&
    expenses.data.length === 0 &&
    purchases.status === "ready" &&
    purchases.data.material_purchases_count === 0 &&
    purchases.data.product_purchases_count === 0 &&
    purchases.data.material_purchases_total === 0 &&
    purchases.data.product_purchases_total === 0

  if (nothing)
    return (
      <div className="flex flex-col gap-3">
        <StateShell icon={Wallet} mobile={mobile} title={R.expensesEmptyTitle} body={R.expensesEmptyBody} />
        <CheckLines checks={pnlChecks(pnl, (p) => [{ label: R.checkExpenses, check: expenseChecks([], p).total }])} />
      </div>
    )

  return (
    <div className={cn("flex flex-col gap-4", !mobile && "gap-5")}>
      {expenses.status === "error" ? (
        <PartError onRetry={expenses.retry} />
      ) : (
        <ExpensesCard rows={expenses.data} period={period} pnl={pnl} mobile={mobile} />
      )}
      {purchases.status === "error" ? (
        <PartError onRetry={purchases.retry} />
      ) : (
        <PurchasesCard p={purchases.data} period={period} mobile={mobile} />
      )}
    </div>
  )
}

function PartError({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className={cn(cardClass, "flex items-center justify-between gap-3 px-4 py-3 text-[13px] text-text-2")}>
      {R.partLoadFailed}
      <Btn variant="outline" size="sm" onClick={onRetry}>
        {R.retry}
      </Btn>
    </div>
  )
}

function ExpensesCard({
  rows,
  period,
  pnl,
  mobile,
}: {
  rows: ExpenseBreakdown[]
  period: ReportPeriod
  pnl: Loader<ProfitAndLoss>
  mobile: boolean
}) {
  const checks = pnlChecks(pnl, (p) => [{ label: R.checkExpenses, check: expenseChecks(rows, p).total }])
  // Display ratios only: each category's share of the returned totals' sum.
  const total = rows.reduce((s, r) => s + r.total_amount, 0)
  const max = Math.max(0, ...rows.map((r) => r.total_amount))
  const share = (v: number) => {
    const t = ratioTenths(v, total)
    return t == null ? R.nil : percentText(t)
  }
  const href = (r: ExpenseBreakdown) => reportLink("/expenses", { category: String(r.category_id) }, period.range)

  const empty = <p className={cn("text-[13px] text-text-3", mobile ? "px-3.5 py-3" : "px-5 py-4")}>{R.expensesEmptyTitle}</p>
  const expenseCount = rows.reduce((s, r) => s + r.expense_count, 0)

  const body =
    rows.length === 0 ? (
      empty
    ) : mobile ? (
      <ul className="flex flex-col">
        {rows.map((r) => (
          <li key={r.category_id} className="flex flex-col gap-1 border-b border-border px-3.5 py-2.5 text-[13px]">
            <span className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-1">
                <span className="truncate font-semibold">{r.category_name}</span>
                <ScreenLink href={href(r)} label={R.openExpenses(r.category_name)} />
              </span>
              <Money value={r.total_amount} className="font-bold" />
            </span>
            <span className="text-xs text-text-3">
              {R.colCount}: <span className="tabular-nums">{formatNumber(r.expense_count)}</span> · {R.colShare}:{" "}
              <span className="tabular-nums">{share(r.total_amount)}</span>
            </span>
          </li>
        ))}
        <li className="flex items-center justify-between gap-2 bg-surface-2 px-3.5 py-3 text-[13px] font-bold">
          {R.total}
          <Money value={total} />
        </li>
      </ul>
    ) : (
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[13.5px]">
          <thead>
            <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:whitespace-nowrap">
              <th scope="col" className="text-start">
                {R.colCategory}
              </th>
              <th scope="col" className="w-full text-start">
                {R.colShare}
              </th>
              <th scope="col" className="text-end">
                {R.colCount}
              </th>
              <th scope="col" className="text-end">
                {R.colAmount}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.category_id}
                className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
              >
                <td>
                  <span className="flex items-center gap-1">
                    <span className="font-semibold">{r.category_name}</span>
                    <ScreenLink href={href(r)} label={R.openExpenses(r.category_name)} />
                  </span>
                </td>
                <td>
                  <span className="flex items-center gap-2.5">
                    <span className="h-2.5 min-w-[80px] grow overflow-hidden rounded-e-[4px] bg-surface-2" aria-hidden>
                      <span className="block h-full rounded-e-[4px] bg-bar-a" style={{ width: `${barPercent(r.total_amount, max)}%` }} />
                    </span>
                    <span className="w-12 text-end text-[12.5px] text-text-3 tabular-nums">{share(r.total_amount)}</span>
                  </span>
                </td>
                <td className="text-end tabular-nums">{formatNumber(r.expense_count)}</td>
                <td className="text-end font-bold">
                  <Money value={r.total_amount} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="font-bold [&>td]:h-12 [&>td]:bg-surface-2 [&>td]:px-4 [&>td]:whitespace-nowrap">
              <td>{R.total}</td>
              <td />
              <td className="text-end tabular-nums">{formatNumber(expenseCount)}</td>
              <td className="text-end">
                <Money value={total} />
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    )

  return (
    <section aria-labelledby="exp-title" className={cn(cardClass, "overflow-hidden")}>
      <div className={cn("flex flex-wrap items-end justify-between gap-2 border-b border-border", mobile ? "px-3.5 py-3" : "px-5 py-4")}>
        <h2 id="exp-title" className="text-[15px] font-bold text-heading">
          {R.expensesTitle}
        </h2>
      </div>
      {body}
      <CheckLines className={cn("border-t border-border", mobile ? "px-3.5 py-3" : "px-5 py-3")} checks={checks} />
      <div className={cn("border-t border-border text-[12.5px] leading-[21px] text-text-2", mobile ? "px-3.5 py-3" : "px-5 py-3")}>
        {PNL_EXPLAIN.operating_expenses.how}
      </div>
    </section>
  )
}

function PurchasesCard({ p, period, mobile }: { p: PurchasesSummary; period: ReportPeriod; mobile: boolean }) {
  const lines = [
    { type: "material", label: R.purchasesMaterial, total: p.material_purchases_total, count: p.material_purchases_count },
    { type: "product", label: R.purchasesProduct, total: p.product_purchases_total, count: p.product_purchases_count },
  ]
  return (
    <section aria-labelledby="pur-title" className={cn(cardClass, "overflow-hidden")}>
      <div className={cn("border-b border-border", mobile ? "px-3.5 py-3" : "px-5 py-4")}>
        <h2 id="pur-title" className="text-[15px] font-bold text-heading">
          {R.purchasesTitle}
        </h2>
      </div>
      <div className={cn("grid", mobile ? "grid-cols-1" : "grid-cols-2")}>
        {lines.map((l) => (
          <div
            key={l.type}
            className={cn(
              "flex items-center justify-between gap-3 border-border",
              mobile ? "border-b px-3.5 py-3" : "border-e px-5 py-4 last:border-e-0"
            )}
          >
            <span className="flex min-w-0 flex-col">
              <span className="flex items-center gap-1 text-[13px] font-semibold text-text-2">
                {l.label}
                <ScreenLink href={reportLink("/purchases", { type: l.type }, period.range)} label={R.openPurchases(l.label)} />
              </span>
              <span className="text-xs text-text-3">{R.purchasesCount(l.count)}</span>
            </span>
            <Money value={l.total} className={cn("font-bold", mobile ? "text-[15px]" : "text-lg")} />
          </div>
        ))}
      </div>
      <div className={cn(mobile ? "p-3" : "p-4")}>
        <ReportNote>
          <span>{R.purchasesNote}</span>
        </ReportNote>
      </div>
    </section>
  )
}
