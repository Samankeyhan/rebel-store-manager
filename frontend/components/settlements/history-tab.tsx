"use client"

import * as React from "react"
import Link from "next/link"
import { ChevronDown, CloudOff, History, Pencil, RotateCw, SearchX } from "lucide-react"
import { Collapsible } from "@/components/common/collapsible"
import { Money } from "@/components/common/money"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { StatusBadge } from "@/components/common/status"
import { orderHref } from "@/components/orders/list/orders-table"
import { Skeleton } from "@/components/ui/skeleton"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import {
  ApiError,
  getSettlement,
  listPaymentMethods,
  listSettlements,
  type PaymentMethod,
  type Settlement,
  type SettlementListItem,
} from "@/lib/api"
import { formatJalali } from "@/lib/jalali"
import { differenceKind, jalaliMonthTitle } from "@/lib/settlements"
import { cn } from "@/lib/utils"
import { S, signedMoney } from "./copy"
import { EditDialog } from "./edit-dialog"
import { differenceTone } from "./record-dialog"

type List = { status: "loading" } | { status: "error"; code: string } | { status: "ready"; rows: SettlementListItem[] }
type Detail = { status: "loading" } | { status: "error" } | { status: "ready"; settlement: Settlement }

const short = (iso: string) => formatJalali(iso, "yyyy/MM/dd")

function errorCode(e: unknown): string {
  return e instanceof ApiError && e.status > 0 ? `SETTLEMENTS_${e.status}` : "NET_TIMEOUT"
}

function periodText(s: SettlementListItem): string {
  return s.jalali_year != null && s.jalali_month != null ? jalaliMonthTitle(s.jalali_year, s.jalali_month) : S.orders(s.order_count)
}

/** db/settlements.py list order: settled_date DESC, id DESC. */
function byNewest(a: SettlementListItem, b: SettlementListItem): number {
  if (a.settled_date !== b.settled_date) return a.settled_date < b.settled_date ? 1 : -1
  return b.id - a.id
}

const filterBtn =
  "flex cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"

/**
 * «سابقه»: recorded settlements, newest first, filtered by method (?method=,
 * inactive methods included). A row's orders load when it is expanded
 * (GET /settlements/{id}); the list has none. Edit = amount received,
 * settled date, note.
 */
export function HistoryTab({
  methodId,
  onMethodChange,
  today,
  mobile,
  onToast,
}: {
  methodId: number | null
  onMethodChange: (id: number | null) => void
  today: string | null
  mobile: boolean
  onToast: (text: string) => void
}) {
  const [list, setList] = React.useState<List>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)
  const [methods, setMethods] = React.useState<PaymentMethod[] | null>(null)
  const [details, setDetails] = React.useState<Record<number, Detail>>({})
  const [expanded, setExpanded] = React.useState<Set<number>>(new Set())
  const [editing, setEditing] = React.useState<SettlementListItem | null>(null)

  React.useEffect(() => {
    let cancelled = false
    listPaymentMethods(true).then(
      (all) => !cancelled && setMethods(all),
      () => {} // the filter then offers only «همه روش‌ها» and the current choice
    )
    return () => {
      cancelled = true
    }
  }, [])

  const [listKey, setListKey] = React.useState(`${methodId}#${attempt}`)
  if (listKey !== `${methodId}#${attempt}`) {
    setListKey(`${methodId}#${attempt}`)
    setList({ status: "loading" })
  }
  React.useEffect(() => {
    let cancelled = false
    listSettlements({ paymentMethodId: methodId }).then(
      (rows) => !cancelled && setList({ status: "ready", rows }),
      (e: unknown) => !cancelled && setList({ status: "error", code: errorCode(e) })
    )
    return () => {
      cancelled = true
    }
  }, [methodId, attempt])

  const loadDetail = React.useCallback((id: number) => {
    setDetails((d) => ({ ...d, [id]: { status: "loading" } }))
    getSettlement(id).then(
      (settlement) => setDetails((d) => ({ ...d, [id]: { status: "ready", settlement } })),
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

  const onSaved = (saved: Settlement) => {
    setEditing(null)
    setList((l) =>
      l.status === "ready"
        ? {
            status: "ready",
            rows: l.rows
              .map((r) =>
                r.id === saved.id
                  ? {
                      ...r,
                      settled_date: saved.settled_date,
                      amount_received: saved.amount_received,
                      expected_amount: saved.expected_amount,
                      difference: saved.difference,
                      note: saved.note,
                    }
                  : r
              )
              .sort(byNewest),
          }
        : l
    )
    setDetails((d) => ({ ...d, [saved.id]: { status: "ready", settlement: saved } }))
    onToast(S.toastEdited)
  }

  const current = methods?.find((m) => m.id === methodId) ?? null
  const methodMenu = (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <button type="button" className={cn(filterBtn, mobile ? "h-11 w-full justify-between" : "h-10 w-fit")}>
          <span className="flex min-w-0 items-center gap-2">
            {!mobile && <span className="text-text-3">{S.methodPrefix}</span>}
            <span className="truncate font-bold">{methodId == null ? S.allMethods : (current?.name ?? S.nil)}</span>
          </span>
          <ChevronDown className="size-3.5 shrink-0 text-text-3" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-80 w-60 overflow-y-auto">
        <DropdownMenuRadioGroup
          value={methodId == null ? "" : String(methodId)}
          onValueChange={(v) => onMethodChange(v ? Number(v) : null)}
        >
          <DropdownMenuRadioItem value="">{S.allMethods}</DropdownMenuRadioItem>
          {(methods ?? []).map((m) => (
            <DropdownMenuRadioItem key={m.id} value={String(m.id)}>
              {m.name}
              {m.is_active !== 1 && <span className="text-xs text-text-3">({S.inactive})</span>}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )

  let body: React.ReactNode
  if (list.status === "loading") body = <LoadingBlock mobile={mobile} label={S.loadingAria} />
  else if (list.status === "error")
    body = (
      <ErrorBlock
        title={S.historyErrorTitle}
        body={S.errorBody}
        retry={S.retry}
        onRetry={() => setAttempt((a) => a + 1)}
        mobile={mobile}
      />
    )
  else if (list.rows.length === 0)
    body =
      methodId == null ? (
        <StateShell icon={History} mobile={mobile} title={S.historyEmptyTitle} body={S.historyEmptyBody} />
      ) : (
        <StateShell
          icon={SearchX}
          mobile={mobile}
          title={S.historyFilteredEmpty}
          action={
            <Btn size={mobile ? "lg" : "sm"} className="mt-1" onClick={() => onMethodChange(null)}>
              {S.showAll}
            </Btn>
          }
        />
      )
  else if (mobile)
    body = (
      <ul className="flex flex-col gap-2" aria-label={S.historyAria}>
        {list.rows.map((s) => (
          <li key={s.id} className={cn(cardClass, "flex flex-col gap-2 px-3.5 py-3 text-[13px]")}>
            <span className="flex items-start justify-between gap-2">
              <span className="flex min-w-0 flex-col gap-0.5">
                <b className="truncate text-[13.5px] text-heading">{s.payment_method_name}</b>
                <span className="text-xs text-text-3 tabular-nums">
                  {short(s.settled_date)} · {periodText(s)}
                </span>
              </span>
              <Btn size="sm" className="h-10 shrink-0" disabled={!today} onClick={() => setEditing(s)}>
                <Pencil className="size-3.5" aria-hidden />
                {S.edit}
              </Btn>
            </span>
            <Line label={S.colExpectedShort}>
              <Money value={s.expected_amount} />
            </Line>
            <Line label={S.colReceived}>
              <Money value={s.amount_received} className="font-bold" />
            </Line>
            <Line label={S.colDifference}>
              <DifferenceFigure value={s.difference} />
            </Line>
            {s.note && (
              <p dir="auto" className="text-xs text-text-2">
                {s.note}
              </p>
            )}
            <Collapsible
              label={S.ordersToggle}
              className="border-t border-border pt-1.5"
              buttonClassName="min-h-11"
              onFirstOpen={() => {
                if (!details[s.id] || details[s.id].status === "error") loadDetail(s.id)
              }}
            >
              <SettlementOrders detail={details[s.id]} onRetry={() => loadDetail(s.id)} mobile />
            </Collapsible>
          </li>
        ))}
      </ul>
    )
  else
    body = (
      <section aria-label={S.historyAria} className={cn(cardClass, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col" className="w-10">
                  <span className="sr-only">{S.ordersOf}</span>
                </th>
                <th scope="col">{S.colSettledDate}</th>
                <th scope="col">{S.colMethod}</th>
                <th scope="col">{S.colPeriod}</th>
                <th scope="col">{S.colExpectedShort}</th>
                <th scope="col">{S.colReceived}</th>
                <th scope="col">{S.colDifference}</th>
                <th scope="col" className="w-full">
                  {S.colNote}
                </th>
                <th scope="col">
                  <span className="sr-only">{S.colActions}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.rows.map((s) => {
                const open = expanded.has(s.id)
                return (
                  <React.Fragment key={s.id}>
                    <tr className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap">
                      <td>
                        <Btn
                          variant="ghost"
                          size="sm"
                          className="size-8 px-0"
                          aria-expanded={open}
                          aria-label={`${S.expand}: ${S.settlementNo(s.id)}`}
                          onClick={() => toggle(s.id)}
                        >
                          <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
                        </Btn>
                      </td>
                      <td className="text-text-2 tabular-nums">{short(s.settled_date)}</td>
                      <td className="max-w-[180px] truncate font-semibold">{s.payment_method_name}</td>
                      <td className="text-text-2">{periodText(s)}</td>
                      <td>
                        <Money value={s.expected_amount} />
                      </td>
                      <td className="font-bold">
                        <Money value={s.amount_received} />
                      </td>
                      <td>
                        <DifferenceFigure value={s.difference} />
                      </td>
                      <td dir="auto" className={cn("max-w-[260px] truncate", !s.note && "text-text-3")}>
                        {s.note || S.nil}
                      </td>
                      <td>
                        <Btn size="sm" disabled={!today} onClick={() => setEditing(s)}>
                          <Pencil className="size-3.5" aria-hidden />
                          {S.edit}
                        </Btn>
                      </td>
                    </tr>
                    {open && (
                      <tr>
                        <td colSpan={9} className="border-b border-border bg-surface-2 px-4 py-3">
                          <div className="mb-2 text-xs font-semibold text-text-3">{S.ordersOf}</div>
                          <SettlementOrders detail={details[s.id]} onRetry={() => loadDetail(s.id)} mobile={false} />
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
      {methodMenu}
      {body}
      {today && (
        <EditDialog settlement={editing} today={today} mobile={mobile} onClose={() => setEditing(null)} onSaved={onSaved} />
      )}
    </div>
  )
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <span className="flex items-center justify-between gap-2">
      <span className="text-text-3">{label}</span>
      {children}
    </span>
  )
}

/** The saved difference (received − expected, from the API), signed, coloured and worded. */
function DifferenceFigure({ value }: { value: number }) {
  const kind = differenceKind(value)
  return (
    <span className="inline-flex flex-col items-end gap-0.5 md:items-start">
      <b className={differenceTone(value)}>{signedMoney(value)}</b>
      <span className="text-[11px] text-text-3">{kind === "over" ? S.over : kind === "under" ? S.under : S.equal}</span>
    </span>
  )
}

function SettlementOrders({ detail, onRetry, mobile }: { detail: Detail | undefined; onRetry: () => void; mobile: boolean }) {
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
        {S.ordersErrorTitle}
        <Btn size="sm" onClick={onRetry}>
          <RotateCw className="size-3.5" aria-hidden />
          {S.retry}
        </Btn>
      </div>
    )
  const orders = detail.settlement.orders
  if (mobile)
    return (
      <ul className="flex flex-col gap-2 pt-1">
        {orders.map((o) => (
          <li key={o.id} className="flex flex-col gap-1 rounded-lg border border-border px-3 py-2 text-[13px]">
            <span className="flex items-center justify-between gap-2">
              <OrderLink id={o.id} invoice={o.invoice_number} />
              <StatusBadge status={o.status} />
            </span>
            <span className="text-xs text-text-3 tabular-nums">
              {S.colPaidDate}: {short(o.paid_date)}
            </span>
            <Line label={S.colCustomerTotal}>
              <Money value={o.customer_total} />
            </Line>
            <Line label={S.colFee}>
              <Money value={o.transaction_fee} />
            </Line>
            <Line label={S.colExpected}>
              <Money value={o.expected_amount} className="font-bold" />
            </Line>
          </li>
        ))}
      </ul>
    )
  return (
    <table className="w-full border-separate border-spacing-0 rounded-lg bg-card text-[13px]">
      <thead>
        <tr className="text-xs font-semibold text-text-3 [&>th]:h-9 [&>th]:border-b [&>th]:border-border [&>th]:px-3 [&>th]:text-start [&>th]:whitespace-nowrap">
          <th scope="col">{S.colInvoice}</th>
          <th scope="col">{S.colPaidDate}</th>
          <th scope="col">{S.colCustomerTotal}</th>
          <th scope="col">{S.colFee}</th>
          <th scope="col">{S.colExpected}</th>
          <th scope="col" className="w-full">
            {S.colStatus}
          </th>
        </tr>
      </thead>
      <tbody>
        {orders.map((o) => (
          <tr key={o.id} className="[&>td]:h-10 [&>td]:border-b [&>td]:border-border [&>td]:px-3 [&>td]:whitespace-nowrap last:[&>td]:border-b-0">
            <td>
              <OrderLink id={o.id} invoice={o.invoice_number} />
            </td>
            <td className="text-text-2 tabular-nums">{short(o.paid_date)}</td>
            <td>
              <Money value={o.customer_total} />
            </td>
            <td className="text-text-2">
              <Money value={o.transaction_fee} />
            </td>
            <td className="font-semibold">
              <Money value={o.expected_amount} />
            </td>
            <td>
              <StatusBadge status={o.status} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function OrderLink({ id, invoice }: { id: number; invoice: string | null }) {
  return (
    <Link
      href={orderHref(id)}
      dir="ltr"
      className="font-mono text-[12.5px] font-semibold text-heading outline-none hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/30"
    >
      {invoice ?? S.nil}
    </Link>
  )
}
