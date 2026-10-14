/**
 * The address of the API. Development: `NEXT_PUBLIC_API_URL` (default http://localhost:8000). The one-process server
 * (api/serve.py) serves the screens and the API on one origin and the screens are built with NEXT_PUBLIC_API_URL=/api,
 * so the base can be a relative path: requests are then made to "/api/..." on whatever port the page came from.
 * No URL object is ever built from the base (a relative base has no origin to parse against).
 */

export const DEFAULT_API_URL = "http://localhost:8000"

/** The base without trailing slashes ("/api/" -> "/api"); an unset variable falls back to the development address. */
export function apiBase(raw: string | undefined): string {
  return (raw ?? DEFAULT_API_URL).replace(/\/+$/, "")
}

/** base + path with exactly one slash between them (a path always starts with "/"). */
export function apiUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`
}
