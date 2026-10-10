"use client"

import * as React from "react"
import { ChevronDown, Info } from "lucide-react"
import { Money } from "@/components/common/money"
import { cardClass } from "@/components/record-sale/primitives"
import type { ProfitAndLoss } from "@/lib/api"
import { formatNumber } from "@/lib/persian-numbers"
import {
  STATEMENT,
  STATEMENT_INFO,
  lineAmount,
  lineSign,
  percentText,
  ratioTenths,
  statementChecks,
  type LineRole,
  type PnlKey,
} from "@/lib/reports"
import { cn } from "@/lib/utils"
import { CheckLines } from "./check-line"
import { PNL_EXPLAIN, R } from "./copy"

const GROUP_TITLES = {
  revenue: R.groupRevenue,
  orderCosts: R.groupOrderCosts,
  afterGross: R.groupAfterGross,
} as const

const ALL_KEYS: PnlKey[] = [...STATEMENT.flatMap((g) => g.lines.map((l) => l.key)), ...STATEMENT_INFO]

const toneText = { profit: "text-profit", loss: "text-loss", plain: "" } as const

/**
 * «سود و زیان»: every figure GET /reports/profit-and-loss returns, in the
 * order of accounting-rules §9, each row expandable to what it means and how
 * db/ computes it. Amounts are the API's; the screen only picks the sign
 * glyph from each figure's real sign and shows display ratios of revenue.
 */
export function PnlTab({ pnl, periodTitle, mobile }: { pnl: ProfitAndLoss; periodTitle: string; mobile: boolean }) {
  const [open, setOpen] = React.useState<Set<PnlKey>>(new Set())
  const allOpen = open.size === ALL_KEYS.length
  const toggle = (k: PnlKey) =>
    setOpen((s) => {
      const next = new Set(s)
      if (next.has(k)) next.delete(k)
      else next.add(k)
      return next
    })

  const checks = statementChecks(pnl)
  const net = pnl.net_profit
  const netPct = ratioTenths(net, pnl.total_revenue)

  const statement = (
    <section aria-labelledby="pnl-title" className={cn(cardClass, "min-w-0 grow overflow-hidden")}>
      <div className={cn("flex flex-wrap items-end justify-between gap-x-4 gap-y-1 border-b border-border", mobile ? "px-3.5 py-3" : "px-5 py-4")}>
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 id="pnl-title" className={cn("font-bold text-heading", mobile ? "text-[15px]" : "text-lg")}>
            {R.statementTitle(periodTitle)}
          </h2>
          <span className="text-xs text-text-3">{R.statementCaption(pnl.order_count)}</span>
        </div>
        <div className="flex items-center gap-3">
          {!mobile && <span className="text-xs text-text-3">{R.pctLegend}</span>}
          <button
            type="button"
            onClick={() => setOpen(allOpen ? new Set() : new Set(ALL_KEYS))}
            className="h-8 cursor-pointer rounded-md px-2 text-xs font-semibold text-primary outline-none hover:bg-surface-2 focus-visible:ring-3 focus-visible:ring-ring/30"
          >
            {allOpen ? R.hideAll : R.showAll}
          </button>
        </div>
      </div>

      {STATEMENT.map((group) => (
        <div key={group.id} role="group" aria-label={GROUP_TITLES[group.id]}>
          <div className={cn("bg-surface-2/60 text-[11.5px] font-semibold text-text-3", mobile ? "px-3.5 py-1.5" : "px-5 py-1.5")}>
            {GROUP_TITLES[group.id]}
          </div>
          {group.lines.map((line) => (
            <StatementRow
              key={line.key}
              k={line.key}
              role={line.role}
              pnl={pnl}
              open={open.has(line.key)}
              onToggle={() => toggle(line.key)}
              mobile={mobile}
            />
          ))}
        </div>
      ))}

      <div role="group" aria-label={R.infoTitle} className="border-t border-border">
        <div className={cn("bg-surface-2/60 text-[11.5px] font-semibold text-text-3", mobile ? "px-3.5 py-1.5" : "px-5 py-1.5")}>
          {R.infoTitle}
        </div>
        {STATEMENT_INFO.map((k) => (
          <StatementRow key={k} k={k} role={null} pnl={pnl} open={open.has(k)} onToggle={() => toggle(k)} mobile={mobile} />
        ))}
      </div>

      <CheckLines
        className={cn("border-t border-border", mobile ? "px-3.5 py-3" : "px-5 py-3")}
        checks={[
          { label: R.checkStatement(PNL_EXPLAIN.total_revenue.label), check: checks[0] },
          { label: R.checkStatement(PNL_EXPLAIN.gross_profit.label), check: checks[1] },
          { label: R.checkStatement(PNL_EXPLAIN.net_profit.label), check: checks[2] },
          { label: R.checkPostageVariance, check: checks[3] },
        ]}
      />
    </section>
  )

  const note = (
    <div role="note" className="flex items-start gap-2.5 rounded-xl bg-info-soft px-3.5 py-3 text-[12.5px] leading-[21px] text-text-2">
      <Info className="mt-0.5 size-[18px] shrink-0 text-info" aria-hidden />
      <span>{R.scopeNote}</span>
    </div>
  )

  if (mobile)
    return (
      <div className="flex flex-col gap-3">
        {statement}
        {note}
      </div>
    )

  return (
    <div className="flex items-start gap-6">
      {statement}
      <aside className="flex w-[320px] shrink-0 flex-col gap-4">
        <Kpi
          label={R.kpiNet}
          value={net}
          tone={lineSign("total", net).tone}
          caption={netPct == null ? R.nil : R.kpiNetCaption(percentText(netPct))}
        />
        <Kpi label={R.kpiGross} value={pnl.gross_profit} tone="plain" caption={R.kpiGrossCaption} />
        {note}
      </aside>
    </div>
  )
}

function Kpi({
  label,
  value,
  tone,
  caption,
}: {
  label: string
  value: number
  tone: "profit" | "loss" | "plain"
  caption: string
}) {
  return (
    <div className={cn(cardClass, "flex flex-col gap-1.5 px-5 py-[18px]")}>
      <span className="text-[13px] font-semibold text-text-2">{label}</span>
      <Money
        value={value}
        className={cn("text-[26px] leading-[38px] font-bold", toneText[tone], value === 0 && "text-text-3")}
        unitClassName="text-[13px] text-text-3"
      />
      <span className="text-xs text-text-3">{caption}</span>
    </div>
  )
}

/** One statement line; `role` null = an information row outside the sums. */
function StatementRow({
  k,
  role,
  pnl,
  open,
  onToggle,
  mobile,
}: {
  k: PnlKey
  role: LineRole | null
  pnl: ProfitAndLoss
  open: boolean
  onToggle: () => void
  mobile: boolean
}) {
  const ex = PNL_EXPLAIN[k]
  const value = pnl[k]
  const label = mobile && ex.short ? ex.short : ex.label
  const sign = role ? lineSign(role, value) : { glyph: "" as const, tone: "plain" as const }
  const shown = role ? lineAmount(role, value) : value
  const tenths = role ? ratioTenths(shown, pnl.total_revenue) : null
  const panelId = `pnl-explain-${k}`
  const isTotal = role === "total"
  const isNet = k === "net_profit"

  return (
    <div className={cn("border-b border-border last:border-b-0", isTotal && !isNet && "bg-surface-2", isNet && "bg-profit-soft")}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        title={R.explainAria(ex.label)}
        onClick={onToggle}
        className={cn(
          "grid w-full cursor-pointer items-center gap-x-3 text-start outline-none hover:bg-surface-2/70 focus-visible:ring-3 focus-visible:ring-ring/30 focus-visible:ring-inset",
          mobile
            ? "min-h-11 grid-cols-[14px_minmax(0,1fr)_auto] px-3.5 py-2 text-[13px]"
            : "min-h-11 grid-cols-[14px_minmax(0,1fr)_180px_90px] px-5 py-2 text-[13.5px]",
          isTotal && "font-bold",
          isNet && !mobile && "min-h-14 text-base font-extrabold"
        )}
      >
        <span className={cn("text-center font-bold", toneText[sign.tone])} aria-hidden>
          {sign.glyph}
        </span>
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="min-w-0">{label}</span>
          <ChevronDown className={cn("size-3.5 shrink-0 text-text-3 transition-transform", open && "rotate-180")} aria-hidden />
        </span>
        <span className={cn("text-end whitespace-nowrap", toneText[sign.tone])}>
          {(sign.glyph === "−" || sign.glyph === "+") && (
            <span className="sr-only">{sign.glyph === "+" ? R.signAdd : R.signSub}: </span>
          )}
          {k === "order_count" ? <span className="tabular-nums">{formatNumber(pnl.order_count)}</span> : <Money value={shown} />}
        </span>
        {!mobile && (
          <span className="text-end text-[12.5px] font-normal text-text-3 tabular-nums">
            {tenths == null ? (role ? R.nil : "") : percentText(tenths)}
          </span>
        )}
      </button>
      <div
        id={panelId}
        hidden={!open}
        className={cn("flex flex-col gap-1.5 text-[12.5px] leading-[21px] text-text-2", mobile ? "px-3.5 pb-3 ps-[38px]" : "px-5 pb-3.5 ps-[46px]")}
      >
        <p className="text-heading">{ex.meaning}</p>
        <p>
          <b className="font-semibold text-text-3">{R.howTitle}: </b>
          {ex.how}
        </p>
        {ex.formula && (
          <p>
            <b className="font-semibold text-text-3">{R.formulaTitle}: </b>
            <span dir="ltr" className="inline-block tabular-nums">
              {ex.formula(pnl)}
            </span>
          </p>
        )}
      </div>
    </div>
  )
}
