"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Check, ChevronDown, Loader2, Plus, Search, SearchX, ShoppingCart } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { Segment } from "@/components/common/segment"
import { Toast } from "@/components/common/toast"
import { DateRangePopover } from "@/components/orders/list/date-range-popover"
import { DrawerShell } from "@/components/products/drawer-shell"
import { norm } from "@/components/products/figures"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import { dateToISO, formatJalali, jalaliMonthRange, utcToLocal, wholeMonthLabel, type IsoRange } from "@/lib/jalali"
import { matchesPayFilter, PAY_FILTERS, parsePayFilter } from "@/lib/payables"
import { itemsSummary, parseTypeFilter, TYPE_FILTERS } from "@/lib/purchase-lines"
import { Money } from "@/components/common/money"
import { cn } from "@/lib/utils"
import { PAY_STATUS_LABELS, U } from "./copy"
import { PayStatusTag } from "./pay-status-tag"
import { PurchaseForm, type PurchaseFormHandle } from "./purchase-form"
import { PurchaseSheet } from "./purchase-sheet"
import { TypeTag } from "./type-tag"
import { usePurchasesData, type PurchaseRow, type RefreshedItem, type TypeFilter } from "./use-purchases-data"
import { useCurrency } from "@/lib/use-currency"

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/
const TYPE_LABELS: Record<TypeFilter, string> = {
  all: U.typeAll,
  material: U.typeMaterials,
  service: U.typeServices,
  product: U.typeProducts,
}

/**
 * خرید (design 07). Desktop: the purchase history (one row per supplier
 * invoice) with filters, the entry form in a left drawer. Mobile: the form
 * first, then «خریدهای اخیر». Filters live in the URL (?type=material|service|
 * product, ?supplier=, ?from=&to=, ?q=, ?pay=).
 */
export function PurchasesPage() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()

  const [now] = React.useState(() => new Date())
  const today = dateToISO(now)
  const defaultRange = React.useMemo(() => jalaliMonthRange(now), [now])

  const type: TypeFilter = parseTypeFilter(params.get("type"))
  const supplierParam = Number(params.get("supplier"))
  const supplierId = Number.isInteger(supplierParam) && supplierParam > 0 ? supplierParam : null
  const from = params.get("from")
  const to = params.get("to")
  const range: IsoRange = from && to && ISO_DAY.test(from) && ISO_DAY.test(to) && from <= to ? { from, to } : defaultRange
  const q = params.get("q") ?? ""
  // the payment status filter is client-side, like the search (the API gives each row its status)
  const pay = parsePayFilter(params.get("pay"))

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

  const [search, setSearch] = React.useState(q)
  React.useEffect(() => {
    if (search === q) return
    const t = window.setTimeout(() => setParams({ q: search || null }), 250)
    return () => window.clearTimeout(t)
  }, [search, q, setParams])

  // Mobile shows the newest purchases overall, so no type/supplier/date filter there.
  const data = usePurchasesData(
    mobile ? { type: "all", supplierId: null, range: null } : { type, supplierId, range }
  )
  const { catalog, list } = data

  const [drawerOpen, setDrawerOpen] = React.useState(false)
  const [formBusy, setFormBusy] = React.useState(false)
  const formRef = React.useRef<PurchaseFormHandle>(null)
  const [openRow, setOpenRow] = React.useState<PurchaseRow | null>(null)
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const onSaved = (items: RefreshedItem[], message: string) => {
    data.replaceItems(items)
    data.refreshList()
    setToast(message)
    setDrawerOpen(false)
  }

  const query = norm(q)
  const rows =
    list.status === "ready"
      ? list.rows.filter(
          (r) =>
            (!query || r.itemNames.some((n) => norm(n).includes(query)) || norm(r.invoiceNumber ?? "").includes(query)) &&
            matchesPayFilter(r.paymentStatus, pay)
        )
      : []
  const filtersActive = !!q || pay != null || type !== "all" || supplierId != null || range.from !== defaultRange.from || range.to !== defaultRange.to
  const clearFilters = () => {
    setSearch("")
    router.replace(pathname, { scroll: false })
  }

  const form =
    catalog.status === "ready" ? (
      <PurchaseForm
        ref={formRef}
        materials={catalog.materials}
        products={catalog.products}
        suppliers={catalog.suppliers}
        today={today}
        mobile={mobile}
        onBusyChange={setFormBusy}
        onSaved={onSaved}
        refreshSuppliers={data.refreshSuppliers}
      />
    ) : null

  const sheet = (
    <PurchaseSheet row={openRow} timeZone={data.timeZone} mobile={mobile} onClose={() => setOpenRow(null)} />
  )
  const toastNode = toast && <Toast title={toast} onClose={closeToast} closeLabel={U.close} />

  const failed = catalog.status === "error" || list.status === "error"
  const loading = catalog.status === "loading" || list.status === "loading"

  // ---------------------------------------------------------------- mobile
  if (mobile) {
    let content: React.ReactNode
    if (failed)
      content = <ErrorBlock title={U.errorTitleMobile} body={U.errorBody} retry={U.retry} onRetry={data.reload} mobile />
    else if (loading) content = <LoadingBlock mobile label={U.loadingAria} />
    else
      content = (
        <>
          <section className={cn(cardClass, "p-3.5")}>{form}</section>
          {list.status === "ready" && list.rows.length === 0 ? (
            <StateShell icon={ShoppingCart} mobile title={U.emptyTitle} body={U.emptyBodyMobile} />
          ) : (
            <>
              <h3 className="mt-1 text-sm font-bold text-heading">{U.recent}</h3>
              {rows.slice(0, 5).map((r) => (
                <button
                  key={r.key}
                  type="button"
                  onClick={() => setOpenRow(r)}
                  className={cn(cardClass, "flex items-center justify-between gap-3 px-3.5 py-3 text-start outline-none focus-visible:ring-3 focus-visible:ring-ring/30")}
                >
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate font-bold">{itemsSummary(r.itemNames, U.moreItems)}</span>
                    <span className="truncate text-xs text-text-3 tabular-nums">
                      {U.recentMeta(shortDate(r.date, data.timeZone), U.lineCount(r.lines.length), r.supplierName)}
                    </span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-1">
                    <Money value={r.total} className="font-bold" />
                    {r.paymentStatus !== "PAID" && <PayStatusTag status={r.paymentStatus} />}
                  </span>
                </button>
              ))}
            </>
          )}
          <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
            <Btn
              variant="primary"
              size="lg"
              className="w-full"
              disabled={formBusy}
              aria-busy={formBusy || undefined}
              onClick={() => formRef.current?.submit()}
            >
              {formBusy ? <Loader2 className="size-[18px] animate-spin" /> : <Check className="size-[18px]" />}
              {U.submit}
            </Btn>
          </div>
        </>
      )
    return (
      <div className="flex flex-col gap-3 pb-24">
        {content}
        {sheet}
        {toastNode}
      </div>
    )
  }

  // ---------------------------------------------------------------- desktop
  const suppliers = catalog.status === "ready" ? catalog.suppliers : []
  const supplierName = supplierId != null ? (suppliers.find((s) => s.id === supplierId)?.name ?? U.supplierAll) : U.supplierAll

  const toolbar = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="relative flex w-[240px] items-center">
          <Search className="pointer-events-none absolute start-3 size-4 text-text-3" aria-hidden />
          <input
            type="search"
            aria-label={U.searchAria}
            placeholder={U.search}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-10 w-full rounded-lg border border-border-strong bg-card ps-9 pe-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30"
          />
        </div>
        <Segment<TypeFilter>
          value={type}
          options={TYPE_FILTERS.map((t) => [t, TYPE_LABELS[t]] as const)}
          onChange={(t) => setParams({ type: t === "all" ? null : t })}
          label={U.typeFilterLabel}
          className="[&_button]:h-[32px]"
        />
        <DropdownMenu dir="rtl">
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex h-10 cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
            >
              <span className="text-text-3">{U.supplierPrefix}</span>
              <span className="font-bold">{supplierName}</span>
              <ChevronDown className="size-3.5 text-text-3" aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="max-h-80 w-60 overflow-y-auto">
            <DropdownMenuRadioGroup
              value={supplierId == null ? "" : String(supplierId)}
              onValueChange={(v) => setParams({ supplier: v || null })}
            >
              <DropdownMenuRadioItem value="">{U.supplierAll}</DropdownMenuRadioItem>
              {[...suppliers]
                .sort((a, b) => a.name.localeCompare(b.name, "fa"))
                .map((s) => (
                  <DropdownMenuRadioItem key={s.id} value={String(s.id)}>
                    {s.name}
                  </DropdownMenuRadioItem>
                ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu dir="rtl">
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex h-10 cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
            >
              <span className="text-text-3">{U.payFilterPrefix}</span>
              <span className="font-bold">{pay ? PAY_STATUS_LABELS[pay.toUpperCase() as keyof typeof PAY_STATUS_LABELS] : U.payFilterAll}</span>
              <ChevronDown className="size-3.5 text-text-3" aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-52">
            <DropdownMenuRadioGroup value={pay ?? ""} onValueChange={(v) => setParams({ pay: v || null })}>
              <DropdownMenuRadioItem value="">{U.payFilterAll}</DropdownMenuRadioItem>
              {PAY_FILTERS.map((f) => (
                <DropdownMenuRadioItem key={f} value={f}>
                  {PAY_STATUS_LABELS[f.toUpperCase() as keyof typeof PAY_STATUS_LABELS]}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
        <DateRangePopover
          value={range}
          onApply={(r) =>
            setParams(
              r.from === defaultRange.from && r.to === defaultRange.to ? { from: null, to: null } : { from: r.from, to: r.to }
            )
          }
        />
      </div>
      <Btn variant="primary" disabled={catalog.status !== "ready"} onClick={() => setDrawerOpen(true)}>
        <Plus className="size-4" />
        {U.add}
      </Btn>
    </div>
  )

  let body: React.ReactNode
  if (failed) body = <ErrorBlock title={U.errorTitle} body={U.errorBody} retry={U.retry} onRetry={data.reload} mobile={false} />
  else if (loading) body = <LoadingBlock mobile={false} label={U.loadingAria} />
  else if (list.status === "ready" && list.rows.length === 0 && !filtersActive)
    body = (
      <StateShell
        icon={ShoppingCart}
        mobile={false}
        title={U.emptyTitle}
        body={U.emptyBody}
        action={
          <Btn variant="primary" className="mt-1.5" onClick={() => setDrawerOpen(true)}>
            <Plus className="size-4" />
            {U.emptyCta}
          </Btn>
        }
      />
    )
  else if (rows.length === 0)
    body = (
      <StateShell
        icon={SearchX}
        mobile={false}
        title={q ? U.noMatch(q) : U.noMatchFiltered}
        action={
          <Btn size="sm" className="mt-1" onClick={clearFilters}>
            {U.clearFilters}
          </Btn>
        }
      />
    )
  else {
    const month = wholeMonthLabel(range)
    const total = rows.reduce((s, r) => s + r.total, 0)
    body = (
      <section className={cn(cardClass, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col">{U.colDate}</th>
                <th scope="col" className="w-full">
                  {U.colItem}
                </th>
                <th scope="col">{U.colType}</th>
                <th scope="col">{U.colSupplier}</th>
                <th scope="col" className="text-end!">
                  {U.colTotal}
                </th>
                <th scope="col">{U.colPayStatus}</th>
                <th scope="col" className="text-end!">
                  {U.colOutstanding}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.key}
                  tabIndex={0}
                  onClick={() => setOpenRow(r)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      setOpenRow(r)
                    }
                  }}
                  className="cursor-pointer outline-none hover:[&>td]:bg-surface-2 focus-visible:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
                >
                  <td className="text-text-3 tabular-nums">{shortDate(r.date, data.timeZone)}</td>
                  <td>
                    <span className="font-bold">{itemsSummary(r.itemNames, U.moreItems)}</span>
                    <span className="ms-2 text-xs text-text-3 tabular-nums">
                      {r.invoiceNumber && <span dir="ltr">{r.invoiceNumber}</span>}
                      {r.lines.length > 1 && <> · {U.lineCount(r.lines.length)}</>}
                    </span>
                  </td>
                  <td>
                    <span className="flex items-center gap-1">
                      {r.types.map((t) => (
                        <TypeTag key={t} type={t} />
                      ))}
                    </span>
                  </td>
                  <td>{r.supplierName ?? U.noSupplier}</td>
                  <td className="text-end font-bold">
                    <Money value={r.total} />
                  </td>
                  <td>
                    <PayStatusTag status={r.paymentStatus} />
                  </td>
                  <td className="text-end">{r.outstanding > 0 ? <Money value={r.outstanding} /> : <span className="text-text-3">—</span>}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-bold [&>td]:h-[52px] [&>td]:bg-surface-2 [&>td]:px-4">
                <td colSpan={4}>{month ? U.footerMonth(month, rows.length) : U.footerRange(rows.length)}</td>
                <td className="text-end">
                  <Money value={total} />
                </td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {toolbar}
      {body}
      <DrawerShell
        open={drawerOpen}
        onOpenChange={(o) => !o && setDrawerOpen(false)}
        mobile={false}
        title={U.formTitle}
        busy={formBusy}
        footer={
          <>
            <Btn variant="primary" disabled={formBusy} aria-busy={formBusy || undefined} onClick={() => formRef.current?.submit()}>
              {formBusy && <Loader2 className="size-4 animate-spin" />}
              {U.submit}
            </Btn>
            <Btn disabled={formBusy} onClick={() => setDrawerOpen(false)}>
              {U.cancel}
            </Btn>
          </>
        }
      >
        {form}
      </DrawerShell>
      {sheet}
      {toastNode}
    </div>
  )
}

/** "۱۴۰۵/۰۶/۲۹" — the purchase's local day in the store's time zone. */
function shortDate(utc: string, timeZone: string): string {
  const local = utcToLocal(utc, timeZone)
  return local ? formatJalali(local.iso, "yyyy/MM/dd") : utc
}
