"use client"

import * as React from "react"
import { DrawerShell, FieldError, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Btn } from "@/components/record-sale/primitives"
import { nameDuplicateMessage } from "@/components/common/copy"
import { ApiError, createKit, type KitDetail } from "@/lib/api"
import { duplicateEntity, isNameDuplicate } from "@/lib/error-codes"
import { K } from "./copy"

/** «کیت جدید»: a name, then the kit opens in the editor to add its materials. */
export function NewKitDialog({
  open,
  mobile,
  onClose,
  onCreated,
}: {
  open: boolean
  mobile: boolean
  onClose: () => void
  onCreated: (kit: KitDetail) => void
}) {
  const [name, setName] = React.useState("")
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const [duplicate, setDuplicate] = React.useState<string | null>(null)

  const [wasOpen, setWasOpen] = React.useState(false)
  if (open && !wasOpen) {
    setWasOpen(true)
    setName("")
    setTouched(false)
    setError(null)
    setDuplicate(null)
  } else if (!open && wasOpen) {
    setWasOpen(false)
  }

  const nameError = touched && !name.trim()
  const save = async () => {
    setTouched(true)
    // The API accepts an empty name; the screen doesn't.
    if (!name.trim() || busy) return
    setBusy(true)
    setError(null)
    setDuplicate(null)
    try {
      onCreated(await createKit(name.trim()))
    } catch (e) {
      if (e instanceof ApiError && isNameDuplicate(e)) setDuplicate(nameDuplicateMessage(duplicateEntity(e)))
      else
      setError(
        e instanceof ApiError
          ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `PACKAGING_${e.status}` }
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
      title={K.newKitTitle}
      busy={busy}
      footer={
        <>
          <Btn variant="primary" disabled={busy} aria-busy={busy || undefined} onClick={save}>
            {K.create}
          </Btn>
          <Btn disabled={busy} onClick={onClose}>
            {K.cancel}
          </Btn>
        </>
      }
    >
      {error && <SaveError {...error} />}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="kit-name" className="text-[13px] font-semibold">
          {K.fieldName}
        </label>
        <input
          id="kit-name"
          autoFocus
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            setDuplicate(null)
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") save()
          }}
          placeholder={K.namePlaceholder}
          className={textInputClass(mobile, nameError || duplicate != null)}
          aria-invalid={nameError || duplicate != null || undefined}
        />
        {nameError && <FieldError>{K.nameRequired}</FieldError>}
        {duplicate && <FieldError>{duplicate}</FieldError>}
        <span className="text-xs text-text-3">{K.nameReadOnly}</span>
      </div>
    </DrawerShell>
  )
}
