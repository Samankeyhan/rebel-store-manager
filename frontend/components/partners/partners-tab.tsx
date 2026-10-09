"use client"

import * as React from "react"
import { UserMinus, Users } from "lucide-react"
import { Collapsible } from "@/components/common/collapsible"
import { Money } from "@/components/common/money"
import { StateShell } from "@/components/common/screen-states"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import { listPartnerTotals, type Partner, type PartnerTotal } from "@/lib/api"
import { percentText } from "@/lib/partners"
import { formatNumber } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { S } from "./copy"

type Totals = { status: "loading" } | { status: "error" } | { status: "ready"; byName: Map<string, PartnerTotal> }

/**
 * «شرکا»: active partners with their percentage and all-time total received
 * (GET /partners/totals, keyed by name), deactivated ones in a collapsible
 * list. Name, phone, email and notes can't be edited after creation (the
 * backend has no endpoint), nor can a partner be reactivated.
 */
export function PartnersTab({
  partners,
  reloadKey,
  mobile,
  onAdd,
  onDeactivate,
}: {
  partners: Partner[]
  /** Changes after every save, so the totals refetch. */
  reloadKey: number
  mobile: boolean
  onAdd: () => void
  onDeactivate: (p: Partner) => void
}) {
  const [totals, setTotals] = React.useState<Totals>({ status: "loading" })
  React.useEffect(() => {
    let cancelled = false
    listPartnerTotals().then(
      (rows) => !cancelled && setTotals({ status: "ready", byName: new Map(rows.map((r) => [r.partner_name, r])) }),
      () => !cancelled && setTotals({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const active = partners.filter((p) => p.is_active === 1)
  const inactive = partners.filter((p) => p.is_active !== 1)

  if (partners.length === 0)
    return (
      <StateShell
        icon={Users}
        mobile={mobile}
        title={S.emptyTitle}
        body={S.emptyBody}
        action={
          <Btn variant="primary" size={mobile ? "lg" : "md"} className="mt-1" onClick={onAdd}>
            {S.addPartner}
          </Btn>
        }
      />
    )

  const received = (p: Partner) => {
    if (totals.status !== "ready") return <span className="text-text-3">{S.nil}</span>
    const t = totals.byName.get(p.name)
    return <Money value={t?.total_received ?? 0} />
  }
  const count = (p: Partner) =>
    totals.status === "ready" ? formatNumber(totals.byName.get(p.name)?.distribution_count ?? 0) : S.nil // qty: a count of payouts
  const contact = (p: Partner) => [p.phone, p.email].filter(Boolean).join(" · ") || S.nil

  const list = (rows: Partner[], isActive: boolean) =>
    mobile ? (
      <ul className="flex flex-col gap-2">
        {rows.map((p) => (
          <li key={p.id} className={cn(cardClass, "flex flex-col gap-2 px-3.5 py-3 text-[13px]")}>
            <span className="flex items-start justify-between gap-2">
              <span className="flex min-w-0 flex-col gap-0.5">
                <b dir="auto" className="truncate text-[13.5px] text-heading">
                  {p.name}
                </b>
                <span dir="auto" className="truncate text-xs text-text-3">
                  {contact(p)}
                </span>
              </span>
              {isActive ? (
                <b className="shrink-0 text-[15px] tabular-nums">{S.percent(percentText(p.current_percentage))}</b>
              ) : (
                <span className="shrink-0 rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-3">{S.inactive}</span>
              )}
            </span>
            <span className="flex items-center justify-between gap-2">
              <span className="text-text-3">{S.colReceived}</span>
              {received(p)}
            </span>
            {p.notes && (
              <p dir="auto" className="text-xs text-text-2">
                {p.notes}
              </p>
            )}
            {isActive && (
              <Btn size="lg" className="h-10" onClick={() => onDeactivate(p)}>
                <UserMinus className="size-4" aria-hidden />
                {S.deactivate}
              </Btn>
            )}
          </li>
        ))}
      </ul>
    ) : (
      <section className={cn(cardClass, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col">{S.colName}</th>
                <th scope="col">{S.colPercent}</th>
                <th scope="col">{S.colReceived}</th>
                <th scope="col">{S.colPayouts}</th>
                <th scope="col">{S.colContact}</th>
                <th scope="col" className="w-full">
                  {S.colNotes}
                </th>
                <th scope="col">
                  <span className="sr-only">{S.colActions}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr
                  key={p.id}
                  className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
                >
                  <td dir="auto" className="max-w-[200px] truncate font-semibold">
                    {p.name}
                  </td>
                  <td className="font-bold tabular-nums">
                    {isActive ? (
                      S.percent(percentText(p.current_percentage))
                    ) : (
                      <span className="rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] font-normal text-text-3">{S.inactive}</span>
                    )}
                  </td>
                  <td>{received(p)}</td>
                  <td className="text-text-2">{count(p)}</td>
                  <td dir="auto" className="max-w-[220px] truncate text-text-2">
                    {contact(p)}
                  </td>
                  <td dir="auto" className={cn("max-w-[260px] truncate", !p.notes && "text-text-3")}>
                    {p.notes || S.nil}
                  </td>
                  <td>
                    {isActive && (
                      <Btn size="sm" onClick={() => onDeactivate(p)}>
                        <UserMinus className="size-3.5" aria-hidden />
                        {S.deactivate}
                      </Btn>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    )

  return (
    <div className="flex flex-col gap-3">
      {totals.status === "error" && <p className="text-xs text-text-3">{S.totalsFailed}</p>}
      {active.length === 0 ? (
        <StateShell icon={Users} mobile={mobile} title={S.noActiveTitle} body={S.noActiveBody} />
      ) : (
        list(active, true)
      )}
      {inactive.length > 0 && (
        <Collapsible label={S.inactiveList(inactive.length)} buttonClassName="min-h-11">
          <div className="pt-2">{list(inactive, false)}</div>
        </Collapsible>
      )}
    </div>
  )
}
