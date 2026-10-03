"use client"

import * as React from "react"
import { ArrowLeftRight, Check, RotateCw } from "lucide-react"
import { CategoryPicker } from "@/components/products/category-picker"
import { DrawerShell, FieldError } from "@/components/products/drawer-shell"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { badgeBase } from "@/components/common/status"
import type { CategoryKind, CategoryTree } from "@/lib/api"
import { cn } from "@/lib/utils"
import { C } from "./copy"
import { refusalOf, type CategoryNode } from "./logic"

export type MovableItem = { id: number; name: string; is_active: number; category_id: number | null }

/** queued → submitting → done | failed; failed → queued («تلاش دوباره…»). */
type RowStatus =
  | { kind: "idle" }
  | { kind: "queued" }
  | { kind: "submitting" }
  | { kind: "done" }
  | { kind: "failed"; message: string; code: string | null }

type Row = { id: number; name: string; inactive: boolean; status: RowStatus }

export type MoveSource = { from: CategoryNode | null }

/**
 * Bulk move. The API moves one item per PATCH, so this is the multi-line
 * production run's pattern: one request at a time, top to bottom; a failure
 * is recorded on its row and the loop goes on; «تلاش دوباره» re-runs only
 * the failed rows. Each success is applied to the page right away.
 */
export function MoveItemsSheet({
  source,
  kind,
  tree,
  items,
  mobile,
  onClose,
  move,
  onFinished,
  onStale,
}: {
  /** null = closed; `from: null` = the uncategorised materials. */
  source: MoveSource | null
  kind: CategoryKind
  tree: CategoryTree[]
  /** Every item of this kind (the source's are picked out when it opens). */
  items: MovableItem[]
  mobile: boolean
  onClose: () => void
  /** One PATCH; resolves once the page has the updated item. */
  move: (itemId: number, categoryId: number) => Promise<void>
  onFinished: (moved: number, destinationName: string) => void
  /** A destination was refused as unassignable: the tree is stale. */
  onStale: () => void
}) {
  const [last, setLast] = React.useState(source)
  if (source && source !== last) setLast(source)
  const s = source ?? last

  const [rows, setRows] = React.useState<Row[]>([])
  const [selected, setSelected] = React.useState<Set<number>>(new Set())
  const [dest, setDest] = React.useState<number | null>(null)
  const [touched, setTouched] = React.useState(false)
  const [running, setRunning] = React.useState<{ done: number; total: number } | null>(null)
  const [summary, setSummary] = React.useState<{ ok: number; failed: number } | null>(null)

  // Snapshot the source's items when the sheet opens; moved rows stay
  // listed (marked done) so the outcome of every item is visible.
  const [opened, setOpened] = React.useState<MoveSource | null>(null)
  if (source && source !== opened) {
    setOpened(source)
    const fromId = source.from?.id ?? null
    const initial = items
      .filter((it) => it.category_id === fromId)
      .map((it) => ({ id: it.id, name: it.name, inactive: it.is_active !== 1, status: { kind: "idle" } as RowStatus }))
    setRows(initial)
    setSelected(new Set(initial.map((r) => r.id)))
    setDest(null)
    setTouched(false)
    setRunning(null)
    setSummary(null)
  } else if (!source && opened) {
    setOpened(null)
  }

  if (!s) return null

  const busy = running != null
  const destName = dest == null ? "" : pathName(tree, dest)
  const movable = rows.filter((r) => r.status.kind !== "done")
  const chosen = movable.filter((r) => selected.has(r.id))
  const failed = rows.filter((r) => r.status.kind === "failed")
  const allChosen = movable.length > 0 && chosen.length === movable.length
  const hasDestination = tree.some(
    (t) =>
      t.is_active === 1 &&
      (t.children.some((c) => c.is_active === 1)
        ? t.children.some((c) => c.is_active === 1 && c.id !== s.from?.id)
        : t.id !== s.from?.id)
  )

  const setStatus = (id: number, status: RowStatus) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, status } : r)))

  const run = async (batch: Row[]) => {
    setTouched(true)
    if (batch.length === 0 || dest == null || busy) return
    const target = dest
    const targetName = destName
    setSummary(null)
    const ids = new Set(batch.map((r) => r.id))
    setRows((rs) => rs.map((r) => (ids.has(r.id) ? { ...r, status: { kind: "queued" } } : r)))
    setRunning({ done: 0, total: batch.length })

    let ok = 0
    let stale = false
    for (const [i, row] of batch.entries()) {
      setStatus(row.id, { kind: "submitting" })
      try {
        await move(row.id, target)
        ok += 1
        setStatus(row.id, { kind: "done" })
        setSelected((sel) => {
          const next = new Set(sel)
          next.delete(row.id)
          return next
        })
      } catch (e) {
        const r = refusalOf(e)
        if (r.kind === "field" && r.field === "category_id") {
          stale = true
          setStatus(row.id, { kind: "failed", message: C.destinationUnavailable, code: null })
        } else if (r.kind === "other") {
          setStatus(row.id, { kind: "failed", message: r.message, code: r.code })
        } else {
          setStatus(row.id, { kind: "failed", message: e instanceof Error ? e.message : String(e), code: null })
        }
      }
      setRunning({ done: i + 1, total: batch.length })
    }
    setRunning(null)
    if (stale) {
      // The destination stopped being assignable mid-run (deactivated or
      // split elsewhere): make the user pick again from a fresh tree.
      setDest(null)
      onStale()
    }
    if (ok < batch.length) setSummary({ ok, failed: batch.length - ok })
    if (ok > 0) onFinished(ok, targetName)
  }

  const toggle = (id: number) =>
    setSelected((sel) => {
      const next = new Set(sel)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const retryMode = failed.length > 0 && chosen.length > 0 && chosen.every((r) => r.status.kind === "failed")
  const fromName = s.from?.name ?? C.uncategorised

  return (
    <DrawerShell
      open={source != null}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={C.moveTitle(fromName)}
      busy={busy}
      footer={
        <>
          <Btn
            variant="primary"
            size={mobile ? "lg" : "md"}
            className={mobile ? "grow" : undefined}
            disabled={busy || chosen.length === 0 || !hasDestination}
            aria-busy={busy || undefined}
            onClick={() => run(chosen)}
          >
            {busy ? (
              <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />
            ) : retryMode ? (
              <RotateCw className="size-4" />
            ) : (
              <ArrowLeftRight className="size-4" />
            )}
            {busy ? C.progress(running.done, running.total) : retryMode ? C.retryFailed : C.moveN(chosen.length, kind)}
          </Btn>
          <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={onClose}>
            {rows.some((r) => r.status.kind === "done") ? C.close : C.cancel}
          </Btn>
        </>
      }
    >
      <div className="flex flex-col gap-1.5">
        <span id="move-dest-label" className="text-[13px] font-semibold">
          {C.fieldDestination}
        </span>
        {hasDestination ? (
          <>
            <CategoryPicker
              tree={tree}
              value={dest}
              onChange={(id) => setDest(id)}
              mobile={mobile}
              error={touched && dest == null}
              excludeId={s.from?.id}
              labelledBy="move-dest-label"
            />
            {touched && dest == null ? (
              <FieldError>{C.destinationRequired}</FieldError>
            ) : (
              <span className="text-xs text-text-3">{C.destinationHelp}</span>
            )}
          </>
        ) : (
          <span className="text-xs text-text-3">{C.noDestination}</span>
        )}
      </div>

      {summary && (
        <Alert tone="warn" icon="triangle">
          {C.summary(summary.ok, summary.failed)}
        </Alert>
      )}

      {rows.length === 0 ? (
        <p className="text-[13px] text-text-3">{C.emptySource}</p>
      ) : (
        <div className="flex flex-col">
          <label className="flex min-h-11 items-center gap-2.5 border-b border-border text-[13px] font-semibold">
            <input
              type="checkbox"
              className="size-4 accent-primary"
              checked={allChosen}
              disabled={busy || movable.length === 0}
              onChange={() => setSelected(allChosen ? new Set() : new Set(movable.map((r) => r.id)))}
            />
            <span className="grow">{C.selectAll}</span>
            <span className="text-xs font-normal text-text-3">{C.selectedOf(chosen.length, movable.length)}</span>
          </label>
          <ul aria-live="polite">
            {rows.map((r) => {
              const done = r.status.kind === "done"
              return (
                <li key={r.id} className="border-b border-border last:border-b-0">
                  <label className={cn("flex min-h-11 items-center gap-2.5 py-1.5 text-[13.5px]", done && "text-text-3")}>
                    <input
                      type="checkbox"
                      className="size-4 accent-primary"
                      checked={!done && selected.has(r.id)}
                      disabled={busy || done}
                      onChange={() => toggle(r.id)}
                    />
                    <span className={cn("min-w-0 grow truncate", r.inactive && "opacity-60")}>{r.name}</span>
                    {r.inactive && (
                      <span className={cn(badgeBase, "border border-dashed border-border-strong bg-card text-text-2")}>
                        {C.inactiveItem}
                      </span>
                    )}
                    <RowPill status={r.status} />
                  </label>
                  {r.status.kind === "failed" && (
                    <div role="alert" className="flex flex-col gap-0.5 pb-2 ps-[26px] text-xs text-loss">
                      <span dir="auto">{r.status.message}</span>
                      {r.status.code && (
                        <span dir="ltr" className="self-end font-mono text-text-3">
                          {r.status.code}
                        </span>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </DrawerShell>
  )
}

function RowPill({ status }: { status: RowStatus }) {
  switch (status.kind) {
    case "idle":
      return null
    case "queued":
      return <span className={cn(badgeBase, "bg-surface-2 text-text-3")}>{C.stQueued}</span>
    case "submitting":
      return (
        <span className={cn(badgeBase, "bg-info-soft text-info")}>
          <span className="size-3 animate-spin rounded-full border-2 border-info/30 border-t-info" aria-hidden />
          {C.stSubmitting}
        </span>
      )
    case "done":
      return (
        <span className={cn(badgeBase, "bg-profit-soft text-profit")}>
          <Check className="size-3" aria-hidden />
          {C.stDone}
        </span>
      )
    case "failed":
      return <span className={cn(badgeBase, "bg-loss-soft text-loss")}>{C.stFailed}</span>
  }
}

function pathName(tree: CategoryTree[], id: number): string {
  for (const t of tree) {
    if (t.id === id) return t.name
    const c = t.children.find((x) => x.id === id)
    if (c) return `${t.name} › ${c.name}`
  }
  return ""
}
