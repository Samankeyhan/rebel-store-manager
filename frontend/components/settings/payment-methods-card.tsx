"use client"

import * as React from "react"
import { Ban, CreditCard, History, Loader2, Pencil, Plus, Star } from "lucide-react"
import { ConfirmShell, Effect } from "@/components/orders/detail/confirm-shell"
import { Switch } from "@/components/products/drawer-shell"
import { PM, feeText, ruleText } from "@/components/payment-methods/copy"
import { CHANNEL_IDS, CHANNELS, type Channel } from "@/components/record-sale/copy"
import { Alert, Btn, cardClass } from "@/components/record-sale/primitives"
import { badgeBase } from "@/components/common/status"
import {
  ApiError,
  deactivatePaymentMethod,
  reactivatePaymentMethod,
  type PaymentMethod,
  type Settings,
} from "@/lib/api"
import { cn } from "@/lib/utils"
import { S, joinList } from "./copy"
import { PaymentMethodDrawer } from "./payment-method-drawer"

function ActiveBadge({ active }: { active: boolean }) {
  return (
    <span className={cn(badgeBase, active ? "bg-profit-soft text-profit" : "bg-surface-2 text-text-3")}>
      {active ? S.payActive : S.payInactive}
    </span>
  )
}

function PendingCount({ n }: { n: number }) {
  return n > 0 ? <span className="tabular-nums">{PM.pending(n)}</span> : <span className="text-text-3">{S.payNoPending}</span>
}

/**
 * [4] روش‌های پرداخت: add, edit, deactivate and reactivate payment methods.
 * Each action saves immediately; it is not part of the settings draft (the
 * channel default method is, in the channels card).
 */
export function PaymentMethodsCard({
  methods,
  settings,
  mobile,
  onChanged,
  onRefresh,
  onToast,
}: {
  methods: PaymentMethod[]
  /** Saved settings: which channels use a method as their default. */
  settings: Settings
  mobile: boolean
  /** A method was created or changed: replace it in the list. */
  onChanged: (method: PaymentMethod) => void
  onRefresh: () => Promise<void>
  onToast: (text: string) => void
}) {
  const [showInactive, setShowInactive] = React.useState(false)
  const [drawer, setDrawer] = React.useState<{ open: boolean; method: PaymentMethod | null }>({ open: false, method: null })
  const [deactivating, setDeactivating] = React.useState<PaymentMethod | null>(null)
  const [busyId, setBusyId] = React.useState<number | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const inactiveCount = methods.filter((m) => m.is_active === 0).length
  const shown = methods.filter((m) => showInactive || m.is_active === 1)
  const defaultOf = (id: number): Channel[] =>
    CHANNEL_IDS.filter((c) => settings.channels[c]?.default_payment_method_id === id)

  const act = async (m: PaymentMethod, request: (id: number) => Promise<PaymentMethod>, toast: string) => {
    setBusyId(m.id)
    setError(null)
    try {
      onChanged(await request(m.id))
      setDeactivating(null)
      onToast(toast)
    } catch (e) {
      setDeactivating(null)
      setError(S.payActionFailed(e instanceof Error ? e.message : String(e)))
      if (e instanceof ApiError && e.status === 404) await onRefresh().catch(() => {})
    } finally {
      setBusyId(null)
    }
  }

  const edit = (m: PaymentMethod | null) => setDrawer({ open: true, method: m })

  const rowActions = (m: PaymentMethod) => (
    <div className="flex items-center justify-end gap-1.5">
      <Btn size="sm" variant="ghost" aria-label={S.payEditAria(m.name)} disabled={busyId === m.id} onClick={() => edit(m)}>
        <Pencil className="size-3.5" />
        {!mobile && S.payEdit}
      </Btn>
      {m.is_active === 1 ? (
        <Btn size="sm" variant="ghost" className="text-loss" disabled={busyId === m.id} onClick={() => setDeactivating(m)}>
          {S.payDeactivate}
        </Btn>
      ) : (
        <Btn
          size="sm"
          variant="ghost"
          disabled={busyId === m.id}
          aria-busy={busyId === m.id || undefined}
          onClick={() => act(m, reactivatePaymentMethod, S.payReactivated(m.name))}
        >
          {busyId === m.id && <Loader2 className="size-3.5 animate-spin" />}
          {S.payReactivate}
        </Btn>
      )}
    </div>
  )

  const header = (
    <div className={cn("flex flex-wrap items-center justify-between gap-3 border-b border-border", mobile ? "px-3.5 py-3" : "px-5 py-4")}>
      <div className="flex min-w-0 flex-col gap-0.5">
        <h2 id="st4" className={cn("font-bold text-heading", mobile ? "text-sm" : "text-base leading-[26px]")}>
          {S.payTitle}
        </h2>
        {!mobile && <span className="text-xs text-text-3">{S.payCaption}</span>}
      </div>
      <div className="flex items-center gap-3">
        {inactiveCount > 0 && (
          <label className="flex items-center gap-2 text-xs text-text-2">
            <span id="pm-show-inactive" className="sr-only">
              {S.payShowInactive}
            </span>
            <Switch checked={showInactive} onChange={setShowInactive} labelledBy="pm-show-inactive" />
            <span aria-hidden>{S.payShowInactive}</span>
          </label>
        )}
        <Btn size="sm" variant="primary" onClick={() => edit(null)}>
          <Plus className="size-4" />
          {S.payAdd}
        </Btn>
      </div>
    </div>
  )

  const empty = (
    <div className="flex flex-col items-center gap-2 px-5 py-8 text-center">
      <CreditCard className="size-8 text-text-3" aria-hidden />
      <b className="text-sm">{S.payEmptyTitle}</b>
      <span className="max-w-[420px] text-xs leading-[19px] text-text-3">{S.payEmptyBody}</span>
    </div>
  )

  const list = mobile ? (
    <ul className="flex flex-col">
      {shown.map((m) => (
        <li key={m.id} className="flex flex-col gap-1.5 border-t border-border px-3.5 py-3 first:border-t-0">
          <div className="flex items-center justify-between gap-2">
            <b className="min-w-0 truncate text-[13.5px]">{m.name}</b>
            <ActiveBadge active={m.is_active === 1} />
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-text-2">
            <span>{feeText(m.fee_bps, m.fee_fixed)}</span>
            <span>{PM.settleLine(m.settlement_rule, m.settlement_days)}</span>
            {m.pending_order_count > 0 && <PendingCount n={m.pending_order_count} />}
          </div>
          {rowActions(m)}
        </li>
      ))}
    </ul>
  ) : (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-0 text-[13.5px]">
        <thead>
          <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
            <th scope="col">{S.payColName}</th>
            <th scope="col">{S.payColFee}</th>
            <th scope="col">{S.payColRule}</th>
            <th scope="col">{S.payColPending}</th>
            <th scope="col">
              <span className="sr-only">{S.payColActions}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {shown.map((m, i) => (
            <tr
              key={m.id}
              className={cn(
                "[&>td]:h-14 [&>td]:px-4 [&>td]:whitespace-nowrap",
                i < shown.length - 1 && "[&>td]:border-b [&>td]:border-border",
                m.is_active === 0 && "text-text-3"
              )}
            >
              <td>
                <span className="flex items-center gap-2">
                  <b className="max-w-[200px] truncate">{m.name}</b>
                  {m.is_active === 0 && <ActiveBadge active={false} />}
                  {defaultOf(m.id).length > 0 && (
                    <Star className="size-3.5 text-text-3" aria-label={S.colMethod} />
                  )}
                </span>
              </td>
              <td>{feeText(m.fee_bps, m.fee_fixed)}</td>
              <td>{ruleText(m.settlement_rule, m.settlement_days)}</td>
              <td>
                <PendingCount n={m.pending_order_count} />
              </td>
              <td>{rowActions(m)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  const target = deactivating
  const targetDefaults = target ? defaultOf(target.id) : []

  return (
    <section id="pay" className={cn(cardClass, "scroll-mt-6 overflow-hidden")} aria-labelledby="st4">
      {header}
      {error && (
        <div className={mobile ? "px-3.5 pt-3" : "px-5 pt-4"}>
          <Alert tone="err">{error}</Alert>
        </div>
      )}
      {methods.length === 0 ? empty : list}
      <PaymentMethodDrawer
        open={drawer.open}
        method={drawer.method}
        mobile={mobile}
        onClose={() => setDrawer((d) => ({ ...d, open: false }))}
        onSaved={(saved, created) => {
          onChanged(saved)
          setDrawer({ open: false, method: saved })
          onToast(created ? S.payCreated(saved.name) : S.paySaved(saved.name))
        }}
        onStale={onRefresh}
      />
      <ConfirmShell
        open={target != null}
        onOpenChange={(o) => !o && setDeactivating(null)}
        mobile={mobile}
        busy={target != null && busyId === target.id}
        icon={Ban}
        title={target ? S.payDeactivateTitle(target.name) : ""}
        subtitle={S.payDeactivateSubtitle}
        confirmLabel={S.payDeactivate}
        confirmIcon={Ban}
        onConfirm={() => target && act(target, deactivatePaymentMethod, S.payDeactivated(target.name))}
        width={500}
      >
        <Effect tone="flat" icon={Ban}>
          {S.payEffNew}
        </Effect>
        <Effect tone="flat" icon={History}>
          {S.payEffExisting}
          {target && target.pending_order_count > 0 && ` (${PM.pending(target.pending_order_count)})`}
        </Effect>
        {targetDefaults.length > 0 && (
          <Effect tone="flat" icon={Star}>
            {S.payEffDefault(joinList(targetDefaults.map((c) => `«${CHANNELS[c].name}»`), 5))}
          </Effect>
        )}
      </ConfirmShell>
    </section>
  )
}
