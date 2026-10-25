"use client"

import * as React from "react"
import { Plus, Trash2 } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { ItemPicker, type PickerItem } from "@/components/common/item-picker"
import { Money } from "@/components/common/money"
import { Segment } from "@/components/common/segment"
import { SaveError } from "@/components/products/drawer-shell"
import { unitLabel } from "@/components/products/figures"
import { Help, InlineMessage, Label, MoneyInput } from "@/components/record-sale/primitives"
import {
  ApiError,
  createPurchase,
  getMaterial,
  getProduct,
  type Material,
  type Product,
  type Supplier,
  type SupplierPaymentMethod,
} from "@/lib/api"
import { classifyPayablesError, type PaymentMode, purchasePaymentBody, purchasePaymentProblem } from "@/lib/payables"
import { formatQuantity, parseDecimal, quantityText } from "@/lib/persian-numbers"
import {
  invoiceTotal,
  type ItemType,
  lineField,
  lineProblems,
  type LineProblem,
  linesBody,
  pickId,
  unpick,
} from "@/lib/purchase-lines"
import { cn } from "@/lib/utils"
import { METHOD_LABELS, METHOD_ORDER, U } from "./copy"
import { LinePreview, type PreviewItem } from "./purchase-preview"
import type { RefreshedItem } from "./use-purchases-data"

const NO_SUPPLIER = 0

export type PurchaseFormHandle = { submit: () => void }

/** One line as typed: the picked item (`pickId`), its quantity text and its total (null = not an exact amount). */
type Draft = { key: number; pick: number | null; qtyText: string; total: number | null }

/** A refusal the server gave for one line, shown under that line's field. */
type LineErrors = Partial<Record<"item" | "qty" | "total", string>>

/**
 * The purchase entry form (design 07 drawer / mobile card): ONE supplier invoice — supplier, date, its lines (each a
 * STOCK material, a service or a finished product, with quantity, line total and the live cost preview), the invoice
 * total (the sum of the lines), what is paid now (full, on credit or partly, with the method and reference) and a
 * note. Used inside the desktop drawer and inline on mobile; the parent owns the submit button and calls `ref.submit()`.
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
    /** After a successful save, with every line's item re-read from the server. */
    onSaved: (items: RefreshedItem[], toast: string) => void
    refreshSuppliers: () => Promise<void>
  }
>(function PurchaseForm({ materials, products, suppliers, today, mobile, onBusyChange, onSaved, refreshSuppliers }, ref) {
  const nextKey = React.useRef(1)
  const newDraft = (): Draft => ({ key: nextKey.current++, pick: null, qtyText: "", total: 0 })
  const [lines, setLines] = React.useState<Draft[]>(() => [newDraft()])
  const [supplierId, setSupplierId] = React.useState(NO_SUPPLIER)
  const [date, setDate] = React.useState(today)
  const [note, setNote] = React.useState("")
  const [payMode, setPayMode] = React.useState<PaymentMode>("FULL")
  /** Integer Rial paid now for PARTIAL; null while the text gives no exact amount. */
  const [paidNow, setPaidNow] = React.useState<number | null>(0)
  const [method, setMethod] = React.useState<SupplierPaymentMethod>("CARD")
  const [reference, setReference] = React.useState("")
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const [supplierGone, setSupplierGone] = React.useState(false)
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>({})
  const [lineErrors, setLineErrors] = React.useState<Record<number, LineErrors>>({})

  // Only what the backend accepts: active STOCK materials, active services, active products.
  const buyableMaterials = materials.filter((m) => m.is_active === 1)
  const buyableProducts = products.filter((p) => p.is_active === 1)
  const itemOf = (pick: number | null): { kind: "material" | "product" | "service"; type: ItemType; item: Material | Product } | null => {
    if (pick == null) return null
    const { kind, id } = unpick(pick)
    if (kind === "PRODUCT") {
      const product = buyableProducts.find((p) => p.id === id)
      return product ? { kind: "product", type: "PRODUCT", item: product } : null
    }
    const material = buyableMaterials.find((m) => m.id === id)
    if (!material) return null
    return material.type === "SERVICE"
      ? { kind: "service", type: "SERVICE", item: material }
      : { kind: "material", type: "STOCK", item: material }
  }

  const itemPill = (stock: number, u: string) => ({
    text: (mobile ? U.stockPillMobile : U.stockPill)(formatQuantity(stock), u),
    tone: "neutral" as const,
  })
  const pickerItems: PickerItem[] = [
    ...buyableMaterials.map((m) =>
      m.type === "SERVICE"
        ? { id: pickId("MATERIAL", m.id), name: m.name, sub: U.subService }
        : { id: pickId("MATERIAL", m.id), name: m.name, sub: U.subMaterial, pill: itemPill(m.current_stock ?? 0, unitLabel(m.unit)) }
    ),
    ...buyableProducts.map((p) => ({ id: pickId("PRODUCT", p.id), name: p.name, sub: U.subProduct, pill: itemPill(p.current_stock, "عدد") })),
  ]
  const supplierItems: PickerItem[] = [
    { id: NO_SUPPLIER, name: U.noSupplierOption },
    ...[...suppliers].sort((a, b) => a.name.localeCompare(b.name, "fa")).map((s) => ({ id: s.id, name: s.name })),
  ]

  const unitOf = (found: ReturnType<typeof itemOf>) =>
    found == null ? "" : found.kind === "product" ? "عدد" : unitLabel((found.item as Material).unit)
  const qtyOf = (d: Draft): number | null => parseDecimal(d.qtyText)
  const problems: (LineProblem | null)[] = lineProblems(
    lines.map((d) => ({ pick: d.pick, itemType: itemOf(d.pick)?.type ?? null, qty: qtyOf(d), total: d.total }))
  )
  const total = invoiceTotal(lines.map((d) => d.total))
  const payProblem = purchasePaymentProblem(payMode, supplierId !== NO_SUPPLIER, total, paidNow)
  const supplierError = (touched && payProblem === "supplier") || fieldErrors.supplier_id ? U.supplierRequired : null
  const paidError = touched && payProblem === "partial_amount" ? U.partialRange : (fieldErrors["payment.amount"] ?? null)
  const linesError = fieldErrors.lines ?? null
  const hasService = lines.some((d) => itemOf(d.pick)?.kind === "service")

  const problemText = (p: LineProblem | null): Pick<LineErrors, "item" | "qty" | "total"> => {
    switch (p) {
      case "item":
        return { item: U.itemRequired }
      case "duplicate":
        return { item: U.duplicateItem }
      case "qty":
        return { qty: U.qtyRequired }
      case "qty_whole":
        return { qty: U.qtyInteger }
      case "total":
        return { total: U.totalInvalid }
      case "service_total":
        return { total: U.serviceTotal }
      default:
        return {}
    }
  }

  const patchLine = (key: number, patch: Partial<Draft>) => {
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)))
    setLineErrors({})
    setError(null)
  }
  const removeLine = (key: number) => {
    setLines((ls) => (ls.length > 1 ? ls.filter((l) => l.key !== key) : ls))
    setLineErrors({})
  }

  const reset = () => {
    setLines([newDraft()])
    setNote("")
    setPayMode("FULL")
    setPaidNow(0)
    setReference("")
    setTouched(false)
    setSupplierGone(false)
    setFieldErrors({})
    setLineErrors({})
  }

  const submit = async () => {
    setTouched(true)
    setError(null)
    setFieldErrors({})
    setLineErrors({})
    if (busy || problems.some((p) => p !== null) || total === null || payProblem !== null) return
    setBusy(true)
    onBusyChange(true)
    const picked = lines.map((d) => ({ pick: d.pick as number, qty: qtyOf(d) as number, total: d.total as number }))
    try {
      const saved = await createPurchase({
        supplier_id: supplierId === NO_SUPPLIER ? null : supplierId,
        // Today: the server stamps the current time. Another day: that day.
        purchase_date: date === today ? null : date,
        notes: note.trim() || null,
        payment: purchasePaymentBody(payMode, paidNow, method, reference),
        lines: linesBody(picked),
      })
      // The response is the invoice (each line's own unit cost); the items' new averages and prices are re-read.
      const refreshed: RefreshedItem[] = []
      await Promise.all(
        picked.map(async ({ pick }) => {
          const { kind, id } = unpick(pick)
          try {
            refreshed.push({ kind, item: kind === "MATERIAL" ? await getMaterial(id) : await getProduct(id) })
          } catch {
            // The purchase is saved either way; the toast just omits the average.
          }
        })
      )
      const only = refreshed.length === 1 && picked.length === 1 ? refreshed[0] : null
      onSaved(
        refreshed,
        only
          ? U.toastSaved(only.item.name, only.item.unit_cost ?? null)
          : U.toastSavedLines(saved.invoice_number, saved.lines.length)
      )
      reset()
    } catch (e) {
      const at = e instanceof ApiError ? lineField(e.field) : null
      if (e instanceof ApiError && e.status === 404 && e.code === "SUPPLIER_NOT_FOUND") {
        // The picked supplier was deleted since the list loaded: say so, make
        // them choose again, and refresh the list.
        setSupplierGone(true)
        setSupplierId(NO_SUPPLIER)
        refreshSuppliers().catch(() => {})
      } else if (e instanceof ApiError && classifyPayablesError(e).kind === "supplier_required") {
        setFieldErrors({ supplier_id: U.supplierRequired })
      } else if (e instanceof ApiError && e.status === 422 && e.field === "payment.amount") {
        setFieldErrors({ "payment.amount": U.partialRange })
      } else if (e instanceof ApiError && e.status === 422 && at) {
        const text =
          e.code === "PURCHASE_DUPLICATE_ITEM"
            ? U.duplicateItem
            : e.code === "SERVICE_PURCHASE_NEEDS_TOTAL"
              ? U.serviceTotal
              : e.code === "QUANTITY_NOT_WHOLE"
                ? U.qtyInteger
                : e.message
        const slot = at.field === "item_id" || at.field === "kind" ? "item" : at.field === "quantity_bought" ? "qty" : "total"
        setLineErrors({ [lines[at.index]?.key ?? -1]: { [slot]: text } })
      } else if (e instanceof ApiError && e.status === 422 && e.field === "lines") {
        setFieldErrors({ lines: e.message })
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

  const lineCard = (d: Draft, index: number) => {
    const found = itemOf(d.pick)
    const shown = touched ? problemText(problems[index]) : {}
    const server = lineErrors[d.key] ?? {}
    const itemError = server.item ?? shown.item ?? null
    const qtyError = server.qty ?? shown.qty ?? null
    const totalError = server.total ?? shown.total ?? null
    const qty = qtyOf(d)
    const preview: PreviewItem | null = found
      ? {
          name: found.item.name,
          kind: found.kind,
          stock: found.kind === "service" ? null : found.item.current_stock,
          cost: found.item.unit_cost,
          unit: unitOf(found),
        }
      : null
    return (
      <div key={d.key} className="flex flex-col gap-2.5 rounded-lg border border-border p-3">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor={`pf-item-${d.key}`}>{lines.length > 1 ? U.lineTitle(index + 1) : U.fieldItem}</Label>
          {lines.length > 1 && (
            <button
              type="button"
              onClick={() => removeLine(d.key)}
              aria-label={`${U.removeLine} (${U.lineTitle(index + 1)})`}
              className="flex cursor-pointer items-center gap-1 text-xs font-semibold text-text-3 outline-none hover:text-loss focus-visible:ring-3 focus-visible:ring-ring/30"
            >
              <Trash2 className="size-3.5" aria-hidden />
              {U.removeLine}
            </button>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <ItemPicker
            id={`pf-item-${d.key}`}
            items={pickerItems}
            value={d.pick}
            onPick={(id) => patchLine(d.key, { pick: id })}
            placeholder={U.pickItem}
            searchLabel={U.searchItem}
            emptyText={U.noItems}
            noMatchText={U.noItemMatch}
            mobile={mobile}
            error={!!itemError}
          />
          {itemError && <InlineMessage severity="error">{itemError}</InlineMessage>}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor={`pf-qty-${d.key}`}>{U.fieldQty}</Label>
            <div className="relative flex items-center">
              <input
                id={`pf-qty-${d.key}`}
                inputMode="decimal"
                value={d.qtyText}
                onChange={(e) => patchLine(d.key, { qtyText: e.target.value })}
                onBlur={() => {
                  const n = parseDecimal(d.qtyText)
                  if (n != null) patchLine(d.key, { qtyText: quantityText(n) })
                }}
                placeholder={formatQuantity(0)}
                aria-invalid={!!qtyError || undefined}
                className={cn(inputCls, "pe-16 tabular-nums", qtyError && "border-loss ring-3 ring-loss-soft")}
              />
              <span className="pointer-events-none absolute end-3 text-xs text-text-3">{unitOf(found)}</span>
            </div>
            {qtyError && <InlineMessage severity="error">{qtyError}</InlineMessage>}
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor={`pf-total-${d.key}`}>{U.fieldLineTotal}</Label>
            <MoneyInput
              id={`pf-total-${d.key}`}
              value={d.total}
              onValue={(v) => patchLine(d.key, { total: v ?? null })}
              tone={totalError ? "error" : touched && d.total === 0 && found?.kind !== "service" && found != null ? "warn" : null}
              className={mobile ? "h-12" : undefined}
            />
          </div>
        </div>
        {totalError ? (
          <InlineMessage severity="error">{totalError}</InlineMessage>
        ) : (
          touched && d.total === 0 && found != null && found.kind !== "service" && <InlineMessage severity="warn">{U.totalZero}</InlineMessage>
        )}
        <LinePreview item={preview} qty={qty} total={d.total} />
      </div>
    )
  }

  const dateField = (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor="pf-date">{mobile ? U.fieldDateMobile : U.fieldDate}</Label>
      <DateField id="pf-date" value={date} today={today} onChange={setDate} todayLabel={U.today} mobile={mobile} />
    </div>
  )

  const methodItems: PickerItem[] = METHOD_ORDER.map((m, i) => ({ id: i + 1, name: METHOD_LABELS[m] }))
  const paymentField = (
    <div className="flex flex-col gap-2.5 rounded-lg border border-border p-3">
      <div className="flex flex-col gap-1.5">
        <Label>{U.fieldPayment}</Label>
        <Segment<PaymentMode>
          value={payMode}
          options={[
            ["FULL", U.payFull],
            ["NONE", U.payNone],
            ["PARTIAL", U.payPartial],
          ]}
          onChange={(m) => {
            setPayMode(m)
            setFieldErrors({})
          }}
          label={U.fieldPayment}
          mobile={mobile}
          className="grid grid-cols-3"
        />
      </div>
      {payMode === "PARTIAL" && (
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="pf-paid">{U.fieldPaidAmount}</Label>
          <MoneyInput
            id="pf-paid"
            value={paidNow}
            onValue={(v) => setPaidNow(v ?? null)}
            tone={paidError ? "error" : null}
            className={mobile ? "h-12" : undefined}
          />
          {paidError && <InlineMessage severity="error">{paidError}</InlineMessage>}
        </div>
      )}
      {payMode !== "NONE" && (
        <div className="grid grid-cols-2 gap-2">
          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor="pf-method">{U.fieldMethod}</Label>
            <ItemPicker
              id="pf-method"
              items={methodItems}
              value={METHOD_ORDER.indexOf(method as (typeof METHOD_ORDER)[number]) + 1}
              onPick={(id) => setMethod(METHOD_ORDER[id - 1] ?? "OTHER")}
              placeholder={U.fieldMethod}
              searchLabel={U.searchMethod}
              emptyText={U.fieldMethod}
              noMatchText={U.noItemMatch}
              mobile={mobile}
            />
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor="pf-ref" optional>
              {U.fieldReference}
            </Label>
            <input id="pf-ref" dir="ltr" value={reference} onChange={(e) => setReference(e.target.value)} className={inputCls} />
          </div>
        </div>
      )}
      {payMode !== "FULL" && <Help>{U.creditHelp}</Help>}
    </div>
  )

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-3.5")}>
      {error && <SaveError {...error} />}
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
          error={supplierGone || !!supplierError}
        />
        {supplierGone ? (
          <InlineMessage severity="error">{U.supplierGone}</InlineMessage>
        ) : supplierError ? (
          <InlineMessage severity="error">{supplierError}</InlineMessage>
        ) : (
          suppliers.length === 0 && <Help>{U.noSuppliersYet}</Help>
        )}
      </div>
      {dateField}
      <div className="flex flex-col gap-2.5">
        <h3 className="text-sm font-bold text-heading">{U.fieldLines}</h3>
        {lines.map(lineCard)}
        <button
          type="button"
          onClick={() => setLines((ls) => [...ls, newDraft()])}
          className="flex h-10 cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-dashed border-border-strong text-[13px] font-semibold text-text-2 outline-none hover:bg-surface-2 focus-visible:ring-3 focus-visible:ring-ring/30"
        >
          <Plus className="size-4" aria-hidden />
          {U.addLine}
        </button>
        {linesError && <InlineMessage severity="error">{linesError}</InlineMessage>}
        {hasService && <Help>{U.serviceHelp}</Help>}
      </div>
      <div className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 px-3 py-2.5">
        <span className="flex flex-col">
          <span className="text-[13px] font-bold text-heading">{U.fieldTotal}</span>
          <span className="text-xs text-text-3">{U.invoiceTotalHelp}</span>
        </span>
        {total === null ? <span className="text-text-3">—</span> : <Money value={total} className="text-[17px] font-bold" />}
      </div>
      {paymentField}
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
