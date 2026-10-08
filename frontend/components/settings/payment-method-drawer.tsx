"use client"

import * as React from "react"
import { Loader2, Lock } from "lucide-react"
import { DrawerShell, FieldError, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Segment } from "@/components/common/segment"
import { PM, ruleText } from "@/components/payment-methods/copy"
import { Alert, Btn, Help, IntInput, Label, MoneyInput } from "@/components/record-sale/primitives"
import { M, moneyInputMessage } from "@/components/common/copy"
import type { MoneyInputError } from "@/lib/money"
import {
  ApiError,
  createPaymentMethod,
  updatePaymentMethod,
  type PaymentMethod,
  type PaymentMethodUpdate,
} from "@/lib/api"
import {
  DAYS_BOUNDS,
  SETTLEMENT_RULES,
  capError,
  capForSave,
  classifyPaymentError,
  formatPercent,
  parsePercent,
  type SettlementRule,
} from "@/lib/payment-methods"
import { S } from "./copy"

type Field = "name" | "fee_bps" | "fee_fixed" | "fee_cap" | "settlement_rule" | "settlement_days"

type Form = {
  name: string
  percent: string
  /** Integer Rial; null while MoneyInput holds text that gives no exact amount (blocks save). */
  fixed: number | null
  /** MoneyInput's reason while `fixed` is null. */
  fixedError: MoneyInputError | null
  /** Cap on the percentage part, integer Rial; undefined = empty = no cap; null = not exact (blocks save). */
  cap: number | null | undefined
  /** MoneyInput's reason while `cap` is null. */
  capError: MoneyInputError | null
  rule: SettlementRule
  days: number
}

/** Default settlement_days when a rule is picked (Zarinpal-style next day; Digipay-style 7th). */
const DEFAULT_DAYS: Record<SettlementRule, number> = { IMMEDIATE: 0, DAYS_AFTER: 1, DAY_OF_NEXT_MONTH: 7 }

function formOf(m: PaymentMethod | null): Form {
  if (!m) {
    return { name: "", percent: "", fixed: 0, fixedError: null, cap: undefined, capError: null, rule: "IMMEDIATE", days: 0 }
  }
  const rule = m.settlement_rule as SettlementRule
  return {
    name: m.name,
    percent: formatPercent(m.fee_bps),
    fixed: m.fee_fixed,
    fixedError: null,
    cap: m.fee_cap ?? undefined,
    capError: null,
    rule,
    days: m.settlement_days ?? 0,
  }
}

const percentMessage = { format: S.fPercentFormat, decimals: S.fPercentDecimals, range: S.fPercentRange } as const

/** Client checks mirroring db/payment_methods.py; the API still decides. */
function clientErrors(f: Form): Partial<Record<Field, string>> {
  const errors: Partial<Record<Field, string>> = {}
  if (!f.name.trim()) errors.name = S.fNameError
  const pct = parsePercent(f.percent)
  if (!pct.ok) errors.fee_bps = percentMessage[pct.error]
  if (f.fixed === null) errors.fee_fixed = f.fixedError ? moneyInputMessage(f.fixedError) : M.reenter
  else if (!Number.isSafeInteger(f.fixed) || f.fixed < 0) errors.fee_fixed = S.fFixedError
  const cap = capError(pct.ok ? pct.bps : null, f.cap)
  if (cap === "inexact") errors.fee_cap = f.capError ? moneyInputMessage(f.capError) : M.reenter
  else if (cap === "min") errors.fee_cap = S.fCapMin
  const bounds = DAYS_BOUNDS[f.rule]
  if (bounds && (f.days < bounds.min || f.days > bounds.max)) errors.settlement_days = S.fDaysError(bounds.min, bounds.max)
  return errors
}

/** The server's 422 field (or a FastAPI body field) → the Persian message under that field. */
function fieldMessage(field: string, f: Form): string | null {
  const bounds = DAYS_BOUNDS[f.rule]
  switch (field) {
    case "name":
      return S.fNameError
    case "fee_bps":
      return S.fPercentRange
    case "fee_fixed":
      return S.fFixedError
    case "fee_cap": {
      const pct = parsePercent(f.percent)
      return pct.ok && pct.bps > 0 ? S.fCapMin : S.fCapNeedsPercent
    }
    case "settlement_rule":
      return S.fRuleError
    case "settlement_days":
      return bounds ? S.fDaysError(bounds.min, bounds.max) : S.fRuleError
    default:
      return null
  }
}

/**
 * Add or edit a payment method. Saves on its own (not part of the settings
 * draft). While the method has orders pending settlement, its rule and days
 * are read-only — the backend refuses the change (409) — but the name and
 * both fees stay editable: each order keeps the fee it was recorded with.
 */
export function PaymentMethodDrawer({
  open,
  method,
  mobile,
  onClose,
  onSaved,
  onStale,
}: {
  open: boolean
  /** null = add a new method. */
  method: PaymentMethod | null
  mobile: boolean
  onClose: () => void
  onSaved: (saved: PaymentMethod, created: boolean) => void
  /** Re-read the methods (the server's state differs from what the drawer showed). */
  onStale: () => Promise<void>
}) {
  const [form, setForm] = React.useState<Form>(() => formOf(method))
  const [seed, setSeed] = React.useState({ open, method })
  const [busy, setBusy] = React.useState(false)
  const [serverField, setServerField] = React.useState<{ field: Field; message: string } | null>(null)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  /** Pending orders the server reported on a refused rule change (newer than `method`). */
  const [lockedCount, setLockedCount] = React.useState<number | null>(null)

  // Reset whenever the drawer opens or switches to another method.
  if (seed.open !== open || seed.method?.id !== method?.id) {
    setSeed({ open, method })
    setForm(formOf(method))
    setServerField(null)
    setError(null)
    setLockedCount(null)
  }

  const editing = method !== null
  const pendingCount = lockedCount ?? method?.pending_order_count ?? 0
  const ruleLocked = editing && pendingCount > 0
  const errors = clientErrors(form)
  const errorFor = (f: Field) => errors[f] ?? (serverField?.field === f ? serverField.message : null)
  const bounds = DAYS_BOUNDS[form.rule]

  const set = (patch: Partial<Form>, field?: Field) => {
    setForm((f) => ({ ...f, ...patch }))
    if (field && serverField?.field === field) setServerField(null)
    setError(null)
  }

  const pct = parsePercent(form.percent)
  const bps = pct.ok ? pct.bps : null
  const days = bounds ? form.days : null
  /** The cap needs a percentage fee: off (and sent as null) while the percentage is empty, 0 or invalid. */
  const capEnabled = !!bps
  const cap = capForSave(bps, form.cap)

  /** Only what changed (PATCH); every field for a new method (POST). */
  const patch: PaymentMethodUpdate = {}
  if (editing && method) {
    if (form.name.trim() !== method.name) patch.name = form.name.trim()
    if (bps !== null && bps !== method.fee_bps) patch.fee_bps = bps
    if (form.fixed !== null && form.fixed !== method.fee_fixed) patch.fee_fixed = form.fixed
    // Emptying the percentage clears the cap in the same PATCH (the backend refuses fee_bps 0 with a cap).
    if (bps !== null && (!capEnabled || form.cap !== null) && cap !== method.fee_cap) patch.fee_cap = cap
    if (!ruleLocked && (form.rule !== method.settlement_rule || days !== method.settlement_days)) {
      patch.settlement_rule = form.rule
      patch.settlement_days = days
    }
  }
  const unchanged = editing && Object.keys(patch).length === 0
  const invalid = Object.keys(errors).length > 0
  const canSave = !busy && !invalid && !unchanged

  const save = async () => {
    if (!canSave || bps === null || form.fixed === null) return
    setBusy(true)
    setError(null)
    setServerField(null)
    try {
      const saved = editing && method
        ? await updatePaymentMethod(method.id, patch)
        : await createPaymentMethod({
            name: form.name.trim(),
            fee_bps: bps,
            fee_fixed: form.fixed,
            fee_cap: cap,
            settlement_rule: form.rule,
            settlement_days: days,
          })
      onSaved(saved, !editing)
    } catch (e) {
      await handleError(e)
    } finally {
      setBusy(false)
    }
  }

  const handleError = async (e: unknown) => {
    if (!(e instanceof ApiError)) {
      setError({ message: String(e), code: "UNKNOWN" })
      return
    }
    const classified = classifyPaymentError(e)
    if (classified?.kind === "duplicateName") {
      setServerField({ field: "name", message: PM.duplicateName })
      return
    }
    if (classified?.kind === "rulePending") {
      // Orders became pending since the list was read: lock the rule and say why.
      setLockedCount(classified.count)
      setForm((f) => ({ ...f, rule: method?.settlement_rule as SettlementRule, days: method?.settlement_days ?? 0 }))
      await onStale().catch(() => {})
      return
    }
    if (e.status === 404) {
      setError({ message: PM.methodGone, code: "PAYMENT_METHODS_404" })
      await onStale().catch(() => {})
      return
    }
    if (e.status === 422 && e.field) {
      const message = fieldMessage(e.field, form)
      if (message) {
        setServerField({ field: e.field as Field, message })
        return
      }
    }
    setError({ message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `PAYMENT_METHODS_${e.status}` })
  }

  const pickRule = (rule: SettlementRule) => set({ rule, days: DEFAULT_DAYS[rule] }, "settlement_rule")

  return (
    <DrawerShell
      open={open}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={editing && method ? S.drawerEdit(method.name) : S.drawerAdd}
      busy={busy}
      footer={
        <>
          <Btn variant="primary" disabled={!canSave} aria-busy={busy || undefined} onClick={save}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {editing ? S.fSave : S.fAdd}
          </Btn>
          <Btn disabled={busy} onClick={onClose}>
            {S.fCancel}
          </Btn>
          {unchanged && <span className="text-xs text-text-3">{S.fNoChanges}</span>}
        </>
      }
    >
      {error && <SaveError {...error} />}

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pm-name">{S.fName}</Label>
        <input
          id="pm-name"
          value={form.name}
          placeholder={S.fNamePlaceholder}
          autoComplete="off"
          onChange={(e) => set({ name: e.target.value }, "name")}
          className={textInputClass(mobile, !!errorFor("name") && form.name !== "")}
          aria-invalid={errorFor("name") ? true : undefined}
        />
        {errorFor("name") && (form.name !== "" || serverField?.field === "name") && <FieldError>{errorFor("name")}</FieldError>}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pm-percent">{S.fPercent}</Label>
          <div className="relative flex items-center">
            <input
              id="pm-percent"
              inputMode="decimal"
              autoComplete="off"
              dir="ltr"
              value={form.percent}
              placeholder="۰"
              onChange={(e) => set({ percent: e.target.value }, "fee_bps")}
              className={textInputClass(mobile, !!errorFor("fee_bps")) + " pe-8 text-end tabular-nums"}
              aria-invalid={errorFor("fee_bps") ? true : undefined}
            />
            <span className="pointer-events-none absolute end-3 text-xs text-text-3">٪</span>
          </div>
          {errorFor("fee_bps") ? <FieldError>{errorFor("fee_bps")}</FieldError> : <Help>{S.fPercentHelp}</Help>}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pm-fixed">{S.fFixed}</Label>
          <MoneyInput
            id="pm-fixed"
            value={form.fixed}
            onValue={(v, error) => set({ fixed: v ?? null, fixedError: error }, "fee_fixed")}
            tone={errorFor("fee_fixed") && form.fixed !== null ? "error" : null}
            className={mobile ? "h-11" : undefined}
          />
          {form.fixed !== null && errorFor("fee_fixed") ? <FieldError>{errorFor("fee_fixed")}</FieldError> : <Help>{S.fFixedHelp}</Help>}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pm-cap" optional>
          {S.fCap}
        </Label>
        <MoneyInput
          id="pm-cap"
          allowEmpty
          disabled={!capEnabled}
          // Off without a percentage: shown empty, the typed cap comes back with the percentage.
          value={capEnabled ? form.cap : undefined}
          onValue={(v, error) => set({ cap: v, capError: error }, "fee_cap")}
          tone={errorFor("fee_cap") && form.cap !== null ? "error" : null}
          className={mobile ? "h-11" : undefined}
          wrapperClassName="sm:max-w-[calc(50%-0.5rem)]"
        />
        {!capEnabled ? (
          <Help>{S.fCapNeedsPercent}</Help>
        ) : form.cap !== null && errorFor("fee_cap") ? (
          <FieldError>{errorFor("fee_cap")}</FieldError>
        ) : (
          <Help>{S.fCapHelp}</Help>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>{S.fRule}</Label>
        {ruleLocked ? (
          <>
            <div className="flex h-10 items-center gap-2 rounded-lg border border-dashed border-border-strong bg-surface-2 px-3 text-sm">
              <Lock className="size-3.5 text-text-3" aria-hidden />
              <b>{ruleText(form.rule, form.rule === "IMMEDIATE" ? null : form.days)}</b>
            </div>
            <Alert tone="warn" icon="lock">
              {PM.rulePending(pendingCount)}
            </Alert>
          </>
        ) : (
          <>
            <Segment
              value={form.rule}
              options={SETTLEMENT_RULES.map((r) => [r, PM.ruleNames[r]] as const)}
              onChange={pickRule}
              label={S.fRuleAria}
              mobile={mobile}
              className={mobile ? "flex-col" : undefined}
            />
            <Help>{PM.ruleHelp[form.rule]}</Help>
            {serverField?.field === "settlement_rule" && <FieldError>{serverField.message}</FieldError>}
          </>
        )}
      </div>

      {bounds && !ruleLocked && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pm-days">{form.rule === "DAYS_AFTER" ? S.fDays : S.fDayOfMonth}</Label>
          <IntInput
            id="pm-days"
            value={form.days}
            onValue={(n) => set({ days: n }, "settlement_days")}
            tone={errorFor("settlement_days") ? "error" : null}
            className={mobile ? "h-11 max-w-[160px]" : "max-w-[160px]"}
            aria-invalid={errorFor("settlement_days") ? true : undefined}
          />
          {errorFor("settlement_days") ? (
            <FieldError>{errorFor("settlement_days")}</FieldError>
          ) : (
            <Help>
              {S.fDaysRange(bounds.min, bounds.max)} {PM.settleLine(form.rule, form.days)}
            </Help>
          )}
        </div>
      )}
    </DrawerShell>
  )
}
