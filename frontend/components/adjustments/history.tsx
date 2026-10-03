"use client"

import * as React from "react"
import { ChevronDown, Plus, SearchX, SlidersHorizontal } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { Segment } from "@/components/common/segment"
import { DateRangePopover } from "@/components/orders/list/date-range-popover"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import type { Adjustment } from "@/lib/api"
import { formatJalali, formatJalaliDateTime, utcToLocal, type IsoRange } from "@/lib/jalali"
import { formatQuantity } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { A } from "./copy"
import { rowKind, rowValue } from "./figures"
import { KindBadge } from "./kind-badge"

export type KindFilter = "all" | "waste" | "correction"

/**
 * The «کالا» filter: "" (all), "type:PRODUCT" / "type:MATERIAL" (sent to the
 * API as item_type), or "PRODUCT:<id>" / "MATERIAL:<id>" (item_type on the
 * server, the id on the client — the API has no item_id filter).
 */
export type ItemFilter = string

type ListState = { status: "loading" } | { status: "error" } | { status: "ready"; rows: Adjustment[] }

// Sign and digits isolated left-to-right (LRI … PDI) so the sign stays in
// front of the number inside RTL running text.
const signed = (q: number, unit: string) => `\u2066${q > 0 ? "+" : ""}${formatQuantity(q)}\u2069 ${unit}`

function shortDate(utc: string, timeZone: string): string {
  const local = utcToLocal(utc, timeZone)
  return local ? formatJalali(local.iso, "yyyy/MM/dd") : utc
}

/** «تاریخچه تعدیل‌ها» (desktop card with filters). */
export function HistoryCard({
  list,
  rows,
  unitOf,
  timeZone,
  kind,
  onKind,
  item,
  onItem,
  itemOptions,
  range,
  onRange,
  filtersActive,
  onClear,
  onRetry,
  onEmptyCta,
}: {
  list: ListState
  rows: Adjustment[]
  unitOf: (row: Adjustment) => string
  timeZone: string
  kind: KindFilter
  onKind: (k: KindFilter) => void
  item: ItemFilter
  onItem: (v: ItemFilter) => void
  itemOptions: { products: [number, string][]; materials: [number, string][] }
  range: IsoRange
  onRange: (r: IsoRange) => void
  filtersActive: boolean
  onClear: () => void
  onRetry: () => void
  onEmptyCta: () => void
}) {
  if (list.status === "error")
    return <ErrorBlock title={A.errorTitle} body={A.errorBody} retry={A.retry} onRetry={onRetry} mobile={false} />
  if (list.status === "loading") return <LoadingBlock mobile={false} label={A.loadingAria} />
  if (list.rows.length === 0 && !filtersActive)
    return (
      <StateShell
        icon={SlidersHorizontal}
        mobile={false}
        title={A.emptyTitle}
        body={A.emptyBody}
        action={
          <Btn variant="primary" className="mt-1.5" onClick={onEmptyCta}>
            <Plus className="size-4" />
            {A.emptyCta}
          </Btn>
        }
      />
    )

  const itemLabel = (() => {
    if (item === "type:PRODUCT") return A.itemAllProducts
    if (item === "type:MATERIAL") return A.itemAllMaterials
    const [type, id] = item.split(":")
    const pool = type === "PRODUCT" ? itemOptions.products : type === "MATERIAL" ? itemOptions.materials : []
    return pool.find(([i]) => String(i) === id)?.[1] ?? A.itemAll
  })()

  return (
    <section aria-labelledby="adj-history-title" className={cn(cardClass, "overflow-hidden")}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3.5">
        <h2 id="adj-history-title" className="text-base font-bold text-heading">
          {A.historyTitle}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <Segment<KindFilter>
            value={kind}
            options={[
              ["all", A.filterAll],
              ["waste", A.filterWaste],
              ["correction", A.filterCorrection],
            ]}
            onChange={onKind}
            label={A.filterKindLabel}
            className="[&_button]:h-[28px]"
          />
          <DropdownMenu dir="rtl">
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
              >
                <span className="text-text-3">{A.itemPrefix}</span>
                <span className="max-w-[180px] truncate font-bold">{itemLabel}</span>
                <ChevronDown className="size-3.5 text-text-3" aria-hidden />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="max-h-80 w-64 overflow-y-auto">
              <DropdownMenuRadioGroup value={item} onValueChange={onItem}>
                <DropdownMenuRadioItem value="">{A.itemAll}</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="type:PRODUCT">{A.itemAllProducts}</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="type:MATERIAL">{A.itemAllMaterials}</DropdownMenuRadioItem>
                {itemOptions.products.length > 0 && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuLabel className="text-xs text-text-3">{A.groupProducts}</DropdownMenuLabel>
                    {itemOptions.products.map(([id, name]) => (
                      <DropdownMenuRadioItem key={`p${id}`} value={`PRODUCT:${id}`}>
                        {name}
                      </DropdownMenuRadioItem>
                    ))}
                  </>
                )}
                {itemOptions.materials.length > 0 && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuLabel className="text-xs text-text-3">{A.groupMaterials}</DropdownMenuLabel>
                    {itemOptions.materials.map(([id, name]) => (
                      <DropdownMenuRadioItem key={`m${id}`} value={`MATERIAL:${id}`}>
                        {name}
                      </DropdownMenuRadioItem>
                    ))}
                  </>
                )}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
          <DateRangePopover value={range} onApply={onRange} />
        </div>
      </div>
      {rows.length === 0 ? (
        <div className="flex flex-col items-center gap-2.5 px-6 py-16 text-center">
          <SearchX className="size-7 text-text-3" aria-hidden />
          <div className="text-[15px] font-bold text-heading">{A.noMatch}</div>
          <Btn size="sm" className="mt-1" onClick={onClear}>
            {A.clearFilters}
          </Btn>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col">{A.colDate}</th>
                <th scope="col">{A.colItem}</th>
                <th scope="col">{A.colKind}</th>
                <th scope="col" className="text-end!">
                  {A.colQty}
                </th>
                <th scope="col" className="text-end!">
                  {A.colValue}
                </th>
                <th scope="col">{A.colPnl}</th>
                <th scope="col" className="w-full">
                  {A.colReason}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const k = rowKind(r)
                const value = rowValue(r)
                return (
                  <tr
                    key={r.id}
                    className="[&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap"
                  >
                    <td className="text-text-3 tabular-nums">{formatJalaliDateTime(r.movement_date, timeZone)}</td>
                    <td>
                      <span className="flex items-center gap-2">
                        <b>{r.item_name ?? "—"}</b>
                        <span className="rounded-[4px] bg-surface-2 px-1.5 text-[11px] font-semibold text-text-3">
                          {r.item_type === "PRODUCT" ? A.tagProduct : A.tagMaterial}
                        </span>
                      </span>
                    </td>
                    <td>
                      <KindBadge kind={k} />
                    </td>
                    <td className={cn("text-end font-semibold tabular-nums", r.quantity_change < 0 ? "text-loss" : "text-profit")}>
                      {signed(r.quantity_change, unitOf(r))}
                    </td>
                    <td className={cn("text-end tabular-nums", value != null && value < 0 && "text-loss")}>
                      {value == null ? "—" : A.signedValue(value)}
                    </td>
                    <td>
                      {k === "waste" ? (
                        <span className="text-xs font-bold text-loss">{A.pnlWaste}</span>
                      ) : (
                        <span className="text-xs text-text-3">{A.pnlNone}</span>
                      )}
                    </td>
                    <td className="max-w-[320px] truncate text-text-2">{r.notes || "—"}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="px-5 py-3 text-xs leading-[1.8] text-text-3">
        {A.footnote} {A.footnoteValue}
      </p>
    </section>
  )
}

/** Mobile «اخیر»: the newest five, unfiltered. */
export function RecentList({
  list,
  unitOf,
  timeZone,
  onRetry,
}: {
  list: ListState
  unitOf: (row: Adjustment) => string
  timeZone: string
  onRetry: () => void
}) {
  if (list.status === "error")
    return <ErrorBlock title={A.errorTitleMobile} body={A.errorBody} retry={A.retry} onRetry={onRetry} mobile />
  if (list.status === "loading") return <LoadingBlock mobile label={A.loadingAria} />
  if (list.rows.length === 0)
    return <StateShell icon={SlidersHorizontal} mobile title={A.emptyTitle} body={A.emptyBodyMobile} />
  return (
    <>
      <h3 className="mt-1 text-sm font-bold text-heading">{A.recent}</h3>
      {list.rows.slice(0, 5).map((r) => {
        const k = rowKind(r)
        const value = rowValue(r)
        const kindText = k === "waste" ? A.badgeWaste : A.filterCorrection
        return (
          <div key={r.id} className={cn(cardClass, "flex items-center justify-between gap-3 px-3.5 py-3")}>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="truncate font-bold">{r.item_name ?? "—"}</span>
              <span className="truncate text-xs text-text-3 tabular-nums">
                {A.recentMeta(shortDate(r.movement_date, timeZone), kindText, signed(r.quantity_change, unitOf(r)))}
                {k !== "waste" && ` · ${A.recentNoPnl}`}
              </span>
              {r.notes && <span className="truncate text-xs text-text-3">{r.notes}</span>}
            </span>
            <span className={cn("shrink-0 font-bold tabular-nums", value != null && value < 0 && "text-loss")}>
              {value == null ? "—" : A.signedValue(value)}
            </span>
          </div>
        )
      })}
    </>
  )
}
