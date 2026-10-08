/**
 * Form state for the record-sale screen: one reducer, plus the mapping from
 * that state to the POST /orders body (api/schemas/orders.py OrderCreate).
 */

import type { Catalog, OrderCreate, OrderDetail, PaymentMethod, Schemas } from "@/lib/api"
import type { Channel, SaleStatus } from "./copy"

export type Product = Schemas["ProductOut"]
export type Kit = Schemas["KitDetailOut"]

export type Line = {
  key: number
  productId: number | null
  qty: number
  unitPrice: number
  /** A typed price survives channel changes. */
  priceEdited: boolean
  discountOpen: boolean
  discount: number
  discountReason: string
}

/** "default" = let the channel decide; "none" = «بدون بسته‌بندی». */
export type KitChoice = { kind: "default" } | { kind: "none" } | { kind: "kit"; id: number }

/** "default" = the channel's default payment method; "none" = «بدون روش». */
export type PaymentChoice = { kind: "default" } | { kind: "none" } | { kind: "method"; id: number }

/**
 * The payment method the order will use, resolved from the choice, the
 * channel default and the methods list (see resolveMethod). Only "none" and
 * "method" can be submitted; the others block saving with a message.
 */
export type ResolvedMethod =
  | { kind: "none" }
  | { kind: "method"; method: PaymentMethod }
  /** The method (chosen or the channel default) is inactive: the API would refuse it. */
  | { kind: "inactive"; method: PaymentMethod; isDefault: boolean }
  /** The methods couldn't be loaded (or the id isn't listed) but the order needs one: retry, never send null. */
  | { kind: "unavailable"; id: number }

const PAID = ["PAID", "COMPLETED"]

/** What POST /orders rejected, classified so the UI can place it. */
export type ServerIssue =
  | {
      kind: "stock"
      itemName: string
      needed: number
      available: number
      /** Set when item_name is one of this order's products. */
      productId: number | null
      /** Material unit, when item_name is a material. */
      unit: string | null
    }
  | { kind: "noCost"; productId: number; name: string }
  | { kind: "noRecipe"; productId: number; name: string }
  | { kind: "generic"; message: string; code: string }
  /** A payment error the screen places next to its field (closed month, future paid date, inactive method…). */
  | { kind: "payment"; field: "paid_date" | "payment_method_id" | "transaction_fee"; message: string }

/**
 * A money field whose typed text gives no exact Rial amount (MoneyInput
 * reported null and shows why: two Toman decimals, a Rial decimal, a minus
 * sign, too large). Its last exact value stays in the
 * form; the field id is listed here, and while any is, nothing is submitted.
 */
export type MoneyField = `price:${number}` | `discount:${number}` | "shipping" | "fee"

export const priceField = (key: number): MoneyField => `price:${key}`
export const discountField = (key: number): MoneyField => `discount:${key}`

export type FormState = {
  channel: Channel
  customerName: string
  lines: Line[]
  /** null = the channel's default shipping charge. 0 is a real override. */
  shipping: number | null
  kit: KitChoice
  payment: PaymentChoice
  /**
   * "auto": a payment method is resolved and the backend computes the fee
   * (transaction_fee: null). "manual": the owner typed the fee (`fee`).
   * Without a method the typed `fee` is always sent, as before.
   */
  feeMode: "auto" | "manual"
  /** The typed fee: a manual override, or the fee of an order with no method. */
  fee: number
  /** Receipt / tracking number (optional). */
  reference: string
  /**
   * When the order is recorded. null = now. This screen has no order-date
   * field yet, so it stays null here; the body builder still handles a
   * backdated order correctly (paid_date follows it).
   */
  orderDate: string | null
  /** The picked payment day; null = the order's own day (what the server stores by default). */
  paidDate: string | null
  invalidMoney: MoneyField[]
  status: SaleStatus
  saving: boolean
  serverIssue: ServerIssue | null
  result: OrderDetail | null
}

export function emptyLine(key: number): Line {
  return {
    key,
    productId: null,
    qty: 1,
    unitPrice: 0,
    priceEdited: false,
    discountOpen: false,
    discount: 0,
    discountReason: "",
  }
}

export function initialState(firstLineKey: number): FormState {
  return {
    channel: "WEBSITE",
    customerName: "",
    lines: [emptyLine(firstLineKey)],
    shipping: null,
    kit: { kind: "default" },
    payment: { kind: "default" },
    feeMode: "auto",
    fee: 0,
    reference: "",
    orderDate: null,
    paidDate: null,
    invalidMoney: [],
    status: "COMPLETED",
    saving: false,
    serverIssue: null,
    result: null,
  }
}

/** The channel's default shipping charge (0 when the channel doesn't charge shipping). */
export function defaultShipping(state: FormState, catalog: Catalog): number {
  const ch = catalog.settings.channels[state.channel]
  return ch?.applies_shipping_charge ? catalog.settings.default_shipping_charge : 0
}

/**
 * The order's customer total — items after discount + shipping (the backend's
 * customer_total, section 7 revenue). The fee preview is asked for exactly
 * this amount, and the summary's total is the same figure.
 */
export function orderTotal(state: FormState, catalog: Catalog): number {
  const itemsNet = state.lines.reduce(
    (sum, l) => sum + l.qty * l.unitPrice - (l.discountOpen ? l.discount : 0),
    0
  )
  return itemsNet + (state.shipping ?? defaultShipping(state, catalog))
}

/** WHOLESALE sells at wholesale_price; every other channel at retail_price. */
export function channelPrice(product: Product, channel: Channel): number {
  return channel === "WHOLESALE" ? product.wholesale_price : product.retail_price
}

type LinePatch = Partial<Omit<Line, "key">>

export type Action =
  | { type: "channel"; channel: Channel; products: Map<number, Product> }
  | { type: "customer"; value: string }
  | { type: "pickProduct"; key: number; product: Product }
  | { type: "line"; key: number; patch: LinePatch }
  | { type: "price"; key: number; value: number }
  | { type: "addLine"; key: number }
  | { type: "removeLine"; key: number }
  | { type: "shipping"; value: number | null }
  | { type: "kit"; choice: KitChoice }
  | { type: "fee"; value: number }
  | { type: "payment"; choice: PaymentChoice }
  /** Switching to manual starts from the fee the API computed (`fee`), so the owner edits, not retypes. */
  | { type: "feeMode"; mode: "auto" | "manual"; fee?: number }
  | { type: "reference"; value: string }
  | { type: "paidDate"; value: string | null }
  | { type: "moneyInvalid"; field: MoneyField; invalid: boolean }
  | { type: "status"; status: SaleStatus }
  | { type: "submitStart" }
  | { type: "submitError"; issue: ServerIssue }
  | { type: "submitSuccess"; result: OrderDetail }
  | { type: "reset"; firstLineKey: number }

function edit(state: FormState, patch: Partial<FormState>): FormState {
  // Any edit invalidates what the server said about the previous submission.
  return { ...state, ...patch, serverIssue: null }
}

function withoutFields(invalid: MoneyField[], drop: (f: MoneyField) => boolean): MoneyField[] {
  const kept = invalid.filter((f) => !drop(f))
  return kept.length === invalid.length ? invalid : kept
}

/** True while a money field holds text that gives no exact Rial amount: the order can't be submitted. */
export function moneyBlocked(state: FormState): boolean {
  return state.invalidMoney.length > 0
}

function patchLine(lines: Line[], key: number, patch: LinePatch): Line[] {
  return lines.map((l) => (l.key === key ? { ...l, ...patch } : l))
}

export function reducer(state: FormState, action: Action): FormState {
  switch (action.type) {
    case "channel":
      // §5: shipping and kit fall back to the new channel's defaults, and
      // every line whose price wasn't typed by hand is re-priced.
      const repriced = new Set<MoneyField>()
      const lines = state.lines.map((l) => {
        const p = l.productId == null ? undefined : action.products.get(l.productId)
        if (!p || l.priceEdited) return l
        repriced.add(priceField(l.key))
        return { ...l, unitPrice: channelPrice(p, action.channel) }
      })
      return edit(state, {
        channel: action.channel,
        shipping: null,
        kit: { kind: "default" },
        // The new channel's default method, with its fee computed again.
        payment: { kind: "default" },
        feeMode: "auto",
        lines,
        // Shipping and re-priced lines got fresh exact values.
        invalidMoney: withoutFields(state.invalidMoney, (f) => f === "shipping" || repriced.has(f)),
      })
    case "customer":
      return edit(state, { customerName: action.value })
    case "pickProduct":
      return edit(state, {
        lines: patchLine(state.lines, action.key, {
          productId: action.product.id,
          unitPrice: channelPrice(action.product, state.channel),
          priceEdited: false,
        }),
        invalidMoney: withoutFields(state.invalidMoney, (f) => f === priceField(action.key)),
      })
    case "line":
      return edit(state, {
        lines: patchLine(state.lines, action.key, action.patch),
        // Closing the discount drops whatever was typed in it.
        invalidMoney:
          action.patch.discountOpen === false
            ? withoutFields(state.invalidMoney, (f) => f === discountField(action.key))
            : state.invalidMoney,
      })
    case "price":
      return edit(state, {
        lines: patchLine(state.lines, action.key, { unitPrice: action.value, priceEdited: true }),
      })
    case "addLine":
      return edit(state, { lines: [...state.lines, emptyLine(action.key)] })
    case "removeLine":
      return edit(state, {
        lines: state.lines.filter((l) => l.key !== action.key),
        invalidMoney: withoutFields(state.invalidMoney, (f) => f === priceField(action.key) || f === discountField(action.key)),
      })
    case "shipping":
      return edit(state, { shipping: action.value })
    case "kit":
      return edit(state, { kit: action.choice })
    case "fee":
      return edit(state, { fee: action.value })
    case "payment":
      // Another method: its own fee, computed again (a manual override was for the old one).
      return edit(state, {
        payment: action.choice,
        feeMode: "auto",
        invalidMoney: withoutFields(state.invalidMoney, (f) => f === "fee"),
      })
    case "feeMode":
      return edit(state, {
        feeMode: action.mode,
        fee: action.fee ?? state.fee,
        // Back to automatic drops whatever was typed in the manual field.
        invalidMoney: action.mode === "auto" ? withoutFields(state.invalidMoney, (f) => f === "fee") : state.invalidMoney,
      })
    case "reference":
      return edit(state, { reference: action.value })
    case "paidDate":
      return edit(state, { paidDate: action.value })
    case "moneyInvalid": {
      const has = state.invalidMoney.includes(action.field)
      if (has === action.invalid) return state
      return edit(state, {
        invalidMoney: action.invalid ? [...state.invalidMoney, action.field] : withoutFields(state.invalidMoney, (f) => f === action.field),
      })
    }
    case "status":
      // DRAFT and PENDING aren't paid: no payment day.
      return edit(state, { status: action.status, paidDate: PAID.includes(action.status) ? state.paidDate : null })
    case "submitStart":
      return { ...state, saving: true, serverIssue: null }
    case "submitError":
      return { ...state, saving: false, serverIssue: action.issue }
    case "submitSuccess":
      return { ...state, saving: false, result: action.result }
    case "reset":
      return initialState(action.firstLineKey)
  }
}

/**
 * The method the order will use. An explicit choice wins; "default" is the
 * channel's default_payment_method_id (none if unset). `methods` is every
 * method, inactive ones included, or null when the list couldn't be loaded.
 */
export function resolveMethod(
  choice: PaymentChoice,
  channelDefaultId: number | null,
  methods: PaymentMethod[] | null
): ResolvedMethod {
  const id = choice.kind === "method" ? choice.id : choice.kind === "default" ? channelDefaultId : null
  if (id == null) return { kind: "none" }
  const method = methods?.find((m) => m.id === id)
  if (!method) return { kind: "unavailable", id }
  if (method.is_active !== 1) return { kind: "inactive", method, isDefault: choice.kind === "default" }
  return { kind: "method", method }
}

/** The order's own local day: its order date, or today (the store's day, see buildOrderBody). */
export const orderDay = (state: FormState, today: string): string => state.orderDate ?? today

/** The payment day the form shows and the server will store: the picked day, else the order's day. */
export const paidDay = (state: FormState, today: string): string => state.paidDate ?? orderDay(state, today)

/**
 * paid_date for the body: only for PAID / COMPLETED. Omitted only when the
 * order is dated today and paid today — then the server's default (the
 * order's local day = today) is exactly what the form showed; otherwise the
 * shown day is sent explicitly, so what is stored always equals what was shown.
 */
export function paidDateForBody(state: FormState, today: string): string | undefined {
  if (!PAID.includes(state.status)) return undefined
  const day = paidDay(state, today)
  return day === today && orderDay(state, today) === today ? undefined : day
}

/**
 * The POST /orders body. `resolved` is resolveMethod's answer (only "none"
 * or "method" can be submitted). `today` is the STORE's calendar day
 * ("YYYY-MM-DD" in settings.timezone, lib/store-day.ts storeToday — the zone
 * the backend's today_local uses), read at submit time, never the browser's
 * local day. Notes are omitted.
 */
export function buildOrderBody(state: FormState, resolved: ResolvedMethod, today: string): OrderCreate {
  // derive() already disables saving; this is the last line of defence.
  if (moneyBlocked(state)) throw new Error("An amount isn't exact; the order can't be submitted.")
  if (resolved.kind !== "none" && resolved.kind !== "method") {
    throw new Error("The payment method can't be used; the order can't be submitted.")
  }
  const method = resolved.kind === "method" ? resolved.method : null
  const reference = state.reference.trim()
  const paid = paidDateForBody(state, today)
  const customer = state.customerName.trim()
  return {
    channel: state.channel,
    items: state.lines.map((l) => {
      const reason = l.discountReason.trim()
      return {
        product_id: l.productId as number,
        quantity: l.qty,
        unit_price: l.unitPrice,
        discount_amount: l.discountOpen ? l.discount : 0,
        discount_reason: l.discountOpen && reason ? reason : null,
      }
    }),
    customer_name: customer || null,
    // null = channel default; a number (including 0) is an override.
    shipping_charge: state.shipping,
    packaging_kit_id:
      state.kit.kind === "default" ? "default" : state.kit.kind === "none" ? null : state.kit.id,
    // No actual-postage entry on this screen: always the channel default.
    postage_cost: null,
    // The resolved method, explicitly (the same one the fee preview used); null = no method.
    payment_method_id: method ? method.id : null,
    // null = the backend computes the fee from the method; an integer (0 too) is an override.
    transaction_fee: method && state.feeMode === "auto" ? null : state.fee,
    payment_reference: reference || null,
    status: state.status,
    ...(state.orderDate ? { order_date: state.orderDate } : {}),
    ...(paid ? { paid_date: paid } : {}),
  }
}

export function productMap(catalog: Catalog): Map<number, Product> {
  return new Map(catalog.products.map((p) => [p.id, p]))
}
