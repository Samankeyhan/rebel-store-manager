"use client"

import * as React from "react"
import { Building2, Pencil, Plus, Search, SearchX } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { Toast } from "@/components/common/toast"
import { norm } from "@/components/products/figures"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import type { Supplier } from "@/lib/api"
import { formatJalali, utcToLocal } from "@/lib/jalali"
import { formatNumber, toPersianDigits } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { S } from "./copy"
import { SupplierDrawer } from "./supplier-drawer"
import { useSuppliersData, type SupplierStats } from "./use-suppliers-data"

type DrawerState = { open: boolean; supplier: Supplier | null; key: number }

/** A phone number as typed, with Persian digits, kept left-to-right. */
function Phone({ value }: { value: string | null }) {
  if (!value) return <span className="text-text-3">—</span>
  return (
    <span dir="ltr" className="tabular-nums">
      {toPersianDigits(value)}
    </span>
  )
}

/**
 * تأمین‌کنندگان (design 14): the supplier directory. Desktop: toolbar +
 * table, add/edit in a left drawer. Mobile: search, cards, a sticky add
 * button, add/edit in a bottom sheet.
 */
export function SuppliersPage() {
  const mobile = useIsMobile()
  const { list, stats, timeZone, reload, upsert } = useSuppliersData()
  const [search, setSearch] = React.useState("")
  const [drawer, setDrawer] = React.useState<DrawerState>({ open: false, supplier: null, key: 0 })
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const openDrawer = (supplier: Supplier | null) => setDrawer((d) => ({ open: true, supplier, key: d.key + 1 }))
  const closeDrawer = () => setDrawer((d) => ({ ...d, open: false }))

  const q = norm(search)
  const suppliers = list.status === "ready" ? list.suppliers : []
  const rows = q
    ? suppliers.filter((s) => [s.name, s.phone, s.email, s.website, s.notes].some((v) => v && norm(v).includes(q)))
    : suppliers

  const statsOf = (id: number): SupplierStats | null => (stats ? (stats.get(id) ?? { count: 0, last: null }) : null)
  const day = (utc: string | null) => {
    if (!utc) return null
    const local = utcToLocal(utc, timeZone)
    return local ? formatJalali(local.iso, "yyyy/MM/dd") : toPersianDigits(utc)
  }

  const searchBox = (
    <div className={cn("relative flex items-center", mobile ? "w-full" : "w-[280px]")}>
      <Search className="pointer-events-none absolute start-3 size-4 text-text-3" aria-hidden />
      <input
        type="search"
        aria-label={S.searchAria}
        placeholder={S.search}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className={cn(
          "w-full rounded-lg border border-border-strong bg-card ps-9 pe-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
          mobile ? "h-11" : "h-10"
        )}
      />
    </div>
  )

  let body: React.ReactNode
  if (list.status === "error")
    body = (
      <ErrorBlock title={mobile ? S.errorTitleMobile : S.errorTitle} body={S.errorBody} retry={S.retry} onRetry={reload} mobile={mobile} />
    )
  else if (list.status === "loading") body = <LoadingBlock mobile={mobile} label={S.loadingAria} />
  else if (suppliers.length === 0)
    body = (
      <StateShell
        icon={Building2}
        mobile={mobile}
        title={S.emptyTitle}
        body={mobile ? S.emptyBodyMobile : S.emptyBody}
        action={
          <Btn variant="primary" size={mobile ? "lg" : "md"} className="mt-1.5" onClick={() => openDrawer(null)}>
            <Plus className="size-4" />
            {S.emptyCta}
          </Btn>
        }
      />
    )
  else if (rows.length === 0)
    body = (
      <StateShell
        icon={SearchX}
        mobile={mobile}
        title={S.noMatch(search.trim())}
        action={
          <Btn size="sm" className="mt-1" onClick={() => setSearch("")}>
            {S.clearSearch}
          </Btn>
        }
      />
    )
  else if (mobile)
    body = (
      <div className="flex flex-col gap-3">
        {rows.map((s) => {
          const st = statsOf(s.id)
          const last = day(st?.last ?? null)
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => openDrawer(s)}
              className={cn(cardClass, "flex flex-col gap-1.5 px-3.5 py-3 text-start outline-none focus-visible:ring-3 focus-visible:ring-ring/30")}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="truncate text-sm font-bold">{s.name}</span>
                {st && st.count > 0 && (
                  <span className="shrink-0 text-sm font-bold tabular-nums">{S.purchaseCount(formatNumber(st.count))}</span>
                )}
              </span>
              {(s.phone || s.email) && (
                <span className="truncate text-xs text-text-2">
                  {s.phone ? <Phone value={s.phone} /> : <span dir="ltr">{s.email}</span>}
                </span>
              )}
              {st && <span className="text-xs text-text-3 tabular-nums">{last ? S.lastPurchase(last) : S.noPurchases}</span>}
            </button>
          )
        })}
      </div>
    )
  else
    body = (
      <section className={cn(cardClass, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col">{S.colName}</th>
                <th scope="col">{S.colPhone}</th>
                <th scope="col">{S.colEmail}</th>
                <th scope="col" className="w-full">
                  {S.colWebsite}
                </th>
                <th scope="col" className="text-end!">
                  {S.colPurchases}
                </th>
                <th scope="col">{S.colLast}</th>
                <th scope="col" className="w-14">
                  <span className="sr-only">{S.edit}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => {
                const st = statsOf(s.id)
                return (
                  <tr
                    key={s.id}
                    onClick={() => openDrawer(s)}
                    className="cursor-pointer hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
                  >
                    <td className="max-w-[260px] truncate font-bold">{s.name}</td>
                    <td>
                      <Phone value={s.phone} />
                    </td>
                    <td className="max-w-[220px] truncate">
                      {s.email ? <span dir="ltr">{s.email}</span> : <span className="text-text-3">—</span>}
                    </td>
                    <td className="max-w-[260px] truncate text-text-2" dir="auto">
                      {s.website || <span className="text-text-3">—</span>}
                    </td>
                    <td className="text-end tabular-nums">{st ? formatNumber(st.count) : "—"}</td>
                    <td className="text-text-3 tabular-nums">{(st && day(st.last)) || "—"}</td>
                    <td>
                      <Btn
                        variant="ghost"
                        size="sm"
                        className="size-8 px-0"
                        aria-label={`${S.edit} — ${s.name}`}
                        onClick={(e) => {
                          e.stopPropagation()
                          openDrawer(s)
                        }}
                      >
                        <Pencil className="size-4" />
                      </Btn>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    )

  const drawerNode = (
    <SupplierDrawer
      key={drawer.key}
      open={drawer.open}
      supplier={drawer.supplier}
      mobile={mobile}
      onClose={closeDrawer}
      onSaved={(s, created) => {
        upsert(s)
        closeDrawer()
        setToast(created ? S.toastCreated(s.name) : S.toastUpdated(s.name))
      }}
      onGone={reload}
    />
  )
  const toastNode = toast && <Toast title={toast} onClose={closeToast} closeLabel={S.close} />

  if (mobile)
    return (
      <div className="flex flex-col gap-3 pb-24">
        {searchBox}
        {body}
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
          <Btn variant="primary" size="lg" className="w-full" onClick={() => openDrawer(null)}>
            <Plus className="size-[18px]" />
            {S.add}
          </Btn>
        </div>
        {drawerNode}
        {toastNode}
      </div>
    )

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        {searchBox}
        <Btn variant="primary" onClick={() => openDrawer(null)}>
          <Plus className="size-4" />
          {S.add}
        </Btn>
      </div>
      {body}
      {drawerNode}
      {toastNode}
    </div>
  )
}
