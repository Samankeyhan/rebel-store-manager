"use client"

import * as React from "react"
import Link from "next/link"
import { ChevronDown, CircleCheck } from "lucide-react"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { Money } from "@/components/common/money"
import { badgeBase } from "@/components/common/status"
import { orderHref } from "@/components/orders/list/orders-table"
import { ruleText } from "@/components/payment-methods/copy"
import { Alert, Btn, btnClass, cardClass } from "@/components/record-sale/primitives"
import {
  ApiError,
  getPendingSettlements,
  listOrders,
  type PendingGroup,
  type PendingMethod,
  type PendingMonthGroup,
  type PendingOrder,
  type Settlement,
} from "@/lib/api"
import { formatJalali } from "@/lib/jalali"
import { attachReferences, groupTitle, isMonthGroup as isMonthLike, referenceMap, selectedExpected } from "@/lib/settlements"
import { cn } from "@/lib/utils"
import { S, differenceText } from "./copy"
import { RecordDialog, type RecordTarget } from "./record-dialog"

type Row = PendingOrder & { payment_reference: string | null }
type Data =
  | { status: "loading" }
  | { status: "error"; code: string }
  | { status: "ready"; methods: PendingMethod[]; refs: Map<number, string | null> | null }
type Selection = { methodId: number; ids: Set<number> } | null

const MONTHLY = "DAY_OF_NEXT_MONTH"
const short = (iso: string) => formatJalali(iso, "yyyy/MM/dd")
const isMonthGroup = (g: PendingGroup): g is PendingMonthGroup => isMonthLike(g)
const groupKey = (g: PendingGroup) => (isMonthGroup(g) ? `m${g.jalali_year}-${g.jalali_month}` : `d${g.expected_date}`)

function errorCode(e: unknown): string {
  return e instanceof ApiError && e.status > 0 ? `SETTLEMENTS_${e.status}` : "NET_TIMEOUT"
}

/**
 * «در انتظار»: one card per method (backend order), its pending orders in
 * groups. IMMEDIATE / DAYS_AFTER: pick any orders of ONE method (picking in
 * another method starts over), across its date groups. DAY_OF_NEXT_MONTH:
 * one button per ended month, no picking. Every sum shown is the backend's,
 * except the selection total, a labelled preview.
 */
export function PendingTab({
  today,
  mobile,
  onToast,
}: {
  today: string | null
  mobile: boolean
  onToast: (text: string) => void
}) {
  const [data, setData] = React.useState<Data>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)
  const [selection, setSelection] = React.useState<Selection>(null)
  const [target, setTarget] = React.useState<RecordTarget | null>(null)

  React.useEffect(() => {
    let cancelled = false
    Promise.all([
      getPendingSettlements(),
      // payment_reference isn't on pending orders (backend gap): join it from
      // the order list, which has no limit and the same pending filter.
      listOrders({ settlement_state: "pending" }).then(referenceMap, () => null),
    ]).then(
      ([methods, refs]) => !cancelled && setData({ status: "ready", methods, refs }),
      (e: unknown) => !cancelled && setData({ status: "error", code: errorCode(e) })
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const reload = () => {
    setData({ status: "loading" })
    setAttempt((a) => a + 1)
  }
  /** Quietly, after a save or a stale-list error: the current list stays until the new one arrives. */
  const refresh = React.useCallback(() => setAttempt((a) => a + 1), [])

  if (data.status === "loading") return <LoadingBlock mobile={mobile} label={S.loadingAria} />
  if (data.status === "error")
    return <ErrorBlock title={S.pendingErrorTitle} body={S.errorBody} retry={S.retry} onRetry={reload} mobile={mobile} />
  if (data.methods.length === 0)
    return (
      <StateShell
        icon={CircleCheck}
        mobile={mobile}
        title={S.pendingEmptyTitle}
        body={S.pendingEmptyBody}
        action={
          <Link href="/orders" className={btnClass("outline", mobile ? "lg" : "md", "mt-1")}>
            {S.toOrders}
          </Link>
        }
      />
    )

  const refs = data.refs ?? new Map<number, string | null>()
  const ordersOf = (m: PendingMethod): Row[] => attachReferences(m.groups.flatMap((g) => g.orders), refs)

  // The selection, limited to orders still pending (a refresh may drop some).
  const selMethod = selection ? data.methods.find((m) => m.payment_method_id === selection.methodId) : undefined
  const selOrders = selMethod && selection ? ordersOf(selMethod).filter((o) => selection.ids.has(o.id)) : []
  const selIds = new Set(selOrders.map((o) => o.id))
  const selTotal = selMethod ? selectedExpected(selOrders, selIds) : 0
  const active = selMethod && selOrders.length > 0 ? { method: selMethod, count: selOrders.length, total: selTotal } : null

  const setPicked = (methodId: number, ids: number[], on: boolean) =>
    setSelection((s) => {
      const next = new Set(s && s.methodId === methodId ? s.ids : [])
      for (const id of ids) {
        if (on) next.add(id)
        else next.delete(id)
      }
      return next.size ? { methodId, ids: next } : null
    })

  const openOrders = () => {
    if (!active) return
    setTarget({ kind: "orders", method: active.method, orderIds: selOrders.map((o) => o.id), expected: active.total })
  }

  const onSaved = (s: Settlement) => {
    setTarget(null)
    setSelection(null)
    refresh()
    onToast(S.toastSaved(differenceText(s.difference)))
  }

  const selectionSummary = active && (
    <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[13px]">
      <b>{S.selected(active.count)}</b>
      <span className="text-text-3">·</span>
      <span className="text-text-2">{S.selectedSum}:</span>
      {active.total === null ? <span className="text-loss">{S.totalTooLarge}</span> : <Money value={active.total} className="font-bold" />}
      <span className="rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-3">{S.preview}</span>
    </span>
  )

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-5", mobile && active && "pb-28")}>
      {!mobile && <p className="text-[13px] text-text-3">{S.intro}</p>}
      {data.refs === null && (
        <Alert tone="warn" icon="triangle">
          {S.refsFailed}
        </Alert>
      )}
      {data.methods.map((m) => (
        <MethodCard
          key={m.payment_method_id}
          method={m}
          rows={ordersOf(m)}
          selected={selMethod?.payment_method_id === m.payment_method_id ? selIds : null}
          canSettle={today != null}
          mobile={mobile}
          onPick={(ids, on) => setPicked(m.payment_method_id, ids, on)}
          onSettleMonth={(group) => setTarget({ kind: "month", method: m, group })}
          footer={
            !mobile && active && active.method.payment_method_id === m.payment_method_id ? (
              <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-b-xl border-t border-border bg-card px-5 py-3 shadow-[0_-6px_14px_rgba(18,22,38,.06)]">
                {selectionSummary}
                <span className="flex items-center gap-2">
                  <Btn size="sm" variant="ghost" onClick={() => setSelection(null)}>
                    {S.clearSelection}
                  </Btn>
                  <Btn variant="primary" disabled={today == null} onClick={openOrders}>
                    {S.settle}
                  </Btn>
                </span>
              </div>
            ) : null
          }
        />
      ))}

      {mobile && active && (
        <div className="fixed inset-x-0 bottom-0 z-30 flex flex-col gap-2 border-t border-border bg-card px-4 pt-3 pb-[max(20px,env(safe-area-inset-bottom))]">
          <div className="text-[12px] text-text-3">{active.method.name}</div>
          {selectionSummary}
          <div className="flex gap-2">
            <Btn variant="primary" size="lg" className="grow" disabled={today == null} onClick={openOrders}>
              {S.settle}
            </Btn>
            <Btn size="lg" onClick={() => setSelection(null)}>
              {S.clearSelection}
            </Btn>
          </div>
        </div>
      )}

      {today && (
        <RecordDialog
          target={target}
          today={today}
          mobile={mobile}
          onClose={() => setTarget(null)}
          onSaved={onSaved}
          onStale={refresh}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------- parts

const badgeTone = {
  overdue: "bg-loss-soft text-loss",
  due: "bg-warn-soft text-warn",
  open: "bg-surface-2 text-text-2",
}

function GroupBadges({ group }: { group: PendingGroup }) {
  return (
    <>
      {group.overdue ? (
        <span className={cn(badgeBase, badgeTone.overdue)}>{S.overdue}</span>
      ) : group.due ? (
        <span className={cn(badgeBase, badgeTone.due)}>{S.dueToday}</span>
      ) : null}
      {isMonthGroup(group) && !group.month_ended && <span className={cn(badgeBase, badgeTone.open)}>{S.monthOpen}</span>}
    </>
  )
}

function InactiveBadge() {
  return (
    <span className={cn(badgeBase, "border border-dashed border-border-strong bg-card text-text-2 before:hidden")}>{S.inactive}</span>
  )
}

/** A checkbox that can show "some selected". */
function Check({
  checked,
  indeterminate = false,
  onChange,
  label,
  className,
}: {
  checked: boolean
  indeterminate?: boolean
  onChange: (on: boolean) => void
  label: string
  className?: string
}) {
  const ref = React.useRef<HTMLInputElement>(null)
  React.useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate
  }, [indeterminate])
  return (
    <input
      ref={ref}
      type="checkbox"
      aria-label={label}
      className={cn("size-4 cursor-pointer accent-primary", className)}
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
    />
  )
}

function groupState(group: PendingGroup, selected: Set<number> | null) {
  const n = selected ? group.orders.filter((o) => selected.has(o.id)).length : 0
  return { all: n > 0 && n === group.orders.length, some: n > 0 && n < group.orders.length }
}

function MonthButton({ group, disabled, onClick, mobile }: { group: PendingGroup; disabled: boolean; onClick: () => void; mobile: boolean }) {
  if (!isMonthGroup(group)) return null
  return (
    <Btn
      variant={group.can_settle ? "primary" : "outline"}
      size={mobile ? "lg" : "sm"}
      className={mobile ? "w-full" : undefined}
      disabled={disabled || !group.can_settle}
      onClick={onClick}
    >
      {S.settleMonth}
    </Btn>
  )
}

function MethodCard({
  method,
  rows,
  selected,
  canSettle,
  mobile,
  onPick,
  onSettleMonth,
  footer,
}: {
  method: PendingMethod
  rows: Row[]
  selected: Set<number> | null
  canSettle: boolean
  mobile: boolean
  onPick: (ids: number[], on: boolean) => void
  onSettleMonth: (group: PendingMonthGroup) => void
  footer: React.ReactNode
}) {
  const monthly = method.settlement_rule === MONTHLY
  const byId = new Map(rows.map((r) => [r.id, r]))
  const headingId = `pm-${method.payment_method_id}`

  const header = (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3.5 md:px-5 md:py-4">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="flex flex-wrap items-center gap-2">
          <h2 id={headingId} className="text-base leading-[26px] font-bold text-heading">
            {method.name}
          </h2>
          {method.is_active !== 1 && <InactiveBadge />}
        </span>
        <span className="text-xs text-text-3">{ruleText(method.settlement_rule, method.settlement_days ?? null)}</span>
      </div>
      <span className="flex items-baseline gap-1.5 text-[13px]">
        <span className="text-text-3">{S.remaining}</span>
        <Money value={method.total_expected} className="text-[15px] font-bold" />
      </span>
    </div>
  )

  if (mobile) {
    return (
      <section aria-labelledby={headingId} className={cardClass}>
        {header}
        {monthly && <p className="px-4 pt-3 text-xs text-text-3">{S.monthlyHelp}</p>}
        <div className="flex flex-col gap-2 p-3">
          {method.groups.map((g) => (
            <MobileGroup
              key={groupKey(g)}
              group={g}
              monthly={monthly}
              rows={g.orders.map((o) => byId.get(o.id) ?? { ...o, payment_reference: null })}
              selected={selected}
              canSettle={canSettle}
              onPick={onPick}
              onSettleMonth={onSettleMonth}
            />
          ))}
        </div>
      </section>
    )
  }

  return (
    <section aria-labelledby={headingId} className={cn(cardClass, "flex flex-col")}>
      {header}
      {monthly && <p className="px-5 pt-3 text-xs text-text-3">{S.monthlyHelp}</p>}
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[13.5px]">
          <thead>
            <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
              {!monthly && (
                <th scope="col" className="w-10">
                  <span className="sr-only">{S.selectedSum}</span>
                </th>
              )}
              <th scope="col">{S.colInvoice}</th>
              <th scope="col">{S.colPaidDate}</th>
              <th scope="col">{S.colCustomerTotal}</th>
              <th scope="col">{S.colFee}</th>
              <th scope="col">{S.colExpected}</th>
              <th scope="col" className="w-full">
                {S.colReference}
              </th>
            </tr>
          </thead>
          {method.groups.map((g) => {
            const title = groupTitle(g)
            const { all, some } = groupState(g, selected)
            const ids = g.orders.map((o) => o.id)
            return (
              <tbody key={groupKey(g)}>
                <tr className="[&>td]:border-b [&>td]:border-border [&>td]:bg-surface-2 [&>td]:px-4 [&>td]:py-2.5 [&>td]:align-middle">
                  {!monthly && (
                    <td>
                      <Check checked={all} indeterminate={some} label={S.selectGroup(title)} onChange={(on) => onPick(ids, on)} />
                    </td>
                  )}
                  <td colSpan={2}>
                    <span className="flex flex-col gap-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <b className="text-heading">{isMonthGroup(g) ? title : S.expectedOn(title)}</b>
                        <GroupBadges group={g} />
                      </span>
                      <span className="text-xs text-text-3">
                        {isMonthGroup(g) ? `${S.settleOn(formatJalali(g.expected_date))} · ` : ""}
                        {S.orders(g.order_count)}
                      </span>
                      {isMonthGroup(g) && !g.can_settle && (
                        <span className="text-xs text-text-3">{S.settleAfter(formatJalali(g.month_last_day))}</span>
                      )}
                    </span>
                  </td>
                  <td className="whitespace-nowrap text-text-2">
                    <Money value={g.customer_total_sum} />
                  </td>
                  <td className="whitespace-nowrap text-text-2">
                    <Money value={g.fee_sum} />
                  </td>
                  <td className="whitespace-nowrap font-bold">
                    <Money value={g.expected_amount} />
                  </td>
                  <td>
                    {isMonthGroup(g) && (
                      <MonthButton group={g} mobile={false} disabled={!canSettle} onClick={() => onSettleMonth(g)} />
                    )}
                  </td>
                </tr>
                {g.orders.map((o) => {
                  const r = byId.get(o.id)
                  const on = selected?.has(o.id) ?? false
                  return (
                    <tr
                      key={o.id}
                      className={cn(
                        "[&>td]:h-[48px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap",
                        on ? "[&>td]:bg-navy-soft" : "hover:[&>td]:bg-surface-2"
                      )}
                    >
                      {!monthly && (
                        <td>
                          <Check checked={on} label={S.selectOrder(o.invoice_number ?? S.nil)} onChange={(v) => onPick([o.id], v)} />
                        </td>
                      )}
                      <td>
                        <InvoiceLink id={o.id} invoice={o.invoice_number} />
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
                        <Reference value={r?.payment_reference ?? null} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            )
          })}
        </table>
      </div>
      {footer}
    </section>
  )
}

function InvoiceLink({ id, invoice }: { id: number; invoice: string | null }) {
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

function Reference({ value }: { value: string | null }) {
  return value ? (
    <span dir="auto" className="font-mono text-[12.5px] text-text-2">
      {value}
    </span>
  ) : (
    <span className="text-text-3">{S.nil}</span>
  )
}

function MobileGroup({
  group,
  monthly,
  rows,
  selected,
  canSettle,
  onPick,
  onSettleMonth,
}: {
  group: PendingGroup
  monthly: boolean
  rows: Row[]
  selected: Set<number> | null
  canSettle: boolean
  onPick: (ids: number[], on: boolean) => void
  onSettleMonth: (group: PendingMonthGroup) => void
}) {
  const [open, setOpen] = React.useState(false)
  const id = React.useId()
  const title = groupTitle(group)
  const { all, some } = groupState(group, selected)
  return (
    <div className="flex flex-col rounded-[10px] border border-border">
      <div className="flex items-center gap-3 px-3 py-2.5">
        {!monthly && (
          <span className="flex size-11 shrink-0 items-center justify-center -my-2 -ms-2">
            <Check
              checked={all}
              indeterminate={some}
              label={S.selectGroup(title)}
              onChange={(on) => onPick(group.orders.map((o) => o.id), on)}
              className="size-5"
            />
          </span>
        )}
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen(!open)}
          className="flex min-h-11 min-w-0 grow cursor-pointer items-center justify-between gap-2 text-start outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
        >
          <span className="flex min-w-0 flex-col gap-1">
            <span className="flex flex-wrap items-center gap-1.5">
              <b className="text-[13.5px] text-heading">{isMonthGroup(group) ? title : S.expectedOn(title)}</b>
              <GroupBadges group={group} />
            </span>
            <span className="flex flex-wrap items-center gap-x-1.5 text-xs text-text-3">
              {S.orders(group.order_count)}
              <span>·</span>
              <Money value={group.expected_amount} className="font-semibold text-foreground" />
            </span>
          </span>
          <ChevronDown className={cn("size-4 shrink-0 text-text-3 transition-transform", open && "rotate-180")} aria-hidden />
        </button>
      </div>
      {isMonthGroup(group) && (
        <div className="flex flex-col gap-1.5 border-t border-border px-3 py-2.5">
          <span className="text-xs text-text-3">{S.settleOn(formatJalali(group.expected_date))}</span>
          <MonthButton group={group} mobile disabled={!canSettle} onClick={() => onSettleMonth(group)} />
          {!group.can_settle && <span className="text-xs text-text-3">{S.settleAfter(formatJalali(group.month_last_day))}</span>}
        </div>
      )}
      <div id={id} hidden={!open}>
        {open && (
          <ul className="flex flex-col gap-2 border-t border-border p-2">
            {rows.map((o) => {
              const on = selected?.has(o.id) ?? false
              return (
                <li
                  key={o.id}
                  className={cn("flex gap-2.5 rounded-lg border border-border px-3 py-2.5", on && "border-heading bg-navy-soft")}
                >
                  {!monthly && (
                    <span className="flex size-11 shrink-0 items-center justify-center -my-2 -ms-2">
                      <Check checked={on} label={S.selectOrder(o.invoice_number ?? S.nil)} onChange={(v) => onPick([o.id], v)} className="size-5" />
                    </span>
                  )}
                  <div className="flex min-w-0 grow flex-col gap-1 text-[13px]">
                    <span className="flex items-center justify-between gap-2">
                      <InvoiceLink id={o.id} invoice={o.invoice_number} />
                      <Reference value={o.payment_reference} />
                    </span>
                    <span className="text-xs text-text-3 tabular-nums">
                      {S.colPaidDate}: {short(o.paid_date)}
                    </span>
                    <MoneyLine label={S.colCustomerTotal} value={o.customer_total} />
                    <MoneyLine label={S.colFee} value={o.transaction_fee} />
                    <MoneyLine label={S.colExpected} value={o.expected_amount} strong />
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

function MoneyLine({ label, value, strong }: { label: string; value: number; strong?: boolean }) {
  return (
    <span className="flex items-center justify-between gap-2">
      <span className="text-text-3">{label}</span>
      <Money value={value} className={strong ? "font-bold" : undefined} />
    </span>
  )
}
