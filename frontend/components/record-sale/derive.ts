/**
 * Pure derivations from form state: per-line view data, the validation rules
 * (design §4 V1–V5, plus V6 and the made-to-order rules) and the summary
 * preview (design/logic/formulas.md §1).
 *
 * Everything here is a PREVIEW and a pre-check. POST /orders is the
 * authority: the saved order's numbers come from its response, and its
 * errors are shown as returned (see classifyOrderError in record-sale.tsx).
 */

import type { Catalog } from "@/lib/api"
import { categoryPath } from "@/lib/category-path"
import { formatNumber, formatQuantity } from "@/lib/persian-numbers"
import { CHANNELS, T } from "./copy"
import { channelPrice, defaultShipping, moneyBlocked, orderTotal, type FormState, type Kit, type Line, type Product, type ResolvedMethod } from "./state"
import type { FeePreview } from "./use-fee-preview"

export type RecipeState =
  | { status: "loading" }
  | { status: "ok"; unitCost: number }
  | { status: "missing" }
  /** Couldn't check (network/server). Not a block: the API decides. */
  | { status: "failed" }

export type Severity = "error" | "warn"

export type LineMessage = {
  severity: Severity
  text: string
  /** Offer «تعداد را N کن». */
  useMax?: number
  /** Offer «ذخیره به‌عنوان پیش‌نویس». */
  toDraft?: boolean
  icon: "alert" | "info" | "lock"
}

export type LineView = {
  line: Line
  index: number
  product: Product | null
  madeToOrder: boolean
  recipe: RecipeState | null
  gross: number
  net: number
  /** The channel's price for this product (for the manual-price note). */
  defaultPrice: number
  /** Help under the product select. */
  meta: string
  stockPill: { text: string; tone: "neutral" | "out" } | null
  selectError: boolean
  qtyTone: "error" | "warn" | null
  discountError: boolean
  messages: LineMessage[]
}

export type Banner =
  | { kind: "noCost"; severity: Severity; name: string }
  | { kind: "noRecipe"; severity: Severity; name: string }

export type Derived = {
  lines: LineView[]
  errors: string[]
  banners: Banner[]
  /** A made-to-order recipe check is still in flight. */
  pending: boolean
  saveDisabled: boolean
  summary: Summary
}

export type Summary = {
  qtyTotal: number
  itemsGross: number
  discount: number
  itemsNet: number
  shipping: number
  shippingDefault: number
  shippingOverridden: boolean
  total: number
  cost: number | null
  kitName: string
  kitCost: number
  postageOn: boolean
  postage: number
  /** The fee the order will carry: the API's preview (auto), the typed fee (manual / no method), or null while the preview is pending. */
  fee: number | null
  /** "auto" = computed by the backend for the chosen method; "manual" = typed override; "none" = no method (typed, as before). */
  feeSource: "auto" | "manual" | "none"
  profit: number | null
  marginPct: number | null
  shipCost: number
  shipResult: number
  showShipEcon: boolean
}

/** The kit the order will actually use: explicit choice, else channel default. */
export function resolveKit(state: FormState, catalog: Catalog): Kit | null {
  if (state.kit.kind === "none") return null
  const id =
    state.kit.kind === "kit"
      ? state.kit.id
      : catalog.settings.channels[state.channel]?.default_packaging_kit_id ?? null
  return id == null ? null : catalog.kits.find((k) => k.id === id) ?? null
}

// Kept in state.ts (no imports) so lib tests and the verification script use the same code.
export { defaultShipping, orderTotal } from "./state"

/** What the screen knows about the order's payment method and its fee. */
export type PaymentView = { resolved: ResolvedMethod; preview: FeePreview }

export function derive(
  state: FormState,
  catalog: Catalog,
  products: Map<number, Product>,
  recipes: Record<number, RecipeState>,
  payment: PaymentView
): Derived {
  const blocking = state.status !== "DRAFT"
  const sev: Severity = blocking ? "error" : "warn"
  const issue = state.serverIssue
  const errors: string[] = []
  const banners: Banner[] = []
  let pending = false
  let itemsGross = 0
  let discount = 0
  let qtyTotal = 0
  let cost = 0
  let costKnown = true

  const lines: LineView[] = state.lines.map((line, i) => {
    const index = i + 1
    const product = line.productId == null ? null : products.get(line.productId) ?? null
    const madeToOrder = !!product?.made_to_order
    const recipe = product && madeToOrder ? recipes[product.id] ?? { status: "loading" } : null
    const gross = line.qty * line.unitPrice
    const lineDiscount = line.discountOpen ? line.discount : 0
    const messages: LineMessage[] = []
    let selectError = false
    let qtyTone: LineView["qtyTone"] = null

    itemsGross += gross
    discount += lineDiscount
    qtyTotal += line.qty

    // V1 — summary list only.
    if (!product) errors.push(T.v1(index))

    // V6 — the API rejects quantity <= 0.
    if (line.qty < 1) {
      qtyTone = "error"
      messages.push({ severity: "error", text: T.v6, icon: "alert" })
      errors.push(T.v6)
    }

    let meta: string = T.pickProductHelp
    let stockPill: LineView["stockPill"] = null

    if (product) {
      const stock = product.current_stock
      if (madeToOrder) {
        // §13: made-to-order is manufactured at sale — never blocked for
        // stock, and not for a missing cost, unless it has no recipe at all.
        meta = `${categoryPath(product)} · ${T.madeToOrder}`
        if (recipe?.status === "loading") {
          pending = true
          meta += ` · ${T.recipeChecking}`
        } else if (recipe?.status === "ok") {
          meta += ` · ${T.estimatedCost(recipe.unitCost)}`
        }
        // With no finished units the help line already says «ساخت هنگام فروش».
        stockPill = stock === 0 ? null : { text: T.stockPill(stock), tone: "neutral" }

        if (recipe?.status === "missing") {
          selectError = blocking
          banners.push({ kind: "noRecipe", severity: sev, name: product.name })
          messages.push(
            blocking
              ? { severity: "error", text: T.noRecipe(product.name), icon: "lock" }
              : { severity: "warn", text: T.noRecipeDraft(product.name), icon: "info" }
          )
          if (blocking) errors.push(T.noRecipeSummary(product.name))
        }
        // V3-MTO-stock: finished units are sold first; selling any of them
        // with no unit_cost is refused by the API (field "unit_cost").
        if (stock > 0 && product.unit_cost == null) {
          pushNoCost(product)
        }

        // Cost preview: finished units at unit_cost, the rest from the recipe.
        const fromStock = Math.min(stock, Math.max(line.qty, 0))
        const toMake = Math.max(line.qty, 0) - fromStock
        if (fromStock > 0) {
          if (product.unit_cost == null) costKnown = false
          else cost += fromStock * product.unit_cost
        }
        if (toMake > 0) {
          if (recipe?.status === "ok") cost += toMake * recipe.unitCost
          else costKnown = false
        }
      } else {
        meta = categoryPath(product)
        stockPill = stock === 0 ? { text: T.outOfStock, tone: "out" } : { text: T.stockPill(stock), tone: "neutral" }

        // V2
        if (line.qty > stock) {
          qtyTone = qtyTone ?? (blocking ? "error" : "warn")
          if (blocking) {
            selectError = true
            messages.push(
              stock === 0
                ? { severity: "error", text: T.v2BlockingZero(product.name), toDraft: true, icon: "alert" }
                : {
                    severity: "error",
                    text: T.v2Blocking(`${formatNumber(stock)} عدد`, product.name),
                    useMax: stock,
                    toDraft: true,
                    icon: "alert",
                  }
            )
            errors.push(T.v2Summary(product.name))
          } else {
            messages.push({ severity: "warn", text: T.v2Draft(product.name, stock), icon: "info" })
          }
        }
        // V3
        if (product.unit_cost == null) pushNoCost(product)

        if (product.unit_cost == null) costKnown = false
        else cost += Math.max(line.qty, 0) * product.unit_cost
      }

      // What the API said about this product on the last submit.
      if (issue?.kind === "stock" && issue.productId === product.id && !messages.some((m) => m.useMax !== undefined || m.text === T.v2BlockingZero(product.name))) {
        selectError = true
        qtyTone = "error"
        messages.push(
          issue.available <= 0
            ? { severity: "error", text: T.v2BlockingZero(product.name), toDraft: true, icon: "alert" }
            : {
                severity: "error",
                text: T.v2Blocking(`${formatQuantity(issue.available)} عدد`, product.name),
                useMax: Number.isInteger(issue.available) ? issue.available : undefined,
                toDraft: true,
                icon: "alert",
              }
        )
      }
      if (issue?.kind === "noCost" && issue.productId === product.id && !banners.some((b) => b.kind === "noCost" && b.name === product.name)) {
        pushNoCost(product, true)
      }
      if (issue?.kind === "noRecipe" && issue.productId === product.id && !banners.some((b) => b.kind === "noRecipe" && b.name === product.name)) {
        selectError = true
        banners.push({ kind: "noRecipe", severity: "error", name: product.name })
        messages.push({ severity: "error", text: T.noRecipe(product.name), icon: "lock" })
      }
    }

    // V4
    const discountError = lineDiscount > gross && gross > 0
    if (discountError) {
      messages.push({ severity: "error", text: T.v4(lineDiscount, gross), icon: "alert" })
      errors.push(T.v4Summary(product?.name ?? ""))
    }

    return {
      line,
      index,
      product,
      madeToOrder,
      recipe,
      gross,
      net: gross - lineDiscount,
      defaultPrice: product ? channelPrice(product, state.channel) : 0,
      meta,
      stockPill,
      selectError,
      qtyTone,
      discountError,
      messages,
    }

    function pushNoCost(p: Product, fromServer = false) {
      const sevHere: Severity = fromServer ? "error" : sev
      banners.push({ kind: "noCost", severity: sevHere, name: p.name })
      if (sevHere === "error") {
        selectError = true
        messages.push({ severity: "error", text: T.v3Inline, icon: "lock" })
        if (!fromServer) errors.push(T.v3Summary(p.name))
      } else {
        messages.push({ severity: "warn", text: T.v3DraftInline, icon: "info" })
      }
    }
  })

  // V5
  if (state.lines.length === 0) errors.push(T.v5)
  // A typed amount that isn't exact Toman (MoneyInput shows why on the field).
  if (moneyBlocked(state)) errors.push(T.vMoney)
  // A payment method the API would refuse, or one we couldn't load: never sent as "no method".
  const resolved = payment.resolved
  if (resolved.kind === "inactive") errors.push(T.vMethodInactive(resolved.method.name))
  if (resolved.kind === "unavailable") errors.push(T.vMethodUnavailable)

  const ch = catalog.settings.channels[state.channel]
  const shippingDefault = defaultShipping(state, catalog)
  const shipping = state.shipping ?? shippingDefault
  const kit = resolveKit(state, catalog)
  const kitCost = kit?.kit_cost ?? 0
  const postageOn = !!ch?.applies_postage
  const postage = postageOn ? catalog.postage_estimate : 0
  const itemsNet = itemsGross - discount
  // The same function the fee preview is asked with (and that the backend's customer_total matches).
  const total = orderTotal(state, catalog)
  const feeSource: Summary["feeSource"] =
    resolved.kind !== "method" ? "none" : state.feeMode === "manual" ? "manual" : "auto"
  const fee =
    feeSource !== "auto" ? state.fee : payment.preview.status === "ready" ? payment.preview.fee : null
  // A preview mirroring the backend's profit formula; unknown until the fee is.
  const profit = costKnown && fee !== null ? total - cost - kitCost - postage - fee : null
  const shipCost = kitCost + postage

  return {
    lines,
    errors,
    banners,
    pending,
    saveDisabled: errors.length > 0 || pending,
    summary: {
      qtyTotal,
      itemsGross,
      discount,
      itemsNet,
      shipping,
      shippingDefault,
      shippingOverridden: state.shipping != null && state.shipping !== shippingDefault,
      total,
      cost: costKnown ? cost : null,
      kitName: kit?.name ?? T.noKit,
      kitCost,
      postageOn,
      postage,
      fee,
      feeSource,
      profit,
      marginPct: profit == null || !total ? null : Math.round((profit / total) * 100),
      shipCost,
      shipResult: shipping - shipCost,
      showShipEcon: shipping > 0 || postage > 0,
    },
  }
}

/** «وب‌سایت: ارسال ۱۸۰٬۰۰۰ · با هزینه پست · جعبه استاندارد» (mobile). */
export function channelSummaryLine(state: FormState, catalog: Catalog): string {
  const ch = catalog.settings.channels[state.channel]
  const meta = CHANNELS[state.channel]
  const ship = ch?.applies_shipping_charge
    ? T.tileShip(catalog.settings.default_shipping_charge)
    : meta.noShipTile
  const post = ch?.applies_postage ? T.tilePostOn : T.tilePostOff
  const kitId = ch?.default_packaging_kit_id ?? null
  const kit = kitId == null ? null : catalog.kits.find((k) => k.id === kitId)
  return `${meta.name}: ${ship} · ${post} · ${kit?.name ?? T.noKit}`
}
