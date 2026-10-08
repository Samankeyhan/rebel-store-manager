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
import { Money } from "@/components/common/money"
import { ApiError, createMaterial, updateMaterial, type CategoryTree, type Material } from "@/lib/api"
import { categoryPath } from "@/lib/category-path"
import { minStockChanged, parseMinStock } from "@/lib/min-stock"
import { formatQuantity, parseDecimal } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { TypeBadge } from "./badges"
import { P } from "./copy"
import { CategoryPicker } from "./category-picker"
import { DrawerShell, FieldError, SaveError, textInputClass } from "./drawer-shell"
import { UNITS, unitLabel } from "./figures"

const readOnlyBox = "flex h-10 items-center rounded-lg border border-border bg-surface-2 px-3 text-sm text-text-2 tabular-nums"

function ReadOnly({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <span className="text-[13px] font-semibold">{label}</span>
      <div className={readOnlyBox}>{children}</div>
    </div>
  )
}

/**
 * Add a material, or (with `material`) edit one. The API edits only
 * min_stock (PATCH /materials/{id}); everything else is shown read-only.
 */
export function MaterialDrawer({
  open,
  material,
  tree,
  mobile,
  onClose,
  onSaved,
}: {
  open: boolean
  /** null = add; a material = edit its minimum stock. */
  material: Material | null
  /** The MATERIAL category tree; a material's category is optional. */
  tree: CategoryTree[]
  mobile: boolean
  onClose: () => void
  onSaved: (m: Material, toast: string) => void
}) {
  const editing = material != null
  const [name, setName] = React.useState("")
  const [type, setType] = React.useState<"STOCK" | "SERVICE">("STOCK")
  const [unit, setUnit] = React.useState<string>(UNITS[0])
  /** Integer Rial; null while MoneyInput holds text that gives no exact amount — blocks save. */
  const [unitCost, setUnitCost] = React.useState<number | null>(0)
  const [stockText, setStockText] = React.useState("")
  const [minText, setMinText] = React.useState("")
  /** Only a minimum the owner typed is sent, so an untouched field never rewrites a saved value. */
  const [minDirty, setMinDirty] = React.useState(false)
  const [minRefused, setMinRefused] = React.useState(false)
  const [category, setCategory] = React.useState<number | null>(null)
  const [categoryError, setCategoryError] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const [touched, setTouched] = React.useState(false)

  const [openedFor, setOpenedFor] = React.useState<number | "add" | null>(null)
  const target = open ? (material?.id ?? "add") : null
  if (target !== openedFor) {
    setOpenedFor(target)
    if (target !== null) {
      setName("")
      setType("STOCK")
      setUnit(UNITS[0])
      setUnitCost(0)
      setStockText("")
      setMinText(material?.min_stock != null ? formatQuantity(material.min_stock) : "")
      setMinDirty(false)
      setMinRefused(false)
      setCategory(null)
      setCategoryError(false)
      setError(null)
      setTouched(false)
    }
  }

  const isStock = editing ? material.type === "STOCK" : type === "STOCK"
  const shownUnit = editing ? unitLabel(material.unit) : unit
  const stock = stockText.trim() === "" ? 0 : parseDecimal(stockText)
  const minParse = parseMinStock(minText)
  const nameError = !editing && touched && !name.trim()
  const stockError = !editing && touched && type === "STOCK" && (stock == null || stock < 0)
  const minError = isStock && ((touched && !minParse.ok) || minRefused)

  const fail = (e: unknown) => {
    if (e instanceof ApiError && e.status === 422 && e.field === "min_stock") {
      setMinRefused(true)
      return
    }
    if (e instanceof ApiError && e.status === 422 && e.field === "category_id") {
      setCategoryError(true)
      return
    }
    setError(
      e instanceof ApiError
        ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `MATERIALS_${e.status}` }
        : { message: String(e), code: "UNKNOWN" }
    )
  }

  const saveEdit = async (m: Material) => {
    if (m.type !== "STOCK" || !minDirty) {
      onClose()
      return
    }
    if (!minParse.ok) return
    if (!minStockChanged(m.min_stock, minParse)) {
      onClose()
      return
    }
    setBusy(true)
    try {
      const updated = await updateMaterial(m.id, { min_stock: minParse.value })
      onSaved(updated, P.toastSaved)
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  const saveNew = async () => {
    if (
      !name.trim() ||
      (type === "STOCK" && (stock == null || stock < 0 || !minParse.ok)) ||
      unitCost === null
    )
      return
    setBusy(true)
    try {
      const created = await createMaterial({
        name: name.trim(),
        type,
        unit,
        unit_cost: unitCost,
        // SERVICE materials hold no stock; the API rejects any initial_stock or min_stock.
        initial_stock: type === "SERVICE" ? null : stock,
        min_stock: type === "SERVICE" || !minParse.ok ? null : minParse.value,
        category_id: category,
      })
      onSaved(created, P.toastMaterialAdded(created.name))
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  const save = () => {
    setTouched(true)
    setError(null)
    return editing ? saveEdit(material) : saveNew()
  }

  const minField = isStock && (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="mf-min" className="text-[13px] font-semibold">
        {P.fieldMinStock}
      </label>
      <div className="relative flex items-center">
        <input
          id="mf-min"
          inputMode="decimal"
          value={minText}
          onChange={(e) => {
            setMinText(e.target.value)
            setMinDirty(true)
            setMinRefused(false)
          }}
          onBlur={() => {
            const p = parseMinStock(minText)
            if (p.ok && p.value != null) setMinText(formatQuantity(p.value))
          }}
          placeholder={P.minStockPlaceholder}
          className={cn(textInputClass(mobile, minError), "pe-16 tabular-nums")}
          aria-invalid={minError || undefined}
          aria-describedby="mf-min-help"
        />
        <span className="pointer-events-none absolute end-3 text-xs text-text-3">{shownUnit}</span>
      </div>
      {minError && <FieldError>{P.invalidQuantity}</FieldError>}
      <span id="mf-min-help" className="text-xs text-text-3">
        {P.minStockHelp}
      </span>
    </div>
  )

  return (
    <DrawerShell
      open={open}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={editing ? P.editMaterialTitle : P.addMaterialTitle}
      busy={busy}
      footer={
        editing && !isStock ? (
          <Btn onClick={onClose}>{P.close}</Btn>
        ) : (
          <>
            <Btn variant="primary" disabled={busy} aria-busy={busy || undefined} onClick={save}>
              {busy && <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />}
              {P.save}
            </Btn>
            <Btn disabled={busy} onClick={onClose}>
              {P.cancel}
            </Btn>
          </>
        )
      }
    >
      {error && <SaveError {...error} />}

      {editing ? (
        <>
          <ReadOnly label={P.fieldMatName}>
            <span className="truncate font-semibold text-heading">{material.name}</span>
          </ReadOnly>
          <div className="grid grid-cols-2 gap-3">
            <ReadOnly label={P.fieldCategory}>
              <span className="truncate">{categoryPath(material) || P.noCategory}</span>
            </ReadOnly>
            <div className="flex min-w-0 flex-col gap-1.5">
              <span className="text-[13px] font-semibold">{P.fieldType}</span>
              <div className="flex h-10 items-center">
                <TypeBadge type={material.type} />
              </div>
            </div>
            <ReadOnly label={P.fieldUnit}>{shownUnit}</ReadOnly>
            <ReadOnly label={P.fieldUnitCost}>
              <Money value={material.unit_cost} />
            </ReadOnly>
          </div>
          {isStock && material.current_stock != null && (
            <div className="flex flex-col gap-1.5">
              <ReadOnly label={P.fieldStock}>
                {formatQuantity(material.current_stock)} {shownUnit}
              </ReadOnly>
              <span className="text-xs text-text-3">{P.matStockHelp}</span>
            </div>
          )}
          <span className="text-xs text-text-3">{isStock ? P.matReadOnlyNote : P.serviceNoMinStock}</span>
          {minField}
        </>
      ) : (
        <>
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

          {minField}
        </>
      )}
    </DrawerShell>
  )
}
