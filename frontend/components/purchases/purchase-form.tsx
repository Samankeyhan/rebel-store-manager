"use client"

import * as React from "react"
import { DateField } from "@/components/common/date-field"
import { ItemPicker, type PickerItem } from "@/components/common/item-picker"
import { Segment } from "@/components/common/segment"
import { SaveError } from "@/components/products/drawer-shell"
import { unitLabel } from "@/components/products/figures"
import { Help, InlineMessage, IntInput, Label } from "@/components/record-sale/primitives"
import {
  ApiError,
  createMaterialPurchase,
  createProductPurchase,
  getMaterial,
  getProduct,
  type Material,
  type Product,
  type Supplier,
} from "@/lib/api"
import { formatQuantity, parseDecimal } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { U } from "./copy"
import { PurchasePreview, type PreviewItem } from "./purchase-preview"
import type { PurchaseKind } from "./use-purchases-data"

const NO_SUPPLIER = 0

export type PurchaseFormHandle = { submit: () => void }

/**
 * The purchase entry form (design 07 drawer / mobile card): type, item,
 * supplier, quantity, total paid, date, note, and the live cost preview.
 * Used inside the desktop drawer and inline on mobile; the parent owns the
 * submit button and calls `ref.submit()`.
 */
export const PurchaseForm = React.forwardRef<
  PurchaseFormHandle,
  {
    materials: Material[]
    products: Product[]
    suppliers: Supplier[]
    today: string
    mobile: boolean
    onBusyChange: (busy: boolean) => void
    /** After a successful save, with the item re-read from the server. */
    onSaved: (kind: PurchaseKind, item: Material | Product, toast: string) => void
    refreshSuppliers: () => Promise<void>
  }
>(function PurchaseForm({ materials, products, suppliers, today, mobile, onBusyChange, onSaved, refreshSuppliers }, ref) {
  const [kind, setKind] = React.useState<PurchaseKind>("material")
  const [itemId, setItemId] = React.useState<number | null>(null)
  const [supplierId, setSupplierId] = React.useState(NO_SUPPLIER)
  const [qtyText, setQtyText] = React.useState("")
  const [productQty, setProductQty] = React.useState(0)
  const [total, setTotal] = React.useState(0)
  const [date, setDate] = React.useState(today)
  const [note, setNote] = React.useState("")
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const [supplierGone, setSupplierGone] = React.useState(false)
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>({})

  // Only what the backend accepts: active STOCK materials, active products.
  const buyableMaterials = materials.filter((m) => m.is_active === 1 && m.type === "STOCK")
  const buyableProducts = products.filter((p) => p.is_active === 1)
  const material = kind === "material" ? (buyableMaterials.find((m) => m.id === itemId) ?? null) : null
  const product = kind === "product" ? (buyableProducts.find((p) => p.id === itemId) ?? null) : null

  const qty: number | null = kind === "material" ? parseDecimal(qtyText) : productQty
  const unit = material ? unitLabel(material.unit) : "عدد"

  const itemPill = (stock: number, u: string) => ({
    text: (mobile ? U.stockPillMobile : U.stockPill)(formatQuantity(stock), u),
    tone: "neutral" as const,
  })
  const pickerItems: PickerItem[] =
    kind === "material"
      ? buyableMaterials.map((m) => ({ id: m.id, name: m.name, pill: itemPill(m.current_stock ?? 0, unitLabel(m.unit)) }))
      : buyableProducts.map((p) => ({ id: p.id, name: p.name, pill: itemPill(p.current_stock, "عدد") }))
  const supplierItems: PickerItem[] = [
    { id: NO_SUPPLIER, name: U.noSupplierOption },
    ...[...suppliers].sort((a, b) => a.name.localeCompare(b.name, "fa")).map((s) => ({ id: s.id, name: s.name })),
  ]

  const previewItem: PreviewItem | null = material
    ? { name: material.name, stock: material.current_stock ?? 0, cost: material.unit_cost, unit, kind: "material" }
    : product
      ? { name: product.name, stock: product.current_stock, cost: product.unit_cost, unit, kind: "product" }
      : null

  const itemError = touched && itemId == null ? U.itemRequired : null
  const qtyError = touched && (qty == null || qty <= 0) ? U.qtyRequired : (fieldErrors.quantity_bought ?? null)

  const switchKind = (k: PurchaseKind) => {
    if (k === kind) return
    setKind(k)
    setItemId(null)
    setQtyText("")
    setProductQty(0)
    setFieldErrors({})
  }

  const submit = async () => {
    setTouched(true)
    setError(null)
    setFieldErrors({})
    if (itemId == null || qty == null || qty <= 0 || busy) return
    setBusy(true)
    onBusyChange(true)
    const common = {
      quantity_bought: qty,
      total_paid: total,
      supplier_id: supplierId === NO_SUPPLIER ? null : supplierId,
      // Today: the server stamps the current time. Another day: that day.
      purchase_date: date === today ? null : date,
      notes: note.trim() || null,
    }
    try {
      if (kind === "material") await createMaterialPurchase({ material_id: itemId, ...common })
      else await createProductPurchase({ product_id: itemId, ...common })
      // The response is the purchase row only; the item's new average is re-read.
      let item: Material | Product | null = null
      try {
        item = kind === "material" ? await getMaterial(itemId) : await getProduct(itemId)
      } catch {
        // The purchase is saved either way; the toast just omits the average.
      }
      const name = (material ?? product)?.name ?? ""
      onSaved(kind, item ?? (material ?? product)!, U.toastSaved(name, item?.unit_cost ?? null))
      setQtyText("")
      setProductQty(0)
      setTotal(0)
      setNote("")
      setTouched(false)
      setSupplierGone(false)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404 && /supplier/i.test(e.message)) {
        // The picked supplier was deleted since the list loaded: say so, make
        // them choose again, and refresh the list.
        setSupplierGone(true)
        setSupplierId(NO_SUPPLIER)
        refreshSuppliers().catch(() => {})
      } else if (e instanceof ApiError && e.status === 422 && e.field && ["quantity_bought", "total_paid"].includes(e.field)) {
        setFieldErrors({ [e.field]: e.message })
      } else {
        setError(
          e instanceof ApiError
            ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `PURCHASES_${e.status}` }
            : { message: String(e), code: "UNKNOWN" }
        )
      }
    } finally {
      setBusy(false)
      onBusyChange(false)
    }
  }

  React.useImperativeHandle(ref, () => ({ submit }))

  const inputCls = cn(
    "w-full min-w-0 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
    mobile ? "h-12" : "h-10"
  )

  const qtyField = (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor="pf-qty">{U.fieldQty}</Label>
      {kind === "material" ? (
        <div className="relative flex items-center">
          <input
            id="pf-qty"
            inputMode="decimal"
            value={qtyText}
            onChange={(e) => setQtyText(e.target.value)}
            onBlur={() => {
              const n = parseDecimal(qtyText)
              if (n != null) setQtyText(formatQuantity(n))
            }}
            placeholder={formatQuantity(0)}
            aria-invalid={!!qtyError || undefined}
            className={cn(inputCls, "pe-16 tabular-nums", qtyError && "border-loss ring-3 ring-loss-soft")}
          />
          <span className="pointer-events-none absolute end-3 text-xs text-text-3">{unit}</span>
        </div>
      ) : (
        <IntInput
          id="pf-qty"
          value={productQty}
          onValue={setProductQty}
          suffix={unit}
          tone={qtyError ? "error" : null}
          className={mobile ? "h-12" : undefined}
        />
      )}
      {qtyError && <InlineMessage severity="error">{qtyError}</InlineMessage>}
    </div>
  )

  const totalField = (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor="pf-total">{U.fieldTotal}</Label>
      <IntInput
        id="pf-total"
        value={total}
        onValue={setTotal}
        suffix={U.toman}
        tone={fieldErrors.total_paid ? "error" : touched && total === 0 ? "warn" : null}
        className={mobile ? "h-12" : undefined}
      />
      {fieldErrors.total_paid ? (
        <InlineMessage severity="error">{fieldErrors.total_paid}</InlineMessage>
      ) : (
        touched && total === 0 && itemId != null && <InlineMessage severity="warn">{U.totalZero}</InlineMessage>
      )}
    </div>
  )

  const dateField = (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor="pf-date">{mobile ? U.fieldDateMobile : U.fieldDate}</Label>
      <DateField id="pf-date" value={date} today={today} onChange={setDate} todayLabel={U.today} mobile={mobile} />
    </div>
  )

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-3.5")}>
      {error && <SaveError {...error} />}
      <div className="flex flex-col gap-1.5">
        {!mobile && <Label>{U.fieldType}</Label>}
        <Segment<PurchaseKind>
          value={kind}
          options={[
            ["material", U.segMaterial],
            ["product", U.segProduct],
          ]}
          onChange={switchKind}
          label={U.fieldType}
          mobile={mobile}
          className={mobile ? "grid grid-cols-2" : undefined}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pf-item">{U.fieldItem}</Label>
        <ItemPicker
          id="pf-item"
          items={pickerItems}
          value={itemId}
          onPick={(id) => {
            setItemId(id)
            setError(null)
          }}
          placeholder={U.pickItem}
          searchLabel={U.searchItem}
          emptyText={U.noItems}
          noMatchText={U.noItemMatch}
          mobile={mobile}
          error={!!itemError}
        />
        {itemError && <InlineMessage severity="error">{itemError}</InlineMessage>}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pf-supplier">{U.fieldSupplier}</Label>
        <ItemPicker
          id="pf-supplier"
          items={supplierItems}
          value={supplierId}
          onPick={(id) => {
            setSupplierId(id)
            setSupplierGone(false)
          }}
          placeholder={U.noSupplierOption}
          searchLabel={U.searchSupplier}
          emptyText={U.noSupplierOption}
          noMatchText={U.noSupplierMatch}
          mobile={mobile}
          error={supplierGone}
        />
        {supplierGone ? (
          <InlineMessage severity="error">{U.supplierGone}</InlineMessage>
        ) : (
          suppliers.length === 0 && <Help>{U.noSuppliersYet}</Help>
        )}
      </div>
      {mobile ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            {qtyField}
            {dateField}
          </div>
          {totalField}
        </>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            {qtyField}
            {totalField}
          </div>
          {dateField}
        </>
      )}
      <PurchasePreview item={previewItem} qty={qty} total={total} mobile={mobile} />
      {!mobile && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pf-note" optional>
            {U.fieldNote}
          </Label>
          <input id="pf-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder={U.notePlaceholder} className={inputCls} />
        </div>
      )}
    </div>
  )
})
