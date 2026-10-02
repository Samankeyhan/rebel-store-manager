"use client"

import * as React from "react"
import { ChevronLeft, Loader2, Minus, Plus, SlidersHorizontal, Trash2 } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { ItemPicker, type PickerItem } from "@/components/common/item-picker"
import { Segment } from "@/components/common/segment"
import { SaveError } from "@/components/products/drawer-shell"
import { Btn, cardClass, Help, InlineMessage, Label, OptionTile, inputClass } from "@/components/record-sale/primitives"
import {
  ApiError,
  createAdjustment,
  getMaterial,
  getProduct,
  type Material,
  type Product,
} from "@/lib/api"
import { dateToISO } from "@/lib/jalali"
import { formatMoney, formatNumber, formatQuantity, parseDecimal, toLatinDigits } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { A } from "./copy"
import {
  fromMaterial,
  fromProduct,
  itemTypeOf,
  previewOf,
  reasonOf,
  signOf,
  validate,
  type AdjItem,
  type Dir,
  type ItemKind,
  type Kind,
  type RowKind,
} from "./figures"
import { KindBadge } from "./kind-badge"

const currentDay = () => dateToISO(new Date())

export type AdjustmentFormHandle = { submit: () => void; focus: () => void }

type SaveErr = { message: string; code: string }

/**
 * «ثبت تعدیل» (design 10): kind, item, direction, quantity, unit cost, date,
 * reason, and the live before → after preview. Desktop renders the form card
 * and the preview card side by side (the preview holds the save button);
 * mobile renders the form and a compact preview, and the parent's sticky
 * footer calls `ref.submit()`.
 */
export const AdjustmentForm = React.forwardRef<
  AdjustmentFormHandle,
  {
    products: Product[]
    materials: Material[]
    mobile: boolean
    onBusyChange: (busy: boolean) => void
    /** After a successful save, with the item re-read from the server (or null if that failed). */
    onSaved: (kind: ItemKind, item: Product | Material | null, toast: string) => void
    /** A fresh copy of one item (after a stock conflict), to replace in the lists. */
    onItemRefreshed: (kind: ItemKind, item: Product | Material) => void
    /** The item turned out gone or inactive: reload the lists. */
    onItemsStale: () => void
  }
>(function AdjustmentForm({ products, materials, mobile, onBusyChange, onSaved, onItemRefreshed, onItemsStale }, ref) {
  const [kind, setKind] = React.useState<Kind>("waste")
  const [dir, setDir] = React.useState<Dir>("minus")
  const [itemKind, setItemKind] = React.useState<ItemKind>("product")
  const [itemId, setItemId] = React.useState<number | null>(null)
  const [qtyText, setQtyText] = React.useState("")
  const [costText, setCostText] = React.useState("")
  const [note, setNote] = React.useState("")
  // null = today, resolved at submission (a session can cross midnight).
  const [pickedDate, setPickedDate] = React.useState<string | null>(null)
  const [today, setToday] = React.useState(currentDay)
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<SaveErr | null>(null)
  const [fieldErrors, setFieldErrors] = React.useState<{ qty?: string; cost?: string }>({})

  React.useEffect(() => {
    const t = window.setInterval(() => setToday(currentDay()), 60_000)
    return () => window.clearInterval(t)
  }, [])

  // Only what the backend accepts: active products, active STOCK materials.
  const items: AdjItem[] =
    itemKind === "product"
      ? products.filter((p) => p.is_active === 1).map(fromProduct)
      : materials.filter((m) => m.is_active === 1 && m.type === "STOCK").map(fromMaterial)
  const item = items.find((i) => i.id === itemId) ?? null

  const sign = signOf(kind, dir)
  const showCost = kind === "correction" && dir === "plus"
  const qty = parseDecimal(qtyText)
  const costDigits = toLatinDigits(costText).replace(/[^0-9]/g, "")
  const unitCost = showCost && costDigits !== "" ? Number.parseInt(costDigits, 10) : null

  const clientError = item ? validate(item, qty, sign) : null
  const showQtyError = touched || qtyText.trim() !== ""
  const qtyError = fieldErrors.qty ?? (showQtyError ? clientError : null)
  const itemError = touched && item == null ? A.itemRequired : null
  const valid = item != null && clientError == null
  const preview = valid ? previewOf(item, qty!, sign, unitCost) : null
  const rowKind: RowKind = kind === "waste" ? "waste" : dir === "plus" ? "plus" : "minus"

  const clearServerErrors = () => {
    setFieldErrors({})
    setError(null)
  }
  const pickKind = (k: Kind) => {
    setKind(k)
    // Waste always decreases: picking it forces the direction (design §3).
    if (k === "waste") setDir("minus")
    clearServerErrors()
  }
  const switchItemKind = (k: ItemKind) => {
    if (k === itemKind) return
    setItemKind(k)
    setItemId(null)
    clearServerErrors()
  }

  const submit = async () => {
    setTouched(true)
    setError(null)
    if (item == null || clientError != null || busy) return
    setFieldErrors({})
    setBusy(true)
    onBusyChange(true)
    const day = currentDay()
    try {
      await createAdjustment({
        item_type: itemTypeOf(item.kind),
        item_id: item.id,
        quantity_change: sign * qty!,
        reason: reasonOf(kind),
        unit_cost: unitCost,
        notes: note.trim() || null,
        // Today: the server stamps the current time. Another day: that day.
        movement_date: pickedDate == null || pickedDate === day ? null : pickedDate,
      })
      let fresh: Product | Material | null = null
      try {
        fresh = item.kind === "product" ? await getProduct(item.id) : await getMaterial(item.id)
      } catch {
        // The adjustment is saved either way; the lists catch up on the next load.
      }
      onSaved(item.kind, fresh, A.toastSaved(item.name))
      setQtyText("")
      setCostText("")
      setNote("")
      setTouched(false)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.type === "InsufficientStockError") {
        // Stock moved since the list loaded: say what the server has, and re-read the item.
        const available = Number(e.details.available ?? 0)
        setFieldErrors({ qty: A.serverShort(available, item.unit, item.name) })
        const reread = item.kind === "product" ? getProduct(item.id) : getMaterial(item.id)
        reread.then((fresh) => onItemRefreshed(item.kind, fresh), () => {})
      } else if (e instanceof ApiError && e.status === 422 && e.field === "quantity_change") {
        setFieldErrors({ qty: e.message })
      } else if (e instanceof ApiError && e.status === 422 && e.field === "unit_cost") {
        setFieldErrors({ cost: e.message })
      } else if (e instanceof ApiError && (e.status === 404 || (e.status === 422 && e.field == null && e.type === "ValidationError"))) {
        // Deactivated, deleted or turned into a service since the list loaded.
        setError({ message: e.message, code: `ADJ_${e.status}` })
        setItemId(null)
        onItemsStale()
      } else {
        setError(
          e instanceof ApiError
            ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `ADJ_${e.status}` }
            : { message: String(e), code: "UNKNOWN" }
        )
      }
    } finally {
      setBusy(false)
      onBusyChange(false)
    }
  }

  React.useImperativeHandle(ref, () => ({
    submit,
    focus: () => document.getElementById("adj-item")?.focus(),
  }))

  const ctlH = mobile ? "h-12" : "h-10"
  const pickerItems: PickerItem[] = items.map((i) => ({
    id: i.id,
    name: i.name,
    pill: { text: A.stockPill(formatQuantity(i.stock), i.unit), tone: i.stock <= 0 ? "out" : "neutral" },
  }))
  const kindLabel = (k: ItemKind) => (k === "product" ? A.segProduct : A.segMaterial)

  // ------------------------------------------------------------ fields
  const kindField = mobile ? (
    <div className="flex flex-col gap-2">
      <Segment<Kind>
        value={kind}
        options={[
          ["waste", A.waste],
          ["correction", A.correction],
        ]}
        onChange={pickKind}
        label={A.fieldKind}
        mobile
        className="grid grid-cols-2 [&_button]:h-11"
      />
      <Help>
        <b className="text-loss">{A.kindHelpMobileWaste}</b>
        {A.kindHelpMobileMid}
        <b className="text-foreground">{A.kindHelpMobileCorrection}</b>
        {A.kindHelpMobileEnd}
      </Help>
    </div>
  ) : (
    <div className="flex flex-col gap-1.5">
      <Label>{A.fieldKind}</Label>
      <div role="radiogroup" aria-label={A.fieldKind} className="grid grid-cols-2 gap-2.5">
        <OptionTile selected={kind === "waste"} onSelect={() => pickKind("waste")}>
          <span className="flex items-center gap-1.5 text-sm font-bold">
            <Trash2 className="size-4" aria-hidden />
            {A.waste}
          </span>
          <span className="text-xs text-text-3">{A.wasteSub1}</span>
          <span className="text-xs font-bold text-loss">{A.wasteSub2}</span>
        </OptionTile>
        <OptionTile selected={kind === "correction"} onSelect={() => pickKind("correction")}>
          <span className="flex items-center gap-1.5 text-sm font-bold">
            <SlidersHorizontal className="size-4" aria-hidden />
            {A.correction}
          </span>
          <span className="text-xs text-text-3">{A.correctionSub1}</span>
          <span className="text-xs font-bold text-foreground">{A.correctionSub2}</span>
        </OptionTile>
      </div>
    </div>
  )

  const itemField = (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="adj-item">{A.fieldItem}</Label>
      <Segment<ItemKind>
        value={itemKind}
        options={[
          ["product", A.segProduct],
          ["material", A.segMaterial],
        ]}
        onChange={switchItemKind}
        label={A.fieldItemType}
        mobile={mobile}
        className="grid grid-cols-2"
      />
      <ItemPicker
        id="adj-item"
        items={pickerItems}
        value={itemId}
        onPick={(id) => {
          setItemId(id)
          clearServerErrors()
        }}
        placeholder={A.pickItem}
        searchLabel={A.searchItem}
        emptyText={A.noItems}
        noMatchText={A.noItemMatch}
        mobile={mobile}
        error={!!itemError}
      />
      {itemError ? (
        <InlineMessage severity="error">{itemError}</InlineMessage>
      ) : (
        item && (
          <Help className="tabular-nums">
            {mobile
              ? A.itemMetaMobile(kindLabel(item.kind), formatQuantity(item.stock), item.unit)
              : A.itemMeta(kindLabel(item.kind), formatQuantity(item.stock), item.unit, item.cost)}
          </Help>
        )
      )}
    </div>
  )

  const dirField = kind === "correction" && (
    <div className="flex flex-col gap-1.5">
      <Label>{A.fieldDir}</Label>
      <div role="radiogroup" aria-label={A.fieldDir} className="grid grid-cols-2 gap-0.5 rounded-[10px] border border-border bg-surface-2 p-[3px]">
        {(
          [
            ["plus", A.dirPlus, Plus],
            ["minus", A.dirMinus, Minus],
          ] as const
        ).map(([v, text, Icon]) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={dir === v}
            onClick={() => {
              setDir(v)
              clearServerErrors()
            }}
            className={cn(
              "flex cursor-pointer items-center justify-center gap-1.5 rounded-[7px] px-3 text-[13px] font-semibold text-text-2 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
              mobile ? "h-10" : "h-[32px]",
              dir === v && "bg-card text-heading shadow-[0_4px_14px_rgba(18,22,38,.08)]"
            )}
          >
            <Icon className="size-3.5" aria-hidden />
            {text}
          </button>
        ))}
      </div>
    </div>
  )

  const qtyField = (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="adj-qty">{A.fieldQty}</Label>
      <div className={cn("relative flex items-center", !mobile && "max-w-[220px]")}>
        <input
          id="adj-qty"
          inputMode="decimal"
          autoComplete="off"
          value={qtyText}
          onChange={(e) => {
            setQtyText(e.target.value)
            if (fieldErrors.qty) setFieldErrors((f) => ({ ...f, qty: undefined }))
          }}
          onBlur={() => {
            const n = parseDecimal(qtyText)
            if (n != null) setQtyText(formatQuantity(n))
          }}
          placeholder={formatQuantity(0)}
          aria-invalid={!!qtyError || undefined}
          aria-describedby="adj-qty-help"
          className={inputClass(qtyError ? "error" : null, cn("pe-16 tabular-nums", ctlH))}
        />
        <span className="pointer-events-none absolute end-3 text-xs text-text-3">{item?.unit ?? ""}</span>
      </div>
      {qtyError && <InlineMessage severity="error">{qtyError}</InlineMessage>}
      {item && (
        <Help>
          <span id="adj-qty-help">{item.kind === "product" ? A.qtyHelpProduct : A.qtyHelpMaterial}</span>
        </Help>
      )}
    </div>
  )

  const costField = showCost && (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="adj-cost" optional>
        {A.fieldCost}
      </Label>
      <div className={cn("relative flex items-center", !mobile && "max-w-[220px]")}>
        <input
          id="adj-cost"
          inputMode="numeric"
          autoComplete="off"
          value={costText === "" ? "" : formatNumber(Number.parseInt(costDigits || "0", 10))}
          onChange={(e) => {
            const d = toLatinDigits(e.target.value).replace(/[^0-9]/g, "")
            setCostText(d)
            if (fieldErrors.cost) setFieldErrors((f) => ({ ...f, cost: undefined }))
          }}
          aria-invalid={!!fieldErrors.cost || undefined}
          className={inputClass(fieldErrors.cost ? "error" : null, cn("pe-14 tabular-nums", ctlH))}
        />
        <span className="pointer-events-none absolute end-3 text-xs text-text-3">{A.toman}</span>
      </div>
      {fieldErrors.cost ? (
        <InlineMessage severity="error">{fieldErrors.cost}</InlineMessage>
      ) : unitCost === 0 ? (
        <InlineMessage severity="warn">{A.costZero}</InlineMessage>
      ) : (
        <Help>{A.costHelp(item?.cost ?? null)}</Help>
      )}
    </div>
  )

  const dateField = (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="adj-date">{A.fieldDate}</Label>
      <DateField
        id="adj-date"
        value={pickedDate ?? today}
        today={today}
        onChange={(d) => setPickedDate(d === today ? null : d)}
        todayLabel={A.today}
        mobile={mobile}
      />
    </div>
  )

  const reasonField = (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="adj-reason" optional>
        {A.fieldReason}
      </Label>
      <input
        id="adj-reason"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder={A.reasonPlaceholder}
        className={inputClass(null, ctlH)}
      />
    </div>
  )

  // ------------------------------------------------------------ preview
  const errored = item != null && clientError != null && showQtyError
  const afterText = !item ? "—" : preview ? formatQuantity(preview.after) : "—"
  const valueLabel = kind === "waste" ? A.valueWaste : dir === "plus" ? A.valuePlus : A.valueMinus
  const valueText =
    preview && preview.value != null ? `\u2066${preview.value > 0 ? "+" : ""}${formatNumber(preview.value)}\u2069 ${A.toman}` : "—"

  const beforeAfter = (
    <div
      className={cn(
        "grid grid-cols-[1fr_auto_1fr] items-center gap-4 rounded-xl bg-surface-2",
        mobile ? "p-3.5" : "px-5 py-[18px]"
      )}
    >
      <div className="flex flex-col">
        <span className="text-xs font-bold text-text-3">{A.before}</span>
        <span className={cn("font-bold tabular-nums", mobile ? "text-2xl" : "text-[28px] leading-10")}>
          {item ? formatQuantity(item.stock) : "—"}
        </span>
        <span className="text-xs text-text-3">{item?.unit ?? ""}</span>
      </div>
      {/* current → after in reading order: in RTL the chevron points left. */}
      <ChevronLeft className={cn("text-text-3", mobile ? "size-5" : "size-6")} aria-hidden />
      <div className="flex flex-col">
        <span className="text-xs font-bold text-text-3">{A.after}</span>
        <span
          className={cn("font-bold tabular-nums", mobile ? "text-2xl" : "text-[28px] leading-10", (errored || fieldErrors.qty) && "text-loss")}
        >
          {fieldErrors.qty ? "—" : afterText}
        </span>
        <span className="text-xs text-text-3">{preview && !fieldErrors.qty ? item?.unit : "\u00a0"}</span>
      </div>
    </div>
  )

  const valueRow = (
    <div className="flex items-center justify-between gap-3 border-b border-border pb-2.5 text-[13px]">
      <span className="text-text-2">{valueLabel}</span>
      <b className={cn("tabular-nums", preview?.value != null && preview.value < 0 && "text-loss")}>{valueText}</b>
    </div>
  )

  const avgRow = preview?.newCost != null && item && (
    <div className="flex items-center justify-between gap-3 border-b border-border pb-2.5 text-[13px]">
      <span className="text-text-2">{A.avgLabel}</span>
      <b className="tabular-nums">
        {item.cost == null ? A.noCost : formatMoney(item.cost)} ← {formatMoney(preview.newCost)}
      </b>
    </div>
  )

  const noCostNote = kind === "waste" && item && item.cost == null && (
    <InlineMessage severity="warn">{A.noCostWaste}</InlineMessage>
  )

  if (mobile) {
    return (
      <>
        <section className={cn(cardClass, "flex flex-col gap-3 p-3.5")}>
          {error && <SaveError {...error} />}
          {kindField}
          {itemField}
          {dirField}
          {qtyField}
          {costField}
          {dateField}
          {reasonField}
        </section>
        <section aria-label={A.previewTitle} className="flex flex-col gap-2.5">
          {beforeAfter}
          {item && (
            <div className="flex flex-col gap-2 px-1">
              {valueRow}
              {avgRow}
              {noCostNote}
            </div>
          )}
        </section>
      </>
    )
  }

  return (
    <div className="flex items-start gap-6">
      <section aria-labelledby="adj-form-title" className={cn(cardClass, "w-[440px] shrink-0")}>
        <div className="border-b border-border px-5 py-4">
          <h2 id="adj-form-title" className="text-base font-bold text-heading">
            {A.formTitle}
          </h2>
        </div>
        <div className="flex flex-col gap-3.5 p-5">
          {error && <SaveError {...error} />}
          {kindField}
          {itemField}
          {dirField}
          {qtyField}
          {costField}
          {dateField}
          {reasonField}
        </div>
      </section>
      <section aria-labelledby="adj-preview-title" className={cn(cardClass, "min-w-0 grow")}>
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <h2 id="adj-preview-title" className="text-base font-bold text-heading">
            {A.previewTitle}
          </h2>
          <KindBadge kind={rowKind} />
        </div>
        <div className="flex flex-col gap-4 p-5">
          {item == null ? (
            <p className="rounded-xl bg-surface-2 px-5 py-8 text-center text-[13px] text-text-3">{A.pickToPreview}</p>
          ) : (
            <>
              {beforeAfter}
              {valueRow}
              {avgRow}
              {noCostNote}
            </>
          )}
          <p className="text-xs leading-[1.8] text-text-3">{kind === "waste" ? A.noteWaste : A.noteCorrection}</p>
          <Btn variant="primary" className="self-start" disabled={busy} aria-busy={busy || undefined} onClick={submit}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {A.submit}
          </Btn>
        </div>
      </section>
    </div>
  )
})
