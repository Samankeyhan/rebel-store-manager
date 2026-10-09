"use client"

import * as React from "react"
import { ChevronDown, CloudOff, HandCoins, RotateCw } from "lucide-react"
import { Collapsible } from "@/components/common/collapsible"
import { Money } from "@/components/common/money"
import { StateShell } from "@/components/common/screen-states"
import { Skeleton } from "@/components/ui/skeleton"
import { Btn, Help, cardClass } from "@/components/record-sale/primitives"
import { getDistribution, type Distribution, type DistributionListItem, type Partner } from "@/lib/api"
import { formatJalali, utcToLocal } from "@/lib/jalali"
import { percentText } from "@/lib/partners"
import { cn } from "@/lib/utils"
import { S } from "./copy"

type Detail = { status: "loading" } | { status: "error" } | { status: "ready"; distribution: Distribution }

/**
 * «پرداخت‌ها»: recorded payouts, newest first (GET /distributions). A row's
 * per-partner shares load when it is expanded (GET /distributions/{id}):
 * the stored amounts and percentage_at_time, so a later percentage change
 * or deactivation never changes them. Read-only: the backend has no edit or
 * delete for a payout.
 */
export function PayoutsTab({
  rows,
  partners,
  timeZone,
  mobile,
}: {
  rows: DistributionListItem[]
  partners: Partner[]
  timeZone: string
  mobile: boolean
}) {
  const [details, setDetails] = React.useState<Record<number, Detail>>({})
  const [expanded, setExpanded] = React.useState<Set<number>>(new Set())

  const loadDetail = React.useCallback((id: number) => {
    setDetails((d) => ({ ...d, [id]: { status: "loading" } }))
    getDistribution(id).then(
      (distribution) => setDetails((d) => ({ ...d, [id]: { status: "ready", distribution } })),
      () => setDetails((d) => ({ ...d, [id]: { status: "error" } }))
    )
  }, [])

  const toggle = (id: number) => {
    const next = new Set(expanded)
    if (next.has(id)) next.delete(id)
    else {
      next.add(id)
      if (!details[id] || details[id].status === "error") loadDetail(id)
    }
    setExpanded(next)
  }

  const inactiveIds = new Set(partners.filter((p) => p.is_active !== 1).map((p) => p.id))
  const paidOn = (d: DistributionListItem) => {
    const local = utcToLocal(d.distribution_date, timeZone)
    return local ? formatJalali(local.iso, "yyyy/MM/dd") : S.nil
  }

  if (rows.length === 0)
    return <StateShell icon={HandCoins} mobile={mobile} title={S.payoutsEmptyTitle} body={S.payoutsEmptyBody} />

  const body = mobile ? (
    <ul className="flex flex-col gap-2" aria-label={S.payoutsAria}>
      {rows.map((d) => (
        <li key={d.id} className={cn(cardClass, "flex flex-col gap-2 px-3.5 py-3 text-[13px]")}>
          <span className="flex items-start justify-between gap-2">
            <span className="flex min-w-0 flex-col gap-0.5">
              <b className="text-[13.5px] text-heading tabular-nums">{paidOn(d)}</b>
              <span className="text-xs text-text-3">{S.periodText(d.period_start, d.period_end)}</span>
            </span>
            <Money value={d.total_amount_distributed} className="shrink-0 font-bold" />
          </span>
          <span className="flex items-center justify-between gap-2">
            <span className="text-text-3">{S.colPeriodProfit}</span>
            <Money value={d.total_profit_available} />
          </span>
          {d.notes && (
            <p dir="auto" className="text-xs text-text-2">
              {d.notes}
            </p>
          )}
          <Collapsible
            label={S.sharesToggle}
            className="border-t border-border pt-1.5"
            buttonClassName="min-h-11"
            onFirstOpen={() => {
              if (!details[d.id] || details[d.id].status === "error") loadDetail(d.id)
            }}
          >
            <Shares detail={details[d.id]} inactiveIds={inactiveIds} onRetry={() => loadDetail(d.id)} />
          </Collapsible>
        </li>
      ))}
    </ul>
  ) : (
    <section aria-label={S.payoutsAria} className={cn(cardClass, "overflow-hidden")}>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[13.5px]">
          <thead>
            <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
              <th scope="col" className="w-10">
                <span className="sr-only">{S.sharesOf}</span>
              </th>
              <th scope="col">{S.colDate}</th>
              <th scope="col">{S.colPeriod}</th>
              <th scope="col">{S.colTotal}</th>
              <th scope="col">{S.colPeriodProfit}</th>
              <th scope="col" className="w-full">
                {S.colNotes}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => {
              const open = expanded.has(d.id)
              return (
                <React.Fragment key={d.id}>
                  <tr className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap">
                    <td>
                      <Btn
                        variant="ghost"
                        size="sm"
                        className="size-8 px-0"
                        aria-expanded={open}
                        aria-label={`${S.expand}: ${S.payoutNo(d.id)}`}
                        onClick={() => toggle(d.id)}
                      >
                        <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
                      </Btn>
                    </td>
                    <td className="text-text-2 tabular-nums">{paidOn(d)}</td>
                    <td className="text-text-2">{S.periodText(d.period_start, d.period_end)}</td>
                    <td className="font-bold">
                      <Money value={d.total_amount_distributed} />
                    </td>
                    <td>
                      <Money value={d.total_profit_available} />
                    </td>
                    <td dir="auto" className={cn("max-w-[260px] truncate", !d.notes && "text-text-3")}>
                      {d.notes || S.nil}
                    </td>
                  </tr>
                  {open && (
                    <tr>
                      <td colSpan={6} className="border-b border-border bg-surface-2 px-4 py-3">
                        <div className="mb-2 text-xs font-semibold text-text-3">{S.sharesOf}</div>
                        <Shares detail={details[d.id]} inactiveIds={inactiveIds} onRetry={() => loadDetail(d.id)} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )

  return (
    <div className="flex flex-col gap-3">
      <Help>{S.payoutsNote}</Help>
      {body}
    </div>
  )
}

function Shares({ detail, inactiveIds, onRetry }: { detail: Detail | undefined; inactiveIds: Set<number>; onRetry: () => void }) {
  if (!detail || detail.status === "loading")
    return (
      <div aria-busy="true" aria-label={S.loadingAria} className="flex flex-col gap-2 py-1">
        {[0, 1].map((i) => (
          <Skeleton key={i} className="h-8 rounded-md bg-card" />
        ))}
      </div>
    )
  if (detail.status === "error")
    return (
      <div role="alert" className="flex flex-wrap items-center gap-2 py-1 text-[13px] text-loss">
        <CloudOff className="size-4" aria-hidden />
        {S.sharesFailed}
        <Btn size="sm" onClick={onRetry}>
          <RotateCw className="size-3.5" aria-hidden />
          {S.retry}
        </Btn>
      </div>
    )
  return (
    <ul className="flex flex-col gap-1.5 pt-1">
      {detail.distribution.shares.map((s) => (
        <li key={s.id} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2 text-[13px]">
          <span className="flex min-w-0 items-center gap-2">
            <b dir="auto" className="truncate">
              {s.partner_name}
            </b>
            {inactiveIds.has(s.partner_id) && (
              <span className="shrink-0 rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-3">{S.inactive}</span>
            )}
            <span className="shrink-0 text-xs text-text-3 tabular-nums" title={S.percentAtTime}>
              {S.percent(percentText(s.percentage_at_time))}
            </span>
          </span>
          <Money value={s.amount} className="shrink-0 font-bold" />
        </li>
      ))}
    </ul>
  )
}
