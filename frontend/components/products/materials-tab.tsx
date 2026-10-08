"use client"

import * as React from "react"
import { Ban, MoreHorizontal, Pencil, RotateCcw } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import type { Material } from "@/lib/api"
import { categoryPath } from "@/lib/category-path"
import { formatQuantity } from "@/lib/persian-numbers"
import { Money } from "@/components/common/money"
import { cn } from "@/lib/utils"
import { ActiveBadge, Chip, TypeBadge } from "./badges"
import { P } from "./copy"
import { inventoryValue, unitLabel } from "./figures"

const pillClass = "inline-flex h-[22px] items-center rounded-md px-2 text-[11.5px] font-semibold whitespace-nowrap tabular-nums"

/** Stock, plus «کم‌موجودی» when the API flags it (is_low_stock: db/materials.py owns the rule). */
function StockCell({ m }: { m: Material }) {
  if (m.type === "SERVICE" || m.current_stock == null) return <Chip>{P.noStock}</Chip>
  if (m.current_stock <= 0) return <span className={cn(pillClass, "bg-loss-soft text-loss")}>{P.outOfStock}</span>
  const qty = `${formatQuantity(m.current_stock)} ${unitLabel(m.unit)}`
  if (m.is_low_stock !== 1) return <span className={cn(pillClass, "bg-surface-2 text-text-2")}>{qty}</span>
  return (
    <span className="inline-flex items-center gap-1">
      <span className={cn(pillClass, "bg-warn-soft text-warn")}>{qty}</span>
      <span className={cn(pillClass, "bg-warn-soft text-warn")}>{P.lowStock}</span>
    </span>
  )
}

export function MaterialsTab({
  rows,
  mobile,
  onEdit,
  onDeactivate,
  onReactivate,
}: {
  rows: Material[]
  mobile: boolean
  /** Opens the drawer, where the minimum stock is set. */
  onEdit: (m: Material) => void
  onDeactivate: (m: Material) => void
  onReactivate: (m: Material) => void
}) {
  if (mobile) {
    return (
      <div className="flex flex-col gap-3">
        {rows.map((m) => {
          const active = m.is_active === 1
          return (
            <div key={m.id} className={cn(cardClass, "flex flex-col gap-2 px-3.5 py-3", !active && "opacity-55")}>
              <span className="flex items-center justify-between gap-2">
                <span className="font-bold">{m.name}</span>
                <span className="flex items-center gap-1">
                  <StockCell m={m} />
                  <DropdownMenu dir="rtl">
                      <DropdownMenuTrigger asChild>
                        <Btn variant="ghost" className="size-11 px-0" aria-label={P.rowActions}>
                          <MoreHorizontal className="size-4" />
                        </Btn>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => onEdit(m)}>
                          <Pencil />
                          {P.edit}
                        </DropdownMenuItem>
                        {active ? (
                          <DropdownMenuItem onSelect={() => onDeactivate(m)} className="text-loss">
                            <Ban />
                            {P.deactivate}
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem onSelect={() => onReactivate(m)}>
                            <RotateCcw />
                            {P.reactivate}
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                </span>
              </span>
              <span className="flex items-center justify-between gap-2 text-xs">
                <span className="flex items-center gap-1.5">
                  <TypeBadge type={m.type} />
                  {m.category_id != null && <Chip>{categoryPath(m)}</Chip>}
                  <span className="text-text-3">{unitLabel(m.unit)}</span>
                </span>
                <Money value={m.unit_cost} className="text-text-2" />
              </span>
              <span className="flex justify-end">
                <ActiveBadge active={active} />
              </span>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <section className={cn(cardClass, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col" className="w-full">
                  {P.colMatName}
                </th>
                <th scope="col">{P.colMatCategory}</th>
                <th scope="col">{P.colType}</th>
                <th scope="col">{P.colUnit}</th>
                <th scope="col">{P.colStock}</th>
                <th scope="col">{P.colUnitCost}</th>
                <th scope="col">{P.colValue}</th>
                <th scope="col">{P.colStatus}</th>
                <th scope="col" className="w-24">
                  <span className="sr-only">{P.colActions}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => {
                const active = m.is_active === 1
                const value = inventoryValue(m)
                return (
                  <tr
                    key={m.id}
                    className={cn(
                      "hover:[&>td]:bg-surface-2 [&>td]:h-[52px] [&>td]:border-b [&>td]:border-border [&>td]:px-4 [&>td]:whitespace-nowrap last:[&>td]:border-b-0",
                      !active && "opacity-55"
                    )}
                  >
                    <td className="font-bold">{m.name}</td>
                    <td>{m.category_id != null ? <Chip>{categoryPath(m)}</Chip> : <span className="text-text-3">—</span>}</td>
                    <td>
                      <TypeBadge type={m.type} />
                    </td>
                    <td>{unitLabel(m.unit)}</td>
                    <td>
                      <StockCell m={m} />
                    </td>
                    <td>
                      <Money value={m.unit_cost} />
                    </td>
                    <td className="text-text-2">{value == null ? "—" : <Money value={value} />}</td>
                    <td>
                      <ActiveBadge active={active} />
                    </td>
                    <td>
                      <span className="flex gap-1">
                      <Btn variant="ghost" size="sm" className="size-8 px-0" aria-label={P.edit} onClick={() => onEdit(m)}>
                        <Pencil className="size-4" />
                      </Btn>
                      {active ? (
                        <Btn
                          variant="ghost"
                          size="sm"
                          className="size-8 px-0"
                          aria-label={P.deactivate}
                          onClick={() => onDeactivate(m)}
                        >
                          <Ban className="size-4" />
                        </Btn>
                      ) : (
                        <Btn
                          variant="ghost"
                          size="sm"
                          className="size-8 px-0"
                          aria-label={P.reactivate}
                          onClick={() => onReactivate(m)}
                        >
                          <RotateCcw className="size-4" />
                        </Btn>
                      )}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
      <p className="text-xs text-text-3">{P.materialsFootnote}</p>
    </div>
  )
}
