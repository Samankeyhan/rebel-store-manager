"use client"

import * as React from "react"
import { ChevronDown } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { CategoryTree } from "@/lib/api"
import { cn } from "@/lib/utils"
import { P } from "./copy"
import { textInputClass } from "./drawer-shell"

const NONE = "none"

/** «فندک › فندک بزرگ» for the node with this id, or null if it isn't in the tree. */
function pathOf(tree: CategoryTree[], id: number): string | null {
  for (const t of tree) {
    if (t.id === id) return t.name
    const child = t.children.find((c) => c.id === id)
    if (child) return `${t.name} › ${child.name}`
  }
  return null
}

/**
 * Picks the one category an item goes in. One dropdown, grouped: a top-level
 * category with active subcategories is a heading, not an option, with its
 * subcategories indented under it — the same leaf rule the API enforces
 * (db/categories.py validate_assignable). Inactive categories are hidden.
 */
export function CategoryPicker({
  id,
  tree,
  value,
  onChange,
  mobile,
  error,
  allowNone,
  excludeId,
  labelledBy,
}: {
  id?: string
  tree: CategoryTree[]
  value: number | null
  onChange: (id: number | null) => void
  mobile: boolean
  error?: boolean
  /** Offer «بدون دسته» (materials: a category is optional). */
  allowNone?: boolean
  /** Leave this category out (a move's source). Its parent stays a heading. */
  excludeId?: number
  labelledBy?: string
}) {
  const active = tree
    .filter((t) => t.is_active === 1)
    .map((t) => ({ ...t, children: t.children.filter((c) => c.is_active === 1) }))
  const offered = (id: number) => id !== excludeId
  const label = value == null ? null : pathOf(tree, value)
  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <button
          id={id}
          type="button"
          aria-labelledby={labelledBy}
          className={cn(textInputClass(mobile, error), "flex cursor-pointer items-center justify-between")}
        >
          <span className={label ? "" : "text-text-3"}>{label ?? (allowNone && value == null ? P.noCategory : P.pickCategory)}</span>
          <ChevronDown className="size-3.5 text-text-3" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-80 w-(--radix-dropdown-menu-trigger-width) overflow-y-auto">
        <DropdownMenuRadioGroup
          value={value == null ? (allowNone ? NONE : "") : String(value)}
          onValueChange={(v) => onChange(v === NONE ? null : Number(v))}
        >
          {allowNone && <DropdownMenuRadioItem value={NONE}>{P.noCategory}</DropdownMenuRadioItem>}
          {active.map((t) =>
            t.children.length === 0 ? (
              offered(t.id) && (
                <DropdownMenuRadioItem key={t.id} value={String(t.id)}>
                  {t.name}
                </DropdownMenuRadioItem>
              )
            ) : (
              t.children.some((c) => offered(c.id)) && (
              <React.Fragment key={t.id}>
                <DropdownMenuLabel className="text-xs text-text-3">{t.name}</DropdownMenuLabel>
                {t.children.filter((c) => offered(c.id)).map((c) => (
                  <DropdownMenuRadioItem key={c.id} value={String(c.id)} className="ps-6">
                    {c.name}
                  </DropdownMenuRadioItem>
                ))}
              </React.Fragment>
              )
            )
          )}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Filter value: "" (all), "none" (no category), or a category id as a string. */
export type CategoryFilterValue = string

/**
 * Toolbar filter. Unlike the picker, a parent is selectable here and means
 * "it and its subcategories". Inactive categories stay listed so items still
 * in them can be found.
 */
export function CategoryFilter({
  tree,
  value,
  onChange,
  withNone,
}: {
  tree: CategoryTree[]
  value: CategoryFilterValue
  onChange: (v: CategoryFilterValue) => void
  withNone?: boolean
}) {
  const label =
    value === "" ? P.categoryAll : value === NONE ? P.noCategory : (pathOf(tree, Number(value)) ?? P.categoryAll)
  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-10 cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
        >
          <span className="text-text-3">{P.categoryLabel}</span>
          <span className="font-bold">{label}</span>
          <ChevronDown className="size-3.5 text-text-3" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-80 w-52 overflow-y-auto">
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          <DropdownMenuRadioItem value="">{P.categoryAll}</DropdownMenuRadioItem>
          {withNone && <DropdownMenuRadioItem value={NONE}>{P.noCategory}</DropdownMenuRadioItem>}
          {tree.map((t) => (
            <React.Fragment key={t.id}>
              <DropdownMenuRadioItem value={String(t.id)} className={cn(t.is_active !== 1 && "text-text-3")}>
                {t.name}
              </DropdownMenuRadioItem>
              {t.children.map((c) => (
                <DropdownMenuRadioItem
                  key={c.id}
                  value={String(c.id)}
                  className={cn("ps-6", c.is_active !== 1 && "text-text-3")}
                >
                  {c.name}
                </DropdownMenuRadioItem>
              ))}
            </React.Fragment>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
