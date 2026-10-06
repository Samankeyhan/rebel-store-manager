"use client"

import * as React from "react"
import Link from "next/link"
import { ChevronDown, Loader2, RotateCcw } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { DateField } from "@/components/common/date-field"
import { Money } from "@/components/common/money"
import { PM, feeText } from "@/components/payment-methods/copy"
import type { PaymentMethod } from "@/lib/api"
import { cn } from "@/lib/utils"
import { T } from "./copy"
import type { Summary } from "./derive"
import { moneyProps } from "./money-field"
import { Btn, Help, InlineMessage, Label, MoneyInput, inputClass } from "./primitives"
import { orderDay, paidDay, type Action, type FormState, type ResolvedMethod } from "./state"
import type { FeePreview } from "./use-fee-preview"

const NONE = "none"

/** Everything the payment fields need beyond the form state. */
export type PaymentUi = {
  /** Every method (inactive included), or null when the list couldn't be loaded. */
  methods: PaymentMethod[] | null
  resolved: ResolvedMethod
  preview: FeePreview
  /** The store's calendar day (settings.timezone). */
  today: string
  retryMethods: () => void
  methodsLoading: boolean
}

type Props = { state: FormState; dispatch: React.Dispatch<Action>; payment: PaymentUi; mobile: boolean }

/** The server refused this field on the last submit. */
function issueFor(state: FormState, field: "paid_date" | "payment_method_id" | "transaction_fee"): string | null {
  const issue = state.serverIssue
  return issue?.kind === "payment" && issue.field === field ? issue.message : null
}

/**
 * «روش پرداخت»: active methods plus «بدون روش», preselected from the channel
 * default. An inactive default is shown (warn) but can't be chosen and blocks
 * saving; a list that failed to load offers a retry. Under it, the rule in
 * words — never a date computed in the browser.
 */
export function PaymentMethodField({ state, dispatch, payment, mobile }: Props) {
  const { methods, resolved } = payment
  const serverError = issueFor(state, "payment_method_id")

  if (methods === null && resolved.kind !== "none") {
    // The channel has a default but the methods couldn't be loaded: retry, never send "no method".
    return (
      <div className="flex flex-col gap-1.5">
        <Label>{T.methodLabel}</Label>
        <InlineMessage severity="error">
          {T.methodsFailed}
          <button
            type="button"
            className="ms-1 inline-flex cursor-pointer items-center gap-1 font-bold text-heading hover:text-primary"
            disabled={payment.methodsLoading}
            onClick={payment.retryMethods}
          >
            {payment.methodsLoading ? <Loader2 className="size-3 animate-spin" /> : <RotateCcw className="size-3" />}
            {T.methodsRetry}
          </button>
        </InlineMessage>
      </div>
    )
  }
  if (methods !== null && methods.filter((m) => m.is_active === 1).length === 0 && resolved.kind === "none") {
    return (
      <div className="flex flex-col gap-1.5">
        <Label>{T.methodLabel}</Label>
        <Help>
          {T.noMethods}{" "}
          <Link href="/settings/#pay" className="font-bold text-heading hover:text-primary">
            {T.noMethodsLink}
          </Link>
        </Help>
      </div>
    )
  }

  const active = (methods ?? []).filter((m) => m.is_active === 1)
  const value = resolved.kind === "method" ? String(resolved.method.id) : resolved.kind === "none" ? NONE : ""
  const name =
    resolved.kind === "method"
      ? resolved.method.name
      : resolved.kind === "inactive"
        ? resolved.isDefault
          ? T.methodDefaultInactive(resolved.method.name)
          : PM.inactive(resolved.method.name)
        : resolved.kind === "none"
          ? T.methodNone
          : "—"
  const warn = resolved.kind === "inactive" || resolved.kind === "unavailable" || !!serverError
  const failedRefresh = methods === null

  return (
    <div className="flex flex-col gap-1.5">
      <Label>{T.methodLabel}</Label>
      <DropdownMenu dir="rtl">
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={T.methodAria}
            className={cn(
              inputClass(warn ? "error" : null),
              "flex cursor-pointer items-center justify-between gap-2",
              mobile && "h-11"
            )}
          >
            <span className="truncate">{name}</span>
            <ChevronDown className="size-3.5 shrink-0 text-text-3" aria-hidden />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[240px]">
          <DropdownMenuRadioGroup
            value={value}
            onValueChange={(v) =>
              dispatch({ type: "payment", choice: v === NONE ? { kind: "none" } : { kind: "method", id: Number(v) } })
            }
          >
            {active.map((m) => (
              <DropdownMenuRadioItem key={m.id} value={String(m.id)}>
                <span className="flex min-w-0 grow items-center justify-between gap-3">
                  <span className="truncate">{m.name}</span>
                  <span className="shrink-0 text-xs text-text-3">{feeText(m.fee_bps, m.fee_fixed)}</span>
                </span>
              </DropdownMenuRadioItem>
            ))}
            <DropdownMenuRadioItem value={NONE}>{T.methodNone}</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {resolved.kind === "inactive" ? (
        <InlineMessage severity="error">{PM.inactiveMethod(resolved.method.name)}</InlineMessage>
      ) : serverError ? (
        <InlineMessage severity="error">{serverError}</InlineMessage>
      ) : resolved.kind === "method" ? (
        <Help>{PM.settleLine(resolved.method.settlement_rule, resolved.method.settlement_days)}</Help>
      ) : null}
      {failedRefresh && (
        <InlineMessage severity="warn">
          {T.methodsFailed}
          <button type="button" className="ms-1 cursor-pointer font-bold text-heading" onClick={payment.retryMethods}>
            {T.methodsRetry}
          </button>
        </InlineMessage>
      )}
    </div>
  )
}

/**
 * The fee. With a method: automatic (the API's fee-preview, sent as null so
 * the server computes it) with «ویرایش دستی»; a manual override is a
 * MoneyInput with «بازگشت به خودکار». With no method: today's manual field.
 */
export function FeeField({
  state,
  dispatch,
  payment,
  summary,
  mobile,
}: Props & { summary: Summary }) {
  const serverError = issueFor(state, "transaction_fee")
  const input = (id: string) => (
    <MoneyInput
      id={id}
      {...moneyProps(state, dispatch, "fee", state.fee, (n) => dispatch({ type: "fee", value: n }))}
      tone={serverError ? "error" : null}
      className={mobile ? "h-11" : undefined}
    />
  )

  if (summary.feeSource === "none") {
    return (
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="sale-fee">{T.feeLabel}</Label>
        {input("sale-fee")}
        {serverError ? <InlineMessage severity="error">{serverError}</InlineMessage> : !mobile && <Help>{T.feeHelp}</Help>}
      </div>
    )
  }

  if (summary.feeSource === "manual") {
    return (
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="sale-fee">{T.feeManual}</Label>
          <Btn size="sm" variant="ghost" onClick={() => dispatch({ type: "feeMode", mode: "auto" })}>
            {T.feeBackAuto}
          </Btn>
        </div>
        {input("sale-fee")}
        {serverError ? <InlineMessage severity="error">{serverError}</InlineMessage> : <Help>{T.feeManualHelp}</Help>}
      </div>
    )
  }

  const preview = payment.preview
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <Label>{T.feeAuto}</Label>
        <Btn
          size="sm"
          variant="ghost"
          onClick={() =>
            dispatch({ type: "feeMode", mode: "manual", fee: preview.status === "ready" ? preview.fee : state.fee })
          }
        >
          {T.feeEdit}
        </Btn>
      </div>
      <div
        className={cn(
          "flex items-center justify-between gap-2 rounded-lg border border-dashed border-border-strong bg-surface-2 px-3",
          mobile ? "h-11" : "h-10"
        )}
        aria-live="polite"
      >
        {preview.status === "ready" ? (
          <b className="tabular-nums">
            <Money value={preview.fee} />
          </b>
        ) : preview.status === "error" ? (
          <span className="flex items-center gap-2 text-xs text-loss">
            {T.feeFailed}
            <button type="button" className="cursor-pointer font-bold text-heading" onClick={preview.retry}>
              {T.methodsRetry}
            </button>
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-xs text-text-3">
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            {T.feeComputing}
          </span>
        )}
      </div>
      {serverError ? <InlineMessage severity="error">{serverError}</InlineMessage> : !mobile && <Help>{T.feeAutoHelp}</Help>}
    </div>
  )
}

export function ReferenceField({ state, dispatch, mobile }: Omit<Props, "payment">) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="sale-ref" optional>
        {T.referenceLabel}
      </Label>
      <input
        id="sale-ref"
        value={state.reference}
        placeholder={T.referencePlaceholder}
        autoComplete="off"
        dir="auto"
        onChange={(e) => dispatch({ type: "reference", value: e.target.value })}
        className={inputClass(null, mobile ? "h-11" : undefined)}
      />
    </div>
  )
}

/**
 * «تاریخ پرداخت», only for PAID / COMPLETED. Shows exactly the day the server
 * will store: the picked day, else the order's own day (paidDay). Future days
 * (after the store's today) can't be picked.
 */
export function PaidDateField({ state, dispatch, payment, mobile }: Props) {
  if (state.status !== "PAID" && state.status !== "COMPLETED") return null
  const today = payment.today
  const serverError = issueFor(state, "paid_date")
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="sale-paid-date">{T.paidDateLabel}</Label>
      <DateField
        id="sale-paid-date"
        value={paidDay(state, today)}
        today={today}
        onChange={(d) => dispatch({ type: "paidDate", value: d === orderDay(state, today) ? null : d })}
        todayLabel={T.today}
        mobile={mobile}
      />
      {serverError ? <InlineMessage severity="error">{serverError}</InlineMessage> : <Help>{T.paidDateHelp}</Help>}
    </div>
  )
}
