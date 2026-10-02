"use client"

import * as React from "react"
import Link from "next/link"
import { Ban, ChevronDown, CircleAlert, Info, Lock } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Btn, IntInput } from "@/components/record-sale/primitives"
import {
  ApiError,
  createProduct,
  setMadeToOrder,
  updateProductPrices,
  type Product,
} from "@/lib/api"
import { categoryLabel } from "@/lib/categories"
import { formatMoney } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { P } from "./copy"
import { DrawerShell, FieldError, SaveError, Switch, textInputClass } from "./drawer-shell"
import { CATEGORY_CODES, costState } from "./figures"

function errorOf(error: unknown): { message: string; code: string } {
  if (error instanceof ApiError) {
    return {
      message: error.message,
      code: error.status === 0 ? "NET_TIMEOUT" : `PRODUCTS_${error.status}`,
    }
  }
  return { message: String(error), code: "UNKNOWN" }
}

function Field({ label, htmlFor, children }: { label: React.ReactNode; htmlFor?: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      {htmlFor ? (
        <label htmlFor={htmlFor} className="text-[13px] font-semibold">
          {label}
        </label>
      ) : (
        <span className="text-[13px] font-semibold">{label}</span>
      )}
      {children}
    </div>
  )
}

function CategorySelect({
  value,
  onChange,
  mobile,
  error,
}: {
  value: string
  onChange: (v: string) => void
  mobile: boolean
  error?: boolean
}) {
  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <button
          id="pf-category"
          type="button"
          className={cn(textInputClass(mobile, error), "flex cursor-pointer items-center justify-between")}
        >
          <span className={value ? "" : "text-text-3"}>{value ? categoryLabel(value) : P.pickCategory}</span>
          <ChevronDown className="size-3.5 text-text-3" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-(--radix-dropdown-menu-trigger-width)">
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {CATEGORY_CODES.map((c) => (
            <DropdownMenuRadioItem key={c} value={c}>
              {categoryLabel(c)}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Add product (empty form) and edit product (prices + made-to-order) in one drawer. */
export function ProductDrawer({
  open,
  product,
  mobile,
  onClose,
  onSaved,
  onDeactivate,
}: {
  open: boolean
  /** null = add mode. */
  product: Product | null
  mobile: boolean
  onClose: () => void
  /** `close` is false for the made-to-order switch, which saves on its own. */
  onSaved: (p: Product, toast: string, close?: boolean) => void
  onDeactivate: (p: Product) => void
}) {
  const editing = product != null
  const [name, setName] = React.useState("")
  const [category, setCategory] = React.useState("")
  const [retail, setRetail] = React.useState(0)
  const [wholesale, setWholesale] = React.useState(0)
  const [madeToOrder, setMto] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [mtoBusy, setMtoBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const [mtoError, setMtoError] = React.useState<string | null>(null)
  const [touched, setTouched] = React.useState(false)

  // Re-seed the form whenever the drawer opens (or switches product).
  const seedKey = open ? `${product?.id ?? "new"}` : ""
  const [seeded, setSeeded] = React.useState("")
  if (seedKey && seeded !== seedKey) {
    setSeeded(seedKey)
    setName(product?.name ?? "")
    setCategory(product?.category ?? "")
    setRetail(product?.retail_price ?? 0)
    setWholesale(product?.wholesale_price ?? 0)
    setMto(!!product?.made_to_order)
    setError(null)
    setMtoError(null)
    setTouched(false)
  } else if (!seedKey && seeded) {
    setSeeded("")
  }

  const nameError = touched && !editing && !name.trim()
  const categoryError = touched && !editing && !category

  const save = async () => {
    setTouched(true)
    setError(null)
    if (!editing && (!name.trim() || !category)) return
    setBusy(true)
    try {
      if (!editing) {
        const created = await createProduct({
          name: name.trim(),
          category,
          retail_price: retail,
          wholesale_price: wholesale,
          made_to_order: madeToOrder,
        })
        onSaved(created, P.toastProductAdded(created.name))
        return
      }
      // Send only what changed; the API leaves omitted prices untouched.
      const changes: { retail_price?: number; wholesale_price?: number } = {}
      if (retail !== product.retail_price) changes.retail_price = retail
      if (wholesale !== product.wholesale_price) changes.wholesale_price = wholesale
      if (Object.keys(changes).length === 0) {
        onClose()
        return
      }
      const updated = await updateProductPrices(product.id, changes)
      onSaved(updated, P.toastSaved)
    } catch (e) {
      setError(errorOf(e))
    } finally {
      setBusy(false)
    }
  }

  /** Its own call: the backend refuses "on" without a recipe (422 made_to_order). */
  const toggleMto = async (next: boolean) => {
    if (!product) {
      setMto(next)
      return
    }
    setMtoError(null)
    setMtoBusy(true)
    try {
      const updated = await setMadeToOrder(product.id, next)
      setMto(!!updated.made_to_order)
      onSaved(updated, P.toastSaved, false)
    } catch (e) {
      setMto(!!product.made_to_order)
      if (e instanceof ApiError && e.status === 422 && e.field === "made_to_order") {
        setMtoError(P.madeToOrderNoRecipe)
      } else {
        setError(errorOf(e))
      }
    } finally {
      setMtoBusy(false)
    }
  }

  const cost = product ? costState({ ...product, made_to_order: madeToOrder ? 1 : 0 }) : null
  const anyBusy = busy || mtoBusy

  return (
    <DrawerShell
      open={open}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      title={editing ? P.editProductTitle : P.addProductTitle}
      busy={anyBusy}
      footer={
        <>
          <Btn variant="primary" disabled={anyBusy} aria-busy={busy || undefined} onClick={save}>
            {busy && <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />}
            {P.save}
          </Btn>
          <Btn disabled={anyBusy} onClick={onClose}>
            {P.cancel}
          </Btn>
          <span className="grow" />
          {editing && product.is_active === 1 && (
            <Btn
              size="sm"
              className="border-loss-border text-loss hover:bg-loss-soft"
              disabled={anyBusy}
              onClick={() => onDeactivate(product)}
            >
              <Ban className="size-3.5" />
              {P.deactivate}
            </Btn>
          )}
        </>
      }
    >
      {error && <SaveError {...error} />}

      {editing ? (
        <div className="flex flex-col gap-1 rounded-[10px] bg-surface-2 px-3 py-2.5 text-[13px]">
          <span className="font-bold">{product.name}</span>
          <span className="text-text-3">
            {P.fieldCategory}: {categoryLabel(product.category)}
          </span>
          <span className="flex items-center gap-1 text-xs text-text-3">
            <Info className="size-3" aria-hidden />
            {P.readOnlyNote}
          </span>
        </div>
      ) : (
        <>
          <Field label={P.fieldName} htmlFor="pf-name">
            <input
              id="pf-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={textInputClass(mobile, nameError)}
              aria-invalid={nameError || undefined}
            />
            {nameError && <FieldError>{P.nameRequired}</FieldError>}
          </Field>
          <Field label={P.fieldCategory}>
            <CategorySelect value={category} onChange={setCategory} mobile={mobile} error={categoryError} />
            {categoryError && <FieldError>{P.categoryRequired}</FieldError>}
          </Field>
        </>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label={P.fieldRetail} htmlFor="pf-retail">
          <IntInput id="pf-retail" value={retail} onValue={setRetail} suffix={P.toman} className={mobile ? "h-11" : undefined} />
        </Field>
        <Field label={P.fieldWholesale} htmlFor="pf-wholesale">
          <IntInput
            id="pf-wholesale"
            value={wholesale}
            onValue={setWholesale}
            suffix={P.toman}
            tone={wholesale > retail ? "warn" : null}
            className={mobile ? "h-11" : undefined}
          />
        </Field>
      </div>
      {wholesale > retail && (
        <span role="status" className="-mt-2 text-xs text-warn">
          {P.wholesaleAboveRetail}
        </span>
      )}

      {editing && cost && (
        <div
          className={cn(
            "flex flex-col gap-1.5 rounded-[10px] p-3",
            cost.kind === "missing" ? "bg-loss-soft" : "bg-surface-2"
          )}
        >
          <span className="flex items-center gap-1.5 text-[13px] font-semibold">
            <Lock className="size-3.5" aria-hidden />
            {P.fieldCost}
          </span>
          <span className={cn("font-bold tabular-nums", cost.kind === "missing" && "text-loss")}>
            {cost.kind === "known" ? formatMoney(cost.cost) : cost.kind === "fromRecipe" ? P.fromRecipe : P.noCost}
          </span>
          {cost.kind === "missing" && (
            <span className="flex items-start gap-1.5 text-xs font-medium text-loss">
              <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              {P.costMissingErr}
            </span>
          )}
          <span className="text-xs text-text-3">{cost.kind === "fromRecipe" ? P.costFromRecipeHelp : P.costHelp}</span>
          {cost.kind === "missing" && (
            <span className="flex gap-3 text-xs font-bold">
              <Link href="/purchases" className="text-heading hover:text-primary">
                {P.bannerPurchase}
              </Link>
              <Link href="/production" className="text-heading hover:text-primary">
                {P.bannerProduction}
              </Link>
            </span>
          )}
        </div>
      )}

      {editing && (
        <Field label={P.fieldStock}>
          <div className="flex h-10 items-center rounded-lg border border-border bg-surface-2 px-3 text-sm text-text-3 tabular-nums">
            {P.stockUnits(product.current_stock)}
          </div>
          <span className="text-xs text-text-3">{P.stockHelp}</span>
        </Field>
      )}

      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2.5">
          <Switch
            id="pf-mto"
            checked={madeToOrder}
            onChange={toggleMto}
            disabled={mtoBusy || (editing && product.is_active !== 1)}
            labelledBy="pf-mto-label"
          />
          <span id="pf-mto-label" className="text-[13px] font-semibold">
            {P.fieldMadeToOrder}
          </span>
          {mtoBusy && (
            <span className="size-3.5 animate-spin rounded-full border-2 border-text-3/40 border-t-text-3" aria-hidden />
          )}
        </div>
        <span className="text-xs text-text-3">
          {editing ? P.madeToOrderHelp : madeToOrder ? P.madeToOrderCreateHelp : P.madeToOrderHelp}
        </span>
        {mtoError && <FieldError>{mtoError}</FieldError>}
      </div>

    </DrawerShell>
  )
}
