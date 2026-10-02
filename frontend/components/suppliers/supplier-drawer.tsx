"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { DrawerShell, FieldError, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Btn, Label } from "@/components/record-sale/primitives"
import { ApiError, createSupplier, updateSupplier, type Supplier, type SupplierUpdate } from "@/lib/api"
import { cn } from "@/lib/utils"
import { S } from "./copy"

const FIELDS = ["phone", "email", "website", "notes"] as const
type Optional = (typeof FIELDS)[number]
type Draft = { name: string } & Record<Optional, string>

const toDraft = (s: Supplier | null): Draft => ({
  name: s?.name ?? "",
  phone: s?.phone ?? "",
  email: s?.email ?? "",
  website: s?.website ?? "",
  notes: s?.notes ?? "",
})

/** Trimmed; empty → null (the column is nullable). */
const clean = (v: string): string | null => v.trim() || null

/**
 * Add / edit drawer (design 14 §1): name (required), phone, email, website,
 * notes. Edit sends only the fields that changed (PATCH semantics: an
 * omitted field is kept, null clears it). Re-mount it (key) per opening.
 */
export function SupplierDrawer({
  open,
  supplier,
  mobile,
  onClose,
  onSaved,
  onGone,
}: {
  open: boolean
  /** null = a new supplier. */
  supplier: Supplier | null
  mobile: boolean
  onClose: () => void
  onSaved: (s: Supplier, created: boolean) => void
  /** The supplier no longer exists (404): refresh the list. */
  onGone: () => void
}) {
  const [draft, setDraft] = React.useState<Draft>(() => toDraft(supplier))
  const [busy, setBusy] = React.useState(false)
  const [nameError, setNameError] = React.useState<string | null>(null)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const set = (k: keyof Draft) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setDraft((d) => ({ ...d, [k]: e.target.value }))
    if (k === "name") setNameError(null)
  }

  const submit = async () => {
    setError(null)
    const name = draft.name.trim()
    if (!name) {
      setNameError(S.nameRequired)
      return
    }
    if (busy) return
    let body: SupplierUpdate = {}
    if (supplier) {
      if (name !== supplier.name) body.name = name
      for (const f of FIELDS) if (clean(draft[f]) !== supplier[f]) body[f] = clean(draft[f])
      if (Object.keys(body).length === 0) {
        onClose()
        return
      }
    } else {
      body = { name, ...Object.fromEntries(FIELDS.map((f) => [f, clean(draft[f])])) }
    }
    setBusy(true)
    try {
      const saved = supplier ? await updateSupplier(supplier.id, body) : await createSupplier({ ...body, name })
      onSaved(saved, supplier == null)
    } catch (e) {
      if (e instanceof ApiError && e.status === 422 && e.field === "name") {
        setNameError(e.message)
      } else {
        setError(
          e instanceof ApiError
            ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `SUPPLIERS_${e.status}` }
            : { message: String(e), code: "UNKNOWN" }
        )
        if (e instanceof ApiError && e.status === 404) onGone()
      }
    } finally {
      setBusy(false)
    }
  }

  const input = (id: string, k: keyof Draft, opts: { ltr?: boolean; placeholder?: string; type?: string } = {}) => (
    <input
      id={id}
      type={opts.type ?? "text"}
      value={draft[k]}
      onChange={set(k)}
      placeholder={opts.placeholder}
      dir={opts.ltr ? "ltr" : undefined}
      autoComplete="off"
      aria-invalid={(k === "name" && !!nameError) || undefined}
      className={cn(textInputClass(mobile, k === "name" && !!nameError), opts.ltr && "text-right tabular-nums")}
    />
  )

  return (
    <DrawerShell
      open={open}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={supplier ? S.titleEdit : S.titleNew}
      busy={busy}
      footer={
        <>
          <Btn variant="primary" disabled={busy} aria-busy={busy || undefined} onClick={submit}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {S.save}
          </Btn>
          <Btn disabled={busy} onClick={onClose}>
            {S.cancel}
          </Btn>
        </>
      }
    >
      <form
        className="flex flex-col gap-3.5"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        {error && <SaveError {...error} />}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sup-name">{S.fieldName}</Label>
          {input("sup-name", "name")}
          {nameError && <FieldError>{nameError}</FieldError>}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sup-phone" optional>
            {S.fieldPhone}
          </Label>
          {input("sup-phone", "phone", { ltr: true, placeholder: S.phonePlaceholder, type: "tel" })}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sup-email" optional>
            {S.fieldEmail}
          </Label>
          {input("sup-email", "email", { ltr: true, placeholder: S.emailPlaceholder, type: "email" })}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sup-website" optional>
            {S.fieldWebsite}
          </Label>
          {input("sup-website", "website", { placeholder: S.websitePlaceholder })}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sup-notes" optional>
            {S.fieldNotes}
          </Label>
          <textarea
            id="sup-notes"
            value={draft.notes}
            onChange={set("notes")}
            placeholder={S.notesPlaceholder}
            className="h-20 w-full resize-none rounded-lg border border-border-strong bg-card px-3 py-2.5 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30"
          />
        </div>
        {/* Enter in a field submits. */}
        <button type="submit" hidden />
      </form>
    </DrawerShell>
  )
}
