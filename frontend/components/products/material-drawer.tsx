"use client"

import * as React from "react"
import { ChevronDown } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Btn, MoneyInput } from "@/components/record-sale/primitives"
import { ApiError, createMaterial, type CategoryTree, type Material } from "@/lib/api"
import { formatQuantity, parseDecimal } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { P } from "./copy"
import { CategoryPicker } from "./category-picker"
import { DrawerShell, FieldError, SaveError, textInputClass } from "./drawer-shell"
import { UNITS } from "./figures"

/** Add material (create only: the API has no material edit endpoint). */
export function MaterialDrawer({
  open,
  tree,
  mobile,
  onClose,
  onSaved,
}: {
  open: boolean
  /** The MATERIAL category tree; a material's category is optional. */
  tree: CategoryTree[]
  mobile: boolean
  onClose: () => void
  onSaved: (m: Material, toast: string) => void
}) {
  const [name, setName] = React.useState("")
  const [type, setType] = React.useState<"STOCK" | "SERVICE">("STOCK")
  const [unit, setUnit] = React.useState<string>(UNITS[0])
  /** Integer Rial; null while MoneyInput holds text that gives no exact amount — blocks save. */
  const [unitCost, setUnitCost] = React.useState<number | null>(0)
  const [stockText, setStockText] = React.useState("")
  const [category, setCategory] = React.useState<number | null>(null)
  const [categoryError, setCategoryError] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const [touched, setTouched] = React.useState(false)

  const [wasOpen, setWasOpen] = React.useState(false)
  if (open && !wasOpen) {
    setWasOpen(true)
    setName("")
    setType("STOCK")
    setUnit(UNITS[0])
    setUnitCost(0)
    setStockText("")
    setCategory(null)
    setCategoryError(false)
    setError(null)
    setTouched(false)
  } else if (!open && wasOpen) {
    setWasOpen(false)
  }

  const stock = stockText.trim() === "" ? 0 : parseDecimal(stockText)
  const nameError = touched && !name.trim()
  const stockError = touched && type === "STOCK" && (stock == null || stock < 0)

  const save = async () => {
    setTouched(true)
    setError(null)
    if (!name.trim() || (type === "STOCK" && (stock == null || stock < 0)) || unitCost === null) return
    setBusy(true)
    try {
      const created = await createMaterial({
        name: name.trim(),
        type,
        unit,
        unit_cost: unitCost,
        // SERVICE materials hold no stock; the API rejects any initial_stock.
        initial_stock: type === "SERVICE" ? null : stock,
        category_id: category,
      })
      onSaved(created, P.toastMaterialAdded(created.name))
    } catch (e) {
      if (e instanceof ApiError && e.status === 422 && e.field === "category_id") {
        setCategoryError(true)
        return
      }
      setError(
        e instanceof ApiError
          ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `MATERIALS_${e.status}` }
          : { message: String(e), code: "UNKNOWN" }
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <DrawerShell
      open={open}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={P.addMaterialTitle}
      busy={busy}
      footer={
        <>
          <Btn variant="primary" disabled={busy} aria-busy={busy || undefined} onClick={save}>
            {busy && <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />}
            {P.save}
          </Btn>
          <Btn disabled={busy} onClick={onClose}>
            {P.cancel}
          </Btn>
        </>
      }
    >
      {error && <SaveError {...error} />}

      <div className="flex flex-col gap-1.5">
        <label htmlFor="mf-name" className="text-[13px] font-semibold">
          {P.fieldMatName}
        </label>
        <input
          id="mf-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={textInputClass(mobile, nameError)}
          aria-invalid={nameError || undefined}
        />
        {nameError && <FieldError>{P.nameRequired}</FieldError>}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="mf-category" className="text-[13px] font-semibold">
          {P.fieldCategory}
        </label>
        <CategoryPicker
          id="mf-category"
          tree={tree}
          value={category}
          onChange={(v) => {
            setCategory(v)
            setCategoryError(false)
          }}
          mobile={mobile}
          error={categoryError}
          allowNone
        />
        {categoryError && <FieldError>{P.categoryUnavailable}</FieldError>}
      </div>

      <div className="flex flex-col gap-1.5">
        <span id="mf-type" className="text-[13px] font-semibold">
          {P.fieldType}
        </span>
        <div
          role="radiogroup"
          aria-labelledby="mf-type"
          className="flex w-full gap-0.5 rounded-[10px] border border-border bg-surface-2 p-[3px]"
        >
          {(
            [
              ["STOCK", P.typeStockSeg],
              ["SERVICE", P.typeServiceSeg],
            ] as const
          ).map(([t, label]) => (
            <button
              key={t}
              type="button"
              role="radio"
              aria-checked={type === t}
              onClick={() => setType(t)}
              className={cn(
                "grow cursor-pointer rounded-[7px] px-2 text-[13px] font-semibold text-text-2 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                mobile ? "h-10" : "h-[34px]",
                type === t && "bg-card text-heading shadow-[0_4px_14px_rgba(18,22,38,.08)]"
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="text-xs text-text-3">{P.typeHelp}</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <span className="text-[13px] font-semibold">{P.fieldUnit}</span>
          <DropdownMenu dir="rtl">
            <DropdownMenuTrigger asChild>
              <button type="button" className={cn(textInputClass(mobile), "flex cursor-pointer items-center justify-between")}>
                {unit}
                <ChevronDown className="size-3.5 text-text-3" aria-hidden />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-(--radix-dropdown-menu-trigger-width)">
              <DropdownMenuRadioGroup value={unit} onValueChange={setUnit}>
                {UNITS.map((u) => (
                  <DropdownMenuRadioItem key={u} value={u}>
                    {u}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <label htmlFor="mf-cost" className="text-[13px] font-semibold">
            {P.fieldUnitCost}
          </label>
          <MoneyInput id="mf-cost" value={unitCost} onValue={(v) => setUnitCost(v ?? null)} className={mobile ? "h-11" : undefined} />
          {unitCost !== null && <span className="text-xs text-text-3">{P.unitCostHelp}</span>}
        </div>
      </div>

      {type === "STOCK" && (
        <div className="flex flex-col gap-1.5">
          <label htmlFor="mf-stock" className="text-[13px] font-semibold">
            {P.fieldInitialStock}
          </label>
          <div className="relative flex items-center">
            <input
              id="mf-stock"
              inputMode="decimal"
              value={stockText}
              onChange={(e) => setStockText(e.target.value)}
              onBlur={() => {
                const n = parseDecimal(stockText)
                if (n != null) setStockText(formatQuantity(n))
              }}
              placeholder={formatQuantity(0)}
              className={cn(textInputClass(mobile, stockError), "pe-16 tabular-nums")}
              aria-invalid={stockError || undefined}
            />
            <span className="pointer-events-none absolute end-3 text-xs text-text-3">{unit}</span>
          </div>
          {stockError ? <FieldError>{P.invalidQuantity}</FieldError> : <span className="text-xs text-text-3">{P.initialStockHelp}</span>}
        </div>
      )}
    </DrawerShell>
  )
}
