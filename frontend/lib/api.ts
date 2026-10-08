/**
 * Typed client for the FastAPI backend. Types come from lib/api-types.ts,
 * generated from the backend's OpenAPI schema — regenerate with
 * `npm run gen:api` after any api/schemas change; never hand-edit it.
 *
 * The app is a static export, so every call happens in the browser
 * (client components only).
 */

import type { components } from "@/lib/api-types"

export type Schemas = components["schemas"]
export type Catalog = Schemas["CatalogOut"]

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "")

/**
 * A failed API call. `type` is the backend error class (NotFoundError,
 * ValidationError, InsufficientStockError, ConflictError, AppError),
 * "RequestValidationError" for FastAPI's own 422s (bad body shape),
 * or "NetworkError" when the backend couldn't be reached at all.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly type: string,
    readonly field: string | null = null,
    readonly details: Record<string, unknown> = {}
  ) {
    super(message)
    this.name = "ApiError"
  }
}

type AppErrorBody = {
  error: {
    type: string
    message: string
    field: string | null
    details: Record<string, unknown>
  }
}
type FastApiErrorBody = {
  detail: string | { loc: (string | number)[]; msg: string }[]
}

function toApiError(status: number, body: unknown): ApiError {
  if (body && typeof body === "object" && "error" in body) {
    const e = (body as AppErrorBody).error
    return new ApiError(e.message, status, e.type, e.field, e.details)
  }
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as FastApiErrorBody).detail
    if (typeof detail === "string") {
      return new ApiError(detail, status, "HTTPError")
    }
    const first = detail[0]
    // loc is e.g. ["body", "items", 0, "unit_price"]; drop the "body" prefix.
    const field = first ? first.loc.slice(1).join(".") || null : null
    return new ApiError(
      first?.msg ?? "Invalid request",
      status,
      "RequestValidationError",
      field,
      { errors: detail }
    )
  }
  return new ApiError(`HTTP ${status}`, status, "HTTPError")
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError(
      `Backend not reachable at ${API_URL}`,
      0,
      "NetworkError"
    )
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw toApiError(res.status, body)
  }
  return (await res.json()) as T
}

export function getCatalog(): Promise<Catalog> {
  return apiFetch<Catalog>("/catalog")
}

export type OrderCreate = Schemas["OrderCreate"]
export type OrderDetail = Schemas["OrderDetailOut"]
export type Recipe = Schemas["RecipeOut"]

export function createOrder(body: OrderCreate): Promise<OrderDetail> {
  return apiFetch<OrderDetail>("/orders", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function getRecipe(productId: number): Promise<Recipe> {
  return apiFetch<Recipe>(`/products/${productId}/recipe`)
}

/** Direct link to the invoice PDF; the backend sends it as an attachment. */
export function invoicePdfUrl(orderId: number): string {
  return `${API_URL}/orders/${orderId}/invoice.pdf`
}

export type OrderListItem = Schemas["OrderListItemOut"]

export type OrderListParams = {
  channel?: string | null
  status?: string | null
  start_date?: string | null
  end_date?: string | null
  /** Orders paid with this method. */
  payment_method_id?: string | null
  /** "pending": paid, has a method, not yet settled; "settled": in a settlement. */
  settlement_state?: "pending" | "settled" | null
}

export function listOrders(params: OrderListParams = {}): Promise<OrderListItem[]> {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value) qs.set(key, value)
  }
  const query = qs.toString()
  return apiFetch<OrderListItem[]>(`/orders${query ? `?${query}` : ""}`)
}

export function getOrder(orderId: number): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/orders/${orderId}`)
}

/**
 * Forward move only: DRAFT → PENDING/PAID/COMPLETED, PENDING → PAID/COMPLETED,
 * PAID → COMPLETED. `paidDate` only when the order becomes paid (from DRAFT or
 * PENDING); omitted, the server stores today. Any other move with a paid date is a 422.
 */
export function changeOrderStatus(orderId: number, status: string, paidDate?: string | null): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/orders/${orderId}/status`, {
    method: "POST",
    body: JSON.stringify(paidDate ? { status, paid_date: paidDate } : { status }),
  })
}

/**
 * PATCH /orders/{id}/paid-date: move a paid, unsettled order's payment day.
 * 409 if the order is unpaid or settled, or the day falls in a month its
 * method has already settled; 422 (field "paid_date") for a future day.
 */
export function setOrderPaidDate(orderId: number, paidDate: string): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/orders/${orderId}/paid-date`, {
    method: "PATCH",
    body: JSON.stringify({ paid_date: paidDate }),
  })
}

/** Cancel (from DRAFT/PENDING/PAID) or refund (from PAID/COMPLETED). */
export function returnOrder(
  orderId: number,
  status: "CANCELLED" | "REFUNDED",
  reason: string | null
): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/orders/${orderId}/return`, {
    method: "POST",
    body: JSON.stringify({ status, reason }),
  })
}

export type Settings = Schemas["SettingsOut"]

export function getSettings(): Promise<Settings> {
  return apiFetch<Settings>("/settings")
}

/**
 * The global settings the UI edits. `timezone` is a valid backend key too but
 * deliberately left out: changing it re-buckets every stored date (see
 * components/settings/general-card.tsx).
 */
export type GlobalSettingKey = "default_shipping_charge" | "postage_estimate_window" | "default_postage_estimate"

/** PUT /settings/{key}: 422 (field "value") for a negative amount or a window < 1. Returns all settings. */
export function updateSetting(key: GlobalSettingKey, value: number): Promise<Settings> {
  return apiFetch<Settings>(`/settings/${key}`, { method: "PUT", body: JSON.stringify({ value }) })
}

/**
 * PUT /settings/display_currency: "TOMAN" or "RIAL" (422, field "value", for
 * anything else). Display only — every amount stays integer Rial on the wire.
 */
export function updateDisplayCurrency(value: Settings["display_currency"]): Promise<Settings> {
  return apiFetch<Settings>("/settings/display_currency", { method: "PUT", body: JSON.stringify({ value }) })
}

export type Product = Schemas["ProductOut"]
export type Material = Schemas["MaterialOut"]
export type ProductCreate = Schemas["ProductCreate"]
export type MaterialCreate = Schemas["MaterialCreate"]
export type MaterialUpdate = Schemas["MaterialUpdate"]

/** All products, including inactive ones (/catalog only has active). */
export function listProducts(activeOnly = false): Promise<Product[]> {
  return apiFetch<Product[]>(`/products?active_only=${activeOnly}`)
}

export function listMaterials(activeOnly = false): Promise<Material[]> {
  return apiFetch<Material[]>(`/materials?active_only=${activeOnly}`)
}

export function createProduct(body: ProductCreate): Promise<Product> {
  return apiFetch<Product>("/products", { method: "POST", body: JSON.stringify(body) })
}

/** Omitted prices are left unchanged. */
export function updateProductPrices(
  productId: number,
  prices: { retail_price?: number; wholesale_price?: number }
): Promise<Product> {
  return apiFetch<Product>(`/products/${productId}/prices`, {
    method: "PATCH",
    body: JSON.stringify(prices),
  })
}

/** Turning made-to-order on needs a recipe: 422 with field "made_to_order" otherwise. */
export function setMadeToOrder(productId: number, madeToOrder: boolean): Promise<Product> {
  return apiFetch<Product>(`/products/${productId}/made-to-order`, {
    method: "POST",
    body: JSON.stringify({ made_to_order: madeToOrder }),
  })
}

export function deactivateProduct(productId: number): Promise<Product> {
  return apiFetch<Product>(`/products/${productId}/deactivate`, { method: "POST" })
}

export function createMaterial(body: MaterialCreate): Promise<Material> {
  return apiFetch<Material>("/materials", { method: "POST", body: JSON.stringify(body) })
}

/**
 * Only min_stock is editable: omitted = unchanged, null = no minimum. 422 with
 * field "min_stock" for a negative value or a minimum on a SERVICE material.
 */
export function updateMaterial(materialId: number, body: MaterialUpdate): Promise<Material> {
  return apiFetch<Material>(`/materials/${materialId}`, { method: "PATCH", body: JSON.stringify(body) })
}

/**
 * Low-stock materials (backend rule: active STOCK at stock 0, or at or below
 * its own min_stock), most urgent first. Empty when nothing is low.
 */
export function listLowStockMaterials(): Promise<Material[]> {
  return apiFetch<Material[]>("/materials/low-stock")
}

export function deactivateMaterial(materialId: number): Promise<Material> {
  return apiFetch<Material>(`/materials/${materialId}/deactivate`, { method: "POST" })
}

export function reactivateProduct(productId: number): Promise<Product> {
  return apiFetch<Product>(`/products/${productId}/reactivate`, { method: "POST" })
}

export function reactivateMaterial(materialId: number): Promise<Material> {
  return apiFetch<Material>(`/materials/${materialId}/reactivate`, { method: "POST" })
}

export type Category = Schemas["CategoryOut"]
export type CategoryTree = Schemas["CategoryTreeOut"]
export type CategoryKind = "PRODUCT" | "MATERIAL"

/** Top-level categories of one kind, each with its subcategories. */
export function listCategoryTree(kind: CategoryKind, activeOnly = false): Promise<CategoryTree[]> {
  return apiFetch<CategoryTree[]>(`/categories/tree?kind=${kind}&active_only=${activeOnly}`)
}

export type CategoryCreate = Schemas["CategoryCreate"]

/**
 * 409 ConflictError when a sibling (active or not) has the name; 422 with
 * field "name" when blank, field "parent_id" for a parent that is missing,
 * a subcategory, of the other kind, or inactive.
 */
export function createCategory(body: CategoryCreate): Promise<Category> {
  return apiFetch<Category>("/categories", { method: "POST", body: JSON.stringify(body) })
}

/** Same name refusals as createCategory. */
export function renameCategory(categoryId: number, name: string): Promise<Category> {
  return apiFetch<Category>(`/categories/${categoryId}`, { method: "PATCH", body: JSON.stringify({ name }) })
}

/**
 * 409 ConflictError while any product/material (inactive ones too) uses it,
 * or while it has active subcategories. The item count is only in the
 * message; details is empty.
 */
export function deactivateCategory(categoryId: number): Promise<Category> {
  return apiFetch<Category>(`/categories/${categoryId}/deactivate`, { method: "POST" })
}

/** 409 ConflictError for a subcategory whose parent is inactive. */
export function reactivateCategory(categoryId: number): Promise<Category> {
  return apiFetch<Category>(`/categories/${categoryId}/reactivate`, { method: "POST" })
}

/** 422 with field "category_id" if the category isn't assignable (wrong kind, inactive, has subcategories). */
export function setProductCategory(productId: number, categoryId: number): Promise<Product> {
  return apiFetch<Product>(`/products/${productId}/category`, {
    method: "PATCH",
    body: JSON.stringify({ category_id: categoryId }),
  })
}

export function setMaterialCategory(materialId: number, categoryId: number): Promise<Material> {
  return apiFetch<Material>(`/materials/${materialId}/category`, {
    method: "PATCH",
    body: JSON.stringify({ category_id: categoryId }),
  })
}

export function getProduct(productId: number): Promise<Product> {
  return apiFetch<Product>(`/products/${productId}`)
}

export function getMaterial(materialId: number): Promise<Material> {
  return apiFetch<Material>(`/materials/${materialId}`)
}

// ------------------------------------------------------------ production

export type ProductionBatchListItem = Schemas["ProductionBatchListOut"]
export type ProductionBatchDetail = Schemas["ProductionBatchDetailOut"]
export type ProductionCreate = Schemas["ProductionCreate"]

/** Newest first. */
export function listProduction(productId?: number): Promise<ProductionBatchListItem[]> {
  return apiFetch<ProductionBatchListItem[]>(
    productId == null ? "/production" : `/production?product_id=${productId}`
  )
}

export function getProductionBatch(batchId: number): Promise<ProductionBatchDetail> {
  return apiFetch<ProductionBatchDetail>(`/production/${batchId}`)
}

/**
 * Runs a batch. 422 when the product has no recipe; 409
 * (InsufficientStockError: details.item_name / needed / available) when a
 * STOCK material is short.
 */
export function runProduction(body: ProductionCreate): Promise<ProductionBatchDetail> {
  return apiFetch<ProductionBatchDetail>("/production", { method: "POST", body: JSON.stringify(body) })
}

// ------------------------------------------------------------ recipes

export type RecipeItemCreate = Schemas["RecipeItemCreate"]

/** Each recipe write returns the whole updated recipe. 409 if the material is already on it. */
export function addRecipeItem(productId: number, body: RecipeItemCreate): Promise<Recipe> {
  return apiFetch<Recipe>(`/products/${productId}/recipe/items`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function updateRecipeItem(
  productId: number,
  materialId: number,
  body: { quantity_needed: number; cost_basis?: string }
): Promise<Recipe> {
  return apiFetch<Recipe>(`/products/${productId}/recipe/items/${materialId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

export function removeRecipeItem(productId: number, materialId: number): Promise<Recipe> {
  return apiFetch<Recipe>(`/products/${productId}/recipe/items/${materialId}`, { method: "DELETE" })
}

// ------------------------------------------------------------ purchases

export type MaterialPurchase = Schemas["MaterialPurchaseOut"]
export type ProductPurchase = Schemas["ProductPurchaseOut"]
export type MaterialPurchaseCreate = Schemas["MaterialPurchaseCreate"]
export type ProductPurchaseCreate = Schemas["ProductPurchaseCreate"]
export type Supplier = Schemas["SupplierOut"]

export type PurchaseFilters = { supplierId?: number | null; from?: string | null; to?: string | null }

function purchaseQuery(f: PurchaseFilters): string {
  const qs = new URLSearchParams()
  if (f.supplierId != null) qs.set("supplier_id", String(f.supplierId))
  if (f.from) qs.set("start_date", f.from)
  if (f.to) qs.set("end_date", f.to)
  const s = qs.toString()
  return s ? `?${s}` : ""
}

export function listMaterialPurchases(f: PurchaseFilters = {}): Promise<MaterialPurchase[]> {
  return apiFetch<MaterialPurchase[]>(`/purchases/materials${purchaseQuery(f)}`)
}

export function listProductPurchases(f: PurchaseFilters = {}): Promise<ProductPurchase[]> {
  return apiFetch<ProductPurchase[]>(`/purchases/products${purchaseQuery(f)}`)
}

export function getMaterialPurchase(id: number): Promise<MaterialPurchase> {
  return apiFetch<MaterialPurchase>(`/purchases/materials/${id}`)
}

export function getProductPurchase(id: number): Promise<ProductPurchase> {
  return apiFetch<ProductPurchase>(`/purchases/products/${id}`)
}

/**
 * The response is the purchase row only (its own unit_cost), not the item's
 * new weighted average — re-fetch the item for that. A deleted supplier is a 404.
 */
export function createMaterialPurchase(body: MaterialPurchaseCreate): Promise<MaterialPurchase> {
  return apiFetch<MaterialPurchase>("/purchases/materials", { method: "POST", body: JSON.stringify(body) })
}

export function createProductPurchase(body: ProductPurchaseCreate): Promise<ProductPurchase> {
  return apiFetch<ProductPurchase>("/purchases/products", { method: "POST", body: JSON.stringify(body) })
}

export type Adjustment = Schemas["AdjustmentOut"]
export type AdjustmentCreate = Schemas["AdjustmentCreate"]
export type AdjustmentReason = "WASTE" | "ADJUSTMENT"
export type AdjustmentItemType = "PRODUCT" | "MATERIAL"

export type AdjustmentFilters = {
  itemType?: AdjustmentItemType | null
  reason?: AdjustmentReason | null
  from?: string | null
  to?: string | null
}

/** WASTE and ADJUSTMENT movements only, newest first. No item filter server-side. */
export function listAdjustments(f: AdjustmentFilters = {}): Promise<Adjustment[]> {
  const qs = new URLSearchParams()
  if (f.itemType) qs.set("item_type", f.itemType)
  if (f.reason) qs.set("reason", f.reason)
  if (f.from) qs.set("start_date", f.from)
  if (f.to) qs.set("end_date", f.to)
  const s = qs.toString()
  return apiFetch<Adjustment[]>(`/adjustments${s ? `?${s}` : ""}`)
}

/**
 * Returns the movement only — re-fetch the item for its new stock/cost.
 * 409 InsufficientStockError (details.item_name / needed / available) when a
 * decrease would take stock below zero; 422 with field quantity_change
 * (zero, fractional product, non-negative WASTE) or unit_cost (only on a
 * positive ADJUSTMENT); 422 without a field for an inactive item or a
 * SERVICE material; 404 for an unknown item.
 */
export function createAdjustment(body: AdjustmentCreate): Promise<Adjustment> {
  return apiFetch<Adjustment>("/adjustments", { method: "POST", body: JSON.stringify(body) })
}

export function listSuppliers(): Promise<Supplier[]> {
  return apiFetch<Supplier[]>("/suppliers")
}

export type SupplierCreate = Schemas["SupplierCreate"]
export type SupplierUpdate = Schemas["SupplierUpdate"]

/** 422 (field "name") for an empty name. */
export function createSupplier(body: SupplierCreate): Promise<Supplier> {
  return apiFetch<Supplier>("/suppliers", { method: "POST", body: JSON.stringify(body) })
}

/** Only the fields present change; null clears an optional field (name can't be null). */
export function updateSupplier(supplierId: number, body: SupplierUpdate): Promise<Supplier> {
  return apiFetch<Supplier>(`/suppliers/${supplierId}`, { method: "PATCH", body: JSON.stringify(body) })
}

// ------------------------------------------------------------ settings (channels)

export type ChannelSettings = Schemas["ChannelSettingsOut"]

/** Only the fields sent change; default_packaging_kit_id: null clears the default kit. */
export function updateChannelSettings(
  channel: string,
  patch: {
    default_packaging_kit_id?: number | null
    default_payment_method_id?: number | null
    applies_shipping_charge?: number
    applies_postage?: number
  }
): Promise<ChannelSettings> {
  return apiFetch<ChannelSettings>(`/settings/channels/${channel}`, { method: "PATCH", body: JSON.stringify(patch) })
}

// ------------------------------------------------------------ packaging

export type Kit = Schemas["KitOut"]
export type KitDetail = Schemas["KitDetailOut"]

/** Name and status only — cost and items come from getKit. */
export function listKits(activeOnly = false): Promise<Kit[]> {
  return apiFetch<Kit[]>(`/packaging/kits?active_only=${activeOnly}`)
}

export function getKit(kitId: number): Promise<KitDetail> {
  return apiFetch<KitDetail>(`/packaging/kits/${kitId}`)
}

export function createKit(name: string): Promise<KitDetail> {
  return apiFetch<KitDetail>("/packaging/kits", { method: "POST", body: JSON.stringify({ name }) })
}

/** STOCK materials only; 409 if the material is already in the kit. Returns the whole kit. */
export function addKitItem(kitId: number, materialId: number, quantity: number): Promise<KitDetail> {
  return apiFetch<KitDetail>(`/packaging/kits/${kitId}/items`, {
    method: "POST",
    body: JSON.stringify({ material_id: materialId, quantity }),
  })
}

export function updateKitItem(kitId: number, materialId: number, quantity: number): Promise<KitDetail> {
  return apiFetch<KitDetail>(`/packaging/kits/${kitId}/items/${materialId}`, {
    method: "PATCH",
    body: JSON.stringify({ quantity }),
  })
}

export function removeKitItem(kitId: number, materialId: number): Promise<KitDetail> {
  return apiFetch<KitDetail>(`/packaging/kits/${kitId}/items/${materialId}`, { method: "DELETE" })
}

export function deactivateKit(kitId: number): Promise<KitDetail> {
  return apiFetch<KitDetail>(`/packaging/kits/${kitId}/deactivate`, { method: "POST" })
}

export function reactivateKit(kitId: number): Promise<KitDetail> {
  return apiFetch<KitDetail>(`/packaging/kits/${kitId}/reactivate`, { method: "POST" })
}

// ------------------------------------------------------------ postage

export type PostageBatch = Schemas["PostageBatchOut"]
export type PostageEstimate = Schemas["PostageEstimateOut"]
export type PostageBatchCreate = Schemas["PostageBatchCreate"]

/** Newest first: paid_date DESC, id DESC — the same order the estimate uses. */
export function listPostageBatches(): Promise<PostageBatch[]> {
  return apiFetch<PostageBatch[]>("/postage/batches")
}

export function getPostageEstimate(): Promise<PostageEstimate> {
  return apiFetch<PostageEstimate>("/postage/estimate")
}

export function createPostageBatch(body: PostageBatchCreate): Promise<PostageBatch> {
  return apiFetch<PostageBatch>("/postage/batches", { method: "POST", body: JSON.stringify(body) })
}

// ------------------------------------------------------------ expenses

export type Expense = Schemas["ExpenseOut"]
export type ExpenseCreate = Schemas["ExpenseCreate"]
export type ExpenseCategory = Schemas["ExpenseCategoryOut"]
export type ExpenseBreakdown = Schemas["ExpenseBreakdownOut"]

export type ExpenseFilters = { categoryId?: number | null; from?: string | null; to?: string | null }

/** Newest first: expense_date DESC, id DESC. No text search server-side. */
export function listExpenses(f: ExpenseFilters = {}): Promise<Expense[]> {
  const qs = new URLSearchParams()
  if (f.categoryId != null) qs.set("category_id", String(f.categoryId))
  if (f.from) qs.set("start_date", f.from)
  if (f.to) qs.set("end_date", f.to)
  const s = qs.toString()
  return apiFetch<Expense[]>(`/expenses${s ? `?${s}` : ""}`)
}

/**
 * 404 for an unknown category (an inactive one is accepted); 422 with field
 * amount for a negative amount. A zero amount and a future date are accepted.
 */
export function createExpense(body: ExpenseCreate): Promise<Expense> {
  return apiFetch<Expense>("/expenses", { method: "POST", body: JSON.stringify(body) })
}

/** Ordered by name. There is no rename / deactivate / reactivate endpoint. */
export function listExpenseCategories(activeOnly = true): Promise<ExpenseCategory[]> {
  return apiFetch<ExpenseCategory[]>(`/expense-categories?active_only=${activeOnly}`)
}

/** 409 ConflictError when the name exists (active or not); 422 field name when blank. */
export function createExpenseCategory(name: string): Promise<ExpenseCategory> {
  return apiFetch<ExpenseCategory>("/expense-categories", { method: "POST", body: JSON.stringify({ name }) })
}

/** Per-category totals for a range, largest first. No category filter. */
export function getExpenseBreakdown(f: { from?: string | null; to?: string | null } = {}): Promise<ExpenseBreakdown[]> {
  const qs = new URLSearchParams()
  if (f.from) qs.set("start_date", f.from)
  if (f.to) qs.set("end_date", f.to)
  const s = qs.toString()
  return apiFetch<ExpenseBreakdown[]>(`/reports/expenses${s ? `?${s}` : ""}`)
}

// ------------------------------------------------------------ reports

export type ProfitAndLoss = Schemas["ProfitAndLossOut"]
export type RevenueSummary = Schemas["RevenueSummaryOut"]
export type ChannelBreakdown = Schemas["ChannelBreakdownOut"]
export type ShippingSummary = Schemas["ShippingSummaryOut"]

/** Whole local days, both ends inclusive (accounting-rules §1). */
export type DateRangeParams = { from: string; to: string }

function rangeQuery(r: DateRangeParams): string {
  return new URLSearchParams({ start_date: r.from, end_date: r.to }).toString()
}

export function getProfitAndLoss(r: DateRangeParams): Promise<ProfitAndLoss> {
  return apiFetch<ProfitAndLoss>(`/reports/profit-and-loss?${rangeQuery(r)}`)
}

/** PENDING/PAID/COMPLETED orders only: count, Σ revenue, Σ per-order profit. */
export function getRevenueSummary(r: DateRangeParams): Promise<RevenueSummary> {
  return apiFetch<RevenueSummary>(`/reports/revenue-summary?${rangeQuery(r)}`)
}

/** Revenue-eligible orders per channel; channels with no orders are omitted. */
export function getChannelBreakdown(r: DateRangeParams): Promise<ChannelBreakdown[]> {
  return apiFetch<ChannelBreakdown[]>(`/reports/channels?${rangeQuery(r)}`)
}

export function getShippingSummary(r: DateRangeParams): Promise<ShippingSummary> {
  return apiFetch<ShippingSummary>(`/reports/shipping?${rangeQuery(r)}`)
}

export type PurchasesSummary = Schemas["PurchasesSummaryOut"]

/** Σ total_paid and count of material / product purchases in range; inventory, not P&L. */
export function getPurchasesSummary(r: DateRangeParams): Promise<PurchasesSummary> {
  return apiFetch<PurchasesSummary>(`/reports/purchases?${rangeQuery(r)}`)
}

// ------------------------------------------------------------ payment methods

export type PaymentMethod = Schemas["PaymentMethodOut"]
export type PaymentMethodCreate = Schemas["PaymentMethodCreate"]
export type PaymentMethodUpdate = Schemas["PaymentMethodUpdate"]
export type FeePreview = Schemas["FeePreviewOut"]

/** Sorted by name; inactive methods only when asked. Each carries pending_order_count. */
export function listPaymentMethods(includeInactive = false): Promise<PaymentMethod[]> {
  return apiFetch<PaymentMethod[]>(`/payment-methods?include_inactive=${includeInactive}`)
}

export function createPaymentMethod(body: PaymentMethodCreate): Promise<PaymentMethod> {
  return apiFetch<PaymentMethod>("/payment-methods", { method: "POST", body: JSON.stringify(body) })
}

/** Only the fields present change. A rule or days change while orders are pending is a 409. */
export function updatePaymentMethod(id: number, patch: PaymentMethodUpdate): Promise<PaymentMethod> {
  return apiFetch<PaymentMethod>(`/payment-methods/${id}`, { method: "PATCH", body: JSON.stringify(patch) })
}

export function deactivatePaymentMethod(id: number): Promise<PaymentMethod> {
  return apiFetch<PaymentMethod>(`/payment-methods/${id}/deactivate`, { method: "POST" })
}

export function reactivatePaymentMethod(id: number): Promise<PaymentMethod> {
  return apiFetch<PaymentMethod>(`/payment-methods/${id}/reactivate`, { method: "POST" })
}

/** The fee the method charges on a customer_total of `amount` (integer Rial), computed by the backend. */
export function getFeePreview(id: number, amount: number, signal?: AbortSignal): Promise<FeePreview> {
  return apiFetch<FeePreview>(`/payment-methods/${id}/fee-preview?amount=${amount}`, { signal })
}
