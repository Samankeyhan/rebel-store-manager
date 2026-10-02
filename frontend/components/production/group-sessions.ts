/**
 * Display-only grouping of production batches into the sittings they were
 * entered in. The backend has no session concept — every batch is its own
 * row — so this only reads created_at (when each batch was recorded).
 */

import type { ProductionBatchListItem } from "@/lib/api"

/**
 * Consecutive batches recorded at most this far apart belong to one sitting.
 * The run tab sends lines back to back, a second or two apart even for 50
 * lines, and the gap is measured between neighbours (not from the first
 * batch), so a long sitting is never split; five minutes leaves room for a
 * slow connection or a retry of failed lines, while separate sessions are
 * normally much further apart.
 */
export const SITTING_GAP_MS = 5 * 60 * 1000

export type Sitting = { key: string; size: number }

export type SittingGroup = {
  key: string
  /** The batches of this sitting that the current filters show, list order. */
  batches: ProductionBatchListItem[]
  /** How many batches the whole sitting has, filtered or not. */
  sittingSize: number
  /** Σ total_cost of the shown batches, or null if any is missing (pre-006). */
  total: number | null
}

function createdMs(b: ProductionBatchListItem): number | null {
  if (!b.created_at) return null
  const ms = Date.parse(`${b.created_at.replace(" ", "T")}Z`)
  return Number.isNaN(ms) ? null : ms
}

/**
 * Sitting of every batch, computed over the FULL unfiltered list, so a filter
 * can neither split a real sitting nor merge batches that had others between
 * them. A batch without created_at (recorded before it was stored) is always
 * a sitting of one.
 */
export function sittingIndex(all: ProductionBatchListItem[]): Map<number, Sitting> {
  const index = new Map<number, Sitting>()
  const timed: { batch: ProductionBatchListItem; ms: number }[] = []
  for (const batch of all) {
    const ms = createdMs(batch)
    if (ms == null) index.set(batch.id, { key: `b${batch.id}`, size: 1 })
    else timed.push({ batch, ms })
  }
  timed.sort((a, b) => a.ms - b.ms || a.batch.id - b.batch.id)

  let run: ProductionBatchListItem[] = []
  let last = -Infinity
  const flush = () => {
    if (run.length === 0) return
    const sitting = { key: `s${run[0].id}`, size: run.length }
    for (const b of run) index.set(b.id, sitting)
    run = []
  }
  for (const { batch, ms } of timed) {
    if (ms - last > SITTING_GAP_MS) flush()
    run.push(batch)
    last = ms
  }
  flush()
  return index
}

/** The filtered rows, grouped by sitting, in the order their first row appears. */
export function groupBySitting(rows: ProductionBatchListItem[], index: Map<number, Sitting>): SittingGroup[] {
  const groups = new Map<string, SittingGroup>()
  for (const batch of rows) {
    const sitting = index.get(batch.id) ?? { key: `b${batch.id}`, size: 1 }
    const group = groups.get(sitting.key)
    if (group) group.batches.push(batch)
    else groups.set(sitting.key, { key: sitting.key, batches: [batch], sittingSize: sitting.size, total: null })
  }
  for (const group of groups.values()) {
    // A sum only when every batch has its real total; never a partial figure.
    group.total = group.batches.every((b) => b.total_cost != null)
      ? group.batches.reduce((s, b) => s + b.total_cost!, 0)
      : null
  }
  return [...groups.values()]
}
