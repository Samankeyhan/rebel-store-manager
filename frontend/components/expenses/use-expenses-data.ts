"use client"

import * as React from "react"
import {
  getExpenseBreakdown,
  getSettings,
  listExpenseCategories,
  listExpenses,
  type Expense,
  type ExpenseBreakdown,
  type ExpenseCategory,
} from "@/lib/api"
import type { IsoRange } from "@/lib/jalali"

type Categories = { status: "loading" } | { status: "error" } | { status: "ready"; all: ExpenseCategory[] }
type List = { status: "loading" } | { status: "error" } | { status: "ready"; rows: Expense[] }
type Breakdown = { status: "loading" } | { status: "error" } | { status: "ready"; rows: ExpenseBreakdown[] }

const DEFAULT_TZ = "Asia/Tehran"

/**
 * Expense categories (active and inactive — the filter shows both, the form
 * only active ones), the expense list for {category, range} and the
 * per-category breakdown for the range (GET /reports/expenses has no
 * category filter, so it always covers every category).
 */
export function useExpensesData(filters: { categoryId: number | null; range: IsoRange }) {
  const [categories, setCategories] = React.useState<Categories>({ status: "loading" })
  const [list, setList] = React.useState<List>({ status: "loading" })
  const [breakdown, setBreakdown] = React.useState<Breakdown>({ status: "loading" })
  const [timeZone, setTimeZone] = React.useState(DEFAULT_TZ)
  const [attempt, setAttempt] = React.useState(0)
  const [listAttempt, setListAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    listExpenseCategories(false).then(
      (all) => !cancelled && setCategories({ status: "ready", all }),
      () => !cancelled && setCategories({ status: "error" })
    )
    getSettings().then(
      (s) => !cancelled && setTimeZone(s.timezone || DEFAULT_TZ),
      () => {}
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const { categoryId } = filters
  const { from, to } = filters.range
  React.useEffect(() => {
    let cancelled = false
    listExpenses({ categoryId, from, to }).then(
      (rows) => !cancelled && setList({ status: "ready", rows }),
      () => !cancelled && setList({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [categoryId, from, to, attempt, listAttempt])

  React.useEffect(() => {
    let cancelled = false
    getExpenseBreakdown({ from, to }).then(
      (rows) => !cancelled && setBreakdown({ status: "ready", rows }),
      () => !cancelled && setBreakdown({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [from, to, attempt, listAttempt])

  const reload = React.useCallback(() => {
    setCategories({ status: "loading" })
    setList({ status: "loading" })
    setBreakdown({ status: "loading" })
    setAttempt((a) => a + 1)
  }, [])

  /** After a save: the list and the breakdown, quietly (no loading flash). */
  const refreshList = React.useCallback(() => setListAttempt((a) => a + 1), [])

  /** Categories again, quietly — after one was created or turned out gone. */
  const refreshCategories = React.useCallback(async () => {
    const all = await listExpenseCategories(false)
    setCategories({ status: "ready", all })
  }, [])

  /** A just-created category, without a round trip (kept in name order). */
  const addCategory = React.useCallback((c: ExpenseCategory) => {
    setCategories((s) =>
      s.status === "ready"
        ? { status: "ready", all: [...s.all.filter((x) => x.id !== c.id), c].sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0)) }
        : s
    )
  }, [])

  return { categories, list, breakdown, timeZone, reload, refreshList, refreshCategories, addCategory }
}
