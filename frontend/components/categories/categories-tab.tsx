"use client"

import * as React from "react"
import { ArrowLeftRight, Ban, Eye, FolderPlus, FolderTree, MoreHorizontal, Pencil, Plus, RotateCcw, TriangleAlert } from "lucide-react"
import { StateShell } from "@/components/common/screen-states"
import { ActiveBadge, Chip } from "@/components/products/badges"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { CategoryKind, CategoryTree } from "@/lib/api"
import { cn } from "@/lib/utils"
import { C } from "./copy"
import type { CategoryNode, Count } from "./logic"

export type CategoryActions = {
  onAddSub: (parent: CategoryTree) => void
  onRename: (node: CategoryNode) => void
  /** null = the uncategorised materials. */
  onMove: (node: CategoryNode | null) => void
  onDeactivate: (node: CategoryNode) => void
  onReactivate: (node: CategoryNode) => void
  /** Open the products/materials tab filtered to this category. */
  onShowItems: (node: CategoryNode) => void
}

type Row = {
  node: CategoryNode
  /** The parent of a subcategory. */
  parent: CategoryTree | null
  count: Count
  /** Items still on a parent that has active subcategories (leaf rule). */
  stranded: boolean
}

const ZERO: Count = { total: 0, inactive: 0 }

function buildRows(tree: CategoryTree[], counts: Map<number, Count>, showInactive: boolean): Row[] {
  const rows: Row[] = []
  for (const t of tree) {
    if (!showInactive && t.is_active !== 1) continue
    const count = counts.get(t.id) ?? ZERO
    const split = t.children.some((c) => c.is_active === 1)
    rows.push({ node: t, parent: null, count, stranded: split && count.total > 0 })
    for (const c of t.children) {
      if (!showInactive && c.is_active !== 1) continue
      rows.push({ node: c, parent: t, count: counts.get(c.id) ?? ZERO, stranded: false })
    }
  }
  return rows
}

/** The menu entries a row offers, in order. Shared by the desktop buttons and the mobile menu. */
function rowActions(row: Row, a: CategoryActions) {
  const { node, parent, count } = row
  const active = node.is_active === 1
  const parentInactive = parent != null && parent.is_active !== 1
  const list: { key: string; label: string; icon: React.ComponentType<{ className?: string }>; run: () => void; disabled?: boolean }[] = []
  if (parent == null && active) list.push({ key: "sub", label: C.addSub, icon: FolderPlus, run: () => a.onAddSub(node as CategoryTree) })
  list.push({ key: "rename", label: C.rename, icon: Pencil, run: () => a.onRename(node) })
  if (count.total > 0) list.push({ key: "move", label: C.move, icon: ArrowLeftRight, run: () => a.onMove(node) })
  if (active) list.push({ key: "off", label: C.deactivate, icon: Ban, run: () => a.onDeactivate(node) })
  else
    list.push({ key: "on", label: C.reactivate, icon: RotateCcw, run: () => a.onReactivate(node), disabled: parentInactive })
  return list
}

/** Count text, as a link to the filtered list when there are items. */
function CountCell({ row, kind, onShow }: { row: Row; kind: CategoryKind; onShow: () => void }) {
  const { count } = row
  if (count.total === 0) return <span className="text-text-3">{C.noItems}</span>
  return (
    <button
      type="button"
      onClick={onShow}
      title={C.showItems(kind)}
      className="cursor-pointer rounded text-start font-semibold text-heading underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/30"
    >
      {C.itemCount(count.total, kind)}
      {count.inactive > 0 && <span className="ms-1 text-xs font-normal text-text-3">{C.inactiveCount(count.inactive)}</span>}
    </button>
  )
}

/** Sub-lines under a name: the leaf-rule warning, or why reactivation is unavailable. */
function Notes({ row, kind, onMove }: { row: Row; kind: CategoryKind; onMove?: () => void }) {
  const parentInactive = row.parent != null && row.parent.is_active !== 1 && row.node.is_active !== 1
  return (
    <>
      {row.stranded && (
        <span role="status" className="flex flex-wrap items-center gap-1.5 text-xs whitespace-normal text-warn">
          <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
          <span>{C.strandedNote(row.count.total, kind, row.node.name)}</span>
          {onMove && (
            <Btn variant="link" className="text-xs" onClick={onMove}>
              {C.moveShort}
            </Btn>
          )}
        </span>
      )}
      {parentInactive && row.parent && (
        <span className="text-xs whitespace-normal text-text-3">{C.parentInactiveNote(row.parent.name)}</span>
      )}
    </>
  )
}

export function CategoriesTab({
  kind,
  tree,
  counts,
  uncategorised,
  showInactive,
  mobile,
  actions,
  onAdd,
  onShowInactive,
}: {
  kind: CategoryKind
  tree: CategoryTree[]
  counts: Map<number, Count>
  /** Materials with no category (always 0 for products: a product must have one). */
  uncategorised: Count
  showInactive: boolean
  mobile: boolean
  actions: CategoryActions
  onAdd: () => void
  onShowInactive: () => void
}) {
  if (tree.length === 0) {
    return (
      <StateShell
        icon={FolderTree}
        mobile={mobile}
        title={C.emptyTitle(kind)}
        body={C.emptyBody(kind)}
        action={
          <Btn variant="primary" size={mobile ? "lg" : "md"} className="mt-1.5" onClick={onAdd}>
            <Plus className="size-4" />
            {C.emptyCta}
          </Btn>
        }
      />
    )
  }
  const rows = buildRows(tree, counts, showInactive)
  if (rows.length === 0) {
    return (
      <StateShell
        icon={FolderTree}
        mobile={mobile}
        title={C.allInactiveTitle}
        action={
          <Btn size={mobile ? "lg" : "md"} className="mt-1" onClick={onShowInactive}>
            <Eye className="size-4" />
            {C.allInactiveCta}
          </Btn>
        }
      />
    )
  }

  if (mobile) return <MobileList kind={kind} rows={rows} uncategorised={uncategorised} actions={actions} />

  return (
    <div className="flex flex-col gap-4">
      <section className={cn(cardClass, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col" className="w-full">
                  {C.colName}
                </th>
                <th scope="col">{C.colItems}</th>
                <th scope="col">{C.colStatus}</th>
                <th scope="col" className="w-[160px]">
                  <span className="sr-only">{C.colActions}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const active = row.node.is_active === 1
                const sub = row.parent != null
                return (
                  <tr
                    key={row.node.id}
                    className={cn(
                      "[&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:py-2 [&>td]:whitespace-nowrap last:[&>td]:border-b-0",
                      row.stranded ? "[&>td]:bg-warn-soft/55" : "hover:[&>td]:bg-surface-2",
                      !active && "opacity-55"
                    )}
                  >
                    <td>
                      <div className={cn("flex flex-col gap-1 leading-tight", sub && "ps-7")}>
                        <span className="flex items-center gap-2">
                          {sub && <span className="h-px w-3 shrink-0 bg-border-strong" aria-hidden />}
                          <span className={cn(sub ? "font-semibold" : "font-bold")}>{row.node.name}</span>
                          {sub && <Chip className="h-5">{C.subChip}</Chip>}
                        </span>
                        <Notes row={row} kind={kind} onMove={() => actions.onMove(row.node)} />
                      </div>
                    </td>
                    <td>
                      <CountCell row={row} kind={kind} onShow={() => actions.onShowItems(row.node)} />
                    </td>
                    <td>
                      <ActiveBadge active={active} />
                    </td>
                    <td>
                      <span className="flex justify-end gap-1">
                        {rowActions(row, actions).map((act) => (
                          <Btn
                            key={act.key}
                            variant="ghost"
                            size="sm"
                            className="size-8 px-0"
                            aria-label={`${act.label} — ${row.node.name}`}
                            title={act.label}
                            disabled={act.disabled}
                            onClick={act.run}
                          >
                            <act.icon className="size-4" />
                          </Btn>
                        ))}
                      </span>
                    </td>
                  </tr>
                )
              })}
              {uncategorised.total > 0 && (
                <tr className="[&>td]:h-[52px] [&>td]:border-t [&>td]:border-border [&>td]:bg-surface-2/60 [&>td]:px-4 [&>td]:whitespace-nowrap">
                  <td>
                    <div className="flex flex-col gap-0.5 leading-tight">
                      <span className="font-bold text-text-2">{C.uncategorised}</span>
                      <span className="text-xs text-text-3">{C.uncategorisedHelp}</span>
                    </div>
                  </td>
                  <td className="font-semibold">
                    {C.itemCount(uncategorised.total, kind)}
                    {uncategorised.inactive > 0 && (
                      <span className="ms-1 text-xs font-normal text-text-3">{C.inactiveCount(uncategorised.inactive)}</span>
                    )}
                  </td>
                  <td />
                  <td>
                    <span className="flex justify-end">
                      <Btn
                        variant="ghost"
                        size="sm"
                        className="size-8 px-0"
                        aria-label={`${C.move} — ${C.uncategorised}`}
                        title={C.move}
                        onClick={() => actions.onMove(null)}
                      >
                        <ArrowLeftRight className="size-4" />
                      </Btn>
                    </span>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      <p className="text-xs text-text-3">{C.footnote}</p>
    </div>
  )
}

function MobileList({
  kind,
  rows,
  uncategorised,
  actions,
}: {
  kind: CategoryKind
  rows: Row[]
  uncategorised: Count
  actions: CategoryActions
}) {
  // One card per top-level category, its subcategories nested inside.
  const groups: Row[][] = []
  for (const row of rows) {
    if (row.parent == null) groups.push([row])
    else groups[groups.length - 1]?.push(row)
  }
  return (
    <div className="flex flex-col gap-3">
      {groups.map(([top, ...children]) => (
        <section key={top.node.id} className={cn(cardClass, "flex flex-col", top.stranded && "border-warn")}>
          <MobileRow row={top} kind={kind} actions={actions} />
          {children.map((c) => (
            <div key={c.node.id} className="border-t border-border ps-4">
              <MobileRow row={c} kind={kind} actions={actions} />
            </div>
          ))}
        </section>
      ))}
      {uncategorised.total > 0 && (
        <section className={cn(cardClass, "flex items-center gap-2 bg-surface-2/60 px-3.5 py-3")}>
          <div className="flex min-w-0 grow flex-col gap-0.5">
            <span className="font-bold text-text-2">{C.uncategorised}</span>
            <span className="text-xs text-text-3">{C.itemCount(uncategorised.total, kind)}</span>
          </div>
          <Btn size="lg" className="h-11" onClick={() => actions.onMove(null)}>
            <ArrowLeftRight className="size-4" />
            {C.moveShort}
          </Btn>
        </section>
      )}
      <p className="text-xs text-text-3">{C.footnote}</p>
    </div>
  )
}

function MobileRow({ row, kind, actions }: { row: Row; kind: CategoryKind; actions: CategoryActions }) {
  const active = row.node.is_active === 1
  const sub = row.parent != null
  return (
    <div className="flex items-start gap-2 px-3.5 py-3">
      <div className={cn("flex min-w-0 grow flex-col gap-1.5", !active && "opacity-55")}>
        <span className="flex items-center gap-2">
          <span className={cn(sub ? "font-semibold" : "font-bold")}>{row.node.name}</span>
          {sub && <Chip className="h-5">{C.subChip}</Chip>}
        </span>
        <span className="flex items-center gap-2 text-xs">
          <CountCell row={row} kind={kind} onShow={() => actions.onShowItems(row.node)} />
          <ActiveBadge active={active} />
        </span>
        <Notes row={row} kind={kind} />
      </div>
      <DropdownMenu dir="rtl">
        <DropdownMenuTrigger asChild>
          <Btn variant="ghost" className="size-11 px-0" aria-label={C.moreActions(row.node.name)}>
            <MoreHorizontal className="size-5" />
          </Btn>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-52">
          {rowActions(row, actions).map((act) => (
            <DropdownMenuItem key={act.key} disabled={act.disabled} onSelect={act.run} className="min-h-11 gap-2.5">
              <act.icon className="size-4" />
              {act.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
