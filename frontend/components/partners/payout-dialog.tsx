"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { Money } from "@/components/common/money"
import { JalaliDateRangePicker, type IsoDateRange } from "@/components/jalali-date-picker"
import { DrawerShell, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Alert, Btn, Help, InlineMessage, Label, MoneyInput } from "@/components/record-sale/primitives"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ApiError,
  createDistribution,
  previewDistribution,
  type Distribution,
  type DistributionCreate,
  type DistributionListItem,
  type DistributionPreview,
} from "@/lib/api"
import { formatJalali } from "@/lib/jalali"
import { classifyDistributionError, defaultPeriod, overCapBy, percentText } from "@/lib/partners"
import { cn } from "@/lib/utils"
import { S, distributionErrorText } from "./copy"

type Preview =
  | { key: string; status: "ready"; data: DistributionPreview }
  | { key: string; status: "error"; text: string }

const PREVIEW_DELAY_MS = 300

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const c = classifyDistributionError(e)
    if (c) return distributionErrorText(c)
    return e.status === 0 ? S.errorBody : e.message
  }
  return String(e)
}

/**
 * «ثبت پرداخت»: the owner types the FULL payout; the split comes from
 * POST /distributions/preview (db/ computes it exactly as it will be stored),
 * so the screen never rounds shares itself. Over the undistributed profit
 * needs a second confirmation (allow_exceeding). The saved shares are the
 * ones POST /distributions returns. Never closes on an error.
 */
export function PayoutDialog({
  open,
  today,
  distributions,
  mobile,
  onClose,
  onSaved,
}: {
  open: boolean
  today: string
  distributions: DistributionListItem[]
  mobile: boolean
  onClose: () => void
  onSaved: (d: Distribution) => void
}) {
  /** Integer Rial; undefined = empty; null = text that gives no exact amount. */
  const [amount, setAmount] = React.useState<number | null | undefined>(undefined)
  const [date, setDate] = React.useState(today)
  const [period, setPeriod] = React.useState<IsoDateRange>({ from: null, to: null })
  const [notes, setNotes] = React.useState("")
  const [touched, setTouched] = React.useState(false)
  const [step, setStep] = React.useState<"form" | "confirm">("form")
  const [busy, setBusy] = React.useState(false)
  const [alert, setAlert] = React.useState<string | null>(null)
  const [saveError, setSaveError] = React.useState<{ message: string; code: string } | null>(null)
  const [preview, setPreview] = React.useState<Preview | null>(null)

  const [wasOpen, setWasOpen] = React.useState(false)
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setAmount(undefined)
      setDate(today)
      setPeriod(defaultPeriod(today, distributions))
      setNotes("")
      setTouched(false)
      setStep("form")
      setAlert(null)
      setSaveError(null)
      setPreview(null)
    }
  }

  const body: DistributionCreate | null =
    amount != null && amount > 0 && period.from && period.to
      ? {
          period_start: period.from,
          period_end: period.to,
          total_amount_distributed: amount,
          distribution_date: date,
          ...(notes.trim() ? { notes: notes.trim() } : {}),
        }
      : null
  // The preview depends only on what changes the split or its checks.
  const key = body ? `${body.period_start}|${body.period_end}|${body.total_amount_distributed}|${body.distribution_date}` : null
  const current = preview && preview.key === key ? preview : null

  React.useEffect(() => {
    if (!open || !key || !body) return
    let cancelled = false
    const req = body
    const t = window.setTimeout(() => {
      previewDistribution(req).then(
        (data) => !cancelled && setPreview({ key, status: "ready", data }),
        (e: unknown) => !cancelled && setPreview({ key, status: "error", text: errorText(e) })
      )
    }, PREVIEW_DELAY_MS)
    return () => {
      cancelled = true
      window.clearTimeout(t)
    }
    // body is rebuilt every render; key carries everything the request depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, key])

  const amountError =
    amount === null ? null : amount === undefined ? (touched ? S.amountRequired : null) : amount === 0 ? S.amountZero : null
  const periodError = touched && (!period.from || !period.to) ? S.periodRequired : null
  const ready = current?.status === "ready" ? current.data : null

  const close = () => {
    if (!busy) onClose()
  }

  const post = async (allowExceeding: boolean) => {
    if (!body) return
    setBusy(true)
    setAlert(null)
    setSaveError(null)
    try {
      onSaved(await createDistribution({ ...body, allow_exceeding: allowExceeding }))
    } catch (e) {
      const c = e instanceof ApiError ? classifyDistributionError(e) : null
      if (c?.kind === "overCap" && ready) setStep("confirm")
      else if (c) {
        setStep("form")
        setAlert(distributionErrorText(c))
      } else {
        setStep("form")
        setSaveError(
          e instanceof ApiError
            ? { message: e.status === 0 ? S.errorBody : e.message, code: `DISTRIBUTIONS_${e.status || "NET"}` }
            : { message: String(e), code: "UNKNOWN" }
        )
      }
    } finally {
      setBusy(false)
    }
  }

  const submit = () => {
    setTouched(true)
    if (busy || !body || !ready) return
    if (ready.exceeds_undistributed) setStep("confirm")
    else void post(false)
  }

  const previewBlock = !body ? (
    <Help>{S.previewWaiting}</Help>
  ) : !current ? (
    <div aria-busy="true" aria-label={S.previewLoading} className="flex flex-col gap-2">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-8 rounded-md bg-surface-2" />
      ))}
    </div>
  ) : current.status === "error" ? (
    <Alert tone="err" title={S.previewFailed}>
      {current.text}
    </Alert>
  ) : (
    <section aria-label={S.previewTitle} className="flex flex-col gap-2">
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 rounded-[10px] bg-surface-2 px-4 py-3 text-[13px]">
        <dt className="text-text-3">{S.periodProfit}</dt>
        <dd>
          <Money value={current.data.total_profit_available} />
        </dd>
        <dt className="text-text-3">{S.undistributed(formatJalali(current.data.period_end))}</dt>
        <dd>
          <Money value={current.data.undistributed_profit} className="font-semibold" />
        </dd>
      </dl>
      {current.data.exceeds_undistributed && <InlineMessage severity="warn">{S.overCapWarn}</InlineMessage>}
      <div className="flex items-center gap-2">
        <span className="text-[13px] font-semibold">{S.previewTitle}</span>
        <span className="rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-3">{S.preview}</span>
      </div>
      <table className="w-full border-separate border-spacing-0 text-[13px]">
        <thead>
          <tr className="text-xs text-text-3 [&>th]:border-b [&>th]:border-border [&>th]:py-1.5 [&>th]:font-semibold">
            <th scope="col" className="text-start">
              {S.colName}
            </th>
            <th scope="col" className="text-start">
              {S.colPercent}
            </th>
            <th scope="col" className="text-end">
              {S.colShare}
            </th>
          </tr>
        </thead>
        <tbody>
          {current.data.shares.map((s) => (
            <tr key={s.partner_id} className="[&>td]:border-b [&>td]:border-border [&>td]:py-2">
              <td className="max-w-[160px] truncate font-semibold" dir="auto">
                {s.partner_name}
              </td>
              <td className="text-text-2 tabular-nums">{S.percent(percentText(s.percentage_at_time))}</td>
              <td className="text-end">
                <Money value={s.amount} className="font-bold" />
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="[&>td]:pt-2">
            <td colSpan={2} className="font-semibold text-text-3">
              {S.sum}
            </td>
            <td className="text-end">
              <Money value={current.data.total_amount_distributed} className="font-bold" />
            </td>
          </tr>
        </tfoot>
      </table>
      <Help>{S.previewHelp}</Help>
    </section>
  )

  const form = (
    <>
      {saveError && <SaveError {...saveError} />}
      {alert && <Alert tone="err">{alert}</Alert>}
      <Help>{S.payoutIntro}</Help>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="po-amount">{S.amount}</Label>
        <MoneyInput
          id="po-amount"
          allowEmpty
          value={amount}
          onValue={(n) => {
            setAmount(n)
            setAlert(null)
          }}
          tone={amountError ? "error" : null}
          aria-invalid={!!amountError || undefined}
          className={mobile ? "h-12" : undefined}
        />
        {amountError && <InlineMessage severity="error">{amountError}</InlineMessage>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="po-period">{S.period}</Label>
        <JalaliDateRangePicker
          id="po-period"
          value={period}
          onChange={(v) => {
            setPeriod(v)
            setAlert(null)
          }}
          className={cn("w-full", mobile ? "h-12" : "h-10")}
        />
        {periodError ? <InlineMessage severity="error">{periodError}</InlineMessage> : <Help>{S.periodHelp}</Help>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="po-date">{S.payoutDate}</Label>
        <DateField id="po-date" value={date} today={today} onChange={setDate} todayLabel={S.today} mobile={mobile} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="po-notes" optional>
          {S.notes}
        </Label>
        <input id="po-notes" dir="auto" value={notes} onChange={(e) => setNotes(e.target.value)} className={textInputClass(mobile)} />
      </div>
      {previewBlock}
    </>
  )

  const diff = ready ? overCapBy(ready.total_amount_distributed, ready.undistributed_profit) : null
  const confirm = ready && (
    <>
      <Alert tone="warn" icon="triangle" title={S.confirmTitle}>
        {S.confirmBody}
      </Alert>
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 rounded-[10px] bg-surface-2 px-4 py-3 text-[13px]">
        <dt className="text-text-3">{S.confirmAmount}</dt>
        <dd>
          <Money value={ready.total_amount_distributed} className="font-bold" />
        </dd>
        <dt className="text-text-3">{S.undistributed(formatJalali(ready.period_end))}</dt>
        <dd>
          <Money value={ready.undistributed_profit} />
        </dd>
        <dt className="text-text-3">{S.confirmDifference}</dt>
        <dd className="text-loss">{diff === null ? S.nil : <Money value={diff} className="font-bold" />}</dd>
      </dl>
    </>
  )

  const footer =
    step === "confirm" ? (
      <>
        <Btn
          variant="primary"
          size={mobile ? "lg" : "md"}
          className={mobile ? "grow" : undefined}
          disabled={busy}
          aria-busy={busy || undefined}
          onClick={() => void post(true)}
        >
          {busy && <Loader2 className="size-4 animate-spin" />}
          {S.confirmYes}
        </Btn>
        <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={() => setStep("form")}>
          {S.back}
        </Btn>
      </>
    ) : (
      <>
        <Btn
          variant="primary"
          size={mobile ? "lg" : "md"}
          className={mobile ? "grow" : undefined}
          disabled={busy || (touched && !ready)}
          aria-busy={busy || undefined}
          onClick={submit}
        >
          {busy && <Loader2 className="size-4 animate-spin" />}
          {S.submit}
        </Btn>
        <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={close}>
          {S.cancel}
        </Btn>
      </>
    )

  return (
    <DrawerShell open={open} onOpenChange={(o) => !o && close()} mobile={mobile} title={S.payoutTitle} busy={busy} footer={footer}>
      {step === "confirm" && ready ? confirm : form}
    </DrawerShell>
  )
}
