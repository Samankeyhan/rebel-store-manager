"use client"

import * as React from "react"
import { ArrowLeftRight, Ban, ChartColumn, EyeOff, FolderTree, Package } from "lucide-react"
import { ConfirmShell, Effect } from "@/components/orders/detail/confirm-shell"
import type { CategoryKind } from "@/lib/api"
import { C } from "./copy"
import type { CategoryNode } from "./logic"

/** What stands in the way, from the local data or from the server's 409. */
export type Blockers = {
  /** Items using the category; null when the server said so without a number. */
  items: number | null
  /** Active subcategory names; [] with `children` true when only the server knows. */
  activeChildren: string[]
  children: boolean
}

export const hasBlockers = (b: Blockers) => b.items !== 0 || b.children

/**
 * deactivate_category refuses while anything (inactive items too) uses the
 * category or it has active subcategories. When either is known to hold, the
 * dialog opens in its blocked state: the reasons, and «انتقال …» in place of
 * the confirm button when items are the problem.
 */
export function DeactivateCategoryDialog({
  target,
  kind,
  blockers,
  mobile,
  busy,
  onCancel,
  onConfirm,
  onMove,
}: {
  target: CategoryNode | null
  kind: CategoryKind
  blockers: Blockers
  mobile: boolean
  busy: boolean
  onCancel: () => void
  onConfirm: () => void
  onMove: (node: CategoryNode) => void
}) {
  // Keep the last target while the dialog animates closed.
  const [last, setLast] = React.useState(target)
  if (target && target !== last) setLast(target)
  const t = target ?? last
  if (!t) return null

  const blocked = hasBlockers(blockers)
  const itemsBlock = blockers.items !== 0
  if (blocked) {
    return (
      <ConfirmShell
        open={target != null}
        onOpenChange={(o) => !o && onCancel()}
        mobile={mobile}
        busy={false}
        icon={Ban}
        title={C.blockedTitle(t.name)}
        subtitle={C.blockedSubtitle}
        // Items are the fix the user can make here; subcategories are
        // deactivated from their own rows.
        confirmLabel={itemsBlock ? C.moveItems(kind) : C.understood}
        confirmIcon={itemsBlock ? ArrowLeftRight : undefined}
        danger={false}
        onConfirm={() => (itemsBlock ? onMove(t) : onCancel())}
        width={520}
      >
        <div role="alert" className="flex flex-col gap-2.5">
          {itemsBlock && (
            <Effect tone="down" icon={Package}>
              {blockers.items == null ? C.blockedItemsNoCount(kind) : C.blockedItems(blockers.items, kind)}
            </Effect>
          )}
          {blockers.children && (
            <Effect tone="down" icon={FolderTree}>
              {C.blockedChildren(blockers.activeChildren)}
            </Effect>
          )}
        </div>
      </ConfirmShell>
    )
  }

  return (
    <ConfirmShell
      open={target != null}
      onOpenChange={(o) => !o && onCancel()}
      mobile={mobile}
      busy={busy}
      icon={Ban}
      title={C.deactivateTitle(t.name)}
      subtitle={C.deactivateSubtitle}
      confirmLabel={C.deactivate}
      confirmIcon={Ban}
      onConfirm={onConfirm}
      width={520}
    >
      <Effect tone="flat" icon={EyeOff}>
        {C.effHidden}
      </Effect>
      <Effect tone="flat" icon={ChartColumn}>
        {C.effHistory}
      </Effect>
      <p className="text-xs text-text-3">{C.deactivateFinal}</p>
    </ConfirmShell>
  )
}
