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

/** Forward move only: DRAFT → PENDING/PAID/COMPLETED, PENDING → PAID/COMPLETED, PAID → COMPLETED. */
export function changeOrderStatus(orderId: number, status: string): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/orders/${orderId}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
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
