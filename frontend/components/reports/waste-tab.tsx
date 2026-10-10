"use client"

import * as React from "react"
import { Trash2 } from "lucide-react"
import { Money } from "@/components/common/money"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { useLoad, type Loader } from "@/components/dashboard/use-dashboard-data"
import { unitLabel } from "@/components/products/figures"
import { cardClass } from "@/components/record-sale/primitives"
import { getWasteReport, type ProfitAndLoss, type WasteReportRow } from "@/lib/api"
import { formatNumber, formatQuantity } from "@/lib/persian-numbers"
import { apiRange, periodKey, type ReportPeriod } from "@/lib/report-period"
import { reportLink, wasteChecks, wasteTotals } from "@/lib/reports"
import { cn } from "@/lib/utils"
import { CheckLines, pnlChecks } from "./check-line"
import { R, WASTE_EXPLAIN } from "./copy"
import { ReportNote, ScreenLink } from "./report-bits"

type Row = WasteReportRow

/** adjustments-page.tsx reads ?kind=waste, ?item=<TYPE>:<id> and ?from=&to=; all time gives no link. */
const adjustmentsHref = (r: Row, period: ReportPeriod) =>
  reportLink("/adjustments", { kind: "waste", item: `${r.item_type}:${r.item_id}` }, period.range)

const quantity = (r: Row) => `${formatQuantity(r.total_wasted)} ${unitLabel(r.unit)}`

function Kind({ type }: { type: string }) {
  return (
    <span className="inline-flex h-5 shrink-0 items-center rounded-md bg-surface-2 px-1.5 text-[11px] font-medium text-text-3">
      {type === "PRODUCT" ? R.kindProduct : R.kindMaterial}
    </span>
  )
}

/** A row's cost: «نامعلوم» when no movement had a cost (never 0), plus a note when some were left out. */
function Cost({ r, className }: { r: Row; className?: string }) {
  if (r.cost === null)
    return (
      <span
        title={R.unknownCostTitle}
        className={cn("inline-flex h-6 items-center rounded-md bg-warn-soft px-2 text-xs font-semibold text-warn", className)}
      >
        {R.unknownCost}
      </span>
    )
  return (
    <span className={cn("inline-flex flex-col items-end", className)}>
      <Money value={r.cost} />
      {r.unknown_cost_count > 0 && <span className="text-[11px] font-normal text-warn">{R.partialCost(r.unknown_cost_count)}</span>}
    </span>
  )
}

/**
 * «ضایعات»: GET /reports/waste for the period (rules §8), one row per item,
 * in the backend's order (known cost highest first, unknown last). The
 * known per-item costs sum exactly to the P&L waste_cost; an unknown cost
 * is shown as unknown, never as 0.
 */
export function WasteTab({
  period,
  pnl,
  mobile,
}: {
  period: ReportPeriod
  pnl: Loader<ProfitAndLoss>
  mobile: boolean
}) {
  const load = useLoad<Row[]>("REPORTS", periodKey(period), () => getWasteReport(apiRange(period)))

  if (load.status === "loading") return <LoadingBlock mobile={mobile} label={R.loadingAria} />
  if (load.status === "error")
    return <ErrorBlock title={R.errorTitle} body={R.errorBody} retry={R.retry} onRetry={load.retry} mobile={mobile} />

  const rows = load.data
  const checks = pnlChecks(pnl, (p) => [{ label: R.checkWaste, check: wasteChecks(rows, p).cost }])

  if (rows.length === 0)
    return (
      <div className="flex flex-col gap-3">
        <StateShell icon={Trash2} mobile={mobile} title={R.wasteEmptyTitle} body={R.wasteEmptyBody} />
        <CheckLines checks={checks} />
      </div>
    )

  const t = wasteTotals(rows)
  const totalCost = (
    <span className="inline-flex flex-col items-end">
      <Money value={t.knownCost} />
      {t.unknownRows > 0 && <span className="text-[11px] font-normal text-warn">{R.unknownRows(t.unknownRows)}</span>}
    </span>
  )

  const list = mobile ? (
    <ul aria-label={R.wasteAria} className="flex flex-col gap-2">
      {rows.map((r) => (
        <li key={`${r.item_type}:${r.item_id}`} className={cn(cardClass, "flex flex-col gap-1.5 px-3.5 py-3 text-[13px]")}>
          <span className="flex items-start justify-between gap-2">
            <span className="flex min-w-0 items-center gap-1.5">
              <Kind type={r.item_type} />
              <b className="truncate text-heading">{r.item_name}</b>
              <ScreenLink href={adjustmentsHref(r, period)} label={R.openAdjustments(r.item_name)} />
            </span>
            <Cost r={r} className="font-bold" />
          </span>
          <span className="flex flex-wrap gap-x-3 text-xs text-text-3">
            <span>
              {R.colQuantity}: <span className="tabular-nums text-text-2">{quantity(r)}</span>
            </span>
            <span>
              {R.colEvents}: <span className="tabular-nums text-text-2">{formatNumber(r.waste_event_count)}</span>
            </span>
          </span>
        </li>
      ))}
      <li className={cn(cardClass, "flex items-start justify-between gap-2 bg-surface-2 px-3.5 py-3 text-[13px] font-bold")}>
        {R.total}
        {totalCost}
      </li>
    </ul>
  ) : (
    <section aria-label={R.wasteAria} className={cn(cardClass, "overflow-hidden")}>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[13.5px]">
          <thead>
            <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:whitespace-nowrap">
              <th scope="col" className="w-full text-start">
                {R.colItem}
              </th>
              <th scope="col" className="text-end">
                {R.colQuantity}
              </th>
              <th scope="col" className="text-end">
                {R.colEvents}
              </th>
              <th scope="col" className="text-end">
                {R.colWasteCost}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={`${r.item_type}:${r.item_id}`}
                className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:py-1.5 [&>td]:whitespace-nowrap"
              >
                <td>
                  <span className="flex items-center gap-1.5">
                    <Kind type={r.item_type} />
                    <span className="font-semibold">{r.item_name}</span>
                    <ScreenLink href={adjustmentsHref(r, period)} label={R.openAdjustments(r.item_name)} />
                  </span>
                </td>
                <td className="text-end tabular-nums">{quantity(r)}</td>
                <td className="text-end tabular-nums">{formatNumber(r.waste_event_count)}</td>
                <td className="text-end">
                  <Cost r={r} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="font-bold [&>td]:h-12 [&>td]:bg-surface-2 [&>td]:px-4 [&>td]:py-1.5 [&>td]:whitespace-nowrap">
              <td>{R.total}</td>
              <td className="text-end text-text-3">{R.nil}</td>
              <td className="text-end tabular-nums">{formatNumber(rows.reduce((s, r) => s + r.waste_event_count, 0))}</td>
              <td className="text-end">{totalCost}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  )

  return (
    <div className="flex flex-col gap-4">
      {list}
      <CheckLines checks={checks} />
      <ReportNote>
        <span>{WASTE_EXPLAIN}</span>
      </ReportNote>
    </div>
  )
}
