"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { CalendarDays, ChevronDown, Plus, Search, SearchX, Wallet } from "lucide-react"
import { subMonths } from "date-fns-jalali"
import { useIsMobile } from "@/hooks/use-mobile"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { Toast } from "@/components/common/toast"
import { DateRangePopover, rangeLabel } from "@/components/orders/list/date-range-popover"
import { norm } from "@/components/products/figures"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import type { Expense, ExpenseCategory } from "@/lib/api"
import { dateToISO, formatJalali, jalaliMonthRange, utcToLocal, wholeMonthLabel, type IsoRange } from "@/lib/jalali"
import { Money } from "@/components/common/money"
import { formatMoney } from "@/lib/money"
import { cn } from "@/lib/utils"
import { BreakdownCard, MobileSummary } from "./category-breakdown"
import { CategoryCard } from "./category-card"
import { E } from "./copy"
import { ExpenseDialog } from "./expense-dialog"
import { NewCategoryDialog } from "./new-category-dialog"
import { useExpensesData } from "./use-expenses-data"
import { useCurrency } from "@/lib/use-currency"

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/
const MOBILE_MONTHS = 12

/** "۱۴۰۵/۰۶/۲۶" — the expense's local day in the store's time zone. */
function shortDate(utc: string, timeZone: string): string {
  const local = utcToLocal(utc, timeZone)
  return local ? formatJalali(local.iso, "yyyy/MM/dd") : utc
}

const chipClass = "inline-flex h-6 items-center rounded-md bg-surface-2 px-2 text-xs whitespace-nowrap text-text-2"

const filterBtn =
  "flex cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"

/**
 * هزینه‌ها (design 11). Desktop: toolbar, the filtered list with a period
 * footer, and an aside with the per-category breakdown and the category
 * list. Mobile: month + category filters, a summary card, expense cards and
 * a bottom «ثبت هزینه». Filters live in the URL (?category=, ?from=&to=, ?q=).
 */
export function ExpensesPage() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()

  const [now] = React.useState(() => new Date())
  const today = dateToISO(now)
  const defaultRange = React.useMemo(() => jalaliMonthRange(now), [now])

  const categoryParam = Number(params.get("category"))
  const categoryId = Number.isInteger(categoryParam) && categoryParam > 0 ? categoryParam : null
  const from = params.get("from")
  const to = params.get("to")
  const range: IsoRange = from && to && ISO_DAY.test(from) && ISO_DAY.test(to) && from <= to ? { from, to } : defaultRange
  const q = params.get("q") ?? ""

  const setParams = React.useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(window.location.search)
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      const qs = next.toString()
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
    },
    [router, pathname]
  )
  const setRange = (r: IsoRange) =>
    setParams(r.from === defaultRange.from && r.to === defaultRange.to ? { from: null, to: null } : { from: r.from, to: r.to })

  const [search, setSearch] = React.useState(q)
  React.useEffect(() => {
    if (search === q) return
    const t = window.setTimeout(() => setParams({ q: search || null }), 250)
    return () => window.clearTimeout(t)
  }, [search, q, setParams])

  const data = useExpensesData({ categoryId, range })
  const { categories, list, breakdown } = data

  const [formOpen, setFormOpen] = React.useState(false)
  const [newCategoryOpen, setNewCategoryOpen] = React.useState(false)
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const allCategories = categories.status === "ready" ? categories.all : []
  const activeCategories = allCategories.filter((c) => c.is_active === 1)
  const filterCategory = categoryId != null ? (allCategories.find((c) => c.id === categoryId) ?? null) : null

  const onSaved = (e: Expense) => {
    setFormOpen(false)
    setToast(E.toastSaved(formatMoney(e.amount), e.category_name))
    data.refreshList()
  }
  const onCategoryCreated = (c: ExpenseCategory) => {
    data.addCategory(c)
    setToast(E.toastCategory(c.name))
  }

  const query = norm(q)
  // Search is client-side (the API has none) and on mobile there's no search box.
  const rows =
    list.status === "ready" ? list.rows.filter((r) => mobile || !query || norm(r.description ?? "").includes(query)) : []
  const filtersActive =
    (!mobile && !!q) || categoryId != null || range.from !== defaultRange.from || range.to !== defaultRange.to
  const clearFilters = () => {
    setSearch("")
    router.replace(pathname, { scroll: false })
  }

  const failed = categories.status === "error" || list.status === "error" || breakdown.status === "error"
  const loading = categories.status === "loading" || list.status === "loading" || breakdown.status === "loading"
  const firstRun = list.status === "ready" && list.rows.length === 0 && !filtersActive
  const month = wholeMonthLabel(range)
  const canAdd = categories.status === "ready"

  const dialogs = (
    <>
      <ExpenseDialog
        open={formOpen}
        mobile={mobile}
        today={today}
        categories={activeCategories}
        initialCategoryId={categoryId}
        onClose={() => setFormOpen(false)}
        onSaved={onSaved}
        onCategoryCreated={data.addCategory}
        refreshCategories={data.refreshCategories}
      />
      <NewCategoryDialog
        open={newCategoryOpen}
        mobile={mobile}
        onClose={() => setNewCategoryOpen(false)}
        onCreated={(c) => {
          onCategoryCreated(c)
          setNewCategoryOpen(false)
        }}
      />
      {toast && <Toast title={toast} onClose={closeToast} closeLabel={E.close} />}
    </>
  )

  const categoryMenu = (trigger: React.ReactNode) => (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-80 w-60 overflow-y-auto">
        <DropdownMenuRadioGroup value={categoryId == null ? "" : String(categoryId)} onValueChange={(v) => setParams({ category: v || null })}>
          <DropdownMenuRadioItem value="">{mobile ? E.categoryAllMobile : E.categoryAll}</DropdownMenuRadioItem>
          {allCategories.map((c) => (
            <DropdownMenuRadioItem key={c.id} value={String(c.id)}>
              {c.name}
              {c.is_active !== 1 && <span className="text-xs text-text-3">{E.inactive}</span>}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )

  // ---------------------------------------------------------------- mobile
  if (mobile) {
    const months = Array.from({ length: MOBILE_MONTHS }, (_, i) => jalaliMonthRange(subMonths(now, i)))
    const rangeKey = `${range.from}_${range.to}`
    const filters = (
      <div className="flex gap-2">
        <DropdownMenu dir="rtl">
          <DropdownMenuTrigger asChild>
            <button type="button" className={cn(filterBtn, "h-11 min-w-0 gap-2 tabular-nums")}>
              <CalendarDays className="size-4 shrink-0 text-text-3" aria-hidden />
              <span className="truncate font-semibold">{month ?? rangeLabel(range)}</span>
              <ChevronDown className="size-3.5 shrink-0 text-text-3" aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="max-h-80 w-52 overflow-y-auto">
            <DropdownMenuLabel className="text-xs text-text-3">{E.monthMenuLabel}</DropdownMenuLabel>
            <DropdownMenuRadioGroup
              value={rangeKey}
              onValueChange={(v) => {
                const [f, t] = v.split("_")
                setRange({ from: f, to: t })
              }}
            >
              {months.map((m) => (
                <DropdownMenuRadioItem key={m.from} value={`${m.from}_${m.to}`}>
                  {wholeMonthLabel(m)}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
        {categoryMenu(
          <button type="button" className={cn(filterBtn, "h-11 min-w-0 gap-2")}>
            <span className="truncate font-semibold">{filterCategory?.name ?? E.categoryAllMobile}</span>
            <ChevronDown className="size-3.5 shrink-0 text-text-3" aria-hidden />
          </button>
        )}
      </div>
    )

    let content: React.ReactNode
    if (failed)
      content = <ErrorBlock title={E.errorTitleMobile} body={E.errorBody} retry={E.retry} onRetry={data.reload} mobile />
    else if (loading) content = <LoadingBlock mobile label={E.loadingAria} />
    else if (firstRun)
      content = (
        <StateShell
          icon={Wallet}
          mobile
          title={E.emptyTitle}
          body={E.emptyBodyMobile}
          action={
            <Btn variant="primary" size="lg" className="mt-1.5" onClick={() => setFormOpen(true)}>
              <Plus className="size-[18px]" />
              {E.add}
            </Btn>
          }
        />
      )
    else
      content = (
        <>
          {breakdown.status === "ready" && (
            <MobileSummary
              rows={breakdown.rows}
              label={month ? E.mobileTotal(month) : E.mobileTotalRange}
              scoped={categoryId != null}
            />
          )}
          {rows.length === 0 ? (
            <StateShell
              icon={SearchX}
              mobile
              title={E.noMatchFiltered}
              action={
                <Btn size="sm" className="mt-1" onClick={clearFilters}>
                  {E.clearFilters}
                </Btn>
              }
            />
          ) : (
            <ul className="flex flex-col gap-2" aria-label={E.listAria}>
              {rows.map((r) => (
                <li key={r.id} className={cn(cardClass, "flex items-center justify-between gap-2 px-3.5 py-3")}>
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate text-sm font-bold">{r.description || r.category_name}</span>
                    <span className="truncate text-xs text-text-3 tabular-nums">
                      {shortDate(r.expense_date, data.timeZone)} · {r.category_name}
                    </span>
                  </span>
                  <Money value={r.amount} className="shrink-0 text-sm font-bold" />
                </li>
              ))}
            </ul>
          )}
        </>
      )

    return (
      <div className="flex flex-col gap-3 pb-24">
        {filters}
        {content}
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
          <Btn variant="primary" size="lg" className="w-full" disabled={!canAdd} onClick={() => setFormOpen(true)}>
            <Plus className="size-[18px]" />
            {E.add}
          </Btn>
        </div>
        {dialogs}
      </div>
    )
  }

  // ---------------------------------------------------------------- desktop
  const toolbar = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="relative flex w-[240px] items-center">
          <Search className="pointer-events-none absolute start-3 size-4 text-text-3" aria-hidden />
          <input
            type="search"
            aria-label={E.searchAria}
            placeholder={E.search}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-10 w-full rounded-lg border border-border-strong bg-card ps-9 pe-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30"
          />
        </div>
        {categoryMenu(
          <button type="button" className={cn(filterBtn, "h-10")}>
            <span className="text-text-3">{E.categoryPrefix}</span>
            <span className="max-w-[180px] truncate font-bold">{filterCategory?.name ?? E.categoryAll}</span>
            <ChevronDown className="size-3.5 text-text-3" aria-hidden />
          </button>
        )}
        <DateRangePopover value={range} onApply={setRange} />
      </div>
      <Btn variant="primary" disabled={!canAdd} onClick={() => setFormOpen(true)}>
        <Plus className="size-4" />
        {E.add}
      </Btn>
    </div>
  )

  let body: React.ReactNode
  if (failed) body = <ErrorBlock title={E.errorTitle} body={E.errorBody} retry={E.retry} onRetry={data.reload} mobile={false} />
  else if (loading) body = <LoadingBlock mobile={false} label={E.loadingAria} />
  else if (firstRun)
    body = (
      <StateShell
        icon={Wallet}
        mobile={false}
        title={E.emptyTitle}
        body={E.emptyBody}
        action={
          <Btn variant="primary" className="mt-1.5" onClick={() => setFormOpen(true)}>
            <Plus className="size-4" />
            {E.emptyCta}
          </Btn>
        }
      />
    )
  else {
    const total = rows.reduce((s, r) => s + r.amount, 0)
    const listCard = (
      <section aria-label={E.listAria} className={cn(cardClass, "min-w-0 grow overflow-hidden")}>
        {rows.length === 0 ? (
          <div className="flex flex-col items-center gap-2.5 px-6 py-16 text-center">
            <SearchX className="size-7 text-text-3" aria-hidden />
            <div className="text-[15px] font-bold text-heading">{q ? E.noMatch(q) : E.noMatchFiltered}</div>
            <Btn size="sm" className="mt-1" onClick={clearFilters}>
              {E.clearFilters}
            </Btn>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0 text-[13.5px]">
              <thead>
                <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                  <th scope="col">{E.colDate}</th>
                  <th scope="col">{E.colCategory}</th>
                  <th scope="col" className="w-full">
                    {E.colDescription}
                  </th>
                  <th scope="col" className="text-end!">
                    {E.colAmount}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.id}
                    className="hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4"
                  >
                    <td className="whitespace-nowrap text-text-3 tabular-nums">{shortDate(r.expense_date, data.timeZone)}</td>
                    <td>
                      <span className={chipClass}>{r.category_name}</span>
                    </td>
                    <td className={cn(!r.description && "text-text-3")}>{r.description || E.noDescription}</td>
                    <td className="text-end font-bold">
                      <Money value={r.amount} />
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-bold [&>td]:h-[52px] [&>td]:bg-surface-2 [&>td]:px-4">
                  <td colSpan={3}>{month ? E.footerMonth(month, rows.length) : E.footerRange(rows.length)}</td>
                  <td className="text-end">
                    <Money value={total} />
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </section>
    )
    body = (
      <div className="flex items-start gap-6">
        {listCard}
        <aside className="flex w-[360px] shrink-0 flex-col gap-5">
          {breakdown.status === "ready" && (
            <BreakdownCard
              rows={breakdown.rows}
              highlight={filterCategory?.name ?? null}
              scoped={categoryId != null || !!q}
            />
          )}
          <CategoryCard categories={activeCategories} onNew={() => setNewCategoryOpen(true)} />
        </aside>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {toolbar}
      {body}
      {dialogs}
    </div>
  )
}
