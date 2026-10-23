"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useIsMobile } from "@/hooks/use-mobile"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import {
  ApiError,
  correctOrder,
  createOrder,
  getCatalog,
  getOrder,
  getVoidPreview,
  listPaymentMethods,
  type Catalog,
  type OrderDetail,
  type PaymentMethod,
  type VoidPreview,
} from "@/lib/api"
import { refusedProductId } from "@/lib/error-codes"
import { formatJalali, utcToLocal } from "@/lib/jalali"
import { canVoid, catalogAfterVoid, correctionPrefill, voidRefusal } from "@/lib/order-correction"
import { D as OrderCopy } from "@/components/orders/copy"
import { voidBlockerTexts } from "@/components/orders/detail/dialogs"
import { isFutureOrderDateError, isStaleSaleDay } from "@/lib/sale-date"
import { classifyPaymentError } from "@/lib/payment-methods"
import { DEFAULT_TZ, storeToday } from "@/lib/store-day"
import { paymentErrorText } from "@/components/payment-methods/copy"
import { T, type Channel } from "./copy"
import { derive, orderTotal } from "./derive"
import type { PaymentUi } from "./payment-fields"
import { useFeePreview } from "./use-fee-preview"
import { Btn } from "./primitives"
import { ChannelCard, InternalCostsCard, ShippingCard, StatusCard } from "./form-cards"
import { ItemsCard } from "./items-card"
import { MobileSummarySheet, SummaryPanel } from "./summary-panel"
import { CorrectionBlocked, CorrectionCard } from "./correction-card"
import {
  buildOrderBody,
  correctionState,
  initialState,
  moneyBlocked,
  orderDay,
  productMap,
  reducer,
  resolveMethod,
  type FormState,
  type ServerIssue,
} from "./state"
import { useRecipes } from "./use-recipes"
import { Banners, EmptyView, LoadErrorView, LoadingView, ServerAlert, SuccessView, Toast } from "./views"
import { useCurrency } from "@/lib/use-currency"

/** «اصلاح سفارش»: the order being corrected and what voiding it does (`/sales/new/?correct=<id>`). */
type Correction = { detail: OrderDetail; preview: VoidPreview }

type Load =
  | { status: "loading" }
  | { status: "error"; code: string }
  /** methods: every payment method (inactive included), or null when that request failed. */
  | { status: "ready"; catalog: Catalog; methods: PaymentMethod[] | null; correction: Correction | null }

function loadErrorCode(error: unknown): string {
  if (error instanceof ApiError && error.status > 0) return `CATALOG_${error.status}`
  return "NET_TIMEOUT"
}

/** Which of this order's products a no-recipe / no-cost refusal is about (details.product_id). */
function refusedProduct(error: ApiError, state: FormState, catalog: Catalog) {
  const id = refusedProductId(error)
  const ids = new Set(state.lines.map((l) => l.productId))
  return id != null && ids.has(id) ? catalog.products.find((p) => p.id === id) : undefined
}

/** Maps a POST /orders failure to where the UI shows it. */
function classifyOrderError(
  error: unknown,
  state: FormState,
  catalog: Catalog,
  methodName: string | null = null
): ServerIssue {
  if (!(error instanceof ApiError)) {
    return { kind: "generic", message: String(error), code: "UNKNOWN" }
  }
  // A correction's void refused (settled meanwhile, a closed day, a stocktake…): say why, in Persian.
  const refusal = voidRefusal(error)
  if (refusal) return { kind: "generic", message: OrderCopy.voidRefusal(refusal), code: error.code ?? `ORDERS_${error.status}` }
  // The sale day itself, before the generic payment-day mapping below.
  if (isFutureOrderDateError(error)) return { kind: "orderDate", message: T.orderDateFuture }
  // Payment errors go next to their field, in Persian (closed month, future paid date, inactive method…).
  const payment = classifyPaymentError(error)
  if (payment) {
    const field =
      payment.kind === "inactiveMethod" ? "payment_method_id" : "paid_date"
    return { kind: "payment", field, message: paymentErrorText(payment, methodName) }
  }
  if (error.status === 404 && error.code === "PAYMENT_METHOD_NOT_FOUND") {
    return { kind: "payment", field: "payment_method_id", message: paymentErrorText({ kind: "inactiveMethod" }, null) }
  }
  if (error.status === 422 && error.field === "transaction_fee") {
    return { kind: "payment", field: "transaction_fee", message: T.feeInvalid }
  }
  if (error.status === 409 && error.type === "InsufficientStockError") {
    const itemName = String(error.details.item_name ?? "")
    const needed = Number(error.details.needed ?? 0)
    const available = Number(error.details.available ?? 0)
    const ids = new Set(state.lines.map((l) => l.productId))
    const product = catalog.products.find((p) => ids.has(p.id) && p.name === itemName)
    const material = product ? undefined : catalog.materials.find((m) => m.name === itemName)
    return {
      kind: "stock",
      itemName,
      needed,
      available,
      productId: product?.id ?? null,
      unit: material?.unit ?? null,
    }
  }
  if (error.status === 422 && (error.field === "unit_cost" || error.field === "made_to_order")) {
    const product = refusedProduct(error, state, catalog)
    if (product) {
      return { kind: error.field === "unit_cost" ? "noCost" : "noRecipe", productId: product.id, name: product.name }
    }
  }
  const code = error.status === 0 ? "NET_TIMEOUT" : `ORDERS_${error.status}`
  return { kind: "generic", message: error.message, code }
}

let lineKeySeq = 1
const nextLineKey = () => lineKeySeq++

export function RecordSale() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const [load, setLoad] = React.useState<Load>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)
  const mobile = useIsMobile()
  const params = useSearchParams()
  const raw = params.get("correct") ?? ""
  const correctId = /^\d+$/.test(raw) ? Number(raw) : null

  React.useEffect(() => {
    let cancelled = false
    // The methods list failing doesn't stop a sale: resolveMethod blocks only
    // when the channel has a default method (see PaymentMethodField's retry).
    const correction: Promise<Correction | null> =
      correctId == null
        ? Promise.resolve(null)
        : Promise.all([getOrder(correctId), getVoidPreview(correctId)]).then(([detail, preview]) => ({ detail, preview }))
    Promise.all([getCatalog(), listPaymentMethods(true).catch(() => null), correction]).then(
      ([catalog, methods, c]) => !cancelled && setLoad({ status: "ready", catalog, methods, correction: c }),
      (error: unknown) => !cancelled && setLoad({ status: "error", code: loadErrorCode(error) })
    )
    return () => {
      cancelled = true
    }
  }, [attempt, correctId])

  const reload = React.useCallback(() => {
    setLoad({ status: "loading" })
    setAttempt((a) => a + 1)
  }, [])

  if (load.status === "loading") return <LoadingView mobile={mobile} />
  if (load.status === "error") return <LoadErrorView code={load.code} onRetry={reload} mobile={mobile} />
  if (load.catalog.products.length === 0) return <EmptyView mobile={mobile} />
  const c = load.correction
  if (c && (!canVoid(c.detail.order) || c.preview.blockers.length > 0)) {
    const reasons = c.preview.blockers.length > 0 ? voidBlockerTexts(c.preview) : [T.correctNotVoidable]
    return <CorrectionBlocked orderId={c.detail.order.id} reasons={reasons} mobile={mobile} />
  }
  return (
    <SaleForm
      key={c ? `correct-${c.detail.order.id}` : "new"}
      baseCatalog={load.catalog}
      initialMethods={load.methods}
      correction={c}
      mobile={mobile}
      onNewSale={reload}
    />
  )
}

const currentStoreDay = (timeZone: string) => storeToday(new Date(), timeZone)

function SaleForm({
  baseCatalog,
  initialMethods,
  correction,
  mobile,
  onNewSale,
}: {
  baseCatalog: Catalog
  initialMethods: PaymentMethod[] | null
  /** «اصلاح سفارش»: the order this sale replaces; null for a new sale. */
  correction: Correction | null
  mobile: boolean
  /** Refetches the catalog so the next sale sees fresh stock and costs. */
  onNewSale: () => void
}) {
  const router = useRouter()
  // A correction voids the old order first, in the same operation: its stock is available to this sale.
  const catalog = React.useMemo(
    () => (correction ? catalogAfterVoid(baseCatalog, correction.preview) : baseCatalog),
    [baseCatalog, correction]
  )
  const [state, dispatch] = React.useReducer(reducer, undefined, () => {
    if (!correction) return initialState(nextLineKey())
    const tz = baseCatalog.settings.timezone || DEFAULT_TZ
    const today = currentStoreDay(tz)
    const day = utcToLocal(correction.detail.order.order_date, tz)?.iso ?? today
    return correctionState(correctionPrefill(correction.detail, day), correction.detail.order.id, nextLineKey, today)
  })
  const [openPicker, setOpenPicker] = React.useState<number | null>(null)
  const [toast, setToast] = React.useState<string | null>(null)
  const topRef = React.useRef<HTMLDivElement>(null)

  const products = React.useMemo(() => productMap(catalog), [catalog])
  const mtoIds = state.lines
    .map((l) => (l.productId == null ? null : products.get(l.productId)))
    .filter((p) => p?.made_to_order)
    .map((p) => p!.id)
  const recipes = useRecipes(mtoIds)

  // Payment method and its fee (the backend computes it; we only ask for a preview).
  const [methods, setMethods] = React.useState(initialMethods)
  const [methodsLoading, setMethodsLoading] = React.useState(false)
  const reloadMethods = React.useCallback(async () => {
    setMethodsLoading(true)
    try {
      setMethods(await listPaymentMethods(true))
    } catch {
      setMethods(null)
    } finally {
      setMethodsLoading(false)
    }
  }, [])
  // "Today" is the store's day (settings.timezone; Asia/Tehran if unset), kept current.
  const timeZone = catalog.settings.timezone || DEFAULT_TZ
  const [today, setToday] = React.useState(() => currentStoreDay(timeZone))
  React.useEffect(() => {
    const t = window.setInterval(() => setToday(currentStoreDay(timeZone)), 60_000)
    return () => window.clearInterval(t)
  }, [timeZone])

  const channelDefault = catalog.settings.channels[state.channel]?.default_payment_method_id ?? null
  const resolved = resolveMethod(state.payment, channelDefault, methods)
  const autoFee = resolved.kind === "method" && state.feeMode === "auto" && !moneyBlocked(state)
  const preview = useFeePreview(
    resolved.kind === "method" ? resolved.method.id : null,
    autoFee ? orderTotal(state, catalog) : null
  )
  const payment: PaymentUi = { methods, resolved, preview, today, retryMethods: reloadMethods, methodsLoading }

  const d = derive(state, catalog, products, recipes, { resolved, preview })

  const onChannel = (channel: Channel) => dispatch({ type: "channel", channel, products })
  const toDraft = () => dispatch({ type: "status", status: "DRAFT" })
  const addLine = () => {
    const key = nextLineKey()
    dispatch({ type: "addLine", key })
    setOpenPicker(key)
  }
  const cancel = () => {
    if (correction) {
      router.push(`/orders/view/?id=${correction.detail.order.id}`)
      return
    }
    setOpenPicker(null)
    dispatch({ type: "reset", firstLineKey: nextLineKey() })
  }

  // Never once saved: the success screen keeps this component mounted.
  const canSave = !d.saveDisabled && !state.saving && !state.result
  // A sale dated more than 31 days back asks once before it is saved (the day, shown in Jalali).
  const [staleDay, setStaleDay] = React.useState<string | null>(null)
  const save = async () => {
    if (!canSave) return
    const now = currentStoreDay(timeZone)
    const day = orderDay(state, now)
    if (isStaleSaleDay(day, now)) {
      setStaleDay(day)
      return
    }
    await submit()
  }
  const submit = async () => {
    if (!canSave) return
    dispatch({ type: "submitStart" })
    try {
      // Read the store's day now: a session can cross midnight.
      const body = buildOrderBody(state, resolved, currentStoreDay(timeZone))
      if (correction) {
        // The old order's notes go with it (this form has no notes field).
        const result = await correctOrder(correction.detail.order.id, state.correctionReason.trim(), {
          ...body,
          notes: correction.detail.order.notes,
        })
        router.push(`/orders/view/?id=${result.order.id}`)
        return
      }
      const result = await createOrder(body)
      dispatch({ type: "submitSuccess", result })
      setToast(result.order.invoice_number ?? "")
      window.scrollTo({ top: 0 })
    } catch (error) {
      const name = resolved.kind === "method" || resolved.kind === "inactive" ? resolved.method.name : null
      const issue = classifyOrderError(error, state, catalog, name)
      // The method was deactivated or removed meanwhile: re-read the list so the picker shows the truth.
      if (issue.kind === "payment" && issue.field === "payment_method_id") void reloadMethods()
      dispatch({ type: "submitError", issue })
      topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    }
  }

  // Ctrl+Enter (⌘+Enter on macOS) saves when the button would.
  const saveRef = React.useRef(save)
  React.useEffect(() => {
    saveRef.current = save
  })
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        void saveRef.current()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const staleDialog = (
    <Dialog open={staleDay != null} onOpenChange={(o) => !o && setStaleDay(null)}>
      <DialogContent
        showCloseButton={false}
        style={{ maxWidth: "min(440px, calc(100% - 2rem))" }}
        className="w-full gap-0 overflow-hidden rounded-[14px] border border-border bg-card p-0 ring-0 sm:max-w-none"
      >
        <div className="flex flex-col gap-2 px-6 py-5">
          <DialogTitle className="text-base font-bold text-heading">{T.staleTitle}</DialogTitle>
          <DialogDescription className="text-sm text-text-2">
            {staleDay ? T.staleBody(formatJalali(staleDay, "yyyy/MM/dd")) : null}
          </DialogDescription>
        </div>
        <div className="flex justify-start gap-2 border-t border-border bg-surface-2 px-6 py-4">
          <Btn
            variant="primary"
            onClick={() => {
              setStaleDay(null)
              void submit()
            }}
          >
            {T.staleConfirm}
          </Btn>
          <Btn onClick={() => setStaleDay(null)}>{T.staleBack}</Btn>
        </div>
      </DialogContent>
    </Dialog>
  )

  const closeToast = React.useCallback(() => setToast(null), [])
  const toastNode = toast ? <Toast invoice={toast} onClose={closeToast} /> : null

  if (state.result) {
    return (
      <>
        <SuccessView result={state.result} catalog={catalog} onNewSale={onNewSale} mobile={mobile} />
        {toastNode}
      </>
    )
  }

  const cardProps = { state, catalog, dispatch, onChannel, summary: d.summary, mobile, payment }
  const draft = correction ? undefined : toDraft
  const saveProps = {
    status: state.status,
    disabled: d.saveDisabled,
    saving: state.saving,
    onSave: save,
    label: correction ? T.saveCorrection : undefined,
  }
  const serverAlert = <ServerAlert issue={state.serverIssue} onDraft={draft} />

  const form = (
    <div ref={topRef} className={mobile ? "flex scroll-mt-20 flex-col gap-3.5" : "flex min-w-0 grow scroll-mt-20 flex-col gap-5"}>
      {mobile && serverAlert}
      {correction && (
        <CorrectionCard
          invoice={correction.detail.order.invoice_number ?? ""}
          preview={correction.preview}
          state={state}
          dispatch={dispatch}
          mobile={mobile}
        />
      )}
      <Banners banners={d.banners} onDraft={draft} />
      <ChannelCard {...cardProps} />
      <ItemsCard
        lines={d.lines}
        products={catalog.products}
        channel={state.channel}
        itemsNet={d.summary.itemsNet}
        invalidMoney={state.invalidMoney}
        dispatch={dispatch}
        onAddLine={addLine}
        openPicker={openPicker}
        setOpenPicker={setOpenPicker}
        mobile={mobile}
      />
      <ShippingCard {...cardProps} />
      {mobile ? (
        <>
          <InternalCostsCard {...cardProps} />
          <StatusCard {...cardProps} />
        </>
      ) : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <InternalCostsCard {...cardProps} />
          <StatusCard {...cardProps} />
        </div>
      )}
    </div>
  )

  if (mobile) {
    return (
      <div className="pb-[150px]">
        {form}
        <MobileSummarySheet
          summary={d.summary}
          catalog={catalog}
          errors={d.errors}
          serverAlert={<ServerAlert issue={state.serverIssue} onDraft={draft} compact />}
          {...saveProps}
        />
        {toastNode}
        {staleDialog}
      </div>
    )
  }

  return (
    // Side-by-side only where the 5-column line grid still fits next to the
    // 384px summary; narrower desktops stack the summary under the form.
    <div className="flex flex-col items-stretch gap-6 min-[1360px]:flex-row min-[1360px]:items-start">
      {form}
      <SummaryPanel
        summary={d.summary}
        channel={state.channel}
        catalog={catalog}
        errors={d.errors}
        serverAlert={serverAlert}
        onCancel={cancel}
        {...saveProps}
      />
      {toastNode}
      {staleDialog}
    </div>
  )
}
