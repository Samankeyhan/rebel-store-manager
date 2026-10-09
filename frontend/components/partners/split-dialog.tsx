"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { DrawerShell, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Alert, Btn, Help, InlineMessage, Label } from "@/components/record-sale/primitives"
import { ApiError, createPartner, deactivatePartner, setPartnerPercentage, type Partner } from "@/lib/api"
import {
  HUNDRED_PERCENT,
  isNameTaken,
  parsePercent,
  percentChanges,
  percentOf,
  percentText,
  splitState,
  totalHundredths,
} from "@/lib/partners"
import { cn } from "@/lib/utils"
import { S, hundredthsText, percentErrorText } from "./copy"

/** What the editor does on save; every mode ends with the active total at exactly 100 (or no active partner left). */
export type SplitMode = { kind: "add" } | { kind: "edit" } | { kind: "deactivate"; partner: Partner }

type Draft = { name: string; phone: string; email: string; notes: string; pct: string }
const emptyDraft: Draft = { name: "", phone: "", email: "", notes: "", pct: "" }

/**
 * «افزودن شریک» / «ویرایش سهم‌ها» / «غیرفعال‌سازی»: one editor of every active
 * partner's percentage with a live total; «ذخیره» only at exactly 100.00.
 * The backend has no atomic "set all", so saving is several requests: the
 * new partner or the deactivation first, then each changed percentage. A
 * failure before anything is saved stays in the dialog; a failure partway
 * closes it and reports what was saved (onPartial).
 */
export function SplitDialog({
  mode,
  partners,
  mobile,
  onClose,
  onDone,
  onPartial,
}: {
  mode: SplitMode | null
  /** All partners, active and inactive (name clashes include inactive ones). */
  partners: Partner[]
  mobile: boolean
  onClose: () => void
  onDone: (toast: string) => void
  onPartial: (saved: string[], error: string) => void
}) {
  const [texts, setTexts] = React.useState<Record<number, string>>({})
  const [draft, setDraft] = React.useState<Draft>(emptyDraft)
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [saveError, setSaveError] = React.useState<{ message: string; code: string } | null>(null)
  const [notice, setNotice] = React.useState<string | null>(null)

  // Keep the last mode while the drawer animates closed; reset on open.
  const [shown, setShown] = React.useState<SplitMode | null>(null)
  if (mode && mode !== shown) {
    setShown(mode)
    setTexts(Object.fromEntries(partners.filter((p) => p.is_active === 1).map((p) => [p.id, percentText(p.current_percentage)])))
    setDraft(emptyDraft)
    setTouched(false)
    setSaveError(null)
    setNotice(null)
  }
  const m = mode ?? shown
  if (!m) return null

  const open = mode != null
  const rows = partners.filter((p) => p.is_active === 1 && !(m.kind === "deactivate" && p.id === m.partner.id))
  const parsed = new Map(rows.map((p) => [p.id, parsePercent(texts[p.id] ?? "")]))
  const draftPct = m.kind === "add" ? parsePercent(draft.pct) : null
  const values = [...[...parsed.values()].map((r) => r.hundredths), ...(draftPct ? [draftPct.hundredths] : [])]
  const total = totalHundredths(values)
  const state = splitState(total)
  const noneLeft = m.kind === "deactivate" && rows.length === 0

  const name = draft.name.trim()
  const nameError = m.kind !== "add" ? null : !name ? (touched ? S.nameRequired : null) : isNameTaken(name, partners) ? S.nameTaken : null
  const edited = new Map<number, number>()
  for (const [id, r] of parsed) if (r.hundredths !== null) edited.set(id, r.hundredths)
  const changes = percentChanges(rows, edited)
  const totalOk = noneLeft || state === "ok"
  const canSave = !busy && totalOk && (m.kind !== "add" || (!!name && !nameError))

  const close = () => {
    if (!busy) onClose()
  }

  const save = async () => {
    setTouched(true)
    setSaveError(null)
    setNotice(null)
    if (!canSave) return
    if (m.kind === "edit" && changes.length === 0) {
      setNotice(S.noChanges)
      return
    }
    const saved: string[] = []
    const nameOf = new Map(rows.map((p) => [p.id, p.name]))
    setBusy(true)
    try {
      if (m.kind === "add" && draftPct?.hundredths != null) {
        const opt = (s: string) => (s.trim() ? s.trim() : null)
        await createPartner({
          name,
          current_percentage: percentOf(draftPct.hundredths),
          phone: opt(draft.phone),
          email: opt(draft.email),
          notes: opt(draft.notes),
        })
        saved.push(S.stepCreated(name))
      }
      if (m.kind === "deactivate") {
        await deactivatePartner(m.partner.id)
        saved.push(S.stepDeactivated(m.partner.name))
      }
      for (const c of changes) {
        await setPartnerPercentage(c.partnerId, c.percentage)
        saved.push(S.stepPercent(nameOf.get(c.partnerId) ?? "", percentText(c.percentage)))
      }
      onDone(m.kind === "add" ? S.toastAdded : m.kind === "deactivate" ? S.toastDeactivated : S.toastSplit)
    } catch (e) {
      const message = e instanceof ApiError ? (e.status === 0 ? S.errorBody : e.message) : String(e)
      if (saved.length === 0)
        setSaveError({ message, code: e instanceof ApiError ? `PARTNERS_${e.status || "NET"}` : "UNKNOWN" })
      else onPartial(saved, message)
    } finally {
      setBusy(false)
    }
  }

  const totalLine = !noneLeft && (
    <div
      role="status"
      className={cn(
        "flex flex-wrap items-center justify-between gap-2 rounded-[10px] border px-4 py-2.5 text-[13px]",
        state === "ok" ? "border-transparent bg-profit-soft" : "border-loss-border bg-loss-soft"
      )}
    >
      <span className="font-semibold">
        {S.total}: {total === null ? S.nil : S.percent(hundredthsText(total))}
      </span>
      <span className={state === "ok" ? "text-profit" : "text-loss"}>
        {state === "ok"
          ? S.totalOk
          : state === "invalid"
            ? S.totalInvalid
            : state === "under"
              ? S.totalUnder(hundredthsText(HUNDRED_PERCENT - (total as number)))
              : S.totalOver(hundredthsText((total as number) - HUNDRED_PERCENT))}
      </span>
    </div>
  )

  const percentField = (id: string, label: string, text: string, onText: (t: string) => void, error: string | null) => (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={id} className="min-w-0 truncate text-[13px] font-semibold">
          {label}
        </label>
        <div className="relative w-28 shrink-0">
          <input
            id={id}
            inputMode="decimal"
            autoComplete="off"
            dir="ltr"
            value={text}
            aria-label={S.percentAria(label)}
            aria-invalid={!!error || undefined}
            onChange={(e) => onText(e.target.value)}
            onFocus={(e) => e.currentTarget.select()}
            className={cn(textInputClass(mobile, !!error), "pe-7 text-end tabular-nums")}
          />
          <span className="pointer-events-none absolute end-2.5 top-1/2 -translate-y-1/2 text-xs text-text-3">٪</span>
        </div>
      </div>
      {error && <InlineMessage severity="error">{error}</InlineMessage>}
    </div>
  )

  const textField = (key: "name" | "phone" | "email" | "notes", label: string, optional: boolean, error?: string | null) => (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={`sp-${key}`} optional={optional}>
        {label}
      </Label>
      <input
        id={`sp-${key}`}
        dir="auto"
        value={draft[key]}
        onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
        aria-invalid={!!error || undefined}
        className={textInputClass(mobile, !!error)}
      />
      {error && <InlineMessage severity="error">{error}</InlineMessage>}
    </div>
  )

  const title = m.kind === "add" ? S.addTitle : m.kind === "edit" ? S.editTitle : S.deactivateTitle(m.partner.name)

  return (
    <DrawerShell
      open={open}
      onOpenChange={(o) => !o && close()}
      mobile={mobile}
      title={title}
      busy={busy}
      footer={
        <>
          <Btn
            variant="primary"
            size={mobile ? "lg" : "md"}
            className={mobile ? "grow" : undefined}
            disabled={!canSave}
            aria-busy={busy || undefined}
            onClick={save}
          >
            {busy && <Loader2 className="size-4 animate-spin" />}
            {m.kind === "deactivate" ? S.confirmDeactivate : S.save}
          </Btn>
          <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={close}>
            {S.cancel}
          </Btn>
        </>
      }
    >
      {saveError && <SaveError {...saveError} />}
      {notice && <Alert tone="warn">{notice}</Alert>}
      {m.kind === "deactivate" && (
        <Alert tone="warn">
          <div>{noneLeft ? S.deactivateLast : S.deactivateHelp}</div>
          <div className="mt-1 text-xs text-text-3">{S.irreversible}</div>
        </Alert>
      )}
      {m.kind === "add" && (
        <>
          {textField("name", S.name, false, nameError)}
          {percentField(
            "sp-new-pct",
            S.newPartnerPercent,
            draft.pct,
            (t) => setDraft((d) => ({ ...d, pct: t })),
            touched || draft.pct ? (draftPct?.error ? percentErrorText(draftPct.error) : null) : null
          )}
          {textField("phone", S.phone, true)}
          {textField("email", S.email, true)}
          {textField("notes", S.notes, true)}
        </>
      )}
      {rows.length > 0 && (
        <section className="flex flex-col gap-3">
          {m.kind === "add" && <div className="text-xs font-semibold text-text-3">{S.otherPartners}</div>}
          {rows.map((p) => {
            const r = parsed.get(p.id)
            return (
              <React.Fragment key={p.id}>
                {percentField(
                  `sp-pct-${p.id}`,
                  p.name,
                  texts[p.id] ?? "",
                  (t) => setTexts((x) => ({ ...x, [p.id]: t })),
                  r?.error ? percentErrorText(r.error) : null
                )}
              </React.Fragment>
            )
          })}
        </section>
      )}
      {totalLine}
      {!noneLeft && <Help>{S.percentHelp}</Help>}
    </DrawerShell>
  )
}
