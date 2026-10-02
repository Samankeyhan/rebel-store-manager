"use client"

import { Plus } from "lucide-react"
import { Btn, cardClass } from "@/components/record-sale/primitives"
import type { ExpenseCategory } from "@/lib/api"
import { E } from "./copy"

/**
 * «دسته‌ها» (desktop aside): the stored active categories, with «دسته جدید».
 * The design's per-row «ویرایش دسته» and its deactivate note are left out —
 * the API has no rename, deactivate or delete for expense categories.
 */
export function CategoryCard({ categories, onNew }: { categories: ExpenseCategory[]; onNew: () => void }) {
  return (
    <section aria-labelledby="exp-categories" className={cardClass}>
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3.5">
        <h2 id="exp-categories" className="text-base font-bold text-heading">
          {E.categoriesTitle}
        </h2>
        <Btn size="sm" onClick={onNew}>
          <Plus className="size-3.5" />
          {E.newCategory}
        </Btn>
      </div>
      <div className="px-3 py-2">
        {categories.length === 0 ? (
          <p className="px-2 py-2.5 text-[13px] text-text-3">{E.categoriesEmpty}</p>
        ) : (
          <ul>
            {categories.map((c) => (
              <li key={c.id} className="flex h-10 items-center border-b border-border px-2 text-[13.5px] last:border-b-0">
                <span className="truncate">{c.name}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
