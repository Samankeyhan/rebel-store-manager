"use client"

import * as React from "react"
import { DrawerShell, FieldError, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Btn } from "@/components/record-sale/primitives"
import { ApiError, createExpenseCategory, type ExpenseCategory } from "@/lib/api"
import { E } from "./copy"

/**
 * «دسته جدید»: just a name (the API has create only — no rename, no
 * deactivate). Opened from the desktop «دسته‌ها» card and from the form's
 * category menu (the only way on mobile, and on a first run with none).
 */
export function NewCategoryDialog({
  open,
  mobile,
  onClose,
  onCreated,
}: {
  open: boolean
  mobile: boolean
  onClose: () => void
  onCreated: (category: ExpenseCategory) => void
}) {
  const [name, setName] = React.useState("")
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [fieldError, setFieldError] = React.useState<string | null>(null)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)

  const [wasOpen, setWasOpen] = React.useState(false)
  if (open && !wasOpen) {
    setWasOpen(true)
    setName("")
    setTouched(false)
    setFieldError(null)
    setError(null)
  } else if (!open && wasOpen) {
    setWasOpen(false)
  }

  const nameError = touched && !name.trim() ? E.categoryNameRequired : fieldError
  const save = async () => {
    setTouched(true)
    if (!name.trim() || busy) return
    setBusy(true)
    setError(null)
    setFieldError(null)
    try {
      onCreated(await createExpenseCategory(name.trim()))
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setFieldError(E.categoryExists)
      else if (e instanceof ApiError && e.status === 422 && e.field === "name") setFieldError(E.categoryNameRequired)
      else
        setError(
          e instanceof ApiError
            ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `EXPENSES_${e.status}` }
            : { message: String(e), code: "UNKNOWN" }
        )
    } finally {
      setBusy(false)
    }
  }

  return (
    <DrawerShell
      open={open}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={E.newCategoryTitle}
      busy={busy}
      footer={
        <>
          <Btn variant="primary" disabled={busy} aria-busy={busy || undefined} onClick={save}>
            {E.create}
          </Btn>
          <Btn disabled={busy} onClick={onClose}>
            {E.cancel}
          </Btn>
        </>
      }
    >
      {error && <SaveError {...error} />}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="exp-cat-name" className="text-[13px] font-semibold">
          {E.fieldCategoryName}
        </label>
        <input
          id="exp-cat-name"
          autoFocus
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            setFieldError(null)
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") save()
          }}
          placeholder={E.categoryNamePlaceholder}
          className={textInputClass(mobile, !!nameError)}
          aria-invalid={!!nameError || undefined}
        />
        {nameError && <FieldError>{nameError}</FieldError>}
      </div>
    </DrawerShell>
  )
}
