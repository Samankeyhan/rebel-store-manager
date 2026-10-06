"use client"

import * as React from "react"
import { useIsMobile } from "@/hooks/use-mobile"
import { ApiError, createOrder, getCatalog, listPaymentMethods, type Catalog, type PaymentMethod } from "@/lib/api"
import { classifyPaymentError } from "@/lib/payment-methods"
import { DEFAULT_TZ, storeToday } from "@/lib/store-day"
import { paymentErrorText } from "@/components/payment-methods/copy"
import { T, type Channel } from "./copy"
import { derive, orderTotal } from "./derive"
import type { PaymentUi } from "./payment-fields"
import { useFeePreview } from "./use-fee-preview"
import { ChannelCard, InternalCostsCard, ShippingCard, StatusCard } from "./form-cards"
import { ItemsCard } from "./items-card"
import { MobileSummarySheet, SummaryPanel } from "./summary-panel"
import {
  buildOrderBody,
  initialState,
  moneyBlocked,
  productMap,
  reducer,
  resolveMethod,
  type FormState,
  type ServerIssue,
} from "./state"
import { useRecipes } from "./use-recipes"
import { Banners, EmptyView, LoadErrorView, LoadingView, ServerAlert, SuccessView, Toast } from "./views"
import { useCurrency } from "@/lib/use-currency"

type Load =
  | { status: "loading" }
  | { status: "error"; code: string }
  /** methods: every payment method (inactive included), or null when that request failed. */
  | { status: "ready"; catalog: Catalog; methods: PaymentMethod[] | null }

function loadErrorCode(error: unknown): string {
  if (error instanceof ApiError && error.status > 0) return `CATALOG_${error.status}`
  return "NET_TIMEOUT"
}

/** Finds which of this order's products a backend message is about. */
function productNamed(message: string, state: FormState, catalog: Catalog) {
  const ids = new Set(state.lines.map((l) => l.productId))
  return catalog.products
    .filter((p) => ids.has(p.id) && message.includes(p.name))
    .sort((a, b) => b.name.length - a.name.length)[0]
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
  // Payment errors go next to their field, in Persian (closed month, future paid date, inactive method…).
  const payment = classifyPaymentError(error)
  if (payment) {
    const field =
      payment.kind === "inactiveMethod" ? "payment_method_id" : "paid_date"
    return { kind: "payment", field, message: paymentErrorText(payment, methodName) }
  }
  if (error.status === 404 && /Payment method/.test(error.message)) {
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
    const product = productNamed(error.message, state, catalog)
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

  React.useEffect(() => {
    let cancelled = false
    // The methods list failing doesn't stop a sale: resolveMethod blocks only
    // when the channel has a default method (see PaymentMethodField's retry).
    Promise.all([getCatalog(), listPaymentMethods(true).catch(() => null)]).then(
      ([catalog, methods]) => !cancelled && setLoad({ status: "ready", catalog, methods }),
      (error: unknown) => !cancelled && setLoad({ status: "error", code: loadErrorCode(error) })
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const reload = React.useCallback(() => {
    setLoad({ status: "loading" })
    setAttempt((a) => a + 1)
  }, [])

  if (load.status === "loading") return <LoadingView mobile={mobile} />
  if (load.status === "error") return <LoadErrorView code={load.code} onRetry={reload} mobile={mobile} />
  if (load.catalog.products.length === 0) return <EmptyView mobile={mobile} />
  return <SaleForm catalog={load.catalog} initialMethods={load.methods} mobile={mobile} onNewSale={reload} />
}

const currentStoreDay = (timeZone: string) => storeToday(new Date(), timeZone)

function SaleForm({
  catalog,
  initialMethods,
  mobile,
  onNewSale,
}: {
  catalog: Catalog
  initialMethods: PaymentMethod[] | null
  mobile: boolean
  /** Refetches the catalog so the next sale sees fresh stock and costs. */
  onNewSale: () => void
}) {
  const [state, dispatch] = React.useReducer(reducer, undefined, () => initialState(nextLineKey()))
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
    setOpenPicker(null)
    dispatch({ type: "reset", firstLineKey: nextLineKey() })
  }

  // Never once saved: the success screen keeps this component mounted.
  const canSave = !d.saveDisabled && !state.saving && !state.result
  const save = async () => {
    if (!canSave) return
    dispatch({ type: "submitStart" })
    try {
      // Read the store's day now: a session can cross midnight.
      const result = await createOrder(buildOrderBody(state, resolved, currentStoreDay(timeZone)))
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
  const saveProps = { status: state.status, disabled: d.saveDisabled, saving: state.saving, onSave: save }
  const serverAlert = <ServerAlert issue={state.serverIssue} onDraft={toDraft} />

  const form = (
    <div ref={topRef} className={mobile ? "flex scroll-mt-20 flex-col gap-3.5" : "flex min-w-0 grow scroll-mt-20 flex-col gap-5"}>
      {mobile && serverAlert}
      <Banners banners={d.banners} onDraft={toDraft} />
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
          serverAlert={<ServerAlert issue={state.serverIssue} onDraft={toDraft} compact />}
          {...saveProps}
        />
        {toastNode}
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
    </div>
  )
}
