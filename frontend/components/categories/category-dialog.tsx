"use client"

import * as React from "react"
import { ChevronDown } from "lucide-react"
import { Segment } from "@/components/common/segment"
import { DrawerShell, FieldError, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Alert, Btn } from "@/components/record-sale/primitives"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { createCategory, renameCategory, type Category, type CategoryKind, type CategoryTree } from "@/lib/api"
import { cn } from "@/lib/utils"
import { C } from "./copy"
import { refusalOf, siblingClash, type CategoryNode, type Count } from "./logic"

export type CategoryForm =
  | { mode: "create"; parentId: number | null }
  | { mode: "rename"; node: CategoryNode }

type Level = "top" | "sub"

/**
 * Create a top-level category or a subcategory, or rename one. Kind comes
 * from the screen's switch and never changes; neither does a parent
 * (update_category only renames).
 */
export function CategoryDialog({
  form,
  kind,
  tree,
  counts,
  mobile,
  onClose,
  onSaved,
  onStale,
}: {
  form: CategoryForm | null
  kind: CategoryKind
  tree: CategoryTree[]
  counts: Map<number, Count>
  mobile: boolean
  onClose: () => void
  onSaved: (category: Category, mode: CategoryForm["mode"]) => void
  /** The tree was out of date: refetch it. */
  onStale: () => void
}) {
  // Keep the last form while the drawer animates closed.
  const [last, setLast] = React.useState(form)
  if (form && form !== last) setLast(form)
  const f = form ?? last

  const [name, setName] = React.useState("")
  const [level, setLevel] = React.useState<Level>("top")
  const [parentId, setParentId] = React.useState<number | null>(null)
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  // The name the server called a duplicate; the message is worked out from
  // the (reloaded) tree at render, so it can say whether the sibling is inactive.
  const [serverDup, setServerDup] = React.useState<string | null>(null)
  const [parentError, setParentError] = React.useState<string | null>(null)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)

  const [opened, setOpened] = React.useState<CategoryForm | null>(null)
  if (form && form !== opened) {
    setOpened(form)
    setName(form.mode === "rename" ? form.node.name : "")
    setLevel(form.mode === "create" && form.parentId != null ? "sub" : "top")
    setParentId(form.mode === "create" ? form.parentId : null)
    setTouched(false)
    setServerDup(null)
    setParentError(null)
    setError(null)
  } else if (!form && opened) {
    setOpened(null)
  }

  if (!f) return null

  const parents = tree.filter((t) => t.is_active === 1)
  const renaming = f.mode === "rename" ? f.node : null
  // A rename stays at its own level; the parent is the node's own.
  const effectiveParent = renaming ? renaming.parent_id : level === "sub" ? parentId : null
  const parent = effectiveParent == null ? null : (tree.find((t) => t.id === effectiveParent) ?? null)
  const trimmed = name.trim()

  const clash = trimmed ? siblingClash(tree, effectiveParent, trimmed, renaming?.id ?? null) : null
  const dupMessage = (kindOf: "active" | "inactive" | null) =>
    kindOf === "inactive" ? C.duplicateInactive(trimmed) : kindOf === "active" ? C.duplicateActive(trimmed) : C.duplicateUnknown
  let nameError: string | null = null
  if (touched && !trimmed) nameError = C.nameRequired
  else if (touched && clash) nameError = dupMessage(clash)
  else if (serverDup != null && serverDup === trimmed) nameError = dupMessage(clash)

  const parentMissing = !renaming && level === "sub" && parentId == null
  const shownParentError = parentError ?? (touched && parentMissing ? C.parentRequired : null)
  const parentItems = parent && !renaming ? (counts.get(parent.id)?.total ?? 0) : 0

  const save = async () => {
    setTouched(true)
    if (!trimmed || clash || parentMissing || busy) return
    if (renaming && trimmed === renaming.name) {
      onClose()
      return
    }
    setBusy(true)
    setError(null)
    setParentError(null)
    try {
      const saved = renaming
        ? await renameCategory(renaming.id, trimmed)
        : await createCategory({ kind, name: trimmed, parent_id: effectiveParent })
      onSaved(saved, f.mode)
    } catch (e) {
      const r = refusalOf(e)
      if (r.kind === "duplicate") {
        setServerDup(trimmed)
        onStale()
      } else if (r.kind === "field" && r.field === "name") {
        setName("")
      } else if (r.kind === "field" && r.field === "parent_id") {
        setParentId(null)
        setParentError(C.parentUnavailable)
        onStale()
      } else if (r.kind === "other") {
        setError({ message: r.message, code: r.code })
      } else {
        setError({ message: e instanceof Error ? e.message : String(e), code: "CATEGORIES_409" })
      }
    } finally {
      setBusy(false)
    }
  }

  const title = renaming ? C.renameTitle : level === "sub" ? C.newSubTitle : C.newTitle

  return (
    <DrawerShell
      open={form != null}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={title}
      busy={busy}
      footer={
        <>
          <Btn
            variant="primary"
            size={mobile ? "lg" : "md"}
            className={mobile ? "grow" : undefined}
            disabled={busy}
            aria-busy={busy || undefined}
            onClick={save}
          >
            {busy && <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />}
            {renaming ? C.save : C.create}
          </Btn>
          <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={onClose}>
            {C.cancel}
          </Btn>
        </>
      }
    >
      {error && <SaveError {...error} />}

      {!renaming && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-semibold">{C.fieldLevel}</span>
          <Segment
            value={level}
            label={C.fieldLevel}
            mobile={mobile}
            options={[
              ["top", C.levelTop],
              ["sub", C.levelSub],
            ]}
            onChange={(v) => {
              setLevel(v)
              setParentError(null)
            }}
          />
          {level === "top" && <span className="text-xs text-text-3">{C.topHelp}</span>}
        </div>
      )}

      {!renaming && level === "sub" && (
        <div className="flex flex-col gap-1.5">
          <span id="cat-parent-label" className="text-[13px] font-semibold">
            {C.fieldParent}
          </span>
          {parents.length === 0 ? (
            <span className="text-xs text-text-3">{C.noParents}</span>
          ) : (
            <ParentPicker
              parents={parents}
              value={parentId}
              mobile={mobile}
              error={!!shownParentError}
              onChange={(id) => {
                setParentId(id)
                setParentError(null)
              }}
            />
          )}
          {shownParentError && <FieldError>{shownParentError}</FieldError>}
        </div>
      )}

      {renaming && parent && (
        <div className="text-[13px] text-text-2">
          {C.levelSub} · {C.fieldParent}: <b>{parent.name}</b>
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label htmlFor="cat-name" className="text-[13px] font-semibold">
          {C.fieldName}
        </label>
        <input
          id="cat-name"
          autoFocus
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            setServerDup(null)
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") save()
          }}
          placeholder={C.namePlaceholder}
          className={textInputClass(mobile, !!nameError)}
          aria-invalid={!!nameError || undefined}
        />
        {nameError && <FieldError>{nameError}</FieldError>}
      </div>

      {parentItems > 0 && parent && (
        <Alert tone="warn" icon="triangle">
          {C.splitWarn(parentItems, kind, parent.name)}
        </Alert>
      )}
    </DrawerShell>
  )
}

/** Active top-level categories of this kind: the only valid parents. */
function ParentPicker({
  parents,
  value,
  mobile,
  error,
  onChange,
}: {
  parents: CategoryTree[]
  value: number | null
  mobile: boolean
  error: boolean
  onChange: (id: number) => void
}) {
  const label = parents.find((p) => p.id === value)?.name ?? null
  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-labelledby="cat-parent-label"
          className={cn(textInputClass(mobile, error), "flex cursor-pointer items-center justify-between")}
        >
          <span className={label ? "" : "text-text-3"}>{label ?? C.pickParent}</span>
          <ChevronDown className="size-3.5 text-text-3" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-80 w-(--radix-dropdown-menu-trigger-width) overflow-y-auto">
        <DropdownMenuRadioGroup value={value == null ? "" : String(value)} onValueChange={(v) => onChange(Number(v))}>
          {parents.map((p) => (
            <DropdownMenuRadioItem key={p.id} value={String(p.id)}>
              {p.name}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
