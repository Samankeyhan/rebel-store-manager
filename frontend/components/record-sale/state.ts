/**
 * Form state for the record-sale screen: one reducer, plus the mapping from
 * that state to the POST /orders body (api/schemas/orders.py OrderCreate).
 */

import type { Catalog, OrderCreate, OrderDetail, Schemas } from "@/lib/api"
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

export type FormState = {
  channel: Channel
  customerName: string
  lines: Line[]
  /** null = the channel's default shipping charge. 0 is a real override. */
  shipping: number | null
  kit: KitChoice
  fee: number
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
    fee: 0,
    status: "COMPLETED",
    saving: false,
    serverIssue: null,
    result: null,
  }
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
  | { type: "status"; status: SaleStatus }
  | { type: "submitStart" }
  | { type: "submitError"; issue: ServerIssue }
  | { type: "submitSuccess"; result: OrderDetail }
  | { type: "reset"; firstLineKey: number }

function edit(state: FormState, patch: Partial<FormState>): FormState {
  // Any edit invalidates what the server said about the previous submission.
  return { ...state, ...patch, serverIssue: null }
}

function patchLine(lines: Line[], key: number, patch: LinePatch): Line[] {
  return lines.map((l) => (l.key === key ? { ...l, ...patch } : l))
}

export function reducer(state: FormState, action: Action): FormState {
  switch (action.type) {
    case "channel":
      // §5: shipping and kit fall back to the new channel's defaults, and
      // every line whose price wasn't typed by hand is re-priced.
      return edit(state, {
        channel: action.channel,
        shipping: null,
        kit: { kind: "default" },
        lines: state.lines.map((l) => {
          const p = l.productId == null ? undefined : action.products.get(l.productId)
          return p && !l.priceEdited ? { ...l, unitPrice: channelPrice(p, action.channel) } : l
        }),
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
      })
    case "line":
      return edit(state, { lines: patchLine(state.lines, action.key, action.patch) })
    case "price":
      return edit(state, {
        lines: patchLine(state.lines, action.key, { unitPrice: action.value, priceEdited: true }),
      })
    case "addLine":
      return edit(state, { lines: [...state.lines, emptyLine(action.key)] })
    case "removeLine":
      return edit(state, { lines: state.lines.filter((l) => l.key !== action.key) })
    case "shipping":
      return edit(state, { shipping: action.value })
    case "kit":
      return edit(state, { kit: action.choice })
    case "fee":
      return edit(state, { fee: action.value })
    case "status":
      return edit(state, { status: action.status })
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

/** The POST /orders body. order_date and notes are omitted (order is dated "now"). */
export function buildOrderBody(state: FormState): OrderCreate {
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
    transaction_fee: state.fee,
    status: state.status,
  }
}

export function productMap(catalog: Catalog): Map<number, Product> {
  return new Map(catalog.products.map((p) => [p.id, p]))
}
