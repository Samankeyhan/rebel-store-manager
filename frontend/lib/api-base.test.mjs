// Run with `npm test`. The one-process server (api/serve.py) is built with NEXT_PUBLIC_API_URL=/api:
// every request must go to "/api/..." with no double slash, and nothing may need `new URL(base)`.
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { join } from "node:path"
import { DEFAULT_API_URL, apiBase, apiUrl } from "./api-base.ts"

test("the one-process build: the base is /api and requests have a single slash", () => {
  const base = apiBase("/api")
  assert.equal(base, "/api")
  assert.equal(apiUrl(base, "/health"), "/api/health")
  assert.equal(apiUrl(base, "/orders?status=PAID&from=2026-01-01"), "/api/orders?status=PAID&from=2026-01-01")
  assert.equal(apiUrl(base, "/orders/12/invoice.pdf"), "/api/orders/12/invoice.pdf")
})

test("trailing slashes on the base and leading slashes on the path never double up", () => {
  assert.equal(apiBase("/api/"), "/api")
  assert.equal(apiBase("/api///"), "/api")
  assert.equal(apiUrl("/api/", "/health"), "/api/health")
  assert.equal(apiUrl("/api", "health"), "/api/health")
  assert.equal(apiUrl("/api", "//health"), "/api/health")
  assert.equal(apiUrl(apiBase("http://localhost:8000/"), "/orders/3/invoice.pdf"), "http://localhost:8000/orders/3/invoice.pdf")
})

test("an unset variable keeps the development address; an empty one means the page's own origin", () => {
  assert.equal(apiBase(undefined), DEFAULT_API_URL)
  assert.equal(DEFAULT_API_URL, "http://localhost:8000")
  assert.equal(apiUrl(apiBase(""), "/health"), "/health")
})

test("the base is used as plain text: no URL object needs an origin", () => {
  // `new URL("/api/health")` throws without a base; building the string must not.
  assert.doesNotThrow(() => apiUrl("/api", "/health"))
  assert.throws(() => new URL("/api/health"))
})

test("nothing in the frontend source builds a URL object from the API base", () => {
  const walk = (dir) =>
    readdirSync(dir).flatMap((name) => {
      const path = join(dir, name)
      if (name === "node_modules" || name === ".next" || name === "out") return []
      return statSync(path).isDirectory() ? walk(path) : /\.(ts|tsx)$/.test(name) ? [path] : []
    })
  const offenders = [...walk("lib"), ...walk("components"), ...walk("app"), ...walk("hooks")].filter((file) =>
    /new URL\(/.test(readFileSync(file, "utf8"))
  )
  assert.deepEqual(offenders, [])
})

test("api.ts builds every request and the invoice link through apiUrl", () => {
  const source = readFileSync("lib/api.ts", "utf8")
  assert.match(source, /apiUrl\(API_URL, path\)/)
  assert.match(source, /apiUrl\(API_URL, `\/orders\/\$\{orderId\}\/invoice\.pdf`\)/)
  assert.doesNotMatch(source, /\$\{API_URL\}\$\{path\}/)
})
